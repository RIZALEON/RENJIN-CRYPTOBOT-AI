#!/bin/sh
# RTOR GHOSTCHAIN cryptoclient — Linux launcher.
#   ./run-linux.sh --check      verify .rzl SHA256, recorded magnet, embedded UI, CHAIN VERIFY (must pass before activation)
#   ./run-linux.sh              serve the R:> Shell + Renjin Torrent on http://127.0.0.1:4984 and keep the RTOR loop running
#   ./run-linux.sh <cmd>        chain verify | chain tail | magnet | send-magnet | flush | outbox | reseed | version
# Holds no keys, signs nothing, mints nothing. Re-seed waits for Rizal's RGHOSTKEY tap on the trusted device.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
case "$(uname -m)" in
  x86_64|amd64) A=x86_64 ;; aarch64|arm64) A=arm64 ;; riscv64) A=riscv64 ;; *) echo "unsupported arch $(uname -m)"; exit 2 ;;
esac
B="$HERE/bin/rtor-ghostchain"; [ -x "$B" ] || B="$HERE/bin/rtor-ghostchain-$A"
[ -x "$B" ] || { echo "no rtor-ghostchain binary for $A in $HERE/bin"; exit 2; }
if [ "${1:-}" = "--check" ]; then shift; exec "$B" check --pkg "$HERE" "$@"; fi
exec "$B" "$@" --pkg "$HERE"
