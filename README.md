# sap-daemon-tools — Claude Code plugin marketplace

SAP GUI 자동화 Claude Code 플러그인 (**macOS + Windows**).

## 포함 플러그인

### sap-gui
SAP GUI 를 자연어로 백그라운드 제어. "sap 창 보여줘", "MM03에서 자재 XXX 열어줘", "이 화면 캡처해서 정리해줘" 같은 명령으로 트랜잭션 조작·화면 판독·스크린샷. 여러 창 멀티타겟 지원.
- **macOS**: SAP GUI for Java + `sap-daemon.js` (HTTP daemon). 캡처는 off-screen 확대.
- **Windows**: SAP GUI for Windows + `win32com` COM 직접 attach (daemon·토큰·런처 불필요). 캡처는 `hardCopy`.
- `sapctl` 이 OS 를 자동 감지 — 같은 명령(`transact` step JSON)이 양 OS 에서 동작. `exec`(JS)만 macOS 전용.

## ⚠️ ① 설치 전 필수 확인

상세·체크 명령은 [SETUP.md](./SETUP.md). OS별:

**macOS**
- **SAP GUI for Java** 설치됨 + Preferences → Web AS ABAP → **스크립팅 → "설정" 체크**
- 서버측 `sapgui/user_scripting = TRUE` (안 되면 **Basis 팀**)
- `python3 --version`

**Windows**
- **SAP GUI for Windows** 설치됨 + Options → Accessibility & Scripting → **Scripting → Enable** 체크
- 서버측 `sapgui/user_scripting = TRUE` (동일)
- Python 3 + `pip install pywin32`

## 📦 ② 최초 설치

### macOS (Claude Code 사용자)
```
/plugin marketplace add dancingbbee/sap-gui-automation
/plugin install sap-gui@sap-daemon-tools
```
그 다음 Claude 에게 `sap daemon 설치해줘` (= `/sap-gui:sap-install` — `~/Applications/SAP (daemon).app` 런처 + 토큰 생성).

**실행 & 로그인**
1. Finder/Spotlight 에서 **`SAP (daemon)`** 더블클릭 (평소 SAP 아이콘 대신 — Dock 고정 추천)
2. 처음 실행 시 *"이 앱이 SAP GUI 를 제어하려 합니다"* 권한 창 → **"허용"** (1회)
3. Logon Pad 로그인 → Claude 에게 **"지금 떠있는 sap 창 보여줘"**

### Windows
```
/plugin marketplace add dancingbbee/sap-gui-automation
/plugin install sap-gui@sap-daemon-tools
```
그 다음 (PowerShell) 점검 스크립트:
```powershell
pip install pywin32
powershell -ExecutionPolicy Bypass -File <plugin>\runtime\install.ps1
```
**실행 & 로그인**
1. **평소처럼 SAP GUI 실행 + 로그인** (특별 런처/daemon/토큰 불필요 — COM 자동 attach)
2. 확인: `python <plugin>\runtime\sapctl health` → conns 나오면 성공. 또는 Claude 에게 "지금 떠있는 sap 창 보여줘"

> **다른 LLM(Codex 등) / 수동 설치**:
> ```
> git clone https://github.com/dancingbbee/sap-gui-automation.git
> # macOS:  bash sap-gui-automation/plugins/sap-gui/runtime/install.sh
> # Windows: pip install pywin32; .\sap-gui-automation\plugins\sap-gui\runtime\install.ps1
> ```
> LLM 에게 `SETUP.md` + `plugins/sap-gui/skills/sap-gui-control/playbook.md` 를 컨텍스트로 주면 자연어 조작을 이해한다.

## 🔄 ③ 업데이트 (자동 아님 — 수동)

```
/plugin marketplace update sap-daemon-tools   # 최신 코드·버전 가져오기
/plugin update sap-gui                          # 플러그인 적용
```
- `daemon` 코드(캡처·자가진단 등)가 바뀐 릴리스는 적용하려면 **SAP 한 번 재시작** (`SAP (daemon)` 다시 실행). `sapctl` CLI 변경은 재시작 없이 바로 적용.
- 버전이 올라간 릴리스만 업데이트로 인지된다 (현재: **2.0.0** — 멀티OS).

## 🩺 문제 해결

- 막히거나 안 되면 Claude 에게 **"sap 안 돼"** → 자동 진단
- 창 없이 떠서 종료 안 되는 잔존 프로세스: `sapctl kill-orphans`
- 그 외 증상별 해법: `plugins/sap-gui/skills/sap-gui-control/playbook.md` §6 / [SETUP.md](./SETUP.md) §2

## 로컬 개발/테스트

```bash
claude --plugin-dir ~/projects/sap/sap_daemon_for_mac/plugins/sap-gui
# 세션에서:  /sap-gui:sap-windows  또는  "sap 창 보여줘"
claude plugin validate ~/projects/sap/sap_daemon_for_mac/plugins/sap-gui
```

## 구조

```
sap-gui-automation/                   # marketplace repo root
├── .claude-plugin/
│   └── marketplace.json
└── plugins/
    └── sap-gui/
        ├── .claude-plugin/plugin.json
        ├── skills/sap-gui-control/   # 자연어 trigger skill + playbook
        ├── commands/                 # /sap-windows, /sap-install
        └── runtime/                  # sap-daemon.js, sapctl, install.sh, uninstall.sh
```

상세는 `plugins/sap-gui/runtime/README.md` (런타임 문서) 참조.
