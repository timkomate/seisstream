#include <amqp.h>
#include <amqp_framing.h>
#include <amqp_tcp_socket.h>

#include <libmseed.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/time.h>
#include <signal.h>
#include <time.h>

#include "consumer.h"
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

static void cleanup_connections(PGconn *pg,
                                amqp_connection_state_t conn,
                                int channel_open,
                                int amqp_logged_in)
{
  if (pg)
    PQfinish(pg);
  if (channel_open && conn)
    amqp_channel_close(conn, 1, AMQP_REPLY_SUCCESS);
  if (amqp_logged_in && conn)
    amqp_connection_close(conn, AMQP_REPLY_SUCCESS);
  if (conn)
    amqp_destroy_connection(conn);
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
    .verbose = 0,
    .pg_host = "localhost",
    .pg_port = 5432,
    .pg_user = "admin",
    .pg_password = "my-secret-pw",
    .pg_dbname = "seismic"
  };

  if (parse_args(argc, argv, &config) != 0)
    return 1;

  register_signal_handlers();

  uint32_t flags = 0;
  flags |= MSF_VALIDATECRC;
  flags |= MSF_PNAMERANGE;
  flags |= MSF_UNPACKDATA;

  int exit_code = 1;
  PGconn *pg = NULL;
  amqp_connection_state_t conn = NULL;
  amqp_socket_t *sock = NULL;
  int amqp_logged_in = 0;
  int channel_open = 0;

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
    ms_log(0, "Connecting to %s\n", pg_conninfo);
    pg = pg_connect_client(pg_conninfo);
  }

  if (!pg)
  {
    fprintf(stderr, "Unable to connect to PostgreSQL\n");
  }
  else if (!(conn = amqp_new_connection()))
  {
    fprintf(stderr, "amqp_new_connection failed\n");
  }
  else if (!(sock = amqp_tcp_socket_new(conn)))
  {
    fprintf(stderr, "Socket alloc failed\n");
  }
  else if (amqp_socket_open(sock, config.host, config.port))
  {
    fprintf(stderr, "Socket open to %s:%d failed\n", config.host, config.port);
  }
  else
  {
    amqp_rpc_reply_t r = amqp_login(conn, config.vhost, 0, 131072, 60,
                                    AMQP_SASL_METHOD_PLAIN, config.user, config.pass);
    if (r.reply_type != AMQP_RESPONSE_NORMAL)
    {
      fprintf(stderr, "Login failed: reply_type=%d\n", r.reply_type);
    }
    else
    {
      amqp_logged_in = 1;

      amqp_channel_open(conn, 1);
      r = amqp_get_rpc_reply(conn);
      if (r.reply_type != AMQP_RESPONSE_NORMAL)
      {
        fprintf(stderr, "Channel open failed: reply_type=%d\n", r.reply_type);
      }
      else
      {
        channel_open = 1;

        amqp_basic_qos(conn, 1, 0, config.prefetch, 0);
        r = amqp_get_rpc_reply(conn);
        if (r.reply_type != AMQP_RESPONSE_NORMAL)
        {
          fprintf(stderr, "basic.qos failed: reply_type=%d\n", r.reply_type);
        }
        else
        {
          int declare_exchange = (config.exchange && *config.exchange);

          if (declare_exchange)
          {
            amqp_exchange_declare(conn, 1,
                                  amqp_cstring_bytes(config.exchange),
                                  amqp_cstring_bytes("topic"),
                                  0, 1, 0, 0, amqp_empty_table);
            r = amqp_get_rpc_reply(conn);
            if (r.reply_type != AMQP_RESPONSE_NORMAL)
            {
              fprintf(stderr, "Exchange declare failed: reply_type=%d\n", r.reply_type);
            }
          }

          amqp_queue_declare_ok_t *qok = amqp_queue_declare(conn, 1,
              amqp_cstring_bytes(config.queue), 0, 0, 0, 0, amqp_empty_table);
          r = amqp_get_rpc_reply(conn);
          if (r.reply_type != AMQP_RESPONSE_NORMAL || qok == NULL)
          {
            fprintf(stderr, "Queue declare failed: reply_type=%d\n", r.reply_type);
          }
          else
          {
            if (declare_exchange)
            {
              amqp_queue_bind(conn, 1,
                              amqp_cstring_bytes(config.queue),
                              amqp_cstring_bytes(config.exchange),
                              amqp_cstring_bytes(config.binding_key),
                              amqp_empty_table);
              r = amqp_get_rpc_reply(conn);
              if (r.reply_type != AMQP_RESPONSE_NORMAL)
              {
                fprintf(stderr, "Queue bind failed: reply_type=%d\n", r.reply_type);
              }
            }

            amqp_basic_consume(conn, 1, amqp_cstring_bytes(config.queue),
                               amqp_empty_bytes, 0, 0, 0, amqp_empty_table);
            r = amqp_get_rpc_reply(conn);
            if (r.reply_type != AMQP_RESPONSE_NORMAL)
            {
              fprintf(stderr, "basic.consume failed: reply_type=%d\n", r.reply_type);
            }
            else
            {
              printf("[consumer] Waiting on queue '%s'… Ctrl-C to stop.\n", config.queue);
              exit_code = 0;

              while (g_run)
              {
                amqp_envelope_t env;
                struct timeval timeout = {.tv_sec = 1, .tv_usec = 0};
                amqp_maybe_release_buffers(conn);

                amqp_rpc_reply_t rc = amqp_consume_message(conn, &env, &timeout, 0);
                if (rc.reply_type == AMQP_RESPONSE_NORMAL)
                {
                  const unsigned char *body = (const unsigned char *)env.message.body.bytes;
                  size_t len = (size_t)env.message.body.len;

                  if (process_message(body, (int64_t)len, flags, config.verbose, pg) != 0)
                  {
                    fprintf(stderr, "MiniSEED parse failed (len=%zu)\n", len);
                    hex_preview(body, len, PAYLOAD_PREVIEW_BYTES);
                  }

                  amqp_basic_ack(conn, 1, env.delivery_tag, 0);
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
            }
          }
        }
      }
    }
  }

  cleanup_connections(pg, conn, channel_open, amqp_logged_in);

  printf("[consumer] Closed.\n");
  return exit_code;
}
