# sap-daemon-tools — Claude Code plugin marketplace

SAP GUI for Java (macOS) 자동화 Claude Code 플러그인.

## 포함 플러그인

### sap-gui
SAP GUI for Java (macOS) 를 자연어로 백그라운드 제어. "sap 창 보여줘", "MM03에서 자재 XXX 열어줘", "이 화면 캡처해서 정리해줘" 같은 명령으로 트랜잭션 조작·화면 판독·스크린샷. 여러 창 멀티타겟 지원.

## ⚠️ 설치 전 필수 확인

**[SETUP.md](./SETUP.md) 의 "0. 사전 점검" 을 먼저 확인하라** (AI 에이전트가 읽고 체크할 수 있는 형태). 요약:
- macOS + SAP GUI for Java 설치됨 + Python 3
- SAP GUI Scripting 활성화 (클라이언트 설정 + 서버 `sapgui/user_scripting=TRUE`)
- 첫 실행 시 macOS 자동화 권한 "허용"

## 설치 (동료용)

**Claude Code 사용자** — plugin 으로:
```
/plugin marketplace add dancingbbee/sap-daemon-for-mac
/plugin install sap-gui@sap-daemon-tools
```
그 다음 Claude 에게 "sap daemon 설치해줘" (= `/sap-gui:sap-install`).

**그 외 LLM(Codex 등) / 수동** — clone 후 설치:
```
git clone https://github.com/dancingbbee/sap-daemon-for-mac.git
bash sap-daemon-for-mac/plugins/sap-gui/runtime/install.sh
```
LLM 에게는 `SETUP.md` 와 `plugins/sap-gui/skills/sap-gui-control/playbook.md` 를 컨텍스트로 주면 자연어 조작을 이해한다.

### 설치 후
1. Finder/Spotlight 에서 **`SAP (daemon)`** 실행 (Dock 고정 추천 — 평소 SAP 아이콘처럼)
2. Logon Pad 에서 시스템 로그인 (+ 자동화 권한 허용)
3. `sapctl status` → `conns:1` 확인, 또는 Claude 에게 "지금 떠있는 sap 창 보여줘"

## 로컬 개발/테스트

```bash
claude --plugin-dir ~/projects/sap/sap_daemon_for_mac/plugins/sap-gui
# 세션에서:  /sap-gui:sap-windows  또는  "sap 창 보여줘"
claude plugin validate ~/projects/sap/sap_daemon_for_mac/plugins/sap-gui
```

## 구조

```
sap-daemon-for-mac/                   # marketplace repo root
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
