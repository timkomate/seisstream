#ifndef CONSUMER_PG_CLIENT_H
#define CONSUMER_PG_CLIENT_H

#include <postgresql/libpq-fe.h>

PGconn *pg_connect_client(const char *conninfo);
int pg_begin_copy(PGconn *pg);
int pg_abort_copy(PGconn *pg, const char *errmsg);
int pg_finish_copy(PGconn *pg);

#endif /* CONSUMER_PG_CLIENT_H */
