#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "auth.h"
#include "cli.h"

int
parameter_proc (SLCD *slconn, int argcount, char **argvec)
{
  int optind;
  int error = 0;

  char *server_address = NULL;
  char *streamfile     = NULL;
  char *multiselect    = NULL;
  char *selectors      = NULL;

  if (argcount <= 1)
    error++;

  /* Process all command line arguments */
  for (optind = 1; optind < argcount; optind++)
  {
    if (strcmp (argvec[optind], "-V") == 0)
    {
      fprintf (stderr, "%s version: %s\n", PACKAGE, VERSION);
      exit (0);
    }
    else if (strcmp (argvec[optind], "-h") == 0)
    {
      usage ();
      exit (0);
    }
    else if (strncmp (argvec[optind], "-v", 2) == 0)
    {
      verbose += strspn (&argvec[optind][1], "v");
    }
    else if (strcmp (argvec[optind], "-p") == 0)
    {
      ppackets = 1;
    }
    else if (strcmp (argvec[optind], "-Ap") == 0)
    {
      sl_set_auth_params (slconn, auth_value_userpass, auth_finish, NULL);
    }
    else if (strcmp (argvec[optind], "-At") == 0)
    {
      sl_set_auth_params (slconn, auth_value_token, auth_finish, NULL);
    }
    else if (strcmp (argvec[optind], "-nt") == 0)
    {
      sl_set_idletimeout (slconn, atoi (argvec[++optind]));
    }
    else if (strcmp (argvec[optind], "-nd") == 0)
    {
      sl_set_reconnectdelay (slconn, atoi (argvec[++optind]));
    }
    else if (strcmp (argvec[optind], "-k") == 0)
    {
      sl_set_keepalive (slconn, atoi (argvec[++optind]));
    }
    else if (strcmp (argvec[optind], "-l") == 0)
    {
      streamfile = argvec[++optind];
    }
    else if (strcmp (argvec[optind], "-s") == 0)
    {
      selectors = argvec[++optind];
    }
    else if (strcmp (argvec[optind], "-S") == 0)
    {
      multiselect = argvec[++optind];
    }
    else if (strcmp (argvec[optind], "-x") == 0)
    {
      statefile = argvec[++optind];
    }
    else if (strcmp (argvec[optind], "--amqp-host") == 0)
    {
      const char *option = argvec[optind];
      amqp_cfg.host = require_argument (option, argcount, argvec, &optind);
    }
    else if (strcmp (argvec[optind], "--amqp-port") == 0)
    {
      const char *option = argvec[optind];
      const char *value = require_argument (option, argcount, argvec, &optind);
      amqp_cfg.port = parse_port (option, value);
    }
    else if (strcmp (argvec[optind], "--amqp-user") == 0)
    {
      const char *option = argvec[optind];
      amqp_cfg.user = require_argument (option, argcount, argvec, &optind);
    }
    else if (strcmp (argvec[optind], "--amqp-password") == 0)
    {
      const char *option = argvec[optind];
      amqp_cfg.password = require_argument (option, argcount, argvec, &optind);
    }
    else if (strcmp (argvec[optind], "--amqp-vhost") == 0)
    {
      const char *option = argvec[optind];
      amqp_cfg.vhost = require_argument (option, argcount, argvec, &optind);
    }
    else if (strcmp (argvec[optind], "--amqp-exchange") == 0)
    {
      const char *option = argvec[optind];
      amqp_cfg.exchange = require_argument (option, argcount, argvec, &optind);
    }
    else if (strcmp (argvec[optind], "--amqp-routing-key") == 0)
    {
      const char *option = argvec[optind];
      const char *value = require_argument (option, argcount, argvec, &optind);
      /* Empty string means: use per-packet source ID as routing key */
      amqp_cfg.routing_key = (*value == '\0') ? NULL : value;
    }
    else if (strncmp (argvec[optind], "-", 1) == 0)
    {
      fprintf (stderr, "Unknown option: %s\n", argvec[optind]);
      exit (1);
    }
    else if (server_address == NULL)
    {
      server_address = argvec[optind];
    }
    else
    {
      fprintf (stderr, "Unknown option: %s\n", argvec[optind]);
      exit (1);
    }
  }

  /* Make sure a server was specified */
  if (server_address == NULL)
  {
    fprintf (stderr, "%s version: %s\n\n", PACKAGE, VERSION);
    fprintf (stderr, "No SeedLink server specified\n\n");
    fprintf (stderr, "Usage: %s [options] [host][:port]\n", PACKAGE);
    fprintf (stderr, "Try '-h' for detailed help\n");
    exit (1);
  }

  sl_set_serveraddress (slconn, server_address);

  /* Initialize the verbosity for the sl_log function */
  sl_loginit (verbose, NULL, NULL, NULL, NULL);

  /* Report the program version */
  sl_log (0, 1, "%s version: %s\n", PACKAGE, VERSION);

  /* If errors then report the usage message and quit */
  if (error)
  {
    usage ();
    exit (1);
  }

  /* Load the stream list from a file if specified */
  if (streamfile)
    sl_add_streamlist_file (slconn, streamfile, selectors);

  /* Parse the 'multiselect' string following '-S' */
  if (multiselect)
  {
    if (sl_add_streamlist (slconn, multiselect, selectors) == -1)
      return -1;
  }
  else if (!streamfile)
  { /* No 'streams' array, assuming all-station mode */
    sl_set_allstation_params (slconn, selectors, SL_UNSETSEQUENCE, NULL);
  }

  /* Attempt to recover sequence numbers from state file */
  if (statefile)
  {
    if (sl_recoverstate (slconn, statefile) < 0)
    {
      sl_log (2, 0, "state recovery failed\n");
    }
  }

  return 0;
}

