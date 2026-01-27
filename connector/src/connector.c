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
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include "connector_amqp_client.h"
#include "auth.h"
#include "cli.h"
#include "connector.h"
#include "mseedformat.h"

AmqpConfig amqp_cfg = {
  .host = "127.0.0.1",
  .port = 5672,
  .user = "guest",
  .password = "guest",
  .vhost = "/",
  .exchange = "",
  .routing_key = NULL
};

short int verbose = 0;
short int ppackets = 0;
char *statefile = NULL;

static void packet_handler (SLCD *slconn, const SLpacketinfo *packetinfo,
                            const char *payload, uint32_t payloadlen,
                            amqp_connection_state_t conn);
static void process_string (char *s);

int
main (int argc, char **argv)
{
  SLCD *slconn = NULL; /* connection parameters */
  const SLpacketinfo *packetinfo = NULL; /* packet information */
  amqp_connection_state_t amqp_conn = NULL;

  char *plbuffer = NULL;
  uint32_t plbuffersize = DEFAULT_PAYLOAD_BUFFER;
  int status = 0;
  char sourceid[64] = {0};

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
  else
  {
    sl_log (1, 0, "AMQP connection established\n");
  }

  /* Allocate payload buffer */
  plbuffer = (char *)malloc (plbuffersize);
  if (plbuffer == NULL)
  {
    sl_log (2, 0, "Memory allocation failed\n");
  }

  /* Loop with the connection manager */
  sl_log (0, 1, "Entering SeedLink collection loop\n");
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

  sl_log (0, 1, "Exiting SeedLink collection loop (status=%d)\n", status);

  if (amqp_conn)
  {
    sl_log (0, 1, "Closing AMQP connection\n");
    amqp_disconnect (amqp_conn);
  }

  if (slconn)
  {
    sl_disconnect (slconn);

    if (statefile)
      sl_savestate (slconn, statefile);

    sl_freeslcd (slconn);
  }
  free (plbuffer);
} /* End of main() */

int
get_source_id (const SLlog *log, const SLpacketinfo *packetinfo,
               const char *plbuffer, uint32_t plbuffer_size,
               char *sourceid, size_t sourceid_size)
{
  /* This whole function is a horrible hack for now, but I did not want to read through the MS3 documentation...*/
  if (!packetinfo || !plbuffer || plbuffer_size == 0)
  {
    sl_log_rl (log, 2, 1, "%s(): invalid input parameters\n", __func__);
    return -1;
  }

  /* Parse requested details from miniSEED v2 */
  if (packetinfo->payloadformat == SLPAYLOAD_MSEED2)
  {
    if (packetinfo->payloadlength < 48)
    {
      sl_log_rl (log, 2, 1, "%s(): payload too short for miniSEEDv2\n", __func__);
      return -1;
    }

    if (sourceid)
    {
      char net[3]  = {0};
      char sta[6]  = {0};
      char loc[3]  = {0};
      char chan[6] = {0};

      sl_strncpclean (net, pMS2FSDH_NETWORK (plbuffer), 2);
      sl_strncpclean (sta, pMS2FSDH_STATION (plbuffer), 5);
      sl_strncpclean (loc, pMS2FSDH_LOCATION (plbuffer), 2);

      /* Map 3 channel codes to BAND_SOURCE_POSITION */
      chan[0] = *pMS2FSDH_CHANNEL (plbuffer);
      chan[1] = '_';
      chan[2] = *(pMS2FSDH_CHANNEL (plbuffer) + 1);
      chan[3] = '_';
      chan[4] = *(pMS2FSDH_CHANNEL (plbuffer) + 2);

      snprintf (sourceid, sourceid_size, "FDSN:%s_%s_%s_%s",
                net, sta, loc, chan);
    }
  }

  /* Parse requested details from miniSEED v3 */
  else if (packetinfo->payloadformat == SLPAYLOAD_MSEED3)
  {
    if (packetinfo->payloadlength < MS3FSDH_LENGTH + *pMS3FSDH_SIDLENGTH(plbuffer))
    {
      sl_log_rl (log, 2, 1, "%s(): payload too short for miniSEEDv3\n", __func__);
      return -1;
    }

    if (sourceid)
    {
      snprintf (sourceid, sourceid_size, "%.*s",
                (int)*pMS3FSDH_SIDLENGTH (plbuffer),
                pMS3FSDH_SID (plbuffer));
    }
  }
  else
  {
    sl_log_rl (log, 2, 1, "%s(): unsupported payload format: %c\n",
               __func__, packetinfo->payloadformat);
    return -1;
  }
  process_string(sourceid);
  return 0;
} /* End of sl_payload_info() */

static void
process_string (char *s)
{
    const char *prefix = "FDSN:";
    size_t len = strlen(prefix);

    if (strncmp(s, prefix, len) == 0) {
        memmove(s, s + len, strlen(s + len) + 1);
    }

    for (char *p = s; *p; p++) {
        if (*p == '_')
            *p = '.';
    }
}

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
  char sourceid[64] = {0};
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

  if (get_source_id (slconn->log, packetinfo, payload, payloadlength, sourceid,
                     sizeof (sourceid)) < 0)
  {
    sl_log (1, 0, "%s() Error getting source ID\n", __func__);
  }

  if (amqp_publish_payload (conn, &amqp_cfg, payload, payloadlength, sourceid) != 0)
  {
    sl_log (2, 0, "%s() Failed to publish packet with seq %" PRIu64 "\n",
            __func__, packetinfo->seqnum);
  }
} /* End of packet_handler() */
