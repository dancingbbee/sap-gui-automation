# sap-daemon

SAP GUI for Java (macOS) 를 **백그라운드로 자동 제어**하는 경량 daemon. SAP GUI 안의 Nashorn 스크립트 엔진에 HTTP 서버를 띄워, 외부 프로세스(CLI·스크립트·AI 에이전트)가 트랜잭션 조작·화면 판독·스크린샷을 수행한다.

AppleScript 로 창을 앞에 띄워 클릭하는 방식과 달리, **창이 가려져 있거나 다른 모니터에 있어도** 동작하고, 사내 배포가 가능하다.

## 무엇이 가능한가

- "MM03 에서 자재 XXX 기본데이터1 화면 열어줘" → 백그라운드 navigate
- "현재 화면 스크린샷 찍어서 정리해줘" → occlusion 무관 PNG 캡처
- "MCP 로 안 되는 Basis T-code 화면 읽고 고쳐줘" → live session read/write

## 동작 원리

```
SAP GUI for Java (JVM, 사용자가 로그인한 상태)
└── sap-daemon.js  (백그라운드 thread)
    └── HTTP  127.0.0.1:18765   ← 토큰 인증, 루프백 전용
         ├── GET  /health
         ├── POST /targets      열린 connection × session 열거 (멀티타겟)
         ├── POST /exec        임의 JS 평가 (범용)
         ├── POST /snapshot     UI 트리 덤프
         ├── POST /screenshot   Frame.paintAll() PNG
         └── POST /transact     선언적 다단계 시나리오
              ↑
        sapctl (Python CLI) / curl / AI 에이전트
```

핵심: SAP GUI Scripting API 는 SAP **공식 인터페이스**다. daemon 은 그 API 를 스크립트 엔진 안에서 호출할 뿐이며, OS 레벨 창 조작(focus/click)에 의존하지 않는다.

## 설치 (5분)

```bash
cd sap-daemon
./install.sh
```

install.sh 가 하는 일:
1. 인증 토큰 생성 (`~/.sap-daemon/token`)
2. 스크린샷 캐시 디렉토리 생성 (`~/Library/Caches/sap-daemon`, macOS 가 자동 정리)
3. 런처 앱 번들 생성 (`~/Applications/SAP (daemon).app`) — Finder/Dock 에서 평소 SAP 아이콘처럼 사용, 터미널/dialog 없음
4. `sapctl` 을 `~/bin` 에 링크 (있으면)

팀 공유 SAP 설정이나 다른 사용자 설정은 건드리지 않는다.

## 생애주기

daemon 은 SAP GUI JVM **안에** 살아서 독립 수명이 없다 — SAP 켜면 같이 뜨고, SAP 끄면(Cmd+Q) 같이 죽는다. 그래서 별도 stop/restart 가 없다.

```bash
sapctl start          # SAP (daemon).app 실행 (이미 떠있으면 no-op)
sapctl status         # 떠있나 + 로그인됐나 + 창 수
sapctl kill-orphans   # 창 없이 남은 잔존 SAP JVM 종료 (daemon·세션은 보존; --dry-run 미리보기)
# 종료: SAP 를 그냥 Cmd+Q (daemon 자동 종료)
```

## 사용

```bash
# 1. SAP+daemon 실행 — Finder/Spotlight 에서 "SAP (daemon)" 더블클릭
#    (Dock 에 고정해두면 평소 SAP 아이콘처럼. 터미널/dialog 안 뜸)
#    또는 shell: sapctl start

# 2. Logon Pad 에서 시스템 더블클릭 로그인 (평소처럼, 1회)

# 3. 확인
sapctl status
#    → {"ok": true, "conns": 1, "version": "8100.0", "running": true}

# 4. 조작
sapctl targets                                   # 떠있는 창 목록
sapctl exec 'application.findById("/app/con[0]/ses[0]").info.getUser()'
sapctl screenshot --match "Easy Access" -o /tmp/sap.png
echo '{"steps":[{"tcode":"MM03"}]}' | sapctl transact -

# 여러 창이 떠 있으면: 먼저 열거 → 타겟 지정
sapctl transact steps.json --con 0 --ses 1     # index 로
sapctl screenshot --system QAS -o /tmp/qas.png  # 이름으로
```

자연어 명령 → step 매핑은 [`claude-playbook.md`](./claude-playbook.md) 참조.

## 파일 구성

| 파일 | 역할 |
|---|---|
| `sap-daemon.js` | daemon 본체 (Nashorn JS). SAP GUI 가 `-f` 로 실행 |
| `sapctl` | Python CLI 클라이언트 |
| `claude-playbook.md` | 자연어 → SAP JS 매핑 cheatsheet (AI 에이전트용) |
| `install.sh` / `uninstall.sh` | 셋업 / 해제 |
| `README.md` | 이 문서 |

## 보안 / 안전

- **루프백 전용** (`127.0.0.1`). 외부 네트워크 노출 없음.
- **토큰 인증**: `/health` 외 모든 요청은 `~/.sap-daemon/token` 의 값을 `X-Token` 헤더로 보내야 함. `sapctl` 이 자동 처리.
- **쓰기 작업 주의**: 조회 트랜잭션은 안전하나, 생성·변경·저장(Ctrl+S)은 실제 데이터를 바꾼다. AI 에이전트는 playbook 규칙에 따라 저장 전 사용자 확인을 받는다.
- 토큰 파일(`~/.sap-daemon/token`)을 코드·로그·외부 채널에 노출하지 말 것.

## 요구 사항

- SAP GUI for Java 8.x (macOS, `com.sap.platin`)
- 클라이언트: Preferences → Web AS ABAP → 스크립팅 → "설정" 체크
- 서버: 프로파일 파라미터 `sapgui/user_scripting = TRUE` (Basis 팀 확인)

## 해제

```bash
./uninstall.sh           # 런처 + 심링크 제거, 토큰/캐시 유지
./uninstall.sh --purge   # 토큰 + 캐시까지 제거
```

## 알려진 제약

- SAP GUI **JVM 이 실행 중 + 로그인된 상태**여야 한다. 완전 무인(cron 새벽 실행 등)은 불가 — 사람이 한 번 로그인해야 함.
- 자동 로그인(`conn=` 인자)은 connection 초기화 중 hang 위험이 있어 미사용. Logon Pad 수동 로그인이 안전한 경로.
- Z-custom 컨테이너의 깊은 트리 walk 는 server roundtrip 으로 느릴 수 있음 — 값 판독은 screenshot 이 빠른 경우가 많다 (playbook 참조).
