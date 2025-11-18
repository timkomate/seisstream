#include <string.h>

#include "amqp_client.h"

amqp_connection_state_t
amqp_connect (const AmqpConfig *config)
{
  amqp_connection_state_t conn = amqp_new_connection ();
  amqp_socket_t *socket = NULL;

  if (!conn)
  {
    sl_log (2, 0, "Unable to allocate AMQP connection\n");
    return NULL;
  }

  socket = amqp_tcp_socket_new (conn);
  if (!socket)
  {
    sl_log (2, 0, "Unable to create AMQP TCP socket\n");
    amqp_destroy_connection (conn);
    return NULL;
  }

  {
    int socket_status = amqp_socket_open (socket, config->host, config->port);
    if (socket_status != AMQP_STATUS_OK)
    {
      sl_log (2, 0, "Unable to open AMQP socket %s:%d: %s\n",
              config->host, config->port, amqp_error_string2 (socket_status));
      amqp_destroy_connection (conn);
      return NULL;
    }
  }

  if (amqp_check_rpc_reply ("Logging in to AMQP",
                            amqp_login (conn, config->vhost, 0, 131072, 60,
                                        AMQP_SASL_METHOD_PLAIN, config->user,
                                        config->password)) != 0)
  {
    amqp_destroy_connection (conn);
    return NULL;
  }

  amqp_channel_open (conn, AMQP_CHANNEL);
  if (amqp_check_rpc_reply ("Opening AMQP channel",
                            amqp_get_rpc_reply (conn)) != 0)
  {
    amqp_destroy_connection (conn);
    return NULL;
  }

  sl_log (0, 1, "Connected to AMQP %s:%d, exchange '%s', routing key '%s'\n",
          config->host, config->port,
          config->exchange ? config->exchange : "",
          config->routing_key ? config->routing_key : "");

  return conn;
}

void
amqp_disconnect (amqp_connection_state_t conn)
{
  if (!conn)
    return;

  amqp_check_rpc_reply ("Closing AMQP channel",
                        amqp_channel_close (conn, AMQP_CHANNEL,
                                            AMQP_REPLY_SUCCESS));
  amqp_check_rpc_reply ("Closing AMQP connection",
                        amqp_connection_close (conn, AMQP_REPLY_SUCCESS));
  amqp_destroy_connection (conn);
}

int
amqp_publish_payload (amqp_connection_state_t conn, const AmqpConfig *config,
                      const char *payload, uint32_t payloadlen)
{
  amqp_bytes_t body = {.len = payloadlen, .bytes = (void *)payload};
  amqp_basic_properties_t props;
  int rc;

  memset (&props, 0, sizeof (props));
  props._flags |= AMQP_BASIC_CONTENT_TYPE_FLAG;
  props.content_type = amqp_cstring_bytes ("application/octet-stream");

  rc = amqp_basic_publish (conn, AMQP_CHANNEL,
                           amqp_cstring_bytes (config->exchange ? config->exchange : ""),
                           amqp_cstring_bytes (config->routing_key ? config->routing_key : ""),
                           0, 0, &props, body);

  if (rc != AMQP_STATUS_OK)
  {
    sl_log (2, 0, "amqp_basic_publish failed: %s\n", amqp_error_string2 (rc));
    return -1;
  }

  return 0;
}

int
amqp_check_rpc_reply (const char *context, amqp_rpc_reply_t reply)
{
  if (reply.reply_type == AMQP_RESPONSE_NORMAL)
    return 0;

  if (reply.reply_type == AMQP_RESPONSE_LIBRARY_EXCEPTION)
  {
    sl_log (2, 0, "%s: %s\n", context, amqp_error_string2 (reply.library_error));
  }
  else if (reply.reply_type == AMQP_RESPONSE_SERVER_EXCEPTION)
  {
    log_amqp_server_exception (context, reply);
  }
  else
  {
    sl_log (2, 0, "%s: Unknown AMQP reply type %d\n",
            context, reply.reply_type);
  }

  return -1;
}

void
log_amqp_server_exception (const char *context, amqp_rpc_reply_t reply)
{
  switch (reply.reply.id)
  {
  case AMQP_CONNECTION_CLOSE_METHOD:
  {
    amqp_connection_close_t *m = reply.reply.decoded;
    sl_log (2, 0, "%s: server connection error %u, message: %.*s\n",
            context, m->reply_code, (int)m->reply_text.len,
            (char *)m->reply_text.bytes);
    break;
  }
  case AMQP_CHANNEL_CLOSE_METHOD:
  {
    amqp_channel_close_t *m = reply.reply.decoded;
    sl_log (2, 0, "%s: server channel error %u, message: %.*s\n",
            context, m->reply_code, (int)m->reply_text.len,
            (char *)m->reply_text.bytes);
    break;
  }
  default:
    sl_log (2, 0, "%s: server exception method 0x%08X\n",
            context, reply.reply.id);
  }
}
