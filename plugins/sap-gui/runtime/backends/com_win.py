"""Windows backend — drives SAP GUI for Windows via COM (win32com).

No daemon/token/launcher: SAP GUI registers its scripting engine in the OS
Running Object Table when running + logged in, and we attach with
GetObject("SAPGUI"). The transact step JSON is the shared interface; exec(JS)
is macOS-only and returns an unsupported error here.

win32com is imported lazily (inside functions) so importing this module on
macOS (where pywin32 is absent) never fails — backends/__init__ only loads it
on Windows anyway.
"""
import os

from .base import Backend


def _engine():
    import win32com.client
    try:
        sapgui = win32com.client.GetObject("SAPGUI")
    except Exception:
        raise RuntimeError("SAP GUI not running / scripting not enabled "
                           "(start SAP GUI, log in, and enable scripting in options).")
    app = sapgui.GetScriptingEngine
    if app is None or app.Children.Count == 0:
        raise RuntimeError("No SAP connection. Log in to a system first.")
    return app


def _session(app, con=0, ses=0):
    return app.Children(int(con)).Children(int(ses))


def _default_shot_path():
    return os.path.join(os.environ.get("TEMP", os.getcwd()), "sap-shot.png")


def _is_png(path):
    try:
        with open(path, "rb") as f:
            return f.read(8) == b"\x89PNG\r\n\x1a\n"
    except Exception:
        return False


def _hardcopy_png(window, path):
    """Capture `window` to a real PNG at `path`.

    SAP GUI's HardCopy(filename) ignores the extension and writes BMP. We:
      1) try HardCopy(filename, "PNG") — newer SAP GUI supports it,
      2) verify the file is really PNG (magic bytes),
      3) else fall back to BMP + Pillow conversion,
      4) if Pillow is absent, keep the BMP and report the real path/format.
    Returns a result dict.
    """
    # 1) native PNG attempt
    try:
        window.HardCopy(path, "PNG")
        if _is_png(path):
            return {"ok": True, "path": path, "format": "png"}
    except Exception:
        pass
    # 2) BMP then convert
    bmp = (path[:-4] if path.lower().endswith(".png") else path) + ".bmp"
    try:
        window.HardCopy(bmp)
    except Exception as e:
        return {"ok": False, "error": "HardCopy failed: %s" % e}
    try:
        from PIL import Image
        Image.open(bmp).save(path, "PNG")
        try:
            os.remove(bmp)
        except Exception:
            pass
        return {"ok": True, "path": path, "format": "png", "note": "converted from BMP via Pillow"}
    except ImportError:
        return {"ok": True, "path": bmp, "format": "bmp",
                "note": "saved BMP (PNG needs Pillow: pip install Pillow). "
                        "Claude image Read wants PNG/JPG — convert if needed."}
    except Exception as e:
        return {"ok": True, "path": bmp, "format": "bmp", "note": "PNG convert failed: %s" % e}


