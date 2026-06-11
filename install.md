# 설치 · 업데이트 안내 — SAP GUI 자동제어 플러그인

Claude Code에서 자연어로 SAP GUI 화면을 **백그라운드로 조회·판독·스크린샷**하는 플러그인입니다. 창을 앞으로 띄우지 않아 다른 작업을 방해하지 않습니다. macOS(SAP GUI for Java) / Windows(SAP GUI for Windows COM) 공통.

> **현재 버전 2.1.2** · 마켓 `sap-gui-tools` · 리포 `dancingbbee/sap-gui-automation`

---

## 1. 최초 설치 (신규)

1. `/plugin marketplace add dancingbbee/sap-gui-automation`
2. `/plugin install sap-gui@sap-gui-tools`
3. **Claude Code 재시작**
4. 런타임 설치 — Claude Code에서 **"SAP 자동화 런타임 설치해줘"** (또는 `/sap-install`)
   - OS 자동 분기: **Windows** = pywin32/Pillow 자동 설치 · **macOS** = daemon 앱 + 토큰 + `sapctl` 설치
5. 확인 — **"지금 떠있는 sap 창 보여줘"** → 창 목록이 표로 나오면 완료

---

## 2. 업데이트 (기존 사용자)

1. `/plugin update sap-gui@sap-gui-tools`
2. **Claude Code 재시작**
3. 새 코드 반영을 위해 SAP GUI 재실행 — **Windows**=평소대로 SAP 실행 / **macOS**=`SAP (daemon)` 앱 재실행

---

## 3. ⚠️ 구 마켓명(`sap-daemon-tools`)으로 받으신 분 — 재등록 1회 필요

초기 버전은 마켓명이 `sap-daemon-tools`, 리포가 다른 이름이었습니다. 지금은 **마켓 `sap-gui-tools` / 리포 `sap-gui-automation`** 으로 바뀌어, **구 이름으로는 `/plugin update`가 새 버전을 못 잡습니다.** 한 번만 재등록해 주세요:

1. `/plugin` 메뉴 → 기존 **`sap-gui` 플러그인 제거** + 구 마켓 **`sap-daemon-tools` 제거**
   - (CLI) `/plugin uninstall sap-gui@sap-daemon-tools` → `/plugin marketplace remove sap-daemon-tools`
2. 새로 추가·설치:
   - `/plugin marketplace add dancingbbee/sap-gui-automation`
   - `/plugin install sap-gui@sap-gui-tools`
3. **Claude Code 재시작**

> 한 번 재등록하면 이후로는 `2. 업데이트`만 하면 됩니다. 런타임 토큰·캐시는 그대로라 **SAP 재로그인은 불필요**합니다. 항목명이 헷갈리면 `/plugin` 메뉴에서 목록을 보고 구 `sap-daemon-tools` 관련을 지운 뒤 2번을 하세요.

---

## 4. 전제 조건

- **SAP GUI 스크립팅 활성화**
  - Windows: SAP Logon → 옵션 → Accessibility & Scripting → Scripting → "Enable scripting"
  - macOS: SAP GUI Preferences → Web AS ABAP → 스크립팅 → "설정"
- 서버측 `sapgui/user_scripting = TRUE` (안 되어 있으면 Basis 팀)
- 가능하면 **표시(display) 권한 계정**으로 로그인 — 저장·변경 방지는 SAP 권한이 담당합니다(도구는 별도 쓰기 차단을 하지 않음).

---

## 5. 이번 버전(2.1.2) 주요 개선

- 캡처가 **SAP 창을 앞으로 안 띄움** — 가려져 있거나 최소화돼 있어도 백그라운드 캡처 (Windows·macOS 공통)
- **모달 팝업 자동 캡처**, 작은 메인 창만 확대(모달은 native 크기로 선명)
- 한글 출력·에러 메시지 정리, 첫 T-code 안정화, `--match`/`--system` 타겟팅, 멀티 connection 제어
- 리포트는 **회사코드/플랜트로 조회조건 좁혀** 실행 권장(무필터는 느림), 큰 결과 ALV는 캡처로 판독

---

## 6. 사용 예 · 문제 신고

- 예: "MM03에서 자재 XXX 열어줘" · "이 화면 캡처해서 정리해줘" · "지금 떠있는 sap 창 보여줘"
- 이슈: <https://github.com/dancingbbee/sap-gui-automation/issues>
- 설치 전 상세 점검(에이전트용): `SETUP.md` 참조
