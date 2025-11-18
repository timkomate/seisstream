#include <inttypes.h>
#include <stdio.h>
#include <string.h>

#include <libmseed.h>

#include "mseed.h"
#include "pg_client.h"

void
hex_preview(const unsigned char *buf, size_t len, size_t n)
{
  size_t show = (len < n) ? len : n;
  fprintf(stderr, "Hex preview (%zu bytes): ", show);
  for (size_t i = 0; i < show; ++i)
    fprintf(stderr, "%02x ", buf[i]);
  fprintf(stderr, "\n");
}

int
process_message(const unsigned char *buf, int64_t len, uint32_t flags,
                int verbose, PGconn *pg)
{
  MS3Record *msr = NULL;
  char network[64], station[64], location[64], channel[64], s_time[64];

  if (pg_begin_copy(pg) != 0)
    return -1;

  int rv = msr3_parse((const char *)buf, len, &msr, flags, verbose ? 1 : 0);
  if (rv != MS_NOERROR || msr == NULL)
  {
    pg_abort_copy(pg, "parse error");
    msr3_free(&msr);
    return -1;
  }

  if (msr->numsamples > 0)
  {
    int samplesize = ms_samplesize(msr->sampletype);
    if (samplesize == 0)
    {
      ms_log(2, "Unrecognized sample type: '%c'\n", msr->sampletype);
      pg_abort_copy(pg, "bad sample type");
      msr3_free(&msr);
      return -1;
    }

    if (ms_sid2nslc_n(msr->sid,
                      network, sizeof network,
                      station, sizeof station,
                      location, sizeof location,
                      channel, sizeof channel))
    {
      ms_log(2, "%s: Cannot parse NSLC from SID\n", msr->sid);
      pg_abort_copy(pg, "bad SID");
      msr3_free(&msr);
      return -1;
    }

    if (msr->samprate <= 0.0)
    {
      ms_log(2, "%s: Invalid sample rate %.6g\n", msr->sid, msr->samprate);
      pg_abort_copy(pg, "invalid sample rate");
      msr3_free(&msr);
      return -1;
    }

    char sr_buf[32];
    const char *p_sr = sr_buf;
    snprintf(sr_buf, sizeof sr_buf, "%.7g", msr->samprate);

    double dt_nsec = 1e9 / msr->samprate;

    for (long cnt = 0; cnt < msr->numsamples; cnt++)
    {
      nstime_t tns = msr->starttime + (nstime_t)(cnt * dt_nsec);

      ms_nstime2timestr_n(tns, s_time, sizeof(s_time), ISOMONTHDAY, NANO_MICRO_NONE);

      void *sptr = (char *)msr->datasamples + cnt * samplesize;
      double val = 0.0;
      if (msr->sampletype == 'i')
        val = (double)(*(int32_t *)sptr);
      else if (msr->sampletype == 'f')
        val = (double)(*(float *)sptr);
      else if (msr->sampletype == 'd')
        val = *(double *)sptr;
      else
      {
        ms_log(2, "Unsupported sample type '%c'\n", msr->sampletype);
        continue;
      }

      char val_buf[64];
      snprintf(val_buf, sizeof val_buf, "%.17g", val);

      char line[256];
      int n = snprintf(line, sizeof line,
                       "%sZ\t%s\t%s\t%s\t%s\t%s\t%s\n",
                       s_time, network, station, location, channel,
                       val_buf, p_sr ? p_sr : "\\N");
      if (n < 0 || n >= (int)sizeof line)
      {
        ms_log(2, "line buffer too small\n");
        pg_abort_copy(pg, "line too long");
        msr3_free(&msr);
        return -1;
      }

      if (PQputCopyData(pg, line, n) != 1)
      {
        ms_log(2, "PQputCopyData failed: %s\n", PQerrorMessage(pg));
        pg_abort_copy(pg, "client error");
        msr3_free(&msr);
        return -1;
      }
    }
  }

  if (pg_finish_copy(pg) != 0)
  {
    msr3_free(&msr);
    return -1;
  }

  msr3_free(&msr);
  return 0;
}
