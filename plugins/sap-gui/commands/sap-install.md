---
description: 이 PC 에 SAP GUI daemon 런타임을 설치한다 (토큰·캐시·런처 셋업)
---

# SAP daemon 설치

이 plugin 에 번들된 런타임을 이 PC 에 설치한다. 설치 스크립트는 plugin 의 `runtime/install.sh` 다.

## 0. 사전 점검 (설치 전 필수)

설치 전에 아래를 순서대로 확인하고, 하나라도 실패하면 멈추고 사용자에게 알려라:

1. `uname -s` → `Darwin` (macOS 전용)
2. `ls -d /Applications/SAP\ Clients/*/*.app/Contents/MacOS/SAPGUI 2>/dev/null` → 경로 출력되면 SAP GUI for Java 설치됨. 없으면 설치 안내 후 중단.
3. `python3 --version` → Python 3.x (sapctl 실행용)
4. SAP GUI Scripting 클라이언트 설정 — 사용자에게 "Preferences → Web AS ABAP → 스크립팅 → 설정 체크" 육안 확인 요청
5. (설치 후) 서버측 `sapgui/user_scripting=TRUE` — 로그인 후 `sapctl status` 의 conns 는 나오는데 exec 가 scripting-disabled 오류면 Basis 팀에 요청
6. (첫 실행 시) macOS 자동화 권한 dialog → "허용" 안내

install.sh 자체도 macOS/python3 를 자동 체크하고 미충족 시 중단한다.

## 절차

1. plugin 의 runtime 디렉토리를 찾아라. plugin 이 marketplace 로 설치됐으면 보통:
   - `~/.claude/plugins/<marketplace>/plugins/sap-gui/runtime/`
   - 또는 `--plugin-dir` 로 로컬 로드했으면 그 경로의 `plugins/sap-gui/runtime/`
   - `find ~/.claude/plugins -name install.sh -path '*sap-gui*' 2>/dev/null` 로 찾을 수 있다.

2. 찾은 `install.sh` 를 실행한다:
   ```bash
   bash <runtime>/install.sh
   ```

3. install.sh 가 하는 일 (모두 reversible):
   - 인증 토큰 생성 (`~/.sap-daemon/token`)
   - 스크린샷 캐시 디렉토리 생성 (`~/Library/Caches/sap-daemon`)
   - 런처 생성 (`~/Applications/SAP-with-daemon.command`)
   - `sapctl` 을 `~/bin` 에 링크 (있으면)

4. 설치 후 안내:
   - `sapctl` 이 PATH 에 없으면 `~/bin` 을 PATH 에 추가하거나, alias 안내.
   - SAP 실행: `sapctl start` (또는 런처 더블클릭) → Logon Pad 로그인.
   - 확인: `sapctl status` → `conns: 1` 이면 준비 완료.

5. 서버 측 요구사항 안내: SAP GUI Scripting 활성화 (`sapgui/user_scripting = TRUE`). 안 되어 있으면 Basis 팀 협조 필요.

해제는 `runtime/uninstall.sh` (옵션 `--purge` 로 토큰·캐시까지 제거).
