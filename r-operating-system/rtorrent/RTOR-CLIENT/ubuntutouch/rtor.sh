#!/bin/sh
# RTOR GHOSTCHAIN (Ubuntu Touch) app launcher. Runs inside the click AppArmor sandbox:
# shell builtins + bundled bin/ only. The always-on server normally runs as the
# rtor-ghostchain.service user unit (started at login); this window then just shows it.
# If no server answers on 127.0.0.1:4984, the launcher starts one for this session.
D="${APP_DIR:-${0%/*}}"; case "$D" in /*) ;; *) D="$PWD/$D" ;; esac
APPN=rtor.rizal
DATA="${XDG_DATA_HOME:-$HOME/.local/share}/$APPN"
CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/$APPN"
export RTOR_IMPORT_DIRS="$CACHE:$DATA/inbox"
export RTOR_LOG="$DATA/client.log"
EP=""
if ! "$D/bin/rtor-ghostchain" ping --addr 127.0.0.1:4984 </dev/null >/dev/null 2>&1; then
  "$D/bin/rtor-ghostchain" serve --pkg "$D" --data "$DATA" --addr 127.0.0.1:4984 </dev/null >/dev/null 2>&1 &
  EP=$!
  trap 'kill $EP 2>/dev/null' EXIT INT TERM
fi
case "$1" in
  magnet:*) "$D/bin/rtor-ghostchain" open-url --addr 127.0.0.1:4984 "$1" </dev/null >/dev/null 2>&1 & ;;
esac
qmlscene "$D/qml/Main.qml"
