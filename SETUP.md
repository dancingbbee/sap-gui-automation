# SETUP — 설치 전 확인 & 설치 가이드

> **AI 에이전트(Claude/Codex 등)에게**: 이 PC 에 sap-daemon 을 설치하기 전에 아래 **0. 사전 점검**을 순서대로 실행해 모두 통과하는지 확인하라. 하나라도 실패하면 설치를 멈추고 사용자에게 알려라. 통과하면 **1. 설치** 로 진행하라.

---

## 0. 사전 점검 (설치 전 필수)

### 0-1. OS 판별 → 분기
```bash
uname -s   # "Darwin" → 아래 macOS(0-2~0-6). Windows(MINGW/CYGWIN/MSYS 또는 PowerShell) → "0W. Windows" 섹션으로.
```
- macOS: 0-2 ~ 0-6 진행.
- Windows: 이 도구는 COM(win32com)으로 동작 — 0-2~0-6(Java/자동화권한 등) 대신 맨 아래 **"0W. Windows 사전 점검"** 을 따른다.

### 0-2. SAP GUI for Java 설치 확인
```bash
ls -d /Applications/SAP\ Clients/*/*.app/Contents/MacOS/SAPGUI 2>/dev/null
```
- 경로가 하나 이상 출력되면 OK.
- 없으면 **중단** → 사용자에게 "SAP GUI for Java 를 먼저 설치하세요" 안내. (이 도구는 Windows COM 판이 아니라 macOS Java 판 전용.)

### 0-3. Python 3 확인 (sapctl CLI 실행에 필요)
```bash
python3 --version   # → Python 3.x. macOS 기본 포함. 없으면 Xcode CLT 또는 brew 안내.
```

### 0-4. SAP GUI Scripting — 클라이언트 설정 활성화
SAP GUI for Java 를 열고 **Preferences (⌘,) → Web AS ABAP → 스크립팅 → "설정" 체크**.
확인(설정 파일에 흔적이 있는 경우):
```bash
grep -i scripting ~/Library/Preferences/SAP/settings 2>/dev/null
```
- 이 항목은 GUI 토글이라 파일로 100% 확인되지 않을 수 있음. **사용자에게 "Preferences → 스크립팅 → 설정 이 체크돼 있는지" 육안 확인을 요청**하라.

### 0-5. SAP 서버측 Scripting 허용 (Basis 영역)
서버 프로파일 파라미터 `sapgui/user_scripting = TRUE` 가 켜져 있어야 한다.
- **설치 시점엔 확인 불가** (로그인 후에만 검증됨). 설치 후 `sapctl status` 로 `conns:1` 이 나오는데 `exec` 가 scripting-disabled 오류를 내면 이 설정이 꺼진 것 → **Basis 팀에 요청**.

### 0-6. (설치 후 첫 실행 시) macOS 자동화 권한
처음 `SAP (daemon).app` 을 실행하면 macOS 가 **"이 앱이 'SAP GUI' 를 제어하려 합니다 — 허용?"** 를 한 번 물어본다. **반드시 "허용"** 해야 한다.
- 이 권한은 SAP 가 `-f` 스크립트 완료 시 띄우는 "스크립트 실행 완료" 알림창을 자동으로 닫는 데만 쓰인다 (네트워크/비밀번호와 무관, 로컬 전용).
- 시스템 설정 → 개인정보 보호 및 보안 → 자동화 에서 나중에 확인/변경 가능.

---

## 0W. Windows 사전 점검 (Windows 인 경우)

> Windows 는 COM(win32com)으로 SAP 에 직접 attach 한다. **daemon·토큰·런처·자동화권한이 모두 불필요**하다. `runtime/install.ps1` 이 1~2 를 점검해준다.

### 0W-1. Python 3
```powershell
python --version   # Python 3.x. 없으면 https://python.org 에서 설치.
```

### 0W-2. pywin32 (win32com 제공)
```powershell
python -c "import win32com.client"   # 오류 없으면 OK
# 없으면:
pip install pywin32
```

### 0W-3. SAP GUI for Windows 설치 + Scripting 활성화
- **SAP GUI for Windows** 설치돼 있어야 한다 (Java 판 아님).
- SAP Logon → Options → **Accessibility & Scripting → Scripting → "Enable scripting"** 체크. ("Notify when a script attaches/opens connection" 두 개는 해제 권장.)
- 레지스트리 자동 변경은 하지 않는다 (보안 토글이라 사용자가 직접).

### 0W-4. 서버측 Scripting 허용 (Basis 영역)
`sapgui/user_scripting = TRUE` — macOS 와 동일. 로그인 후 `sapctl health` 의 conns 는 나오는데 조작이 막히면 이 설정 → **Basis 팀에 요청**.

### 0W-5. 실행
- **평소처럼 SAP GUI 실행 + 로그인** (특별 런처 불필요 — COM 이 자동 등록).
- `python <plugin>\runtime\sapctl health` → conns 가 나오면 준비 완료.

---

## 1. 설치

```bash
# 1) 런타임 설치 (토큰·캐시·런처앱 생성). 팀 공유 설정은 건드리지 않음.
bash plugins/sap-gui/runtime/install.sh

# 2) SAP 실행 — Finder/Spotlight 에서 "SAP (daemon)" 더블클릭
#    (또는)
sapctl start

# 3) Logon Pad 에서 시스템 로그인 (평소처럼, 1회)
#    → 0-6 자동화 권한 dialog 가 뜨면 "허용"

# 4) 검증
sapctl status        # → {"running": true, "conns": 1, ...}
sapctl targets       # → 떠있는 SAP 창 목록
```

`conns: 1` 까지 나오면 준비 완료. 자연어로 "지금 sap 창 보여줘" 등 사용.

---

## 2. 문제 해결

| 증상 | 원인 / 조치 |
|---|---|
| `sapctl: command not found` | `~/bin` 이 PATH 에 없음. `alias sapctl='<repo>/plugins/sap-gui/runtime/sapctl'` 또는 PATH 추가 |
| `connect failed` | SAP GUI 미실행. `SAP (daemon).app` 으로 실행 (일반 SAP 아이콘은 daemon 안 붙음) |
| `conns: 0` | 로그인 안 됨. Logon Pad 더블클릭 |
| exec 가 scripting-disabled 오류 | 서버 `sapgui/user_scripting=TRUE` 미설정 → Basis (0-5) |
| "스크립트 실행 완료" 창이 안 닫히고 로그인 폼 막힘 | 자동화 권한 거부됨 → 시스템 설정 → 자동화 에서 허용 (0-6) |
| 첫 실행 시 "확인되지 않은 개발자" | install.sh 가 ad-hoc 서명함. 그래도 뜨면 우클릭 → 열기 1회 |

---

## 3. 해제
```bash
bash plugins/sap-gui/runtime/uninstall.sh            # 런처·심링크 제거
bash plugins/sap-gui/runtime/uninstall.sh --purge    # 토큰·캐시까지 제거
```
