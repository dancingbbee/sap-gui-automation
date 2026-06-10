# sap-daemon-tools — Claude Code plugin marketplace

SAP GUI for Java (macOS) 자동화 Claude Code 플러그인.

## 포함 플러그인

### sap-gui
SAP GUI for Java (macOS) 를 자연어로 백그라운드 제어. "sap 창 보여줘", "MM03에서 자재 XXX 열어줘", "이 화면 캡처해서 정리해줘" 같은 명령으로 트랜잭션 조작·화면 판독·스크린샷. 여러 창 멀티타겟 지원.

## ⚠️ ① 설치 전 필수 확인

하나라도 안 되면 설치해도 안 돌아간다 (상세·체크 명령은 [SETUP.md](./SETUP.md)):
- **macOS** + **SAP GUI for Java** 설치됨
- SAP GUI Preferences → Web AS ABAP → **스크립팅 → "설정" 체크**
- 서버측 스크립팅 허용 `sapgui/user_scripting = TRUE` — 안 되어 있으면 **Basis 팀에 요청**
- `python3 --version` 으로 Python 3 확인 (보통 기본 포함)

## 📦 ② 최초 설치 (Claude Code 사용자)

```
/plugin marketplace add dancingbbee/sap-daemon-for-mac
/plugin install sap-gui@sap-daemon-tools
```
그 다음 Claude 에게 한 마디:
```
sap daemon 설치해줘
```
(= `/sap-gui:sap-install` — `~/Applications/SAP (daemon).app` 런처 + 토큰 생성)

**실행 & 로그인**
1. Finder/Spotlight 에서 **`SAP (daemon)`** 더블클릭 (평소 SAP 아이콘 대신 이걸로 — Dock 고정 추천)
2. 처음 실행 시 *"이 앱이 SAP GUI 를 제어하려 합니다"* 권한 창 → **"허용"** (1회)
3. Logon Pad 에서 평소처럼 로그인
4. 확인: Claude 에게 **"지금 떠있는 sap 창 보여줘"** → 창 목록 나오면 성공 🎉

> **Claude Code 가 아닌 다른 LLM(Codex 등) / 수동 설치**:
> ```
> git clone https://github.com/dancingbbee/sap-daemon-for-mac.git
> bash sap-daemon-for-mac/plugins/sap-gui/runtime/install.sh
> ```
> LLM 에게 `SETUP.md` + `plugins/sap-gui/skills/sap-gui-control/playbook.md` 를 컨텍스트로 주면 자연어 조작을 이해한다.

## 🔄 ③ 업데이트 (자동 아님 — 수동)

```
/plugin marketplace update sap-daemon-tools   # 최신 코드·버전 가져오기
/plugin update sap-gui                          # 플러그인 적용
```
- `daemon` 코드(캡처·자가진단 등)가 바뀐 릴리스는 적용하려면 **SAP 한 번 재시작** (`SAP (daemon)` 다시 실행). `sapctl` CLI 변경은 재시작 없이 바로 적용.
- 버전이 올라간 릴리스만 업데이트로 인지된다 (현재: **1.1.0**).

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
