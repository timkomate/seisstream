#ifndef CONNECTOR_AMQP_CLIENT_H
#define CONNECTOR_AMQP_CLIENT_H

#include "connector.h"

amqp_connection_state_t amqp_connect (const AmqpConfig *config);
void amqp_disconnect (amqp_connection_state_t conn);
int amqp_publish_payload (amqp_connection_state_t conn, const AmqpConfig *config,
                          const char *payload, uint32_t payloadlen);
int amqp_check_rpc_reply (const char *context, amqp_rpc_reply_t reply);
void log_amqp_server_exception (const char *context, amqp_rpc_reply_t reply);

#endif /* CONNECTOR_AMQP_CLIENT_H */
