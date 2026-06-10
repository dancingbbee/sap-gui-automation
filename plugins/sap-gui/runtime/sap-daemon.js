// sap-daemon.js — HTTP daemon over SAP GUI for Java Scripting API.
// v2 (production). Runs inside SAP GUI's Nashorn engine on a background thread.
//
// Launch:   SAPGUI -f /path/to/sap-daemon.js
// Listen:   127.0.0.1:18765  (loopback only)
// Auth:     every request must carry  X-Token: <contents of ~/.sap-daemon/token>
//
// Endpoints (all POST take a JSON body; all responses are JSON):
//   GET  /health                          → { ok, ts, conns, version }
//   POST /exec      { script, edt? }       → { ok, value | error }
//   POST /snapshot  { id?, maxDepth? }     → { ok, tree }
//   POST /screenshot{ path?, match? }      → { ok, path, w, h }
//   POST /transact  { steps: [...] }       → { ok, results }   (see runStep)
//
// Design notes learned during the spike:
//   - SAP wrapper objects do their own threading; calling them ON the Swing EDT
//     deadlocks. So EDT is OFF by default. Only Frame.paintAll() needs the EDT.
//   - openConnection("name") returns null; auto-login via conn= arg hangs.
//     The supported path is: user double-clicks a Logon Pad entry once.
//   - Robot screen-capture only sees the primary display and is occluded by
//     other windows. Frame.paintAll() renders the component tree directly, so
//     it is occlusion- and multi-monitor-independent.

var PORT  = 18765;
var BIND  = "127.0.0.1";
var TOKEN_PATH = java.lang.System.getProperty("user.home") + "/.sap-daemon/token";
var CACHE_DIR  = java.lang.System.getProperty("user.home") + "/Library/Caches/sap-daemon";
var LOG   = CACHE_DIR + "/daemon.log";
var SHOT_TTL_MS = 60 * 60 * 1000;   // screenshots older than 1h get swept
var SWEEP_EVERY_MS = 10 * 60 * 1000;

var ServerSocket   = java.net.ServerSocket;
var InetAddress    = java.net.InetAddress;
var Runnable       = java.lang.Runnable;
var Thread         = java.lang.Thread;
var SwingUtilities = javax.swing.SwingUtilities;
var File           = java.io.File;

function ts() { return new java.util.Date().toString(); }

function log(msg) {
  try {
    var fw = new java.io.FileWriter(LOG, true);
    fw.write(ts() + " | " + msg + "\n");
    fw.close();
  } catch (e) {}
}

function readToken() {
  try {
    var f = new File(TOKEN_PATH);
    if (!f.exists()) return null;
    var s = new java.util.Scanner(f, "UTF-8");
    try { return s.hasNext() ? String(s.next()).trim() : null; }
    finally { s.close(); }
  } catch (e) { return null; }
}

var EXPECTED_TOKEN = readToken();

// ---- EDT helper (only used for Swing paint) ----
function runOnEDT(fn) {
  var box = { value: undefined, err: null };
  var r = new Runnable({ run: function() { try { box.value = fn(); } catch (e) { box.err = e; } } });
  if (SwingUtilities.isEventDispatchThread()) r.run();
  else SwingUtilities.invokeAndWait(r);
  if (box.err) throw box.err;
  return box.value;
}

// ---- target resolution ----
// A target is a (connection, session) pair. Identify it by index (con/ses) or
// by name (system substring / window-title substring). resolveTarget returns
// {con, ses, prefix} where prefix = "/app/con[c]/ses[s]".
function listTargets() {
  var out = [];
  var conns = application.getConnections();
  for (var c = 0; c < conns.getLength(); c++) {
    var conn = conns.elementAt(c);
    var sessions = conn.getSessions();
    for (var s = 0; s < sessions.getLength(); s++) {
      var ses = sessions.elementAt(s);
      var t = { con: c, ses: s, prefix: "/app/con[" + c + "]/ses[" + s + "]" };
      try {
        var info = ses.info;
        t.system = String(info.getSystemName());
        t.client = String(info.getClient());
        t.user = String(info.getUser());
        t.tcode = String(info.getTransaction());
      } catch (e) { t.infoErr = String(e); }
      // window titles + count (popups stack as wnd[0], wnd[1], ...)
      t.windows = [];
      for (var w = 0; w < 8; w++) {
        try {
          var wnd = ses.findById("wnd[" + w + "]");
          if (wnd == null) break;
          t.windows.push(String(wnd.getText()));
        } catch (e) { break; }
      }
      out.push(t);
    }
  }
  return out;
}

