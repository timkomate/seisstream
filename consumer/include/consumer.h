#ifndef CONSUMER_H
#define CONSUMER_H

#include <amqp.h>
#include <signal.h>

typedef struct {
  const char *host;
  int         port;
  const char *user;
  const char *pass;
  const char *vhost;
  const char *exchange;
  const char *queue;
  const char *binding_key;
  int         prefetch;
  int         verbose;
  const char *pg_host;
  int         pg_port;
  const char *pg_user;
  const char *pg_password;
  const char *pg_dbname;
} ConsumerConfig;

#define PAYLOAD_PREVIEW_BYTES 32

extern volatile sig_atomic_t g_run;

void register_signal_handlers(void);

#endif /* CONSUMER_H */
