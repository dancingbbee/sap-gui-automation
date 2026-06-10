#!/usr/bin/env bash
# install.sh — set up the SAP GUI daemon on this Mac.
#
# What it does (all reversible via uninstall.sh):
#   1. generates an auth token at ~/.sap-daemon/token (if absent)
#   2. creates the screenshot cache dir ~/Library/Caches/sap-daemon
#   3. builds an app bundle  ~/Applications/SAP (daemon).app  that launches
#      SAP GUI for Java with  -f <this>/sap-daemon.js  — no terminal, no dialog
#   4. symlinks sapctl into ~/bin (if on PATH) or prints how to add it
#
# It does NOT modify SAP GUI's own preferences or any team-shared config.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DAEMON_JS="$HERE/sap-daemon.js"
SAPCTL="$HERE/sapctl"

CFG_DIR="$HOME/.sap-daemon"
CACHE_DIR="$HOME/Library/Caches/sap-daemon"
TOKEN="$CFG_DIR/token"
APP="$HOME/Applications/SAP (daemon).app"

say() { printf '\033[1;32m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[!]\033[0m %s\n' "$*"; }

# --- prerequisite: macOS ---
if [ "$(uname -s)" != "Darwin" ]; then
  warn "This tool is macOS-only (uname=$(uname -s)). Aborting."
  exit 1
fi

# --- prerequisite: python3 (sapctl needs it) ---
if ! command -v python3 >/dev/null 2>&1; then
  warn "python3 not found — sapctl requires it."
  warn "Install with: xcode-select --install   (or via Homebrew)"
  exit 1
fi
say "python3: $(python3 --version 2>&1)"

# --- locate SAP GUI for Java bundle ---
say "Locating SAP GUI for Java..."
SAP_APP=""
for cand in "/Applications/SAP Clients/"*/*.app; do
  if [ -x "$cand/Contents/MacOS/SAPGUI" ]; then
    SAP_APP="$cand"
    break
  fi
done
if [ -z "$SAP_APP" ]; then
  warn "SAP GUI for Java not found under /Applications/SAP Clients/."
  warn "Edit SAP_APP in the generated launcher manually after install."
  SAP_BIN="/Applications/SAP Clients/SAPGUI/SAPGUI.app/Contents/MacOS/SAPGUI"
else
  SAP_BIN="$SAP_APP/Contents/MacOS/SAPGUI"
  say "Found: $SAP_APP"
fi

# --- 1. token ---
mkdir -p "$CFG_DIR"
chmod 700 "$CFG_DIR"
if [ ! -f "$TOKEN" ]; then
  head -c 24 /dev/urandom | base64 | tr -d '/+=' | head -c 32 > "$TOKEN"
  chmod 600 "$TOKEN"
  say "Generated auth token at $TOKEN"
else
  say "Auth token already exists at $TOKEN (kept)"
fi

# --- 2. cache dir ---
mkdir -p "$CACHE_DIR"
say "Cache dir ready: $CACHE_DIR"

# --- 3. launcher app bundle ---
# Build via osacompile so the executable is a real Mach-O applet (NOT a shell
# script) — a shell-script executable makes macOS open Terminal. The applet
# runs `do shell script` which launches SAP GUI with -f in the background, with
# no terminal window. Then ad-hoc code-sign so Gatekeeper doesn't prompt.
mkdir -p "$HOME/Applications"
rm -rf "$APP"

SCPT="$(mktemp /tmp/sap-launch-XXXXXX.applescript)"
cat > "$SCPT" <<EOF
do shell script "nohup '$SAP_BIN' -f '$DAEMON_JS' >/dev/null 2>&1 &"
EOF
osacompile -o "$APP" "$SCPT"
rm -f "$SCPT"

# borrow SAP's own icon so it looks like SAP (replace applet.icns)
if [ -n "${SAP_APP:-}" ]; then
  SAP_ICNS="$(/usr/bin/find "$SAP_APP/Contents/Resources" -maxdepth 1 -iname '*.icns' 2>/dev/null | head -1 || true)"
  if [ -n "$SAP_ICNS" ] && [ -f "$APP/Contents/Resources/applet.icns" ]; then
    cp "$SAP_ICNS" "$APP/Contents/Resources/applet.icns"
  fi
fi

# ad-hoc sign so the first launch isn't blocked by Gatekeeper, and clear any
# quarantine attribute (harmless if absent)
codesign --force --deep --sign - "$APP" >/dev/null 2>&1 || warn "codesign failed (app may prompt on first launch)"
xattr -dr com.apple.quarantine "$APP" 2>/dev/null || true

/usr/bin/touch "$APP"
say "App bundle written: $APP"

# --- 4. sapctl on PATH ---
if [ -d "$HOME/bin" ]; then
  ln -sf "$SAPCTL" "$HOME/bin/sapctl"
  say "Linked sapctl -> ~/bin/sapctl"
else
  warn "~/bin not found. Add this to your shell rc to use 'sapctl':"
  warn "    alias sapctl='$SAPCTL'"
fi

printf '\n\033[1;32m✓ Install complete.\033[0m\n'
cat <<EOF

To use:
  1. Launch SAP with the daemon — double-click in Finder/Spotlight:
       SAP (daemon)
     (drag it to the Dock and use it like your normal SAP icon.
      No terminal, no dialog — just SAP, with automation enabled.)
     Or from a shell:  open "$APP"   /   sapctl start
  2. Log in to your system from the Logon Pad as usual (one click).
  3. Verify:
       sapctl status
     → should show {"ok": true, "conns": 1, ...}

The daemon listens on 127.0.0.1:18765 (loopback only) and requires the
token at $TOKEN. Screenshots land in $CACHE_DIR
and macOS sweeps them automatically.

Server side: SAP GUI Scripting must be enabled (profile parameter
sapgui/user_scripting = TRUE). Ask Basis if 'sapctl health' shows conns
but exec calls fail with a scripting-disabled error.
EOF
