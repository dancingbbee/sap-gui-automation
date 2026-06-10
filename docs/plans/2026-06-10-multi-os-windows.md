# 멀티OS (Windows) 지원 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `sap-gui` 플러그인을 macOS 전용에서 macOS+Windows 멀티OS 로 확장한다 (단일 `sapctl`, OS별 백엔드).

**Architecture:** `sapctl`(Python)이 `platform.system()` 으로 백엔드 선택 — macOS=기존 HTTP daemon, Windows=win32com COM. `transact` step JSON 이 OS 중립 공통 인터페이스, `exec`(JS)는 macOS 전용. skill/playbook/캐시 공유.

**Tech Stack:** Python 3 (stdlib + win32com on Windows), SAP GUI Scripting (Java daemon / Windows COM), PowerShell (install.ps1).

**검증 방식:** SAP 실물 의존이라 통합 검증 위주. macOS = 이 환경에서 `sapctl` 실제 실행. Windows = 사용자 윈도우 PC 베타. 순수 로직(OS 감지/step 정규화)은 인라인 assert.

**참조:** spec `docs/specs/2026-06-10-multi-os-windows-design.md`

---

## File Structure

```
plugins/sap-gui/runtime/
├── sapctl                 # [MODIFY] 얇게 — 인자 파싱 + 백엔드 선택 + 출력
├── backends/
│   ├── __init__.py        # [CREATE] select_backend(): platform 분기
│   ├── base.py            # [CREATE] Backend ABC (인터페이스 계약)
│   ├── http_mac.py        # [CREATE] 기존 sapctl 의 HTTP 로직 이전
│   └── com_win.py         # [CREATE] win32com COM 백엔드 (지연 import)
├── sap-daemon.js          # [MODIFY] transact 에 select/read step 추가
├── install.ps1            # [CREATE] Windows 설치 점검·안내
└── uninstall.ps1          # [CREATE] Windows 해제
```

---

## Task 1: 백엔드 추상화 + macOS 로직 이전 (회귀 위험 — 최우선 검증)

기존 272줄 `sapctl` 의 HTTP/daemon 로직을 `backends/http_mac.py` 로 옮기고, `sapctl` 은 백엔드 선택만 하게 얇게 만든다. **macOS 동작이 1바이트도 안 바뀌어야 한다.**

**Files:**
- Create: `plugins/sap-gui/runtime/backends/__init__.py`
- Create: `plugins/sap-gui/runtime/backends/base.py`
- Create: `plugins/sap-gui/runtime/backends/http_mac.py`
- Modify: `plugins/sap-gui/runtime/sapctl`

- [ ] **Step 1: Backend 인터페이스 정의 (base.py)**

```python
# backends/base.py
class Backend:
    """OS-neutral SAP control interface. Subclass per platform."""
    def health(self, timeout): raise NotImplementedError
    def status(self, timeout): raise NotImplementedError
    def start(self, timeout): raise NotImplementedError
    def kill_orphans(self, dry_run): raise NotImplementedError
    def targets(self, timeout): raise NotImplementedError
    def exec_(self, body, timeout): raise NotImplementedError      # macOS only
    def snapshot(self, body, timeout): raise NotImplementedError
    def screenshot(self, body, timeout): raise NotImplementedError
    def transact(self, body, timeout): raise NotImplementedError
```

- [ ] **Step 2: 기존 HTTP 로직을 http_mac.py 로 이전**

현재 `sapctl` 의 `call()`, `token()`, `daemon_pid()`, `cmd_status`, `cmd_start`, `cmd_kill_orphans`, `list_sap_pids`, `_window_count`, 그리고 각 엔드포인트 호출 로직을 `HttpBackend(Backend)` 의 메서드로 그대로 옮긴다. 로직 변경 없이 위치만 이동. 상수(`HOST/PORT/TOKEN_PATH/LAUNCHER`)도 함께.

```python
# backends/http_mac.py
import json, os, subprocess, time, urllib.request, urllib.error
from .base import Backend

HOST = os.environ.get("SAP_DAEMON_HOST", "127.0.0.1")
PORT = int(os.environ.get("SAP_DAEMON_PORT", "18765"))
TOKEN_PATH = os.path.expanduser("~/.sap-daemon/token")
LAUNCHER = os.path.expanduser("~/Applications/SAP (daemon).app")

class HttpBackend(Backend):
    # token(), call(), daemon_pid(), list_sap_pids(), _window_count(),
    # status(), start(), kill_orphans(), targets(), exec_(), snapshot(),
    # screenshot(), transact() — 기존 sapctl 본문에서 그대로 이전.
    # (각 cmd_* 의 call(...) 호출부를 메서드로 래핑)
    ...
```