function resolveTarget(opts) {
  opts = opts || {};
  // explicit index wins
  if (opts.con != null || opts.ses != null) {
    var c = opts.con || 0, s = opts.ses || 0;
    return { con: c, ses: s, prefix: "/app/con[" + c + "]/ses[" + s + "]" };
  }
  // name-based: match against system name or any window title
  if (opts.system != null || opts.match != null) {
    var targets = listTargets();
    for (var i = 0; i < targets.length; i++) {
      var t = targets[i];
      if (opts.system != null && t.system && t.system.indexOf(opts.system) >= 0) return t;
      if (opts.match != null) {
        for (var w = 0; w < t.windows.length; w++) {
          if (t.windows[w].indexOf(opts.match) >= 0) return t;
        }
      }
    }
    throw new java.lang.RuntimeException("no target matches system=" + opts.system + " match=" + opts.match);
  }
  // default
  return { con: 0, ses: 0, prefix: "/app/con[0]/ses[0]" };
}

function session(idx) {
  return application.findById("/app/con[0]/ses[" + (idx || 0) + "]");
}

// ---- snapshot (recursive UI walk) ----
function snapshot(comp, depth, maxDepth) {
  if (depth > maxDepth) return { _truncated: true };
  var node = { id: String(comp.getId()), type: String(comp.getType()), name: String(comp.getName()) };
  try { var t = comp.getText(); if (t != null) node.text = String(t); } catch (e) {}
  try {
    if (comp.isContainerType && comp.isContainerType()) {
      var kids = comp.getChildren();
      if (kids != null) {
        var len = kids.getLength();
        node.children = [];
        for (var i = 0; i < Math.min(len, 200); i++) {
          node.children.push(snapshot(kids.elementAt(i), depth + 1, maxDepth));
        }
        if (len > 200) node._dropped = len - 200;
      }
    }
  } catch (e) { node._err = String(e); }
  return node;
}

// ---- screenshot via Frame.paintAll (occlusion-independent) ----
// enlarge (default true): temporarily grow a small SAP window so the capture is
// large/legible, then restore. setSize/setBounds do NOT change z-order or focus
// (verified) — the window does NOT come to front, so the user's other work is
// undisturbed. paintAll renders the component tree regardless of occlusion.
var ENLARGE_W = 1600, ENLARGE_H = 1000;
var ENLARGE_RELAYOUT_MS = 600;     // SAP relayouts its working pane async on resize
var ENLARGE_OFFSCREEN_X = 30000;   // move off-screen during enlarge so it's invisible

