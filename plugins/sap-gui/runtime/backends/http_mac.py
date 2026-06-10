"""macOS backend — talks to the sap-daemon.js HTTP server (127.0.0.1:18765)
running inside SAP GUI for Java. Logic moved verbatim from the original sapctl;
behavior is unchanged.
"""
import json
import os
import subprocess
import time
import urllib.request
import urllib.error

from .base import Backend

HOST = os.environ.get("SAP_DAEMON_HOST", "127.0.0.1")
PORT = int(os.environ.get("SAP_DAEMON_PORT", "18765"))
TOKEN_PATH = os.path.expanduser("~/.sap-daemon/token")
LAUNCHER = os.path.expanduser("~/Applications/SAP (daemon).app")


def _token():
    try:
        with open(TOKEN_PATH) as f:
            return f.read().strip()
    except FileNotFoundError:
        return None


def _call(method, path, body=None, timeout=30):
    url = f"http://{HOST}:{PORT}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    tok = _token()
    if tok:
        req.add_header("X-Token", tok)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode())
        except Exception:
            return {"ok": False, "error": f"HTTP {e.code}"}
    except urllib.error.URLError as e:
        return {"ok": False, "error": f"connect failed: {e.reason} "
                                      f"(is SAP GUI running with sap-daemon.js?)"}


def _daemon_pid():
    """PID of the SAP GUI JVM holding port 18765, or None."""
    try:
        out = subprocess.run(["lsof", "-nP", "-iTCP:%d" % PORT, "-sTCP:LISTEN", "-t"],
                             capture_output=True, text=True, timeout=10).stdout.strip()
        return int(out.splitlines()[0]) if out else None
    except Exception:
        return None


def _list_sap_pids():
    try:
        out = subprocess.run(["pgrep", "-f", "SAPGUI 8.10"],
                             capture_output=True, text=True, timeout=10).stdout
        me = os.getpid()
        return [int(p) for p in out.split() if p.strip().isdigit() and int(p) != me]
    except Exception:
        return []


def _window_count(pid):
    script = ('tell application "System Events" to count windows of '
              '(first application process whose unix id is %d)' % pid)
    try:
        r = subprocess.run(["osascript", "-e", script],
                           capture_output=True, text=True, timeout=10)
        return int(r.stdout.strip())
    except Exception:
        return -1


class HttpBackend(Backend):
    def health(self, timeout):
        return _call("GET", "/health", None, timeout)

    def targets(self, timeout):
        return _call("POST", "/targets", {}, timeout)

    def status(self, timeout):
        pid = _daemon_pid()
        if pid is None:
            return {"ok": False, "running": False,
                    "error": "daemon not running (no listener on %d). Use 'sapctl start'." % PORT}
        h = _call("GET", "/health", None, timeout)
        h["running"] = True
        h["pid"] = pid
        if h.get("conns", 0) == 0:
            h["hint"] = "daemon up but no SAP login. Double-click a system in the Logon Pad."
        return h

    def start(self, timeout):
        if _daemon_pid() is not None:
            return {"ok": True, "running": True, "note": "already running",
                    "status": _call("GET", "/health", None, timeout)}
        if not os.path.exists(LAUNCHER):
            return {"ok": False, "error": "launcher not found at %s — run install.sh first" % LAUNCHER}
        subprocess.run(["open", LAUNCHER], check=False)
        for _ in range(20):
            time.sleep(0.5)
            if _daemon_pid() is not None:
                return {"ok": True, "running": True,
                        "note": "started; now log in via the Logon Pad",
                        "status": _call("GET", "/health", None, timeout)}
        return {"ok": False, "error": "launched but daemon did not bind within 10s"}

    def kill_orphans(self, dry_run):
        daemon = _daemon_pid()
        result = {"ok": True, "daemon_pid": daemon, "checked": [], "orphans": [], "killed": []}
        for pid in _list_sap_pids():
            if pid == daemon:
                result["checked"].append({"pid": pid, "role": "daemon", "action": "keep"})
                continue
            wc = _window_count(pid)
            if wc == 0:
                result["orphans"].append(pid)
                if dry_run:
                    result["checked"].append({"pid": pid, "windows": 0, "action": "would-kill"})
                else:
                    subprocess.run(["kill", str(pid)], check=False)
                    result["killed"].append(pid)
                    result["checked"].append({"pid": pid, "windows": 0, "action": "killed"})
            else:
                result["checked"].append({"pid": pid, "windows": wc,
                                           "action": "keep (has windows or unknown)"})
        return result

    def exec_(self, body, timeout):
        return _call("POST", "/exec", body, timeout)

    def snapshot(self, body, timeout):
        return _call("POST", "/snapshot", body, timeout)

    def screenshot(self, body, timeout):
        return _call("POST", "/screenshot", body, timeout)

    def transact(self, body, timeout):
        return _call("POST", "/transact", body, timeout)
