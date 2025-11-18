#ifndef CONNECTOR_AUTH_H
#define CONNECTOR_AUTH_H

#include "connector.h"

const char *auth_value_userpass (const char *server, void *data);
const char *auth_value_token (const char *server, void *data);
void auth_finish (const char *server, void *data);

#endif /* CONNECTOR_AUTH_H */
