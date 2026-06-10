"""Windows backend — drives SAP GUI for Windows via COM (win32com).

No daemon/token/launcher: SAP GUI registers its scripting engine in the OS
Running Object Table when running + logged in, and we attach with
GetObject("SAPGUI"). The transact step JSON is the shared interface; exec(JS)
is macOS-only and returns an unsupported error here.

Screenshots use the Win32 **PrintWindow** API (PW_RENDERFULLCONTENT) instead of
SAP GUI's HardCopy. PrintWindow renders the window into an off-screen device
context via WM_PRINT, so it:
  * does NOT bring the SAP window to the foreground (the user's other work is
    undisturbed — HardCopy tended to foreground/activate the window),
  * captures even when the window is occluded or minimized,
  * can capture modal popups (wnd[1]/wnd[2]) directly,
  * produces a PIL image saved straight to PNG (no BMP detour).
HardCopy(BMP→Pillow) remains a fallback when pywin32/Pillow are unavailable.

win32com et al. are imported lazily (inside functions) so importing this module
on macOS (where pywin32 is absent) never fails — backends/__init__ only loads it
on Windows anyway.
"""
import os
import re

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


def _target_of(sess):
    """Parse {con, ses} out of a session's Id (e.g. /app/con[0]/ses[1])."""
    try:
        m = re.search(r"con\[(\d+)\]/ses\[(\d+)\]", str(sess.Id))
        if m:
            return {"con": int(m.group(1)), "ses": int(m.group(2))}
    except Exception:
        pass
    return {}


def _clean_com_error(e):
    """Turn a raw pywintypes.com_error into a readable one-liner (OBS-1).

    SAP scripting errors arrive as COM errors whose human text is buried in
    excepinfo[2] (e.g. "The control could not be found by id."). Surface that
    instead of the opaque (hresult, msg, excepinfo, arg) tuple.
    """
    try:
        import pywintypes
        if isinstance(e, pywintypes.com_error):
            info = getattr(e, "excepinfo", None)
            if info and len(info) > 2 and info[2]:
                return str(info[2]).strip()
            if getattr(e, "strerror", None):
                return str(e.strerror)
            return "COM error %s" % (e.args[0] if e.args else "")
    except Exception:
        pass
    return str(e)


def _default_shot_path():
    return os.path.join(os.environ.get("TEMP", os.getcwd()), "sap-shot.png")


def _is_png(path):
    try:
        with open(path, "rb") as f:
            return f.read(8) == b"\x89PNG\r\n\x1a\n"
    except Exception:
        return False


def _hardcopy_png(window, path):
    """Fallback capture via SAP GUI HardCopy when PrintWindow is unavailable.

    HardCopy(filename) ignores the extension and writes BMP. We:
      1) try HardCopy(filename, "PNG") — newer SAP GUI supports it,
      2) verify the file is really PNG (magic bytes),
      3) else fall back to BMP + Pillow conversion,
      4) if Pillow is absent, keep the BMP and report the real path/format.
    """
    try:
        window.HardCopy(path, "PNG")
        if _is_png(path):
            return {"ok": True, "path": path, "format": "png", "method": "hardcopy"}
    except Exception:
        pass
    bmp = (path[:-4] if path.lower().endswith(".png") else path) + ".bmp"
    try:
        window.HardCopy(bmp)
    except Exception as e:
        return {"ok": False, "error": "HardCopy failed: %s" % _clean_com_error(e)}
    try:
        from PIL import Image
        Image.open(bmp).save(path, "PNG")
        try:
            os.remove(bmp)
        except Exception:
            pass
        return {"ok": True, "path": path, "format": "png", "method": "hardcopy",
                "note": "converted from BMP via Pillow"}
    except ImportError:
        return {"ok": True, "path": bmp, "format": "bmp", "method": "hardcopy",
                "note": "saved BMP (PNG needs Pillow: pip install Pillow). "
                        "Claude image Read wants PNG/JPG — convert if needed."}
    except Exception as e:
        return {"ok": True, "path": bmp, "format": "bmp", "method": "hardcopy",
                "note": "PNG convert failed: %s" % e}


