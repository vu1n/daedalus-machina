#!/bin/sh
set -eu

URLS=${HEALTHCHECK_URLS:-}
INTERVAL=${PING_INTERVAL_SECONDS:-300}

if [ -z "$URLS" ]; then
  echo "No HEALTHCHECK_URLS set; will loop with sleep only ($INTERVAL s)."
fi

while true; do
  OLDIFS=$IFS
  IFS=','
  for u in $URLS; do
    [ -z "$u" ] && continue
    echo "Pinging: $u"
    if ! curl -fsS "$u" >/dev/null 2>&1; then
      echo "Ping failed: $u" >&2
    fi
  done
  IFS=$OLDIFS
  sleep "$INTERVAL"
done
