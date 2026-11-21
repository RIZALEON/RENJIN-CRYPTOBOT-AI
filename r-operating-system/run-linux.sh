#!/bin/sh
# R OPERATING SYSTEM — pure Linux runner. Pure RZL only.
# Usage: sh run-linux.sh [--check]  — serves the integrated R:> Shell on localhost:4984
# and runs ThundR Autosign --thundr-check (read+check only, never signs).
set -e
cd "$(dirname "$0")"
echo "R OPERATING SYSTEM — pure Linux · PURE RZL"
echo "ThundR · ЯID-0014-KREH · Gizmo · Я-DEVICE-1PYZ7VG0Z1-ZE"
if [ -x "$(command -v node)" ]; then node --check renjin/src/yaseed-core-v3.js 2>/dev/null || true; fi
if [ "${1:-}" = "--check" ]; then
  echo "check: shell present: $(ls -l rshell/R-SHELL-MERGED.html)"
  sh autosign/thundr-autosign.sh --thundr-check 2>/dev/null || echo "check: autosign needs a device in the RENJIN RZL OPERATING SYSTEM"
  exit 0
fi
echo "Serving integrated shell at http://127.0.0.1:4984/ (Ctrl-C to stop)"
python3 -m http.server 4984 --bind 127.0.0.1
