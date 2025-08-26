#!/bin/sh
set -eu

URLS=${HEALTHCHECK_URLS:-}
INTERVAL=${PING_INTERVAL_SECONDS:-300}

if [ -z "$URLS" ]; then
  echo "No HEALTHCHECK_URLS set; sleeping."
fi

IFS=',' read -r -a arr << EOF
$URLS
EOF

while true; do
  for u in "${arr[@]}"; do
    [ -z "$u" ] && continue
    echo "Pinging: $u"
    if ! curl -fsS "$u" >/dev/null 2>&1; then
      echo "Ping failed: $u" >&2
    fi
  done
  sleep "$INTERVAL"
done

