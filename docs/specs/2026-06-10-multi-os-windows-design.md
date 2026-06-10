# 멀티OS 지원 (Windows) 설계 — sap-gui v2.0.0

작성: 2026-06-10 · 상태: 승인됨 (구현 전)

## 1. 목표 / 배경

현재 `sap-gui` 플러그인은 **macOS + SAP GUI for Java** 전용이다 (Nashorn daemon + HTTP + osacompile 런처). 윈도우(SAP GUI for Windows)도 지원하도록 확장한다.

핵심 통찰: 윈도우는 **COM Scripting** 으로 외부 프로세스가 SAP 에 직접 attach 한다 (`GetObject("SAPGUI")`). macOS 에서 우리가 손으로 만든 통신 계층(HTTP daemon)을 윈도우는 OS(COM/ROT)가 기본 제공하므로, 윈도우 구현이 더 단순하다 (daemon·토큰·특별 런처 불필요, 스크린샷은 `hardCopy` 내장).

가치의 대부분(skill·playbook·pi-kb 연동·tcode 캐시)은 `findById` 경로·step 이 **OS 무관**이라 공유된다. 따라서 단일 repo·단일 플러그인을 유지하고, OS 차이는 sapctl 백엔드와 설치 스크립트로 흡수한다.

## 2. 비목표 (YAGNI)

- 윈도우 off-screen 확대 캡처 (1차 제외 — `hardCopy` 기본 캡처로 시작, 베타에서 필요성 확인 후 추가)
- 별도 repo / 별도 플러그인 분리 (공유 자산 중복 비용이 커서 기각)
- 윈도우 daemon (COM 이 대체 — 불필요)

## 3. 아키텍처

```
sapctl (Python, cross-platform)
└─ platform.system() 으로 백엔드 선택
   ├─ Darwin  → backends/http_mac.py   (기존 daemon :18765 HTTP)
   └─ Windows → backends/com_win.py    (win32com, GetObject("SAPGUI"))
```

- `sapctl` 본체는 얇게: 인자 파싱 + 출력(JSON) + 백엔드 선택만.
- 백엔드는 `backends/` 로 **파일 분리**. `win32com` 은 com_win.py 안에서 **지연 import** → macOS 에선 로드 안 됨 (의존성 오염 0).
- 공통 Backend 인터페이스(메서드): `health / targets / exec_ / snapshot / screenshot / transact` (+ 라이프사이클 `status / start / kill_orphans`).

## 4. 공통 언어 = transact step JSON (1급 인터페이스)

OS 중립 선언적 step. 양쪽 백엔드가 각자 번역 실행한다.

step 종류:
| step | 의미 | macOS (daemon JS) | Windows (COM) |
|---|---|---|---|
| `tcode` | `/n<code>` + Enter | okcd.text + sendVKey(0) | 동일 |
| `set` | 필드 텍스트 | findById(id).text=v | findById(id).text=v |
| `read` | 필드/상태 읽기 | findById(id).text | 동일 |
| `vkey` | 기능키 | wnd[n].sendVKey(k) | 동일 |
| `tab` | 탭 선택 | tab.select() | 동일 |
| `press` | 버튼 | btn.press() | 동일 |
| `select` | 체크박스/라디오 bool | **신규** setSelected/selected | selected=bool |
| `selectRows` | 테이블 행 | rows.elementAt(i).setSelected | 동일 개념 |
| `snapshot` | UI 트리 | 재귀 walk | 재귀 walk (.Children) |
| `screenshot` | PNG | Frame.paintAll(off-screen 확대) | **wnd[0].hardCopy(path)** |
| `sleep` | 대기 | Thread.sleep | time.sleep |

- **`select`/`read` step 은 신규** — macOS daemon.js 의 transact 에도 추가해야 한다 (현재 없어서 exec 로 처리하던 것). 양쪽 백엔드 모두 구현.
- `exec`(임의 JS)는 **macOS 전용 escape hatch.** Windows 백엔드는 JS 엔진이 없으므로 명확한 "미지원: step 을 쓰라" 에러를 반환한다.

## 5. 서브커맨드 OS 매핑