class ComBackend(Backend):
    # ---- target resolution (index | system name | window title) ----
    def _resolve(self, app, body):
        con = body.get("con")
        ses = body.get("ses")
        if con is not None or ses is not None:
            return _session(app, con or 0, ses or 0)
        system = body.get("system")
        match = body.get("match")
        if system or match:
            for c in range(app.Children.Count):
                conn = app.Children(c)
                for s in range(conn.Children.Count):
                    sess = conn.Children(s)
                    if system and system.lower() in str(sess.Info.SystemName).lower():
                        return sess
                    if match:
                        try:
                            if match.lower() in str(sess.findById("wnd[0]").Text).lower():
                                return sess
                        except Exception:
                            pass
            raise RuntimeError("no SAP target matched (system=%r match=%r)" % (system, match))
        return _session(app, 0, 0)

    # ---- lifecycle ----
    def health(self, timeout):
        try:
            app = _engine()
            return {"ok": True, "conns": app.Children.Count,
                    "version": "%s.%s" % (app.MajorVersion, app.MinorVersion),
                    "os": "windows"}
        except Exception as e:
            return {"ok": False, "error": _clean_com_error(e)}

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
            return {"ok": False, "error": _clean_com_error(e)}
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
            sess = self._resolve(app, body)
            sid = body.get("id")
            start = sess.findById(sid) if sid else sess
            return {"ok": True, "target": _target_of(sess),
                    "tree": self._walk(start, 0, body.get("maxDepth", 10))}
        except Exception as e:
            return {"ok": False, "error": _clean_com_error(e)}

    # ---- screenshot (PrintWindow — front-independent, modal-capable) ----
    def _active_window_id(self, sess):
        """Highest existing wnd index — so modal popups (wnd[1]+) are captured
        by default instead of the main window beneath them (BUG-4)."""
        last = "wnd[0]"
        for w in range(1, 8):
            try:
                sess.findById("wnd[%d]" % w)
                last = "wnd[%d]" % w
            except Exception:
                break
        return last

    def _get_window_handle(self, sess, window_id):
        """Native HWND for a SAP window: COM .Handle first, else match by title."""
        import win32gui
        window = sess.findById(window_id)
        try:
            hwnd = window.Handle
            if hwnd and win32gui.IsWindow(hwnd):
                return int(hwnd)
        except Exception:
            pass
        title = str(window.Text)
        found = []

        def _enum(h, _):
            if win32gui.IsWindowVisible(h) and win32gui.GetWindowText(h) == title:
                found.append(h)
            return True

        try:
            win32gui.EnumWindows(_enum, None)
        except Exception:
            pass
        return found[0] if found else None

    def _capture_printwindow(self, hwnd, width, height):
        """PrintWindow(PW_RENDERFULLCONTENT) → PIL image. Captures occluded windows."""
        import ctypes
        import win32gui
        import win32ui
        from PIL import Image
        hwndDC = win32gui.GetWindowDC(hwnd)
        mfcDC = win32ui.CreateDCFromHandle(hwndDC)
        saveDC = mfcDC.CreateCompatibleDC()
        bmp = win32ui.CreateBitmap()
        bmp.CreateCompatibleBitmap(mfcDC, width, height)
        saveDC.SelectObject(bmp)
        # PW_RENDERFULLCONTENT = 2 (Windows 8.1+); renders without foregrounding.
        ctypes.windll.user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), 2)
        bmpinfo = bmp.GetInfo()
        bmpstr = bmp.GetBitmapBits(True)
        img = Image.frombuffer("RGB", (bmpinfo["bmWidth"], bmpinfo["bmHeight"]),
                               bmpstr, "raw", "BGRX", 0, 1)
        win32gui.DeleteObject(bmp.GetHandle())
        saveDC.DeleteDC()
        mfcDC.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwndDC)
        return img

    # Off-screen enlarge (parity with macOS): grow a small window so the capture
    # is large/legible, then restore. Done off-screen with SWP_NOACTIVATE so the
    # window never comes to front or changes z-order — the user is undisturbed.
    _ENLARGE_W = 1600
    _ENLARGE_H = 1000
    _OFFSCREEN_X = 30000
    _RELAYOUT_S = 0.6   # SAP relayouts its working pane async on resize

    def _printwindow_png(self, sess, path, window_id, enlarge=True):
        """Capture `window_id` to PNG via PrintWindow without foregrounding.

        Returns a result dict on success, or None if dependencies are missing /
        capture fails (caller then falls back to HardCopy)."""
        try:
            import ctypes
            import time
            import win32gui
            import win32ui  # noqa: F401  (needed by _capture_printwindow)
            from PIL import Image, ImageGrab  # noqa: F401
        except Exception:
            return None  # pywin32/Pillow missing → fall back to HardCopy
        try:
            window = sess.findById(window_id)
        except Exception:
            return None
        user32 = ctypes.windll.user32
        hwnd = self._get_window_handle(sess, window_id)
        SWP_NOZORDER = 0x0004
        SWP_NOACTIVATE = 0x0010

        def _rect(h):
            try:
                l, t, r, b = win32gui.GetWindowRect(h)
                return [l, t, r - l, b - t]
            except Exception:
                return None

        # 1) minimized → restore off-screen (no visible flicker), capture,
        #    re-minimize. SW_SHOWMINIMIZED→SHOWNORMAL with an off-screen normal
        #    rect, DWM transitions disabled, avoids the restore animation.
        was_min = False
        placement = None
        if hwnd and user32.IsIconic(hwnd):
            was_min = True
            placement = win32gui.GetWindowPlacement(hwnd)
            rc = placement[4]
            w = rc[2] - rc[0]
            h = rc[3] - rc[1]
            off = (self._OFFSCREEN_X, self._OFFSCREEN_X, self._OFFSCREEN_X + w, self._OFFSCREEN_X + h)
            try:
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, 3, ctypes.byref(ctypes.c_int(1)), ctypes.sizeof(ctypes.c_int))
            except Exception:
                pass
            win32gui.SetWindowPlacement(hwnd, (placement[0], 2, placement[2], placement[3], off))
            win32gui.SetWindowPlacement(hwnd, (placement[0], 1, placement[2], placement[3], off))
            time.sleep(0.3)

        # current native rect (GetWindowRect is authoritative; fall back to COM)
        nr = _rect(hwnd) if hwnd else None
        if nr:
            left, top, width, height = nr
        else:
            try:
                left, top = int(window.Left), int(window.Top)
                width, height = int(window.Width), int(window.Height)
            except Exception:
                left = top = width = height = 0

        # 2) enlarge a small window off-screen (legibility). SWP_NOACTIVATE keeps
        #    it in the background — no focus/z-order change (mirrors macOS).
        restore_rect = None
        if (enlarge and not was_min and hwnd and width > 0 and height > 0
                and (width < self._ENLARGE_W or height < self._ENLARGE_H)):
            restore_rect = [left, top, width, height]
            ew = max(self._ENLARGE_W, width)
            eh = max(self._ENLARGE_H, height)
            try:
                user32.SetWindowPos(hwnd, 0, self._OFFSCREEN_X, top, ew, eh,
                                    SWP_NOZORDER | SWP_NOACTIVATE)
                time.sleep(self._RELAYOUT_S)
                er = _rect(hwnd)
                if er:
                    left, top, width, height = er
            except Exception:
                restore_rect = None  # couldn't enlarge; capture as-is

        # 3) capture
        img = None
        method = None
        enlarged = restore_rect is not None
        if hwnd and width >= 100 and height >= 100:
            try:
                img = self._capture_printwindow(hwnd, width, height)
                method = "printwindow"
            except Exception:
                img = None

        # 4) restore enlarge
        if restore_rect is not None:
            try:
                user32.SetWindowPos(hwnd, 0, restore_rect[0], restore_rect[1],
                                    restore_rect[2], restore_rect[3],
                                    SWP_NOZORDER | SWP_NOACTIVATE)
            except Exception:
                pass

        # 5) restore minimized
        if was_min and hwnd and placement:
            win32gui.SetWindowPlacement(hwnd, (placement[0], 2, placement[2], placement[3], placement[4]))
            try:
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, 3, ctypes.byref(ctypes.c_int(0)), ctypes.sizeof(ctypes.c_int))
            except Exception:
                pass

        # 6) last resort: grab the on-screen region. Only when the window is
        #    where we read it (not minimized, not staged off-screen for enlarge).
        if img is None and not was_min and not enlarged and width >= 100 and height >= 100:
            try:
                img = ImageGrab.grab(bbox=(left, top, left + width, top + height))
                method = "imagegrab"
            except Exception:
                img = None

        if img is None:
            return None  # let caller fall back to HardCopy
        try:
            img.save(path, "PNG")
        except Exception as e:
            return {"ok": False, "error": "PNG save failed: %s" % e}
        return {"ok": True, "path": path, "format": "png",
                "method": method, "window": window_id, "enlarged": enlarged}

    def _capture(self, sess, path, window_id, enlarge=True):
        """PrintWindow first (front-independent); HardCopy as fallback."""
        res = self._printwindow_png(sess, path, window_id, enlarge)
        if res is not None:
            return res
        try:
            return _hardcopy_png(sess.findById(window_id), path)
        except Exception as e:
            return {"ok": False, "error": _clean_com_error(e)}

    def screenshot(self, body, timeout):
        try:
            app = _engine()
            sess = self._resolve(app, body)
        except Exception as e:
            return {"ok": False, "error": _clean_com_error(e)}
        p = body.get("path") or _default_shot_path()
        wnd = body.get("wnd")
        window_id = "wnd[%d]" % int(wnd) if wnd is not None else self._active_window_id(sess)
        return self._capture(sess, p, window_id, body.get("enlarge", True) is not False)

    # ---- exec: macOS-only ----
    def exec_(self, body, timeout):
        return {"ok": False,
                "error": "exec (raw JS) is macOS-only. On Windows use transact steps."}

    # ---- transact: step JSON → COM ----
    def transact(self, body, timeout):
        try:
            app = _engine()
            sess = self._resolve(app, body)
        except Exception as e:
            return {"ok": False, "error": _clean_com_error(e)}
        results = []
        for st in body.get("steps", []):
            try:
                results.append(self._run_step(sess, st))
            except Exception as e:
                msg = _clean_com_error(e)
                results.append({"error": msg, "step": st})
                # Stop the batch on first failure (don't press buttons on a
                # wrong screen); return partial results for self-diagnosis.
                return {"ok": False, "target": _target_of(sess),
                        "results": results, "error": "step failed: %s" % msg}
        return {"ok": True, "target": _target_of(sess), "results": results}

    def _run_step(self, sess, st):
        import time
        if "tcode" in st:
            raw = str(st["tcode"]).strip()
            tc = (raw[2:] if raw[:2].lower() == "/n" else raw).upper()

            def _go():
                sess.findById("wnd[0]/tbar[0]/okcd").Text = "/n" + tc
                sess.findById("wnd[0]").sendVKey(0)

            _go()
            now = str(sess.Info.Transaction)
            if now.upper() != tc:
                # First tcode right after attach can silently no-op (BUG-5);
                # retry once before reporting.
                time.sleep(0.3)
                _go()
                now = str(sess.Info.Transaction)
            return {"tcode": tc, "now": now, "ok": now.upper() == tc}
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
            wnd = st.get("wnd")
            window_id = "wnd[%d]" % int(wnd) if wnd is not None else self._active_window_id(sess)
            return self._capture(sess, p, window_id, st.get("enlarge", True) is not False)
        if "sleep" in st:
            time.sleep(st["sleep"] / 1000.0)
            return {"slept": st["sleep"]}
        return {"error": "unknown/unsupported step on Windows", "step": st}