function screenshot(path, match, enlarge) {
  var Frame         = java.awt.Frame;
  var BufferedImage = java.awt.image.BufferedImage;
  var ImageIO       = javax.imageio.ImageIO;

  var target = null, origBounds = null;

  // step 1 (EDT): locate the frame; if small, move it OFF-SCREEN and enlarge.
  // Doing the resize off-screen means the user never sees the window grow/shrink
  // (the earlier in-place resize was visible behind other windows). setBounds
  // does NOT change z-order/focus, so the window does not come to front.
  runOnEDT(function() {
    var frames = Frame.getFrames();
    for (var i = 0; i < frames.length; i++) {
      var f = frames[i];
      if (!f.isShowing()) continue;
      var title = String(f.getTitle());
      var cls = String(f.getClass().getName());
      if (match && title.indexOf(match) >= 0) { target = f; break; }
      if (!match && cls.indexOf("SAPFrame") >= 0) {
        if (target == null || (f.getWidth() * f.getHeight()) > (target.getWidth() * target.getHeight())) target = f;
      }
    }
    if (target == null) throw new java.lang.RuntimeException("no matching SAP frame (match=" + match + ")");
    if (enlarge !== false && (target.getWidth() < ENLARGE_W || target.getHeight() < ENLARGE_H)) {
      origBounds = target.getBounds();
      var ew = Math.max(ENLARGE_W, target.getWidth()), eh = Math.max(ENLARGE_H, target.getHeight());
      target.setBounds(ENLARGE_OFFSCREEN_X, origBounds.y, ew, eh);  // off-screen + enlarged, atomic
      target.validate();
    }
  });

  // step 2: let SAP process the resize (relayout the working pane) before
  // painting — otherwise the content stays small inside a large canvas.
  if (origBounds != null) { try { Thread.sleep(ENLARGE_RELAYOUT_MS); } catch (e) {} }

  // step 3 (EDT): paint the (now enlarged) component tree to PNG.
  var result = runOnEDT(function() {
    var w = target.getWidth(), h = target.getHeight();
    var img = new BufferedImage(w, h, BufferedImage.TYPE_INT_ARGB);
    var g = img.createGraphics();
    target.paintAll(g);
    g.dispose();
    new File(CACHE_DIR).mkdirs();
    ImageIO.write(img, "png", new File(path));
    return { ok: true, path: path, w: w, h: h, title: String(target.getTitle()), enlarged: (origBounds != null) };
  });

  // step 4 (EDT): restore original size.
  if (origBounds != null) {
    runOnEDT(function() { try { target.setBounds(origBounds); target.validate(); } catch (e) {} });
  }
  return result;
}

// ---- transact: declarative multi-step driver ----
// step kinds:
//   { tcode: "MM03" }                              → /n<tcode> + Enter
//   { set: "wnd[0]/usr/ctxtRMMG1-MATNR", to: "X" } → field.setText
//   { vkey: 0, wnd: 0 }                            → window.sendVKey
//   { tab: "wnd[0]/usr/tabsTABSPR1/tabpSP02" }     → tab.select
//   { selectRows: "wnd[1]/usr/tblXXX", rows: [0] } → table row select (others off)
//   { select: "wnd[0]/usr/chkX", value: true }     → checkbox/radio setSelected
//   { press: "wnd[1]/tbar[0]/btn[0]" }             → button.press
//   { read: "wnd[0]/usr/ctxtX" }                   → returns getText
//   { sleep: 500 }                                 → Thread.sleep(ms)
//   { snapshot: "wnd[0]/usr", maxDepth: 4 }        → subtree snapshot
//   { screenshot: true, match?: "...", path?: "...", enlarge?: false }
function abs(id, prefix) {
  if (id.indexOf("/app/") === 0) return id;       // already absolute
  return (prefix || "/app/con[0]/ses[0]") + "/" + id;
}