- [ ] **Step 3: 백엔드 선택기 (__init__.py)**

```python
# backends/__init__.py
import platform
def select_backend():
    sysname = platform.system()
    if sysname == "Darwin":
        from .http_mac import HttpBackend
        return HttpBackend()
    if sysname == "Windows":
        from .com_win import ComBackend   # lazy: win32com only imported here
        return ComBackend()
    raise SystemExit("Unsupported OS: %s (macOS/Windows only)" % sysname)
```

- [ ] **Step 4: sapctl 을 얇게 — 백엔드에 위임**

`sapctl` 의 argparse 는 유지, 각 `cmd` 분기에서 `select_backend()` 의 메서드를 호출하도록 변경. `emit()` 출력 헬퍼는 sapctl 에 유지.

```python
# sapctl (발췌)
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from backends import select_backend
# ... argparse 동일 ...
be = select_backend()
if args.cmd == "health":     return emit(be.health(args.timeout), args.raw)
if args.cmd == "status":     return emit(be.status(args.timeout), args.raw)
if args.cmd == "start":      return emit(be.start(args.timeout), args.raw)
if args.cmd == "kill-orphans": return emit(be.kill_orphans(args.dry_run), args.raw)
if args.cmd == "targets":    return emit(be.targets(args.timeout), args.raw)
if args.cmd == "exec":       return emit(be.exec_({"script":args.script,"edt":args.edt, ...}, args.timeout), args.raw)
if args.cmd == "snapshot":   return emit(be.snapshot({...}, args.timeout), args.raw)
if args.cmd == "screenshot": return emit(be.screenshot({...}, args.timeout), args.raw)
if args.cmd == "transact":   return emit(be.transact({"steps":steps, ...}, args.timeout), args.raw)
```

- [ ] **Step 5: 순수 로직 인라인 테스트 (OS 감지)**

Run:
```bash
cd plugins/sap-gui/runtime && python3 -c "
import platform
from backends import select_backend
assert platform.system()=='Darwin', 'this check is macOS-only'
b=select_backend(); print('backend:', type(b).__name__)
assert type(b).__name__=='HttpBackend'
print('OK')"
```
Expected: `backend: HttpBackend` / `OK` (win32com 이 import 안 됨)

- [ ] **Step 6: macOS 회귀 통합 검증 (SAP 실물)**

SAP(daemon) 실행·로그인 상태에서:
```bash
sapctl health      # {"ok":true,...}
sapctl targets     # 창 목록
sapctl status      # running/conns
echo '{"steps":[{"tcode":"MM03"}]}' | sapctl transact -   # tcode MM03
sapctl screenshot -o /tmp/regress.png    # enlarged PNG
```
Expected: 리팩토링 전과 **동일 출력**. 하나라도 다르면 Step 2 이전 누락.

- [ ] **Step 7: Commit**

```bash
git add plugins/sap-gui/runtime/sapctl plugins/sap-gui/runtime/backends/
git commit -m "refactor(sapctl): extract HTTP logic into backends/http_mac (macOS unchanged)"
```

---

## Task 2: daemon.js 에 select/read step 추가 (macOS, step 인터페이스 완성)

데모에서 `exec`(JS)로 하던 체크박스/라디오 토글·필드 읽기를 transact step 으로 흡수.

**Files:**
- Modify: `plugins/sap-gui/runtime/sap-daemon.js` (runStep 함수)

- [ ] **Step 1: runStep 에 select / read step 추가**

`runStep(step, tgt)` 의 분기 체인에 추가 (기존 set/vkey/tab/press/selectRows/read… 옆):

```javascript
if (step.select != null) {                 // checkbox / radio 토글
  var c = application.findById(abs(step.select, prefix));
  c.setSelected(step.value !== false);      // value 생략 시 true
  return { select: step.select, selected: (step.value !== false) };
}
if (step.read != null) {                    // 필드/상태 읽기 (이미 있으면 확인만)
  var r = application.findById(abs(step.read, prefix));
  var val = (step.read.indexOf("sbar") >= 0)
    ? (r.getMessageType() + ":" + r.getText())
    : String(r.getText());
  return { read: step.read, value: val };
}
```
(주의: `read` 가 이미 있으면 sbar 분기만 보강. `select` 는 신규.)

