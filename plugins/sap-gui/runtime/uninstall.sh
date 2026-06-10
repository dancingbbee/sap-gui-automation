#!/usr/bin/env bash
# uninstall.sh — reverse install.sh. Leaves the daemon source untouched.

set -euo pipefail

CFG_DIR="$HOME/.sap-daemon"
CACHE_DIR="$HOME/Library/Caches/sap-daemon"
APP="$HOME/Applications/SAP (daemon).app"
OLD_LAUNCHER="$HOME/Applications/SAP-with-daemon.command"

say() { printf '\033[1;32m==>\033[0m %s\n' "$*"; }

# stop a running daemon if present (kills the SAP GUI JVM holding port 18765)
PID="$(lsof -nP -iTCP:18765 -sTCP:LISTEN -t 2>/dev/null || true)"
if [ -n "$PID" ]; then
  say "Stopping daemon (SAP GUI pid $PID)..."
  kill "$PID" 2>/dev/null || true
fi

[ -e "$APP" ] && rm -rf "$APP" && say "Removed app bundle"
[ -e "$OLD_LAUNCHER" ] && rm -f "$OLD_LAUNCHER" && say "Removed old .command launcher"
[ -L "$HOME/bin/sapctl" ] && rm -f "$HOME/bin/sapctl" && say "Removed sapctl symlink"

if [ "${1:-}" = "--purge" ]; then
  rm -rf "$CFG_DIR" "$CACHE_DIR"
  say "Purged token + cache ($CFG_DIR, $CACHE_DIR)"
else
  say "Kept token + cache. Use '--purge' to remove them too."
fi

say "Done."
