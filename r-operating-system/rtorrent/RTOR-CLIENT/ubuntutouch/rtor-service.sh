#!/bin/sh
# RTOR GHOSTCHAIN always-on server for the rtor-ghostchain.service user unit (systemd --user, phablet session).
# Starts at login, keeps 127.0.0.1:4984 up, and seeds/leeches library files automatically (no tap needed).
# Runs under the app's own AppArmor profile (rtor.rizal_rtor_<version>) when aa-exec is available.
D="$(cd "${0%/*}" && pwd)"
APPN=rtor.rizal
DATA="$HOME/.local/share/$APPN"
CACHE="$HOME/.cache/$APPN"
export RTOR_IMPORT_DIRS="$CACHE:$DATA/inbox"
export RTOR_LOG="$DATA/client.log"
VER=$(sed -n 's/.*"version": *"\([^"]*\)".*/\1/p' "$D/manifest.json" | head -1)
PROFILE="${APPN}_rtor_${VER}"
if "$D/bin/rtor-ghostchain" ping --addr 127.0.0.1:4984 >/dev/null 2>&1; then
  echo "rtor-service: a server already answers on 127.0.0.1:4984; waiting for it to exit before taking over" >&2
  exit 75   # systemd restarts us after RestartSec; only one instance ever holds 4984
fi
if command -v aa-exec >/dev/null 2>&1 && [ -e "/var/lib/apparmor/profiles/click_$PROFILE" ]; then
  exec aa-exec -p "$PROFILE" -- "$D/bin/rtor-ghostchain" serve --pkg "$D" --data "$DATA" --addr 127.0.0.1:4984
fi
exec "$D/bin/rtor-ghostchain" serve --pkg "$D" --data "$DATA" --addr 127.0.0.1:4984