function runStep(step, tgt) {
  var prefix = tgt.prefix;
  if (step.tcode != null) {
    var s = application.findById(prefix);
    s.findById("wnd[0]/tbar[0]/okcd").setText("/n" + step.tcode);
    s.findById("wnd[0]").sendVKey(0);
    return { tcode: step.tcode, now: String(s.info.getTransaction()) };
  }
  if (step.set != null) {
    var f = application.findById(abs(step.set, prefix));
    f.setText(String(step.to));
    return { set: step.set, value: String(f.getText()) };
  }
  if (step.vkey != null) {
    var wid = "wnd[" + (step.wnd || 0) + "]";
    application.findById(abs(wid, prefix)).sendVKey(step.vkey);
    return { vkey: step.vkey };
  }
  if (step.tab != null) {
    application.findById(abs(step.tab, prefix)).select();
    return { tab: step.tab };
  }
  if (step.selectRows != null) {
    var t = application.findById(abs(step.selectRows, prefix));
    var rows = t.getRows();
    var want = {}; for (var i = 0; i < step.rows.length; i++) want[step.rows[i]] = true;
    for (var j = 0; j < rows.getLength(); j++) rows.elementAt(j).setSelected(!!want[j]);
    return { selectRows: step.selectRows, selected: step.rows };
  }
  if (step.press != null) {
    application.findById(abs(step.press, prefix)).press();
    return { press: step.press };
  }
  if (step.select != null) {                 // checkbox / radio toggle
    var c = application.findById(abs(step.select, prefix));
    c.setSelected(step.value !== false);      // value omitted → true
    return { select: step.select, selected: (step.value !== false) };
  }
  if (step.read != null) {
    var r = application.findById(abs(step.read, prefix));
    var val = (step.read.indexOf("sbar") >= 0)
      ? (String(r.getMessageType()) + ":" + String(r.getText()))   // status bar: type+text
      : String(r.getText());
    return { read: step.read, value: val };
  }
  if (step.sleep != null) {
    Thread.sleep(step.sleep);
    return { slept: step.sleep };
  }
  if (step.snapshot != null) {
    var comp = application.findById(abs(step.snapshot, prefix));
    return { snapshot: snapshot(comp, 0, step.maxDepth || 6) };
  }
  if (step.screenshot != null) {
    var p = step.path || (CACHE_DIR + "/transact-" + java.lang.System.nanoTime() + ".png");
    // screenshot matches by window title; default to the target's active window title
    var m = step.match;
    if (m == null) {
      var tlist = listTargets();
      for (var k = 0; k < tlist.length; k++) {
        if (tlist[k].con === tgt.con && tlist[k].ses === tgt.ses && tlist[k].windows.length > 0) {
          m = tlist[k].windows[tlist[k].windows.length - 1]; break;
        }
      }
    }
    return screenshot(p, m, step.enlarge);
  }
  return { error: "unknown step", step: step };
}

// ---- HTTP plumbing ----
function readBody(br, contentLength) {
  if (contentLength <= 0) return "";
  var buf = java.lang.reflect.Array.newInstance(java.lang.Character.TYPE, contentLength);
  var read = 0;
  while (read < contentLength) {
    var r = br.read(buf, read, contentLength - read);
    if (r < 0) break;
    read += r;
  }
  return String(new java.lang.String(buf, 0, read));
}

function sendJSON(pw, code, codeText, obj) {
  var body = JSON.stringify(obj);
  var bodyBytes = body.getBytes("UTF-8");
  pw.print("HTTP/1.1 " + code + " " + codeText + "\r\n");
  pw.print("Content-Type: application/json; charset=utf-8\r\n");
  pw.print("Content-Length: " + bodyBytes.length + "\r\n");
  pw.print("Connection: close\r\n\r\n");
  pw.print(body);
  pw.flush();
}

