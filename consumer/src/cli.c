#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "consumer_cli.h"

int
parse_args(int argc, char **argv, ConsumerConfig *config)
{
  if (!config)
    return -1;

  for (int i = 1; i < argc; ++i)
  {
    if (strcmp(argv[i], "-h") == 0 && i + 1 < argc)
      config->host = argv[++i];
    else if (strcmp(argv[i], "-p") == 0 && i + 1 < argc)
      config->port = atoi(argv[++i]);
    else if (strcmp(argv[i], "-u") == 0 && i + 1 < argc)
      config->user = argv[++i];
    else if (strcmp(argv[i], "-P") == 0 && i + 1 < argc)
      config->pass = argv[++i];
    else if (strcmp(argv[i], "-v") == 0 && i + 1 < argc)
      config->vhost = argv[++i];
    else if (strcmp(argv[i], "-q") == 0 && i + 1 < argc)
      config->queue = argv[++i];
    else if (strcmp(argv[i], "--prefetch") == 0 && i + 1 < argc)
      config->prefetch = atoi(argv[++i]);
    else if (strcmp(argv[i], "--verbose") == 0)
      config->verbose = 1;
    else if (strcmp(argv[i], "--pg-host") == 0 && i + 1 < argc)
      config->pg_host = argv[++i];
    else if (strcmp(argv[i], "--pg-port") == 0 && i + 1 < argc)
      config->pg_port = atoi(argv[++i]);
    else if (strcmp(argv[i], "--pg-user") == 0 && i + 1 < argc)
      config->pg_user = argv[++i];
    else if (strcmp(argv[i], "--pg-password") == 0 && i + 1 < argc)
      config->pg_password = argv[++i];
    else if (strcmp(argv[i], "--pg-db") == 0 && i + 1 < argc)
      config->pg_dbname = argv[++i];
    else
    {
      usage(argv[0]);
      return -1;
    }
  }

  return 0;
}

void
usage(const char *progname)
{
  fprintf(stderr,
          "Usage: %s [opts]\n"
          "  -h <host>        (default 127.0.0.1)\n"
          "  -p <port>        (default 5672)\n"
          "  -u <user>        (default guest)\n"
          "  -P <pass>        (default guest)\n"
          "  -v <vhost>       (default /)\n"
          "  -q <queue>       (default binq)\n"
          "  --prefetch <n>   (default 10)\n"
          "  --verbose        (libmseed verbose parsing)\n"
          "  --pg-host h      PostgreSQL host (default 192.168.0.106)\n"
          "  --pg-port n      PostgreSQL port (default 5432)\n"
          "  --pg-user u      PostgreSQL user (default admin)\n"
          "  --pg-password p  PostgreSQL password (default my-secret-pw)\n"
          "  --pg-db name     PostgreSQL database name (default seismic)\n",
          progname);
}