void
usage (void)
{
  fprintf (stderr, "\nUsage: %s [options] [host][:port]\n\n", PACKAGE);
  fprintf (stderr,
           " ## General program options ##\n"
           " -V             report program version\n"
           " -h             show this usage message\n"
           " -v             be more verbose, multiple flags can be used\n"
           " -p             print details of data packets\n"
           " -Ap            prompt for authentication user/password (v4 only)\n"
           " -At            prompt for authentication token (v4 only)\n"
           "\n"
           " -nd delay      network re-connect delay (seconds), default 30\n"
           " -nt timeout    network timeout (seconds), re-establish connection if no\n"
           "                  data/keepalives are received in this time, default 600\n"
           " -k interval    send keepalive packets this often (seconds)\n"
           " -x statefile   save/restore stream state information to this file\n"
           "\n"
           " ## Data stream selection ##\n"
           " -l listfile    read a stream list from this file for multi-station mode\n"
           " -s selectors   selectors for all-station or default for multi-station\n"
           " -S streams     select streams for multi-station\n"
           "   'streams' = 'stream1[:selectors1],stream2[:selectors2],...'\n"
           "        'stream' is in NET_STA format, for example:\n"
           "        -S \"IU_COLA:BHE BHN,GE_WLF,MN_AQU:HH?\"\n"
           "\n"
           " ## AMQP options ##\n"
           " --amqp-host host     AMQP broker host (default 127.0.0.1)\n"
           " --amqp-port port     AMQP broker port (default 5672)\n"
           " --amqp-user user     AMQP username (default guest)\n"
           " --amqp-password pass AMQP password (default guest)\n"
           " --amqp-vhost vhost   AMQP vhost (default /)\n"
           " --amqp-exchange exch AMQP exchange to publish to (default empty)\n"
           " --amqp-routing-key k AMQP routing key / queue (default binq; pass empty \"\" to use source ID)\n"
           "\n"
           " [host][:port]        Address of the SeedLink server in host:port format\n"
           "                        if host is omitted (i.e. ':18000'), localhost is assumed\n"
           "                        if :port is omitted (i.e. 'localhost'), 18000 is assumed\n"
           "\n");
}

char *
require_argument (const char *option, int argcount, char **argvec, int *index)
{
  if ((*index + 1) >= argcount)
  {
    fprintf (stderr, "Option %s requires an argument\n", option);
    exit (1);
  }

  (*index)++;
  return argvec[*index];
}

int
parse_port (const char *option, const char *value)
{
  char *endptr = NULL;
  long parsed = strtol (value, &endptr, 10);

  if (endptr == value || *endptr != '\0' || parsed <= 0 || parsed > INT_MAX)
  {
    fprintf (stderr, "Invalid numeric value for %s: %s\n", option, value);
    exit (1);
  }

  return (int)parsed;
}
