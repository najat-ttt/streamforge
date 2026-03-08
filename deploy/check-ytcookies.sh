#!/bin/sh
# Check Playwright yt cookies freshness and optionally alert via webhook or email
# Config can be placed in /etc/default/check-ytcookies (see README)

CONF="/etc/default/check-ytcookies"
[ -f "$CONF" ] && . "$CONF"

FILE="/home/streamforge/firefox-cookies.txt"
MAX_AGE=${MAX_AGE:-86400}
WEBHOOK_URL=${WEBHOOK_URL:-https://webhook.site/fa48a3f5-7337-4593-9e44-a507b6160816}
# Default MAILTO set to requested address; can be overridden in /etc/default/check-ytcookies
MAILTO=${MAILTO:-sheikhsiamnajat@gmail.com}

status=0
age=0
MSG=""

if [ ! -f "$FILE" ]; then
  MSG="MISSING: $FILE"
  echo "$MSG"
  status=2
else
  age=$(( $(date +%s) - $(stat -c %Y "$FILE") ))
  if [ "$age" -gt "$MAX_AGE" ]; then
    MSG="STALE: $FILE age $age seconds"
    echo "$MSG"
    status=1
  else
    exit 0
  fi
fi

# Send webhook if requested (best-effort, do not fail on network error)
if [ -n "$WEBHOOK_URL" ]; then
  payload=$(printf '{"message":"%s","file":"%s","age":%d}' "$MSG" "$FILE" "$age")
  command -v curl >/dev/null 2>&1 && curl -fsS -X POST -H 'Content-Type: application/json' -d "$payload" "$WEBHOOK_URL" || true
fi

# Send mail if requested (best-effort)
if [ -n "$MAILTO" ]; then
  if command -v mail >/dev/null 2>&1; then
    echo "$MSG" | mail -s "ytcookies check alert" "$MAILTO" || true
  fi
fi

exit $status
