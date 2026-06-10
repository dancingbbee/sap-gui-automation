---
description: 지금 떠있는 SAP GUI 창(connection × session) 목록을 표로 보여준다
---

# SAP 창 목록

`sapctl targets` 를 실행해서 현재 떠있는 SAP GUI 창들을 조회하고, 결과 JSON 을 **표로 정리**해서 보여줘라.

```bash
sapctl targets
```

표 열 순서:

| # | 타겟 | 시스템 | 클라이언트 | 로그인ID | T-code | 화면 |
|---|------|--------|-----------|---------|--------|------|

- `타겟` = `conX/sesY`
- `로그인ID` = 응답의 `user` 필드
- `화면` = `windows` 의 (마지막) 창 제목

오류 처리:
- `command not found` → 런타임 미설치. `/sap-install` 안내.
- `connect failed` / `running: false` → SAP GUI 미실행. `sapctl start` 또는 런처 안내.
- `conns: 0` → 로그인 필요. Logon Pad 더블클릭 안내.

표시 후, 사용자가 어느 창을 제어할지 물어보거나 다음 지시를 기다려라.
