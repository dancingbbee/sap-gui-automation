---
name: sap-gui-control
description: >
  Use when the user wants to view, navigate, read, or screenshot a running SAP
  GUI for Java (macOS) screen via natural language — e.g. "sap 창 보여줘",
  "지금 떠있는 sap 창 리스트", "MM03에서 자재 XXX 열어줘", "이 화면 캡처해서
  vault에 정리해줘", "CO01 생산오더 만드는 법 단계별로 찍어줘", "MCP로 안 되는
  basis 티코드 화면 읽고 수정해줘". Drives SAP through the local sap-daemon
  (HTTP 127.0.0.1:18765) using the `sapctl` CLI. Works in the background — the
  SAP window does not need to be focused or visible.
---

# SAP GUI 제어 (sap-daemon)

사용자가 SAP GUI for Java 화면을 자연어로 조회·조작·판독·캡처하려 할 때 사용한다. 실제 제어는 로컬 `sap-daemon` (SAP GUI 안에서 도는 HTTP 서버, `127.0.0.1:18765`) 을 `sapctl` CLI 로 호출해서 한다. **SAP 창이 앞에 있거나 보일 필요 없다** (백그라운드 동작, 가려져도 OK).

## 0. 전제 확인 (항상 먼저)

```bash
sapctl health
```
- `sapctl: command not found` → 런타임 미설치. `/sap-install` 안내 또는 README 참조.
- `connect failed` → SAP GUI 가 안 떠있거나 daemon 미실행. 사용자에게 `~/Applications/SAP-with-daemon.command` 로 SAP 실행 + 로그인 요청.
- `conns: 0` → 로그인 안 됨. Logon Pad 에서 시스템 더블클릭 로그인 요청.
- `conns: 1` 이상 → 준비 완료.

> `sapctl` 이 PATH 에 없으면 `~/bin/sapctl` 또는 plugin runtime 의 `sapctl` 절대경로를 쓴다.

## 1. "sap 창 보여줘" / 창 리스트

```bash
sapctl targets
```
결과(JSON)를 **raw 로 보여주지 말고 표로 정리**한다. 열 순서:

| # | 타겟 | 시스템 | 클라이언트 | 로그인ID | T-code | 화면 |
|---|------|--------|-----------|---------|--------|------|

(`타겟` = `conX/sesY`, `로그인ID` = user 필드.) 그 후 사용자가 어느 창을 제어할지 고르게 한다.

## 2. 타겟 지정

여러 창이 있으면 모든 명령에 타겟을 붙인다. **index 또는 이름** 둘 다 가능:

```bash
sapctl exec --con 0 --ses 1 'sess.info.getTransaction()'
sapctl transact steps.json --match "BOM"        # 창 제목 substring
sapctl screenshot --system QAS -o /tmp/qas.png   # 시스템명
```
- 타겟 생략 시 `con0/ses0`.
- `exec` 스크립트엔 `T`(타겟 경로 prefix), `sess`(세션 객체) 가 주입됨.

## 3. 조작 패턴

상세 매핑은 같은 디렉토리의 [`playbook.md`](./playbook.md) 참조. 요약:

- **T-code 열기**: `echo '{"steps":[{"tcode":"MM03"}]}' | sapctl transact -`
- **자재/문서 조회 + 캡처**: transact 로 navigate → 필드 set → vkey → screenshot (playbook §3 예시)
- **값 읽기**: 필드 ID 알면 `{"read":"wnd[0]/usr/ctxtX"}`. 모르면 **screenshot 후 이미지 판독이 더 빠름** (Z-custom 트리 walk 는 느리거나 hang).
- **화면 캡처**: `sapctl screenshot --match "<창제목 일부>" -o <path>` — occlusion 무관. PNG 를 Read 로 보고 요약.

## 4. 안전 규칙 (중요)

- **조회(표시) 트랜잭션은 안전**. 생성·변경·저장은 실제 데이터를 바꾼다.
- **저장(Ctrl+S = vkey 11, 저장 버튼)은 사용자 명시 확인 없이는 절대 누르지 않는다.**
- 생성/변경 트랜잭션(MM01, CO01, ME21N, VA01…)은 실행 전 사용자에게 의도 확인.
- 토큰(`~/.sap-daemon/token`)을 응답·로그에 출력하지 않는다. `sapctl` 이 자동 처리하므로 직접 다룰 일 없음.

## 5. 작업 결과를 vault 에 정리할 때

"단계별 스크린샷 찍어서 vault {path}에 정리" 류 요청:
1. 각 단계마다 `sapctl screenshot -o <path>/step-N.png`
2. 각 PNG 를 Read 로 확인
3. markdown 으로 단계 설명 + 이미지 링크 작성해 지정 경로에 저장