function handle(sock) {
  var br = new java.io.BufferedReader(new java.io.InputStreamReader(sock.getInputStream(), "UTF-8"));
  var pw = new java.io.PrintWriter(new java.io.OutputStreamWriter(sock.getOutputStream(), "UTF-8"));
  try {
    var requestLine = br.readLine();
    if (requestLine == null) { sock.close(); return; }
    var parts = String(requestLine).split(" ");
    var method = parts[0], path = parts[1];
    var contentLength = 0, token = null;
    while (true) {
      var h = br.readLine();
      if (h == null || String(h).length() === 0) break;
      var hs = String(h);
      var low = hs.toLowerCase();
      if (low.indexOf("content-length:") === 0) contentLength = parseInt(hs.substring(15).trim());
      else if (low.indexOf("x-token:") === 0) token = hs.substring(8).trim();
    }
    var bodyStr = contentLength > 0 ? readBody(br, contentLength) : "";
    var bodyJson = {};
    if (bodyStr.length > 0) { try { bodyJson = JSON.parse(bodyStr); } catch (e) {} }

    // auth (health is open so monitoring can ping without token)
    if (path !== "/health" && EXPECTED_TOKEN != null && token !== EXPECTED_TOKEN) {
      log("AUTH FAIL " + method + " " + path);
      sendJSON(pw, 401, "Unauthorized", { ok: false, error: "bad or missing X-Token" });
      sock.close();
      return;
    }

    log("req " + method + " " + path + " bodyLen=" + bodyStr.length);

    if (method === "GET" && path === "/health") {
      var conns = -1;
      try { conns = application.getConnections().getLength(); } catch (e) {}
      sendJSON(pw, 200, "OK", { ok: true, ts: ts(), conns: conns, port: PORT,
                                version: application.getMajorVersion() + "." + application.getMinorVersion() });

    } else if ((method === "GET" || method === "POST") && path === "/targets") {
      try {
        sendJSON(pw, 200, "OK", { ok: true, targets: listTargets() });
      } catch (e) {
        sendJSON(pw, 500, "Error", { ok: false, error: String(e) });
      }

    } else if (method === "POST" && path === "/exec") {
      var script = bodyJson.script || "";
      var useEDT = bodyJson.edt === true;   // default OFF
      try {
        var tgt = resolveTarget(bodyJson);
        // expose target helpers to the script scope:
        //   T    = target path prefix string ("/app/con[c]/ses[s]")
        //   sess = the session wrapper object
        var T = tgt.prefix;
        var sess = application.findById(T);
        var fn = function() { return eval(script); };
        var value = useEDT ? runOnEDT(fn) : fn();
        sendJSON(pw, 200, "OK", { ok: true, target: { con: tgt.con, ses: tgt.ses },
                                  value: (value === undefined ? null : String(value)) });
      } catch (e) {
        sendJSON(pw, 500, "Error", { ok: false, error: String(e) });
      }

    } else if (method === "POST" && path === "/snapshot") {
      try {
        var tgt2 = resolveTarget(bodyJson);
        // id defaults to the target's root; relative ids get the target prefix
        var startId = bodyJson.id ? abs(bodyJson.id, tgt2.prefix) : tgt2.prefix;
        var maxDepth = bodyJson.maxDepth || 10;
        var comp = application.findById(startId);
        if (comp == null) throw new java.lang.RuntimeException("not found: " + startId);
        sendJSON(pw, 200, "OK", { ok: true, target: { con: tgt2.con, ses: tgt2.ses },
                                  tree: snapshot(comp, 0, maxDepth) });
      } catch (e) {
        sendJSON(pw, 500, "Error", { ok: false, error: String(e) });
      }

    } else if (method === "POST" && path === "/screenshot") {
      try {
        var p = bodyJson.path || (CACHE_DIR + "/shot-" + java.lang.System.nanoTime() + ".png");
        var m = bodyJson.match;
        // if no explicit match, derive from target's active window title
        if (m == null && (bodyJson.con != null || bodyJson.ses != null || bodyJson.system != null)) {
          var tgt3 = resolveTarget(bodyJson);
          var tl = listTargets();
          for (var z = 0; z < tl.length; z++) {
            if (tl[z].con === tgt3.con && tl[z].ses === tgt3.ses && tl[z].windows.length > 0) {
              m = tl[z].windows[tl[z].windows.length - 1]; break;
            }
          }
        }
        sendJSON(pw, 200, "OK", screenshot(p, m, bodyJson.enlarge));
      } catch (e) {
        sendJSON(pw, 500, "Error", { ok: false, error: String(e) });
      }

    } else if (method === "POST" && path === "/transact") {
      try {
        var tgt4 = resolveTarget(bodyJson);
        var steps = bodyJson.steps || [];
        var results = [];
        for (var i = 0; i < steps.length; i++) {
          results.push(runStep(steps[i], tgt4));
        }
        sendJSON(pw, 200, "OK", { ok: true, target: { con: tgt4.con, ses: tgt4.ses }, results: results });
      } catch (e) {
        sendJSON(pw, 500, "Error", { ok: false, error: String(e), partial: true });
      }

    } else {
      sendJSON(pw, 404, "Not Found", { ok: false, error: "unknown route " + method + " " + path });
    }
  } catch (e) {
    log("handle err: " + e);
    try { sendJSON(pw, 500, "Error", { ok: false, error: String(e) }); } catch (e2) {}
  } finally {
    try { sock.close(); } catch (e) {}
  }
}

