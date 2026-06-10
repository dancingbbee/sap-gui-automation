# SAP GUI daemon — Claude playbook

자연어 명령을 SAP GUI 조작으로 옮길 때 참조하는 cheatsheet. `sapctl` (Python CLI) 로 호출한다.

> **멀티OS**: `sapctl` 은 OS 자동 감지 — macOS=`sap-daemon.js` (HTTP `127.0.0.1:18765`), Windows=`win32com` COM 직접. **`transact` step JSON 이 OS 공통 인터페이스이니 step 으로 작성하는 걸 우선**한다. **`exec`(임의 JS)는 macOS 전용** escape hatch (Windows 는 "미지원" 에러 → step 으로 대체). 체크박스/라디오는 `{"select":"<id>","value":true}`, 상태바는 `{"read":"wnd[0]/sbar"}` step 으로 — exec 없이 양 OS 에서 동작.

> **캡처는 창을 앞으로 가져오지 않는다 (양 OS 공통)**: macOS 는 `Window.paintAll()`(모든 top-level Window — `SAPFrame` 메인 + `SAPDialog` 모달 포함), Windows 는 Win32 `PrintWindow`(PW_RENDERFULLCONTENT) 로 렌더 — 둘 다 **occlusion·focus 무관**이라 SAP 창이 가려져 있거나 최소화돼 있어도 캡처되고, 사용자가 보던 다른 작업을 방해하지 않는다. 기본 캡처 대상은 **최상위/활성 창**이라 모달 popup(wnd[1]+)이 떠 있으면 그게 잡힌다; 특정 창은 `--wnd N`(또는 step `{"screenshot":true,"wnd":1}`)으로 지정. **작은 메인 창**은 화면 밖에서 잠깐 확대→캡처→복원(가독성 ↑, 깜빡임 없음, `--no-enlarge` 로 끔). **모달/다이얼로그는 확대하지 않는다** — 고정 레이아웃이라 키워도 내용이 reflow 안 되고 여백만 늘기 때문(native 크기로 캡처해도 선명). 산출물은 항상 PNG.

## 0. 전제 / 안전

- daemon 은 **사용자가 SAP GUI 를 띄우고 Logon Pad 에서 한 번 로그인한 상태**에서만 의미 있다. JVM 이 없거나 미로그인이면 `conns=0`.
- 토큰: 모든 요청(`/health` 제외)은 `~/.sap-daemon/token` 의 값을 `X-Token` 헤더로 보내야 함. `sapctl` 이 자동 처리.
- **쓰기 작업 주의**: `setText` + `sendVKey` 는 실제 SAP 트랜잭션을 친다. 조회(MM03, 표시 모드)는 안전하지만 생성/변경(MM01, CO01, ME21N…)은 사용자 확인 후 실행. 저장(`/11` = Ctrl+S, 저장 버튼)은 명시 지시 없이는 누르지 말 것.
- 값을 "읽기"만 할 때는 트리 walk 보다 **screenshot → 이미지 판독**이 빠르고 안전 (lazy-load roundtrip 회피).

## 1. 핵심 호출 형태

```bash
# 헬스
sapctl health

# 선언적 step (OS 공통 — 우선 사용)
echo '{"steps":[{"tcode":"MM03"},{"set":"wnd[0]/usr/ctxtRMMG1-MATNR","to":"X"},{"vkey":0}]}' | sapctl transact -

# 임의 JS 평가 (macOS 전용 escape hatch — Windows 미지원)
sapctl exec 'application.findById("/app/con[0]/ses[0]").info.getUser()'

# UI 트리 덤프
sapctl snapshot --id '/app/con[0]/ses[0]/wnd[0]/usr' --depth 3

# 스크린샷 (창 제목 substring 으로 타겟; occlusion·front 무관)
sapctl screenshot --match 100-100 -o /tmp/mat.png
# 모달 popup 만 캡처 (기본은 최상위/활성 창 자동 — 모달 뜨면 모달이 잡힘)
sapctl screenshot --wnd 1 -o /tmp/popup.png

# 선언적 다단계 (steps.json 또는 stdin)
echo '{"steps":[{"tcode":"MM03"}]}' | sapctl transact -
```

## 1.5 멀티타겟 (여러 창 제어)

