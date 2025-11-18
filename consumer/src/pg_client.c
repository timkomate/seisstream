#include <stdio.h>

#include <libmseed.h>

#include "pg_client.h"

PGconn *
pg_connect_client(const char *conninfo)
{
  PGconn *pg = PQconnectdb(conninfo);

  if (!pg)
  {
    fprintf(stderr, "PQconnectdb returned NULL\n");
    return NULL;
  }

  if (PQstatus(pg) != CONNECTION_OK)
  {
    fprintf(stderr, "PostgreSQL connection failed: %s\n", PQerrorMessage(pg));
    PQfinish(pg);
    return NULL;
  }

  return pg;
}

int
pg_begin_copy(PGconn *pg)
{
  PGresult *res = PQexec(pg, "BEGIN");
  if (!res)
  {
    ms_log(2, "BEGIN failed: no result\n");
    return -1;
  }
  if (PQresultStatus(res) != PGRES_COMMAND_OK)
  {
    ms_log(2, "BEGIN failed: %s\n", PQerrorMessage(pg));
    PQclear(res);
    return -1;
  }
  PQclear(res);

  res = PQexec(pg,
               "COPY seismic_samples(ts, net, sta, loc, chan, value, sample_rate) "
               "FROM STDIN WITH (FORMAT text)");
  if (!res)
  {
    ms_log(2, "COPY ... FROM STDIN failed: no result\n");
    PGresult *rb = PQexec(pg, "ROLLBACK");
    if (rb)
      PQclear(rb);
    return -1;
  }
  if (PQresultStatus(res) != PGRES_COPY_IN)
  {
    ms_log(2, "COPY ... FROM STDIN failed: %s\n", PQerrorMessage(pg));
    PQclear(res);
    PGresult *rb = PQexec(pg, "ROLLBACK");
    if (rb)
      PQclear(rb);
    return -1;
  }
  PQclear(res);

  return 0;
}

int
pg_abort_copy(PGconn *pg, const char *errmsg)
{
  PGresult *res;

  if (PQputCopyEnd(pg, errmsg) != 1)
  {
    ms_log(2, "PQputCopyEnd failed: %s\n", PQerrorMessage(pg));
  }

  while ((res = PQgetResult(pg)) != NULL)
  {
    PQclear(res);
  }

  res = PQexec(pg, "ROLLBACK");
  if (!res)
  {
    ms_log(2, "ROLLBACK failed: no result\n");
    return -1;
  }
  if (PQresultStatus(res) != PGRES_COMMAND_OK)
  {
    ms_log(2, "ROLLBACK failed: %s\n", PQerrorMessage(pg));
  }
  PQclear(res);

  return -1;
}

int
pg_finish_copy(PGconn *pg)
{
  PGresult *res;

  if (PQputCopyEnd(pg, NULL) != 1)
  {
    ms_log(2, "PQputCopyEnd failed: %s\n", PQerrorMessage(pg));
    res = PQexec(pg, "ROLLBACK");
    if (res)
      PQclear(res);
    return -1;
  }

  while ((res = PQgetResult(pg)) != NULL)
  {
    if (PQresultStatus(res) != PGRES_COMMAND_OK)
    {
      ms_log(2, "COPY result not OK: %s\n", PQerrorMessage(pg));
      PQclear(res);
      res = PQexec(pg, "ROLLBACK");
      if (res)
        PQclear(res);
      return -1;
    }
    PQclear(res);
  }

  res = PQexec(pg, "COMMIT");
  if (!res)
  {
    ms_log(2, "COMMIT failed: no result\n");
    return -1;
  }
  if (PQresultStatus(res) != PGRES_COMMAND_OK)
  {
    ms_log(2, "COMMIT failed: %s\n", PQerrorMessage(pg));
    PQclear(res);
    return -1;
  }
  PQclear(res);

  return 0;
}
