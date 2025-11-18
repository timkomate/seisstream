#ifndef CONNECTOR_CLI_H
#define CONNECTOR_CLI_H

#include "connector.h"

int parameter_proc (SLCD *slconn, int argcount, char **argvec);
void usage (void);
char *require_argument (const char *option, int argcount, char **argvec, int *index);
int parse_port (const char *option, const char *value);

#endif /* CONNECTOR_CLI_H */