SAP 창이 여러 개 떠 있을 수 있다. 두 축:
- **connection** `con[0]`, `con[1]`... = 시스템별 로그인 (DEV, QAS)
- **session** `ses[0]`, `ses[1]`... = 한 시스템에서 `/o` 로 띄운 추가 창

**워크플로우**: 사용자가 "창 제어해줘" 하면 **먼저 `sapctl targets` 로 열거해서 보여주고**, 사용자가 고르면 그 타겟으로 조작.

```bash
sapctl targets
# → [{con:0, ses:0, system:"DEV", tcode:"MM03", windows:["자재 조회..."]},
#    {con:0, ses:1, system:"DEV", tcode:"CS03", windows:["자재 BOM 조회..."]}]
```

타겟 지정은 **index 또는 이름** 둘 다 가능 (모든 명령에 공통 플래그):

```bash
# index 로
sapctl exec --con 0 --ses 1 'sess.info.getTransaction()'
sapctl transact steps.json --con 0 --ses 1
sapctl screenshot --con 0 --ses 1 -o /tmp/win2.png

# 이름으로 (system 명 또는 창 제목 substring)
sapctl snapshot --system QAS --id 'wnd[0]/usr'
sapctl transact steps.json --match "BOM"      # 창 제목에 BOM 포함된 세션
```

- 타겟 생략 시 `con[0]/ses[0]` default.
- `exec` 스크립트 스코프엔 타겟 헬퍼 주입됨: **`T`** = 타겟 경로 prefix 문자열, **`sess`** = 세션 객체. 예: `sapctl exec --con 0 --ses 1 'sess.findById("wnd[0]/tbar[0]/okcd").setText("/nVA03")'`
- transact step 의 상대 id (`wnd[0]/usr/...`) 는 자동으로 타겟 prefix 가 붙음.

**여러 창 동시 제어**: 각 호출에 다른 타겟을 주면 여러 창을 번갈아 제어 가능 (실측됨). SAP 가 automation 호출을 내부 mutex 로 직렬화하므로 물리적 동시는 아니지만 ms 단위로 번갈아 처리 → 체감상 동시. "DEV 에서 조회하며 QAS 에서 확인" 류 워크플로우 OK.

## 2. ID 경로 규칙

- 루트: `/app/con[0]/ses[0]/wnd[0]` (메인), `wnd[1]`/`wnd[2]` = 모달 popup (위로 쌓임)
- 입력 필드: `wnd[0]/usr/ctxt<NAME>` (CTextField), `wnd[0]/usr/txt<NAME>`, `wnd[0]/tbar[0]/okcd` (명령창)
- `transact` step 의 `set`/`read`/`tab` 등에서는 `/app/con[0]/ses[0]/` 접두사 **생략 가능** (`abs()` 가 자동 보충). `exec` 의 `findById` 에는 풀 경로 써야 함.

## 3. 의도 → step 매핑

### "T-code XXX 열어줘"
```json
{"steps":[{"tcode":"MM03"}]}
```

### "MM03 에서 자재 100-100 기본데이터1 보여줘"
```json
{"steps":[
  {"tcode":"MM03"},
  {"set":"wnd[0]/usr/ctxtRMMG1-MATNR","to":"100-100"},
  {"vkey":0,"wnd":0},
  {"sleep":500},
  {"selectRows":"wnd[1]/usr/tblSAPLMGMMTC_VIEW","rows":[0]},
  {"vkey":0,"wnd":1},
  {"sleep":800},
  {"vkey":0,"wnd":1},
  {"sleep":1000},
  {"screenshot":true,"match":"100-100","path":"/tmp/mat-basic1.png"}
]}
```
- 뷰 선택 popup: 39개 뷰가 기본 전체선택 상태. row 0 = "기본 데이터 1". `selectRows` 가 나머지 해제 + 지정 row 만 선택.
- 그 다음 조직레벨 popup 이 또 뜰 수 있음 → 한번 더 `vkey:0,wnd:1` 로 skip (기본데이터1/2는 client 레벨이라 plant 불필요).

