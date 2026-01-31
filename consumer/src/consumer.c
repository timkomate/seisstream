#include <amqp.h>
#include <amqp_framing.h>
#include <amqp_tcp_socket.h>

#include <libmseed.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <inttypes.h>
#include <sys/time.h>
#include <signal.h>
#include <time.h>

#include "consumer.h"
#include "consumer_amqp_client.h"
#include "consumer_cli.h"
#include "mseed.h"
#include "pg_client.h"

volatile sig_atomic_t g_run = 1;

static void on_sig(int sig) { (void)sig; g_run = 0; }

void
register_signal_handlers(void)
{
  signal(SIGINT, on_sig);
  signal(SIGTERM, on_sig);
}

static void
cleanup_connections(PGconn *pg, amqp_connection_state_t amqp_conn)
{
  if (pg)
    PQfinish(pg);
  if (amqp_conn)
  {
    amqp_disconnect (amqp_conn);
  }
}

int
main(int argc, char **argv)
{
  ConsumerConfig config = {
    .host = "127.0.0.1",
    .port = 5672,
    .user = "guest",
    .pass = "guest",
    .vhost = "/",
    .exchange = "",
    .queue = "binq",
    .binding_key = "binq",
    .prefetch = 10,
    .verbose = 1,
    .pg_host = "localhost",
    .pg_port = 5432,
    .pg_user = "admin",
    .pg_password = "my-secret-pw",
    .pg_dbname = "seismic"
  };

  if (parse_args(argc, argv, &config) != 0)
    return 1;

  register_signal_handlers();

  fprintf(stderr,
          "Config: amqp=%s:%d vhost=%s exchange=%s queue=%s binding=%s prefetch=%d\n",
          config.host ? config.host : "(null)",
          config.port,
          config.vhost ? config.vhost : "(null)",
          (config.exchange && *config.exchange) ? config.exchange : "(default)",
          config.queue ? config.queue : "(null)",
          (config.binding_key && *config.binding_key) ? config.binding_key : "(default)",
          config.prefetch);
  fprintf(stderr,
          "Config: pg_host=%s pg_port=%d pg_user=%s pg_db=%s\n",
          config.pg_host ? config.pg_host : "(null)",
          config.pg_port,
          config.pg_user ? config.pg_user : "(null)",
          config.pg_dbname ? config.pg_dbname : "(null)");

  uint32_t flags = 0;
  flags |= MSF_VALIDATECRC;
  flags |= MSF_PNAMERANGE;
  flags |= MSF_UNPACKDATA;

  PGconn *pg = NULL;
  amqp_connection_state_t amqp_conn = NULL;

  char pg_conninfo[256];
  int n = snprintf(pg_conninfo, sizeof pg_conninfo,
                   "dbname=%s user=%s password=%s host=%s port=%d",
                   config.pg_dbname ? config.pg_dbname : "",
                   config.pg_user ? config.pg_user : "",
                   config.pg_password ? config.pg_password : "",
                   config.pg_host ? config.pg_host : "192.168.0.106",
                   config.pg_port);
  if (n < 0 || n >= (int)sizeof pg_conninfo)
  {
    fprintf(stderr, "pg conninfo too long\n");
  }
  else
  {
    fprintf(stderr, "Connecting to %s\n", pg_conninfo);
    pg = pg_connect_client(pg_conninfo);
  }

  if (!pg)
  {
    fprintf(stderr, "Unable to connect to PostgreSQL\n");
    fprintf(stderr, "[consumer] Closed.\n");
    cleanup_connections(pg, amqp_conn);
    return 1;
  }

  amqp_conn = amqp_connect(&config);
  if (!amqp_conn)
  {
    fprintf(stderr, "Unable to establish AMQP connection\n");
    cleanup_connections(pg, amqp_conn);
    fprintf(stderr, "[consumer] Closed.\n");
    return 1;
  }

  fprintf(stderr, "[consumer] Waiting on queue '%s'... Ctrl-C to stop.\n", config.queue);

  while (g_run)
  {
    amqp_envelope_t env;
    struct timeval timeout = {.tv_sec = 1, .tv_usec = 0};
    amqp_maybe_release_buffers(amqp_conn);

    amqp_rpc_reply_t rc = amqp_consume_message(amqp_conn, &env, &timeout, 0);
    if (rc.reply_type == AMQP_RESPONSE_NORMAL)
    {
      const unsigned char *body = (const unsigned char *)env.message.body.bytes;
      size_t len = (size_t)env.message.body.len;

      fprintf(stderr,
              "Received message: delivery_tag=%" PRIu64 " exchange=%.*s routing_key=%.*s body_len=%zu\n",
              env.delivery_tag,
              (int)env.exchange.len, (char *)env.exchange.bytes,
              (int)env.routing_key.len, (char *)env.routing_key.bytes,
              len);

      if (process_message(body, (int64_t)len, flags, config.verbose, pg) != 0)
      {
        fprintf(stderr, "MiniSEED parse failed (len=%zu)\n", len);
        hex_preview(body, len, PAYLOAD_PREVIEW_BYTES);
      }
      else
      {
        fprintf(stderr, "Processed message (len=%zu)\n", len);
      }

      amqp_basic_ack(amqp_conn, 1, env.delivery_tag, 0);
      fprintf(stderr, "Acked delivery_tag=%" PRIu64 "\n", env.delivery_tag);
      amqp_destroy_envelope(&env);
    }
    else if (rc.reply_type == AMQP_RESPONSE_LIBRARY_EXCEPTION &&
             rc.library_error == AMQP_STATUS_TIMEOUT)
    {
      continue;
    }
    else
    {
      fprintf(stderr, "consume_message failed: reply_type=%d liberr=%d\n",
              rc.reply_type, rc.library_error);
      break;
    }
  }

  cleanup_connections(pg, amqp_conn);

  fprintf(stderr, "[consumer] Closed.\n");
  return 0;
}