class ComBackend(Backend):
    # ---- lifecycle ----
    def health(self, timeout):
        try:
            app = _engine()
            return {"ok": True, "conns": app.Children.Count,
                    "version": "%s.%s" % (app.MajorVersion, app.MinorVersion),
                    "os": "windows"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def status(self, timeout):
        h = self.health(timeout)
        h["running"] = h.get("ok", False)
        return h

    def start(self, timeout):
        return {"ok": True, "note": "Windows: COM attaches automatically. "
                "Just launch SAP GUI and log in (no daemon/launcher needed)."}

    def kill_orphans(self, dry_run):
        return {"ok": True, "note": "Windows: no daemon; nothing to clean (no-op).",
                "orphans": [], "killed": []}

    # ---- introspection ----
    def targets(self, timeout):
        try:
            app = _engine()
        except Exception as e:
            return {"ok": False, "error": str(e)}
        out = []
        for c in range(app.Children.Count):
            conn = app.Children(c)
            for s in range(conn.Children.Count):
                sess = conn.Children(s)
                info = sess.Info
                wins = []
                for w in range(8):
                    try:
                        wins.append(str(sess.findById("wnd[%d]" % w).Text))
                    except Exception:
                        break
                out.append({"con": c, "ses": s,
                            "prefix": "/app/con[%d]/ses[%d]" % (c, s),
                            "system": str(info.SystemName), "client": str(info.Client),
                            "user": str(info.User), "tcode": str(info.Transaction),
                            "windows": wins})
        return {"ok": True, "targets": out}

    def _walk(self, comp, depth, maxd):
        node = {"id": str(comp.Id), "type": str(comp.Type), "name": str(comp.Name)}
        try:
            node["text"] = str(comp.Text)
        except Exception:
            pass
        if depth >= maxd:
            return node
        try:
            if comp.ContainerType:
                kids = comp.Children
                node["children"] = []
                for i in range(min(kids.Count, 200)):
                    node["children"].append(self._walk(kids(i), depth + 1, maxd))
        except Exception:
            pass
        return node

    def snapshot(self, body, timeout):
        try:
            app = _engine()
            sess = _session(app, body.get("con", 0), body.get("ses", 0))
            sid = body.get("id")
            start = sess.findById(sid) if sid else sess
            return {"ok": True, "target": {"con": body.get("con", 0), "ses": body.get("ses", 0)},
                    "tree": self._walk(start, 0, body.get("maxDepth", 10))}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ---- screenshot (HardCopy is built in on Windows) ----
    def screenshot(self, body, timeout):
        try:
            app = _engine()
            sess = _session(app, body.get("con", 0), body.get("ses", 0))
            p = body.get("path") or _default_shot_path()
            return _hardcopy_png(sess.findById("wnd[0]"), p)
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ---- exec: macOS-only ----
    def exec_(self, body, timeout):
        return {"ok": False,
                "error": "exec (raw JS) is macOS-only. On Windows use transact steps."}

    # ---- transact: step JSON → COM ----
    def transact(self, body, timeout):
        try:
            app = _engine()
            sess = _session(app, body.get("con", 0), body.get("ses", 0))
            results = []
            for st in body.get("steps", []):
                results.append(self._run_step(sess, st))
            return {"ok": True, "target": {"con": body.get("con", 0), "ses": body.get("ses", 0)},
                    "results": results}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _run_step(self, sess, st):
        import time
        if "tcode" in st:
            sess.findById("wnd[0]/tbar[0]/okcd").Text = "/n" + st["tcode"]
            sess.findById("wnd[0]").sendVKey(0)
            return {"tcode": st["tcode"], "now": str(sess.Info.Transaction)}
        if "set" in st:
            f = sess.findById(st["set"])
            f.Text = str(st["to"])
            return {"set": st["set"], "value": str(f.Text)}
        if "select" in st:
            sess.findById(st["select"]).Selected = (st.get("value") is not False)
            return {"select": st["select"], "selected": (st.get("value") is not False)}
        if "vkey" in st:
            sess.findById("wnd[%d]" % st.get("wnd", 0)).sendVKey(int(st["vkey"]))
            return {"vkey": st["vkey"]}
        if "tab" in st:
            sess.findById(st["tab"]).Select()
            return {"tab": st["tab"]}
        if "press" in st:
            sess.findById(st["press"]).Press()
            return {"press": st["press"]}
        if "selectRows" in st:
            t = sess.findById(st["selectRows"])
            want = set(st.get("rows", []))
            for j in range(t.Rows.Count):
                t.Rows(j).Selected = (j in want)
            return {"selectRows": st["selectRows"], "selected": st.get("rows", [])}
        if "read" in st:
            r = sess.findById(st["read"])
            val = (str(r.MessageType) + ":" + str(r.Text)) if "sbar" in st["read"] else str(r.Text)
            return {"read": st["read"], "value": val}
        if "snapshot" in st:
            return {"snapshot": self._walk(sess.findById(st["snapshot"]), 0, st.get("maxDepth", 6))}
        if "screenshot" in st:
            p = st.get("path") or _default_shot_path()
            return _hardcopy_png(sess.findById("wnd[0]"), p)
        if "sleep" in st:
            time.sleep(st["sleep"] / 1000.0)
            return {"slept": st["sleep"]}
        return {"error": "unknown/unsupported step on Windows", "step": st}