- [ ] **Step 2: daemon.js parse 체크**

Run: `node --check plugins/sap-gui/runtime/sap-daemon.js`
Expected: parse OK (Nashorn 문법은 SAP 재시작 시 최종 검증)

- [ ] **Step 3: macOS 통합 검증 (SAP 재시작 후)**

SAP(daemon) 재시작 → CS15 류로:
```bash
echo '{"steps":[{"tcode":"CS15"},{"set":"wnd[0]/usr/ctxtRC29L-MATNR","to":"<자재>"},{"select":"wnd[0]/usr/chkRC29L-DIRKT","value":true},{"select":"wnd[0]/usr/chkRC29L-MATTP","value":true},{"read":"wnd[0]/sbar"}]}' | sapctl transact -
```
Expected: 체크박스 2개 select + sbar read 가 step 만으로 동작 (exec 없이).

- [ ] **Step 4: Commit**

```bash
git add plugins/sap-gui/runtime/sap-daemon.js
git commit -m "feat(daemon): add select(checkbox/radio) + sbar read transact steps"
```

---

## Task 3: Windows COM 백엔드 (com_win.py) — 베타 검증

**Files:**
- Create: `plugins/sap-gui/runtime/backends/com_win.py`

- [ ] **Step 1: COM 연결 + 공통 메서드 골격**

```python
# backends/com_win.py  — Windows only; win32com imported lazily by __init__
from .base import Backend

def _engine():
    import win32com.client
    try:
        sapgui = win32com.client.GetObject("SAPGUI")
    except Exception:
        raise RuntimeError("SAP GUI not running / scripting not enabled "
                           "(start SAP GUI, log in, enable scripting).")
    app = sapgui.GetScriptingEngine
    if app is None or app.Children.Count == 0:
        raise RuntimeError("No SAP connection. Log in to a system first.")
    return app

def _session(app, con=0, ses=0):
    return app.Children(int(con)).Children(int(ses))

class ComBackend(Backend):
    def health(self, timeout):
        try:
            app = _engine()
            return {"ok": True, "conns": app.Children.Count,
                    "version": "%s.%s" % (app.MajorVersion, app.MinorVersion), "os": "windows"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def status(self, timeout):
        return self.health(timeout)

    def start(self, timeout):
        return {"ok": True, "note": "Windows: COM attaches automatically. "
                "Just launch SAP GUI and log in (no special launcher needed)."}

    def kill_orphans(self, dry_run):
        return {"ok": True, "note": "Windows: no daemon, nothing to clean (no-op)."}
```

- [ ] **Step 2: targets / snapshot**

```python
    def targets(self, timeout):
        app = _engine(); out = []
        for c in range(app.Children.Count):
            conn = app.Children(c)
            for s in range(conn.Children.Count):
                sess = conn.Children(s); info = sess.Info
                wins = []
                for w in range(8):
                    try: wins.append(str(sess.findById("wnd[%d]" % w).Text))
                    except Exception: break
                out.append({"con": c, "ses": s, "prefix": "/app/con[%d]/ses[%d]" % (c, s),
                            "system": str(info.SystemName), "client": str(info.Client),
                            "user": str(info.User), "tcode": str(info.Transaction), "windows": wins})
        return {"ok": True, "targets": out}

    def _walk(self, comp, depth, maxd):
        node = {"id": str(comp.Id), "type": str(comp.Type), "name": str(comp.Name)}
        try: node["text"] = str(comp.Text)
        except Exception: pass
        try:
            if comp.ContainerType:
                kids = comp.Children; node["children"] = []
                for i in range(min(kids.Count, 200)):
                    node["children"].append(self._walk(kids(i), depth+1, maxd))
        except Exception: pass
        return node

    def snapshot(self, body, timeout):
        app = _engine(); sess = _session(app, body.get("con",0), body.get("ses",0))
        sid = body.get("id"); start = sess.findById(sid) if sid else sess
        return {"ok": True, "tree": self._walk(start, 0, body.get("maxDepth",10))}
```

- [ ] **Step 3: transact (step → COM) + screenshot(hardCopy) + exec 미지원**

