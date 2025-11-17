/***************************************************************************
 * connector.c
 * A SeedLink client that forwards received packets to an AMQP broker.
 *
 * Based on the SeedLink Library example client `slclient.c`
 * by Chad Trabant (2024, EarthScope Data Services) and licensed under
 * the Apache License, Version 2.0:
 * https://www.apache.org/licenses/LICENSE-2.0
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 ***************************************************************************/

#include <inttypes.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

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

static AmqpConfig amqp_cfg = {
  .host = "127.0.0.1",
  .port = 5672,
  .user = "guest",
  .password = "guest",
  .vhost = "/",
  .exchange = "",
  .routing_key = "binq"
};

static short int verbose = 0;
static short int ppackets = 0;
static char *statefile = NULL;

static char auth_buffer[1024] = {0};

static void packet_handler (SLCD *slconn, const SLpacketinfo *packetinfo,
                            const char *payload, uint32_t payloadlen,
                            amqp_connection_state_t conn);
static int parameter_proc (SLCD *slconn, int argcount, char **argvec);
static const char *auth_value_userpass (const char *server, void *data);
static const char *auth_value_token (const char *server, void *data);
static void auth_finish (const char *server, void *data);
static void usage (void);
static char *require_argument (const char *option, int argcount, char **argvec,
                               int *index);
static int parse_port (const char *option, const char *value);
static amqp_connection_state_t amqp_connect (const AmqpConfig *config);
static void amqp_disconnect (amqp_connection_state_t conn);
static int amqp_publish_payload (amqp_connection_state_t conn,
                                 const AmqpConfig *config,
                                 const char *payload, uint32_t payloadlen);
static int amqp_check_rpc_reply (const char *context,
                                 amqp_rpc_reply_t reply);
static void log_amqp_server_exception (const char *context,
                                       amqp_rpc_reply_t reply);

int
main (int argc, char **argv)
{
  SLCD *slconn = NULL; /* connection parameters */
  const SLpacketinfo *packetinfo = NULL; /* packet information */
  amqp_connection_state_t amqp_conn = NULL;

  char *plbuffer = NULL;
  uint32_t plbuffersize = DEFAULT_PAYLOAD_BUFFER;
  int status = 0;

  /* Allocate and initialize a new connection description */
  slconn = sl_initslcd (PACKAGE, VERSION);

  /* Configure authentication via SEEDLINK_USERNAME and SEEDLINK_PASSWORD
   * environment variables if they are set */
  if (getenv ("SEEDLINK_USERNAME") && getenv ("SEEDLINK_PASSWORD"))
  {
    sl_set_auth_envvars (slconn, "SEEDLINK_USERNAME", "SEEDLINK_PASSWORD");
  }

  /* Process given parameters (command line and parameter file) */
  if (parameter_proc (slconn, argc, argv) < 0)
  {
    fprintf (stderr, "Parameter processing failed\n\n");
    fprintf (stderr, "Try '-h' for detailed help\n");
  }

  /* Set signal handlers to trigger clean connection shutdown */
  if (sl_set_termination_handler (slconn) < 0)
  {
    sl_log (2, 0, "Failed to set termination handler\n");
  }

  /* Establish the AMQP connection */
  amqp_conn = amqp_connect (&amqp_cfg);
  if (!amqp_conn)
  {
    sl_log (2, 0, "Unable to establish AMQP connection\n");
  }

  /* Allocate payload buffer */
  plbuffer = (char *)malloc (plbuffersize);
  if (plbuffer == NULL)
  {
    sl_log (2, 0, "Memory allocation failed\n");
  }

  /* Loop with the connection manager */
  while ((status = sl_collect (slconn, &packetinfo,
                               plbuffer, plbuffersize)) != SLTERMINATE)
  {
    if (status == SLPACKET)
    {
      packet_handler (slconn, packetinfo, plbuffer,
                      packetinfo->payloadcollected, amqp_conn);
    }
    else if (status == SLTOOLARGE)
    {
      /* Here we could increase the payload buffer size to accommodate if desired.
       * If you wish to increase the buffer size be sure to copy any data that might
       * have already been collected from the old buffer to the new.  realloc() does this. */
      sl_log (2, 0, "received payload length %u too large for max buffer of %u\n",
              packetinfo->payloadlength, plbuffersize);

      break;
    }
    else if (status == SLNOPACKET)
    {
      sl_log (0, 2, "sleeping after receiving no data from sl_collect()\n");
      sl_usleep (500000);
    }
  }

  if (amqp_conn)
    amqp_disconnect (amqp_conn);

  if (slconn)
  {
    sl_disconnect (slconn);

    if (statefile)
      sl_savestate (slconn, statefile);

    sl_freeslcd (slconn);
  }

  free (plbuffer);
} /* End of main() */

/***************************************************************************
 * packet_handler():
 * Process a received packet based on packet type.
 ***************************************************************************/