// ---- dismiss SAP's "script finished" popup ----
// SAP GUI for Java pops a modal titled "스크립팅" ("스크립트 실행이 완료되었습니다")
// whenever an -f script returns. It can't be disabled — it fires even for an
// empty script and no settings flag controls it. So we dismiss it: while the
// dialog is present, bring SAP frontmost and press Return (its default OK
// button). AXPress on the Swing button does NOT work, but the default-button
// keystroke does. Polls ~9s and only acts while the dialog exists, so it won't
// steal focus afterward. Requires macOS Automation permission for the launcher
// app (granted once on first run).
function dismissFinishDialogs() {
  var as =
    'repeat 30 times\n' +
    '  set hit to false\n' +
    '  try\n' +
    '    tell application "System Events"\n' +
    '      repeat with proc in (every application process whose name contains "SAPGUI")\n' +
    '        repeat with w in (every window of proc)\n' +
    '          if (name of w) is "스크립팅" then set hit to true\n' +
    '        end repeat\n' +
    '        if hit then set frontmost of proc to true\n' +
    '      end repeat\n' +
    '      if hit then\n' +
    '        delay 0.1\n' +
    '        key code 36\n' +
    '      end if\n' +
    '    end tell\n' +
    '  end try\n' +
    '  delay 0.3\n' +
    'end repeat\n';
  new Thread(new Runnable({ run: function() {
    try { new java.lang.ProcessBuilder(["osascript", "-e", as]).start().waitFor(); }
    catch (e) { log("dismiss err: " + e); }
  }}), "sap-daemon-dismiss").start();
}

// ---- accept loop ----
function acceptLoop(srv) {
  log("accept loop start");
  while (true) {
    try {
      var sock = srv.accept();
      new Thread(new Runnable({ run: function() { handle(sock); } }), "sap-daemon-handler").start();
    } catch (e) { log("accept err: " + e); }
  }
}

// ---- housekeeping: sweep old screenshots ----
function startSweeper() {
  new Thread(new Runnable({ run: function() {
    while (true) {
      try {
        var dir = new File(CACHE_DIR);
        if (dir.exists()) {
          var files = dir.listFiles();
          var cutoff = java.lang.System.currentTimeMillis() - SHOT_TTL_MS;
          for (var i = 0; i < files.length; i++) {
            var f = files[i];
            if (String(f.getName()).toLowerCase().endsWith(".png") && f.lastModified() < cutoff) f.delete();
          }
        }
        Thread.sleep(SWEEP_EVERY_MS);
      } catch (e) { try { Thread.sleep(SWEEP_EVERY_MS); } catch (e2) {} }
    }
  }}), "sap-daemon-sweeper").start();
}

// ---- boot ----
new File(CACHE_DIR).mkdirs();
log("=== sap-daemon v2 starting (auth=" + (EXPECTED_TOKEN != null) + ") ===");
var server = null;
try {
  server = new ServerSocket(PORT, 50, InetAddress.getByName(BIND));
  log("bound on " + BIND + ":" + PORT);
} catch (e) {
  // Another SAP instance already owns the daemon port. Do NOT throw — throwing
  // pops a SAP scripting error dialog. Just skip the daemon: this SAP window
  // works normally, and the existing daemon already covers every connection
  // and session via multi-target, so a second daemon is unnecessary.
  log("port " + PORT + " already in use — skipping daemon (another SAP instance owns it): " + e);
  server = null;
}

// Always auto-dismiss SAP's "script finished" popup (fires whether or not we
// bound the port — the -f script returns in both cases).
dismissFinishDialogs();

if (server != null) {
  startSweeper();
  // Run the accept loop on a NON-daemon background thread and let the -f script
  // return immediately. Blocking the -f script thread interferes with SAP's
  // startup/UI (the login form becomes briefly unclickable), so we must return.
  // setDaemon(false) keeps the JVM (and thus the daemon) alive after return.
  var t = new Thread(new Runnable({ run: function() { acceptLoop(server); } }), "sap-daemon");
  t.setDaemon(false);
  t.start();
  log("daemon ready (background thread)");
}
// else: port already owned by another SAP instance's daemon — just return.