```python
    def _abs(self, sess, sid):
        return sid  # findById on session takes relative ids directly on Windows

    def transact(self, body, timeout):
        app = _engine(); sess = _session(app, body.get("con",0), body.get("ses",0))
        results = []
        for st in body.get("steps", []):
            results.append(self._run_step(sess, st))
        return {"ok": True, "results": results}

    def _run_step(self, sess, st):
        import time
        if "tcode" in st:
            sess.findById("wnd[0]/tbar[0]/okcd").Text = "/n"+st["tcode"]
            sess.findById("wnd[0]").sendVKey(0)
            return {"tcode": st["tcode"], "now": str(sess.Info.Transaction)}
        if "set" in st:
            f = sess.findById(st["set"]); f.Text = str(st["to"]); return {"set": st["set"]}
        if "select" in st:
            sess.findById(st["select"]).Selected = (st.get("value") is not False); return {"select": st["select"]}
        if "vkey" in st:
            sess.findById("wnd[%d]" % st.get("wnd",0)).sendVKey(int(st["vkey"])); return {"vkey": st["vkey"]}
        if "tab" in st:   sess.findById(st["tab"]).Select(); return {"tab": st["tab"]}
        if "press" in st: sess.findById(st["press"]).Press(); return {"press": st["press"]}
        if "read" in st:
            r = sess.findById(st["read"])
            val = (r.MessageType+":"+r.Text) if "sbar" in st["read"] else str(r.Text)
            return {"read": st["read"], "value": val}
        if "sleep" in st: time.sleep(st["sleep"]/1000.0); return {"slept": st["sleep"]}
        if "screenshot" in st:
            p = st.get("path") or os.path.join(os.environ.get("TEMP","."), "sap-shot.png")
            sess.findById("wnd[0]").HardCopy(p); return {"ok": True, "path": p}
        return {"error": "unknown/unsupported step on Windows", "step": st}

    def screenshot(self, body, timeout):
        app = _engine(); sess = _session(app, body.get("con",0), body.get("ses",0))
        p = body.get("path") or os.path.join(os.environ.get("TEMP","."), "sap-shot.png")
        sess.findById("wnd[0]").HardCopy(p)
        return {"ok": True, "path": p}

    def exec_(self, body, timeout):
        return {"ok": False, "error": "exec(JS) is macOS-only. Use transact steps on Windows."}
```
(상단에 `import os` 추가.)

- [ ] **Step 4: 구문 체크 (mac 에서 — win32com 은 지연 import 라 통과)**

Run: `python3 -c "import ast; ast.parse(open('plugins/sap-gui/runtime/backends/com_win.py').read()); print('OK')"`
Expected: `OK` (win32com 미설치 mac 에서도 파싱됨 — import 가 함수 안)

- [ ] **Step 5: Commit**

```bash
git add plugins/sap-gui/runtime/backends/com_win.py
git commit -m "feat(win): COM backend (win32com) — transact/snapshot/screenshot/targets"
```

> **베타 검증(윈도우 PC)**: `sapctl health` → conns, `sapctl targets`, `transact` MM03, `screenshot`. §8 함정(hardCopy 포맷/유니코드/GetObject 타이밍) 대응.

---

## Task 4: Windows 설치 스크립트 (install.ps1 / uninstall.ps1)

**Files:**
- Create: `plugins/sap-gui/runtime/install.ps1`
- Create: `plugins/sap-gui/runtime/uninstall.ps1`

- [ ] **Step 1: install.ps1 (점검·안내, 자동 변경 없음)**