static void
packet_handler (SLCD *slconn, const SLpacketinfo *packetinfo,
                const char *payload, uint32_t payloadlength,
                amqp_connection_state_t conn)
{
  char payloadsummary[128] = {0};
  double dtime;   /* Epoch time */
  double secfrac; /* Fractional part of epoch time */
  time_t itime;   /* Integer part of epoch time */
  char timestamp[30] = {0};
  struct tm *timep;
  int printed;

  /* Build a current local time string */
  dtime   = sl_dtime (void);
  secfrac = (double)((double)dtime - (int)dtime);
  itime   = (time_t)dtime;
  timep   = localtime (&itime);

  printed = snprintf (timestamp, sizeof (timestamp), "%04d-%03dT%02d:%02d:%02d.%01.0f",
                      timep->tm_year + 1900, timep->tm_yday + 1, timep->tm_hour,
                      timep->tm_min, timep->tm_sec, secfrac);

  if ((size_t)printed >= sizeof (timestamp))
  {
    sl_log (1, 0, "%s() Time string overflow\n", __func__);
  }

  sl_log (0, 1, "%s, seq %" PRIu64 ", Received %u bytes of payload format %s\n",
          timestamp, packetinfo->seqnum, payloadlength,
          sl_formatstr (packetinfo->payloadformat, packetinfo->payloadsubformat));

  /* Print summary of the payload */
  if (sl_payload_summary (slconn->log, packetinfo, payload, payloadlength,
                          payloadsummary, sizeof (payloadsummary)) != -1)
  {
    sl_log (1, 1, "%s\n", payloadsummary);
  }
  else
  {
    sl_log (1, 1, "%s() Error generating payload summary\n", __func__);
  }

  if (amqp_publish_payload (conn, &amqp_cfg, payload, payloadlength) != 0)
  {
    sl_log (2, 0, "%s() Failed to publish packet with seq %" PRIu64 "\n",
            __func__, packetinfo->seqnum);
  }
} /* End of packet_handler() */

/***************************************************************************
 * parameter_proc:
 *
 * Process the command line parameters.
 *
 * Returns 0 on success, and -1 on failure
 ***************************************************************************/
static int
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
      amqp_cfg.routing_key = require_argument (option, argcount, argvec, &optind);
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
} /* End of parameter_proc() */

/***************************************************************************
 * auth_value_userpass:
 *
 * A callback function registered at SLCD.auth_value() that should return
 * a string to be submitted with the SeedLink AUTH command.
 *
 * In this case, the function prompts the user for a username and password
 * for interactive input.
 *
 * Returns authorization value string on success, and NULL on failure
 ***************************************************************************/
static const char *
auth_value_userpass (const char *server, void *data)
{
  (void)data; /* User-supplied data is not used in this case */
  char username[256] = {0};
  char password[256] = {0};
  int printed;

  fprintf (stderr, "Enter username for [%s]: ", server);
  if (fgets (username, sizeof (username), stdin) == NULL)
  {
    fprintf (stderr, "%s() Failed to read username\n", __func__);
    return NULL;
  }
  username[strcspn (username, "\n")] = '\0';

  fprintf (stderr, "Enter password: ");
  if (fgets (password, sizeof (password), stdin) == NULL)
  {
    fprintf (stderr, "%s() Failed to read password\n", __func__);
    return NULL;
  }
  password[strcspn (password, "\n")] = '\0';

  /* Create AUTH value of "USERPASS <username> <password>" */
  printed = snprintf (auth_buffer, sizeof (auth_buffer),
                      "USERPASS %s %s",
                      username, password);

  if ( (size_t)printed >= sizeof (auth_buffer))
  {
    fprintf (stderr, "%s() Auth value is too large (%d bytes)\n", __func__, printed);

    return NULL;
  }

  return auth_buffer;
}

/***************************************************************************
 * auth_value_token:
 *
 * A callback function registered at SLCD.auth_value() that should return
 * a string to be submitted with the SeedLink AUTH command.
 *
 * In this case, the function prompts the user for a username and password
 * for interactive input.
 *
 * Returns authorization value string on success, and NULL on failure
 ***************************************************************************/
static const char *
auth_value_token (const char *server, void *data)
{
  (void)data; /* User-supplied data is not used in this case */
  char token[4096] = {0};
  int printed;

  fprintf (stderr, "Enter token for [%s]: ", server);
  if (fgets (token, sizeof (token), stdin) == NULL)
  {
    fprintf (stderr, "%s() Failed to read token\n", __func__);
    return NULL;
  }
  token[strcspn (token, "\n")] = '\0';

  /* Create AUTH value of "JWT <token>" */
  printed = snprintf (auth_buffer, sizeof (auth_buffer),
                      "JWT %s",
                      token);

  if ((size_t)printed >= sizeof (auth_buffer))
  {
    fprintf (stderr, "%s() Auth value is too large (%d bytes)\n", __func__, printed);

    return NULL;
  }

  return auth_buffer;
}

/***************************************************************************
 * auth_finish:
 *
 * A callback function registered at SLCD.auth_finish() that is called
 * after the AUTH command has been sent to the server.
 *
 * In this case, the function clears the memory used to store the
 * username and password populated by auth_value().
 ***************************************************************************/
static void
auth_finish (const char *server, void *data)
{
  (void)server; /* Server address is not used in this case */
  (void)data;   /* User-supplied data is not used in this case */

  /* Clear memory used to store auth value */
  memset (auth_buffer, 0, sizeof (auth_buffer));
}

/***************************************************************************
 * usage:
 * Print the usage message and exit.
 ***************************************************************************/
static void
usage ()
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
           " --amqp-routing-key k AMQP routing key / queue (default binq)\n"
           "\n"
           " [host][:port]        Address of the SeedLink server in host:port format\n"
           "                        if host is omitted (i.e. ':18000'), localhost is assumed\n"
           "                        if :port is omitted (i.e. 'localhost'), 18000 is assumed\n"
           "\n");
} /* End of usage() */

static char *
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

static int
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

static amqp_connection_state_t
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

static void
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

static int
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

static int
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

static void
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
