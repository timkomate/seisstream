#include <stdio.h>
#include <string.h>

#include "auth.h"

static char auth_buffer[1024] = {0};

const char *
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

  if ((size_t)printed >= sizeof (auth_buffer))
  {
    fprintf (stderr, "%s() Auth value is too large (%d bytes)\n", __func__, printed);

    return NULL;
  }

  return auth_buffer;
}

const char *
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

void
auth_finish (const char *server, void *data)
{
  (void)server; /* Server address is not used in this case */
  (void)data;   /* User-supplied data is not used in this case */

  /* Clear memory used to store auth value */
  memset (auth_buffer, 0, sizeof (auth_buffer));
}
