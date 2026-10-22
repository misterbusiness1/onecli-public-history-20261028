#!/bin/sh
# Production containers require a real credential. Local ambient administration
# is available only through an explicit development opt-in.
if [ "${ONECLI_ALLOW_UNAUTHENTICATED_LOCAL:-false}" = "true" ]; then
  printf '%s\n' local
elif [ -n "${NEXTAUTH_SECRET:-}" ]; then
  printf '%s\n' oauth
else
  printf '%s\n' api-key
fi
