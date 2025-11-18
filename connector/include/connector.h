#ifndef CONNECTOR_H
#define CONNECTOR_H

#include <inttypes.h>
#include <stdint.h>

#include <amqp.h>
#include <amqp_framing.h>
#include <amqp_tcp_socket.h>
#include <libslink.h>

#define PACKAGE "slclient"
#define VERSION LIBSLINK_VERSION

#define DEFAULT_PAYLOAD_BUFFER 16384
#define AMQP_CHANNEL 1
#define PAYLOAD_PREVIEW_BYTES 32

typedef struct
{
  const char *host;
  int port;
  const char *user;
  const char *password;
  const char *vhost;
  const char *exchange;
  const char *routing_key;
} AmqpConfig;

extern AmqpConfig amqp_cfg;
extern short int verbose;
extern short int ppackets;
extern char *statefile;

#endif /* CONNECTOR_H */