### "기본데이터2 탭으로 전환"
```json
{"steps":[{"tab":"wnd[0]/usr/tabsTABSPR1/tabpSP02"}]}
```
MM 자재 탭 id: SP01=기본1, SP02=기본2, SP04/05=영업, SP12~15=MRP1~4, SP24/25=회계.
(탭 id 는 화면마다 다를 수 있으니 모르면 먼저 `snapshot --id .../tabsTABSPR1 --depth 1`)

### "X 필드 값 읽어줘"
- 필드 ID 를 알면: `{"read":"wnd[0]/usr/ctxtZZEMARA-ZZxxx"}`
- 필드 ID 를 모르면: **screenshot 후 이미지 판독이 가장 빠름**. 트리 walk 는 Z-custom container 에서 server roundtrip 으로 느리거나 hang 날 수 있음.

### "현재 화면 캡처해서 vault 에 정리"
```bash
sapctl screenshot --match "조회" -o ~/vault/.../shot.png
```
+ 캡처 후 Claude 가 이미지를 Read 로 보고 markdown 으로 요약.

### "MCP 안 되는 Basis T-code 화면 읽고 수정"
1. `{"tcode":"<TCODE>"}` 로 진입
2. `snapshot --id .../wnd[0]/usr --depth 4` 또는 screenshot 으로 화면 파악
3. 필드 ID 확인 → `{"set":...,"to":...}` 로 수정
4. **저장은 사용자 확인 후** `{"press":"wnd[0]/tbar[0]/btn[11]"}` 또는 `{"vkey":11,"wnd":0}` (Ctrl+S)

## 3.5 다음 화면으로 못 넘어갈 때 — 자가 진단 (중요)

특정 T-code 에서 "어떻게 다음 화면으로 가는지" 모를 때, **T-code 별 정답을 외우지 말고 아래 절차로 그 자리에서 스스로 알아낸다.** 대부분의 화면이 이 절차로 해결된다.

**1) 현재 화면 전부 열거** — 입력 필드·버튼·탭이 뭐가 있는지:
```bash
sapctl snapshot --id 'wnd[0]/usr' --depth 4
```
- `GuiCTextField`/`GuiTextField` 중 `text` 가 비어있는 것 = **채워야 할 입력 필드** (보통 화면 키값: 자재/오더/회사코드/날짜 등)
- `GuiButton`/`GuiTab` = 누를 수 있는 것

**2) status bar 읽기** — SAP 가 "뭐가 필요한지" 말해준다. **step 으로 (OS 공통, 권장)**:
```bash
echo '{"steps":[{"read":"wnd[0]/sbar"}]}' | sapctl transact -   # → "E:자재 X..." 형태(type:text)
# 타겟: ... | sapctl transact - --con 0 --ses 1
```
(macOS 한정 고급: `sapctl exec 'var sb=sess.findById("wnd[0]/sbar"); sb.getMessageType()+": "+sb.getText()'`)
`E:`(Error)/`W:`(Warning) 메시지면 그 필드/조건이 빠진 것 — 메시지 내용이 곧 힌트. 빈 type 이면 에러 없음(정상 진행).

**3) 실행 키 시도** (대부분 이 순서로 다음 화면 진입):
- 입력 필드 채운 뒤 **Enter** (`{"vkey":0}`) — 조회/단순 진입
- 안 되면 **F8** (`{"vkey":8}`) — 실행(리포트·조회 결과 화면)
- 화면 상단 toolbar 버튼: `snapshot` 에서 본 `wnd[0]/tbar[1]/btn[N]` 을 `{"press":...}`

**4) popup 뜨면** §5 절차로 (확인/취소/버튼 선택).

**5) 그래도 막히면**:
- 화면 캡처해서 사용자에게 보여주고 판단 요청: `sapctl screenshot -o /tmp/stuck.png` → Read 로 확인
- **내부 지식베이스가 있으면** 해당 T-code 사용법 조회 (예: `qmd query "<TCODE> 조회 조건 입력"` 또는 사내 매뉴얼). 조회 결과의 입력값/조건을 step 으로 옮긴다. (이 plugin 은 사내 데이터를 포함하지 않는다 — 각자 환경의 KB 를 조회한다.)

> 원칙: 화면 구조(snapshot) + status bar 메시지 + 표준 실행 키 3가지면 T-code 하드코딩 없이 대부분 진행된다. 막히는 핵심 원인은 거의 "필수 입력 필드 누락" 이고, status bar 가 그걸 알려준다.

