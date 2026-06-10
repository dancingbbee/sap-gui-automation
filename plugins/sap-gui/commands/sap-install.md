---
description: 이 PC 에 SAP GUI 자동화 런타임을 설치한다 (OS 자동 분기 — macOS/Windows)
---

# SAP 자동화 런타임 설치

`sapctl` 은 OS 에 따라 다르게 동작한다. **먼저 OS 를 판별하고 분기하라.**

```bash
uname -s    # Darwin → macOS / MINGW·MSYS·CYGWIN 또는 Windows → Windows
```
- `Darwin` → **A. macOS** 절차
- 그 외(Windows/MINGW 등) → **B. Windows** 절차

---

## A. macOS

런타임 = `sap-daemon.js`(SAP GUI for Java 안 HTTP daemon) + `.app` 런처 + 토큰.

**사전 점검** (하나라도 실패하면 멈추고 사용자에게 알려라):
1. `ls -d /Applications/SAP\ Clients/*/*.app/Contents/MacOS/SAPGUI 2>/dev/null` → SAP GUI for Java 설치됨. 없으면 중단.
2. `python3 --version` → Python 3.x
3. SAP GUI Preferences → Web AS ABAP → 스크립팅 → "설정" 체크 (사용자 육안 확인)
4. 서버측 `sapgui/user_scripting=TRUE` (로그인 후 검증; 안 되면 Basis 팀)

**설치**:
1. runtime 디렉토리 찾기: `find ~/.claude/plugins -name install.sh -path '*sap-gui*' 2>/dev/null`
2. `bash <runtime>/install.sh` 실행 — 토큰(`~/.sap-daemon/token`) + 캐시(`~/Library/Caches/sap-daemon`) + 런처(`~/Applications/SAP (daemon).app`) 생성, `sapctl` 을 `~/bin` 에 링크
3. 실행: Finder 에서 **`SAP (daemon)`** 더블클릭 (또는 `sapctl start`) → Logon Pad 로그인 → 첫 실행 시 자동화 권한 "허용"
4. 확인: `sapctl status` → `conns: 1`

해제: `bash <runtime>/uninstall.sh` (`--purge` 로 토큰·캐시까지).

---

## B. Windows

**런타임 설치가 거의 없다.** Windows 는 COM(win32com)으로 SAP 에 직접 attach — daemon·토큰·런처·자동화권한이 **전부 불필요**하다. `install.ps1` 은 점검·안내만 한다.

**사전 점검**:
1. `python --version` → Python 3.x
2. `python -c "import win32com.client"` → 오류 없으면 OK. 오류면 `pip install pywin32`
3. **SAP GUI for Windows** 설치됨 + Options → Accessibility & Scripting → Scripting → **"Enable scripting"** 체크 (사용자 육안 확인; "Notify..." 2개 해제 권장)
4. 서버측 `sapgui/user_scripting=TRUE` (로그인 후 검증; 안 되면 Basis 팀)

**설치 (LLM 이 능동 실행하라 — 안내만 하지 말 것)**:
1. `install.ps1` 경로를 찾는다:
   ```
   Get-ChildItem -Path "$env:USERPROFILE\.claude\plugins" -Recurse -Filter install.ps1 -ErrorAction SilentlyContinue | Select -First 1 -Expand FullName
   ```
   (Bash 도구로 윈도우에서 돌 때는 `powershell.exe -Command "..."` 로 감싼다.)
2. **그 install.ps1 을 실행한다** — python 체크 + **pywin32 자동 설치** + 스크립팅 안내까지 자동으로 함:
   ```
   powershell.exe -ExecutionPolicy Bypass -File "<찾은 install.ps1 경로>"
   ```
   - pywin32 가 없으면 이 스크립트가 `pip install pywin32` 를 **직접 실행**한다.
   - 단 **SAP GUI 스크립팅 'Enable' 체크(레지스트리/보안 토글)는 자동 변경하지 않는다** — 사용자에게 SAP Logon → 옵션 → Scripting → Enable 체크를 요청하라 (출력 메시지에 안내됨).
3. 실행: **평소처럼 SAP GUI 실행 + 로그인** (특별 런처 불필요 — COM 자동 attach)
4. 확인: `python "<runtime>\sapctl" health` → `conns` 나오면 준비 완료

> Windows 는 `sap-daemon.js`·`.app`·토큰을 쓰지 않는다. `exec`(JS)도 macOS 전용이라 Windows 에선 `transact` step 으로 조작한다 (playbook 참조).

---

설치 후 양 OS 공통 확인: 사용자에게 **"지금 떠있는 sap 창 보여줘"** → `sapctl targets` 결과(창 목록)가 나오면 성공.
