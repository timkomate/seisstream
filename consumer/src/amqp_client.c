#include <stdio.h>
#include <unistd.h>

#include <amqp_tcp_socket.h>

#include "consumer_amqp_client.h"

static void log_amqp_server_exception(const char *context, amqp_rpc_reply_t reply);
static int amqp_check_rpc_reply(const char *context, amqp_rpc_reply_t reply);

static amqp_connection_state_t
amqp_connect_once(const ConsumerConfig *config)
{
  amqp_connection_state_t conn = NULL;
  amqp_socket_t *socket = NULL;
  int declare_exchange = 0;

  if (!config)
  {
    fprintf(stderr, "amqp_connect: config is NULL\n");
    return NULL;
  }

  declare_exchange = (config->exchange && *config->exchange);

  conn = amqp_new_connection();
  if (!conn)
  {
    fprintf(stderr, "amqp_new_connection failed\n");
    return NULL;
  }

  socket = amqp_tcp_socket_new(conn);
  if (!socket)
  {
    fprintf(stderr, "amqp_tcp_socket_new failed\n");
    amqp_destroy_connection(conn);
    return NULL;
  }

  if (amqp_socket_open(socket, config->host, config->port))
  {
    fprintf(stderr, "Socket open to %s:%d failed\n", config->host, config->port);
    amqp_destroy_connection(conn);
    return NULL;
  }

  if (amqp_check_rpc_reply("Logging in to AMQP",
                           amqp_login(conn, config->vhost, 0, 131072, 60,
                                      AMQP_SASL_METHOD_PLAIN, config->user, config->pass)) != 0)
  {
    amqp_destroy_connection(conn);
    return NULL;
  }

  amqp_channel_open(conn, 1);
  if (amqp_check_rpc_reply("Opening AMQP channel", amqp_get_rpc_reply(conn)) != 0)
  {
    amqp_disconnect(conn);
    return NULL;
  }

  amqp_basic_qos(conn, 1, 0, config->prefetch, 0);
  if (amqp_check_rpc_reply("basic.qos", amqp_get_rpc_reply(conn)) != 0)
  {
    amqp_disconnect(conn);
    return NULL;
  }

  if (declare_exchange)
  {
    amqp_exchange_declare(conn, 1,
                          amqp_cstring_bytes(config->exchange),
                          amqp_cstring_bytes("topic"),
                          0, 1, 0, 0, amqp_empty_table);
    if (amqp_check_rpc_reply("Exchange declare", amqp_get_rpc_reply(conn)) != 0)
    {
      amqp_disconnect(conn);
      return NULL;
    }
  }

  amqp_queue_declare_ok_t *qok = amqp_queue_declare(conn, 1,
      amqp_cstring_bytes(config->queue), 0, 0, 0, 0, amqp_empty_table);
  if (amqp_check_rpc_reply("Queue declare", amqp_get_rpc_reply(conn)) != 0 || qok == NULL)
  {
    amqp_disconnect(conn);
    return NULL;
  }

  if (declare_exchange)
  {
    amqp_queue_bind(conn, 1,
                    amqp_cstring_bytes(config->queue),
                    amqp_cstring_bytes(config->exchange),
                    amqp_cstring_bytes(config->binding_key),
                    amqp_empty_table);
    if (amqp_check_rpc_reply("Queue bind", amqp_get_rpc_reply(conn)) != 0)
    {
      amqp_disconnect(conn);
      return NULL;
    }
  }

  amqp_basic_consume(conn, 1, amqp_cstring_bytes(config->queue),
                     amqp_empty_bytes, 0, 0, 0, amqp_empty_table);
  if (amqp_check_rpc_reply("basic.consume", amqp_get_rpc_reply(conn)) != 0)
  {
    amqp_disconnect(conn);
    return NULL;
  }

  return conn;
}

amqp_connection_state_t
amqp_connect(const ConsumerConfig *config)
{
  const uint32_t max_attempts = 20;
  const uint32_t max_delay_s = 60;
  uint32_t attempt = 0;
  uint32_t delay_s;

  while (1)
  {
    if (attempt >= max_attempts)
      break;

    amqp_connection_state_t conn = amqp_connect_once(config);
    if (conn)
      return conn;

    delay_s = 1 << attempt;
    if (delay_s > max_delay_s)
      delay_s = max_delay_s;

    fprintf(stderr, "AMQP connect attempt %u failed, retrying in %u s\n",
            attempt + 1, delay_s);
    sleep(delay_s);
    attempt++;
  }

  return NULL;
}

void
amqp_disconnect(amqp_connection_state_t conn)
{
  if (!conn)
    return;

  amqp_check_rpc_reply("Closing AMQP channel",
                        amqp_channel_close(conn, 1, AMQP_REPLY_SUCCESS));
  amqp_check_rpc_reply("Closing AMQP connection",
                        amqp_connection_close(conn, AMQP_REPLY_SUCCESS));
  amqp_destroy_connection(conn);
}

static int
amqp_check_rpc_reply(const char *context, amqp_rpc_reply_t reply)
{
  if (reply.reply_type == AMQP_RESPONSE_NORMAL)
    return 0;

  if (reply.reply_type == AMQP_RESPONSE_LIBRARY_EXCEPTION)
  {
    fprintf(stderr, "%s: %s\n", context, amqp_error_string2(reply.library_error));
  }
  else if (reply.reply_type == AMQP_RESPONSE_SERVER_EXCEPTION)
  {
    log_amqp_server_exception(context, reply);
  }
  else
  {
    fprintf(stderr, "%s: Unknown AMQP reply type %d\n", context, reply.reply_type);
  }

  return -1;
}

static void
log_amqp_server_exception(const char *context, amqp_rpc_reply_t reply)
{
  switch (reply.reply.id)
  {
  case AMQP_CONNECTION_CLOSE_METHOD:
  {
    amqp_connection_close_t *m = reply.reply.decoded;
    fprintf(stderr, "%s: server connection error %u, message: %.*s\n",
            context, m->reply_code, (int)m->reply_text.len,
            (char *)m->reply_text.bytes);
    break;
  }
  case AMQP_CHANNEL_CLOSE_METHOD:
  {
    amqp_channel_close_t *m = reply.reply.decoded;
    fprintf(stderr, "%s: server channel error %u, message: %.*s\n",
            context, m->reply_code, (int)m->reply_text.len,
            (char *)m->reply_text.bytes);
    break;
  }
  default:
    fprintf(stderr, "%s: server exception method 0x%08X\n",
            context, reply.reply.id);
  }
}