## 3.6 검증된 플로우 재사용 (로컬 캐시 — 선택)

한 번 풀어낸 transact step 시퀀스는 **재현 가능**하므로 로컬에 저장해두면 다음엔 자가진단 없이 바로 쓴다.

- 저장 위치는 **반드시 plugin 디렉토리 밖** — 그래야 `/plugin update` 때 안 덮어써진다. 권장:
  - `~/.sap-daemon/flows.md` (토큰과 같은 사용자 디렉토리, 업데이트 무관) — 자유 형식으로 "<T-code> → step JSON" 기록
  - 또는 개인 skill 의 `tcodes/<TCODE>.md` (예: 별도 로컬 skill)
- **막히기 전에 먼저** 이 캐시가 있으면 읽어서 해당 T-code 시퀀스를 찾는다. 있으면 그대로 transact.
- 이 캐시는 **사용자 소유·plugin 밖**이라 회사 특화 값(자재/플랜트 등)을 담아도 public repo 와 무관하다.

> 이 플러그인 자체는 검증 플로우를 번들하지 않는다(각 환경이 다름). 위는 "있으면 참조하라"는 discovery 안내일 뿐이다.

## 3.7 리포트(선택화면 → 결과) 실행 — 조회조건 바운딩 + ALV 판독

리포트형 T-code(보통 Z*리포트, `*03` 조회)는 선택화면에서 조건을 받고 **F8**(`{"vkey":8}`)로 결과를 낸다. 핵심 주의 3가지:

1. **조회조건을 반드시 바운딩한다 — 특히 회사코드/플랜트**. 조건 없이(또는 너무 넓게) F8 하면 전체 스캔이 되어 수 분씩 걸리고 결과 ALV 도 거대해진다. **회사코드(BUKRS)·플랜트(WERKS)는 거의 모든 조직 단위 리포트의 1차 필터**이니 **무조건 채워서 행수를 좁힌다.** 추가로 날짜/문서번호 범위 등으로 더 좁힐 수 있으면 좁힌다.
   - 구체 코드값(회사코드/플랜트 번호 등)은 **환경마다 다르다** — 각자 환경의 로컬 KB/skill 에 default 가 있으면 그걸 쓰고, 없으면 사용자에게 묻는다. (이 public plugin 은 회사 코드값을 담지 않는다.)
2. **무거운 쿼리는 타임아웃을 늘린다**. 기본 HTTP 타임아웃은 30초라 큰 리포트 F8 은 초과할 수 있다 → `sapctl --timeout 180 transact ...`. **클라이언트가 타임아웃나도 쿼리는 서버에서 계속 실행**되며, con 이 풀리면 다음 호출이 즉시 응답한다(긴 `--timeout` 단일 호출로 완료를 기다리는 게 효율적). 빠져나올 땐 okcd `/n` 으로 한 번에 Easy Access 복귀.
3. **ALV 결과 read 는 OS 차이가 있다**:
   - **macOS(SAP GUI for Java)**: ALV `GuiGridView` 가 scripting 트리에 **노출되지 않는다** (`wnd[0]/usr` 자식 0개) → `snapshot`/`read` 로 셀을 못 읽는다. **screenshot 이미지 판독이 유일·정답**. (실측: ZMMR류 리포트 결과 그리드)
   - **Windows(COM)**: `GuiGridView` 가 노출돼 셀 직접 read 가 보통 가능(`GetCellValue`). 그래도 행수 많으면 screenshot 이 빠를 때가 많다.

## 4. 자주 쓰는 vkey

| vkey | 의미 |
|---|---|
| 0 | Enter |
| 2 | F2 (선택/상세) |
| 3 | F3 / Back (뒤로) |
| 8 | F8 (실행) |
| 11 | Ctrl+S (저장) |
| 12 | F12 / Cancel |

## 5. popup 처리 패턴

