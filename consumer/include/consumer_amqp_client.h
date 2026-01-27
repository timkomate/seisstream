#ifndef CONSUMER_AMQP_CLIENT_H
#define CONSUMER_AMQP_CLIENT_H

#include "consumer.h"

amqp_connection_state_t amqp_connect(const ConsumerConfig *config);
void amqp_disconnect(amqp_connection_state_t conn);

#endif /* CONSUMER_AMQP_CLIENT_H */
