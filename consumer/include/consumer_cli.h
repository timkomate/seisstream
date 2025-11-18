#ifndef CONSUMER_CLI_H
#define CONSUMER_CLI_H

#include "consumer.h"

int parse_args(int argc, char **argv, ConsumerConfig *config);
void usage(const char *progname);

#endif /* CONSUMER_CLI_H */