매 step 후 popup 이 떴는지 확인하려면:
```bash
sapctl exec 'var s=application.findById("/app/con[0]/ses[0]"); "wnd1=" + (s.findById("wnd[1]")!=null) + " title=" + (s.findById("wnd[1]") ? s.findById("wnd[1]").getText() : "-")'
```
- 정보성 popup → `{"vkey":0,"wnd":1}` (확인)
- 취소 필요 → `{"vkey":12,"wnd":1}`
- 버튼 명시 → `{"press":"wnd[1]/usr/btnSPOP-OPTION1"}` 등

## 6. 트러블슈팅

| 증상 | 원인 / 해법 |
|---|---|
| `connect failed` | SAP GUI 가 안 떠있거나 daemon 미실행. `SAPGUI -f sap-daemon.js` 로 재기동 |
| `conns=0` | 로그인 안 됨. Logon Pad 에서 시스템 더블클릭 로그인 |
| exec 가 timeout | EDT 에 SAP API 호출 wrap 함. `--edt` 빼기 (기본 OFF 가 정답) |
| `findById` null | 화면이 예상과 다름. 먼저 snapshot 으로 실제 트리 확인 |
| getChildren hang | Z-custom container lazy-load. 트리 walk 포기, screenshot 으로 |
| 리포트 F8 이 timeout / 응답 없음 | 조회조건 너무 넓어 전체 스캔. ① 회사코드·플랜트 등으로 좁히고 ② `--timeout 180`. 쿼리는 서버에서 계속 도니 긴 timeout 단일 호출로 완료 대기. 빠져나올 땐 okcd `/n`. (§3.7) |
| ALV 결과 셀이 `snapshot`/`read` 로 안 잡힘 (macOS) | SAP GUI for Java 가 `GuiGridView` 를 트리에 노출 안 함(`usr` 자식 0). **screenshot 이미지 판독** 사용. Windows COM 은 GuiGridView 셀 read 가능. (§3.7) |
| 스크린샷이 엉뚱한 창 | 기본은 타겟 세션의 **최상위/활성 창**(모달 우선). 특정 창은 `--wnd N`(0=메인, 1=첫 모달), 또는 `--match` 로 창 제목 substring. |
| 모달 popup 이 안 잡히고 뒤 메인화면만 캡처됨 | 기본이 최상위 창이라 보통 자동으로 모달이 잡힘. 명시하려면 `--wnd 1`. (Windows=PrintWindow 로 모달 hwnd 직접 / macOS=`Window.getWindows()` 로 `SAPDialog` 모달까지 paintAll — `Frame.getFrames()` 는 Dialog 를 못 봄) |
| 모달 캡처가 큰 여백으로 채워짐 | 구버전(2.1.0)에서 enlarge 가 고정 레이아웃 모달까지 키워 발생(이슈 #2). **2.1.1+ 에서 모달은 확대 스킵** — native 크기로 선명하게 캡처. |
| 캡처 때 SAP 창이 잠깐 깜빡/이동 | 작은 **메인** 창 확대 캡처 과정. 거슬리면 `--no-enlarge`. (Windows: 포그라운드 점유 없이 `SWP_NOACTIVATE` 로 처리. 모달은 확대 안 하므로 해당 없음) |
| (Windows) 스크린샷이 `.bmp` 로 저장됨 | Pillow 미설치 → PrintWindow 대신 HardCopy(BMP) fallback. `py -3 -m pip install --user Pillow` 로 PNG 직접 저장 활성화 |
| SAP 가 종료 안 됨 / 창 없이 떠있음 | 창 없는 잔존 JVM. `sapctl kill-orphans` (포트 안 잡고 창 0개인 SAP 만 종료, daemon·세션은 보존). 미리보려면 `--dry-run` |
| `sess=null` / `/app/con[0]/ses[0] not found` (targets 엔 보이는데 exec/transact/snapshot 만 실패) | 잔존 JVM 으로 **con/ses 인덱스 불일치**. ① `sapctl targets` 로 실제 살아있는 인덱스 확인 → `--con/--ses` 로 그 인덱스 지정, ② 또는 `sapctl kill-orphans` 로 잉여 JVM 정리(근본 해결). macOS 진단: `sapctl exec 'var o="";for(var c=0;c<3;c++)for(var s=0;s<3;s++){try{var e=application.findById("/app/con["+c+"]/ses["+s+"]");if(e)o+="con"+c+"ses"+s+"="+e.info.getTransaction()+";"}catch(x){}}o'` |
