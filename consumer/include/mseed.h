#ifndef CONSUMER_MSEED_H
#define CONSUMER_MSEED_H

#include <postgresql/libpq-fe.h>
#include <stdint.h>

int process_message(const unsigned char *buf, int64_t len, uint32_t flags,
                    int verbose, PGconn *pg);
void hex_preview(const unsigned char *buf, size_t len, size_t n);

#endif /* CONSUMER_MSEED_H */