| 커맨드 | macOS | Windows |
|---|---|---|
| exec/snapshot/screenshot/transact/targets | 공통 | 공통 (exec 제외 — exec 는 mac 전용) |
| health | daemon ping | `GetObject("SAPGUI")` attach 가능 여부 + conns |
| status | daemon 살아있나+로그인 | COM attach + conns |
| start | `SAP (daemon).app` 실행 | SAP GUI 실행 안내 (COM 자동, 특별 런처 불필요) |
| kill-orphans | 창없는 daemon JVM kill | 해당없음 → no-op + 안내 |

## 6. 설치

- **macOS**: `install.sh` (런처 .app + 토큰) — 기존 유지.
- **Windows**: `install.ps1` (신규) —
  - `pywin32` 설치 여부 점검 (없으면 `pip install pywin32` 안내/실행)
  - SAP GUI 스크립팅 활성화 **점검 + 안내** (레지스트리 자동 변경은 위험하므로 안 함)
  - 런처/토큰 불필요 (COM 직접) → 거의 점검·안내 스크립트
- 인증: macOS=토큰(HTTP 보호) 유지 / Windows=COM 은 OS 권한 → **토큰 미사용** (sapctl 이 win 에선 토큰 생략).

## 7. 디렉토리

```
plugins/sap-gui/runtime/
├── sapctl                 # cross-platform CLI (백엔드 선택)
├── backends/
│   ├── __init__.py
│   ├── http_mac.py        # macOS — daemon HTTP (기존 sapctl 로직 이전)
│   └── com_win.py         # Windows — win32com (신규, 지연 import)
├── sap-daemon.js          # macOS 전용 daemon (select/read step 추가)
├── install.sh             # macOS
├── install.ps1            # Windows (신규)
├── uninstall.sh           # macOS
└── uninstall.ps1          # Windows (신규, 가벼움)
```

## 8. 윈도우 COM 구현 주의 (베타 전 코드 품질 — 함정)

mac 개발 환경에서 검증 불가하므로 코드 작성 시 방어:
1. `GetObject("SAPGUI")` 는 SAP GUI 실행 + connection ≥ 1 일 때만 ROT 등록 → 미실행/미로그인 시 명확한 에러 메시지 (mac 의 connect-failed 와 동일 톤).
2. `hardCopy()` 출력 포맷이 버전별로 BMP/PNG 다를 수 있음 → 베타에서 확인, 필요시 변환(PIL 등) 또는 확장자 처리.
3. 한글/유니코드 COM 문자열 인코딩 — `findById` 결과·입력값.
4. `.Children` (COM, property) vs Java wrapper `getChildren()` — 백엔드가 흡수.
5. COM dispatch: `win32com.client.GetObject` + 필요시 `gencache` / late-binding 선택.

## 9. skill / playbook / tcode 캐시

- **공유.** `exec`(JS)로 작성된 부분을 step 으로 정리:
  - `sap-gui-control` playbook: step 우선 안내 (exec 는 mac 전용 고급으로 격하)
  - 로컬 `sap-gui-pi` 캐시(VA05·CS15): step 표현 보강 (체크박스 `select` step 등)
- OS 무관하므로 macOS·Windows 양쪽에서 그대로 동작.

## 10. 버전 / 테스트

- 버전 **2.0.0** (멀티OS + step 인터페이스 격상 = major).
- 테스트:
  - macOS: 회귀 (기존 동작 보존 — 최우선. 백엔드 분리 리팩토링이 기존 HTTP 동작을 깨지 않을 것)
  - Windows: 사용자의 윈도우 PC 에서 베타 검증.

## 11. 구현 순서 (개요 — 상세는 plan 에서)

1. sapctl 백엔드 추상화 + `backends/http_mac.py` 로 기존 로직 이전 (macOS 회귀 검증)
2. daemon.js 에 `select`/`read` step 추가 (macOS)
3. `backends/com_win.py` 작성 (win32com, 모든 step + targets/health/screenshot)
4. `install.ps1` / `uninstall.ps1`
5. playbook·tcode 캐시 step 정리
6. README / SETUP 윈도우 섹션
7. 버전 2.0.0, 커밋·태그
8. 윈도우 베타 검증 → 함정(§8) 대응