```powershell
# install.ps1 — Windows prerequisite check for sap-gui
Write-Host "== sap-gui (Windows) setup ==" -ForegroundColor Green

# 1) Python
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { Write-Host "[!] python not found — install Python 3" -ForegroundColor Yellow }
else { Write-Host "python: $(python --version)" }

# 2) pywin32
python -c "import win32com.client" 2>$null
if ($LASTEXITCODE -ne 0) {
  Write-Host "[!] pywin32 missing. Install with:  pip install pywin32" -ForegroundColor Yellow
} else { Write-Host "pywin32: OK" }

# 3) SAP GUI scripting (점검 안내만 — 레지스트리 자동변경 안 함)
Write-Host "확인: SAP GUI Options > Accessibility & Scripting > Scripting > Enable 체크"
Write-Host "서버측 sapgui/user_scripting = TRUE (안 되면 Basis 팀)"

Write-Host "`n사용: SAP GUI 실행·로그인 후  sapctl health  /  sapctl targets" -ForegroundColor Green
```

- [ ] **Step 2: uninstall.ps1 (가벼움 — 런처/토큰 없음)**

```powershell
# uninstall.ps1 — Windows has no launcher/token/daemon to remove
Write-Host "sap-gui (Windows): nothing to uninstall (no launcher/token/daemon)." -ForegroundColor Green
Write-Host "Remove the plugin via Claude Code: /plugin uninstall sap-gui"
```

- [ ] **Step 3: Commit**

```bash
git add plugins/sap-gui/runtime/install.ps1 plugins/sap-gui/runtime/uninstall.ps1
git commit -m "feat(win): install.ps1 / uninstall.ps1 (prereq check, no auto registry change)"
```

---

## Task 5: playbook / tcode 캐시 step 정리 + sapctl help (OS 공통화)

**Files:**
- Modify: `plugins/sap-gui/skills/sap-gui-control/playbook.md`
- Modify: `~/.claude/skills/sap-gui-pi/tcodes/CS15.md`, `VA05.md` (로컬 — repo 아님)

- [ ] **Step 1: playbook 에 step 우선 안내 + exec=macOS전용 명시**

`playbook.md` §1·§3.5 에 추가: "체크박스/라디오는 `{"select":"<id>","value":true}` step. status bar 는 `{"read":"wnd[0]/sbar"}`. `exec`(JS)는 **macOS 전용** — 윈도우는 step 으로." (기존 exec 예시 옆에 step 대안 병기)

- [ ] **Step 2: 로컬 tcode 캐시(CS15/VA05) step 표현으로 갱신**

`~/.claude/skills/sap-gui-pi/tcodes/CS15.md` 의 exec 시퀀스를 transact step JSON 으로 교체 (select step 사용). VA05 도 동일. (로컬 파일 — repo 커밋 대상 아님)

- [ ] **Step 3: Commit (repo 변경분만)**

```bash
git add plugins/sap-gui/skills/sap-gui-control/playbook.md
git commit -m "docs(playbook): step-first guidance; exec marked macOS-only"
```

---

## Task 6: README / SETUP 윈도우 섹션

**Files:**
- Modify: `README.md`, `SETUP.md`

- [ ] **Step 1: README 에 OS별 설치 분기**

`README.md` "② 최초 설치" 에 탭/섹션: **macOS**(기존) / **Windows**(`pip install pywin32` → SAP GUI 스크립팅 enable → SAP 실행·로그인 → `sapctl health`). daemon/런처/토큰 없음 명시.

- [ ] **Step 2: SETUP.md 윈도우 사전점검**

`SETUP.md §0` 에 Windows 분기: Python3 / pywin32 / SAP GUI for Windows 스크립팅 enable / 서버 user_scripting. (자동화 권한·런처는 macOS 한정 표시)

- [ ] **Step 3: Commit**

```bash
git add README.md SETUP.md
git commit -m "docs: Windows install/prereq sections"
```

---

## Task 7: 버전 2.0.0 + 릴리스

**Files:**
- Modify: `plugins/sap-gui/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`

- [ ] **Step 1: version 1.1.0 → 2.0.0**

두 파일의 `"version"` 을 `2.0.0` 으로.

- [ ] **Step 2: macOS 회귀 최종 확인**

Run: `sapctl health && sapctl targets && echo '{"steps":[{"tcode":"MM03"}]}' | sapctl transact -`
Expected: 정상 (멀티OS 리팩토링 후에도 macOS 무결).

- [ ] **Step 3: Commit + tag + push**

```bash
git add -A
git commit -m "Release 2.0.0 — multi-OS (macOS + Windows) support"
git tag v2.0.0
git push origin main && git push origin v2.0.0
```

---

## 자기 검토 메모

- spec 커버리지: §3 아키텍처→T1, §4 step→T1/T2/T3, §5 매핑→T3, §6 설치→T4, §7 디렉토리→T1·T4, §8 함정→T3 베타, §9 skill→T5, §10 버전→T7. 전부 task 존재.
- 윈도우 task(3)는 mac 에서 parse 만 검증 가능 → 베타 명시.
- 회귀 위험(T1)에 통합 검증 step(6) 배치.
- `select` step 의 property: macOS `setSelected()` / Windows `.Selected=` — 백엔드가 각자 흡수 (계약은 step `{"select":id,"value":bool}` 로 통일).
