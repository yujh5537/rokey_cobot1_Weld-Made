# 통합 감사 보고서 — 접촉 스캔 시스템 MVP (2026-09-21, Day 4)

- 감사 기준: `origin/main` **717cbdd** (2026-09-21 16:41 KST, #118 병합 직후) + 열린 PR #122 · #127
- 방법: 읽기 전용. GitHub 이력(PR 64 · 이슈 63 · CI 200회 · 커밋 90) 수집, 코드 정독, origin/main 스냅샷을 격리 도메인(`ROS_DOMAIN_ID=99`, localhost only)에서 빌드·테스트. 코드·PR·이슈는 고치지 않았다. 실기·Virtual 로봇 명령은 실행하지 않았다.
- 근거 표기: `PR #번호` · `커밋 7자리` · `파일:줄` · `CI 실행 ID`. **★ = 감사자가 직접 재확인한 항목**, 나머지는 하위 분석(부록 A~F)의 `파일:줄` 근거를 따른다.
- 시각은 모두 KST.

## 0. 지시문과 저장소가 다른 점 (먼저 읽을 것)

| 지시문 | 저장소 실제 | 처리 |
|---|---|---|
| 정의서 통합본 v1.1 | `docs/design/contact-scan-interface-spec-integrated-v1.2.md`만 있다 | v1.2를 기준으로 썼다 |
| 노드 구성도 v1.0, 연결 39선 | `contact-scan-node-diagram-v1.1.md`, **40선**(자체 27 · 표준 3 · 외부 8 · 검토안 2). v1.1에서 P03 추가(`:183` `:211` `:272`) | 40선 전부 확인 |
| BRD v3.1.0 (md) | `docs/BRD.md`는 v3.2.0(#48). v3.1.0은 `docs/archive/`의 docx뿐 | v3.2.0 기준 |
| 일정 시트 상태 열은 전부 "대기" | 9/21 09:51 갱신본(#96 이후 로컬 갱신)은 완료 18 · 진행 5 · 지연 5 · 대기 14 | 그래도 상태는 GitHub 근거로 판정 |
| README 6절 "정의서 2장 → 3~5장 → 노드 구성도 3장 → drawio 동시 갱신" | `docs/design/README.md`는 17줄, 절 번호 없음. 이 문구는 전 브랜치에서 찾지 못했다. 저장소 규칙은 "계약(`docs/contracts/`)과 다르면 계약이 맞다"이다 | 4곳 갱신 여부는 확인했으나, 규칙 자체는 **미확인** |
| 계약 1차 기준 = 정의서 | 레포 규칙(CLAUDE.md, `docs/contracts/README.md`)은 **`docs/contracts/`가 1차, `docs/design/`은 참고** | 드리프트 표에 두 문서를 모두 놓았다 |

### 0-1. 감사 스냅샷(717cbdd, 16:41) 이후 바뀐 것 — 이 보고서 본문에는 반영되지 않았다

| 시각 | 변경 | 본문에서 낡은 곳 |
|---|---|---|
| 17:22 | `origin/euiseok/20260921-t35-spring-history`에 `277289a` 1커밋(Spring 작업·공작물·스캔 이력 관리, 24파일 +1350, `docker/postgres/init/002_business_schema.sql` 포함). PR은 아직 없음 | 2절 T35 "미착수" → **진행**. 3.3 "Spring용 테이블 없음", 5절 규칙 6 "Spring 미확인"은 다시 봐야 한다 |
| 17:26 · 17:30 | PR #127에 `a95d185`(자동 영점이 실패하면 정지 F₀로 돌아가지 않고 다음 구간을 다시 모은다) · `30b36d6`(real.yaml 주석 위치) | 부록 D의 "자동 영점이 실패하면 main과 같은 정지 F₀ 판정으로 돌아간다"는 더 이상 맞지 않다 |
| 17:26 | #129 `0cd18d1` 병합: sim(Virtual) 종단 원본(`docs/test-reports/data/20260921/scan_sim_t19b/`) | M2 판정의 근거가 하나 더 생겼다(판정은 그대로) |

---

## 1. 한 장 요약

**전체 진척률**: 42개 작업 중 **완료 26(62 %)**, 진행 3, 미착수·지연 7, 당일 판정 1(T37), 계획일 전 5. D4까지 계획된 37개 기준으로는 70 %. 마일스톤은 M1(2일 지연 달성) · M2(2일 지연 달성) · **M3 미달성** · **M4 미달성**.

**M4까지 남은 핵심 결함 (5개)**

| # | 결함 | 근거 |
|---|---|---|
| 1 | **웹이 결과를 그리지 않는다.** React에 `scan/result` 분기가 없고 직육면체는 고정 크기 목업이다. ROS → MQTT → FastAPI(WS·DB)까지는 이어진다 | ★`frontend/src/App.jsx:390-482`(분기 5종뿐) · ★`App.jsx:597-604`(`BoxGeometry(2,1,1.2)`) · `scan/result` grep 0건 |
| 2 | **실기 START가 거절된다.** `search_origin_pose` · `base_to_fixture`가 의도적으로 꺼져 있고, 켜는 조건 둘(#109 해결 = PR #127, 새 탐침 TCP x·y = PR #122 절차 1)이 모두 미병합·미실시 | ★`contact_scan_bringup/config/real.yaml:148-158` |
| 3 | **실기에서 모서리(EDGE)를 한 번도 검출하지 못했다.** 큐브가 밀기에 19 mm 밀려났고(고정 필요), 낙하가 0.35 mm/s로 느리며, 실제 누름이 목표 3 N이 아니라 약 8.3 N(REL 기준선) | ★`docs/test-reports/realrobot-session_20260921.md` 5-1 · 5-12 |
| 4 | **정지 상태 tare로는 허공에서 거짓 CONTACT가 난다**(큐브 45 mm 위). 수정 PR #127은 리뷰 0건, 현지의 "보류 대신 둔한 임계 6 N" 요청 미반영 | 같은 문서 5-2 · 5-5 · 5-11, PR #127 |
| 5 | **bringup이 mqtt_bridge 파라미터를 주입하지 않는다.** 코드 기본값 `broker_host=127.0.0.1`로 떠서 웹 PC가 별도 기기면 연결되지 않는다(#112에서는 손으로 지정) | `real.yaml:186-187` · `sim.yaml:182-183` · `mqtt_bridge/mqtt_bridge.py:173-179` · `bringup.launch.py:48-62` |

**지연 원인 상위 3개**
1. **D1~D2 골격·환경 작업이 1~2일씩 밀려 연쇄됐다.** 자체 노드 5개가 모두 main에 들어온 것이 9/20 17:08(M1 2일 지연). 그 결과 실기(D3)와 통합(D2)이 통째로 밀렸다.
2. **실기에서만 드러나는 물리 문제가 D4 오전을 다 썼다**(tare의 운동 상태 의존, 탐침 밀림·교체, 툴·TCP 등록 풀림 2회, 큐브 밀림). 위험 2가 실현됐다.
3. **통합이 늦었다.** 저녁 통합은 9/18·9/19 미실시, 첫 통합이 9/20 밤. 그래서 통합 결함(`/robot/stop` 서버 50시간 부재, safety_monitor 기동 즉시 래치·첫 정지 조건에서 크래시)이 9/21 하루에 9건 몰려 나왔다. 병합 57건 중 32건이 무리뷰, main CI는 flaky로 7회 실패.

**오늘 바로 해야 할 일 3개**
1. **PR #127 결정·병합 → sim 종단(M2) 재실행 → PR #122 절차 1(TCP x·y) → `real.yaml` 좌표 2개 켜기.** 부재 고정(본드·테이프선)을 먼저 한다. (학민·현지)
2. **React가 `scan/result`를 받아 직육면체·엣지를 그리게 한다**(T36 최소판). Spring Boot(T35)는 이력 조회 1화면으로 줄인다. (의석)
3. **`sim.yaml`/`real.yaml`에 `mqtt_bridge:` 절을 넣고**(현지 소유 파일) robot_manager 종료 경로의 순응 해제 구멍을 이슈로 올린다. (현지 → 학민)

---

## 2. 작업 진척표

판정: `완료`(main 병합 + 기능 코드 존재) · `진행`(미병합 브랜치/열린 PR 또는 일부만) · `미착수` · `지연`(계획일이 지났는데 완료 아님). 지연 일수는 계획일 대비 main 도달일.

| ID | 작업 | 담당 | 계획 | 판정 | 근거 | 비고 |
|---|---|---|---|---|---|---|
| T01 | 인터페이스 v0.1 동결 | 전원 | D1 | 완료(+1일) | #47 `cf24fc3` 9/19 12:28 | 회의는 D1, 계약 PR 병합이 D2 |
| T02 | 실기 연결, 툴·TCP 등록 | 학민 | D1 | 완료(+1일) | #57 9/19 16:14, #110 9/21(TCP z 252.12) | 새 탐침 x·y는 옛 값(−1.30, 3.71). 확인은 #122 절차 1 |
| T03 | 작업대 원점·z=0·홈 | 학민 | D1 | 완료(+1일) | #60 9/19, #80 9/20, #110(z 100.503) | 옆면 2.1° 기울기 처리 결정 없음(계약은 축 평행 가정) |
| T04 | API 호출 확인 로그 | 학민 | D1 | 완료(+3일) | #66 9/21 15:45 (46.4 h 열림) | Real은 부분. `move_line` success=true 무동작 사례 기재 요청(#100) 반영 여부 미확인 |
| T05 | 저장소·브랜치 규칙 | 현지 | D1 | 완료(+2일) | `f96fdc0` 9/18, #61 9/20 09:27 | |
| T06 | 일일 통합 빌드 | 현지 | D1~5 | **진행** | #92, `docs/test-reports/daily/2026091{8,9}.md`(미실시·소급), `20260920.md`(부분), `20260921.md`(오전) | 9/21 저녁 기록은 아직 없음 |
| T07 | contact_detector 골격, sim 입력원 | 현지 | D1 | 완료(+3일) | #68 9/20, #97 9/21 09:15, #100 9/21 15:14 | |
| T08 | 무접촉 외력·수집 주기 측정 | 현지·학민 | D1 | 완료(+2일) | #57, #71, #92(`TR-01_20260920.md`), 9/21 세션 5-1(이동 중 잡음) | |
| T09 | contact_scan_interfaces | 병후 | D1 | 완료(+1일) | #49(base=#47 브랜치) → main 9/19 12:28 | 빌드 ★20종 등록 확인 |
| T10 | scan_manager 상태 기계 골격 | 병후 | D1 | 완료(+1일) | #50 9/19 14:12 | |
| T11 | docker-compose 골격 | 의석 | D1 | 완료(정시) | #46 9/18 20:22 | |
| T12 | React·Three.js 골격, 목업 | 의석 | D1 | 완료(+1일) | #56 9/19 13:37 | |
| T13 | execute_motion Action | 학민 | D2 | 완료(+2일) | #73 9/21 09:44 (22.7 h 열림, 코멘트 16) | 시트는 "진행" |
| T14 | /robot/stop, finally 해제 | 학민 | D2 | 완료(+2일) | #101 9/21 14:41, #114, #116, #121 9/21 16:26 | 잔여: 노드 종료 경로 해제 미보장(5절 규칙 8), #125 OPEN |
| T15 | RobotSample 발행, 주기 실측 | 학민 | D2 | 완료(+1일) | #72 9/20 15:21, #83, #98 | |
| T16 | contact_detector 완성 | 현지 | D2 | 완료(+1일), **재작업 진행** | #74, #86 9/20 17:08 / 이슈 #16 OPEN, PR #127 OPEN | 실기 결과로 tare·EDGE 켜기 방식 변경 중 |
| T17 | geometry_estimator | 현지 | D2 | 완료(+1일) | #70, #75 9/20 | |
| T18 | safety_monitor 최소판 | 현지 | D2 | 완료(+1일) | #89 9/20 17:08, 수정 #99 · #117 9/21 | 9/21 실기에서 2회 크래시 후 수정 |
| T19 | scan_manager 전체 시퀀스 sim | 병후 | D2 | 완료(+2일) | #76, #77 9/20, #104, #106, #118, #119 9/21 / sim 종단 통과 `daily/20260921.md:22-40` | 이슈 #19 OPEN |
| T20 | result_store | 병후 | D2 | 완료(정시) | #64 9/19 17:47 | |
| T21 | mqtt_bridge | 의석 | D2 | 완료(+1일) | #67 9/20 12:04, #88 | 담당 병후→의석 #63. ★테스트가 paho 없는 PC에서 0건 실행 |
| T22 | FastAPI MQTT↔WS | 의석 | D2 | 완료(정시) | #65 9/19 17:22 | |
| T23 | 3D 뷰, 4버튼, 단계 표시 | 의석 | D2 | 완료(+1일) | #56, #78 9/20 13:38 | 직육면체는 목업 고정 크기 |
| T24 | 실기 TR-01 임계 튜닝 | 학민·현지 | D3 | **지연(진행)** | 9/21 세션 5-5·5-8: 접촉 판정 성공 / `TR-01_20260920.md:53-58` 부분 실시 / PR #122 OPEN | 10회 산포·검출 하중·판정 지연·임계 확정 미실시 |
| T25 | 실기 슬라이딩·모서리 검출 | 학민·현지 | D3 | **지연(진행)** | 9/21 세션 5-1(EDGE 없음) · 5-12(모서리 못 찾음) | 미확인(실기 기록 필요): 4방향 |
| T26 | 중지·안전복귀·재시작 로직 | 병후 | D3 | 완료(+1일) | #95 9/21 11:01 | |
| T27 | mqtt_bridge↔FastAPI 실제 연결 | 병후·의석 | D3 | 완료(+1일) | #112 9/21 14:47 | broker_host 수동 지정 |
| T28 | PostgreSQL 스키마, DB 쓰기 | 의석 | D3 | 완료(정시) | #84 9/20 16:09 | |
| T29 | 로그 패널, 접수/완료 표시 | 의석 | D3 | 완료(정시) | #93 9/20 17:52 | |
| T30 | 실기 5점 전체 탐색, 편향 실측 | 학민·현지 | D4 | **지연(미착수)** | `real.yaml:148-158`, PR #122 본문 "아직 못 함" | 선행: #127 + TCP x·y |
| T31 | TR-02 ±3 mm, 120 s | 학민·현지 | D4 | 지연(미착수) | 흔적 없음 | 미확인(실기 기록 필요) |
| T32 | 실기 중지·안전복귀·재시작(TR-08) | 병후·학민 | D4 | 지연(미착수) | `/robot/stop` 수동 호출 확인만(세션 5-10) | |
| T33 | safety_monitor 확장(최신성, HB) | 현지 | D4 | 지연(미착수·**포기 선언**) | `daily/20260920.md:118`, ★`safety_monitor.py:83-85` 구독 2개뿐 | 데이터 최신성은 T18에 포함. `/web/heartbeat` 감시 없음 |
| T34 | 반복성 10회 | 현지 | D4 | 지연(미착수) | 흔적 없음 | |
| T35 | Spring Boot 작업·이력 | 의석 | D4 | 지연(미착수) | `origin/euiseok/20260921-t35-spring-history` 고유 커밋 0(= `d5c869a`) | main의 Spring은 기동 클래스 + actuator뿐 |
| T36 | 엣지 강조·좌표 표, 진행 표시 | 의석 | D4 | 지연(미착수) | 브랜치·PR 없음. `App.jsx:38-42` HOMING/RESUMING 라벨만 | M4 결함 1과 같은 자리 |
| T37 | 기능 동결 | 전원 | D4 | 미확인 | 감사 시각(16:41) 이후 | 열린 PR #122 · #127 |
| T38~T42 | D5 시험·리허설 | — | D5 | 계획일 전 | — | |

### 팀원별 집계 (공동 작업은 양쪽, "전원"은 4명 모두)

| 담당 | 계획 | 완료 | 진행 | 미착수·지연 | 당일(T37) | 계획일 전 | 정시 완료 |
|---|---|---|---|---|---|---|---|
| 학민 | 16 | 8 | 2 (T24·T25) | 3 (T30·T31·T32) | 1 | 2 | 0 |
| 현지 | 17 | 7 | 3 (T06·T24·T25) | 4 (T30·T31·T33·T34) | 1 | 2 | 0 |
| 병후 | 11 | 7 | 0 | 1 (T32) | 1 | 2 | 1 (T20) |
| 의석 | 14 | 9 | 0 | 2 (T35·T36) | 1 | 2 | 4 (T11·T22·T28·T29) |
| 팀 | 42 | 26 | 3 | 7 | 1 | 5 | 5 |

### M1~M4 조건별 판정

| 마일스톤 | 조건 | 판정 | 근거 |
|---|---|---|---|
| M1 9/18 | 인터페이스 v0.1 동결 | 일치(+1일) | #47 9/19 12:28 |
| | 전 노드 빈 껍데기 빌드 | 일치(+2일) | 5번째 노드 도달 #89 9/20 17:08. 9/18에는 `ws_cobot1/src` 비어 있음(`daily/20260918.md:17`) |
| | 좌표 기준 확정 | 부분 | #57·#60·#110. 축 평행은 2.1° 기울기로 판정 불가 |
| M2 9/19 | ROS: Virtual+sim 5점 → 직육면체 | 일치(+2일) | `daily/20260921.md:22-40` (100×60×40 mm 박스, 오차 −0.14~−0.23 mm) |
| | 웹: 목업 3D | 일치(정시) | #56 9/19 13:37 |
| M3 9/20 | 실기 윗면 1점 검출 | 일치(+1일, 수동 goal) | 세션 5-5: CONTACT, 판정 오차 0.016 mm |
| | 실기 모서리 1방향 이상 | **누락** | 세션 5-1·5-12: EDGE 이벤트 0회 |
| | 웹 버튼으로 sim 시작·중지 | 일치(+1일) | #112 9/21 14:47 |
| M4 9/21 | 시작 버튼 → 실기 5점 → 3D 직육면체 | **누락** | 실기: START 거절(`real.yaml:148-158`). 웹: `scan/result` 미표시 |
| | 저녁 기능 동결 | 미확인 | 열린 PR 2건 |

---

## 3. 계약 드리프트 표

**총평**: msg 11 · srv 5 · action 4 = **20종이 정의서·계약 문서·패키지 3자 일치**(★`ros2 interface list` 20종 확인, `test_contract_sync.py` 22 passed). QoS는 모든 노드가 `contact_scan_qos` 상수만 import해 비호환 조합 0건. MQTT 19개 토픽 이름·키·QoS·retain도 계약과 일치. 검토안(`/scan/calibrate` · `/calibration/result`) 구현 없음 → **범위 초과 없음**. 이름·타입·QoS가 달라서 연결이 안 되는 결함은 **0건**이고, 끊김은 전부 "한쪽 끝이 없는" 경우다.

### 3.1 연결이 끊기는 결함 (한쪽 끝 없음)

| 인터페이스 | 정의서/계약 | 발행·서버 측 | 구독·클라이언트 측 | 판정 |
|---|---|---|---|---|
| MQTT `scan/result` → 화면 | `mqtt-schema.md` 4장 | `mqtt_bridge.py:510-517` → FastAPI `main.py:227-247`(WS 중계 + DB) | **React 분기 없음** ★`App.jsx:390-482` | 누락 (M4 차단) |
| `/web/heartbeat` (L26) | `ros-interfaces.md:39` safety_monitor가 구독 | `mqtt_bridge.py:239, 312-319` | **safety_monitor 구독 없음** ★`safety_monitor.py:83-85`. `HB_EXPIRED(405)` 발급처 없음 | 누락 (T33 포기) |
| MQTT `hb/web` · `conn/web`(LWT) | 계약: 웹이 발행 | **FastAPI 발행 코드 없음**(publish는 `main.py:411, 540` 두 곳) | `mqtt_bridge.py:284-285, 312-324` 수신 준비됨 | 누락. 지금은 무해, T33 병합 시 HB_EXPIRED 래치 위험 |
| `/scan/state` → safety_monitor (L10) | `ros-interfaces.md:35` | scan_manager 발행 | safety_monitor 구독 없음. `RobotSample.operation`으로 대체(`safety_core.py:128-130`) | 누락 — 연결 표를 고칠지 코드를 고칠지 결정 필요 |
| `/onrobot/sendCommand` (X06) | 외부 선 | — | 호출 0건, `rg2_grip_*` 파라미터 없음 | 누락 — 수동 파지로 확정했는지 미확인 |
| mqtt_bridge 파라미터 | 정의서 6장 | `mqtt_bridge/config/mqtt_bridge.yaml`은 설치만 되고 로드 안 됨 | `bringup.launch.py:48-62`는 sim/real.yaml만 전달, 두 파일에 절 없음 | 부분 — 별도 PC 배치 시 끊김 |

### 3.2 불일치 · 부분

| 항목 | 계약 | 구현 | 근거 |
|---|---|---|---|
| Action goal 거절 | 계약 5.1~5.3: 조건 불충족은 goal 거절 → 웹 `cmd/ack accepted=false` | scan_manager가 **항상 ACCEPT**, 거절은 Result(1xx) abort. 웹은 BUSY·SAFETY_LATCHED에도 `accepted=true`를 먼저 받는다 | ★`scan_manager.py:257` · `:612-628` · `mqtt_bridge.py:379-387` · 계약 `ros-interfaces.md:419,434,450` · `mqtt-schema.md:45,76` |
| stop의 `command_result` | 모든 명령은 완료/실패 통지 | `_pending_stop`은 `phase=STOPPED`일 때만 비운다. IDLE에서 받은 stop·ERROR로 끝난 stop은 결과가 안 나가고, 남은 request_id가 **다음 작업의 STOPPED에 엉뚱하게 성공 처리**된다 | ★`mqtt_bridge.py:417-427` · `:491-508` · `state_machine.py:84-88` |
| `debounce_n` 미지값 | 미측정은 null | uint8이라 NaN 불가, `debounce_set`으로 구분하는데 bridge가 `*_set`을 읽지 않아 **0으로 나가 DB에 저장** | `scan_manager/conversions.py:171-185` · `mqtt_bridge.py:91-105` · `encoders.py:223` · `db.py:244-247` |
| `RobotStatus.error/error_code` | 오류 상태 반영 | 항상 False/OK | `robot_manager.py:334-335` |
| `SafetyStatus.reason_code` | 4xx | 하강 제한에 `DROP_LIMIT(205)` | `safety_monitor.py:55-60` · 계약 `:273` |
| 하강 제한 기준 z | 1차·2차 "기준도 같다"(계약 7.2) | 1차 = goal 직전 샘플(`robot_manager.py:423-426`), 2차 = OP_SLIDE 첫 샘플(`safety_core.py:128-130`) | 실차는 미확인 |
| `ExecuteMotion.Result.pose` 무효 | 유효 플래그 없음 | 미측정 시 0, scan_manager가 `pose_stamp==0`을 "없음"으로 해석(암묵 규칙) | `robot_manager.py:837-839` · `conversions.py:123-129` |
| 미구현 감시 | `OVER_SPEED(401)` · `OUT_OF_WORKSPACE(402)` · `HB_EXPIRED(405)` · `MAX_DISTANCE(202)` | 발급처·파라미터 없음. 툴·TCP 시작 시 확인(`units-frames.md:93`) 없음(#123) | 부록 A §8 |
| request_id | UUID v4 | 로컬 발급분이 UUID 아님 | `safety_monitor.py:183-185` · `scan_manager.py:1292-1293` |
| 사유 코드 용도 | 계약 7.2 표 | tare에 `BUSY`, mqtt_bridge가 서버 미기동에 `NOT_SUPPORTED` · 예외에 `ROBOT_ERROR` | `contact_detector.py:285-289` · `mqtt_bridge.py:417-421` |
| React 명령 수 | 6종(안전 해제·설정 등록 포함) | 버튼 4종. **웹에서 래치를 풀 수 없다.** safety/status · robot/status · hb/ros · conn/ros 미사용 | `App.jsx:828-846` |
| React 축 매핑 | Base 우수 좌표 | (x, z, y) = 거울상. 올바른 것은 (x, z, −y) | `App.jsx:725-729` |
| 웹 DB 중복 키 | 계약 v0.1.9: `(scan_id, stamp)` | `scan_id` 단일 키 → 재시작 시 부분 결과 덮어씀 | `001_schema.sql:7,25,99` · `db.py:88,161,240` |

### 3.3 미결 항목의 사실상 결정

정의서 `:13` · `:1345`가 "T01 회의로 (a) 제안을 전부 계약 v0.1로 채택"이라 적어 타입·enum·QoS는 이미 계약이다. 아래는 값·규칙이 TBD였던 것이 코드로 굳은 항목이다.

| 미결 항목 | 굳은 내용 | 근거 |
|---|---|---|
| HOME 목표(#19 계열) | `home_pose`(double[6]) → **`home_joint_deg` + move_joint** | `robot_manager.py:96-97, 489-492`. 계약 5.4 주석(`:459`) · `ExecuteMotion.action:5`는 아직 `home_pose` |
| Action cancel | "(제안) cancel = /scan/stop" → **cancel REJECT** | ★`scan_manager.py:258-259` |
| `moving` 근거 | 위치 변화 창 판정 | `robot_manager.py:84-85, 258-262` (#72, #101) |
| 두산 호출 | amovel 대신 `motion/move_line` ASYNC, `DR_QSTOP`, `DR_FC_MOD_REL` | `dsr_client.py:14-39` |
| 해제 순서 | move_stop → release_force(0.3 s) → release_compliance, 실패 시 `compliance_released=false` | `robot_manager.py:778-808` (#121) |
| 미접촉·미소실 | `REASON_MAX_DISTANCE` + `NO_CONTACT/NO_EDGE`, goal은 succeed | `robot_manager.py:449-450, 621-628` |
| `/scan/state` 주기 | 2 Hz 제안 → 1 Hz | `real.yaml:120` |
| 엣지 보조 신호 | 외력 감소(`edge_force_drop_ratio`) 미사용, z만 | `detector_core.py:10-17` |
| 작업 시작 순서 | 설계서 tare → MOVE_TO / 코드 **MOVE_TO → 정지 확인 → tare → DESCEND** | `sequence.py:448-461` |
| DB·REST | 테이블 `scan_jobs`·`measurements`·`contact_events`·`scan_configs`(정의서 `scan_result`·`scan_event`), REST `/commands/*`, WS `/ws`(정의서 `/api/*`, `/ws/live`) | `001_schema.sql`, `main.py` |
| 파라미터 이름 | `downsample_hz`→`sample_publish_hz`, `hb_ros_hz`→`heartbeat_hz`, `stop_timeout_s` 1.0→`stop_settle_s` 1.5 | `mqtt_bridge.py:173-179, 248` |

### 3.4 문서만 낡은 것 (상위)

- 정의서 v1.2 ↔ 계약 어긋남 14항목: `tip_radius_m` 0.003(실측 0.000225) · `detect_latency_s` 0.040(0.020) · `contact_threshold_n` 4.0(3.0) · `sample_stale_ms` 100(sim 500/real 300) · `search_origin_pose` double[6](7원소 quaternion) · `base_to_fixture`(3원소) · 결과 중복 키 · 판정 샘플 정의 · `moving` TBD · `move_speed_mps` 없음 · 1.7절(phase 기반)과 6.3절(operation 기반) 모순 · 4.1/4.2/3.7 필드 표에 `requester`·`baseline_norm_n`·`stop_confirmed` 등 누락.
- 계약 내부: `ros-interfaces.md:5`(출처 "v1.1") · `:115`("moving 근거 TBD") vs `:688`("T15에서 정했다") · `:686` 값 TBD 문구 · `mqtt-schema.md:3` 머리말 v0.1.9 누락 · 계약 예시 `contact_threshold_n` 4.0.
- ★`real.yaml:125-131, 145, 147, 169`: 값이 이미 채워졌는데 "TBD" 주석 8줄이 남아 있다(감사자도 처음에 이 줄 때문에 오판했다).
- 전체 표: 부록 A(ROS) · 부록 B(MQTT·웹).

---

## 4. 계약 변경 이력

| 버전 | PR · 병합 | 누가 | 무엇이 → 무엇으로 (이유) |
|---|---|---|---|
| v0.0 | `f96fdc0` 9/18 15:38, **main 직접 커밋**(보호 설정 전) | 현지 | 계약 초안 |
| v0.1 | #47 9/19 12:28 | 병후 | 정의서 제안 전부 채택, T01 회의 결정 |
| v0.1.1 | #49(base = #47 브랜치) | 병후 | 인터페이스 패키지. 코드오너 아닌 의석만 승인, 내용은 #47에서 재검토 |
| v0.1.2 | #57 9/19 16:14 | 학민 | TCP 249.99, 팁 반지름 0.225 mm, 툴 등록 휘발성 |
| v0.1.3 | #60 9/19 17:58 | 학민 | z=0 100.6, 작업대 원점, 홈 관절각 |
| v0.1.4 | #72 9/20 15:21 (+#83, #85 덧붙임) | 학민 | `/robot/sample` 37.6 Hz 실측, 위치 변화 기반 `moving` |
| v0.1.5 | #79 9/20 16:07 | 병후 | 판정 샘플 = 조건이 처음 성립한 샘플 |
| v0.1.6 | #82 9/20 16:20 (**PR 제목은 "v0.1.7"**) | 병후 | `search_origin_pose` 추가 |
| v0.1.7·8 | #80 9/20 17:27 | 학민 | 라운드 가설 폐기, 축 기울기 2.1°, 편향 2.25 mm(잠정·이후 무효), TCP z 248.52 |
| v0.1.10 | #98 9/21 11:09 | 학민 | 발행 주기를 부하 의존 범위로, 공백 꼬리 |
| v0.1.11 | #110 9/21 14:23 | 학민 | 배치 원칙, 탐침 전제조건, TCP z 252.12 |
| v0.1.9 | #91 9/21 14:47 (**번호보다 늦게 병합**, 21.6 h 열림) | 병후 | target_force_n 대응, recontact 파라미터, MQTT TBD, 결과 중복 키 |
| v0.1.12 | #127 OPEN, 리뷰 0 | 학민 | 하강 중 자동 영점, 밀기 z 기반 EDGE 켜기 |

**이력 관리 자체는 지켜졌다.** 계약 경로 14커밋 중 CHANGELOG 없이 바뀐 것은 #62(package.xml 이메일)뿐, 코드오너 승인 없이 병합된 계약 PR 없음, v0.1 이후 타입 변경 없음. 다만 승인 뒤 추가 커밋이 재승인 없이 병합된 사례(#110 `80fc5a1` — 계약 본문 실질 변경, #72, #85, #98)가 있다(브랜치 보호: 최소 승인 0, 새 커밋에 승인 무효화 없음).

**문서 4곳 반영**: `docs/design/`은 #48(`8dd44c8`, 9/19 14:31) 이후 **한 번도 갱신되지 않았다**. v0.1.2~.11 전부 정의서 2장·3~5장에 미반영. 연결선은 v0.1 이후 바뀌지 않아 노드 구성도 3장·drawio의 선은 지금도 맞다(L10·L26은 문서가 아니라 코드가 빠진 것). #127이 병합되면 정의서 4.2(`:691`) · 노드 구성도 L12(`:166`) · architecture drawio의 tare 카드가 처음으로 틀려진다.

**파급 누락**

| 계약 | 영향받는 코드 | 상태 |
|---|---|---|
| v0.1 `/robot/stop` | robot_manager 서버 | **50.2 h 부재**(9/19 12:28 → #101 9/21 14:41). safety_monitor(#89)는 21.5 h 동안 없는 서비스를 호출 |
| v0.1.2 툴·TCP 확인 | robot_manager | 코드 0건, 9/21 실기에서 2회 풀림(#123 OPEN) |
| v0.1.3 작업영역 | safety_monitor | 없음(T33) |
| v0.1.5 판정 샘플 | `real.yaml:167` | `detect_stamp − force_stamp`로 잰다는 주석이 계약 정의(디바운스 몫 제외)와 어긋남 |
| v0.1.8 축 기울기 2.1° | geometry_estimator | 처리 결정(이슈·ADR) 없음 |
| v0.1.9 중복 키 · hb/web | 웹 DB · FastAPI | `scan_id` 단일 키, hb/web 발행 없음 |
| v0.1.10 공백 꼬리 | yaml 근거 주석 | `real.yaml:34,61` · `sim.yaml:32,80` 옛 수치 |
| 9/21 수정 PR 5건 | 계약 | `startup_grace_s`(#99) · 정지 미확인 시 요청 유지(#114) · 그래도 HOME은 출발(#116) · SLIDE 종료 0.3 s 대기(#121) · SIGINT 시 CANCELED(#119) — **계약·정의서 grep 0건** |

전체: 부록 F.

---

## 5. 구조 규칙 판정표

| # | 규칙 | 판정 | 근거 | 설명 |
|---|---|---|---|---|
| 1 | 자체 노드 5개, geometry_estimator·result_store는 모듈 | 일치 | `scan_manager.py:173` · `robot_manager.py:73` · `contact_detector.py:96` · `safety_monitor.py:68` · `mqtt_bridge.py:169` · `bringup.launch.py:25-31` | Node 상속 클래스 정확히 5개 |
| 2 | 정지 경로 3가지 | 일치 | ① `mqtt_bridge.py:404` → `scan_manager.py:1029-1074` → `robot_manager.py:671-707` ② `robot_manager.py:345-363, 587-588, 652-669` ③ `safety_monitor.py:156-189` | ③은 실기에서 수동 호출로만 확인(세션 5-10) |
| 3 | 래치 | 일치(비고) | `safety_core.py:281-296` · `scan_manager.py:422-432` | 래치가 프로세스 메모리에만 있고 scan_manager가 `/safety/status` **최신성을 안 본다**(#120 OPEN). safety_monitor가 죽으면 마지막 `latched=false`를 믿고 시작을 받는다 |
| 4 | 접수 ≠ 완료 | 부분 | 지킴: `robot_manager.py:704-706, 763-776` · `scan_manager.py:461-478` · FastAPI `main.py:145-156` · React `App.jsx:935-953`. 어긋남: ★`mqtt_bridge.py:417-427` | stop 완료 통지 누락·오배정(3.2) |
| 5 | 중단 위치 vs 측정 좌표 | 일치 | `scan_manager.py:1328-1346, 1421-1434` · `resume.py:188-201` · `conversions.py:81-96` | 섞어 쓰는 곳 없음 |
| 6 | 미측정 ≠ 0 (TR-10) | 부분 | 어긋남: `debounce_n`(3.2), `robot_manager.py:836-840`(Result.pose), `motions.py:68-72`(`distance_travelled` 0.0) | 나머지 전 구간은 NaN/null/`*_valid` 유지: `encoders.py:249-259`(`allow_nan=False`) · `db.py:193-224` · `001_schema.sql:31-57`(nullable, DEFAULT 0 없음). **Spring은 코드가 없어 미확인** |
| 7 | 단위 | 부분 | 변환: `robot_manager/conversions.py:12-40` · `mqtt_bridge/encoders.py:74-91`(m→mm) · `decoders.py:38-61`(mm→m). 어긋남: ★`dsr_client.py:87-89` | 이중 변환·역류 없음. **`MoveLine.vel[1]`(deg/s)에 mm/s 값**을 넣는다(★`MoveLine.srv:6`). 가속 계수 4·2 하드코딩 |
| 8 | 순응·힘 제어 해제 | 부분 | finally: `robot_manager.py:433-445, 778-808`, 시험 `test_node.py:639-692`(7경로). 어긋남: ★`robot_manager.py:852-864` | **노드 종료 경로 미보장**: `KeyboardInterrupt`만 잡고 종료 시 해제 호출 없음. 해제 실패 뒤 `compliance_active=True`여도 OP_HOME이 출발 가능(`:386-418`) |
| 9 | 드라이버 호출은 robot_manager만 | 일치 | `robot_manager/dsr_client.py:10-12`가 유일. 그 밖은 `docs/env/*.py` 4개(환경 스크립트) | |
| 10 | 중지가 홈·재시작을 부르지 않음 | 일치 | `scan_manager.py:1029-1065` · `state_machine.py:85-88` · `main.py:460-488` · `App.jsx:339-341` | |

전체: 부록 C.

---

## 6. 시나리오 추적 매트릭스

| 시나리오 | 판정 | 핵심 사유 (근거) |
|---|---|---|
| 1.1 작업 시작 | 부분 | 순서가 MOVE_TO → tare → DESCEND(`sequence.py:448-461`). goal 항상 ACCEPT(★`scan_manager.py:257`). `allow_concurrent` 파라미터 없음. **실기는 START 거절**(★`real.yaml:148-158`) |
| 1.2 접촉 판정 | 일치(sim) / 실기 부분 | 임계·디바운스·stale, 판정 pose와 정지 pose 분리 일치. 실기는 정지 tare로 거짓 CONTACT(#109) → #127 |
| 1.3 엣지 판정 | 부분 | 방향 순서 `[POS_X, NEG_X, POS_Y, NEG_Y]`(`real.yaml:179`), n/4 일치. 외력 감소 보조 신호 미사용. **실기 EDGE 검출 0회** |
| 1.4 작업 중지 | 일치(구멍 1) | 접수·완료 분리, STOPPED 전이, 홈 자동 실행 없음. stop `command_result` 누락 경우(3.2) |
| 1.5 안전복귀 | 일치 | 측정값·로그 보존, 래치 중에도 허용. **들어 올림 없이 OP_HOME 하나**(`sequence.py:598-607`) — 실기에서 부재를 긁을 수 있음(PR #122가 수동 lift 절차로 우회) |
| 1.6 재시작 | 일치 | 별도 Action, 기록 복원 후 남은 방향부터(`resume.py:188-201`). 안전복귀를 거친 작업·ERROR 작업은 `NOT_SUPPORTED` |
| 1.7 안전 이상 정지 | 부분 | 웹 경유 없는 정지·래치 일치. 속도·작업영역·HB 감시 없음. 래치가 Result보다 늦으면 사유가 204로 남음 |
| 1.8 설정 등록 | 부분 | 동작 중 거절, P01~P03 전파·되읽기 일치(#104). **React에 설정 UI 없음.** 부분 실패 처리는 #52 OPEN |
| 1.9 과대 외력 | 일치 | 이중 감시, 시작 전 두 임계 되읽기. 실기에서 끝까지 동작 확인(세션 5-0). 동시 발생 시 사유 400/204 갈림 |
| 1.10 래치 해제 | 부분 | 조건 해소 시에만 성공(`safety_core.py:281-296`). **React에 해제 버튼·safety/status 표시 없음** |

**연결 표 40선**: 연결됨 33(L01~L09, L11~L25, L27, P01~P03, X01~X05. X04는 amovel 대신 `move_line` ASYNC — 이름 다름) · **끊김 2**(L10, L26 — safety_monitor 구독 없음) · 미구현 3(X06 `/onrobot/sendCommand`, C01·C02는 검토안이라 정상) · 미확인 2(X07·X08 드라이버↔컨트롤러, 저장소 밖) · 방향 반대 0.

**M4 종단 경로의 첫 단절 지점**
- **sim 경로**: 웹 버튼 → FastAPI → MQTT → mqtt_bridge → `/scan/run` → 5점 → geometry → result_store → `/scan/result` → MQTT → FastAPI(WS·DB)까지 연결. **첫 단절 = React가 `scan/result`를 받지 않는 곳**(★`App.jsx:390-482`). 결과 조회 REST도 없어 발행 후 접속한 브라우저는 결과를 못 받는다. 팁·접촉점은 Base 좌표로 그려져 원점의 목업 박스와 떨어져 보인다.
- **실기 경로**: **첫 단절 = scan_manager의 START 거절**(★`real.yaml:155, 158` 주석). 그 뒤로도 ① 정지 tare 거짓 접촉(#109) ② EDGE 미검출·부재 고정 ③ REL 누름 8.3 N ④ `edge_bias_offset_m` 0.0(미측정) ⑤ 특이점 자세에서 `move_line`이 success=true로 조용히 실패(`daily/20260921.md:66-87`, 코드 방어 없음)가 남아 있다.

전체: 부록 D.

---

## 7. 디버깅 변경 영향

**수정 PR**: 12건 중 9건이 9/21 하루에 병합. #99 · #114 · #116은 리뷰 0건으로 2~10분 만에 병합.

| PR | 고친 것 | 남긴 것 |
|---|---|---|
| #83 | pending_calls 경쟁 | `call_queue.py:25 abandon_after_s=5.0` 하드코딩. 시간 초과 1회에 5 s 샘플 단절 → SAMPLE_STALE |
| #99 | safety_monitor 기동 즉시 래치 | `startup_grace_s` 3.0 — 계약에 없음, 실기 충분성 미확인 |
| #100 | sim 좌표·`home_joint_deg` | 특이점 무동작은 "사람이 먼저 홈으로"라는 운영 전제로만 남음 |
| #101 | `/robot/stop` 서버 신설 | `motion_state.py:16 min_span_ratio=0.5` 하드코딩, `moving` 판정식 변경이 계약에 없음 |
| #114 → #116 | 정지 미확인 시 요청 유지 → HOME은 예외 | 정지 미확인 상태에서 movej가 나갈 수 있음. `/scan/resume` 첫 MOVE_TO는 거절, 복구는 수동 `/robot/stop` 재호출뿐 |
| #117 | severity 전환 ValueError 크래시(실기 2회) | 감시자가 죽어도 아무도 모름(#120 OPEN) |
| #119 | SIGINT 트레이스백 | 모션 중 SIGINT에 `/robot/stop`·cancel을 보내지 않음 |
| #121 | 켜기 시간 초과 시 순응이 켜진 채 남던 구멍 | SLIDE 종료마다 0.3 s 대기(`robot_manager.py:800`) |
| #124 | 노드 시험 0.2 s → 2.0 s | **머지 커밋 `3be7879`가 같은 증상으로 main CI 실패**(★실행 35571365338). #107은 CLOSED인데 미해소 |

**임시 우회 코드**: TODO/FIXME/HACK, 주석 처리된 호출, bare except, xfail, 삭제된 시험은 **없다**. 있는 것 — 하드코딩 수치(`dsr_client.py:89,95` 가속 4×·2×, `robot_manager.py:40 LOOP_PERIOD_S=0.02`, `abandon_after_s`, `min_span_ratio`, `mqtt_bridge.py:250 client_id`), yaml에 없는 코드 기본값(`stop_settle_s` 1.5 · `motion_timeout_s` 60 · `feedback_period_s`), `mqtt_bridge.py` 넓은 except 7곳(#90), 디버그 출력(`backend/app/main.py:221` 모든 payload print + `on_message` 안 동기 DB 저장, `App.jsx:384` console.log).

**파라미터 값 변화표 (핵심)**

| 파라미터 | 정의서/BRD | 현재 (sim / real) | 변경 PR | 구분 |
|---|---|---|---|---|
| `over_force_n` | 30 N | 30 / 30 (9/21 실기는 실행 중 15로 낮춤) | — | BRD 일치. 실기 15 N은 문서 반영 필요 |
| `drop_limit_m` | 5 mm | 0.005 | — | 일치 |
| 샘플 · 표시 · HB | 50 Hz · 10 Hz · 1 Hz | 일치 | — | 일치(실측 49.6 Hz, 최대 공백 358 ms) |
| `contact_threshold_n` | 4.0 | 3.0 | #61/#97 | 문서 반영 필요(mqtt-schema 예시도 4.0) |
| `tip_radius_m` | 0.003 | 0.000225 | #57 | 정당(실측) |
| `detect_latency_s` | 0.040 | 0.020 | #97 | 계산값, 실측 아님(T24) |
| `sample_stale_ms` | 100 | 500 / 300 | #89/#99 | **실기 공백 337~358 ms가 300을 넘는다** |
| `stale_age_ms` | 100 | 200 / 100 | #97 | **SLIDE 중 102·199 ms 공백에 EDGE 추세선 초기화**(세션 5-12) |
| `slide_target_force_n` | TBD | 3.0 (REL) | #73 | **실제 누름 약 8.3 N > KPI 5 N** |
| `max_descend_m` | TBD | 0.080 / 0.120 | #100/#110 | 정당(근거 주석 있음) |
| `max_slide_m` | TBD | 0.080(←0.15) / 0.060 | #100 | sim 쪽 근거 약함 |
| `edge_bias_offset_m` | TBD | 0.0 | — | "미측정인데 0" — 규칙 4의 경계. #80의 2.25 mm는 무효 처리 |
| `startup_grace_s` | 없음 | 3.0 | #99 | 문서 반영 필요 |

**CI**: 200회 중 실패 12(전부 `ros` 잡). 원인: scan_manager 노드 시험 flaky 9(#107, reason_code 104) · robot_manager `test_sample_id_increases` flaky 2(추적 이슈 없음) · #100의 진짜 실패 1(#106으로 해소) · #94 설정 오류 1. **main push 실패 7회**(9/20 17:52, 9/21 09:39 · 10:30 · 12:54 · 14:53 · 15:02 · 16:06), 빨간 구간 합계 약 168분·최장 85분(12:54~14:19), 재실행 0회. cancel-in-progress로 main SHA 9개(안전 수정 #117 `ca46fde` 포함)가 검증 없이 지나갔다.

전체: 부록 E.

---

## 8. 지연 원인 분석

### 지표

| 담당 | 병합 PR | 열림 중앙값 | 최장 | 하룻밤 넘긴 PR | 무리뷰 병합 | 첫 리뷰 중앙값 | 1000줄 초과 | 리뷰 후 재작업 커밋 |
|---|---|---|---|---|---|---|---|---|
| 학민 | 16 | 2.7 h | 46.4 h (#66) | #66, #73 | 4/16 | 2.3 h | #72, #73, #80 | 14 |
| 현지 | 12 | 2.2 h | 19.2 h (#61) | #61, #92, #97 | 10/12 | 0.9 h | #89 | 0 |
| 병후 | 20 | 1.9 h | 21.6 h (#91) | #47, #48, #50, #91, #95, #96 | 11/20 | 1.5 h | #47, #48, #50, #64, #76, #77, #95, #104 | 11 |
| 의석 | 9 | 0.4 h | 18.4 h (#67) | #67, #88 | 7/9 | 9.3 h | #56, #67 | 0 |

- 병합 57건 중 **무리뷰 32건(56 %)**. revert 0, force-push 흔적 없음, main 직접 푸시는 초기 커밋 `f96fdc0` 1건.
- **모든 커밋이 09~18시에 몰려 있다.** 17시 이후 올린 PR 13건은 전부 다음 날 오전에 병합됐다 — "저녁 통합" 시간대에 병합이 멈춘다.
- 일자별 커밋: 9/18 4 · 9/19 13 · 9/20 43 · 9/21 30. 9/18에 병후·학민 커밋 0(병후는 PR 생성만, 학민은 실기 환경).

### 작업별 원인

| 지연 작업 | [사실] | [추론] |
|---|---|---|
| M1 (+2일) | 9/18 main에 ROS 패키지 0개. 계약 PR #47이 15.8 h 열림(9/18 20:43 → 9/19 12:28). 9/19 학민은 T02·T03, 현지는 T05(D1 작업)에 시간을 씀(`daily/20260919.md:34-35`) | D1에 회의·환경·골격을 모두 넣은 계획이 실제 가용 시간(15시 이후 착수)보다 컸다 |
| T13·T14 (+2일) | #73 22.7 h 열림·코멘트 16. `/robot/stop` 서버가 #73에 없어 #101로 따로 만듦(9/21 14:41). 이후 #114 → #116 → #121 연쇄 | T14가 T13에 묻혀 있다가 9/21 오전 실기·sim 통합에서 부재가 드러났다. "계약이 말한 서버가 떠 있는가"를 보는 시험이 없다 |
| T19·M2 (+2일) | 9/20 통합에서 `detect_latency_s` 하나로 START 거절(`daily/20260920.md:82-84`), 9/21에는 기동 즉시 래치(#99) · execute_motion 서버 없음(#73 미병합) · 특이점(#100) 4단 장애 | 값의 소유자가 갈린 파라미터(병후 노드, 현지가 값 결정)가 통합 전까지 드러나지 않았다 |
| T24·T25·M3 | 9/20 실기는 T03 후속 측정만(#80), 그 시점 contact_detector·robot_manager가 main에 없음. 9/21 오전은 탐침 밀림·교체, 툴·TCP 풀림 2회, tare 문제, 큐브 밀림 | 위험 2("Day 2까지 sim만")의 전제가 깨졌다 — sim이 D4에야 돌았으므로 실기가 첫 통합 시험장이 됐다 |
| T30~T32·T34 | 선행(T24·T25, #127, TCP x·y) 미완 | 위 연쇄 |
| T35·T36 | T35 브랜치 고유 커밋 0, T36 흔적 없음. 의석 9/21 커밋 2건(#112) | 위험 1 실현. Must인 "결과 3D 표시"가 Should인 T36에 묶여 있어 같이 밀렸다 |
| T33 | 현지가 9/20에 포기 선언 | 위험 3(현지 D1~D2 밀도) — 9/20 하루 커밋 22건 |
| T06 | 9/18·9/19 미실시, 기록은 9/20 소급 | 돌릴 대상이 없었다(9/18), 기록 규칙이 "미실시도 기록"임을 놓쳤다(`daily/20260918.md:27-29`) |

### 구조적 원인 vs 개별 원인

**구조적**
1. **통합 빌드 부재 → 늦은 결함 발견** [사실] 첫 통합 9/20 밤, 통합 결함 수정 9건이 9/21에 집중. [추론] 9/19 저녁에 "빈 노드라도 5개 띄우기"를 했다면 `/robot/stop` 부재·기동 래치·필수 파라미터 누락이 하루 일찍 나왔다.
2. **리뷰 병목이 아니라 "무리뷰 + 하룻밤" 패턴** [사실] 첫 리뷰 중앙값은 1~2 h로 빠르지만 56 %가 무리뷰, 17시 이후 PR은 전부 익일 병합. 계약 PR(#91 21.6 h, #47 15.8 h)이 특히 길다.
3. **CI 신호 신뢰도 저하** [사실] flaky로 main 7회 실패, 문서·프런트 전용 PR(#92 · #98 · #93)도 ROS flaky로 실패, 재실행 0회. 수정(#124) 후에도 재발.
4. **계약 흔들림은 크지 않다** [사실] v0.1 이후 타입 변경 0, 변경은 실측값·문구 위주. 코드가 계약보다 먼저 들어간 사례 3건(최대 26.7 h). [추론] 지연의 주원인은 계약이 아니다.
5. **역할 과부하(위험 1·3)** [사실] 의석 T35·T36 미착수, 현지 T33 포기. 학민은 실기 + robot_manager 수정 연쇄 + 계약 PR 6건을 혼자 맡음(9/21 PR 9건).

**개별**
- 9/21 1차 에뮬레이터 사망은 `pkill -f "bringup.launch.py"` 실수(`daily/20260921.md:56`).
- 9/21 실기 첫 실행에서 tare 호출 누락(절차, 세션 5-1).
- 9/20 실기 세션이 입회자 없이 진행(`TR-01_20260920.md:75-79`).

---

## 9. 조치 목록

| 우선 | 내용 | 담당 제안 | 근거 | 영향 |
|---|---|---|---|---|
| **P0** | PR #127 결정(보류 vs 둔한 임계 6 N) → 병합 → **sim 종단 재실행**(필수 파라미터 5개 추가, sim.yaml 변경) | 학민(작성) · 현지(소유자 리뷰) | #109, 세션 5-11 | M3·M4, TR-01 |
| **P0** | PR #122 절차 1(TCP x·y) → `real.yaml:155,158` 켜기. **부재를 본드·테이프선으로 고정한 뒤** | 학민·현지 | `real.yaml:148-158`, 세션 5-12 | M4, T30 |
| **P0** | React: `scan/result` 수신 → `dims`/꼭짓점으로 직육면체, 엣지·경로 후보 선 표시. 접속 시 최신 결과 조회 REST 1개 | 의석 | `App.jsx:390-482, 597-604` | M4, 4.4.5 |
| **P0** | `sim.yaml`·`real.yaml`에 `mqtt_bridge:` 절(`broker_host` 등) 추가 | 현지(소유 파일) · 값은 의석 | `real.yaml:186-187` | M4, TR-09 |
| **P0** | 실기 EDGE 판정: 낙하 0.35 mm/s·z 낙차 1 mm 문제(#128), REL 누름 8.3 N(#105) 결정 | 학민·현지 | 세션 5-1·5-12 | M3, TR-02 |
| P1 | robot_manager 종료 경로에서 `release_all` 보장(시그널 훅) + 해제 실패 시 goal 차단 | 학민 | `robot_manager.py:852-864, 386-418`, #125 | TR-07 |
| P1 | scan_manager가 `/safety/status` 수신 시각을 보고, 끊기면 시작 거절. bringup respawn 검토 | 병후·현지 | #120 | TR-07 |
| P1 | mqtt_bridge stop 완료 통지: ERROR·IDLE 경우 처리, FastAPI ack/결과 timeout | 의석·병후 | `mqtt_bridge.py:417-427` | TR-05, TR-09 |
| P1 | goal 항상 ACCEPT ↔ 계약 5.1: 계약을 구현에 맞춰 명문화(코드 변경보다 싸다) | 병후 | `scan_manager.py:257` | TR-09 |
| P1 | `debounce_n` 0 → null(`debounce_set` 반영) | 의석·병후 | `encoders.py:223` | TR-10 |
| P1 | `sample_stale_ms` 300 · `stale_age_ms` 100을 실기 공백(358 · 199 ms) 기준으로 재설정 | 현지 | 세션 5-1·5-12 | 연속 시험, TR-07 |
| P1 | `MoveLine.vel[1]`에 mm/s가 들어가는 것 수정, 가속 계수 파라미터화 | 학민 | `dsr_client.py:87-89` | #109 원인 후보 |
| P1 | 툴·TCP 등록 확인(기동 시 + goal 수락 시) | 학민 | #123 | 안전 |
| P1 | React 안전 해제 버튼 + safety/status 표시(지금은 웹에서 래치를 못 푼다) | 의석 | `App.jsx:828-846` | 1.10, TR-07 |
| P1 | flaky 2종: #107 재오픈, `test_sample_id_increases` 이슈화. main 실패 시 재실행 규칙 | 병후·학민 | 실행 35571365338 | 기능 동결 신뢰도 |
| P1 | 통합 PC에 `rosdep install`(paho) — mqtt_bridge 테스트 0건 실행 | 현지 | ★`colcon test` exit 5 | T06 |
| P2 | 9/21 수정 5건을 계약에 반영, `real.yaml` 낡은 TBD 주석 8줄 삭제, yaml 근거 주석 갱신 | 각 소유자 | 4절 | 문서 |
| P2 | 웹 DB 키 `(scan_id, stamp)`, React 축 매핑 (x, z, −y), print·console.log 제거 | 의석 | 3.2 | TR-10 |
| P2 | 안전복귀 전 들어 올림(시퀀스) 또는 운영 절차 명문화, 특이점 무동작 방어 | 병후·학민 | `sequence.py:598-607` | TR-08 |

**일정 조정 제안** ("줄이는 순서"를 따름, "줄이지 않는 것"은 그대로)
1. 2단 속도(4.2.7) — 이미 미착수, 뺀다.
2. 로그 다운로드(4.4.6) — 뺀다.
3. TR-03 배치 민감도 — 뺀다(`daily/20260921.md:139`에서 이미 예고).
4. 엣지 좌표 **표** — 뺀다. 단 **엣지·경로 후보의 3D 강조와 직육면체 표시는 Must(4.4.1·M4)이므로 남긴다.**
5. Spring Boot 사용자 관리 — 뺀다. T35는 이력 조회 + 작업·공작물 최소 CRUD만.
6. 반복성 10회 → 5회.
- 건드리지 않는 것: Must 전체, ±3 mm, 중지·안전복귀·재시작 분리(코드상 분리는 일치 — 규칙 10).
- M4 판정은 9/22 오전으로 하루 미루고, 9/22는 T30 → T31(TR-02) → T32(TR-08) → TR-07 순으로 실기를 점유하는 것이 현실적이다. T33(heartbeat)는 포기 유지, 대신 #120(감시자 생존 확인)을 P1로 한다.

---

## 10. 문서 갱신 필요 목록

| 문서 | 고칠 것 |
|---|---|
| 정의서 v1.2 | 3.4절 14항목(`tip_radius_m`, `detect_latency_s`, `contact_threshold_n`, stale 값, `search_origin_pose` 7원소, `base_to_fixture` 3원소, `home_joint_deg`, `move_speed_mps`, 결과 중복 키, 판정 샘플, `moving` 근거, 1.7↔6.3 모순, 필드 표 누락, 1.1 순서 MOVE_TO → tare) · mqtt_bridge 파라미터 이름 · 13장 REST/WS 경로 · DDL 테이블 이름. #127 병합 시 4.2 tare 설명 |
| 노드 구성도 v1.1 · drawio | L10 · L26(구독 없음 — 코드를 고칠지 선을 지울지 결정), X04(`move_line` ASYNC), X06(RG2 미사용 시 삭제), #127 병합 시 L12 · tare 카드 |
| `docs/contracts/` | `ros-interfaces.md:5`(출처 v1.2) · `:115`(moving TBD 삭제) · `:459` + `ExecuteMotion.action:5`(`home_pose` → 관절각, **인터페이스 패키지 주석이므로 계약 PR로**) · `:599` · `:686` · 5.1~5.3(goal ACCEPT 후 Result 거절) · 9/21 수정 5건 · 9/21 실기 주기표(최대 358 ms) · `mqtt-schema.md:3` 머리말 · 예시 임계 4.0 → 3.0 · CHANGELOG의 v0.1.6/0.1.7 번호 혼선, 이슈 번호로 적힌 항목(#108 → #110, #109 → #127) |
| BRD | `:467` TR-02 "부재 2종" vs 배치 원칙 "큐브 한 종", 부재 고정 요구(세션 5-12 — BRD·계약에 없는 요구사항) |
| 일정 시트 | 상태 열: T04 · T13 · T14 · T19 · T27 → 완료, T24 · T25 → 진행, T30~T36 → 지연, T33 비고 "포기(9/20)". 기준 문서 표기 v3.0.0 → v3.2.0. 마일스톤 달성 여부: M1 9/20, M2 9/21 |
| yaml 주석 | `real.yaml:125-131, 145, 147, 169` 낡은 TBD, `real.yaml:34,61` · `sim.yaml:32,80` 옛 주기 수치, `test_sim_process.py:11` 머리말 |

---

## 11. 미확인 항목

| 항목 | 누구에게 무엇을 |
|---|---|
| "README 6절" 4곳 동시 갱신 규칙의 출처 | 지시문 작성자 — 어느 README의 어느 판인지 |
| 9/21 오후 실기 결과(T24 10회, T25 4방향, TCP x·y) | 학민 — `realrobot-session_20260921_pm.md` 작성본(#122는 절차서뿐) |
| T35 작업이 로컬에 있는지 | 의석 — 원격 브랜치는 고유 커밋 0 |
| 기능 동결(T37) 실시 여부, 9/21 저녁 통합 결과 | 현지 — `daily/20260921.md` 저녁 절 |
| RG2 파지를 수동으로 확정했는지(X06) | 학민 · 팀 결정 |
| 하강 제한 1차·2차 기준 z의 실차 | 학민 — SLIDE bag에서 두 기준 샘플 비교 |
| SLIDE 중 Ctrl-C 시 컨트롤러에 순응이 남는지 | 학민 — Virtual에서 `get_control_mode` 조회(사람이 실행) |
| `startup_grace_s` 3 s가 실기에서 충분한지, `moving_eps_m` 오탐 | 현지·학민 — 실기 기동 로그 |
| Spring Boot 구간의 `*_valid`·null 보존(TR-10) | 의석 — 코드가 생긴 뒤 boxed `Double`·null 직렬화 확인 |
| 런타임 DDS 매칭(`ros2 topic info -v`) | Virtual 기동은 사람이 해야 한다. 이번 감사는 정적 분석 + 빌드·단위 시험까지 |
| T04: `move_line` success=true 무동작 사례가 `api-check-log.md`에 들어갔는지 | 학민 |
| #88의 실제 Ctrl+C 검증 기록, FastAPI 동기 DB 저장의 지연 영향(TR-05 200 ms) | 의석 |

### Phase 8 실행 결과 (★)
- `colcon build --symlink-install`: 7 packages, 24.4 s, 실패 0 (origin/main 717cbdd 스냅샷, `ws_dsr` source).
- `ros2 interface list | grep contact_scan`: msg 11 · srv 5 · action 4 = 20종, 계약 2장 목록과 일치.
- `colcon test`: **1361 tests, 0 errors, 0 failures, 0 skipped** — scan_manager 1089 · robot_manager 87 · contact_detector 78 · safety_monitor 53 · bringup 12 (+ interfaces). **mqtt_bridge는 `paho` 미설치로 0건 실행(exit 5).**
- sim/Virtual 런치 후 `ros2 node/topic/service/action list`, `param dump`: **미실시.** Virtual Mode는 에뮬레이터(`sodvir`) 기동이 필요하고 이 PC는 실기와 같은 도메인(30)에 연결될 수 있어, 읽기 전용 감사에서는 띄우지 않았다. 대체 근거: `daily/20260920.md:72-80` · `daily/20260921.md:22-40`의 사람 실행 기록.

---

# 부록 (하위 분석 원문)



---

## 부록 A. ROS 계약 3자 대조

### Phase 3 — ROS 계약 3자 대조 (정의서 v1.2 · contracts 문서 · 인터페이스 패키지 · 사용 코드)

- 감사 대상: origin/main 스냅샷(717cbdd). 경로는 모두 저장소 루트 기준 상대경로다.
- 방식: 읽기 전용. 저장소 파일 수정 · 커밋 · gh 쓰기 · ros2/로봇 실행 없음. 실행한 것은 파일 읽기 · grep과, ROS 없이 도는 `contact_scan_interfaces/test/test_contract_sync.py`(문서 ↔ 패키지 비교 테스트, 22건 통과)뿐이다.
- 판정 등급: `일치` · `부분` · `불일치` · `누락` + 별도 분류 `미결 항목의 사실상 결정` · `범위 초과` · `문서만 낡음`.

#### 0. 전제와 주의

| # | 사실 | 근거 |
|---|---|---|
| 0-1 | **지시문은 정의서 v1.1을 기준으로 하라고 했으나 저장소에는 v1.2만 있다.** `docs/design/README.md`가 "이전 버전 파일은 지운다"고 적고 있고 v1.1 파일은 없다. 이 감사는 v1.2를 1차 기준으로 썼다 | `docs/design/README.md:3,9` · `docs/design/contact-scan-interface-spec-integrated-v1.2.md:1` |
| 0-2 | 정의서 v1.2 스스로 "구속력 있는 계약은 `docs/contracts/` v0.1이며, 이 문서와 다르면 계약이 우선"이라고 적었다. 레포 규칙(CLAUDE.md)과 같다 | 정의서 `:4` · `docs/design/README.md:5` |
| 0-3 | **정의서 10장 머리말: T01 회의로 (a) 제안을 전부 계약 v0.1로 채택**(#11만 예외). 따라서 본문에 `제안(TBD)`라고 표기돼 있어도 **타입 · 필드 · enum · 코드표 · QoS는 이미 계약**이다. 이 보고서에서 "미결 항목의 사실상 결정"으로 분류한 것은 ① 정의서 6장의 값이 `TBD`인 파라미터, ② 정의서 본문에 "(제안)"으로만 남고 contracts 문서가 침묵하는 동작 규칙, ③ contracts 9장 TBD 목록에 있는 것에 한한다 | 정의서 `:13`, `:1345` · `docs/contracts/ros-interfaces.md:683-699` |
| 0-4 | contracts 문서 머리말은 아직 출처를 "정의서 통합본 **v1.1**"이라고 적고 있다(저장소에는 v1.2만 있음) | `docs/contracts/ros-interfaces.md:5` |
| 0-5 | 스냅샷의 contracts 버전은 `ros-interfaces.md` v0.1.10 / `units-frames.md` v0.1.11 / CHANGELOG 최상단 v0.1.11 | `docs/contracts/ros-interfaces.md:3` · `docs/contracts/CHANGELOG.md:5` |

#### 1. 핵심 결론

1. **이름 · 타입 · QoS 불일치로 연결 자체가 안 되는 결함은 없다.** 모든 Topic 발행 · 구독이 `contact_scan_qos`의 같은 상수를 import해서 쓰고, 노드 코드에 손으로 만든 `QoSProfile`이 없다. 토픽 · 서비스 · 액션 이름 문자열도 전부 계약과 글자 단위로 같고, launch에 네임스페이스 · remap이 없다(§5).
2. 대신 **한쪽 끝이 아예 없는 연결이 3건** 있다: `/web/heartbeat`(발행만 있고 구독자 없음), `/scan/state → safety_monitor`(구독 없음), `/onrobot/sendCommand`(호출 없음). 앞의 둘은 계약 2.1 연결 표와 어긋난다(§4 ①).
3. **타입 정의 3자(정의서 코드 블록 · contracts 코드 블록 · 패키지 파일)는 20개 전부 일치**한다(§3). 드리프트는 타입이 아니라 **동작 규칙 · 파라미터 · 문서 표**에 있다.
4. 가장 큰 동작 불일치: **scan_manager가 Action goal을 항상 accept**하고 거절을 Result(abort)로 돌려준다. 계약 5.1~5.3과 `mqtt-schema.md`의 "goal 수락/거절 → `cmd/ack`" 매핑과 다르며, 그 결과 웹은 BUSY · SAFETY_LATCHED 거절에도 `cmd/ack accepted=true`를 먼저 받는다(§4 ②-1).
5. 파라미터: 정의서 6장의 이름 중 **계약 이름(★) 14개는 전부 일치**, 그 밖은 크게 드리프트했다(robot_manager `home_pose`→`home_joint_deg`, mqtt_bridge `downsample_hz`→`sample_publish_hz` 등). mqtt_bridge는 bringup yaml에 절이 없어 **코드 기본값(브로커 127.0.0.1)으로 돈다**(§7).

---

#### 2. 3-A 기준 계약 추출 (정의서 v1.2)

##### 2.1 Topic T1~T8 (정의서 2.1 · 3장 · 7.6)
| # | 이름 | 타입 | 발행 | 구독 | QoS | 정의서 줄 |
|---|---|---|---|---|---|---|
| T1 | `/robot/sample` | `RobotSample` | robot_manager | contact_detector · safety_monitor · mqtt_bridge | SENSOR | `:209`, `:265-305` |
| T2 | `/robot/status` | `RobotStatus` | robot_manager | scan_manager · safety_monitor · mqtt_bridge | STATE | `:210`, `:309-343` |
| T3 | `/contact/event` | `ContactEvent` | contact_detector | robot_manager · scan_manager · mqtt_bridge | EVENT | `:211`, `:347-398` |
| T4 | `/scan/state` | `ScanState` | scan_manager | contact_detector · safety_monitor · mqtt_bridge | STATE | `:212`, `:402-450` |
| T5 | `/scan/result` | `ScanResult` | scan_manager | mqtt_bridge | STATE | `:213`, `:454-522` |
| T6 | `/scan/log` | `ScanLog` | scan_manager | mqtt_bridge | LOG | `:214`, `:536-574` |
| T7 | `/safety/status` | `SafetyStatus` | safety_monitor | scan_manager · mqtt_bridge | STATE | `:215`, `:576-611` |
| T8 | `/web/heartbeat` | `WebHeartbeat` | mqtt_bridge | safety_monitor | HEARTBEAT | `:216`, `:615-638` |

##### 2.2 Service S1~S5 · Action A1~A4 (정의서 2.2 · 2.3 · 4장 · 5장)
| # | 이름 | 타입 | 서버 | 클라이언트 | 정의서 줄 |
|---|---|---|---|---|---|
| S1 | `/robot/stop` | `StopRobot` | robot_manager | scan_manager · safety_monitor | `:222`, `:672-682` |
| S2 | `/contact/tare` | `TareForce` | contact_detector | scan_manager | `:223`, `:711-723` |
| S3 | `/scan/stop` | `StopScan` | scan_manager | mqtt_bridge | `:224`, `:737-747` |
| S4 | `/scan/set_config` | `SetConfig` | scan_manager | mqtt_bridge | `:225`, `:775-784` |
| S5 | `/safety/reset` | `ResetSafety` | safety_monitor | mqtt_bridge | `:226`, `:843-851` |
| A1 | `/scan/run` | `RunScan` | scan_manager | mqtt_bridge | `:232`, `:879-895` |
| A2 | `/scan/home` | `ReturnHome` | scan_manager | mqtt_bridge | `:233`, `:912-924` |
| A3 | `/scan/resume` | `Resume` | scan_manager | mqtt_bridge | `:234`, `:941-953` |
| A4 | `/robot/execute_motion` | `ExecuteMotion` | robot_manager | scan_manager | `:235`, `:1002-1054` |

하위 msg 3종: `ScanConfig`(12값 + `*_set` 12개, `:786-815`) · `Segment`(start · end · length · valid, `:524-530`) · `ReasonCode`(상수 33개, `:1199-1234`).
표준 인터페이스: `rcl_interfaces/srv/SetParameters` P01~P03(`:1328`). 외부: `dsr_msgs2`(`:1286-1300`) · `/onrobot/sendCommand`(`:1302-1307`). 검토안: `/scan/calibrate` · `/calibration/result`(`:1332-1337`).

##### 2.3 7.1 enum · 7.2 코드표 · 7.3 ID · 7.6 QoS
- enum(`:1145-1155`): `TYPE_CONTACT/EDGE/OVER_FORCE=0/1/2` · `PHASE_IDLE..RESUMING=0..10` · `DIR_NONE/POS_X/NEG_X/POS_Y/NEG_Y=0..4` · `OP_NONE/MOVE_TO/DESCEND/SLIDE/HOME=0..4` · `REASON_TARGET_REACHED..REJECTED=0..9` · safety `LEVEL_OK/WARN/STOP=0/1/2` · log `LEVEL_INFO/WARN/ERROR=0/1/2`.
- 코드표(`:1163-1197`): 0 / 100~108 / 200~205 / 300~307 / 400~406 / 500~501. "번호는 추가만"(`:1161`).
- ID(`:1238-1245`): `request_id` UUID v4(웹=FastAPI, 로컬=요청 노드) · `scan_id` `YYYYMMDD-HHMMSS-xxxx` · `motion_id` uint32, scan 안에서 1부터, 0=없음 · `sample_id`/`event_id` uint64 발행마다 +1, 0=없음 · `session_id` UUID.
- QoS(`:1271-1278`): SENSOR=BEST_EFFORT/VOLATILE/KEEP_LAST 5 · STATE=RELIABLE/TRANSIENT_LOCAL/1 · EVENT=RELIABLE/VOLATILE/50 · LOG=RELIABLE/VOLATILE/100 · HEARTBEAT=BEST_EFFORT/VOLATILE/1 · Service/Action 기본.
- 6장 파라미터는 §7에서 코드 · yaml과 나란히 놓는다.

---

#### 3. 3-B 인터페이스 패키지 실제 정의

| 항목 | 결과 | 근거 |
|---|---|---|
| 등록 목록 | msg 11(RobotSample · RobotStatus · ContactEvent · ScanState · ScanResult · Segment · ScanLog · SafetyStatus · WebHeartbeat · ScanConfig · ReasonCode) + srv 5 + action 4 = **20개. 디렉터리의 파일 20개와 1:1**, 빠진 것 · 남는 것 없음 | `ws_cobot1/src/contact_scan_interfaces/CMakeLists.txt:12-34` |
| 의존 | `builtin_interfaces` · `geometry_msgs` · `action_msgs`. `dsr_msgs2` 의존 없음(의도) | `CMakeLists.txt:33` · `package.xml:14-17` |
| QoS 모듈 | `ament_python_install_package(contact_scan_qos)`. 5개 프로파일 + `PROFILES` dict | `CMakeLists.txt:38` · `contact_scan_qos/__init__.py:28-45` |
| 검토안 | `Calibrate` · `CalibrationResult` **없음** → 범위 초과 없음. 노드 코드에도 `calibrat` 문자열 없음 | `CMakeLists.txt:12-34` · grep 결과 0건 |
| 정의서 코드 블록 ↔ 패키지 | 주석 · 공백을 뺀 정의 줄 비교(스크립트): **20/20 SAME**(필드 이름 · 타입 · 순서 · 상수값 · `---`) | 정의서 3~5장 · 7.2 코드 블록 vs `msg/*.msg` `srv/*.srv` `action/*.action` |
| contracts 코드 블록 ↔ 패키지 | `test_contract_sync.py` 오프라인 실행 **22 passed** | `ws_cobot1/src/contact_scan_interfaces/test/test_contract_sync.py:1-16` |
| QoS 값 | 모듈 값 = 정의서 7.6 = contracts 6.3 (5개 모두) | `contact_scan_qos/__init__.py:28-36` · 정의서 `:1271-1277` · `docs/contracts/ros-interfaces.md:575-581` |

판정: 타입 · 상수 · QoS 값 **일치(3자)**.

---

#### 4. 3-C 실제 사용처 (노드 코드, 테스트 제외)

| 노드 | 발행 | 구독 | 서비스 서버 | 서비스 클라이언트 | Action 서버 | Action 클라이언트 |
|---|---|---|---|---|---|---|
| robot_manager | `/robot/sample` SENSOR `robot_manager/robot_manager/robot_manager.py:127` · `/robot/status` STATE `:128` | `/contact/event` EVENT `:129` | `/robot/stop` `:163` | `dsr_msgs2` 10종 `robot_manager/robot_manager/dsr_client.py:24-45` | `/robot/execute_motion` `robot_manager.py:164-169` | — |
| contact_detector | `/contact/event` EVENT `contact_detector/contact_detector/contact_detector.py:124` | `/robot/sample` SENSOR `:125` · `/scan/state` STATE `:126` | `/contact/tare` `:130` | — | — | — |
| safety_monitor | `/safety/status` STATE `safety_monitor/safety_monitor/safety_monitor.py:82` | `/robot/sample` SENSOR `:83` · `/robot/status` STATE `:84` | `/safety/reset` `:86` | `/robot/stop` `:85` | — | — |
| scan_manager | `/scan/state` STATE `scan_manager/scan_manager/scan_manager.py:220` · `/scan/result` STATE `:221` · `/scan/log` LOG `:222` | `/robot/status` STATE `:231-232` · `/safety/status` STATE `:233-234` · `/contact/event` EVENT `:235-236` | `/scan/stop` `:265` · `/scan/set_config` `:268-270` | `/contact/tare` `:239` · `/robot/stop` `:240-241` · `/{node}/set_parameters` · `/{node}/get_parameters` ×3 `:244-250` | `/scan/run` · `/scan/home` · `/scan/resume` `:254-264` | `/robot/execute_motion` `:237-238` |
| mqtt_bridge | `/web/heartbeat` HEARTBEAT `mqtt_bridge/mqtt_bridge/mqtt_bridge.py:239` | `/robot/sample` SENSOR `:203-207` · `/robot/status` `:208-212` · `/scan/state` `:213-217` · `/scan/result` `:218-222` (모두 STATE) · `/scan/log` LOG `:223-227` · `/contact/event` EVENT `:228-232` · `/safety/status` STATE `:233-237` | — | `/scan/stop` `:243` · `/scan/set_config` `:244` · `/safety/reset` `:245` | — | `/scan/run` `:240` · `/scan/home` `:241` · `/scan/resume` `:242` |

(경로는 모두 `ws_cobot1/src/` 아래.)

- `QoSProfile(` 직접 생성: 노드 코드 0건(전부 `from contact_scan_qos import QOS_*`: `robot_manager.py:27` · `contact_detector.py:23` · `safety_monitor.py:20` · `scan_manager.py:39-41` · `mqtt_bridge.py:18`).
- `dsr_msgs2` import: `robot_manager/robot_manager/dsr_client.py:10-12` 한 곳뿐. 서비스 경로는 `/<ns>/dsr_controller2/{aux_control/get_current_posx, aux_control/get_tool_force, system/get_robot_state, motion/move_line, motion/move_joint, motion/move_stop, force/task_compliance_ctrl, force/release_compliance_ctrl, force/set_desired_force, force/release_force}`(`dsr_client.py:24-39`).
- `/onrobot/sendCommand` 호출: **저장소 전체에 0건**(grep `onrobot|sendCommand`는 README 문구 2건만 걸린다: `ws_cobot1/src/README.md:27`, `ws_cobot1/src/robot_manager/README.md:3`).
- launch: 노드 5개를 `name=패키지명`으로, 네임스페이스 · remap 없이 띄운다(`ws_cobot1/src/contact_scan_bringup/launch/bringup.launch.py:56-63`). 파라미터 파일은 `sim.yaml`/`real.yaml` 하나만 넘긴다(`:48-49,62`).

---

#### 5. QoS · 이름 · 타입 호환 분석 (연결 성립 여부)

| 토픽 | 발행 QoS | 구독 QoS(전 구독자) | DDS 호환 | 비고 |
|---|---|---|---|---|
| `/robot/sample` | BEST_EFFORT · VOLATILE · 5 | 같은 상수 ×3 | 성립(BE 발행 ↔ BE 구독) | RELIABLE로 구독하는 곳이 없다 |
| `/robot/status` · `/scan/state` · `/scan/result` · `/safety/status` | RELIABLE · TRANSIENT_LOCAL · 1 | 같은 상수 | 성립. 늦게 뜬 구독자도 마지막 값을 받는다 | VOLATILE 구독자 없음(있어도 성립은 한다) |
| `/contact/event` | RELIABLE · VOLATILE · 50 | 같은 상수 ×3 | 성립 | TRANSIENT_LOCAL을 요구하는 구독자 없음 |
| `/scan/log` | RELIABLE · VOLATILE · 100 | 같은 상수 | 성립 | |
| `/web/heartbeat` | BEST_EFFORT · VOLATILE · 1 | **구독자 없음** | — | §6 ①-1 |

- 비호환 조합(BEST_EFFORT 발행 ↔ RELIABLE 구독, VOLATILE 발행 ↔ TRANSIENT_LOCAL 구독)은 **0건**.
- 이름: 계약의 8 Topic · 5 Service · 4 Action 이름이 서버 · 클라이언트 양쪽에서 같은 문자열이다(§4 표의 줄 참고). 타입도 양쪽이 같은 클래스를 import한다.
- Service · Action QoS: 양쪽 모두 기본값(인자 없음).

---

#### 6. 3-D 드리프트 표

열: [정의서 v1.2] · [contracts] · [패키지] · [발행/서버 코드] · [구독/클라이언트 코드] · [차이] · [판정]. 경로 접두사 `ws_cobot1/src/`는 생략한다(`RM`=`robot_manager/robot_manager/robot_manager.py`, `CD`=`contact_detector/contact_detector/contact_detector.py`, `SM`=`safety_monitor/safety_monitor/safety_monitor.py`, `SC`=`scan_manager/scan_manager/scan_manager.py`, `MB`=`mqtt_bridge/mqtt_bridge/mqtt_bridge.py`, 정의서=`docs/design/contact-scan-interface-spec-integrated-v1.2.md`, 계약=`docs/contracts/ros-interfaces.md`).

##### ① 연결이 성립하지 않는 것 (이름 · 타입 · QoS 불일치 0건 / 한쪽 끝 없음 3건)

| # | 인터페이스 | 정의서 v1.2 | contracts | 패키지 | 발행/서버 | 구독/클라이언트 | 차이 | 판정 |
|---|---|---|---|---|---|---|---|---|
| ①-1 | T8 `/web/heartbeat` | 구독 safety_monitor (정의서 `:216`, `:159`) | 구독 safety_monitor (계약 `:39`) | `WebHeartbeat.msg` 있음 | `MB:239` 발행, `MB:312-319`에서 `hb/web` 수신 시에만 발행(자체 생성 없음 — 이 부분은 일치) | **없음.** `SM:82-86`에 `/web/heartbeat` 구독이 없고 `WebHeartbeat` import도 없다(`SM:18-19`) | 발행만 있고 받는 노드가 없다. `HB_EXPIRED(405)`를 내는 코드도 없다(§8.2). `hb_timeout_s` · `hb_expired_action` 파라미터도 없다(§7.3) | **누락**(구독 측). 만료 시 조치(warn/stop)는 계약 9장 TBD(계약 `:698`)지만, 구독 자체는 연결 표에 확정돼 있다 |
| ①-2 | T4 `/scan/state` → safety_monitor | 구독 safety_monitor, "단계별 한계"(정의서 `:212`, `:158`) | 구독 safety_monitor (계약 `:35`) | — | `SC:220` | **없음**(`SM:82-86`). contact_detector(`CD:126`) · mqtt_bridge(`MB:213-217`)는 구독한다 | safety_monitor는 단계 대신 `RobotSample.operation`으로 SLIDE 구간을 가린다(`safety_monitor/safety_monitor/safety_core.py:128-130`). 정의서 6.3 · 계약 7.2가 요구하는 기준("operation이 OP_SLIDE로 바뀐 첫 샘플")과는 맞다 | **누락**(연결 표 대비). 기능상 대체돼 있으므로 "연결 표가 낡았다"로 정리할지 팀 결정 필요 |
| ①-3 | 외부 `/onrobot/sendCommand` | robot_manager → onrobot_driver, 탐침 파지(정의서 `:1306`, 파라미터 `rg2_grip_width_m` · `rg2_grip_force_n` `:1075`) | "RG2 드라이버는 robot_manager만 호출"(계약 `:72`) | 해당 없음 | — | **호출 0건**(grep). 파라미터 선언도 없다(`RM:77-108`) | 탐침 파지 명령이 코드에 없다. 파지는 사람이 수동으로 하는 전제로 보이나 문서에 그 결정이 없다 | **누락** · 파지 절차를 수동으로 확정했는지는 **미확인**(`docs/decisions/` · `docs/env/tool-tcp-register.md`를 보면 확인된다) |

##### ② 불일치 · 부분

| # | 인터페이스 | 정의서 v1.2 | contracts | 패키지 | 서버/발행 코드 | 클라이언트/구독 코드 | 차이 | 판정 |
|---|---|---|---|---|---|---|---|---|
| ②-1 | A1~A3 goal 거절 | "cmd/ack(접수/거절)는 goal 수락/거절로 매핑"(정의서 `:68`), 진행 중이면 goal 거절 `BUSY`(`:866`) | "진행 중이면 goal 거절 `BUSY`, 래치 중이면 `SAFETY_LATCHED`…"(계약 `:419`, `:434`, `:450`) · `mqtt-schema.md:45,76` "goal 수락/거절 → `cmd/ack`" | 타입 일치 | **항상 ACCEPT**: `goal_callback=lambda _goal: GoalResponse.ACCEPT`(`SC:257`). 거절은 phase를 바꾸지 않고 `Result(success=false, reason_code=1xx)` + `abort()`(`SC:612-628`) | mqtt_bridge는 `handle.accepted`면 `cmd/ack accepted=true`(`MB:379-387`), Result는 `scan/command_result`(`MB:391-400`) | 웹은 BUSY · SAFETY_LATCHED · INVALID_VALUE 거절에도 **`cmd/ack accepted=true`를 먼저 받고**, 곧이어 `scan/command_result success=false`를 받는다. 의도된 우회이며 README가 "계약 문서 PR에서 문구를 맞춘다"고 적어 둠(`scan_manager/README.md:154`) — 계약은 아직 안 고쳐졌다 | **불일치**(계약 5.1~5.3 · mqtt-schema 2~3장). 계약을 고치거나 mqtt_bridge가 즉시 abort를 `cmd/ack accepted=false`로 바꿔야 한다 |
| ②-2 | T2 `RobotStatus.error` · `error_code` | 드라이버/로봇 오류 상태 · 7.2 코드(정의서 `:324-325`) | 같은 필드(계약 `:106-107`) | 일치 | **항상 `error=False`, `error_code=OK`로 고정**(`RM:334-335`). 연결 끊김 · 상태 조회 시간 초과도 `detail` 문자열로만 나간다(`RM:250,267`) | scan_manager · safety_monitor · mqtt_bridge가 구독 | 필드는 있으나 값이 채워지지 않는다. 드라이버 알람 · SAFE_OFF(`dsr_client.py:21`의 3)를 보는 코드 없음 | **부분** |
| ②-3 | T7 `SafetyStatus.reason_code` | "7.2 코드(4xx). OK = 0"(정의서 `:590`, `:603`) | "ReasonCode 4xx"(계약 `:273`) | 일치 | 하강 제한 2차 감시가 **`DROP_LIMIT(205)`**(2xx)을 싣는다(`SM:55-60`, `safety_core.py:28`). `/robot/stop`의 `reason`에도 205(`SM:186`) | mqtt_bridge `REASON_NAMES`에 205가 있어 직렬화는 된다(`mqtt_bridge/mqtt_bridge/encoders.py:21`) | 계약은 4xx 범위에 하강 제한 코드를 두지 않았고(402 `OUT_OF_WORKSPACE`가 "작업영역 · 하강 한계"), 7.2절은 2차 감시의 코드를 명시하지 않는다 | **부분**(주석상 범위 위반). 계약에 "2차 감시의 DROP_LIMIT은 205"를 적는 쪽이 간단하다 |
| ②-4 | S1 `/robot/stop` 요청 `request_id` | "로컬이면 노드가 생성", 형식 UUID v4(정의서 `:660`, `:1240`) | UUID v4(계약 `:557`) | string | — | safety_monitor `'safety_monitor-{seq}'`(`SM:183-185`), scan_manager 웹 `request_id` 그대로(`SC:1051-1052`) 또는 `'scan_manager-{scan_id}'`(`SC:1292-1293`) | 로컬 발급 ID가 UUID v4가 아니다. safety_monitor의 seq는 프로세스 재시작 시 1부터 다시 시작해 전역 유일성이 없다 | **부분**(ID 규칙) |
| ②-5 | A4 하강 제한 1차 기준 z | 1차 · 2차 "값도 기준 z도 같다", 기준 = operation이 SLIDE로 바뀐 첫 샘플(정의서 `:1099`) | 같음(계약 `:641`) | — | robot_manager 기준 = **goal 실행 시작 시점의 마지막 유효 샘플 z**(operation을 SLIDE로 바꾸기 직전, `RM:423-426`), 감시 `RM:589-594` | safety_monitor 기준 = operation이 SLIDE로 처음 찍힌 샘플 z(`safety_core.py:128-130`) | 두 기준이 **한 샘플 어긋난다.** 그 사이에 순응 · 힘 제어가 켜진다(`RM:479`, `RM:532-546`)는 점에서 정지 상태라도 z가 같다는 보장이 없다 | **부분**. 실기에서 두 기준 z의 차를 로그로 확인해야 한다(미확인) |
| ②-6 | A4 `Result.pose` 미측정 | 미측정값 0 금지(정의서 `:55`) | NaN + `*_valid`(계약 `:19`). 다만 `Result.pose`에는 valid 플래그가 없다 | `pose` · `pose_stamp`만 | 마지막 pose를 모르면 **msg 기본값(0,0,0 · stamp 0)**으로 둔다(`RM:837-839`) | scan_manager가 `pose_stamp==0`을 "없음"으로 해석해 막는다(`scan_manager/scan_manager/conversions.py:123-129`) | 규칙 4(0 금지)를 양쪽의 암묵 약속(stamp 0 = 없음)으로 우회한다. 계약에 없는 규칙이다 | **부분**. 계약에 "pose_stamp 0 = pose 없음"을 적거나 NaN으로 채워야 한다 |
| ②-7 | S2 `/contact/tare` 실패 코드 | `TOOL_REG_SUSPECT` · `SAMPLE_STALE` · `ROBOT_MOVING` · `NO_SAMPLE`(정의서 `:707`) | + `TARE_UNSTABLE` · `TARE_TIMEOUT` · `TARE_FAILED`(계약 `:375`) | 일치 | contact_detector는 `NO_SAMPLE` · `TARE_TIMEOUT` · `TARE_UNSTABLE` · `TOOL_REG_SUSPECT` · 그 밖 `TARE_FAILED`만 낸다(`CD:80-85`, `:307`). **tare 중복 요청에 `BUSY(100)`**를 낸다(`CD:285-289`) — 계약 목록에 없음. `ROBOT_MOVING` · `SAMPLE_STALE`은 내지 않는다 | scan_manager가 호출 전 정지 확인 실패 시 `ROBOT_MOVING`을 **자기 쪽에서** 낸다(`scan_manager/scan_manager/sequence.py:456-457`). 서버 없음은 `TARE_FAILED`, 응답 없음은 `TARE_TIMEOUT`(`SC:1313,1318`) | 코드 발급 주체가 계약 서술("실패 코드" = 서비스 응답)과 다르고 `BUSY`가 추가됐다 | **부분** |
| ②-8 | T3 `detect_stamp` | "contact_detector가 판정을 확정한 시각(지연 실측용)"(정의서 `:369`) | "판정을 확정한 시각 (확정 샘플. 연속 N 번째)"(계약 `:134`, `:151`) | Time | **확정 샘플의 `force_stamp`**를 넣는다(`CD:271`). 노드 시계의 "판정 시각"이 아니다 | — | 계약 v0.1.5 해석(확정 샘플의 값)과는 맞고, 정의서의 "판정 확정 시각(TR-01 판정 지연 실측)"과는 다르다. 노드 처리 지연은 이 값에 안 들어간다 | contracts 기준 **일치** / 정의서 기준 **부분**(정의서가 낡음) |
| ②-9 | mqtt_bridge의 코드 의미 | `NOT_SUPPORTED`=미구현 절차, `ROBOT_ERROR`=드라이버 · 로봇 오류(정의서 `:1173`, `:1179`) | 같음 | — | — | 서버 미기동에 `NOT_SUPPORTED`(`MB:368,407,432,452`), 서비스 호출 예외에 `ROBOT_ERROR`(`MB:377,402,421,444,464`), goal reject를 `BUSY` 고정(`MB:379-386`) | 코드표에 "상대 노드 없음/내부 오류"용 코드가 없어 의미가 다른 코드를 빌려 쓴다 | **부분** |
| ②-10 | S5 해제 로그 | "해제는 `ScanLog`(level=WARN, message='safety latch reset by operator')로 기록"(정의서 `:853`) | 언급 없음 | — | safety_monitor는 rclpy 로그만 남긴다(`SM:211`). `/scan/log` 발행자는 scan_manager뿐(`SC:222`) | — | 정의서 규칙 미구현. contracts가 침묵 | **누락**(정의서 기준) · contracts 기준 해당 없음 |
| ②-11 | `units-frames.md` "robot_manager는 시작할 때와 탐색 전에 현재 툴 · TCP를 확인해야 한다" | BRD 4.1.5 | `docs/contracts/units-frames.md:93` | — | robot_manager에 툴 · TCP 조회 서비스가 없다(`dsr_client.py:24-35`의 10종에 `get_current_tool`/`tcp` 없음) | — | 등록이 휘발성(`sodreal` 재기동 시 삭제)이라는 실측이 있는데 자동 확인이 없다. tare의 `TOOL_REG_SUSPECT`(|F0|>6 N)가 간접 방어 | **누락** |
| ②-12 | `frame_id` 확인 | "좌표를 쓰는 쪽은 `frame_id`를 확인"(계약 `:18`, `units-frames.md:28`) | 같음 | — | robot_manager goal 검사 `RM:413-415` ✔ · scan_manager Result 검사 `SC:1263-1269` ✔ · contact_detector sim 검사 `CD:209-212` ✔ | **safety_monitor는 `frame_id`를 보지 않는다**(`SM:126-133`, grep 0건) | 지금 감시 항목(힘 크기 · z 차이)은 프레임에 덜 민감하지만 `position`을 그대로 `SafetyStatus.position`에 싣는다 | **부분** |

##### ③ 미결 항목의 사실상 결정 (정의서 값 TBD · "(제안)" · contracts 9장 TBD)

| # | 항목 | 정의서 v1.2 / contracts의 상태 | 코드가 정한 것 | 근거 |
|---|---|---|---|---|
| ③-1 | HOME 목표 | 정의서 #19 제안: robot_manager 파라미터 **`home_pose` double[6] m·rad, 값 TBD**(정의서 `:1071`, `:1369`). 계약 5.4 주석도 "파라미터 home_pose"(계약 `:459`) | **`home_joint_deg`**(관절각 6개, **deg**) + `home_speed_deg_s`, `move_joint`로 이동. `units-frames.md:48`은 홈을 관절각으로 정의 → contracts 두 문서끼리 표기가 다르다 | `RM:96-97` · `RM:489-492` · `real.yaml:77-80` |
| ③-2 | Action cancel | 정의서 "goal cancel = `/scan/stop`과 같은 처리(제안)"(정의서 `:867`). contracts 침묵 | scan_manager Action 서버는 **cancel을 REJECT**. 중지는 `/scan/stop` 하나로만 | `SC:258-259` |
| ③-3 | 작업 중지 시 goal cancel 병행 | #21 제안(정의서 `:1371`) → 계약 4.1이 채택(계약 `:359`) | 채택대로 구현: `/robot/stop` 호출 + `cancel_goal_async()` | `SC:1051-1055` — **일치** |
| ③-4 | `RobotStatus.moving` 근거 | 정의서 "[E19] 확인 후 확정"(정의서 `:345`). 계약 본문 3.2는 아직 "TBD"(계약 `:115`), 9장은 "T15에서 정했다"(계약 `:688-694`) | 위치 변화 창(`moving_eps_m` 0.0002 · `moving_window_s` 0.3), 모르면 이동 중 | `RM:84-85`, `RM:258-262`, `RM:317-320` |
| ③-5 | 두산 서비스 실제 이름 | 정의서 "[E19] 실PC 확인 필요"(정의서 `:1288`) | `/dsr01/dsr_controller2/<group>/<name>` 10종, `move_stop(stop_mode=DR_QSTOP=1)`, `set_desired_force(mod=DR_FC_MOD_REL)`, `get_*(ref=DR_BASE)` | `dsr_client.py:14-39`, `:99-114` |
| ③-6 | 해제 실패 시 보고 | 계약 9장 TBD(계약 `:695`) | `compliance_released=false`로 사실대로 보고, `RobotStatus` 플래그는 켜진 채 유지 | `RM:778-808`, `RM:848` |
| ③-7 | 정지 시 `move_stop` → 해제 순서 | 계약 9장 TBD(계약 `:696`) | `move_stop` → 정지 확인 → `release_force(time=0.3)` → sleep → `release_compliance_ctrl` | `RM:752-776`, `RM:784-808` |
| ③-8 | `MAX_DISTANCE` 종료의 `reason_code` | 정의서 · 계약 모두 규정 없음 | robot_manager가 `REASON_MAX_DISTANCE`에 **`NO_CONTACT(300)`/`NO_EDGE(301)`**을 싣고 goal을 `succeed()` 처리. scan_manager도 같은 매핑. `MAX_DISTANCE(202)`는 실제로 발급되지 않는다 | `RM:449-450`, `RM:621-628` · `sequence.py:195-198` |
| ③-9 | `/scan/state` 주기 | 정의서 "제안 2 Hz"(정의서 `:408`) | **1 Hz**(`state_publish_period_s: 1.0`) | `SC:98,177-178` · `sim.yaml:136` · `real.yaml:120` |
| ③-10 | 값이 TBD이던 파라미터의 값 | 정의서 6장 TBD: `slide_target_force_n` · `descend_speed_mps` · `slide_speed_mps` · `max_descend_m` · `max_slide_m` · `motion_timeout_s` · `recontact_speed_mps` · `tare_max_force_n` · `robot_status_timeout_ms` · `cmd_expiry_s` · `sim_box_*` · `result_dir` · `search_origin_pose` · `base_to_fixture`. 계약 9장도 하강 속도 · 누름 힘 · `recontact_*` 값 TBD(계약 `:686-687`) | yaml에 출발값이 들어갔다(§7). 계약 9장 TBD 문구는 갱신되지 않았다. `real.yaml`은 `search_origin_pose` · `base_to_fixture`를 **일부러 꺼 둬** START가 거절된다(fail-safe) | `real.yaml:82,133-147,155-158` · `sim.yaml:101,140-156` |
| ③-11 | Resume 재접근 | TBD → `NOT_SUPPORTED` 거절(정의서 `:955`, 계약 `:451`) | 기록에 남기지 못한 안전복귀 뒤 재시작을 `NOT_SUPPORTED`로 거절 | `SC:938-942` — **일치** |
| ③-12 | HB 만료 조치 | 계약 9장 TBD(계약 `:698`) | 구현 없음(①-1) | `SM:41-52` |

##### ④ 문서만 낡은 것

| # | 문서 | 낡은 내용 | 실제(코드 · 다른 계약) | 근거 |
|---|---|---|---|---|
| ④-1 | 계약 머리말 | 출처 "정의서 통합본 v1.1" | 저장소에는 v1.2만 있다. CHANGELOG도 "정의서 v1.2에 반영 요청"까지만 적혀 있다 | 계약 `:5` · `docs/contracts/CHANGELOG.md:113` |
| ④-2 | 계약 5.4 주석 | `OP_HOME # 홈위치(파라미터 home_pose)` | 파라미터는 `home_joint_deg`(③-1). 같은 주석이 패키지 `.action`에도 복사돼 있다 | 계약 `:459` · `contact_scan_interfaces/action/ExecuteMotion.action`(OP_HOME 줄) |
| ④-3 | 계약 3.2 | "`moving`의 근거는 TBD(실PC 확인)" | 9장은 "T15에서 정했다"(본문과 9장이 서로 다름) | 계약 `:115` vs `:688-694` |
| ④-4 | 계약 9장 TBD | 하강 속도 · 누름 목표 힘 · `recontact_*` **값** TBD | yaml에 값이 있다(③-10). "출발값이 들어갔고 확정은 T24/T25"로 고쳐야 한다 | 계약 `:686` · `real.yaml:82,133,143,146` |
| ④-5 | 정의서 4.1 · 4.2 · 3.7 **필드 표** | `StopRobot`/`StopScan` 표에 `requester` 없음, `TareForce` 응답 표에 `baseline_norm_n` · `std_norm_n` 없음, `SafetyStatus` 표에 `stop_confirmed` · `motion_id` · `position` · `position_valid` 없음 | 같은 절의 코드 블록과 패키지에는 있다(정의서 안에서 표와 코드 블록이 어긋남) | 정의서 `:656-662` vs `:675` · `:703-709` vs `:721-722` · `:586-593` vs `:605-609` |
| ④-6 | 정의서 6.4 | `base_to_fixture` double[6] m·rad · `search_origin_pose` double[6] m·rad | 코드: `base_to_fixture` **3원소(평행 이동만)** · `search_origin_pose` **7원소(x y z + quaternion)**. `units-frames.md:42,49`(v0.1.6 · v0.1.11)와 코드가 맞고 정의서가 낡았다 | 정의서 `:1123,1125` · `scan_manager/scan_manager/params.py:102-105` |
| ④-7 | 정의서 6.4 | `tip_radius_m` 0.003 · `detect_latency_s` 0.040 | yaml 0.000225(실측, `units-frames.md:50`) · 0.020(설계 출발값) | 정의서 `:1120-1121` · `real.yaml:162,168` |
| ④-8 | 정의서 2.5 · 6장 파라미터 목록 | §7의 "정의서에만 있음" 항목 전부(예: `mode` · `dsr_model` · `filter_window` · `edge_force_drop_ratio` · `max_speed_mps` · `workspace_*` · `latch_levels` · `allow_concurrent` · `topic_map_file` · `qos_default` · `client_id`) | 코드에 없다. 정의서가 "그 밖은 담당자 재량"이라 했으므로 계약 위반은 아니고 목록이 낡은 것이다 | 정의서 `:1061` · §7 |
| ④-9 | 정의서 1.7 · 3.4 | safety_monitor가 `/scan/state`로 "단계별 한계"를 본다 | operation 기반(①-2). 정의서 6.3 자체도 v1.2에서 operation 기준으로 바뀌어 **정의서 내부에서 1.7절과 6.3절이 어긋난다** | 정의서 `:158`, `:407` vs `:1099` |
| ④-10 | `real.yaml` 주석 | `descend_speed_mps` 등을 "TBD"로 적은 주석 블록과 `move_speed_mps` · `recontact_speed_mps` · `detect_latency_s`의 주석 처리된 "TBD" 줄이 남아 있는데, 바로 아래 · 위에 실제 값이 있다 | 값은 들어가 있다. "TBD로 남긴 항목을 채우기 전에는 START가 거절된다"는 문구는 이제 좌표 2개에만 해당 | `ws_cobot1/src/contact_scan_bringup/config/real.yaml:123-131` vs `:133-147`, `:145,147,169` |
| ④-11 | `sim.yaml`/`real.yaml` 끝 | `# mqtt_bridge: # (병후)` 빈 절. 계약 CHANGELOG는 담당을 의석으로 고쳤다 | mqtt_bridge 절 미작성(§7.5) | `real.yaml:186-187` · `docs/contracts/CHANGELOG.md:34` |

##### ⑤ 일치로 확인한 것 (요약)

| 인터페이스 | 확인 내용 | 근거 |
|---|---|---|
| T1 | 필드 전부 채움, 실패값 NaN + `valid=false`, `motion_id`/`operation`을 goal 수락~Result 사이에 직접 찍음, `sample_id` +1(첫 값 1) | `RM:268-302`, `RM:426,442` |
| T2 | 기동 직후 1회 + 변경 시 + 주기(10 Hz), `compliance_active` · `force_ctrl_active` 분리 | `RM:157,159,317-342` |
| T3 | 판정 모드 = 샘플의 `operation`(DESCEND→CONTACT, SLIDE→EDGE), OVER_FORCE는 전 모드, 첫 샘플/확정 샘플 필드 배정(v0.1.5), `z_drop_m` NaN, `source`, `event_id` +1, `/scan/state`는 `scan_id` 태깅만 | `contact_detector/contact_detector/detector_core.py:248,266` · `CD:181-182`, `CD:251-274` |
| T3 → robot_manager 대조 규칙 | `motion_id` 0/불일치 · 동작 불일치는 무시 + 로그, OVER_FORCE는 대조 없이 정지 | `RM:345-363` |
| T4/T5/T6 | STATE/LOG QoS, 변경 시 + 주기, 결과는 GEOMETRY 직후 발행, `stamp` 새로 찍음 | `SC:220-222`, `SC:272`, `scan_manager/scan_manager/conversions.py:226` |
| T5 중복 방지 | mqtt_bridge 키 = `(scan_id, stamp)`(계약 7.4 v0.1.9와 일치. 정의서는 `scan_id`만 — 정의서가 낡음) | `MB:164-166`, `MB:510-517` · 계약 `:672` · 정의서 `:459` |
| T7 | 기동 1회 + 변경 시 + 1 Hz, 래치는 reset으로만 해제, position NaN 처리 | `SM:88,92`, `SM:205-213`, `SM:232-236` |
| S1 | 접수 ≠ 완료, 멱등, 미연결이면 `accepted=false` + `ROBOT_DISCONNECTED`, 자동 상승 · 홈 없음 | `RM:671-707` |
| S3 | 작업 없어도 접수, `/robot/stop` + goal cancel 병행, 홈 · 재시작 안 부름, mqtt_bridge가 `PHASE_STOPPED`에서 `command_result` | `SC:1029-1065` · `MB:417-427`, `MB:501-508` |
| S4 | 동작 중 판정 = phase ∉ {IDLE, DONE, ERROR, STOPPED}, `PARAM_SET_FAILED`, `applied`는 되읽은 실제 값 | `scan_manager/scan_manager/state_machine.py:53-54,83` · `SC:1090-1150` |
| P01~P03 | `target_force_n`→`slide_target_force_n`, 쌍 검사(`over_force_n` · `drop_limit_m`), 순서 P03→P02→P01 | `scan_manager/scan_manager/propagation.py:40-60` |
| S5 | 조건 미해소 `CONDITION_ACTIVE`, 멱등, 로봇 안 움직임 | `SM:205-213` |
| A4 | 동시 1개, SLIDE는 try/finally 해제, Feedback 10 Hz(`feedback_period_s` 0.1), `OP_MOVE_TO` 프레임 검사 | `RM:366-384`, `RM:433-446`, `RM:101`, `RM:413-415` |
| ID | `scan_id` = `%Y%m%d-%H%M%S-%04d`, `motion_id` 1부터(재시작 · 안전복귀는 이어서 발급) | `SC:131-133` · `scan_manager/scan_manager/sequence.py:328-336` · `SC:1221` |
| 단위 변환 경계 | 두산 mm·deg ↔ m·quaternion은 robot_manager만(`dsr_client.py:82-91`, `robot_manager/robot_manager/conversions.py`), mm 변환은 mqtt_bridge 인코더만(`mqtt_bridge/mqtt_bridge/encoders.py:74-79`) | |

---

#### 7. 파라미터 3자 대조 (정의서 6장 · 코드 `declare_parameter` · bringup yaml)

표기: `—` = 없음, `(필수)` = 코드 기본값 없이 선언해 yaml에 없으면 기동 실패 또는 START 거절. yaml 경로는 `ws_cobot1/src/contact_scan_bringup/config/`.

##### 7.1 robot_manager
| 파라미터 | 정의서 6.1 (단위 · 출발값) | 코드 기본값 (`RM` 줄) | sim.yaml | real.yaml | 판정 |
|---|---|---|---|---|---|
| `slide_target_force_n` ★ | N · TBD | (필수) `:92` | 3.0 `:101` | 3.0 `:82` | 이름 일치 · 값은 사실상 결정(③-10) |
| `drop_limit_m` ★ | m · 0.005 | (필수) `:93` | 0.005 `:100` | 0.005 `:81` | 일치 |
| `sample_rate_hz` | Hz · 50 | 50.0 `:79` | 50.0 `:128` | 50.0 `:109` | 일치 |
| `status_rate_hz` | Hz · 10 | 10.0 `:80` | 10.0 `:129` | 10.0 `:110` | 일치 |
| `home_pose` | double[6] m·rad · TBD | **—** (대신 `home_joint_deg` deg `:96`, `home_speed_deg_s` 20.0 `:97`) | 관절각 `:95`, 30.0 `:99` | 관절각 `:77`, 20.0 `:80` | 사실상 결정(③-1). **단위가 deg** — 두산 경계 노드라 규칙 위반은 아니나 이름 접미사로만 구분된다 |
| `frame_id` | `base_link` | `'base_link'` `:77` | `:126` | `:107` | 일치 |
| `dsr_namespace` | `dsr01` | `'dsr01'` `:78` | `:127` | `:108` | 일치 |
| `dsr_model` · `mode` | `m0609` · `real\|virtual` | — | — | — | 정의서에만 있음(④-8) |
| `rg2_grip_width_m` · `rg2_grip_force_n` | m · N · TBD | — | — | — | 누락(①-3) |
| `stop_timeout_s` | s · 1.0 | — (유사: `stop_settle_s` **1.5** `:100`) | — | — | 이름 · 값 다름. **yaml에 없어 코드 기본값 1.5로 돈다** |
| 코드에만 있음 | — | `service_timeout_s` 0.5 `:81` · `moving_eps_m` 0.0002 `:84` · `moving_window_s` 0.3 `:85` · `compliance_stiffness` (필수) `:98` · `motion_timeout_s` 60.0 `:99` · `feedback_period_s` 0.1 `:101` · `arrival_grace_s` 1.0 `:103` · `arrival_tolerance_m` (필수) `:105` · `release_force_time_s` 0.3 `:108` | 대부분 있음. **`motion_timeout_s` · `stop_settle_s` · `feedback_period_s`는 두 yaml 모두에 없다** | 같음 | 부분(규칙 7: 수치 기본값이 코드에 있음). 추가로 상수 `LOOP_PERIOD_S = 0.02`(`RM:40`)와 가속도 계수 `acc = 4×vel`(`dsr_client.py:89`) · `2×vel`(`:95`)이 코드에 박혀 있다 |

##### 7.2 contact_detector (코드 기본값 없음 — 전부 필수, `CD:52-78`, `CD:143-147`)
| 파라미터 | 정의서 6.2 | sim.yaml | real.yaml | 판정 |
|---|---|---|---|---|
| `source` | `robot_force\|sim` | sim `:11` | robot_force `:13` | 일치 |
| `contact_threshold_n` ★ | 4.0 (3~5) | 3.0 `:12` | 3.0 `:14` | 이름 일치 · 값 다름(yaml 주석이 사유를 적음) |
| `edge_drop_m` ★ | 0.0005 | 0.0005 `:16` | 0.0005 `:18` | 일치 |
| `debounce_n` ★ | 3 | 3 `:19` | 3 `:21` | 일치 |
| `over_force_n` ★ | 30 | 30.0 `:20` | 30.0 `:22` | 일치 |
| `tare_duration_s` | 1.5 | 1.5 `:39` | 1.5 `:38` | 일치 |
| `tare_max_force_n` | TBD | 6.0 `:42` | 6.0 `:41` | 사실상 결정 |
| `stale_age_ms` | 100 | **200** `:31` | 100 `:33` | sim만 다름(계약 6.3 실측 97.7 ms 근거) |
| `edge_force_drop_ratio` · `filter_window` | TBD | — | — | 정의서에만 있음 |
| `sim_box_size_m` · `sim_box_origin_m` | TBD | [0.10,0.06,0.04] `:54` · [0.425,-0.184,0.400] `:50` | — | 사실상 결정 |
| 코드에만 있음 | — | `over_force_debounce_n` 1 · `edge_arm_force_n` 1.5 · `edge_trend_window_s` 0.5 · `edge_trend_min_samples` 10 · `tare_min_samples` 30 · `tare_max_std_n` 0.3 · `sim_box_frame_id` · `sim_stiffness_n_per_m` · `sim_tip_radius_m` · `sim_fall_speed_mps` · `sim_slide_press_n` | sim_* 제외 같음 | 담당자 재량. 상수 `KEPT_MESSAGES=256` · `WARN_PERIOD_S=2.0`(`CD:49-50`)은 튜닝 값이 아니다 |

##### 7.3 safety_monitor (코드 기본값 없음 — 전부 필수, `SM:41-52`, `SM:96-100`)
| 파라미터 | 정의서 6.3 | sim.yaml | real.yaml | 판정 |
|---|---|---|---|---|
| `over_force_n` ★ | 30 | 30.0 `:69` | 30.0 `:49` | 일치(contact_detector와 같은 값) |
| `drop_limit_m` ★ | 0.005 | 0.005 `:70` | 0.005 `:50` | 일치(robot_manager와 같은 값) |
| `sample_stale_ms` | 100 | **500** `:79` | **300** `:59` | 이름 일치 · 값 다름(계약 6.3 v0.1.10이 300을 기준으로 논의) |
| `robot_status_timeout_ms` | TBD | 1000 `:81` | 500 `:63` | 사실상 결정 |
| `max_speed_mps` · `workspace_min_m` · `workspace_max_m` · `max_descend_m` | TBD | — | — | **누락**: `OVER_SPEED(401)` · `OUT_OF_WORKSPACE(402)` 감시 미구현(§8.2) |
| `hb_timeout_s` · `hb_expired_action` | TBD · `warn\|stop` | — | — | **누락**(①-1) |
| `latch_levels` | `["STOP"]` | — | — | 정의서에만 있음(래치는 코드 고정) |
| 코드에만 있음 | — | `confirm_n` 1 · `startup_grace_s` 3.0 · `stop_confirm_timeout_s` 0.6 · `stop_retry_period_s` 2.0 · `status_publish_period_s` 1.0 · `check_period_s` 0.05 | 같음 | 담당자 재량 |

##### 7.4 scan_manager (`scan_manager/scan_manager/params.py:90-121`, 수치 기본값 없음)
| 파라미터 | 정의서 6.4 | 코드 | sim.yaml | real.yaml | 판정 |
|---|---|---|---|---|---|
| `descend_speed_mps` ★ | TBD | 필수 | 0.005 `:140` | 0.003 `:133` | 이름 일치 · 값 사실상 결정 |
| `slide_speed_mps` ★ | TBD(예 0.010) | 필수 | 0.010 `:141` | 0.005 `:135` | 같음 |
| `max_descend_m` ★ | TBD | 필수 | 0.080 `:142` | 0.120 `:136` | 같음 |
| `max_slide_m` ★ | TBD | 필수 | 0.080 `:144` | 0.060 `:140` | 같음 |
| `motion_timeout_s` ★ | TBD | 필수 | 30.0 `:145` | 60.0 `:141` | 같음 |
| `lift_height_m` ★ | 0.05 | 필수 | 0.05 `:146` | 0.05 `:144` | 일치 |
| `recontact_margin_m` | 0.001 | 필수 | 0.001 `:149` | 0.001 `:146` | 일치 |
| `recontact_speed_mps` | TBD | 필수 | 0.005 `:151` | 0.002 `:143` | 사실상 결정 |
| `tip_radius_m` | 0.003 | 필수 | 0.000225 `:158` | 0.000225 `:168` | 정의서 낡음(④-7) |
| `detect_latency_s` | 0.040 | 필수 | 0.020 `:160` | 0.020 `:162` | 정의서 낡음 |
| `result_frame_id` | `workpiece_fixture` | 기본 `'workpiece_fixture'` `params.py:115-116` | `:175` | `:179` | 일치 |
| `base_to_fixture` | double[6] m·rad | **3원소** `params.py:104-105` | `:156` | 꺼 둠 `:158` | 정의서 낡음(④-6) |
| `search_origin_pose` | double[6] m·rad | **7원소(quaternion)** `params.py:102-103` | `:152` | 꺼 둠 `:155` | 정의서 낡음 |
| `support_z_m` | 0.0 | 필수 | 0.0 `:157` | 0.0 `:161` | 일치 |
| `result_dir` | TBD | 필수 | data `:173` | data `:177` | 사실상 결정 |
| `allow_concurrent` | false | — | — | — | 정의서에만 있음(동시 작업 금지는 상태 기계 고정) |
| 코드에만 있음 | — | `move_speed_mps`(계약 6.4에 등재, 계약 `:624`) · `edge_round_radius_m` · `edge_bias_offset_m` · `event_wait_timeout_s` · `stop_confirm_timeout_s` · `server_wait_timeout_s` · `motion_frame_id`(`'base_link'`) · `direction_order` · `state_publish_period_s`(코드 기본 1.0 `SC:98`) | 모두 있음 | 모두 있음 | 담당자 재량 |

##### 7.5 mqtt_bridge (`MB:173-179`, **전부 코드 기본값**)
| 파라미터 | 정의서 6.5 | 코드 기본값 | bringup yaml | `mqtt_bridge/config/mqtt_bridge.yaml` | 판정 |
|---|---|---|---|---|---|
| `broker_host` · `broker_port` | TBD(웹 PC) | `127.0.0.1` · 1883 | **절 없음**(`sim.yaml` · `real.yaml` 끝의 주석뿐) | 127.0.0.1 · 1883 `:3-4` | **부분/위험**: bringup은 `sim.yaml`/`real.yaml`만 넘긴다(`bringup.launch.py:62`). 패키지 자체 yaml은 설치만 되고(`mqtt_bridge/setup.py:12`) 로드되지 않는다. 메인 PC ↔ 웹 PC 분리 배치에서 bringup으로 띄우면 **localhost 브로커에 붙는다**. `backend/app/README.md:143`은 `broker_host = <Web PC 주소>`를 요구한다 |
| `client_id` | `mqtt_bridge` | 파라미터 없음. `f"mqtt_bridge-{pid}"` 하드코딩 `MB:250` | — | — | 불일치(이름 없음) |
| `topic_map_file` | TBD | — | — | — | 정의서에만 있음(토픽 매핑 코드 고정) |
| `downsample_hz` | 10 | **`sample_publish_hz`** 10.0 | — | 10.0 `:8` | 이름 다름 |
| `hb_ros_hz` | 1 | **`heartbeat_hz`** 1.0 | — | 1.0 `:9` | 이름 다름 |
| `cmd_expiry_s` | TBD | 5.0 | — | 5.0 `:7` | 사실상 결정(`mqtt-schema.md:68` "출발값 5"와 일치) |
| `qos_default` | 1 | — (토픽별 QoS 하드코딩 `MB:479-572`) | — | — | 정의서에만 있음(`mqtt-schema.md` 표를 따름) |
| 코드에만 있음 | — | `topic_prefix` "" · `dedup_cache_size` 100 · `keepalive_s` 60 · 큐 드레인 주기 0.02 하드코딩 `MB:247` | — | 있음 | 담당자 재량 |

계약 이름(계약 6.4, 14개) 요약: robot_manager 2 · contact_detector 4 · safety_monitor 2 · scan_manager 6 — **코드 선언명 · yaml 키 · 전파 표(`propagation.py:40-54`)가 전부 일치**한다.

---

#### 8. enum · 상수 · 사유 코드 · ID

##### 8.1 enum/상수 사본
| 위치 | 내용 | msg 상수와 대조 | 검증 수단 |
|---|---|---|---|
| `scan_manager/scan_manager/contract_enums.py:13-104` | Phase · Direction · Operation · MotionReason · Reason 전체 | 값 전부 일치(눈 대조) | `scan_manager/test/test_contract_match.py`가 CI에서 비교 |
| `contact_detector/contact_detector/detector_core.py:27-36` | `OP_*` 5개 · `TYPE_*` 3개 | 일치 | 직접 비교 테스트는 없으나 노드 테스트가 msg 상수(`RobotSample.OP_DESCEND` · `ContactEvent.TYPE_EDGE`)로 코어를 구동해 간접 검증한다(`contact_detector/test/test_node.py:121-147`) |
| `safety_monitor/safety_monitor/safety_core.py:23-24` | `OP_NONE=0` · `OP_SLIDE=3` | 일치 | 간접 검증: 노드 테스트가 `RobotSample.OP_SLIDE`로 구동(`safety_monitor/test/test_node.py:82,155-158`) |
| `mqtt_bridge/mqtt_bridge/encoders.py:12-37` | OP · REASON(33개) · PHASE · DIR · TYPE · LEVEL 이름표 | 값 · 이름 전부 일치 | 표에 없는 값이 오면 `ValueError`(`encoders.py:40-43`) → 콜백이 삼키고 그 메시지는 MQTT로 안 나간다(`MB:152-161`). ReasonCode를 추가할 때 이 표를 같이 안 고치면 **해당 상태가 웹에서 사라진다** |
| `mqtt_bridge/mqtt_bridge/command_guard.py:10-11` | 101 · 106 | 일치 | — |

##### 8.2 사유 코드 사용 현황 (테스트 · 사본 파일 제외 grep)
| 코드 | 발급 주체 | 판정 |
|---|---|---|
| 100~108 | scan_manager(100 · 102~105 · 107 · 108) · mqtt_bridge(100 · 101 · 106 · 107) · robot_manager(102 · 104 로그/응답) · contact_detector(100) | 일치. 단 mqtt_bridge의 107 · 204 전용(②-9), contact_detector의 100(②-7) |
| 200 · 201 · 203 · 204 · 205 | robot_manager · scan_manager · safety_monitor(205) | 일치 / 205의 SafetyStatus 사용은 ②-3 |
| **202 `MAX_DISTANCE`** | **발급처 없음**(robot_manager는 300/301을 싣는다, ③-8) | 부분 — 코드표에 있으나 실제로 쓰이지 않는다 |
| 300 · 301 | robot_manager(`RM:624-628`) · scan_manager(`sequence.py:195-198`) | 일치 |
| 302 · 303 · 305 · 306 · 307 | contact_detector(`CD:80-85,307`) · scan_manager(303 · 306) | 일치 |
| 304 `ROBOT_MOVING` | scan_manager만(`sequence.py:457`) | 부분(②-7) |
| 400 · 403 · 404 · 406 | safety_monitor(`SM:55-60`, `:209`) · robot_manager(400) · scan_manager(404) | 일치 |
| **401 `OVER_SPEED` · 402 `OUT_OF_WORKSPACE` · 405 `HB_EXPIRED`** | **발급처 없음** | **누락** — 정의서 1.7이 나열한 감시 6종 중 속도 · 작업영역/하강 한계 · HB 3종이 미구현(`SM:41-61`). BRD 4.6 · 4.5.3 대비는 Phase 다른 감사 범위 |
| 500 · 501 | scan_manager | 일치 |

##### 8.3 ID 규칙
| ID | 계약 | 코드 | 판정 |
|---|---|---|---|
| `request_id` | UUID v4, mqtt_bridge가 중복 · 만료 거절 | 웹 값 그대로 전달(`MB:336-350`), 중복 106 · 만료 101(`command_guard.py:60-100`). 로컬 발급은 UUID 아님(②-4) | 부분 |
| `scan_id` | `YYYYMMDD-HHMMSS-xxxx` | `SC:131-133`(벽시계 + 난수 4자리, 충돌 시 재발급 `SC:732-733`) | 일치 |
| `motion_id` | scan 안에서 1부터, 0=없음 | `sequence.py:328-336`, 재시작 · 안전복귀는 이어서 발급(`SC:1221`) | 일치 |
| `sample_id` | 발행마다 +1, 0=미발급 | `RM:268-270` | 일치 |
| `event_id` | 발행마다 +1, 0=없음 | `CD:254-256` | 일치 |
| `session_id` | FastAPI UUID | `hb/web`의 값을 그대로 `WebHeartbeat.session_id`에(`MB:315`) | 일치(받는 노드가 없음, ①-1) |

---

#### 9. 미확인 항목과 확인 방법

| # | 미확인 | 확인 방법 |
|---|---|---|
| U1 | RG2 탐침 파지를 수동으로 확정했는지(①-3) | `docs/decisions/` · `docs/env/tool-tcp-register.md` · 이슈 검색 |
| U2 | 1차 · 2차 하강 제한 기준 z의 실제 차(②-5) | SLIDE 시작 시 robot_manager `start_z` 로그와 safety_monitor `slide_start_z`를 같은 세션에서 비교(Virtual 가능) |
| U3 | contact_detector · safety_monitor의 enum 사본에는 scan_manager의 `test_contract_match.py` 같은 **직접** 비교 테스트가 없다(간접 검증만 확인, §8.1). `OP_MOVE_TO` · `OP_HOME` · `TYPE_OVER_FORCE`처럼 노드 테스트가 안 쓰는 값까지 덮이는지는 미확인 | 두 패키지 `test/`에 msg 상수 전수 비교 테스트를 추가하면 닫힌다 |
| U4 | 실제 DDS 매칭(런타임 `ros2 topic info -v`) | 이 감사는 정적 분석만 했다. 저녁 통합(사람 실행)에서 `ros2 topic info -v /web/heartbeat` 등으로 구독자 수 0을 확인하면 ①-1이 실증된다 |
| U5 | mqtt_bridge를 분리 배치에서 어떤 방법으로 띄우는지(§7.5) | `docs/` 통합 절차 · `daily-integration` 스킬 · 실제 launch 명령 기록 |

#### 10. 후속 조치 후보 (읽기 전용 감사이므로 제안만)

1. **계약 PR 1건(문서만)**: ②-1(goal 항상 accept → 계약 5.1~5.3 · mqtt-schema 문구), ②-3(205 사용 명시), ②-6(`pose_stamp=0` = pose 없음), ④-1~④-4, ③-8(MAX_DISTANCE의 reason_code 매핑)을 계약 · CHANGELOG에 반영. 타입 변경 없음.
2. **safety_monitor 이슈**: `/web/heartbeat` 구독(만료 조치는 TBD라도 최소 `warn`), 연결 표의 `/scan/state` 구독을 유지할지 삭제할지 결정, `frame_id` 확인.
3. **bringup 이슈**: `sim.yaml`/`real.yaml`에 `mqtt_bridge:` 절 추가(`broker_host` 등), robot_manager의 `motion_timeout_s` · `stop_settle_s` · `feedback_period_s`를 yaml로.
4. **robot_manager 이슈 초안**: `RobotStatus.error`/`error_code` 채우기, 툴 · TCP 확인(②-11), 하강 제한 기준 z를 "OP_SLIDE 첫 샘플"로 맞추기(②-5).
5. **정의서 v1.3**: ④-5~④-9 정리(필드 표, 6장 파라미터 목록, 1.7절).


---

## 부록 B. MQTT·웹 계약 대조

### Phase 3 — MQTT·웹 구간 계약 대조 + 미측정값 유효성 전 구간 추적

- 대상 스냅샷: origin/main `717cbdd` (읽기 전용). 경로는 전부 저장소 루트 기준 상대경로.
- 기준 문서: 정의서 `docs/design/contact-scan-interface-spec-integrated-v1.2.md` 12장 · 7.1~7.3 · 7.5 · 11장 · 13장 / 동결 계약 `docs/contracts/mqtt-schema.md` · `units-frames.md` · `CHANGELOG.md`
- 판정 등급: `일치` · `부분` · `불일치` · `누락` · `미결 항목의 사실상 결정`(정의서 10장 TBD) · `범위 초과`(검토안 구현)
- 검증 방법: 코드 정독 + 읽기 전용 스크립트로 `mqtt_bridge/encoders.py` 출력 키와 `mock_publisher` 발행 키를 `mqtt-schema.md` 4장 JSON 예시 키와 기계 대조(저장소 파일은 건드리지 않음, `PYTHONDONTWRITEBYTECODE=1`).

---

#### 0. 요약 (심각도 순)

| # | 발견 | 등급 | 근거 |
|---|---|---|---|
| A | **React가 `scan/result`를 전혀 읽지 않는다.** 3D 직육면체는 고정 크기 목업 `BoxGeometry(2,1,1.2)`이고 꼭짓점·엣지·경로 후보·치수 표시 코드가 없다. M4 "결과 → 3D 직육면체 표시"는 **React 수신 분기에서 끊긴다** | 누락 (M4 차단) | `frontend/src/App.jsx:380-493`(수신 분기에 `scan/result` 없음), `frontend/src/App.jsx:598-616`(고정 목업 상자) |
| B | **FastAPI가 `hb/web` · `conn/web`(LWT)을 발행하지 않는다.** mqtt_bridge는 받을 준비가 돼 있으나 발행 측이 없다 → `/web/heartbeat`가 한 번도 나가지 않는다. main의 safety_monitor는 아직 heartbeat를 보지 않아(T33 미완) 지금은 무해하지만, T33이 들어오면 `HB_EXPIRED` 래치로 시작이 막힌다 | 누락 | 발행 코드 없음: `backend/app/main.py` 전체(`publish`는 `main.py:411`, `main.py:540` 둘뿐) / 구독 측 `ws_cobot1/src/mqtt_bridge/mqtt_bridge/mqtt_bridge.py:284-285, 312-324` / safety_monitor에 heartbeat 구독 없음(`ws_cobot1/src/safety_monitor/` grep 0건) |
| C | **웹 UI에 안전 해제·설정 등록 버튼이 없다.** 정의서 13.3은 4버튼 + 설정 등록 + 안전 해제. React는 4버튼뿐. 래치가 걸리면 웹에서 풀 방법이 없다(REST는 있음). `safety/status` · `robot/status` · `hb/ros` · `conn/ros`도 React가 읽지 않는다 | 누락 | `frontend/src/App.jsx:828-846`(버튼 4개), `frontend/src/App.jsx:49-66`, REST는 `backend/app/main.py:491-508` |
| D | **거절이 "접수 후 실패"로 웹에 나간다.** scan_manager가 goal을 항상 ACCEPT하고 Result로 1xx를 돌려주므로, `SAFETY_LATCHED` · `BUSY` · `NO_RESUMABLE_SCAN`이 `cmd/ack accepted=true` → `scan/command_result success=false`로 보인다. 계약 예시(`cmd/ack accepted=false, 103`)와 다르다 | 부분 | `ws_cobot1/src/scan_manager/scan_manager/scan_manager.py:257, 612-628` / `ws_cobot1/src/mqtt_bridge/mqtt_bridge/mqtt_bridge.py:373-389` / 계약 `docs/contracts/mqtt-schema.md:183-194` |
| E | **멈출 작업이 없을 때의 stop은 `command_result`가 영영 안 나간다.** scan_manager는 IDLE/DONE/ERROR에서도 stop을 접수(phase 불변)하고, mqtt_bridge는 `STOPPED` 전이만 기다린다. 남은 request_id는 다음번 다른 작업의 STOPPED 때 엉뚱한 `scan_id`로 완료 처리된다. FastAPI에 ack/결과 대기 timeout("미확정")도 없다 | 부분 | `ws_cobot1/src/scan_manager/scan_manager/state_machine.py:84-88, 246` / `mqtt_bridge.py:424-427, 504-508` / `backend/app/main.py:103-194`(timeout 없음) / 계약 `mqtt-schema.md:81` |
| F | **`debounce_n` 미지값이 0으로 나간다.** `uint8`이라 NaN을 못 싣고 `debounce_set=false`로만 구분하는데, mqtt_bridge가 `*_set`을 읽지 않아 `scan/result.config.debounce_n` · `cmd/ack.applied.debounce_n`이 `0`이 된다(실행 확인). 그대로 `scan_configs.config` JSONB에 저장된다 | 불일치 (TR-10, 설정값 한정) | `ws_cobot1/src/scan_manager/scan_manager/conversions.py:171-185` / `mqtt_bridge.py:91-105` / `encoders.py:223` / 계약 `mqtt-schema.md:31` |
| G | bringup이 mqtt_bridge 파라미터를 넣지 않는다. `sim.yaml` · `real.yaml`의 `mqtt_bridge:` 절이 주석이고, 패키지의 `config/mqtt_bridge.yaml`은 launch에서 읽히지 않는다 → `broker_host` 기본 `127.0.0.1`(코드 기본값). 웹 PC가 다른 기기면 수동 `-p`가 필요하다(규칙 7 위반 소지: 기본값이 코드에 있음) | 부분 | `ws_cobot1/src/contact_scan_bringup/config/sim.yaml:182-183`, `real.yaml:186-187`, `launch/bringup.launch.py:47-63`, `mqtt_bridge.py:173-179` |
| H | React 3D 축 매핑이 거울상이다. ROS (x,y,z) → three (x, z, y)는 두 축 교환이라 좌표계 손잡이가 뒤집힌다(올바른 회전은 (x, z, −y)). 팁·궤적·접촉점이 실제와 좌우 반전으로 보인다 | 관찰 | `frontend/src/App.jsx:725-729, 750-756, 805-809` |
| I | Spring Boot(T35) · T36은 main과 원격 브랜치 모두 **미구현**. `origin/euiseok/20260921-t35-spring-history`는 main의 조상 커밋(`d5c869a`)을 가리키며 고유 커밋 0개 | 누락 | 6장 참조 |
| J | 새로 접속한 브라우저는 최신 상태를 못 받는다. FastAPI가 retain 상태를 캐시·재전송하지 않아 React는 `phase='IDLE'` 기본값을 "대기"로 표시한다(모르는 상태를 정상값으로 표시) | 부분 | `backend/app/main.py:353-377`(접속 시 스냅샷 전송 없음), `frontend/src/App.jsx:156` |

토픽 이름·JSON 키가 발행 측과 구독 측에서 **서로 달라 연결이 안 되는** 경우는 **없다**(전 토픽 19개 이름 일치, 키는 기계 대조로 일치). "연결 자체가 안 되는" 경우는 전부 **한쪽이 아예 없는** 형태다(A, B, C).

---

#### 1. MQTT 드리프트 표

열 약어: BR = `ws_cobot1/src/mqtt_bridge/mqtt_bridge/mqtt_bridge.py`, ENC = `.../encoders.py`, DEC = `.../decoders.py`, GRD = `.../command_guard.py`, API = `backend/app/main.py`, DB = `backend/app/db.py`, FE = `frontend/src/App.jsx`, MOCK = `backend/mock_publisher/mock_publisher.py`, 계약 = `docs/contracts/mqtt-schema.md`, 정의서 = `docs/design/contact-scan-interface-spec-integrated-v1.2.md`

##### 1.1 한쪽 끝이 없는 토픽 (최상단: 연결이 성립하지 않음)

| 토픽 | 정의서 12장 | 계약 | mqtt_bridge | FastAPI | React/WS | mock | 차이 | 판정 |
|---|---|---|---|---|---|---|---|---|
| `hb/web` | 정의서:1456 (FastAPI 1 Hz) | 계약:43, 165-173 (QoS0, retain F) | 구독 BR:284, 처리 BR:312-320, 검사 DEC:118-136 | **발행 없음** | — | 없음 | 발행자 부재. `/web/heartbeat` 미발행 | **누락** |
| `conn/web` | 정의서:1457 (LWT) | 계약:44, 175-179 (QoS1, retain T) | 구독 BR:285, 검사만 BR:322-324 | **발행·LWT 없음** (`will_set` 없음, API:41-43) | — | 없음 | 발행자 부재 | **누락** |
| `scan/result` | 정의서:1463 | 계약:50, 314-425 | 발행 BR:510-517 (QoS1, retain F), ENC:253-295 | 수신·WS 전달 API:227-230, DB 저장 API:233-247 | **FE 수신 분기 없음** (FE:380-493) | MOCK:189-371 | 소비자(React) 부재. 3D 직육면체·엣지·경로 후보 미표시 | **누락 (M4 차단)** |
| `safety/status` | 정의서:1466 | 계약:53, 447-464 | 발행 BR:544-552 (QoS1, retain T) | WS 원문 전달만 | **FE 미사용** | 없음 | 래치·안전 상태가 화면에 없음. "안전 해제는 래치 상태에서만 활성"(정의서:1528) 구현 불가 | **누락** |
| `robot/status` | 정의서:1461 | 계약:48, 254-271 | 발행 BR:481-489 (QoS1, retain T) | WS 원문 전달만 | **FE 미사용** | 없음 | 연결·동작·오류·순응 상태 미표시 | **누락** |
| `hb/ros` | 정의서:1467 (1 Hz) | 계약:54, 466-469 | 발행 BR:570-572 (QoS0, retain F), 주기 파라미터 `heartbeat_hz`=1.0 BR:176, 248 | WS 원문 전달만. **만료 감시 없음**(정의서:1514 "hb/ros 만료 감시") | FE 미사용 | 없음 | 메인 PC 생존 감시 없음. 만료 기준 필드는 계약 TBD(계약:481) | **누락** (기준은 미결) |
| `conn/ros` | 정의서:1468 (LWT) | 계약:55, 471-475 | LWT BR:255-260, 접속 시 true BR:287, 종료 시 false BR:578 (QoS1, retain T) | WS 원문 전달만 | FE 미사용 | 없음 | 발행은 계약대로, 소비 없음 | 발행 **일치** / 소비 **누락** |
| `cmd/scan/set_config` | 정의서:1454 | 계약:41, 139-152 | 구독 BR:282, 처리 BR:429-447, 변환 DEC:24-62 | REST→발행 API:491-498 | **FE 버튼 없음** | 없음 | UI 없음(REST 직접 호출로만 가능) | bridge·API **일치** / FE **누락** |
| `cmd/safety/reset` | 정의서:1455 | 계약:42, 154-163 | 구독 BR:283, 처리 BR:449-466 | REST→발행 API:501-508 | **FE 버튼 없음** | 없음 | UI 없음 → 웹에서 래치 해제 불가 | bridge·API **일치** / FE **누락** |

##### 1.2 양 끝이 다 있는 토픽

| 토픽 | 정의서 | 계약 | mqtt_bridge | FastAPI | React/WS | mock | 차이 | 판정 |
|---|---|---|---|---|---|---|---|---|
| `cmd/scan/start` | 정의서:1450 | 계약:37, 92-102 | 구독 `cmd/scan/+` BR:282, goal BR:334-340, `config_override` DEC:65-74 | 발행 API:450-457, 본문 API:398-416 (QoS1, retain F) | 버튼 FE:334-336, `fetch('/commands/scan/start')` FE:287-299, `payload:{}` | 없음 | 키 일치. `session_id`는 FE가 보내지 않음(선택이라 허용, 계약:72) | **일치** |
| `cmd/scan/stop` | 정의서:1451 | 계약:38, 104-113 | BR:352-353, 404-427, 만료 검사 제외 GRD:96-97 | API:460-467 | FE:339-341 | 없음 | 키 일치. IDLE 시 완료 통지 없음(발견 E) | **부분** |
| `cmd/scan/home` | 정의서:1452 | 계약:39 | BR:341-345 | API:470-477 | FE:344-346 | 없음 | — | **일치** |
| `cmd/scan/resume` | 정의서:1453 | 계약:40, 126-137 | BR:346-351, `scan_id` 최상위 키 DEC:95-100 | API:480-488, `scan_id` 최상위 API:408-409 | FE:281-284 (`scan/state`에서 받은 scan_id) | 없음 | 키 위치 일치(최상위) | **일치** |
| `cmd/ack` | 정의서:1458 | 계약:45, 183-221 (QoS1, retain F) | 발행 BR:554-560, ENC:298-310 (`applied`는 set_config 성공 시만 BR:446) | 구독 API:36, 상태 갱신 API:114-158, 268-280 | 가상 토픽 `command/status`로 표시 FE:482-492, 936-942 | 없음 | 키 일치(기계 대조). goal reject 사유가 `BUSY` 고정(BR:379-386) — scan_manager가 항상 accept하므로 실사용 경로는 발견 D | **부분** |
| `scan/command_result` | 정의서:1459 | 계약:46, 223-235 | 발행 BR:562-568, Action Result BR:391-402, stop은 STOPPED 전이 BR:501-508 | 구독(`scan/#`) API:33, 상태 갱신 API:161-194, 283-295 | FE:945-979 | 없음 | 키 일치. start 완료 시점 = RunScan Result(계약:78) 일치. stop 완료 누락 사례(발견 E) | **부분** |
| `robot/sample` | 정의서:1460 (10 Hz) | 계약:47, 237-252 (QoS0) | 다운샘플 BR:468-472 (`sample_publish_hz`=10.0 BR:176, 196), 발행 BR:479 (QoS0, retain F) | WS 전달(QoS1로 구독하나 발행 QoS0이라 실효 0) API:204-205 | FE:412-439 (`valid===true`만) | MOCK:89-130 (QoS0) | 키·단위 일치. 파라미터 이름은 정의서 `downsample_hz`와 다름(1.4절) | **일치** |
| `scan/state` | 정의서:1462 | 계약:49, 273-286 (QoS1, retain T) | BR:491-502 | WS 전달 | FE:390-410 | MOCK:58-82 (retain T) | 키 일치. FE 기본값 `IDLE`/`progress ?? 0`(발견 J) | **일치** (표시 기본값은 부분) |
| `scan/log` | 정의서:1464 | 계약:51, 427-445 | BR:519-527, `pose_valid=false`면 `pose:null` ENC:194 | WS 전달 | FE:473-479, 82-140 (`pose_valid===true`일 때만 좌표) | MOCK:378-412 | 키 일치. DB 저장 없음(정의서 11.2는 `scan_event`만 요구 → 위반 아님) | **일치** |
| `contact/event` | 정의서:1465 | 계약:52, 288-312 | BR:529-542, ENC:154-178 | WS 전달 + DB 저장 API:249-265, DB:252-335 | FE:441-471 (`type` 구분 없이 같은 색) | MOCK:137-182 | 키 일치. FE가 CONTACT/EDGE/OVER_FORCE를 구분하지 않음 | **일치** (표시는 부분) |
| 검토안 `cmd/scan/calibrate` · `scan/calibration/result` | 정의서:1469 | 계약:60 | 없음(`cmd/scan/calibrate`가 오면 `NOT_SUPPORTED` BR:358-359) | 없음 | 없음 | 없음 | `calibrat` grep 0건(mqtt_bridge · backend · frontend · docker) | **범위 초과 없음** |

기계 대조 결과: ENC 출력 키 = 계약 예시 키 — `robot/sample` · `robot/status` · `scan/state` · `contact/event` · `scan/result` · `scan/log` · `safety/status` · `cmd/ack`(거절 · applied) · `scan/command_result` · `hb/ros` · `conn/ros` 전부 일치. MOCK 5종(`scan/state` · `robot/sample` · `contact/event` · `scan/result` · `scan/log`)도 키 · QoS · retain 일치.

##### 1.3 공통 규칙 점검

| 항목 | 정의서/계약 | 구현 | 판정 |
|---|---|---|---|
| 명령 식별자 이름 | `request_id`. `command_id` · `job_id` 금지(계약:20) | 전 구간 `request_id`. `command_id` · `job_id` grep 0건 | **일치** |
| 명령 필수 필드 | `schema_version` · `request_id` · `timestamp_ms` · `payload`(계약:72, 정의서:1485) | 발행 API:398-403 / 검사 GRD:14-19, 63-88 (UUID v4 · 정수 · 객체 검사 포함) | **일치** |
| `session_id` | 명령에서 선택(계약:72) | API:405-406(있을 때만), GRD는 검사 안 함 | **일치** |
| 명령 종류 수 | 정의서·계약 6종(정의서:1450-1455, 계약:37-42) | mqtt_bridge 6종(BR:334-357) / FastAPI REST 6종(API:450-508) / **React 버튼 4종**(FE:828-846) / 이슈 T21 제목은 "명령 4종"이나 코드는 6종 | bridge·API **일치**, FE **누락 2종** |
| cmd/ack vs command_result | 접수 ≠ 완료. set_config · safety/reset은 ack가 곧 결과(계약:76-80) | BR가 분리 발행(BR:387-389, 423-427). API `ACK_IS_FINAL_TOPICS`(API:108-111, 147-151) | **일치** (3장 상세) |
| 중복 명령(TR-09) | 최근 N개 기억, `DUPLICATE_REQUEST(106)`(계약:66) | GRD:51, 90-94, 크기 파라미터 `dedup_cache_size`=100(BR:175, 188-192). 테스트 `ws_cobot1/src/mqtt_bridge/test/test_command_guard.py:17` | **일치**. 관찰: 만료로 거절되는 명령도 먼저 기억된다(GRD:94가 GRD:99보다 앞) — FastAPI는 매번 새 UUID라 실해는 없음 |
| 만료 | `cmd_expiry_s`=5, stop 제외(계약:68) | GRD:96-101, 파라미터 BR:176, 191 | **일치** |
| FastAPI "미확정" 표시 | ack 제한 시간 초과 시(계약:81, 정의서:1483). 제한 시간 값은 계약 TBD(계약:479) | **없음**. `PUBLISHED`에서 영구 정지(API:418-433) | **누락** (값은 미결) |
| 웹 다운샘플 10 Hz | 정의서:1490, 계약:47 | BR:468-472, `time.monotonic` 기준, 파라미터화 | **일치** |
| heartbeat 1 Hz | `hb/ros` 1 Hz(계약:54), `hb/web` 1 Hz(계약:43) | `hb/ros` BR:248, 570-572 **일치** / `hb/web` **누락**(발견 B) | 부분 |
| QoS · retain | 계약:35-57 | BR 발행 전부 계약대로(BR:479, 489, 500, 517, 527, 542, 552, 558, 566, 572, 287). API 명령 QoS1 · retain F(API:411-416) | **일치** |
| retain 상태의 오래된 값 배제 | 웹이 `stamp_ms`로 배제(계약:57), 기준 시간 TBD(계약:482) | API · FE 모두 검사 없음 | **누락** (기준은 미결) |
| 구독 필터 | 계약:58 | API:31-39 · BR:281-286 글자 그대로 | **일치** |
| `topic_prefix` | 기본 `""`(계약:59) | BR:175, 183, 40-54. 웹은 접두사 없음 전제 | **일치** |
| 알 수 없는 ReasonCode | 표는 추가만(정의서:1161) | ENC:40-43이 `ValueError` → `_safe_ros_callback`이 메시지를 버림(BR:152-161). 현재 `ReasonCode.msg` 33개 = ENC `REASON_NAMES` 33개라 지금은 발생 안 함. 기존 이슈 #90(OPEN) | **부분** (잠재) |

##### 1.4 미결 항목의 사실상 결정 (정의서 10장 · 6장 "제안(TBD)")

| 항목 | 정의서 제안 | 구현으로 굳은 것 | 근거 |
|---|---|---|---|
| #23 PostgreSQL ERD/DDL | `scan_result` · `scan_event` · `calibration_result`(FastAPI) / `job` · `workpiece` · `user`(Spring), 컬럼 1:1 + `*_valid` 유지(정의서:1436, 10장 #23) | `scan_jobs` · `measurements` · `contact_events` · `scan_configs`. 스칼라는 1:1 컬럼 + `*_valid`, 배열·pose·wrench·config는 JSONB. `calibration_result` 없음(검토안 미채택과 부합). Spring용 테이블 없음 | `docker/postgres/init/001_schema.sql:6-106` |
| mqtt_bridge 파라미터 이름(6.5, 제안) | `client_id` · `topic_map_file` · `downsample_hz` · `hb_ros_hz` · `qos_default`(정의서:1131-1139) | `topic_prefix` · `dedup_cache_size` · `sample_publish_hz` · `heartbeat_hz` · `keepalive_s`. `topic_map_file` · `qos_default` 없음(QoS는 코드 고정), `client_id`는 `mqtt_bridge-<pid>` 고정(BR:250) | BR:173-179, `ws_cobot1/src/mqtt_bridge/config/mqtt_bridge.yaml:1-10`. 정의서 6장 머리말상 ★ 아닌 파라미터는 담당자 재량(정의서:1061) |
| REST · WS 경로(13장, 범위 밖·초안) | `POST /api/scan/*` · `POST /api/safety/reset` · `WS /ws/live`(정의서:1505-1511) | `POST /commands/scan/*` · `POST /commands/safety/reset` · `WS /ws` + `GET /commands/{request_id}` | API:353, 450-529 / FE:288, 365 / `frontend/vite.config.js:8-21` (FE ↔ API 서로는 일치) |
| WebSocket 메시지 형식(계약 5장 TBD, 계약:479) | 미정 | `{"topic", "payload"}` 원문 중계 + 가상 토픽 `command/status` | API:54-70, 277-295 / FE:386, 482 |
| `request_id` 중복 기억 개수 · 만료 | 출발값 100 · 5 s(정의서:1497) | 그대로 파라미터화 | BR:175-176 |

---

#### 2. 단위 변환 (규칙 7 · `units-frames.md:12`)

계약: "두산↔ROS는 robot_manager, ROS↔웹은 **mqtt_bridge**. 그 외에서는 변환하지 않는다"(`docs/contracts/units-frames.md:12`, `docs/contracts/mqtt-schema.md:14`).

| 구간 | 변환 | 근거 | 판정 |
|---|---|---|---|
| ROS→MQTT (m→mm, m/s→mm/s) | mqtt_bridge `encoders.py` 한 곳. point/pose ENC:74-91, z_drop ENC:155-158, 결과 스칼라 ENC:249-250, 271-286, segment ENC:240-246, config ENC:219-237. 힘·토크는 무변환 ENC:94-102 | `ws_cobot1/src/mqtt_bridge/mqtt_bridge/conversions.py:6-23` | **일치** |
| MQTT→ROS (mm→m) | mqtt_bridge `decoders.py` 한 곳 DEC:38-61. `*_m` 키를 웹이 직접 보내면 unknown key로 거절 DEC:26-28 → mm 값이 m 필드로 역류할 길이 막혀 있음 | DEC:10-15, 24-62 | **일치** |
| FastAPI | 변환 없음. `payload`를 그대로 실음(API:398-403), DB에 mm 그대로 저장(DB:197-224) | — | **일치** |
| React | 단위 변환 없음. `DISPLAY_SCALE = 0.01`(100 mm = 1 unit)은 화면 축척이지 단위 변환이 아님 | FE:722, 747, 784 | **일치** |
| 이중 변환 | 없음. BR가 ROS 원값(m)을 dict로 옮긴 뒤(BR:72-140) ENC에서 한 번만 ×1000 | — | **일치** |
| 역류 | 없음. 단 `set_config` 값의 **타입·범위 검증이 FastAPI에 없다**(정의서:1514 "입력 검증"). 문자열 등은 mqtt_bridge에서 예외 → `INVALID_REQUEST`로 막힘(BR:360-362) | API:384-387 | 부분(검증 위치) |

관찰(단위는 아니나 좌표 관련):
- FE 3D 축 매핑 (x, z, y)은 반사 변환이다(발견 H). FE:725-729.
- `robot/sample` · `contact/event`는 `base_link`, `scan/result`는 `workpiece_fixture`(계약:325). T36에서 결과 상자를 그릴 때 두 프레임을 한 장면에 섞으면 `base_to_fixture`만큼 어긋난다. 현재 FE에는 프레임 구분 로직이 없다(`frameId`는 텍스트 표시만, FE:895).
- 목업 상자·작업대 크기(FE:578-616)는 코드 상수(목업이므로 규칙 7 대상은 아님, T36에서 제거 대상).

---

#### 3. 접수 ≠ 완료 (규칙 4, 웹 부분)

| 위치 | 동작 | 근거 | 판정 |
|---|---|---|---|
| FastAPI 상태 기계 | `PUBLISHED` →(ack true)→ `ACCEPTED` →(result)→ `SUCCEEDED`/`FAILED`. ack false → `REJECTED`. `ack`와 `result` 원문을 **별도 키**로 보관 | API:145-156, 186-192 | **일치** |
| ack를 완료로 취급? | `set_config` · `safety/reset`만 ack=true를 `SUCCEEDED`로 처리. 계약:80이 허용하는 예외와 정확히 같다. Action 명령은 ack만으로 완료가 되지 않는다 | API:108-111, 147-151, 테스트 `backend/app/tests/test_commands.py:44-59, 128-149` | **일치** |
| React 표시 | "접수 결과"(ack 기준)와 "실행 결과"(status 기준)를 **다른 줄**로 표시. ACCEPTED는 실행 결과 "대기" | FE:935-953 | **일치** |
| REST 응답 | `status: PUBLISHED`만 반환(접수조차 아님을 명시). FE 로그 "명령 전송: PUBLISHED" | API:441-447, FE:317-319 | **일치** |
| 순서 역전 | `command_result` 뒤에 ack가 오면 `SUCCEEDED`→`ACCEPTED`로 되돌아간다(가드 없음). 같은 연결의 QoS1 순서 보장으로 통상 발생하지 않음 | API:147-153 | 부분(방어 없음) |
| 거절의 표현 | 발견 D: 거절 사유(1xx)가 ack가 아니라 command_result로 온다 → 화면에 "접수 → 실패 (SAFETY_LATCHED)". 정의서 12.2(정의서:1483)의 "거절은 cmd/ack" 의미와 다르다. 웹 코드 문제가 아니라 scan_manager↔mqtt_bridge 사이 설계 선택(`scan_manager.py:615-617`에 사유 명시) | 위 0장 D | **부분** — 계약에 반영 필요(이슈 초안 대상) |
| 완료 미도착 | 발견 E(IDLE stop) + timeout 없음 → "대기" 영구 표시 | 위 0장 E | **부분** |
| 저장 성공 표시 | 계약:82 "저장 성공은 커밋 후에만 표시". FastAPI는 커밋 후 `print`만 하고(API:235-240) WS로 알리지 않는다. 거짓 성공 표시는 없으나 저장 성공/실패 표시 자체가 없다. DB 저장 실패도 로그뿐(API:242-247) | API:233-265 | **누락** |
| 명령 이력 영속 | 프로세스 메모리(API:103). 재시작 시 소실(README 명시 `backend/app/README.md`의 "현재 명령 상태는…" 문단). DB 테이블 없음 | — | 관찰 |

---

#### 4. 미측정값 유효성 전 구간 추적 (규칙 6 · TR-10)

| 구간 | 처리 | 근거 | 0으로 뭉개지는가 |
|---|---|---|---|
| ① ROS msg 생성(scan_manager) | 무효 = NaN + `*_valid=false`. 거절 Result도 `blank_result_msg()`로 NaN | `ws_cobot1/src/scan_manager/scan_manager/conversions.py:206-245`, `ws_cobot1/src/contact_scan_interfaces/msg/ScanResult.msg:1` | 아니오 |
| ①' `ScanConfig.debounce_n` | `uint8`이라 NaN 불가 → 값 0 + `debounce_set=false` | `conversions.py:171-185` | ROS 안에서는 플래그로 구분됨 |
| ② mqtt_bridge JSON | 스칼라: `*_valid=false`면 `null`, NaN/Inf도 `null`(ENC:249-250, `conversions.py:31-35`). 배열: `box_valid=false`면 `vertices/edges/path_candidates = null`(ENC:254-259). `z_drop_mm`(ENC:155-158), `scan/log.pose`(ENC:194), `safety/status.position`(ENC:212)도 `null`. `*_valid` 키 항상 유지. `json.dumps(allow_nan=False)`로 NaN 누출 차단(BR:57-58, 테스트 `test_node.py:20`) | 실행 확인: 실패 케이스 → `None None None None None` | 아니오 |
| ②' **config의 `debounce_n`** | `_scan_config_dict`가 `*_set`을 읽지 않음(BR:91-105) → `"debounce_n": 0` | 실행 확인: 전 필드 미지 config → 나머지 11개는 `null`, `debounce_n`만 `0` | **예 (발견 F)** |
| ③ FastAPI 파싱 | `payload["..."]` 직접 접근, 기본값 없음. `None`→SQL NULL. JSONB는 `to_jsonb(None)`→SQL NULL(DB:36-47). 키 누락이면 `KeyError`→저장 실패 로그(0 대체 없음). `or 0` · `float(x or 0)` · `.get(…, 0)` grep 0건 | DB:193-224, 314-332 | 아니오 |
| ③' `scan_configs.config` | JSONB 통째 저장(DB:244-247) → ②'의 `debounce_n: 0`이 그대로 들어감 | — | **예 (②' 전파)** |
| ④ PostgreSQL 스키마 | 측정 컬럼 전부 `DOUBLE PRECISION` NULL 허용, **`DEFAULT 0` 없음**, `NOT NULL` 없음. `*_valid`는 `BOOLEAN NOT NULL DEFAULT FALSE`(기본이 "무효" 쪽이라 안전). `vertices/edges/path_candidates` JSONB NULL 허용 | `docker/postgres/init/001_schema.sql:31-57, 83-86` | 아니오 |
| ④' upsert | `ON CONFLICT (scan_id) DO UPDATE` — 재시작(같은 scan_id)의 최종 결과가 부분 결과를 덮어씀. 계약의 `(scan_id, stamp)` 의도와 부합(DB:161-191). `contact_events`는 `(scan_id, event_id)` — `event_id`가 프로세스 수명(정의서:1244)이라 contact_detector 재기동 + resume이면 앞 이벤트를 덮어쓸 수 있음 | DB:296-312 | 아니오(덮어쓰기 위험은 별개) |
| ⑤ Spring Boot 엔티티/DTO/조회 API | **없음.** Java 파일 1개(기동 클래스), JPA·JDBC 의존성 없음, datasource 설정 없음, compose에 DB 환경변수 없음 | `backend/spring/src/main/java/com/weldmade/backend/WeldMadeApplication.java:1-19`, `backend/spring/build.gradle:20-28`, `backend/spring/src/main/resources/application.properties:1-6`, `docker/docker-compose.yml:76-88` | **미확인(코드 없음)**. 구현 시 확인할 것: 엔티티 필드가 `Double`(boxed)인지 `double`인지, DTO 직렬화가 `null`을 유지하는지, `*_valid`를 같이 내보내는지 |
| ⑥ React 표시 | 결과 표시 코드 자체가 없음(발견 A). 기존 숫자 표시는 `formatNumber`가 `Number.isFinite` 아니면 `'-'`(FE:76-80) → null이 0.00으로 보이지 않음. `?? 0`은 `payload.code ?? 0`(FE:105, 로그 코드 표시)과 `payload.progress ?? 0`(FE:400, 진행도) 두 곳 — 측정값 아님 | FE:76-80, 105, 400 | 아니오(측정값 기준). 단 `robot/sample`은 `valid===true`만 반영(FE:413-417) **일치**, `contact/event`는 `payload.pose` 존재만 확인(FE:442-445) — pose 내부 `x_mm:null`이면 `null*0.01=0`으로 **원점에 마커가 찍힌다**(FE:805-809). 실제 발생 조건: ContactEvent.pose가 NaN인 경우(정상 경로에서는 드묾) |

TR-10 결론: **측정값(z_top · x/y_pos/neg · 치수 · 꼭짓점 · 엣지 · z_drop)은 ROS→MQTT→FastAPI→PostgreSQL까지 0으로 뭉개지는 곳이 없다.** 예외는 설정 스냅샷의 `debounce_n`(발견 F) 한 곳과, React `contact/event` 마커의 null→0 곱셈(잠재). Spring 구간은 코드가 없어 미확인. DB 저장 경로에 대한 자동 테스트는 없다(`backend/app/tests/`에 `test_commands.py`뿐, null 저장 테스트 없음; mock도 실패 케이스 `scan/result`를 발행하지 않음 MOCK:189-371).

---

#### 5. M4 종단 경로의 웹 절반

##### 5.1 명령 경로: 시작 버튼 → /scan/run — **끊김 없음**

1. 버튼 `onClick={handleStart}` — FE:830-832 → `sendScanCommand('start')` FE:334-336
2. `fetch('/commands/scan/start', POST, {payload:{}})` — FE:287-299
3. vite 프록시 `/commands` → `http://127.0.0.1:8000` — `frontend/vite.config.js:14-16` (개발 서버 전제. compose에 frontend 컨테이너 없음 `docker/docker-compose.yml:1-93`)
4. FastAPI `POST /commands/scan/start` — API:450-457 → `publish_command` API:390-416 (`request_id`=uuid4, `timestamp_ms`, QoS1, retain F)
5. Mosquitto — `docker/mosquitto/config/mosquitto.conf:1-7` (1883, 익명 허용)
6. mqtt_bridge 구독 `cmd/scan/+` — BR:281-286 → 큐 BR:293-307 → 가드 BR:329-332 → `RunScan.Goal` BR:334-340 → `send_goal_async` BR:366-371
7. ack BR:387 → API:268-280 → WS `command/status` → FE:482-492

조건부 끊김: (a) mqtt_bridge `broker_host`가 bringup yaml에 없어 기본 `127.0.0.1`(발견 G) — 웹 PC가 다른 기기면 수동 파라미터 필요. T27 검증은 수동 지정으로 통과한 기록(`backend/app/README.md` "T27 … 실제 통합 검증" 절). (b) 두 PC 시계가 5 s 넘게 어긋나면 start가 `command expired`로 거절(GRD:99-101, chrony는 별도 PR 계약:84).

##### 5.2 결과 경로: /scan/result → 3D 직육면체 — **React에서 끊김**

1. scan_manager `/scan/result` 발행 — `scan_manager.py:221, 794-797`
2. mqtt_bridge 구독 BR:218-222 → dedup `(scan_id, stamp)` BR:164-166, 510-516 → `encode_scan_result` ENC:253-295 → `scan/result` QoS1 BR:517
3. FastAPI 구독 `scan/#` API:33 → WS 원문 중계 API:227-230 → DB 저장 API:233-247
4. **끊기는 첫 지점: `frontend/src/App.jsx:380-493`의 `websocket.onmessage`.** 분기는 `scan/state`(390) · `robot/sample`(413) · `contact/event`(442) · `scan/log`(474) · `command/status`(482)뿐이고 `scan/result` 분기가 없다. 메시지는 브라우저까지 도착하지만 `console.log`(FE:384)로만 남는다.
5. 3D 직육면체: FE:598-616의 `BoxGeometry(2, 1, 1.2)` 고정 목업. **실제 결과 키도, 목업 결과 키도 읽지 않는다**(`vertices` · `edges` · `path_candidates` · `width_mm` 등 grep 0건). 엣지·경로 후보 강조, 치수·좌표 표 없음.

부수 위험(결과 경로): `scan/result`는 retain=false(계약:50)이고 FastAPI가 최신 결과를 캐시하거나 REST로 제공하지 않는다 → 결과 발행 시점에 브라우저/ FastAPI가 연결돼 있지 않으면 화면에 복구할 방법이 없다(DB에는 있으나 조회 API가 없음 — Spring 미구현).

##### 5.3 T29(CLOSED) 범위 확인
시간순 로그 패널(FE:1006-1024)과 접수/거절 · 완료/실패 표시(FE:917-993)는 구현돼 있다. T23(CLOSED)은 제목대로 "목업 데이터" 3D 뷰다.

---

#### 6. Spring Boot(T35) · 엣지 강조/좌표 표(T36) 구현 상태

| | main (`717cbdd`) | 미병합 브랜치 |
|---|---|---|
| T35 Spring Boot | 골격만. `WeldMadeApplication.java` 1개 + actuator health. `spring-boot-starter-web` · `actuator`만 의존(`backend/spring/build.gradle:20-28`). `/mgmt/jobs` · `/mgmt/workpieces` · `/mgmt/history`(정의서:1519-1521) **없음**. JPA/JDBC · datasource · 엔티티 · DTO · 테스트 **없음**. compose의 spring 서비스에 DB 환경변수 없음(`docker/docker-compose.yml:76-88`) | `origin/euiseok/20260921-t35-spring-history` = `d5c869a`. 이 커밋은 **origin/main의 조상**이다(`git merge-base --is-ancestor` 참, `git ls-remote origin`으로 원격 값도 동일 확인). `git diff origin/main...브랜치 --stat` **빈 출력**, `git log origin/main..브랜치` **0건**. 즉 브랜치 이름만 있고 T35 작업 커밋은 원격에 없다(로컬 미푸시 여부는 이 저장소에서 확인 불가 — 의석 PC에서 `git log` 확인 필요) |
| T36 엣지·경로 후보 강조 · 좌표 표 · 홈 복귀/재시작 진행 표시 | 엣지 강조 · 좌표/길이 표 **없음**(발견 A). 홈 복귀 · 재시작 진행 표시는 phase 라벨 수준으로만 있음: `HOMING`→"홈 복귀 진행", `RESUMING`→"재시작 진행"(FE:38-42), 명령별 접수/완료 표시(FE:925-953) | T36 브랜치 없음(`git branch -r`: `euiseok/…t35…` · `t109-…` · `t15-…` · `t18-…` · `t30-…`뿐). 열린 PR은 #127 · #122 둘이고 웹 관련 아님. 이슈 #35 · #36 모두 OPEN |

스키마 쪽 준비 상태: Spring이 쓸 `job` · `workpiece` · `user` 테이블이 `001_schema.sql`에 없다(1.4절). T35 구현 시 DDL 추가가 필요하고, 이미 만들어진 볼륨에는 `docker-entrypoint-initdb.d`가 다시 돌지 않는다(`docker/docker-compose.yml:31-33`) — 마이그레이션 방법을 정해야 한다.

---

#### 7. 이슈 초안 후보 (소유자: 의석=web · mqtt_bridge, 병후=scan_manager. 현지 소유 아님 → 수정하지 않고 초안만)

1. **[web] React가 `scan/result`를 받아 직육면체 · 엣지 · 경로 후보를 그린다**(T36에 흡수 가능). `box_valid=false` · `vertices=null` 처리, `workpiece_fixture`↔`base_link` 프레임 구분, 축 매핑 (x, z, −y) 수정 포함. 근거 FE:380-493, 598-616, 725-729.
2. **[web] FastAPI `hb/web` 1 Hz 발행 + `conn/web` LWT**. T33 병합 전 선행. 근거 계약:43-44, 73-74.
3. **[web] 안전 해제 · 설정 등록 UI + `safety/status` · `robot/status` · `conn/ros` · `hb/ros` 표시**. 근거 정의서:1528.
4. **[bridge] `encode_scan_config`가 `debounce_set=false`면 `debounce_n: null`**. `_scan_config_dict`에 `*_set` 전달. 근거 BR:91-105, ENC:223, 계약:31.
5. **[bridge/scan] 멈출 작업이 없는 stop의 완료 통지** — 접수 응답에 "phase 불변"이 실려 오면 즉시 `command_result`를 내거나 pending에 넣지 않는다. 근거 BR:424-427, `state_machine.py:84-88`.
6. **[계약] 거절 표현 정리** — "goal은 항상 accept, 거절 사유는 `scan/command_result`의 1xx"를 `mqtt-schema.md` 3장에 명문화하거나, mqtt_bridge가 1xx Result를 `cmd/ack accepted=false`로 바꿔 내도록 정한다. 계약 · 인터페이스 · CHANGELOG 동시 변경 대상. 근거 `scan_manager.py:612-628`, 계약:183-194.
7. **[bringup, 현지 소유] `sim.yaml` · `real.yaml`의 `mqtt_bridge:` 절을 채운다**(`broker_host` 등). 근거 `sim.yaml:182-183`, `real.yaml:186-187`.
8. **[web] FastAPI: ack/결과 timeout "미확정", 접속 시 최신 상태 스냅샷 전송, 저장 성공/실패 WS 통지, DB 저장 null 케이스 테스트 + mock 실패 케이스 발행**.


---

## 부록 C. 구조 규칙 검증

### Phase 4: 구조 규칙 검증 (읽기 전용 통합 감사)

- 기준 스냅샷: origin/main `717cbdd` (경로는 저장소 상대경로)
- 기준 문서: `docs/design/contact-scan-interface-spec-integrated-v1.2.md` 7장(7.4 · 7.5) · 8장 · 14장, `docs/contracts/ros-interfaces.md` 1장 · 4.1 · 5.x · 7.1~7.4 · 9장, `docs/contracts/mqtt-schema.md` 19 · 31 · 45~46 · 68 · 76~80행
- 미병합 PR #127(`origin/t109-descend-tare-slide-arm`, `2ac32ce`)은 `git diff origin/main...`으로 읽기만 했다. 변경 파일 9개가 모두 contact_detector · 계약 문서 · bringup yaml 이다. **10개 규칙의 판정을 바꾸지 않는다**(규칙별 비고 참고).
- 코드 실행 · 로봇 · ros2 명령 없음. 판정은 전부 정적 읽기다. 실행으로만 확인되는 것은 `미확인`으로 적었다.
- 등급: `일치` · `부분` · `불일치` · `누락`

#### 판정 요약

| # | 규칙 | 판정 |
|---|---|---|
| 1 | 자체 노드 5개, geometry_estimator · result_store 는 모듈 | 일치 |
| 2 | 정지 경로 3가지 | 일치 |
| 3 | 래치는 `/safety/reset` 으로만 해제, 래치 중 시작 · 재시작 거절 | 일치 (비고 3건) |
| 4 | 접수 ≠ 완료 (ROS 부분) | 부분 |
| 5 | 중단 위치 = Result pose, 측정 좌표 = ContactEvent pose | 일치 |
| 6 | 미측정값은 0 이 아니다 (ROS 부분) | 부분 |
| 7 | 단위 m · rad · N, 변환은 경계에서만 | 부분 |
| 8 | 순응 · 힘 제어 해제 finally 보장 | 부분 |
| 9 | 드라이버 호출은 robot_manager 만 | 일치 |
| 10 | 중지가 홈 복귀 · 재시작을 자동 실행하지 않는다 | 일치 |

---

#### 규칙 1. 자체 노드 5개 — 일치

**`Node` 상속 클래스 전수(제품 코드)** — 정확히 5개다.

| 노드 | 클래스 | entry_point |
|---|---|---|
| scan_manager | `ws_cobot1/src/scan_manager/scan_manager/scan_manager.py:173` `ScanManager(Node)`, 이름 `'scan_manager'` (:176) | `ws_cobot1/src/scan_manager/setup.py:27` |
| robot_manager | `ws_cobot1/src/robot_manager/robot_manager/robot_manager.py:73` `RobotManager(Node)` (:76) | `ws_cobot1/src/robot_manager/setup.py:27` |
| contact_detector | `ws_cobot1/src/contact_detector/contact_detector/contact_detector.py:96` `ContactDetectorNode(Node)` | `ws_cobot1/src/contact_detector/setup.py:27` |
| safety_monitor | `ws_cobot1/src/safety_monitor/safety_monitor/safety_monitor.py:68` `SafetyMonitorNode(Node)` (NODE_NAME :39) | `ws_cobot1/src/safety_monitor/setup.py:27` |
| mqtt_bridge | `ws_cobot1/src/mqtt_bridge/mqtt_bridge/mqtt_bridge.py:169` `MqttBridge(Node)` (:171) | `ws_cobot1/src/mqtt_bridge/setup.py:23` |

- launch: `ws_cobot1/src/contact_scan_bringup/launch/bringup.launch.py:25-31` 의 `NODES` 가 위 5개뿐이고, 패키지 = 실행 파일 = 노드 이름으로 띄운다(:56-63). launch 파일은 이것 하나다. `contact_scan_bringup/setup.py:30-31` 의 console_scripts 는 비어 있다.
- **geometry_estimator · result_store 는 모듈이다.** `scan_manager/scan_manager/geometry_estimator/{__init__,bias,estimator}.py`, `scan_manager/scan_manager/result_store/{__init__,records,store}.py` 어디에도 `rclpy` import 가 없다(각 파일 머리말에 "rclpy 를 import 하지 않는다"). scan_manager 가 함수로 부른다: `scan_manager.py:69`(`compute_shape`), `:72-78`(`ResultStore`). 디스크 쓰기는 노드 안의 쓰기 스레드 1개다(`scan_manager.py:215`).

**보조 실행 파일(노드 5개에 넣지 않는다)**

| 파일 | Node 인가 | 구분 |
|---|---|---|
| `contact_detector/contact_detector/sim_source.py` (`SimBox` :32, `SimSource` :77) | 아니다. rclpy 없음. contact_detector 노드 안에서 객체로 쓴다 | sim 입력원(모듈) |
| `contact_detector/contact_detector/offline.py` (`main` :194, entry `analyze_samples` = `contact_detector/setup.py:28`) | 아니다. CSV 분석 CLI, rclpy 없음 | 분석기 |
| `docs/env/check_api_calls.py:381` · `measure_idle_force.py:220` · `probe_point.py:84` · `apply_tool_tcp.py:69` | `rclpy.create_node(...)` 로 임시 노드를 만든다(클래스 상속 아님) | 환경 점검 스크립트. launch 에 없다. 사람이 직접 돌린다 |
| `docs/env/pivot_tcp.py` | 아니다(rclpy · dsr import 없음) | 계산 스크립트 |
| `backend/mock_publisher/mock_publisher.py:5` | 아니다(paho MQTT) | 웹 쪽 가짜 발행기 |
| `scan_manager/test/fake_peers.py:80` `FakeParamPeer(Node)` · `:141` `FakePeers(Node)`, 각 패키지 `test/test_node*.py` 의 `rclpy.create_node('fake_*' / '*_listener')` | 시험용 노드 | 시험 전용 |

기록기(rosbag 등)에 해당하는 실행 파일은 저장소에 없다(`find` · `grep rosbag` 결과 없음).

비고: PR #127 은 노드 · entry_point 를 추가하지 않는다(`detector_core.py` 에 `DescendTareConfig` 클래스 추가뿐). bringup 은 `mqtt_bridge/config/mqtt_bridge.yaml` 을 읽지 않는다(`bringup.launch.py:48-49` 는 sim/real.yaml 만 넘기고 그 안에 `mqtt_bridge:` 절이 없다). mqtt_bridge 는 bringup 아래에서 코드 기본값(`mqtt_bridge.py:173-179`, broker 127.0.0.1)으로 뜬다. 규칙 1 밖의 일이지만 통합에서 걸린다.

---

#### 규칙 2. 정지 경로 3가지 — 일치

##### ① 웹 중지 `/scan/stop` → scan_manager → `/robot/stop`
1. `mqtt_bridge/mqtt_bridge/mqtt_bridge.py:352-353` `cmd/scan/stop` → `_dispatch_stop` (:404-415) → `/scan/stop` 호출(클라이언트 :243). 만료 검사에서 stop 은 제외된다(`mqtt_bridge/command_guard.py:96-97`, 시험 `mqtt_bridge/test/test_command_guard.py:25`).
2. `scan_manager/scan_manager/scan_manager.py:265` 서비스 등록 → `_on_stop` (:1029-1065): 상태 기계 `Command.STOP` (:1042), `job.stop_event.set()` (:1045).
3. `/robot/stop` 요청: `:1051-1052` → `request_robot_stop` (:1067-1074, `call_async`, 응답을 기다리지 않는다). 계약 4.1 대로 goal cancel 도 **함께** 한다(:1054-1055).
4. `robot_manager/robot_manager/robot_manager.py:163` 서비스 등록 → `on_stop_request` (:671-707) 가 `stop_requested` 에 적는다(:692-693). 동작 중이면 `watch` 가 꺼낸다(:573-586) → `stop_robot` (:752-776) → `move_stop` (:763, `dsr_client.py:99-100` DR_QSTOP). 동작이 없으면 `stop_idle` 스레드(:702, :727-735).
5. 완료: 시퀀스 스레드 `sequence.py:394-400` `_finish_stop` → `wait_still` (`scan_manager.py:461-478`) → `record_stop` → `STOP_CONFIRMED` → phase STOPPED → mqtt_bridge `_on_scan_state` (:491-502) → `scan/command_result`.

##### ② `/contact/event` → robot_manager 자체 정지
- 구독 `robot_manager.py:129` → `on_event` (:345-363): OVER_FORCE 는 대조 없이(:348-351), CONTACT · EDGE 는 `motion_id` 와 동작이 맞을 때만(:352-363) `motion.event` 에 둔다.
- `watch` (:587-588) → `stop_for_event` (:652-669) → `stop_robot` → `move_stop`. 정지를 확인하지 못하면 정상 코드 대신 `ROBOT_ERROR` 로 올린다(:656-658, :663-666).
- scan_manager 는 Result 뒤에 이벤트를 `event_id` 로 맞춘다(`sequence.py:377-392`, `scan_manager.py:1298-1305`).
- 비고: 동작이 없을 때(`motion is None`) 온 OVER_FORCE 는 robot_manager 가 버린다(:349-351). 그 구간은 2차 감시(③)만 남는다. 계약 7.2 의 이중 감시 범위 안이다.
- 비고(PR #127): 하강 시작 뒤 `descend_tare_delay_s + tare_duration_s`(real.yaml 6.0 + 1.5 s) 동안 CONTACT 를 보류한다. 그 구간에서 경로 ② 는 OVER_FORCE 로만 선다. 경로 자체(호출 체인)는 그대로다.

##### ③ safety_monitor → `/robot/stop` (웹 경유 없음)
- `safety_monitor/safety_monitor/safety_monitor.py:83-84` 구독 → `on_sample` (:126-133) · `on_check` (:144-154) → `react` (:156-172) → `state.note` (래치, `safety_core.py:281-285`) + `send_stop` (:176-189).
- `/robot/stop` 클라이언트는 노드 안에 직접 있다(:85). MQTT · mqtt_bridge 를 거치지 않는다. 호출은 비동기(:189).
- 완료: `on_status` (:135-142) → `StopTracker.on_status` (`safety_core.py:234-239`) → `stop_confirmed`. 제한 시간 안에 확인하지 못하면 UNCONFIRMED 로 올리고 느리게 재요청한다(`safety_monitor.py:149-153`, `safety_core.py:241-252`).
- 시험: `safety_monitor/test/test_node.py:134`(과대 외력 → 정지 + 래치) · `:153`(하강 제한) · `:181`(미확인 재시도) · `:196`(서버 없음).

이력: `/robot/stop` 서버는 2026-09-21 까지 없었다(`robot_manager.py:160-163` 주석). main 에는 있다(#101 · #114).

---

#### 규칙 3. 래치 — 일치 (비고 3건)

- **래치를 들고 있는 곳**: safety_monitor 하나다. `safety_core.py:259-266` `SafetyState.latched`. 거는 곳은 `note()` (:281-285), 푸는 곳은 `reset()` (:287-296) **한 곳뿐**이다(`grep latched` 전수: `safety_core.py:266 · 276 · 284 · 293`). 조건이 사라져도 자동으로 풀리지 않고, 조건이 아직 참이면 `CONDITION_ACTIVE` 로 거절한다(`safety_monitor.py:205-213`). 파라미터 변경으로도 풀리지 않는다(`safety_monitor.py:107-122`).
- **scan_manager 가 아는 방법**: `/safety/status`(QOS_STATE) 구독 `scan_manager.py:233-234` → `_on_safety_status` (:422-424) → `conditions()` (:426-432) → 상태 기계 `_check` 가 START · RESUME 을 `SAFETY_LATCHED` 로 거절(`state_machine.py:326-330`). **아직 한 번도 받지 못했으면(None) 그것도 거절**한다(:327-328).
- 접수 지점: START `scan_manager.py:745-749`, RESUME `:949-953` · `:976-980`. 작업 도중에 걸린 래치는 모션마다 다시 본다(`sequence.py:351-355`). 모션 중의 래치는 "요청하지 않은 정지"로 실패 처리된다(`sequence.py:161-169`).
- 시험: `scan_manager/test/test_commands.py:119-127 · 283-285`, `test_resume.py:392-394`, `test_state_machine.py:196`, `safety_monitor/test/test_node.py:212`(조건이 참이면 reset 거절 → 해소 뒤 성공) · `:231`(멱등).

비고
1. **안전복귀(HOME)는 래치가 막지 않는다**(`state_machine.py:326` 에 HOME 없음, `sequence.py:603-604`, 시험 `test_commands.py:187` · `test_sequence.py:378`). 정의서 7.5 · 계약 5.1 은 "시작 · 재시작" 거절만 요구하므로 위반이 아니다. T10 결정으로 적혀 있다.
2. **goal 은 항상 accept 하고 Result 로 거절한다**(`scan_manager.py:257`, `_reject` :611-628). 그래서 래치 중의 start 에도 mqtt_bridge 는 `cmd/ack accepted=true` 를 보내고(`mqtt_bridge.py:387`), 거절은 `scan/command_result success=false, SAFETY_LATCHED` 로 간다. 로봇은 움직이지 않고 phase 도 안 바뀌므로 기능상 거절이지만, 계약 5.1 의 "goal 거절" · mqtt-schema 76행의 "수락/거절을 cmd/ack 로" 와 글자 그대로는 다르다. 웹은 `cmd/ack` 만 보고 "시작됨"으로 표시하면 안 된다.
3. **래치는 메모리에만 있다.** safety_monitor 프로세스를 다시 띄우면 `latched=False` 로 시작한다(`safety_core.py:262`). 또 scan_manager 는 `/safety/status` 의 최신성을 보지 않는다(`scan_manager.py:422-432`). safety_monitor 가 죽은 뒤에도 마지막 `latched=false` 를 계속 믿고 시작을 받는다. bringup 에 respawn 은 없다(`bringup.launch.py:56-63`). 규칙 문장("reset 으로만 풀린다")의 코드 경로는 지켜지지만, 프로세스 수준의 구멍은 남아 있다. 이슈 후보.

---

#### 규칙 4. 접수 ≠ 완료 (ROS 부분) — 부분

지켜지는 것
- **`/robot/stop` 응답의 뜻**: `robot_manager.py:704-706` `accepted=true` + detail "접수. 정지 완료는 /robot/status 의 connected && !moving 으로 확인한다". 핸들러는 `move_stop` 을 기다리지 않는다(:696-703). 미연결이면 `accepted=false, ROBOT_DISCONNECTED` (:683-689).
- **scan_manager 의 stop 처리**: `_on_stop` 은 접수만 돌려준다(`scan_manager.py:1030-1033 · 1057-1065`). `/robot/stop` 응답은 기다리지 않고, 접수 실패만 로그로 남긴다(:1076-1086, "정지 완료는 어차피 /robot/status 로만 확인한다"). STOPPED 로 가는 길은 `_finish_stop` → `wait_still` 하나다(`sequence.py:394-400`). `wait_still` 은 **요청 시각보다 뒤에 찍힌** `/robot/status` 로만 통과시킨다(`scan_manager.py:461-478`). 확인하지 못하면 STOPPED 가 아니라 ERROR(`ROBOT_STATUS_LOST`)다(`sequence.py:395-397`, 시험 `test_sequence.py:310`, `test_commands.py:68`).
- **robot_manager 안쪽**: `stop_robot` 은 `move_stop` 응답이 아니라 `self.moving` 이 false 가 될 때까지 기다린다(`robot_manager.py:763-776`). 확인하지 못한 정지는 `ROBOT_ERROR` 로 올리고(:569-571 · 577-584 · 597-599 · 656-658 · 663-666), 정지 요청을 되돌려 놓아 다음 goal 을 거절한다(:582, :388-393). 시험 `robot_manager/test/test_node.py:263 · 432 · 506`.
- **safety_monitor**: `StopPhase` 가 REQUESTED · ACCEPTED · CONFIRMED 를 나눈다(`safety_core.py:190-198`). CONFIRMED 는 `on_status` 로만 된다(:234-239).
- **goal accepted**: scan_manager 는 goal 수락 뒤 Result 를 기다린다(`scan_manager.py:1244-1261`). 늦은 수락 · Result 미도착은 "완료"가 아니라 취소 + `/robot/stop` + 정지 좌표 모름으로 처리한다(:1238-1243 · 1255-1260). mqtt_bridge 는 수락에 `cmd/ack`, Result 에 `command_result` 를 따로 보낸다(`mqtt_bridge.py:387-402`).
- tare: 응답 `success` 를 그대로 쓰되, 그 전에 `wait_still` 을 거친다(`sequence.py:454-461`).

어긋나는 것
- **[부분] mqtt_bridge 의 stop 완료 통지가 `phase=STOPPED` 전이에만 묶여 있다.** `mqtt_bridge.py:417-427` 은 accepted 인 stop 을 `_pending_stop` 에 넣고, `_on_scan_state` (:491-502) 가 STOPPED 일 때만 `_finish_stops` (:504-508, `success=True`)를 부른다. `_pending_stop` 을 만지는 곳은 :200 · :425 · :505-506 뿐이다.
  - 정지를 확인하지 못해 ERROR 로 끝난 stop(`sequence.py:395-397`)은 `command_result` 가 **영영 나가지 않는다.** 웹은 실패를 모른다.
  - 멈출 작업이 없는 상태(IDLE · DONE · ERROR)의 stop 도 scan_manager 는 `accepted=true` 로 돌려주므로(`state_machine.py:85-88`, `scan_manager.py:1047-1048`) `_pending_stop` 에 남는다. 이 request_id 는 **나중에 다른 작업이 STOPPED 가 될 때 `success=true` 로 같이 나간다.** 완료가 아닌 것을 완료로 알리는 경로다.
  - 이미 STOPPED 인 상태에서 온 stop 은 `/robot/status` 를 다시 보지 않고 즉시 `success=true` 다(:426-427). scan_manager 는 이때도 `/robot/stop` 을 다시 보낸다(`scan_manager.py:1050-1052`). 그 정지의 완료는 아무도 확인하지 않는다.
  - 기준: mqtt-schema 46 · 79행은 "stop: phase=STOPPED 전이"만 적고 실패 경로를 정하지 않았다. 계약 보완 + mqtt_bridge 수정 이슈 후보(소유자: mqtt_bridge 담당).
- **[부분] 경로 ③ 에서 scan_manager 가 `/robot/status` 를 직접 확인하지 않는다.** 정의서 7.5 는 "safety_monitor · scan_manager 각각 확인"이다. scan_manager 는 요청하지 않은 정지를 `_Fail` → `fail()` → ERROR 로 보내며 `wait_still` 을 거치지 않는다(`sequence.py:161-169 · 402-404`). robot_manager 가 `REASON_STOP_REQUESTED` 를 `stop_robot` 확인 뒤에만 돌려주므로(`robot_manager.py:573-586`) 간접 확인은 된다. 계약 7.1 은 ③ 의 완료 확인을 `SafetyStatus.stop_confirmed` 로만 적어 계약과는 맞다. 정의서와 계약의 차이다.
- 참고: `RobotStatus.error` · `error_code` 는 항상 `False` · `OK` 로 나간다(`robot_manager.py:334-335`). 드라이버 오류가 상태로 드러나지 않는다. 규칙 4 의 직접 위반은 아니지만 "완료 확인"의 근거가 `connected && !moving` 하나뿐이라는 점과 맞물린다.

PR #127: 영향 없음.

---

#### 규칙 5. 중단 위치 vs 측정 좌표 — 일치

- **측정 좌표 = ContactEvent.pose**: `scan_manager.py:1298-1305` `wait_event` → `MatchedEvent(position_of(event.pose))`. 기하 입력은 이것만 쓴다: `:1335` `TopMeasurement(event.position, …)`, `:1345-1346` `EdgeMeasurement(event.position, z_drop…)` → `geometry_adapter.py:77-92` → `estimate_box`. 재시작 때도 기록의 `detection.pose` 에서 다시 만든다(`resume.py:188-196`). 기록에는 둘을 **따로** 둔다: `Measurement(detection_from_event(event.raw), stop_pose_record(result.raw))` (`scan_manager.py:1328-1330`, `conversions.py:81-96 · 145-149`).
- **중단 위치 = ExecuteMotion.Result.pose**: `record_stop` (`scan_manager.py:1421-1434`)은 `result.raw` → `stop_pose_record` 만 쓴다. 재시작 위치는 기록의 `last.pose`(중지의 정지 좌표)다(`resume.py:201 · 206`). 들어 올림 · 방향 전환 · 마무리 올림도 `self._position = result.position`(Result)에서 나온다(`sequence.py:359-360 · 477-480 · 493-495`). `ReturnHome.final_pose` 도 Result 다(`scan_manager.py:848 · 865-867`).
- robot_manager 는 Result.pose 에 정지 뒤의 마지막 샘플 pose 를 싣고 주석으로 구분한다(`robot_manager.py:838-839`). contact_detector 는 이벤트 pose 에 **조건이 처음 성립한 샘플**을 싣는다(`contact_detector.py:260-267`).
- ScanLog 의 pose 는 문구로 출처를 밝힌다("판정 좌표" `scan_manager.py:1337 · 1348`, "정지 좌표" `:1405 · 1436`). `log_info` 는 좌표가 이벤트와 같을 때만 이벤트 pose 를 싣는다(:1440-1449).
- 시험: `scan_manager/test/test_sequence.py:103` `test_first_contact_z_is_the_detection_not_the_stop_pose`.

섞어 쓰는 곳: **찾지 못했다.** 경계에 있는 것 하나 — 방향 전환 · 재시작의 `recontact` 목표 z 는 판정 좌표의 z 다(`sequence.py:468 · 96-99`, `resume.py:200`). 계약 7.3 의 3번("첫 하강에서 기록한 접촉 z")이 정한 것이라 위반이 아니다. 보정 전 원값을 쓴다(윗면 보정 `top_correction` 은 적용하지 않는다).

PR #127: `ContactEvent.pose` 의 출처(첫 성립 샘플)를 바꾸지 않는다. 영향 없음.

---

#### 규칙 6. 미측정값은 0 이 아니다 (ROS 부분) — 부분

지켜지는 것
- scan_manager: `conversions.py:152-157` `nan_pose`, `:170-185` `config_to_msg`(NaN + `*_set=false`), `:194-216`(Point · Segment · blank_result NaN), `:231-237`(`*_valid=false` 면 NaN). ScanLog pose 없음 = NaN + `pose_valid=false` (`scan_manager.py:391-398`). 거절 Result 도 NaN(`:620-625`). `_effective_config` 는 모르는 값을 None 으로 둔다(:491-507).
- geometry_estimator: 입력 검사에서 None · 비유한값을 거절(`bias.py:45-50`). 빠진 방향은 `None` → `Measured.missing()` (`geometry_adapter.py:84-88 · 101-102`). 5점이 없으면 치수 · 꼭짓점 · 선분은 None(:140-152).
- result_store: `records.py:180-195` `Measured(None, False)`, `:854-868` 무효 선분에 좌표가 있으면 ValueError("0 금지"). 시험 `test_result_store_records.py:63 · 134 · 177 · 273 · 321`.
- robot_manager 샘플: 실패 시 NaN + `valid=false` (`robot_manager.py:278-301`, `dsr_client.py:60-72` None 반환). 시험 `robot_manager/test/test_node.py:88`.
- contact_detector: `z_drop_m` NaN + `z_drop_valid=false` (`contact_detector.py:268-269`), tare 실패 시 NaN (`:308-317`).
- safety_monitor: position NaN + `position_valid=false` (`safety_monitor.py:232-236`).
- mqtt_bridge: NaN · `*_valid=false` → `null` (`conversions.py:31-42`, `encoders.py:74-102 · 249-290`). `box_valid=false` 면 배열 통째로 `null` (:254-259).

어긋나는 것
1. **[부분] `debounce_n` 을 모를 때 웹으로 `0` 이 나간다.** scan_manager 는 uint8 이라 NaN 을 못 실어 `0 + debounce_set=false` 로 둔다(`scan_manager/conversions.py:36 · 173 · 180-182`). mqtt_bridge 의 `_scan_config_dict` (`mqtt_bridge.py:91-105`)는 `*_set` 플래그를 읽지 않고, `encode_scan_config` 는 `"debounce_n": config["debounce_n"]` 을 그대로 싣는다(`encoders.py:223`). mqtt-schema 31행("모르는 값은 `null`. 0 을 넣지 않는다")과 어긋난다. contact_detector 에서 값을 읽지 못한 때(`scan_manager.py:596-602`)에 일어난다. `scan/result.config` 와 `cmd/ack.applied` 둘 다 해당한다.
2. **[부분] `ExecuteMotion.Result.pose` 에는 유효 플래그가 없고, 모르면 (0,0,0) + `pose_stamp=0` 이다**(`robot_manager.py:836-840`). scan_manager 가 `pose_stamp == 0` 을 "없음"으로 읽어 막는다(`scan_manager/conversions.py:123-130 · 141 · 145-149`). 소비 측 방어는 있으나 msg 수준에서는 0 이다. Feedback.pose 도 같다(`robot_manager.py:825-834`). 계약에 `pose_valid` 가 없어서 생긴 일이다(계약 변경 사안).
3. **[부분] `distance_travelled` 는 모르면 `0.0` 이다**(`robot_manager/motions.py:68-72` "한쪽이라도 모르면 0.0", 쓰는 곳 `robot_manager.py:830-831 · 845-847`). 0 m 이동과 구분되지 않는다. 지금 이 필드를 읽는 곳은 없다(`grep distance_travelled` scan_manager · mqtt_bridge 결과 없음). 영향은 작다.
4. 참고: `safety_core.py:143` 의 `drop or 0.0` 은 로그 문구용이다. 저장 · 발행 값이 아니다.

PR #127: `detector_core.py` 추가분은 기준값 없음을 `None` 으로 둔다(diff 의 `descend_baseline: Optional[Vector3] = None`). 0 채움 없음. 영향 없음.

---

#### 규칙 7. 단위 · 변환 위치 — 부분

**robot_manager 의 두산 경계 변환 전수**

| 방향 | 위치 | 내용 |
|---|---|---|
| mm · deg → m · quaternion | `robot_manager/conversions.py:12-13`(`mm_to_m`) · `:16-29`(ZYZ deg → quaternion) · `:32-40`(`posx_to_pose_fields`) | 호출: `robot_manager.py:280` 한 곳 |
| N · N·m → 그대로 | `conversions.py:43-50` | 호출: `robot_manager.py:292` |
| m · quaternion → mm · deg | `motions.py:30-48`(quaternion → ZYZ deg) · `:51-56`(`pose_to_posx_mm_deg`) | 호출: `robot_manager.py:494-497` (OP_MOVE_TO) |
| m → mm (상대 이동) | `motions.py:59-65` `relative_target_mm` | 호출: `robot_manager.py:502-503` (DESCEND · SLIDE) |
| m/s → mm/s | `dsr_client.py:87-89` | `move_line_request` |
| deg 그대로 | `dsr_client.py:94-96` `move_joint_request` ← `home_joint_deg` · `home_speed_deg_s` (`robot_manager.py:490-491`) | ROS 메시지에 들어가지 않는다 |
| N 그대로 | `dsr_client.py:111-114` `force_on_request` ← `slide_target_force_n` | |

- 샘플 · 상태 · Result · Feedback 의 pose 는 전부 `last_pose`(= 변환을 거친 값)에서 나온다(`robot_manager.py:285 · 828 · 839`). **mm · deg 값이 ROS 메시지에 그대로 들어가는 곳, 이중 변환되는 곳은 찾지 못했다.** `robot_manager.py:640-641` 의 `* 1000` 은 로그 문구다.
- 다른 노드: scan_manager 는 변환하지 않는다(`scan_manager/conversions.py:4`). 프레임 평행 이동만 한다(`geometry_adapter.py:65-67`). mm 변환은 mqtt_bridge 의 직렬화(`mqtt_bridge/encoders.py:74-91 · 219-250`, `conversions.py:6-23`)와 역직렬화(`decoders.py:39-60`)뿐이다. FastAPI · React 는 `*_mm` 을 그대로 쓴다(`frontend/src/App.jsx:118-124 · 420-422`, `backend/app/main.py` 에 길이 변환 없음). 웹에는 각도 대신 quaternion 을 싣는다(`encoders.py:87-90`).
- 보조: `contact_detector/offline.py:39` 는 CSV 의 `*_mm` 을 m 로 바꾼다(분석기). `docs/env/*.py` 는 두산 원시 단위(mm)로 기록한다(환경 스크립트).

**yaml 단위 접미사 ↔ 사용처**
- `_m` · `_mps` · `_n` · `_s`: real.yaml/sim.yaml 의 값이 코드에서 그 단위로 쓰인다(예: `drop_limit_m` → `robot_manager.py:554` · `motions.py:75-79`, `moving_eps_m` → `:112`, `arrival_tolerance_m` → `:634`).
- `_ms`: `sample_stale_ms` · `robot_status_timeout_ms` → `safety_core.py:178` `* 1e-3`, `stale_age_ms` → `contact_detector.py:155 · 187` `* 1e-3`. 접미사대로 쓰인다(ROS 메시지에는 안 들어간다).
- `_deg` · `_deg_s`: `home_joint_deg` · `home_speed_deg_s` 는 두산 호출에만 쓴다(위 표).
- `_hz`: `sample_rate_hz` 등 → `robot_manager.py:158-159`.

어긋나는 것
1. **[부분] `MoveLine.vel` · `acc` 의 둘째 칸(각속도 deg/s · deg/s²)에 mm/s 값을 그대로 넣는다**: `dsr_client.py:87-89` `vel=[speed_mm_s, speed_mm_s], acc=[4 * speed_mm_s, 4 * speed_mm_s]`. 선속도 5 mm/s 면 각속도도 5 deg/s 가 된다. 자세 고정 탐색에서는 드러나지 않지만, `search_origin_pose` 로 자세가 바뀌는 OP_MOVE_TO 에서는 단위가 섞인 값으로 돈다. 가속도 배수 `4` 도 코드에 박혀 있다(CLAUDE.md 규칙 7). `move_joint_request` 의 `acc=2 * vel` (:95)도 같다. 두산 `MoveLine` 의 vel[1] 뜻은 `docs/env/api-check-log.md` 나 dsr_msgs2 srv 정의로 확인한다 — **미확인**(이 스냅숏에 dsr_msgs2 소스 없음).
2. **[부분] `compliance_stiffness` 에 단위 접미사가 없다**(`real.yaml:97`, `robot_manager.py:98 · 535`). 앞 3개 N/m, 뒤 3개 N·m/rad 로 보이지만 이름으로는 알 수 없다. 계약 이름이 아니므로(계약 6.4) 담당자 재량이다.
3. 참고: `robot_manager.py:77-108` 에 코드 기본값이 여럿 있다(`sample_rate_hz 50.0`, `stop_settle_s 1.5`, `motion_timeout_s 60.0`, `LOOP_PERIOD_S 0.02` :40 등). 단위 규칙이 아니라 CLAUDE.md 규칙 7 의 문제다. `stop_settle_s` · `motion_timeout_s` · `feedback_period_s` 는 yaml 에 없어 기본값으로 돈다(`real.yaml:75-116` 에 없음).

PR #127: 새 파라미터 5개(`descend_tare_delay_s` · `edge_arm_still_window_s` · `edge_arm_still_m` · `edge_arm_travel_m` · `descend_tare_enabled`)는 접미사와 사용 단위가 맞는다(diff 의 yaml 주석과 `_configs`). 영향 없음.

---

#### 규칙 8. 순응 · 힘 제어 해제 — 부분

지켜지는 것
- 켜는 곳은 한 곳: `robot_manager.py:506-547` `start_slide_force`(SLIDE 전용, :479). **호출을 보내기 전에** 해제 대상으로 표시한다(:532 · :540). 켜기 응답이 시간 초과여도 해제를 부른다.
- 해제: `execute_motion` 의 `try / except Exception / finally` (:433-445) → `release_all` (:778-808). 힘 → 램프 대기 → 순응 순서(:785-807).
- 종료 경로별: 정상(EDGE · 도착) `:587-588 · 605-606`, cancel `:567-572`, `/robot/stop` `:573-586`, 과대 외력 · 접촉 `:652-669`, 하강 제한 `:589-594`, 제한 시간 `:595-601`, 연결 끊김 `:602-604`, 켜기 실패 `:479-481`, 이동 명령 실패 `:482-483`, 예외 `:435-438` — 전부 `run_motion` 의 return/raise 라서 `finally` 를 거친다.
- 필드: `RobotStatus.compliance_active` · `force_ctrl_active` 를 실제 상태로 채운다(`robot_manager.py:336-337`, 켜기 :532 · :540, 끄기 :789 · :804, 상태 키에 포함 :326). `ExecuteMotion.Result.compliance_released` = `release_all` 의 반환값(:440 · :848). 해제 호출이 실패하면 `false` 로 사실대로 보고하고 플래그도 true 로 남긴다(:790-792 · 805-807).
- scan_manager 는 `compliance_released=false` 면 더 진행하지 않는다(`sequence.py:154-158`, 시험 `test_sequence.py:233`).
- **시험**: `robot_manager/test/test_node.py:639-692` `test_force_control_is_released_on_every_exit_path` — `exception · cancel · stop_request · event · timeout · drop_limit · edge` 7경로를 매개변수로 돌리고 해제 호출 · 순서 · 램프 대기 · `compliance_released` · 두 플래그를 본다. `:696`(켜기 시간 초과 뒤에도 해제) · `:715`(해제 실패를 숨기지 않는다) · `:731`(DESCEND 는 힘 제어를 건드리지 않는다) · `:753`(release_force 시간 초과여도 램프를 기다린다). 기동 직후 플래그 false `:81-82`.

어긋나는 것
1. **[부분 · 가장 큼] 노드 종료 경로가 보장되지 않는다.** `robot_manager.py:852-864` `main` 은 `KeyboardInterrupt` 만 잡고 `destroy_node` → `rclpy.shutdown` 을 한다. `destroy_node` 재정의 · 종료 훅 · 시그널 처리가 없다(`grep destroy_node|shutdown|ExternalShutdown` 결과 :862 · :864 뿐). SLIDE 도중 Ctrl-C · launch 종료 · SIGTERM 이 오면:
   - rclpy 가 context 를 먼저 내린다. `watch` 스레드의 `finally` 는 돌지만 `release_all` → `call_sync` → `CallQueue.submit` 의 서비스 호출이 내려간 context 에서 나가지 못한다(응답을 받을 executor 도 멈췄다). `call_sync` 는 `service_timeout_s * 4 + 1.0` 을 기다리다 False 를 돌려준다(:820-823).
   - 결과: **컨트롤러에 순응 · 힘 제어가 켜진 채 노드가 끝날 수 있다.** 다시 띄운 노드는 `compliance_active=False` 로 시작하므로(:141-142) 상태도 거짓이 된다.
   - `ExternalShutdownException` 을 잡지 않아 SIGTERM 에서는 트레이스백이 난다(scan_manager · safety_monitor · contact_detector 는 잡는다: `scan_manager.py:1476`, `safety_monitor.py:271`, `contact_detector.py:329`).
   - 이 경로의 시험이 없다. 실제 동작(종료 시 해제 호출이 나가는지)은 **미확인** — Virtual 에서 SLIDE 중 SIGINT 를 주고 `dsr_controller2` 의 `release_compliance_ctrl` 호출 로그를 보면 확인된다. 단 Virtual 은 힘 제어가 정상 동작하지 않는다(BRD 위험 2).
2. **[부분] 해제에 실패한 뒤 다시 시도하는 경로가 없다.** `compliance_active=True` 로 남아도 `reject_reason` (:386-418)은 이것을 보지 않는다. 관제자의 HOME(OP_HOME)은 순응이 켜진 채 출발할 수 있다. 동작이 없을 때의 `/robot/stop` (`stop_idle` :727-735)도 `move_stop` 만 보내고 해제는 하지 않는다 — 계약 4.1 의 "move_stop → 순응 · 힘 제어 해제(finally)" 는 동작 중 경로에서만 성립한다. 해제 실패 보고는 계약 9장 TBD 다.
3. 참고: `except Exception` (:435)은 `BaseException` 을 잡지 않지만 `finally` 는 돈다. 해제는 보장되고 Result 만 못 만든다.

PR #127: robot_manager 를 건드리지 않는다. 영향 없음.

---

#### 규칙 9. 드라이버 호출은 robot_manager 만 — 일치

`grep -rE "dsr_msgs2|DSR_ROBOT2|DR_init|onrobot|dsr_controller2"` 전수(문서 제외)

| 구분 | 위치 | 내용 |
|---|---|---|
| 제품 코드 | `ws_cobot1/src/robot_manager/robot_manager/dsr_client.py:10-12` | `from dsr_msgs2.srv import …` — **유일한 import.** 서비스 10종(:24-35), 클라이언트 생성 :42-45 |
| 제품 코드 | `robot_manager/robot_manager/robot_manager.py:122` | `dsr_client.make_clients` 호출. 다른 모듈(`conversions.py` · `motions.py` · `call_queue.py` · `motion_state.py`)은 import 하지 않는다 |
| 시험 | `robot_manager/test/test_node.py:17` | `find_spec('dsr_msgs2')` 로 있을 때만 돈다. CI 는 고정 커밋으로 빌드(`.github/workflows/ci.yml:37-62`) |
| 시험 | `contact_detector/test/test_node.py:204-205` | `source='rg2'` 를 **거절하는지** 보는 시험. 드라이버 호출 아님 |
| docs/env 스크립트 | `docs/env/apply_tool_tcp.py:27`, `check_api_calls.py:39 · 43`(`onrobot_rg_msgs.srv.SetCommand`, `/onrobot/sendCommand` :46 · 328-332), `measure_idle_force.py:49`, `probe_point.py:28` | 환경 점검 · 실측용. 사람이 직접 돌린다. launch · 패키지 밖이다 |
| 의존 선언 | `robot_manager/package.xml:14-15`, `contact_scan_interfaces/package.xml:14` | 주석만. dsr 의존을 선언하지 않는다 |

- scan_manager · contact_detector · safety_monitor · mqtt_bridge · contact_scan_bringup · backend · frontend 에는 import · 서비스 이름 · 호출이 없다.
- **RG2(onrobot) 는 제품 코드 어디에서도 호출하지 않는다**(robot_manager 포함). 정의서 8.2 의 "탐침 파지 명령 `/onrobot/sendCommand`" 는 구현되지 않았다 — 파지는 사람이 미리 해 둔다는 전제로 보인다. 규칙("robot_manager 만 호출")에는 어긋나지 않는다. 파지 상실 감지는 정의서에서도 TBD 다.
- `DSR_ROBOT2` Python 래퍼는 쓰지 않는다(`dsr_client.py:5-6`, 서비스 직접 호출 + 시간 제한).

PR #127: 드라이버 import 추가 없음. 영향 없음.

---

#### 규칙 10. 중지는 홈 복귀 · 재시작을 부르지 않는다 — 일치

- scan_manager `/scan/stop`: `_on_stop` (`scan_manager.py:1029-1065`)은 STOP 요청 · `/robot/stop` · goal cancel 만 한다. HOME · RESUME 호출이 없다. cancel 로 작업을 멈추는 길도 막았다(`:257-259` `CancelResponse.REJECT`).
- 상태 기계: `Command.STOP` 의 갈 곳은 STOPPING 또는 제자리뿐(`state_machine.py:85-88`). STOPPING → STOPPED 는 `STOP_CONFIRMED` 신호로만 가고, STOPPED 에서 신호로 나가는 길이 없다. 시험 `test_commands.py:35 · 44 · 49 · 55`.
- 시퀀스: `_finish_stop` (`sequence.py:394-400`)은 정지 확인 → 기록 → 통지로 끝난다. 실패(`_finish_fail` :402-404, `fail()` `scan_manager.py:1400-1419` "홈 복귀는 하지 않는다")도 복귀하지 않는다. 마무리 복귀는 GEOMETRY 성공 뒤에만 돈다(`sequence.py:417-433`, 계약 7.4). 시험 `test_sequence.py:165 · 216 · 292 · 339`.
- `_stop_untracked` (`scan_manager.py:1290-1296`)는 `/robot/stop` 만 부른다.
- robot_manager: 정지 뒤 자동 상승 · 홈이 없다(`stop_robot` :752-776, `release_all` :778-808 만). 계약 4.1 "자동 상승 · 홈 없음"과 같다.
- safety_monitor: `/safety/reset` 은 로봇을 움직이지 않는다(`safety_core.py:287-296`, 모션 클라이언트 자체가 없다 `safety_monitor.py:82-86`).
- mqtt_bridge: 명령 1개 → 호출 1개(`mqtt_bridge.py:334-359`). stop 뒤에 다른 goal 을 보내는 코드가 없다.
- 웹: FastAPI 는 엔드포인트마다 토픽 하나만 발행한다(`backend/app/main.py:460-488`, `publish_command` :395-446). React 의 `handleStop` 은 `sendScanCommand('stop')` 하나다(`frontend/src/App.jsx:339-341`). `sendScanCommand` 호출은 버튼 4개뿐이고(:335 · 340 · 345 · 350), `useEffect` 안에서 명령을 보내는 곳은 없다. Spring 에는 stop/home 관련 코드가 없다(`grep -il` 결과 없음).

비고: robot_manager 는 정지 확인에 실패해 남은 요청이 있어도 OP_HOME 을 받는다(`robot_manager.py:388-393 · 459-470`, #115). "중지가 홈을 부른다"가 아니라 "관제자가 누른 홈을 막지 않는다"이다. 규칙 10 위반이 아니다. 다만 정지를 확인하지 못한 채 출발할 수 있다(:467-469 "그대로 출발한다")는 점은 안전 검토 대상이다.

PR #127: 영향 없음.

---

#### 가장 심각한 발견

1. **robot_manager 종료 경로에서 순응 · 힘 제어 해제가 보장되지 않는다**(규칙 8). `robot_manager.py:852-864`. SLIDE 중 Ctrl-C · SIGTERM 이면 context 가 먼저 내려가 `release_all` 의 서비스 호출이 나가지 못한다. 종료 훅 · 시험 없음. BRD 4.5.2 · CLAUDE.md 규칙 2 의 "모든 종료 경로"에 해당한다. 소유: robot_manager 담당 → 이슈 초안 대상.
2. **mqtt_bridge 의 stop 완료 통지가 어긋난다**(규칙 4). `mqtt_bridge.py:417-427 · 491-508`. 정지 확인 실패(ERROR)는 `command_result` 가 안 나가고, 멈출 것이 없던 stop 의 request_id 는 나중의 무관한 STOPPED 에 `success=true` 로 나간다.
3. **래치가 프로세스 메모리에만 있고 scan_manager 가 `/safety/status` 최신성을 보지 않는다**(규칙 3 비고). `safety_core.py:262`, `scan_manager.py:422-432`. safety_monitor 가 죽으면 2차 감시 없이 시작이 접수된다.
4. **`MoveLine` 각속도 칸에 mm/s 값을 넣는다**(규칙 7). `dsr_client.py:87-89`. 가속도 배수 4 · 2 도 코드에 박혀 있다.
5. **해제 실패 뒤 재시도 · 차단이 없다**(규칙 8). `compliance_active=True` 로 남아도 다음 goal(특히 OP_HOME)을 받는다. `robot_manager.py:386-418 · 727-735`. 계약 9장 TBD 와 묶어 결정이 필요하다.

그 밖: `debounce_n` 미상 → 웹에 0 (규칙 6, `encoders.py:223`), goal 항상 accept 로 `cmd/ack accepted=true` 뒤에 거절이 오는 구조(규칙 3 비고 2), `RobotStatus.error` 가 항상 false (`robot_manager.py:334-335`), bringup 이 mqtt_bridge yaml 을 읽지 않음(규칙 1 비고).

#### 미확인 목록
- 종료 시 해제 호출이 실제로 나가는지(규칙 8-1): Virtual/실기에서 SLIDE 중 SIGINT 뒤 `dsr_controller2` 로그. 사람이 확인한다(실기 명령은 Claude 가 실행하지 않는다).
- `MoveLine.vel[1]` · `acc[1]` 의 뜻과 단위(규칙 7-1): dsr_msgs2 의 `MoveLine.srv` 정의 · `docs/env/api-check-log.md`.
- `compliance_stiffness` 6칸의 단위(규칙 7-2): 두산 매뉴얼 `task_compliance_ctrl`.


---

## 부록 D. 시나리오·연결선 추적

### Phase 5 — 시나리오 추적 + 연결 표 확인 (읽기 전용 감사)

- 대상 스냅샷: origin/main `717cbdd` (경로는 저장소 상대경로)
- 기준: `docs/design/contact-scan-interface-spec-integrated-v1.2.md` 1.1~1.10 · `docs/design/contact-scan-node-diagram-v1.1.md` 3 · 4장 · `docs/BRD.md` · (우선순위가 더 높은) `docs/contracts/ros-interfaces.md`
- 미병합 PR #127(`origin/t109-descend-tare-slide-arm`)은 `git diff origin/main...` 로만 읽었다. 판정은 main 기준, 브랜치 영향은 D절.
- 판정 등급: `일치` · `부분` · `불일치` · `누락`. 설계서의 `제안(TBD)` 와 다르게 구현된 것은 **[미결의 사실상 결정]** 으로 표기.
- 실행(ros2 · 로봇 · 빌드)은 하지 않았다. 모든 판정은 코드 정독 근거다. sim 종단이 실제로 돈 기록은 `docs/test-reports/daily/20260921.md:22-39`(M2, `ros2 action send_goal` 기준) 뿐이며, 이번 감사에서 재현하지 않았다.

#### 0. 선 수에 대한 사실

사용자 지시문은 "39선(자체 27 · 표준 2 · 외부 8 · 검토안 2)"이라 했지만, 저장소의 v1.1 문서는 **40선(자체 27 · 표준 3 · 외부 8 · 검토안 2)** 이다.
- `docs/design/contact-scan-node-diagram-v1.1.md:183` "표준 ROS 인터페이스 연결 — 3선 (… P03은 v1.1 추가)"
- `docs/design/contact-scan-node-diagram-v1.1.md:211` "합계: … = **40선**", `:272` "선 수 39 → 40"
- 39선은 v1.0 기준 수치다. 아래 B절은 40선 전부를 확인했다.

---

#### A. 시나리오 10개

공통 웹 진입 경로(1.1 · 1.4 · 1.5 · 1.6 에 공통): React 버튼 `frontend/src/App.jsx:830-842` → `fetch('/commands/scan/<action>')` `frontend/src/App.jsx:287-288` → FastAPI `backend/app/main.py:450-488` → `publish_command` `backend/app/main.py:390-416`(schema_version · UUID4 request_id · timestamp_ms · payload) → mqtt_bridge 구독 `ws_cobot1/src/mqtt_bridge/mqtt_bridge/mqtt_bridge.py:281-286` → 큐 → `_handle_mqtt` `:309-364`(CommandGuard `command_guard.py:54-103`).

##### 1.1 작업 시작 — 종합 **부분**

| # | 기대(정의서 1.1 · 구성도 4장) | 실제 | 판정 | 근거 |
|---|---|---|---|---|
| 1 | 웹 `cmd/scan/start {request_id}` | React 시작 버튼 → FastAPI → MQTT qos1 | 일치 | `frontend/src/App.jsx:334-336`, `backend/app/main.py:450-457` |
| 2 | mqtt_bridge ⇒ `/scan/run` goal | `RunScan.Goal` 조립 후 `send_goal_async` | 일치 | `mqtt_bridge.py:334-340`, `:366-371` |
| 3 | `cmd/ack`(접수/거절) = goal 수락/거절 | scan_manager 는 goal 을 **항상 ACCEPT** 하고, 거절은 `Result(success=false, reason_code=1xx)` + abort 로 돌려준다. 그래서 BUSY · SAFETY_LATCHED · ROBOT_DISCONNECTED 거절도 `cmd/ack accepted=true` 뒤 `scan/command_result success=false` 로 나간다. 계약 5.1("진행 중이면 goal 거절 BUSY")·mqtt-schema 45행과 표현이 다르다 | **부분** | `scan_manager.py:257`, `:612-628`(이유 주석), `mqtt_bridge.py:379-389`, `docs/contracts/ros-interfaces.md:419` |
| 4 | 시작 조건: connected · latched=false · 동시 작업 없음 | 상태 기계 `_check`: 미수신(None)도 거절. busy 는 락 밖 1회 + 락 안 1회 | 일치 | `state_machine.py:326-336`, `scan_manager.py:696-698`, `:711-713`, `:426-432` |
| 4' | (추가) 1차·2차 감시값 불일치면 시작 거절 | START 직전 세 노드 되읽기 → `pair_mismatches` → `PARAM_SET_FAILED` | 일치(계약 7.2 보강) | `scan_manager.py:699-707` |
| 5 | scan_id 발급 → `/scan/state` PREPARING | 벽시계+난수, 기존 디렉터리와 충돌 검사 → START 전이 → on_change 발행 | 일치 | `scan_manager.py:131-133`, `:731-746`, `:342-344`, `state_machine.py:340-346` |
| 6 | `/contact/tare` → **그 다음** MOVE_TO 기준점 상공 → DESCEND | 실제 순서는 **MOVE_TO(to_origin) → 정지 확인(wait_still) → tare → PREPARE_DONE → DESCEND**. 설계서와 tare·MOVE_TO 순서가 반대다. BRD 4.1.3("접촉 직전 비접촉·정지 1~2 s")에는 코드 쪽이 더 가깝고, 계약 7장에는 순서 규정이 없다 | **부분(순서 상이)** | `sequence.py:448-461`, `docs/BRD.md:240` |
| 7 | tare 실패(툴 등록 이상)면 실패 | `TOOL_REG_SUSPECT`·`TARE_UNSTABLE`·`TARE_TIMEOUT`·`NO_SAMPLE` → `_Fail` → ERROR | 일치 | `detector_core.py:365-373`, `contact_detector.py:80-85`, `:278-322`, `scan_manager.py:1310-1326`, `sequence.py:459-461` |
| 8 | motion_id 발급, MOVE_TO → Result TARGET_REACHED | `itertools.count`, 도착 허용치까지 검사 | 일치 | `sequence.py:335`, `:356`, `robot_manager.py:629-642` |
| 9 | DESCEND → phase=TOP_SEARCH | PREPARE_DONE 에서 TOP_SEARCH, 이어서 `descend()` goal | 일치 | `state_machine.py:93`, `sequence.py:463-468`, `:67-70` |
| 10 | robot_manager → dsr_msgs2 | `motion/move_line`(ASYNC, 상대 −z) | 일치 | `robot_manager.py:486-504`, `dsr_client.py:82-91` |
| — | 동시 작업 제한 파라미터 `allow_concurrent`(구성도 1.1) | 파라미터 없음. 항상 1개로 고정 | 누락(경미) | `ws_cobot1/src/scan_manager/scan_manager/params.py:90-121`(SPECS 에 없음) |

##### 1.2 접촉 판정(DESCEND) — 종합 **일치**

| # | 기대 | 실제 | 판정 | 근거 |
|---|---|---|---|---|
| 1 | `/robot/sample` 50 Hz 목표 → contact_detector | 타이머 50 Hz(실측 Virtual 37.6 · 실기 42.8 Hz), SENSOR QoS | 일치 | `robot_manager.py:79`, `:127`, `:158`, `:302`; `contact_detector.py:125`; `real.yaml:109` |
| 2 | 판정 모드 · motion_id 는 샘플에서 | `operation != OP_DESCEND` 면 CONTACT 안 함. 이벤트 motion_id = 판정(첫 성립) 샘플의 값 | 일치 | `detector_core.py:247-250`, `contact_detector.py:260-263` |
| 3 | `/scan/state` 는 scan_id 태깅만 | `on_scan_state` 가 scan_id 만 저장 | 일치 | `contact_detector.py:126`, `:181-182`, `:257` |
| 4 | \|F−F₀\| > 임계, 연속 3회 | 성분별 차의 크기, `debounce_n` 연속, motion_id 당 1회 래치 | 일치 | `detector_core.py:251-260`, `:307-310`; `real.yaml:14`, `:21` |
| 5 | stale 판정 | `stale_age_ms` 넘게 묵은 샘플 폐기 + 간격 경고. 무효 샘플은 세지도 끊지도 않음 | 일치 | `contact_detector.py:186-198`, `detector_core.py:213-215` |
| 6 | CONTACT 이벤트 즉시 발행(판정 샘플 pose · stamps) | first_sample 의 pose/wrench/stamp, 확정 샘플의 detect_stamp | 일치 | `contact_detector.py:251-274`, `:230-231` |
| 7 | robot_manager: motion_id 대조 + DESCEND 일 때만 → move_stop → Result{정지 pose, CONTACT} | 대조 → `motion.event` → watch → `stop_robot`(move_stop + moving=false 대기) → Result. 설계서의 "scan_id·motion_id 대조" 중 scan_id 는 보지 않지만 계약 5.4 는 motion_id 만 요구 | 일치(계약 기준) | `robot_manager.py:345-363`, `:587-588`, `:661-669`, `:752-776`, `:836-849`; `docs/contracts/ros-interfaces.md:504` |
| 8 | scan_manager: 판정 샘플 pose 로 z_top, 정지 pose 와 구분 | `Result.event_id` ↔ 이벤트 짝 맞춤, `Measurement(detection, stop_pose)` 분리 기록, 첫 접촉 z = 이벤트 z | 일치 | `event_matcher.py:56-89`, `scan_manager.py:1298-1305`, `:1328-1338`, `sequence.py:463-468` |
| 9 | mqtt_bridge 표시 | `contact/event` qos1, m→mm 변환 | 일치 | `mqtt_bridge.py:529-542`, `encoders.py:154-178` |
| 10 | 정지 완료 = `/robot/status` moving=false | robot_manager 가 Result 전에 같은 `moving` 근거로 기다림. 확인 못 하면 ROBOT_ERROR 로 격상 | 일치 | `robot_manager.py:765-772`, `:663-666` |
| — | 구성도 1.1 의 `filter_window` · `edge_force_drop_ratio` 파라미터(필터) | 구현 없음(grep 0건). 디바운스만 있다 | 누락(경미) | `contact_detector.py:52-67` |
| 실기 | 정지 상태 tare 의 F₀ 로 하강하면 이동 중 외력 치우침(약 2.3 N)으로 허공에서 거짓 CONTACT | main 에는 대책 없음(PR #127 대상) | 실기 위험 | `real.yaml:149-152` |

##### 1.3 엣지 판정(SLIDE) — 종합 **부분(경미)**

| # | 기대 | 실제 | 판정 | 근거 |
|---|---|---|---|---|
| 1 | 방향 전환: MOVE_TO ① lift ② 원점 상공 ③ 첫 접촉 z+margin 저속 내림(판정 안 함) | `change_direction` = lift + reapproach(2개). 속도는 ③만 `recontact_speed_mps`. 첫 방향은 DESCEND 접촉 자리에서 바로 민다(계약 7.3 "한 방향의 밀기가 끝나면"과 일치) | 일치 | `sequence.py:82-101`, `:441-446`, `:476-480` |
| 2 | SLIDE goal(direction, speed, max_distance, timeout) | `slide()` | 일치 | `sequence.py:72-76`, `conversions.py:101-120` |
| 3 | robot_manager: task_compliance_ctrl + set_desired_force(−z, 파라미터) + amovel · 하강 제한 5 mm | 순서대로 호출, `DR_FC_MOD_REL`, 하강 제한은 `start_z` 기준 `drop_limit_m` → `DROP_LIMIT(205)` | 일치 | `robot_manager.py:506-547`, `:589-594`, `dsr_client.py:103-114`; `real.yaml:81-82` |
| 4 | `/scan/state` EDGE_SEARCH · direction · progress n/4 · motion_id | `_enter` 가 progress 로 방향 결정, `set_motion_id` | 일치 | `state_machine.py:94-98`, `:387-390`, `:417-420`; `scan_manager.py:1226` |
| 5 | z 급강하 ≥0.5 mm(주) **+ 외력 감소(보조)** 연속 3회 | 주 신호는 "최근 구간 z 추세선 대비 하강 > edge_drop_m" + 누름 확인(arm) 후 판정, 디바운스 N. **보조 신호(외력 감소)는 쓰지 않는다**(코드 주석에 명시). 계약 9장에서 TBD 인 항목 | **부분 · [미결의 사실상 결정: 보조 신호 미사용]** (BRD 4.1.2 Must 문구와는 차이) | `detector_core.py:10-17`, `:262-305`; `docs/contracts/ros-interfaces.md:687`; `docs/BRD.md:239` |
| 6 | EDGE → robot_manager 정지 → 순응·힘 해제(finally) → Result{EDGE} | `finally: release_all` — force_off → ramp 대기 → compliance_off. 켜기 시간 초과도 해제 대상으로 표시 | 일치 | `robot_manager.py:433-445`, `:528-546`, `:778-808` |
| 7 | scan_manager: 판정 pose 기록 → progress+1 → 다음 방향 | `record_edge`(디스크 확인 후) → `EDGE_FOUND` | 일치 | `scan_manager.py:1340-1349`, `sequence.py:470-474` |
| 8 | 방향 순서 +x → −x → +y → −y | 기본값·yaml 모두 `[POS_X, NEG_X, POS_Y, NEG_Y]`. 계약에 순서가 없어 파라미터화 | 일치 | `state_machine.py:65-67`, `real.yaml:181`, `sim.yaml:177` |
| 9 | max_distance 안에 EDGE 없음 → MAX_DISTANCE → 실패 | `REASON_MAX_DISTANCE + NO_EDGE` → `_Fail(NO_EDGE)` → ERROR, 자동 복귀 없음 | 일치 | `robot_manager.py:626-628`, `sequence.py:197-198`, `:423-424` |
| 10 | 4/4 → GEOMETRY: 계산 → result_store 저장 → `/scan/result` 즉시 발행 | 저장 → 발행 순서 고정 | 일치 | `scan_manager.py:1369-1383`, `geometry_adapter.py:113-158`, `result_store/store.py:279` |
| 11 | HOMING: 팁 올림(MOVE_TO) → HOME, 정상 완료일 때만 | `_final_homing` 은 `_search`·`_geometry` 성공 뒤에만 | 일치 | `sequence.py:417-433`, `:492-497` |
| 12 | DONE: RunScan Result → `scan/command_result`, 결과 중복 방지 | Result 에서는 command_result 만 내고 ScanResult 는 `/scan/result` 토픽으로만 MQTT 에 나간다. dedup 키 `(scan_id, stamp)` | 일치 | `mqtt_bridge.py:391-402`, `:164-166`, `:510-517` |
| 13 | 마무리 복귀 실패: 측정 유효 · ERROR · success=false | `HOMING_FAILED` | 일치 | `sequence.py:431-432`, `scan_manager.py:671-685` |
| 실기 | SLIDE 의 실제 누름 = 호출 시점 기준선 + 목표(REL). 첫 방향은 접촉력 위에 더해짐. 값은 "잠정" | 미확정 파라미터 | 실기 위험 | `robot_manager.py:509-516`, `real.yaml:82-96`, `docs/env/api-check-log.md:18-19` |

##### 1.4 작업 중지(경로 ①) — 종합 **일치** (웹 결과 통지에 경미한 구멍)

| # | 기대 | 실제 | 판정 | 근거 |
|---|---|---|---|---|
| 1 | 웹 `cmd/scan/stop` → mqtt_bridge (만료 검사 제외) | stop 은 만료 검사에서 제외 | 일치 | `command_guard.py:96-97`, `mqtt_bridge.py:352-353`, `:404-415` |
| 2 | `/scan/stop` → accepted = 접수일 뿐 | 콜백은 상태 전이 + stop_event 세팅 + 비동기 요청만 하고 바로 응답. 아무것도 기다리지 않는다 | 일치 | `scan_manager.py:1029-1065` |
| 3 | goal cancel(제안 #21) + `/robot/stop` 병행 | 둘 다 보낸다(`call_async` + `cancel_goal_async`). **[미결 #21 의 사실상 결정: cancel + /robot/stop 병행]** — 계약 7.1 과 같다 | 일치 | `scan_manager.py:1051-1055`, `:1067-1074`; `docs/contracts/ros-interfaces.md:633` |
| 4 | robot_manager: move_stop → 순응·힘 해제(finally) | watch 가 cancel/stop 요청을 보고 `stop_robot` → finally `release_all` | 일치 | `robot_manager.py:567-586`, `:671-707`, `:439-445` |
| 5 | `/robot/status` moving=false 로 **완료** 확인 → STOPPED | `wait_still`: 요청 **이후에 찍힌** status 로만 통과 → `record_stop` → `STOP_CONFIRMED`. 확인 못 하면 ERROR(`ROBOT_STATUS_LOST`) | 일치 | `scan_manager.py:461-478`, `sequence.py:394-400` |
| 6 | 중단 위치 = ExecuteMotion Result.pose, 측정값 보존 | `record_stop(Interruption(..., pose))`, 중지 뒤 도착한 측정값은 버림(T26 결정) | 일치 | `scan_manager.py:1421-1438`, `sequence.py:385-391` |
| 7 | 홈 복귀 · 재시작 자동 실행 없음 | 전이표에 STOPPING → STOPPED/ERROR 뿐. `_on_stop` 에 HOME/RESUME 호출 없음. Action cancel 은 REJECT(중지는 /scan/stop 하나) | 일치 | `state_machine.py:85-88`, `:102-105`, `scan_manager.py:258-259` |
| 8 | mqtt_bridge `scan/command_result` | `phase=STOPPED` 전이 때 pending stop 을 완료 처리 | 일치 | `mqtt_bridge.py:417-427`, `:501-508` |
| 구멍 | 정지 확인 실패로 ERROR 가 되거나, 멈출 작업이 없는 휴지 phase(IDLE·DONE·ERROR)에서 stop 을 접수한 경우 | `_pending_stop` 이 STOPPED 가 올 때까지 남아 그 request 의 `scan/command_result` 가 **나가지 않는다**(나중의 다른 STOPPED 때 엉뚱한 scan_id 로 나감) | 부분(경미) | `mqtt_bridge.py:424-427`, `:504-508` |

##### 1.5 안전복귀 — 종합 **일치**

| # | 기대 | 실제 | 판정 | 근거 |
|---|---|---|---|---|
| 1 | 웹 `cmd/scan/home` ⇒ `/scan/home` | | 일치 | `backend/app/main.py:470-477`, `mqtt_bridge.py:341-345` |
| 2 | phase=HOMING, 동작 중 거절 | REST_PHASES 에서만, 미연결이면 거절. **래치는 안전복귀를 막지 않는다** | 일치 | `state_machine.py:89`, `:331-335`, `scan_manager.py:810-833`, `sequence.py:603-604` |
| 3 | 측정값 · 로그 보존 | 기록에는 `record_home_requested/finished` 만 덧붙인다. 프로세스 재시작 뒤에도 기록에서 상태를 되돌린 뒤 같은 기록에 남긴다 | 일치 | `scan_manager.py:834-853`, `:989-1025`, `result_store/store.py:239` |
| 4 | ExecuteMotion HOME → `home_pose` 파라미터로 이동 | robot_manager 파라미터 **`home_joint_deg`(관절각) + move_joint**. 설계서의 `home_pose` 와 이름·형식이 다름. **[미결 #19 의 사실상 결정: goal 필드가 아니라 robot_manager 파라미터(관절각)]** | 일치(이름 다름) | `robot_manager.py:96`, `:200-209`, `:489-492`; `real.yaml:77` |
| 5 | Result → ReturnHome Result → `scan/command_result` | `final_pose` 없으면 NaN | 일치 | `scan_manager.py:865-870`, `mqtt_bridge.py:391-402` |
| 6 | 남은 정지 요청이 안전복귀를 막지 않음(#115) | OP_HOME 은 stop_requested 가 남아도 수락, 출발 전 정지 재시도 | 일치 | `robot_manager.py:388-393`, `:459-470` |
| 실기 | 안전복귀는 **OP_HOME 하나만** 보낸다(들어 올림 없음 · 경로 TBD). 팁이 윗면/모서리에 닿은 채 중지된 자세에서 관절 이동이 바로 나간다. J6 −204.84° 경고도 있다 | 실기 위험(설계 TBD) | `sequence.py:598-607`, `real.yaml:77-79` |
| 실기 | `motion_timeout_s` 없으면 안전복귀도 거절 — real.yaml 에 60.0 이 있어 통과 | 확인 | `scan_manager.py:816-821`, `real.yaml:141` |

##### 1.6 재시작 — 종합 **일치**

| # | 기대 | 실제 | 판정 | 근거 |
|---|---|---|---|---|
| 1 | 웹 `cmd/scan/resume {request_id, scan_id}` | React 는 마지막 `scan/state` 의 scan_id 를 싣는다. scan_id 는 최상위 필드(mqtt-schema 72행과 일치) | 일치 | `frontend/src/App.jsx:281-284`, `backend/app/main.py:408-409`, `:480-488`, `decoders.py:95-100` |
| 2 | **별도 Action** `/scan/resume`(결정 #1) | 독립 ActionServer · 독립 execute | 일치 | `scan_manager.py:263`, `:887-904` |
| 3 | result_store 진행 기록 확인 | 접수 **전에** 기록 로드 · `plan_resume`. 메모리가 아니라 기록이 기준. 프로세스 재시작 뒤에도 `_adopt_recorded_scan` | 일치 | `scan_manager.py:906-987`, `resume.py:138-207` |
| 4 | latched=false 확인 | START 와 같은 `_check` + 1차/2차 값 불일치 검사 | 일치 | `state_machine.py:326-330`, `scan_manager.py:919-927` |
| 5 | 기존 측정값 유지 · scan_id 유지 · RESUMING | `job.top/edges` 를 기록에서 복원, 확정 방향에는 모션을 보내지 않음, `_catch_up` | 일치 | `scan_manager.py:971-975`, `sequence.py:552-590` |
| 6 | 중단 방향부터 1.3 계속 | 올림 → 정지 확인 → tare → 원점 재접근 → `remaining` 방향을 처음부터 민다(중단 x·y 로 돌아가지 않음) | 일치 | `sequence.py:559-570` |
| 7 | 안전복귀 후 재접근 TBD → 거절 | `moved_since_stop` → `NOT_SUPPORTED`; 기록 못 남긴 복귀도 거절; ERROR 작업 재시작도 `NOT_SUPPORTED`(TBD) | 일치(BRD 4.4.9) | `state_machine.py:311-324`, `scan_manager.py:938-942`, `resume.py:153-158` |
| 8 | 마무리 HOMING 중 중지는 재시작 대상 아님 | `NO_RESUMABLE_SCAN` | 일치 | `state_machine.py:351-353`, `resume.py:157-158` |

##### 1.7 안전 이상 정지(경로 ③) — 종합 **부분**

| # | 기대 | 실제 | 판정 | 근거 |
|---|---|---|---|---|
| 1 | `/robot/sample` · `/robot/status` → safety_monitor | 구독함 | 일치 | `safety_monitor.py:83-84` |
| 2 | `/scan/state` → safety_monitor (단계별 한계) | **구독 없음**. 단계는 샘플의 operation 으로만 본다 | **누락** (L10) | `safety_monitor.py:82-89` |
| 3 | `/web/heartbeat` → safety_monitor | **구독 없음**. mqtt_bridge 는 발행하지만 받는 곳이 없고, 웹 스택에도 `hb/web` 발행자가 없다(grep 0건) | **누락** (L26) | `mqtt_bridge.py:239`, `:312-320`; `backend/app/main.py:31-39`(발행 없음) |
| 4 | 감시 조건: 과대 외력 · 속도 · 하강/작업영역 · 샘플 stale · 로봇 연결 · HB 만료 | 구현: **과대 외력 · SLIDE 하강 제한 · 샘플 stale · status 미수신** 4개. **속도 · 작업영역 · max_descend · HB 만료는 없음**(파라미터도 없음). stale 2종은 이동 중일 때만 정지 | **부분** | `safety_core.py:26-30`, `:123-187`, `:88-91`; `safety_monitor.py:41-52`, `:164-171` |
| 5 | `/robot/stop` 즉시 · 로컬 · 웹 경유 없음 | 직접 서비스 클라이언트, 비동기 호출, 미확인 시 느린 재요청 | 일치 | `safety_monitor.py:85`, `:176-189`, `:144-154` |
| 6 | 래치 설정 | `note()` — 첫 원인 유지, `/safety/reset` 으로만 해제(파라미터로 못 품) | 일치 | `safety_core.py:282-286`, `safety_monitor.py:107-108`, `:164-169` |
| 7 | `/safety/status`(STOP, reason, stop_required, latched) 변경 시 | 변경 시 + 주기, `stop_confirmed` 포함 | 일치 | `safety_monitor.py:218-262` |
| 8 | robot_manager 정지 | 동작 중이면 watch, 없으면 `stop_idle` 스레드. 미확인 요청이 남으면 다음 goal 거절(HOME 제외) | 일치 | `robot_manager.py:671-707`, `:727-750`, `:388-393` |
| 9 | scan_manager: 작업 중단 처리(1.4 의 정지 확인과 동일) · 재시작 거절 | `/safety/status` 는 **저장만** 한다. 진행 중 작업은 robot_manager Result(STOP_REQUESTED, 요청 안 함) → `classify` → **FAILED → ERROR**. 실패 경로에는 `wait_still` 이 없다(정지 확인은 robot_manager 의 stop_robot 에 의존). 모션 사이에는 `safety_reason_code` 로 다음 모션 차단. 래치 중 START/RESUME 거절 | 부분 | `scan_manager.py:422-424`, `:434-439`; `sequence.py:161-169`, `:351-355`, `:402-404`; `state_machine.py:326-330` |
| 10 | 실패 사유 기록 | SafetyStatus(latched)가 Result 보다 늦게 오면 사유가 안전 코드 대신 `ROBOT_ERROR(204)` 로 남는다(Result.reason_code 의 4xx 는 detail 에만 들어감) | 부분(경합) | `sequence.py:164-169`, `robot_manager.py:585-586` |
| 11 | 정지 완료 확인(safety_monitor) | `/robot/status` connected && !moving → `stop_confirmed` | 일치 | `safety_core.py:234-239`, `safety_monitor.py:135-142` |

##### 1.8 설정 등록 — 종합 **부분** (ROS 구간 일치, 웹 UI 없음)

| # | 기대 | 실제 | 판정 | 근거 |
|---|---|---|---|---|
| 1 | 웹 `cmd/scan/set_config` | FastAPI REST 는 있다. **React 에 설정 화면·버튼이 없다**(버튼 4개: 시작·중지·안전복귀·재시작) | 부분 | `backend/app/main.py:491-498`, `frontend/src/App.jsx:830-842` |
| 2 | mqtt_bridge → `/scan/set_config`, mm→m · `*_set` 플래그 | 허용 키 검사, 단위 변환 | 일치 | `decoders.py:10-62`, `mqtt_bridge.py:429-438` |
| 3 | 동작 중 거절(phase ∉ {IDLE, DONE, ERROR, STOPPED}) | `SET_CONFIG: _same(REST_PHASES)` → 그 밖은 `BUSY` | 일치 | `state_machine.py:54`, `:83`, `:310-316`; `scan_manager.py:1102-1112` |
| 4 | 자체 값 갱신 | 모션 6개만 `_config` 에 반영, 범위 밖이면 전체 미적용 | 일치 | `scan_manager.py:1105-1116`, `params.py:85-88` |
| 5 | SetParameters 전파 P01~P03(결정 #16) | 순서 safety_monitor → contact_detector → robot_manager, 부분 실패는 되돌리지 않고 `PARAM_SET_FAILED` + 되읽기 + 쌍 불일치 검사 | 일치 | `propagation.py:38-53`, `scan_manager.py:520-555`, `:1118-1133` |
| 6 | 수신 측 콜백 | contact_detector · safety_monitor 는 범위 검증 콜백. **robot_manager 는 콜백 없이** 매번 파라미터를 읽음(음수·0 도 set 자체는 성공, SLIDE goal 때 ≤0 만 거절; drop_limit_m 은 검증 없음) | 일치(검증 약함) | `contact_detector.py:132`, `:158-177`; `safety_monitor.py:89`, `:107-122`; `robot_manager.py:92-93`, `:399-400`, `:554` |
| 7 | 응답 `applied` → `cmd/ack` | applied = 되읽은 실제 값(모르면 NaN → JSON null). FastAPI 는 이 두 명령의 ack 를 최종으로 취급 | 일치 | `scan_manager.py:1145-1146`, `mqtt_bridge.py:440-447`, `backend/app/main.py:108-111` |

##### 1.9 과대 외력(경로 ②) — 종합 **일치** (경합 주의)

| # | 기대 | 실제 | 판정 | 근거 |
|---|---|---|---|---|
| 1 | contact_detector: 원시 \|F\| > 30 N, 모든 모드 | operation·F₀ 와 무관, `over_force_debounce_n`(=1) | 일치 | `detector_core.py:236-245`, `real.yaml:22-23` |
| 2 | robot_manager: 대조 없이 우선 정지 → Result OVER_FORCE | `on_event` 첫 분기. 단 **진행 중 goal 이 없으면 아무것도 하지 않는다**(정지 호출 없음) | 일치 | `robot_manager.py:348-351`, `:652-660` |
| 3 | scan_manager: 실패 · 원인·위치·단계 기록 | `classify` → `OVER_FORCE` → `fail()`(로그+기록+부분 결과 발행) | 일치 | `sequence.py:201-202`, `scan_manager.py:1400-1419` |
| 4 | safety_monitor 독립 감시 → `/robot/stop` + 래치(결정 #17) | 같은 원시 \|F\|, 같은 값 30.0 | 일치 | `safety_core.py:136-139`, `safety_monitor.py:156-172`; `real.yaml:49` |
| 5 | 두 임계값 동일 보장 | yaml 검사(test_config) + START/RESUME/SetConfig 때 되읽어 불일치면 거절 | 일치 | `scan_manager.py:702-706`, `propagation.py:56-59` |
| 주의 | 1차·2차가 같은 샘플에서 동시에 걸린다(confirm_n=1). robot_manager watch 는 `/robot/stop` 요청을 이벤트보다 **먼저** 본다 → Result 가 OVER_FORCE 가 아니라 STOP_REQUESTED(4xx) 로 끝나고, scan_manager 기록 사유가 래치 도착 시점에 따라 400 또는 204 가 된다(이슈 #53 미결) | 경합 | `robot_manager.py:573-588`, `sequence.py:161-169`, `real.yaml:57-58` |
| sim | safety_monitor 는 Virtual 의 원시 외력(≈0)을 보므로 sim 에서는 2차 경로가 실질적으로 시험되지 않는다 | 한계 | `contact_detector.py:208-214`, `safety_monitor.py:126-133` |

##### 1.10 안전 래치 해제 — 종합 **부분** (ROS 구간 일치, 웹 UI 없음)

| # | 기대 | 실제 | 판정 | 근거 |
|---|---|---|---|---|
| 1 | 웹 "안전 해제" 버튼 → `cmd/safety/reset` | FastAPI REST 는 있다. **React 에 버튼이 없고 `safety/status` 도 화면에 표시하지 않는다**(App.jsx 에 safety 문자열 0건) | 부분 | `backend/app/main.py:501-508`, `frontend/src/App.jsx:380-492`, `:830-842` |
| 2 | mqtt_bridge → `/safety/reset` | `cmd/safety/reset` 별도 구독 | 일치 | `mqtt_bridge.py:283`, `:356-357`, `:449-466` |
| 3 | 조건이 아직 참이면 거절(CONDITION_ACTIVE), 해소됐으면 latched=false | `watch.active` 가 비어야 성공. 멱등. 정지 미확인(UNCONFIRMED) 상태여도 조건만 해소되면 풀린다 | 일치 | `safety_core.py:288-296`, `safety_monitor.py:205-213` |
| 4 | `/safety/status`(OK, latched=false) → scan_manager · mqtt_bridge | 즉시 publish, scan_manager 는 다음 START/RESUME 에서 읽음 | 일치 | `safety_monitor.py:212`, `scan_manager.py:233-234`, `mqtt_bridge.py:544-552` |
| 5 | 로봇은 움직이지 않음 | reset 경로에 모션·stop 호출 없음 | 일치 | `safety_monitor.py:205-213` |

##### 시나리오 종합표

| 시나리오 | 종합 | 핵심 사유 |
|---|---|---|
| 1.1 작업 시작 | 부분 | tare ↔ MOVE_TO 순서가 설계서와 반대 · 거절이 goal reject 가 아니라 Result 로 나감(ack 는 accepted=true) |
| 1.2 접촉 판정 | 일치 | (필터 파라미터 미구현은 경미) 실기는 #109 거짓 CONTACT 위험 |
| 1.3 엣지 판정 | 부분(경미) | 외력 감소 보조 신호 미사용 [미결의 사실상 결정] |
| 1.4 작업 중지 | 일치 | stop 의 command_result 가 STOPPED 에만 묶여 있는 구멍(경미) |
| 1.5 안전복귀 | 일치 | HOME 목표 = `home_joint_deg` [미결 #19 사실상 결정]. 들어 올림 없는 단일 OP_HOME(경로 TBD) |
| 1.6 재시작 | 일치 | — |
| 1.7 안전 이상 | 부분 | L10 · L26 미구독, 속도/작업영역/하강/HB 감시 없음, scan_manager 는 ERROR 로만 처리 |
| 1.8 설정 등록 | 부분 | ROS 구간 일치, React UI 없음 |
| 1.9 과대 외력 | 일치 | 1차·2차 동시 발동 시 기록 사유 경합 |
| 1.10 래치 해제 | 부분 | ROS 구간 일치, React 버튼·safety 표시 없음 |

---

#### B. 연결 표 40선

판정어: 연결됨 / 끊김 / 방향 반대 / 이름 다름 / 미구현. QoS 는 전부 `contact_scan_qos` 의 공용 프로파일을 양쪽이 같이 써서 호환된다.
경로 접두: `SM`=`ws_cobot1/src/scan_manager/scan_manager/scan_manager.py`, `RM`=`ws_cobot1/src/robot_manager/robot_manager/robot_manager.py`, `CD`=`ws_cobot1/src/contact_detector/contact_detector/contact_detector.py`, `SAF`=`ws_cobot1/src/safety_monitor/safety_monitor/safety_monitor.py`, `MB`=`ws_cobot1/src/mqtt_bridge/mqtt_bridge/mqtt_bridge.py`.

##### B.1 자체 27선

| # | 이름 | 종류 | 발신→수신 | 발신 측 | 수신 측 | 판정 |
|---|---|---|---|---|---|---|
| L01 | `/scan/run` | 자체 A | MB→SM | `MB:240`, `:334-340` | `SM:254-264`(261), `:632` | 연결됨 |
| L02 | `/scan/home` | 자체 A | MB→SM | `MB:241`, `:341-345` | `SM:262`, `:810` | 연결됨 |
| L03 | `/scan/resume` | 자체 A | MB→SM | `MB:242`, `:346-351` | `SM:263`, `:887` | 연결됨 |
| L04 | `/scan/stop` | 자체 S | MB→SM | `MB:243`, `:404-415` | `SM:265`, `:1029` | 연결됨 |
| L05 | `/scan/set_config` | 자체 S | MB→SM | `MB:244`, `:429-438` | `SM:268-270`, `:1090` | 연결됨 |
| L06 | `/scan/state` | 자체 T | SM→MB | `SM:220`, `:329-340` | `MB:213-217`, `:491-502` | 연결됨 |
| L07 | `/scan/result` | 자체 T | SM→MB | `SM:221`, `:794-797` | `MB:218-222`, `:510-517` | 연결됨 |
| L08 | `/scan/log` | 자체 T | SM→MB | `SM:222`, `:376-399` | `MB:223-227`, `:519-527` | 연결됨 |
| L09 | `/scan/state` | 자체 T | SM→CD | `SM:220` | `CD:126`, `:181-182` | 연결됨 |
| L10 | `/scan/state` | 자체 T | SM→SAF | `SM:220` | **없음** (`SAF:82-89` 구독은 sample·status 뿐) | **끊김(수신 측 미구현)** |
| L11 | `/robot/execute_motion` | 자체 A | SM→RM | `SM:237-238`, `:1237` | `RM:164-169`, `:420` | 연결됨 |
| L12 | `/contact/tare` | 자체 S | SM→CD | `SM:239`, `:1315-1316` | `CD:130-131`, `:278` | 연결됨 |
| L13 | `/robot/sample` | 자체 T | RM→CD | `RM:127`, `:302` | `CD:125`, `:184` | 연결됨 |
| L14 | `/robot/sample` | 자체 T | RM→SAF | `RM:127` | `SAF:83`, `:126` | 연결됨 |
| L15 | `/robot/sample` | 자체 T | RM→MB | `RM:127` | `MB:203-207`, `:468-479`(10 Hz 다운샘플) | 연결됨 |
| L16 | `/robot/status` | 자체 T | RM→SM | `RM:128`, `:329-342` | `SM:231-232`, `:417-420` | 연결됨 |
| L17 | `/robot/status` | 자체 T | RM→SAF | `RM:128` | `SAF:84`, `:135-142` | 연결됨 |
| L18 | `/robot/status` | 자체 T | RM→MB | `RM:128` | `MB:208-212`, `:481-489` | 연결됨 |
| L19 | `/contact/event` | 자체 T | CD→RM | `CD:124`, `:230-231` | `RM:129-130`, `:345-363` | 연결됨 |
| L20 | `/contact/event` | 자체 T | CD→SM | `CD:124` | `SM:235-236` → `event_matcher.py:56` | 연결됨 |
| L21 | `/contact/event` | 자체 T | CD→MB | `CD:124` | `MB:228-232`, `:529-542` | 연결됨 |
| L22 | `/robot/stop` | 자체 S | SM→RM | `SM:240-241`, `:1067-1074` | `RM:163`, `:671` | 연결됨 |
| L23 | `/robot/stop` | 자체 S | SAF→RM | `SAF:85`, `:176-189` | `RM:163`, `:671` | 연결됨 |
| L24 | `/safety/status` | 자체 T | SAF→SM | `SAF:82`, `:255-262` | `SM:233-234`, `:422-424` | 연결됨 |
| L25 | `/safety/status` | 자체 T | SAF→MB | `SAF:82` | `MB:233-237`, `:544-552` | 연결됨 |
| L26 | `/web/heartbeat` | 자체 T(점선) | MB→SAF | `MB:239`, `:312-320`(hb/web 실수신 시에만 — 규칙은 지킴) | **없음** (`SAF:82-89`) | **끊김(수신 측 미구현)**. 상류 `hb/web` 발행자도 웹 스택에 없다 |
| L27 | `/safety/reset` | 자체 S | MB→SAF | `MB:245`, `:449-458` | `SAF:86`, `:205-213` | 연결됨 |

##### B.2 표준 ROS 3선

| # | 이름 | 발신→수신 | 발신 측 | 수신 측 | 판정 |
|---|---|---|---|---|---|
| P01 | `/robot_manager/set_parameters` | SM→RM | `SM:244-250`, `:541-544`; `propagation.py:49-52`(target_force_n → `slide_target_force_n`) | `RM:92-93` 선언, 사용 `RM:542`, `:554`(매번 읽음 · 검증 콜백 없음) | 연결됨 |
| P02 | `/contact_detector/set_parameters` | SM→CD | `propagation.py:43-48` | `CD:132`, `:158-177` | 연결됨 |
| P03 | `/safety_monitor/set_parameters` | SM→SAF | `propagation.py:39-42` | `SAF:89`, `:107-122` | 연결됨 |

(추가 구현: 같은 세 노드에 `get_parameters` 되읽기 `SM:248-249`, `:557-580` — 연결 표에는 없는 선이지만 표준 서비스이고 계약 7.2 보강용이다. 범위 초과로 보지 않았다.)

##### B.3 외부 8선

| # | 연결 | 발신→수신 | 코드 | 판정 |
|---|---|---|---|---|
| X01 | MQTT `cmd/scan/+` · `hb/web` · `conn/web` | Broker→MB | `MB:281-286`(+`cmd/safety/reset`), 처리 `MB:309-364`. `conn/web` 은 검증만 하고 버린다(`MB:322-324`) | 연결됨 (단 `hb/web`·`conn/web` 은 보내는 쪽이 없음) |
| X02 | MQTT `robot/…` `scan/…` `contact/event` `safety/status` `cmd/ack` `scan/command_result` `hb/ros` `conn/ros` | MB→Broker | `MB:479`, `:489`, `:500`, `:517`, `:527`, `:542`, `:552`, `:554-560`, `:562-568`, `:570-572`, `:255-260`·`:287` | 연결됨 |
| X03 | MQTT 발행/구독 | FastAPI↔Broker | 구독 `backend/app/main.py:31-39`, `:201-206`; 발행 `:411-416`; DB 쓰기 `:233-265` | 연결됨 (부분: `hb/web` · `conn/web` 미발행) |
| X04 | `dsr_msgs2` 서비스 | RM→두산 | `dsr_client.py:24-35`, `:42-45`. amovel = `motion/move_line` `sync_type=ASYNC`(`dsr_client.py:82-91`). `check_position_condition` 은 **의도적으로 미사용**(`docs/env/api-check-log.md:103`), 대신 `move_joint` · `get_robot_state` 추가 | 연결됨 (이름 다름: amovel → move_line ASYNC, 경로 `/dsr01/dsr_controller2/...`) |
| X05 | 로봇 상태 · TCP/힘 응답 | 두산→RM | `RM:225-252`, `dsr_client.py:60-79` | 연결됨 |
| X06 | `/onrobot/sendCommand` | RM→RG2 드라이버 | **코드 없음**(ws_cobot1/src 전체 grep `onrobot|rg2|sendCommand` 0건). `rg2_grip_*` 파라미터도 없음. 실기는 탐침을 이미 파지한 상태로 운용(`docs/env/api-check-log.md:22`) | **미구현** |
| X07 | DRCF TCP/IP | 두산 드라이버↔컨트롤러 | 저장소 밖 | 미확인(외부) — `docs/env/api-check-log.md:5` 의 Real 브링업 로그가 간접 근거 |
| X08 | RG2 명령·상태 | RG2 드라이버↔RG2 | 저장소 밖. X06 미구현이라 자체 시스템에서 이 경로를 구동하는 코드는 없다 | 미확인(외부) |

##### B.4 검토안 2선

| # | 이름 | 코드 | 판정 |
|---|---|---|---|
| C01 | `/scan/calibrate` (A) | 인터페이스 정의도 클라이언트/서버도 없음(`contact_scan_interfaces/action/` 4개뿐, grep `calibrat` 0건) | 미구현 — **정상(범위 초과 없음)** |
| C02 | `/calibration/result` (T) | 없음 | 미구현 — **정상(범위 초과 없음)** |

##### B.5 집계 (40선)

| 판정 | 개수 | 선 |
|---|---|---|
| 연결됨 | 33 | L01~L09, L11~L25, L27 (25) · P01~P03 (3) · X01~X05 (5; X04 는 이름 다름 병기, X01·X03 은 hb/web·conn/web 발행자 부재 병기) |
| 끊김 | 2 | **L10**(`/scan/state`→safety_monitor), **L26**(`/web/heartbeat`→safety_monitor) — 둘 다 safety_monitor 가 구독하지 않음 |
| 미구현 | 3 | **X06**(RG2 파지), C01 · C02(검토안 — 정상) |
| 미확인(외부) | 2 | X07 · X08 (저장소 밖) |
| 방향 반대 | 0 | — |
| 범위 초과(검토안 구현) | 0 | — |

---

#### C. M4 종단 경로

"웹 시작 버튼 → mqtt_bridge → /scan/run → 5점 탐색 → geometry_estimator → result_store → /scan/result → mqtt_bridge → FastAPI → React 3D 직육면체"

| # | 단계 | sim 경로 | 실기 경로 | 근거 |
|---|---|---|---|---|
| 1 | React 시작 버튼 → REST | 이어짐 | 이어짐 | `frontend/src/App.jsx:830`, `:334-336`, `:287-288`; dev 프록시 `frontend/vite.config.js`(`/commands`·`/ws` → 127.0.0.1:8000) |
| 2 | FastAPI → MQTT `cmd/scan/start` | 이어짐 | 이어짐 | `backend/app/main.py:450-457`, `:390-416` |
| 3 | Broker → mqtt_bridge | 이어짐(같은 PC) | **2 PC 구성이면 설정 필요**: `broker_host` 기본값이 127.0.0.1 이고 bringup yaml 에 mqtt_bridge 절이 주석이며 launch 인자도 없다. 패키지의 `config/mqtt_bridge.yaml` 은 bringup 이 읽지 않는다. 또 `cmd_expiry_s`=5 s 는 두 PC 시계 차에 민감 | `mqtt_bridge.py:173-179`, `real.yaml:186`, `sim.yaml:182`, `bringup.launch.py:56-63`, `mqtt_bridge/config/mqtt_bridge.yaml:3`, `command_guard.py:99-101` |
| 4 | mqtt_bridge → `/scan/run` | 이어짐 | 이어짐 | `mqtt_bridge.py:334-340` |
| 5 | scan_manager START 접수 | 이어짐 | **막힘 ①**: `search_origin_pose` · `base_to_fixture` 가 real.yaml 에서 주석 → 필수값 검사 → `INVALID_VALUE` 거절(의도한 fail-safe). 켜는 조건 = #109 해결 + 새 탐침 TCP x·y 확인 | `real.yaml:148-160`, `params.py:102-105`, `scan_manager.py:725-727` |
| 6 | 5점 탐색(윗면 1 + 모서리 4) | 이어짐 — sim 입력원이 샘플의 외력·z 를 가상 박스 값으로 바꿈. M2 통과 기록 | **막힘 ②**(①을 풀어도): 정지 tare 의 F₀ 로는 하강 중 거짓 CONTACT(#109) → 허공 SLIDE 위험. **막힘 ③**: `slide_target_force_n` 잠정 · REL 기준선 문제, `detect_latency_s` 미실측, `edge_bias_offset_m` = 0(미측정), `edge_drop_m` 0.5 mm 재검토 필요 | `sim_source.py:88-107`, `docs/test-reports/daily/20260921.md:22-39`; `real.yaml:18-20`, `:82-96`, `:149-154`, `:162-167`, `:173-174` |
| 6' | 실기 모션 구현 여부 | — | MOVE_TO · DESCEND · SLIDE · HOME 모두 실제 dsr 호출로 구현돼 있다(미구현 모션 없음). `move_line` 은 특이점 근처에서 success=true 인데 안 움직일 수 있고, 그때는 `arrival_tolerance_m` 검사로 ROBOT_ERROR 가 된다 | `robot_manager.py:486-504`, `:629-642`, `docs/test-reports/daily/20260921.md:66-88` |
| 7 | geometry_estimator 계산 | 이어짐 | 이어짐(좌표 파라미터가 있어야 함) | `scan_manager.py:1369-1376`, `geometry_adapter.py:113-158` |
| 8 | result_store 저장 → `/scan/result` 발행 | 이어짐 | 이어짐 | `scan_manager.py:1375-1376`, `:794-797` |
| 9 | mqtt_bridge → MQTT `scan/result`(mm 변환, NaN→null) | 이어짐. retain=false 라 나중에 붙은 구독자는 못 받음 | 동일 | `mqtt_bridge.py:510-517`, `encoders.py:253-295` |
| 10 | FastAPI: WS 브로드캐스트 + DB 저장 | 이어짐. 단 결과 **조회 REST 가 없다**(GET 은 /health · /commands/{id} · /db/test 뿐, Spring 은 빈 골격) → 결과 발행 뒤 접속/새로고침한 브라우저는 결과를 받을 길이 없다 | 동일 | `backend/app/main.py:226-247`, `:342-346`, `:515-529`, `:556`; `backend/spring/src/main/java/com/weldmade/backend/WeldMadeApplication.java` |
| 11 | **React: 결과로 3D 직육면체 표시** | **끊김** — WebSocket 핸들러에 `scan/result` 분기가 없다(처리: scan/state · robot/sample · contact/event · scan/log · command/status). 화면의 직육면체는 **고정 크기 `BoxGeometry(2, 1, 1.2)`** 자리표시자다. vertices · edges · path_candidates · 치수를 쓰는 코드가 없다 | 동일 | `frontend/src/App.jsx:380-492`, `:598-616` |
| 11' | 좌표계 | 팁·접촉점은 Base(mm)×0.01 로 그리는데 고정 박스는 장면 원점에 있다 → 서로 떨어져 보인다. ScanResult 는 `workpiece_fixture` 프레임이라 표시 때 프레임 정렬이 필요 | 동일 | `frontend/src/App.jsx:720-729`, `:805-809`; `real.yaml:179` |

##### 끊기는 첫 지점

- **sim 경로: 단계 11 (React).** 1~10 은 코드상 끊김 없이 이어진다. `scan/result` 가 WebSocket 으로 브라우저까지 도착하지만 `frontend/src/App.jsx:380-492` 에 받는 분기가 없고, 3D 직육면체는 `frontend/src/App.jsx:598-616` 의 고정 상자다. → M4 의 마지막 고리("결과로 3D 직육면체 표시")가 **미구현**이다.
- **실기 경로: 단계 5 (scan_manager START 거절).** `real.yaml:155`, `:158` 의 `search_origin_pose` · `base_to_fixture` 가 주석이라 `/scan/run` 이 `INVALID_VALUE` 로 끝난다(의도한 fail-safe, 해제 조건은 `real.yaml:149-154`). 그 앞의 단계 3 은 2 PC 구성일 때만 설정 문제다.
- 실기에서만 막히는 지점 요약: ① 좌표 파라미터 미기재(START 거절) ② #109 거짓 CONTACT(정지 tare) — PR #127 대기 ③ SLIDE 누름 힘 · 지연 · 편향 · edge_drop 미확정 ④ 안전복귀가 들어 올림 없는 단일 OP_HOME(경로 TBD, J6 경고) ⑤ mqtt_bridge `broker_host` 가 bringup 에서 주입되지 않음 ⑥ X06 RG2 파지 명령 미구현(수동 파지 전제) ⑦ safety_monitor 의 속도·작업영역·하강(max_descend)·HB 감시 부재 — 부재가 없을 때 팁이 작업대까지 내려가는 것을 막는 것은 `max_descend_m` 하나뿐(`real.yaml:139`).

---

#### D. PR #127 (`origin/t109-descend-tare-slide-arm`)이 1.1~1.3 을 어떻게 바꾸는가

변경 파일 9개(계약 문서 2 · contact_detector 코드 2 · 테스트 2 · README · real.yaml · sim.yaml). scan_manager · robot_manager · 인터페이스 타입은 바뀌지 않는다(계약 v0.1.12, "타입 변경 없음 · scan_manager 절차 변경 없음").

| 시나리오 | main | PR #127 뒤 |
|---|---|---|
| 1.1 | tare(정지) 의 F₀ 가 하강 판정의 기준 | `/contact/tare` 호출 순서·시점은 그대로지만 **역할이 "툴 등록 점검 + 예비 기준"으로 내려간다**. 설계서 1.1 의 "tare = F₀ 설정" 설명과 어긋나므로 설계서 갱신이 필요(계약은 같은 PR 에서 갱신) |
| 1.2 | `\|F−F₀\|`(정지 F₀) > 임계 연속 N | DESCEND 가 시작될 때마다 `descend_tare_delay_s`(실기 6.0 s · sim 1.0 s) 뒤 `tare_duration_s` 동안 **이동 중 F₀ 를 자동으로 다시 잡고**, 그동안 **CONTACT 를 보류**한다(OVER_FORCE 는 계속 감시). 잡으면 그 값으로, 실패하면 정지 F₀ 로 판정(=main 동작, 거짓 CONTACT 위험이 되살아남). 보류 거리 = 하강 속도×(delay+duration) — 실기 3 mm/s 면 22.5 mm: 그 안에 윗면이 있으면 30 N 과대 외력만이 보호다 |
| 1.3 | EDGE 판정 켜기 = `\|F−F₀\| > edge_arm_force_n` 연속 N | `edge_arm_still_window_s > 0` 이면 **"z 멈춤 + x·y 이동"** 으로 켠다(F₀ 에 기대지 않음). z 급강하 판정식·디바운스·이벤트 형식은 그대로. `edge_arm_force_n` 은 yaml 에 남지만 쓰이지 않게 된다 |
| 공통 | — | contact_detector 필수 파라미터 5개 추가(`descend_tare_enabled` 등). 코드 기본값이 없으므로 **yaml 에 없으면 노드가 기동하지 않는다** → 개인 yaml 을 쓰는 사람은 병합 즉시 영향. sim.yaml 도 같은 경로를 타도록 바뀌므로 M2(sim 종단) **재실행 필요**. real.yaml 의 좌표 주석(막힘 ①)은 이 PR 에서도 그대로다(조건 ②가 남음). yaml 삽입 위치가 `tare_max_force_n` 주석 블록 중간이라 주석이 끊겨 읽힌다(표시상의 문제) |

판정에 미치는 영향: 1.2 · 1.3 의 "일치/부분" 등급은 바뀌지 않는다(선·순서·이벤트 형식 동일). 실기 막힘 ②가 해소 후보가 되고, 새 위험(보류 구간, 자동 영점 실패 시 폴백)이 생긴다.

---

#### E. 미결 항목의 사실상 결정 모음

| 항목 | 설계서 상태 | 구현된 결정 | 근거 |
|---|---|---|---|
| #21 작업 중지 시 ExecuteMotion cancel | 제안 | cancel + `/robot/stop` 병행 | `scan_manager.py:1051-1055` |
| #19 HOME 목표 출처 | 파라미터 `home_pose`(TBD) | robot_manager 파라미터 `home_joint_deg`(관절각) + move_joint | `robot_manager.py:96`, `:489-492` |
| 외력 감소 보조 신호 | 계약 9장 TBD | 미사용(z 추세선 대비 하강만) | `detector_core.py:10-17` |
| goal 거절 방식 | 계약 5.1 "goal 거절" | goal 은 항상 수락, 거절은 Result(1xx) — ack 는 accepted=true | `scan_manager.py:612-628` |
| `RobotStatus.moving` 근거 | TBD→T15 결정 | TCP 위치 변화(창 0.3 s · 0.2 mm) | `robot_manager.py:258-262`, `docs/contracts/ros-interfaces.md:688-694` |
| 정지 시 move_stop ↔ 해제 순서 | 계약 9장 TBD | move_stop(+정지 대기) → release_force → ramp 대기 → release_compliance | `robot_manager.py:752-808` |
| 홈 복귀 경로 | TBD | 안전복귀 = OP_HOME 1개, 마무리 = 올림 + OP_HOME | `sequence.py:492-497`, `:598-607` |
| HB 만료 조치 | TBD | 미구현(구독 자체가 없음) | `safety_monitor.py:82-89` |


---

## 부록 E. 디버깅 변경 영향

### Phase 6 — 디버깅으로 생긴 변경의 영향 (읽기 전용 감사)

- 기준 스냅샷: `origin/main` `717cbdd` (2026-09-21 16:41 KST). 경로는 스냅샷 기준 상대경로.
- 데이터: `data/pr/<번호>.json`, `data/runs.json`(200건), `git log origin/main`, `gh run view --log-failed`(읽기 전용, 12건 전부 확인).
- 표기: 근거가 없는 항목은 `미확인`. 시각은 KST.
- 위험도: **M4 막음**(실기 5점 탐색/시연을 직접 막음) · **TR 위험**(TR·KPI 판정을 흐리거나 실기에서 오동작 가능) · **정리**(동결 후 청소).

---

#### 0. 핵심 요약 (먼저 읽을 것)

1. **수정 PR 12건 중 9건이 9/21 하루에 몰렸고, 안전 경로(정지·2차 감시) 결함이 연쇄로 나왔다.** `#89`(safety_monitor) 머지 9/20 17:08 ~ `#101` 머지 9/21 14:41 동안 main 에는 `/robot/stop` 서버가 없었고(PR #101 본문), `#117` 머지(15:06) 전까지 safety_monitor 는 "정지가 필요한 첫 조건"에서 죽었다(PR #117, 실기 2회 10:34 · 11:51).
2. **수정이 만든 동작 변화 5건이 계약·정의서에 없다**: `startup_grace_s`(#99), 정지 요청이 남아 HOME 아닌 goal 을 거절(#114), 남은 요청이 있어도 HOME 은 출발(#116, 정지 미확인 상태에서 movej 가 나감), SLIDE 종료마다 +0.3 s 대기(#121), 종료 중 CANCELED `'scan_manager 종료'`(#119). `docs/contracts/*.md` · 정의서 6장에서 `startup_grace|stop_settle|stop_at_accept|release_force_time` grep 결과 0건.
3. **real.yaml 은 아직 실기 START 가 불가능하다**: `search_origin_pose` · `base_to_fixture` 가 주석 처리(`real.yaml:155,158`). 켜는 조건 ①이 열린 PR **#127**(리뷰 변경 요청 미반영, 커밋 1개), ②가 새 탐침 TCP x·y 180° 확인(미실시). → **M4 막음**.
4. **real.yaml 값과 9/21 실기 관측이 어긋난 채 남은 것 3건**: `sample_stale_ms` 300 < 실기 공백 337 ms(#101 로그) · 342/340 ms(계약 6.3), `stale_age_ms` 100 < 실기 SLIDE 중 공백 102 · 199 ms(세션 기록 5-12), `slide_target_force_n` 3.0(REL) → 실제 누름 ≈ 8.3 N > KPI 5 N(세션 기록 5-12).
5. **CI 실패 12건 중 7건이 main push 에서 났고 전부 재실행되지 않았다(attempt=1).** 9건은 scan_manager 노드 시험 flaky(#107), 2건은 **추적 이슈가 없는** robot_manager `test_sample_id_increases` flaky, 1건은 #100 의 진짜 실패, 1건은 CI 설정 PR 자체. **#124(#107 수정) 머지 커밋 `3be7879` 자체가 main 에서 같은 증상(104)으로 실패**했다 → #107 은 닫혔지만 해소되지 않았다.
6. 코드에 `TODO/FIXME/HACK/XXX`, 주석 처리된 호출, `skip/xfail` 로 꺼 둔 시험, 삭제된 시험은 **없다**. 남은 것은 하드코딩 수치(가속도 비율 · 포기 시간 등)와 웹 쪽 디버그 출력이다.

---

#### 1. 수정성 커밋 · PR 표

##### 1.1 main 에 들어간 수정 PR (지정 12건 + 열린 #127)

| PR / 커밋 | 작성자 | 머지 시각 | 무엇을 고쳤나 | 원인(앞선 PR) | 계약 · 시나리오에 남긴 부작용 |
|---|---|---|---|---|---|
| **#83** `abb60fd` | rokeyhak | 09-20 15:47 | ① `pending_calls` 가드(`if attempt is self.attempt`) ② `ws_cobot1/src/qt_hmi` 심볼릭 링크 삭제 ③ 계약 9장 통지 문장 | **#72**(`3cf58e8`): 리뷰 뒤 커밋이 main 에 못 들어간 채 머지, `git add -A` 로 개인 PC 절대경로 링크 커밋 | 시간 초과가 한 번 나면 **항상 5 s 대기**(`call_queue.py:25 abandon_after_s=5.0` 하드코딩) → 그동안 샘플 없음 → scan_manager 쪽 `SAMPLE_STALE(403)`, safety_monitor 정지 요청 가능(#83 리뷰 코멘트 ok778ts123). "파라미터로" 후속은 **미반영**. CHANGELOG v0.1.4 에 한 줄 추가(계약 3파일 동시 수정 규칙은 지킴) |
| **#88** `272206d` | EuiseokJeongNZ | 09-21 09:43 | `rclpy.shutdown()` → `try_shutdown()` (1줄) | **#67**(`7d5c35a`) mqtt_bridge 최초 구현 | 없음. 단 PR 본문이 "실제 런타임 Ctrl+C 검증은 통합 환경에서 확인 필요"로 남김 → 확인 기록 **미확인**. main push CI 는 concurrency 로 cancelled |
| **#99** `c1b3278` | yujh5537 | 09-21 09:39 | `startup_grace_s` 3.0 s 신설: 기동 후 최신성(샘플·상태)으로 정지·래치 안 함 | **#89**(safety_monitor) × **#72**("위치 모르면 moving=true") 두 보수값의 겹침 + `/robot/stop` 서버 부재 | 정의서 6.3 · 계약에 없는 파라미터. **safety_monitor 가 스캔 도중 재기동되면 3 s 동안 최신성 감시 공백**(9/21 실기에서 실제로 2회 죽었음 → #117). 실기에서 3 s 가 충분한지 "내일 봐야 한다"(PR 본문) → 결과 기록 **미확인**. 생성~머지 2분, 리뷰 0건 |
| **#100** `983be2c` | yujh5537 | 09-21 15:14 | sim 박스·기준점을 홈 아래로, `max_descend_m` · `max_slide_m` 재조정, 두 yaml 에 `home_joint_deg` · `home_speed_deg_s` 추가 → **M2 통과** | **#97**/**#77**(도달 불가 sim 좌표 `[0.40,0,0.10]`), **#73**(`home_joint_deg` 없으면 OP_HOME 거절) | **특이점 자세에서 `move_line` 이 success=true 로 조용히 실패**하는 문제는 코드로 막지 않음 — "스캔 전에 사람이 홈으로 보낸다"는 운영 전제로만 남음(`docs/test-reports/daily/20260921.md:135`). 계약·시나리오 1.1 에는 없음 → **TR 위험**. real.yaml `home_joint_deg` J6 = −204.84° 큰 회전 경고(`real.yaml:79`) |
| **#101** `8147d94` | rokeyhak | 09-21 14:41 | ① `/robot/stop` 서버 신설 ② `is_moving(..., window_s)`: 창의 절반도 못 덮으면 "이동 중" | ① **#72/#73**: 계약 2.2 가 "robot_manager 가 제공"이라 적은 서비스가 **한 번도 구현되지 않았음**(리뷰 누락, yujh5537 코멘트) ② **#72** `trim` 뒤 점 2개(25 ms)로 정지 오판 → 실기에서 완료 보고 뒤 12 mm 더 하강 | `min_span_ratio=0.5` 하드코딩(`motion_state.py:16`). 정지 확인 대기 `stop_settle_s` 1.5 s 는 정의서 6.1 `stop_timeout_s` 1.0(KPI 1 s) 과 이름·값 모두 다름 → **문서 반영 필요**. 실기 확인됨(PR 코멘트, 8.84 mm 에서 정지) |
| **#106** `74c371f` | ok778ts123 | 09-21 12:54 | `test_sim_process` 의 가짜 상자를 `sim.yaml` 에서 읽음 | **#77** 시험이 상자를 상수로 박아 둠 → **#100** 의 yaml 변경이 CI 실패 | 제품 코드 영향 없음. 머지 커밋 main CI 는 flaky 로 **28건 실패**(아래 4장) |
| **#114** `825781c` | rokeyhak | 09-21 14:53 | 동작 중 정지 확인 실패 시 요청을 되돌려 남김(`restore_stop_request`) | **#101** 두 정지 경로의 약속 불일치(#113) | **시나리오 1.5(안전복귀) · 1.6(재시작) 영향**: 요청이 남으면 모든 goal 이 `STOP_REQUESTED` 로 거절. 복구는 수동 `ros2 service call /robot/stop`(README 에만 기재). 9분 뒤 #116 으로 HOME 만 예외. **재시작(`/scan/resume`)의 첫 MOVE_TO 는 여전히 거절** — scan_manager 가 `/robot/stop` 재호출 뒤 재시도하는 후속은 없음(#114 코멘트). 실기 미확인. 리뷰 0건 |
| **#116** `beda383` | rokeyhak | 09-21 15:02 | 남은 정지 요청이 있어도 OP_HOME 은 수락, 출발 전 `move_stop` 재시도 | **#114** 가 웹 안전복귀 버튼을 막음(#115) | **안전 맞바꿈**: 정지를 확인 못 한(로봇 상태를 모르는) 상태에서도 관제자가 안전복귀를 누르면 movej 출발(PR 본문 "맞바꿈"). 계약 4.1 · 7.1 에 없음. #114 의 시험 단정("HOME 도 거절")을 새 정책으로 **바꿈**(삭제 아님). 실기 미확인. 생성~머지 7분, 리뷰 0건 |
| **#117** `ca46fde` | yujh5537 | 09-21 15:06 | `react()` 의 `error`/`warn` 을 다른 줄로 분리 | **#89**: 같은 줄에서 severity 전환 → `RcutilsLogger` ValueError → 타이머 콜백에서 미포착 → 노드 사망 | 판정 로직 변화 없음. **잔여: 감시자가 죽어도 아무도 모른다(#120 OPEN)**. main push CI 는 cancelled(검증된 main 실행 없음) |
| **#119** `618faf3` | ok778ts123 | 09-21 16:22 | 종료 중 발행 억제(`_shutting_down` · `_publish_quietly`), 종료가 깨운 예외는 실패로 남기지 않음 | **#77** 종료 경로(idle 에서만 검증) | 모션 중 SIGINT → 명령이 `CANCELED 'scan_manager 종료'` 로 끝나고 **`/robot/stop` · goal cancel 을 보내지 않음**(T19b D2 안건 유지). robot_manager · safety_monitor 몫은 미수정(#111 OPEN). 발행 3곳이 `_publish_quietly` 를 거치게 됨(종료 중 예외만 삼키고 그 밖은 올린다는 시험 포함) |
| **#121** `91fbc08` | rokeyhak | 09-21 16:26 | 켜는 호출 **전에** 해제 대상 표시, 7경로 해제 시험, `release_force` 뒤 `release_force_time_s` 대기 | **#73** `start_slide_force` 가 성공 응답 뒤에만 플래그를 세움(규칙 2 위반 구멍) | **SLIDE 종료마다 결과가 0.3 s 늦음**(`robot_manager.py:800 time.sleep(ramp_s)`, 시간 초과여도 대기) → scan_manager `event_wait_timeout_s` 1.0 과의 여유 감소(영향 실측 **미확인**). 승인 뒤 동작 변경 커밋 2개(`dbe52c9` · `5fd2989`). `compliance_released` 의 뜻은 여전히 "해제 호출 성공"(#125 OPEN) |
| **#124** `3be7879` | ok778ts123 | 09-21 16:06 | 시험용 한도 0.2/0.2/0.5 s → 제품값 2.0/1.0/5.0 s | **#77** 시험이 제품의 1/10 한도를 정상 경로에 검 | **해소되지 않음**: 머지 커밋이 main 에서 `lift: goal 응답이 오지 않았다 → 104` 로 실패(run `35571365338`, 2.0 s 한도에서도). 제품과 같은 한도에서 난 것이라 **실기/통합에서도 같은 거절이 날 수 있는지 미확인** → TR 위험 |
| **#127** OPEN `2ac32ce` | rokeyhak | — (09-21 16:49 생성) | 하강 기준/밀기 기준 분리: 하강 중 자동 영점, 밀기는 z 로 판정 켜기. 계약 v0.1.12, 새 파라미터 5개 | **#86/#97** 정지 tare 하나를 하강·밀기에 공용 + 9/21 실기 2~3 N 치우침(#109) | ① **보류 구간(실기 7.5 s × 3 mm/s = 22.5 mm)에는 CONTACT 가 없다** → 30 N 까지 무방비. yujh5537 이 "끄지 말고 둔하게(6 N)" 변경 요청 — **미반영**(커밋 1개) ② 소유자 아닌 사람이 `contact_detector` 수정(CLAUDE.local 소유 경로) ③ real.yaml 좌표를 켜는 조건 ①이 이 PR 에 달림 ④ mergeStateStatus=BLOCKED, 리뷰 승인 0 |

##### 1.2 그 밖의 수정성 PR · 커밋

| PR / 커밋 | 작성자 | 시각 | 내용 | 비고 |
|---|---|---|---|---|
| #45 `b5cb21c` | yujh5537 | 09-18 15:44 | 브랜치 보호 확인용 주석 원복 | #43 시험 커밋의 되돌림. 영향 없음 |
| #80 `ed588e7` | rokeyhak | 09-20 17:27 | [T03 후속] 실기 측정(2.1° 기울기, 편향 2.25 mm 잠정) | 두 값 모두 **v0.1.11(#110)에서 무효화**(밀린 탐침 · 고정 안 된 큐브). `edge_bias_offset_m` 은 0.0 유지 |
| #85 `eb1dc61` | rokeyhak | 09-20 16:33 | 계약 머리말 v0.1.4 구절 누락 보완 | #72 의 계약 수정 누락 |
| #98 `93a5761` | rokeyhak | 09-21 11:09 | 계약 6.3 발행 주기를 부하 의존 범위로(v0.1.10) | 맞바꿈만 기록, `sample_stale_ms` 값은 그대로(3장 참조) |
| 머지 전 브랜치 커밋 `6d3f7fe` · `5fbb807` · `5c66a77`(→#61), `014d980`(→#68), `5c03f62`(→#86), `900556e`(→#89), `f638d15`(→#99), `6a29138`(→#100) | yujh5537 | 09-19~21 | 리뷰 반영 fix: `sim_tip_radius_m` 0.45→0.225 mm(지름/반지름 혼동), sim `stale_age_ms` 200 · `tare_max_force_n` 6.0, `/robot/status` 끊기면 moving=모름 | 전부 squash 되어 main 에는 PR 단위로만 남음 |

##### 1.3 수정이 남긴 열린 이슈 (후속 미처리)

`#90`(표에 없는 ReasonCode 를 mqtt_bridge 가 조용히 버림) · `#105`(첫 방향만 누름 힘 다름) · `#109`(→#127) · `#111`(robot_manager · safety_monitor SIGINT −2) · `#120`(감시자 사망 미감지) · `#123`(툴·TCP 풀린 채 goal 수락, 실기 2회) · `#125`(`compliance_released` 조회 판정) · `#126`(노드 시험 DOMAIN_ID 충돌). 근거: `data/issues.json`.

---

#### 2. 임시 우회 코드 탐지

검색 범위: `ws_cobot1/src`, `backend`, `frontend/src`, `docker`, `scripts`.

##### 2.1 없음으로 확인된 것
- `TODO` · `FIXME` · `HACK` · `XXX` · `workaround` · `우회`: 코드 0건. `임시`는 `result_store/store.py:8,474`(임시 파일 → os.replace, 정상 설계)뿐.
- 주석 처리된 호출: 0건. bare `except:`: 0건.
- `xfail` · 기능 비활성용 `skip`: 0건. `importorskip`(ROS 없는 셸용)과 `robot_manager/test/test_node.py:22`(드라이버 없으면 모듈 skip — CI 는 #94 로 dsr_msgs2 를 빌드해 실제로 돈다)뿐.
- 삭제된 시험: 0건. `git log --diff-filter=D` 는 `ws_cobot1/src/qt_hmi`(#83) 하나. 시험 함수 이름이 빠진 3건은 전부 개명·대체(#124 fixture 교체, #95 `test_resume_is_not_supported_yet` → 재시작 시험군).

##### 2.2 발견 목록

| # | 파일:줄 | 내용 | 위험도 | 도입 |
|---|---|---|---|---|
| 1 | `ws_cobot1/src/contact_scan_bringup/config/real.yaml:155,158` | `search_origin_pose` · `base_to_fixture` 주석 처리 → 실기 START 는 `INVALID_VALUE` 거절(의도한 fail-safe) | **M4 막음** | #110 `a7e3226` |
| 2 | `ws_cobot1/src/contact_scan_bringup/launch/bringup.launch.py:51-62` + `config/*.yaml:182-187` | bringup 은 sim/real.yaml 만 넘기는데 두 파일에 `mqtt_bridge` 절이 없다(주석 placeholder, 담당 표기도 "(병후)"로 낡음 — #63 에서 의석으로 변경). 실제 값은 `mqtt_bridge/config/mqtt_bridge.yaml` 에 따로 있고 launch 가 읽지 않는다 → bringup 으로 띄우면 코드 기본값 `broker_host=127.0.0.1`(`mqtt_bridge.py:174`). 2-PC 구성에서는 실행 시 수동 지정(#112 본문 "실행 시 broker_host 를 Web PC 주소로 지정") | **M4 막음**(시연 절차에 수동 단계) | #61 / #67 |
| 3 | `robot_manager/robot_manager/dsr_client.py:89,95` | 가속도 하드코딩 `acc = 4 × speed`(movel), `2 × vel`(movej). BRD 4.2.1 은 가감속 관성력이 외력으로 읽히는 것을 피하라고 함 — #109 의 "출발 약 4 s 뒤 계단식 치우침" 원인 후보(가감속 끝)와 직결되는데 조정 불가 | **TR 위험**(규칙 7 위반) | #73 `e86256d` |
| 4 | `robot_manager/robot_manager/call_queue.py:25` | `abandon_after_s=5.0` 하드코딩. 호출처 `robot_manager.py:125` 는 인자를 안 넘김. 5 s 샘플 공백 → SAMPLE_STALE/정지 | **TR 위험** | #72(`ABANDON_AFTER_S`) → #73 현재 형태. #83 후속 미반영 |
| 5 | `robot_manager/robot_manager/robot_manager.py:820` | `done.wait(timeout=service_timeout_s * 4 + 1.0)` 매직 계수 | 정리 | #73 |
| 6 | `robot_manager/robot_manager/motion_state.py:16` | `min_span_ratio=0.5` 하드코딩(정지 판정에 직접 영향) | TR 위험(낮음) | #101 `8147d94` |
| 7 | `robot_manager/robot_manager/robot_manager.py:40` | `LOOP_PERIOD_S = 0.02` 모션 감시 주기(50 Hz). 하강 제한·이벤트 반응 지연의 하한 | 정리 | #73 |
| 8 | `robot_manager/robot_manager/robot_manager.py:79-108` | 코드 기본값이 있는 수치 파라미터 11개(`sample_rate_hz` 50, `moving_eps_m` 0.0002, `stop_settle_s` 1.5, `motion_timeout_s` 60 등). yaml 에도 있지만 **`stop_settle_s` · `motion_timeout_s` · `feedback_period_s` 는 yaml 에 없고 코드 기본값만** 쓴다. contact_detector · safety_monitor · scan_manager 는 "코드 예비값 없음" 방식이라 노드 간 정책 불일치 | 정리(규칙 7) | #72/#73 |
| 9 | `robot_manager/robot_manager/robot_manager.py:557,767,800` | 제품 코드 `time.sleep`. 557·767 은 감시 루프 주기, **800 은 `release_force` 뒤 0.3 s 대기**(Action 스레드, 락 없음 — #121 코멘트에서 Virtual 최대 간격 43 ms 확인) | 정리(800 은 1장 #121 부작용 참조) | #73 / #121 |
| 10 | `scan_manager/scan_manager/scan_manager.py:98,107,109,113` | `DEFAULT_STATE_PUBLISH_PERIOD_S=1.0` · `STARTUP_READ_DELAY_S=0.5` · `_WAIT_SLICE_S=0.1` · `_SHUTDOWN_GRACE_S=5.0`. 주석으로 "구조값"이라 설명됨 | 정리 | #50/#77 |
| 11 | `contact_detector/contact_detector/contact_detector.py:49-50` | `KEPT_MESSAGES=256`(약 6 s 분량 가정) · `WARN_PERIOD_S=2.0` | 정리 | #86 |
| 12 | `mqtt_bridge/mqtt_bridge/mqtt_bridge.py:582-583` | 종료 시 `except Exception: pass`(`wait_for_publish(timeout=1.0)` 실패 삼킴). 종료 경로 한정 | 정리 | #67 |
| 13 | `mqtt_bridge/mqtt_bridge/mqtt_bridge.py:157,360,376,401,420,443,463` | 넓은 `except Exception as exc` 7곳. #90(표에 없는 ReasonCode 를 조용히 버림)과 같은 계열 | TR 위험(낮음, #90 OPEN) | #67 |
| 14 | `mqtt_bridge/mqtt_bridge/mqtt_bridge.py:171-178` | 파라미터 이름이 정의서 6.5 와 다름: `sample_publish_hz`(정의서 `downsample_hz`) · `heartbeat_hz`(`hb_ros_hz`). 값(10 Hz · 1 Hz)은 BRD 와 일치. `cmd_expiry_s` 5.0 은 정의서 TBD 를 코드에서 확정 | 정리(문서 반영 필요) | #67 |
| 15 | `backend/app/main.py:221-224` | **모든 MQTT 메시지 payload 를 `print`**(샘플 10 Hz 포함). `print` 12곳. `on_message` 안에서 DB 저장도 동기 호출(`main.py:232-262`) → 브로커 수신 스레드 지연 가능(영향 실측 미확인) | 정리 / TR 위험(낮음, 웹 지연 KPI) | #65 `2a92615` · #84 |
| 16 | `frontend/src/App.jsx:384` (+311,372,505) | `console.log('[WS] message:', message)` — WS 메시지마다 출력(10 Hz) | 정리 | #78 `5697e5b` |
| 17 | `frontend/vite.config.js:10,15,19` | 프록시 대상 `127.0.0.1:8000` 하드코딩(dev 서버 한정) | 정리 | #56/#78 |
| 18 | `ws_cobot1/src/contact_scan_bringup/config/real.yaml:125-131,145,147,169` | **값이 이미 채워졌는데 "TBD" 주석 줄이 그대로 남음**(#77 이 넣은 placeholder 를 #97 이 값만 추가하고 안 지움). `real.yaml:124` "TBD 를 채우기 전에는 START 거절"은 이제 사실이 아님(거절 원인은 좌표 2개뿐) | 정리(오독 위험) | #77 → #97 |
| 19 | `ws_cobot1/src/scan_manager/test/test_sim_process.py:11` | 머리말이 "sim.yaml 의 detect_latency_s 는 TBD"라 적지만 #97 에서 채워짐(본문 63·291 행은 맞게 갱신). 시험은 여전히 `TEST_LATENCY_S` 로 덮어써 **sim.yaml 의 0.020 은 시험으로 검증되지 않는다** | 정리 | #77 / #97 |
| 20 | ROS 노드의 토픽 이름 문자열 리터럴 약 50곳(`mqtt_bridge.py` 21 · `scan_manager.py` 14 · `robot_manager.py` 5 · `safety_monitor.py` 5 · `contact_detector.py` 4) | 계약 이름과 일치하지만 공용 상수 없이 흩어져 있음. `backend/app/main.py:233,249,268,283` 도 MQTT 토픽 리터럴(`topic_prefix` 를 쓰면 어긋남) | 정리 | 각 최초 구현 PR |
| 21 | `scan_manager/scan_manager/state_machine.py:313-324`, `resume.py:154-156`, `sequence.py:155,601` | 계약 9장 TBD 에 기대 `NOT_SUPPORTED` 로 막아 둔 경로: 오류 뒤 재시작, 안전복귀 뒤 재접근, 해제 실패 보고, 홈 복귀 경로 | TR 위험(TR-08 재시작 범위 한정) | #50/#77/#95 |

---

#### 3. 파라미터 기본값 대조표

범례 — 코드: `declare_parameter` 기본값(`없음` = 필수, yaml 없으면 기동 실패/START 거절). 정의서: `docs/design/contact-scan-interface-spec-integrated-v1.2.md` 6장. BRD: `docs/BRD.md`.

##### 3.1 contact_detector (코드 기본값 전부 없음 — `contact_detector.py:144 _required`)

| 파라미터 | sim.yaml | real.yaml | 정의서 6.2 | BRD | 판정 |
|---|---|---|---|---|---|
| `contact_threshold_n` ★ | 3.0 | 3.0 | **4.0**(3~5) | KPI 검출 하중 ≤5 N(`BRD.md:435`) | **문서 반영 필요**. 근거는 yaml 주석(#57 무접촉 σ 0.50 N). `mqtt-schema.md:147,206,365,408` 예시는 4.0 |
| `edge_drop_m` ★ | 0.0005 | 0.0005 | 0.0005 | 0.5 mm(4.1.2) | 일치. r=0.225 mm 에서 재검토 메모(`real.yaml:19-20`) |
| `debounce_n` ★ | 3 | 3 | 3 | 4.1.4 | 일치 |
| `over_force_n` ★ | 30.0 | 30.0 | 30 | 30 N(4.5.3) | 일치 |
| `over_force_debounce_n` | 1 | 1 | 없음 | — | 문서 반영 필요(#68 신설) |
| `edge_arm_force_n` | 1.5 | 1.5 | 없음 | — | 문서 반영 필요(#86). **#127 이 밀기에서 이 값을 쓰지 않게 바꿈** |
| `edge_trend_window_s` / `edge_trend_min_samples` | 0.5 / 10 | 0.5 / 10 | 없음 | — | 문서 반영 필요(#86). 정의서의 `edge_force_drop_ratio` · `filter_window` 는 **미구현** |
| `stale_age_ms` | **200** | 100 | 100 | 4.1.6 | sim 200 = 실측 근거(Virtual 최대 97.7 ms, 계약 6.3) → 정당. **real 100 은 9/21 실기 SLIDE 공백 102·199 ms 보다 작다**(세션 기록 5-12: 추세선을 버리고 EDGE 를 못 봄) → **문서/값 재검토 필요, TR 위험** |
| `tare_duration_s` | 1.5 | 1.5 | 1.5 | 1~2 s(4.1.3) | 일치 |
| `tare_min_samples` / `tare_max_std_n` | 30 / 0.3 | 30 / 0.3 | 없음 | — | 문서 반영 필요(#86). 실측 0.035 N 주석 있음 |
| `tare_max_force_n` | 6.0 | 6.0 | TBD | 4.1.5 | 실측 근거(`real.yaml:41-45`, 등록 1.8~3.7 N vs 미등록 11~12.5 N) → **정당**, 정의서 TBD 갱신 필요 |
| `sim_box_origin_m` | [0.425,−0.184,0.400] | — | TBD | — | #100 에서 변경(3.5 참조) |
| `sim_stiffness_n_per_m` / `sim_tip_radius_m` / `sim_fall_speed_mps` / `sim_slide_press_n` | 20000 / 0.000225 / 0.050 / 3.0 | — | 없음 | — | sim 전용. 문서 반영 필요 |

##### 3.2 safety_monitor (코드 기본값 없음 — `safety_monitor.py:96-100`)

| 파라미터 | sim.yaml | real.yaml | 정의서 6.3 | BRD | 판정 |
|---|---|---|---|---|---|
| `over_force_n` ★ | 30.0 | 30.0 | 30 | 30 N | 일치 |
| `drop_limit_m` ★ | 0.005 | 0.005 | 0.005 | 5 mm(4.5.4) | 일치 |
| `confirm_n` | 1 | 1 | 없음 | — | 문서 반영 필요(#89, 이슈 #53 대기) |
| `startup_grace_s` | 3.0 | 3.0 | **없음** | — | #99 신설. 근거는 yaml 주석 + `daily/20260921.md` 3절 → sim 은 정당, **real 3.0 은 근거 없음(실기 미확인)**. 문서 반영 필요 |
| `sample_stale_ms` | **500** | **300** | **100** | 위험 10 | 정의서의 3~5배. sim 은 Virtual 근거. **real 300 은 실기 공백 337 ms(#101 로그) · 342/340 ms(계약 6.3)에 걸린다** — 계약이 "한계를 올리기 전에 공백 원인부터"라 적고 값은 유지 → **결정 대기, TR 위험(TR-07 오탐 정지)** |
| `robot_status_timeout_ms` | 1000 | 500 | TBD | — | 근거 Virtual 9.3~9.8 Hz. 실기 미측정(`real.yaml:63`) |
| `stop_confirm_timeout_s` | 0.6 | 0.6 | 없음(6.1 `stop_timeout_s` 1.0) | KPI 1 s | 설계 출발값. T32 에서 확정 예정. `moving_window_s` 0.3 과 묶임 |
| `stop_retry_period_s` / `status_publish_period_s` / `check_period_s` | 2.0 / 1.0 / 0.05 | 동일 | 없음 | — | 문서 반영 필요 |
| 정의서의 `max_speed_mps` · `workspace_*` · `max_descend_m` · `hb_timeout_s` · `hb_expired_action` · `latch_levels` | — | — | TBD | 4.6 · 6장 | **미구현**(최소판 #89). heartbeat 만료 감시 없음 |

##### 3.3 robot_manager

| 파라미터 | 코드 기본값 | sim.yaml | real.yaml | 정의서 6.1 | 판정 |
|---|---|---|---|---|---|
| `slide_target_force_n` ★ | 없음 | 3.0 | 3.0 | TBD("낮은 누름 힘") | #73 에서 TBD→3.0. **실기 실제 누름 ≈ 8.3 N**(기준선 5.31 + 3.0, 세션 기록 5-12) → KPI 5 N 초과. 값은 유지 → **재결정 필요, TR 위험** |
| `drop_limit_m` ★ | 없음 | 0.005 | 0.005 | 0.005 | 일치(7.2 동일값 검사 `test_config.py`) |
| `sample_rate_hz` | 50.0 | 50.0 | 50.0 | 50 | 일치(BRD 50 Hz). 실측 37.6~49.8 Hz |
| `status_rate_hz` | 10.0 | 10.0 | 10.0 | 10 | 일치 |
| `service_timeout_s` | 0.5 | 0.5 | 0.5 | 없음 | 문서 반영 필요 |
| `moving_eps_m` / `moving_window_s` | 0.0002 / 0.3 | 동일 | 동일 | 없음(계약 9장에 통지 문장) | 실기 오탐 여부 "다음 세션"(`real.yaml:112-115`) → 결과 **미확인** |
| `home_joint_deg` | 없음 | [-24.14, 17.03, 51.68, -0.18, 111.39, -204.84] | 동일 | `home_pose` double[6] m·rad **TBD** | #100 추가. 실기 확정값(units-frames.md) → **정당**. 정의서는 이름·단위 모두 다름 → 문서 반영 필요 |
| `home_speed_deg_s` | 20.0 | 30.0 | 20.0 | 없음 | #100. 근거 기록 없음(설계 출발값) |
| `compliance_stiffness` | 없음 | [3000×3, 200×3] | 동일 | 없음 | 두산 기본값. "실기에서 조정" — 미조정 |
| `arrival_tolerance_m` / `arrival_grace_s` | 없음 / 1.0 | 0.003 / 1.0 | 동일 | 없음 | #73. 문서 반영 필요 |
| `release_force_time_s` | 0.3 | 0.3 | 0.3 | 없음 | #73, #121 에서 대기에도 사용 |
| `stop_settle_s` | **1.5** | (없음) | (없음) | `stop_timeout_s` **1.0** | **yaml 에 없고 코드값만**. 정의서·KPI(1 s)와 다름 → 문서 반영 필요 + yaml 이관 |
| `motion_timeout_s` / `feedback_period_s` | 60.0 / 0.1 | (없음) | (없음) | 없음 | yaml 이관 필요 |
| 정의서의 `mode` · `dsr_model` · `rg2_grip_*` | — | — | — | TBD | 미구현 |

##### 3.4 scan_manager (수치 필수값은 코드 기본값 없음 — `params.py:91-114`)

| 파라미터 | sim.yaml | real.yaml | 정의서 6.4 | 판정 |
|---|---|---|---|---|
| `descend_speed_mps` ★ | 0.005 | 0.003 | TBD(저속) | 설계 출발값(#97). TR-01 에서 조정 예정 |
| `slide_speed_mps` ★ | 0.010 | 0.005 | TBD(예 0.010) | 설계 출발값 |
| `max_descend_m` ★ | 0.080 | 0.120 | TBD | real: `units-frames.md` v0.1.11 실측 범위 [0.113, 0.1823] 안 → **정당**(#110, 세션 기록 5-9) |
| `max_slide_m` ★ | 0.080 | 0.060 | TBD | sim 0.15→0.080(#100, 근거 주석만) |
| `motion_timeout_s` ★ | 30.0 | 60.0 | TBD | 설계 출발값. 실기 하강 107 mm ÷ 3 mm/s ≈ 36 s < 60 s |
| `lift_height_m` ★ | 0.05 | 0.05 | 0.05 | 일치(BRD 4.2.6) |
| `move_speed_mps` | 0.05 | 0.030 | 없음 | 문서 반영 필요 |
| `recontact_margin_m` / `recontact_speed_mps` | 0.001 / 0.005 | 0.001 / 0.002 | 0.001 / TBD | 일치 / 출발값 |
| `tip_radius_m` | 0.000225 | 0.000225 | **0.003** | 실측(#57, units-frames.md) → **정당**, 정의서 갱신 필요 |
| `detect_latency_s` | 0.020 | 0.020 | **0.040** | #97 에서 TBD→0.020. "실측이 아니다"(`real.yaml:162`). T24 실측 대기 → **미확정** |
| `edge_round_radius_m` | 0.0 | 0.0 | 없음 | 실측(#80, 캘리퍼) → 정당 |
| `edge_bias_offset_m` | 0.0 | **0.0(미측정)** | 없음 | **규칙 4 경계**: "아직 재지 않아 0"(`real.yaml:173`). 0 이 보정 없음과 미측정을 구분하지 못한다. T25 대기 |
| `search_origin_pose` | [0.425,−0.184,0.500,q] | **주석 처리** | TBD(double[6] m·rad) | 값은 계약 v0.1.11 에 확정, 미활성. 정의서는 [6] 오일러, 구현은 [7] quaternion(v0.1.7) → 문서 반영 필요 |
| `base_to_fixture` | [0.425,−0.184,0.400] | **주석 처리** | TBD(double[6]) | 구현은 [3] 평행 이동만 |
| `support_z_m` | 0.0 | 0.0 | 0.0 | 일치 |
| `event_wait_timeout_s` / `stop_confirm_timeout_s` / `server_wait_timeout_s` | 1.0 / 5.0 / 2.0 | 동일 | 없음 | 설계 출발값(#77). #124 로 시험도 같은 값 |
| `state_publish_period_s` | 1.0 | 1.0 | 없음 | — |
| 정의서의 `allow_concurrent` | — | — | false | 미구현(동작은 BUSY 거절로 대체) |

##### 3.5 mqtt_bridge (bringup yaml 에 절 없음 — 2.2절 #2)

| 파라미터 | 코드 기본값 (`mqtt_bridge.py:173-177`) | `mqtt_bridge/config/mqtt_bridge.yaml` | 정의서 6.5 | BRD | 판정 |
|---|---|---|---|---|---|
| `broker_host` / `broker_port` | 127.0.0.1 / 1883 | 동일 | TBD(웹 PC) | — | 실제 주소는 비공개라 실행 시 지정(#112) |
| `sample_publish_hz` | 10.0 | 10.0 | `downsample_hz` 10 | 10 Hz | 값 일치, **이름 불일치** |
| `heartbeat_hz` | 1.0 | 1.0 | `hb_ros_hz` 1 | 1 Hz | 값 일치, **이름 불일치** |
| `cmd_expiry_s` | 5.0 | 5.0 | TBD | 위험 10 | 근거 기록 없음 |
| `dedup_cache_size` / `keepalive_s` / `topic_prefix` | 100 / 60 / "" | 동일 | 없음 | — | — |

##### 3.6 yaml 값 변경 이력 (`git log -p origin/main -- ws_cobot1/src/contact_scan_bringup/config/`)

| 파라미터 | 이전 → 이후 | PR(커밋) | 이유 | 구분 |
|---|---|---|---|---|
| `slide_target_force_n` (양쪽) | TBD → 3.0 | #73 `e86256d` | 출발값·잠정. REL 기준 경고 주석 | 근거 약함 → 9/21 실기에서 실제 8.3 N 확인, **재결정 필요** |
| `descend_speed_mps` 등 real 모션 7종 | TBD → 0.003/0.005/0.120/0.060/60/0.030/0.002 | #97 `ae1c79b` | "전부 설계 출발값" | 문서 반영 필요(정의서 TBD). `max_descend_m` 만 실측 근거 |
| `detect_latency_s` (양쪽) | TBD → 0.020 | #97 | 계산값(샘플 반주기 + 조회 왕복) | **근거는 계산, 실측 아님**. 정의서 0.040 과 다름 |
| `startup_grace_s` (양쪽) | 없음 → 3.0 | #99 `c1b3278` | 기동 직후 508 ms 공백으로 래치 | sim: 실측으로 바뀐 정당한 변경(`daily/20260921.md` 3절). real: 근거 없음 |
| `max_descend_m` real 주석 | 근거 "#60·#80 약 0.112" → "v0.1.11, 187.34/107.44 mm" | #110 `a7e3226` | TCP z 252.12 확정 | 정당(값 불변, 근거 갱신. 세션 기록 5-9) |
| `search_origin_pose` · `base_to_fixture` real | TBD → 값 기재(주석 상태) | #110 | 값 확정, 켜는 조건 2개 명시 | 정당. **미활성** |
| `edge_bias_offset_m` real 주석 | "#80 의 2.25 mm" → "무효" | #110 | 밀린 탐침으로 잰 값 | 정당 |
| `home_joint_deg` · `home_speed_deg_s` (양쪽) | 없음 → 추가 | #100 `983be2c` | 없으면 OP_HOME 거절 → `success=false` | 정당(units-frames.md 실기 확정값) |
| `sim_box_origin_m` | [0.40,0,0] → [0.425,−0.184,0.400] | #100 | Virtual 특이점 회피, 홈 아래 | 정당(`daily/20260921.md` 2.2절, ok778ts123 독립 재현) |
| `search_origin_pose` sim | [0.40,0,0.10,0,1,0,0] → [0.425,−0.184,0.500,q홈] | #100 | 위와 같음 | 정당 |
| `base_to_fixture` sim | [0.40,0,0] → [0.425,−0.184,0.400] | #100 | 박스 밑면과 일치 | 정당 |
| `max_descend_m` sim | 0.08 → 0.080(근거 교체) | #100 | 기준점 0.500 − 윗면 0.440 | 정당 |
| `max_slide_m` sim | 0.15 → 0.080 | #100 | "박스 반폭 0.050 에 여유" | 주석 근거만. PR 본문에 언급 없음 → **근거 약함** |

##### 3.7 real.yaml 미확정 목록

| 항목 | 상태 | 채울 조건 |
|---|---|---|
| `scan_manager.search_origin_pose` | **주석 처리**(`real.yaml:155`) | ① #109/#127 해결 ② 새 탐침 TCP x·y 180° 확인(`real.yaml:149-154`) |
| `scan_manager.base_to_fixture` | **주석 처리**(`:158`) | 위와 같음 + 부재 본드 고정(세션 기록 5-12: 큐브가 +x 로 19 mm 밀림) |
| `scan_manager.edge_bias_offset_m` | 0.0 = 미측정(`:173`) | T25 (새 탐침으로 재측정) |
| `scan_manager.detect_latency_s` | 0.020 설계값(`:162`) | T24 (`detect_stamp − force_stamp`) |
| `robot_manager.slide_target_force_n` | 3.0 "잠정"(`:82`) | REL/ABS 결정(세션 기록 6절 빈칸), #105 |
| `robot_manager.compliance_stiffness` | 두산 기본값(`:97-99`) | 실기 조정 미실시 |
| `robot_manager.moving_eps_m` | 0.0002(`:112-115`) | 실기 posx 잡음 확인 — 결과 미기록 |
| `robot_manager.arrival_tolerance_m` | 0.003 출발값(`:100`) | 실기 확정 — 세션 기록 5-12 표 빈칸 |
| `contact_detector.contact_threshold_n` | 3.0(`:14-17`) | TR-01(T24). 하강 중 관성력 미측정 |
| `contact_detector.edge_drop_m` | 0.0005(`:18-20`) | T25 (r=0.225 mm 에서 재검토) |
| `contact_detector.stale_age_ms` | 100(`:33-35`) | robot_manager 실기 주기 "미측정" 주석 — 실제로는 9/21 에 102·199 ms 공백 관측됨 |
| `safety_monitor.sample_stale_ms` | 300(`:59-62`) | 공백 원인 규명 뒤(계약 6.3) |
| `safety_monitor.robot_status_timeout_ms` | 500(`:63`) | 실기 미측정 |
| `safety_monitor.stop_confirm_timeout_s` | 0.6(`:66-69`) | T32(TR-08) |
| `safety_monitor.startup_grace_s` | 3.0(`:52`) | 실기 확인 미기록 |
| `mqtt_bridge` 절 | **없음**(`:186-187` 주석) | launch 가 `mqtt_bridge.yaml` 을 읽게 하거나 절 추가 |
| (#127 예정) `descend_tare_delay_s` 6.0 · `edge_arm_still_*` | 미머지 | 전부 설계 출발값, 실기 미확인 |
| TCP x·y (−1.30, 3.71) | 옛 탐침 값(`units-frames.md:45`) | yaml 밖이지만 위 좌표 2개의 전제 |

---

#### 4. CI

`data/runs.json` 200건(09-19 13:21 ~ 09-21 16:49): success 165 · cancelled 23 · **failure 12**. 워크플로 `CI`(job `ros` · `web`). 12건 모두 `ros` job 실패, `web` 은 전부 success. `concurrency.cancel-in-progress: true`(`.github/workflows/ci.yml:10-12`).

##### 4.1 실패 12건 (전부 `gh run view --log-failed` 로 확인)

| run id | 브랜치 · 이벤트 | 시각 | SHA | 원인 |
|---|---|---|---|---|
| 35499115310 | `euiseok/20260920-t29-log-panel` PR(#93) | 09-20 17:16 | `56787bb` | scan_manager flaky 1건(`test_home_is_not_blocked_by_a_record_that_cannot_be_written`). **#93 은 frontend 만 바꾼 PR** |
| 35499924303 | 같은 PR | 09-20 17:34 | `09de9c6` | scan_manager flaky 8건(`test_node_scan.py`, 전부 `104`) |
| 35500071397 | `ci-dsr-msgs2` PR(#94) | 09-20 17:37 | `71f27a6` | CI 설정 작업 중 첫 실행 실패: `set -u` 상태에서 `/opt/ros/jazzy/setup.bash: line 8: AMENT_TRACE_SETUP_FILES: unbound variable`. 같은 PR 에서 `-u` 를 빼 해소(`ci.yml` 주석에 남음) |
| **35500760033** | **main push** | 09-20 17:52 | `e9461ea`(#93) | scan_manager flaky 8건 |
| **35548395502** | **main push** | 09-21 09:39 | `c1b3278`(#99) | scan_manager flaky 8건 + **robot_manager `test_sample_id_increases`**(`[1, 21, 2] == [1, 2, 21]`) |
| 35549346457 | `t15-rate-loaddep` PR(#98, 문서 전용) | 09-21 09:58 | `39b41b2` | scan_manager flaky 9건 |
| 35550407443 | `t07-sim-reachable` PR(#100) | 09-21 10:17 | `2e1f75f` | **진짜 실패**: `test_sim_process` 가 상수 상자를 씀 → `(300, 'max_descend_m 0.08 안에 접촉이 없다')`. #106 으로 해소 |
| **35551129220** | **main push** | 09-21 10:30 | `a9d0229`(#92, 문서 전용) | **robot_manager `test_sample_id_increases`**(`[1, 26, 2] == [1, 2, 26]`) 단독 |
| **35559108309** | **main push** | 09-21 12:54 | `74c371f`(#106) | scan_manager flaky **28건**(314 s, 러너 느림) |
| **35566235646** | **main push** | 09-21 14:53 | `825781c`(#114) | scan_manager flaky 2건 |
| **35566766978** | **main push** | 09-21 15:02 | `beda383`(#116) | scan_manager flaky 1건(`[event_after]`) |
| **35571365338** | **main push** | 09-21 16:06 | `3be7879`(**#124 자체**) | scan_manager `test_stop_during_the_resume_preparation_keeps_the_resume_point`: `lift: goal 응답이 오지 않았다` → `104`. **2.0 s 한도에서도 재현**(444 s) |

원인별: scan_manager 노드 시험 flaky **9건**(#107) · robot_manager `test_sample_id_increases` **2건**(1건은 위와 중복 실행) · #100 진짜 실패 1건 · CI 설정 1건.

##### 4.2 main 에서의 실패와 "빨간" 시간대

main push 54건 중 failure **7** · cancelled **9** · success 38. **7건 모두 attempt=1, 재실행 없음**(`gh run view --json attempt`).

| 빨간 구간 | 시작(실패 커밋) | 다음 success | 길이 |
|---|---|---|---|
| 1 | 09-20 17:52 `e9461ea` | 17:58 `ac628ad` | 약 6분 |
| 2 | 09-21 09:39 `c1b3278` | 09:44 `e86256d` | 약 5분 |
| 3 | 09-21 10:30 `a9d0229` | 11:01 `a42bed6` | 약 31분 |
| 4 | 09-21 12:54 `74c371f` | 14:19 `21d4556` | **약 85분** |
| 5 | 09-21 14:53 `825781c` → 15:02 `beda383` | 15:14 `983be2c` | 약 21분 |
| 6 | 09-21 16:06 `3be7879` | 16:26 `91fbc08` | 약 20분 |

합계 약 168분. **결정론적으로 main 이 깨진 커밋은 없다**(전부 flaky — 다음 커밋이 같은 코드 위에서 통과). 그러나:
- **CI 신호가 신뢰를 잃었다.** 문서 전용 PR(#98, #92)과 프런트 전용 PR(#93)이 ROS 시험으로 빨개졌다. 실패를 "또 flaky"로 넘기는 습관이 생기면 #100 같은 진짜 실패(1/12)를 놓친다.
- **cancelled 9건은 그 SHA 가 main 에서 한 번도 검증되지 않았다는 뜻이다**: `6ceb76d`(#70) · `77f4a06`(#81) · `1e2e4d6`(#79) · `d0e9989`(#77) · `eb20e0e`(#86) · `272206d`(#88) · `77fb9b2`(#112) · **`ca46fde`(#117, 안전 수정)** · **`618faf3`(#119)**. 머지가 몇 초~몇 분 간격으로 이어져 concurrency 가 앞 실행을 걷어냈다.
- **기능상 깨져 있던 구간(CI 가 못 잡음)**: ① `/robot/stop` 서버 부재 09-20 17:08(#89) ~ 09-21 14:41(#101) ② safety_monitor 사망 결함 09-20 17:08 ~ 09-21 15:06(#117) ③ 기동 즉시 래치 09-20 17:08 ~ 09-21 09:39(#99) ④ sim 종단(M2) 불가: `home_joint_deg` 부재 · 도달 불가 좌표 09-21 09:44(#73) ~ 15:14(#100). 네 건 모두 **실제 노드를 붙여 돌려서** 발견됐다(단위 시험은 전부 통과 상태였음).

##### 4.3 미추적 항목
- `robot_manager/test/test_node.py::test_sample_id_increases` flaky: `data/issues.json` 63건에 해당 이슈 **없음**. main 2회 실패.
- #107 은 CLOSED 인데 `3be7879` 에서 재발. #126(DOMAIN_ID 충돌)은 로컬 PC 용 이슈라 CI 재발을 설명하지 못한다. 재오픈 필요.

---

#### 5. 권고 (수정 범위 밖 — 이슈 초안 거리)

1. **M4 전**: #127 리뷰 반영(보류 중 둔한 임계) → real.yaml 좌표 2개 활성 → TCP x·y 180° 확인. bringup 이 mqtt_bridge 파라미터를 읽게 하기.
2. **TR 전**: `sample_stale_ms`(300) · `stale_age_ms`(100) 을 9/21 실기 공백 분포로 재결정, `slide_target_force_n` REL/ABS 결정, 가속도 비율(`dsr_client.py:89,95`) 파라미터화.
3. **계약 반영(한 PR, CHANGELOG 포함)**: `startup_grace_s`, 남은 정지 요청 정책(#114/#116), SLIDE 해제 대기 0.3 s, 종료 시 CANCELED, `stop_settle_s` ↔ `stop_timeout_s`, mqtt_bridge 파라미터 이름, `contact_threshold_n` 3.0/4.0.
4. **CI**: #107 재오픈, `test_sample_id_increases` 이슈 생성, main push 는 `cancel-in-progress` 제외 검토, 실패한 main 실행 재실행 규칙.
5. **정리**: real.yaml 의 낡은 TBD 주석 8줄, `backend/app/main.py:221` · `frontend/src/App.jsx:384` 메시지별 출력.


---

## 부록 F. 계약 변경 이력

### Phase 3-D 후반 — 계약 변경 이력 · 문서 동기화 · 파급 누락

- 기준: origin/main `717cbdd`(2026-09-21 16:41 KST) 스냅샷, 열린 PR #127(`origin/t109-descend-tare-slide-arm`, `2ac32ce`)
- 시각은 전부 KST. 근거 표기: `PR #n` · `해시 7자리` · `경로:줄`(줄 번호는 `717cbdd` 스냅샷 기준)
- 방법: `git log origin/main -- docs/contracts ws_cobot1/src/contact_scan_interfaces`(14커밋 전수), `git log origin/main -- docs/design`(1커밋), `data/pr/*.json`, `gh pr view`(읽기), `gh api .../branches/main/protection`(읽기)
- 읽기 전용. 저장소 파일은 고치지 않았다.

---

#### 1. CHANGELOG 버전 ↔ PR/커밋 대응

| 버전 | 도입 PR · 커밋 | main 병합(KST) | 작성자 | 닿은 계약 경로 | 비고 |
|---|---|---|---|---|---|
| v0.0 | PR 없음 · `f96fdc0` (main 직접 커밋) | 09-18 15:38 | yujh5537 | contracts 5개 파일 신규 | 브랜치 보호 시험(#43~#45, 15:41~15:44)보다 앞선 레포 골격 커밋. `CHANGELOG.md:137` |
| v0.1 | PR #47 · `cf24fc3` | 09-19 12:28 | ok778ts123 | contracts 5개 + `contact_scan_interfaces/` 26개 | CHANGELOG 날짜는 회의일 09-18. 병합은 09-19 |
| v0.1.1 | PR #49 (base = `t01-contract-freeze`, main 아님) → #47에 실려 main 도착 | #49 병합 09-18 21:38, main 도착 09-19 12:28 | ok778ts123 | `ros-interfaces.md` 6.3 · `contact_scan_qos` | `gh pr view 49`: baseRefName=`t01-contract-freeze`. main에는 v0.1과 **같은 커밋**으로 들어왔다 |
| v0.1.2 | PR #57 · `734a762` | 09-19 16:14 | rokeyhak | `units-frames.md` | |
| v0.1.3 | PR #60 · `8110ea6` | 09-19 17:58 | rokeyhak | `units-frames.md` | |
| v0.1.4 | PR #72 · `3cf58e8` | 09-20 15:21 | rokeyhak | `ros-interfaces.md` 6.3 · 9장 | |
| v0.1.4 (추가) | PR #83 · `abb60fd` | 09-20 15:47 | rokeyhak | `ros-interfaces.md` 9장 | **새 번호 없이** v0.1.4 항목에 한 줄 추가(`CHANGELOG.md:76`) |
| v0.1.4 (추가) | PR #85 · `eb1dc61` | 09-20 16:33 | rokeyhak | `ros-interfaces.md` 머리말 | 새 번호 없음(`CHANGELOG.md:77`). 같은 PR에서 `.claude/rules/contracts.md`에 "머리말 상태 줄" 규칙 신설(`222369f`) |
| v0.1.5 | PR #79 · `1e2e4d6` | 09-20 16:07 | ok778ts123 | `ros-interfaces.md` 3.3 · `msg/ContactEvent.msg`(주석) | |
| v0.1.6 | PR #82 · `e8ee009` | 09-20 16:20 | ok778ts123 | `units-frames.md` 탐색 기준점 행 | **PR 제목 · main 커밋 제목은 "(v0.1.7)"인데 CHANGELOG · 문서 머리말은 v0.1.6**(`CHANGELOG.md:56`, `units-frames.md:3`). 커밋 `c55ac36` "번호를 v0.1.6으로 맞춤" 뒤 제목을 안 고쳤다 |
| v0.1.7 · v0.1.8 | PR #80 · `ed588e7` | 09-20 17:27 | rokeyhak | `units-frames.md` | **PR 하나에 버전 둘**(`CHANGELOG.md:37,49`) |
| v0.1.10 | PR #98 · `93a5761` | 09-21 11:09 | rokeyhak | `ros-interfaces.md` 6.3 | v0.1.9보다 **먼저** 병합 |
| v0.1.11 | PR #110 · `a7e3226` | 09-21 14:23 | rokeyhak | `units-frames.md`(+ `real.yaml` · `docs/env/*`) | CHANGELOG 머리에 PR 번호가 아니라 **이슈 번호 #108**(`CHANGELOG.md:5`). 형식 규정은 `(날짜, PR)`(`CHANGELOG.md:3`) |
| v0.1.9 | PR #91 · `d5c869a` | 09-21 14:47 | ok778ts123 | `ros-interfaces.md` · `mqtt-schema.md` · `msg/ScanConfig.msg`(주석) | v0.1.10 · v0.1.11보다 **나중** 병합. 번호 예약 경위는 `CHANGELOG.md:6,35` |
| v0.1.12 | PR #127 (OPEN) · `2ac32ce` | 미병합 (09-21 16:49 생성) | rokeyhak | `ros-interfaces.md` 2장 · 3.3 | CHANGELOG 머리에 이슈 번호 #109. 리뷰 0건(`pr_timeline.txt:65`) |

**병합 순서와 번호 순서가 다르다**: …v0.1.8 → v0.1.10(11:09) → v0.1.11(14:23) → v0.1.9(14:47). CHANGELOG 파일 안의 순서는 번호순(위에서부터 .11 → .10 → .9)이라 "위가 최신"이 성립하지 않는다.

##### CHANGELOG 없이 계약 경로를 바꾼 커밋 (전수 14커밋 중)
| 커밋 | PR | 내용 | 판정 |
|---|---|---|---|
| `0fff77f` (09-19 14:51) | #62 | `contact_scan_interfaces/package.xml` maintainer 이메일 | CHANGELOG 없음. 인터페이스 정의가 아니라 메타데이터. **형식상 규칙 5 위반이지만 실질 영향 없음**. yujh5537 승인 있음 |
| `f96fdc0` (09-18 15:38) | 없음 | 계약 초안 v0.0 | CHANGELOG v0.0 있음. PR 없이 main 직접 커밋(레포 골격) |

그 밖의 12커밋은 전부 CHANGELOG를 같이 고쳤다. `.msg`를 건드린 두 PR(#79 · #91)도 계약 문서 · 인터페이스 · CHANGELOG를 한 PR에서 바꿨다(주석만 변경, 필드 · 타입 불변). v0.1 이후 **타입 변경은 0건**이다.

##### 머리말 상태 줄 누락(`.claude/rules/contracts.md` 규칙, #85에서 신설)
| 문서 | 상태 | 근거 |
|---|---|---|
| `ros-interfaces.md:3` | v0.1 · .1 · .4 · .5 · .9 · .10 기재. 정상 | #72 · #79에서 누락 → #85로 보완 |
| `units-frames.md:3` | v0.1.2 · .3 · .6 · .7 · .8 · .11 기재. 정상 | |
| `mqtt-schema.md:3` | **"v0.1 동결"뿐. v0.1.9(#91)가 이 문서 머리말 · 2장 변환표 · 4장 `contact/event` 설명 · 5장 TBD 2건을 고쳤는데 머리말에 없다** | `d5c869a`의 `mqtt-schema.md` diff. 규칙 문구("CHANGELOG 첫 문장이 이름을 부른 문서")로는 빠져나가지만 문서만 읽는 사람은 v0.1로 오해한다 |

---

#### 2. 계약이 바뀐 PR마다: 무엇이 → 무엇으로, 누가, 언제, 왜

| PR | 누가 · 언제(KST) | 무엇이 → 무엇으로 | 이유(PR 본문 · 커밋 · CHANGELOG) |
|---|---|---|---|
| #47 (v0.1) | ok778ts123 · 09-19 12:28 | v0.0 초안 → 정의서 v1.1 채택 + T01 결정. `command_id`→`request_id`, `job_id`→`scan_id`, MQTT 19토픽, `RobotSample` float64[6]→Pose · Wrench, `motion_id` · `operation` 추가, `OP_*` 번호, `force_ctrl_active` 분리, P03 신설, ReasonCode 305~307, NaN+`*_valid` | T01 1 · 2차 동결 회의(`CHANGELOG.md:103-135`). 리뷰 반영으로 `cmd/scan/stop` 만료 검사 제외 등 |
| #49 (v0.1.1) | ok778ts123 · 09-18 21:38(#47 브랜치로) | QoS 정의 위치 TBD → `contact_scan_interfaces`가 설치하는 Python 모듈 `contact_scan_qos` | rosidl이 같은 이름 Python 패키지를 이미 설치(빌드로 확인)(`CHANGELOG.md:96-101`) |
| #57 (v0.1.2) | rokeyhak · 09-19 16:14 | 툴 무게 · TCP · 팁 반지름 TBD → 1.3 kg, TCP [-1.30, 3.71, 249.99] mm, r = 0.225 mm(설계 출발값 3 mm 대체). 툴 · TCP 등록 휘발성 명시 | T02 실기 실측(`CHANGELOG.md:88-94`) |
| #60 (v0.1.3) | rokeyhak · 09-19 17:58 | z=0 · 작업대 원점 · 축 평행 · 홈 TBD → z=0 100.6 mm, 원점 (423.56, −186.06, 100.6), 축 평행 "판정 불가", 홈 관절각 6개, `max_descend_m` 하한 0.116. "탐색 기준점은 별도 파라미터를 두지 않는다" | T03 실측. 리뷰 2회 반영(`CHANGELOG.md:79-86`) |
| #72 (v0.1.4) | rokeyhak · 09-20 15:21 | 6.3 "실측 주기는 T15에서" → `/robot/sample` 37.6 Hz(최대 97.7 ms), `/robot/status` 9.3~9.8 Hz. 9장 TBD `moving의 근거` → 위치 변화 기반(0.3 s 창 · 0.2 mm), 모르면 이동 중 | `get_robot_state`가 Virtual에서 이동 중에도 STANDBY. 두산 서비스 직렬 호출(`3cf58e8` diff) |
| #83 | rokeyhak · 09-20 15:47 | 9장에 "`moving_eps_m` · `moving_window_s`를 바꾸면 전원에게 알린다" 추가 | scan_manager 정지 확인 지연 · safety_monitor `stop_confirmed` 시점이 같이 바뀜(`abb60fd`) |
| #85 | rokeyhak · 09-20 16:33 | 머리말에 v0.1.4 구절 추가, `.claude/rules/contracts.md`에 머리말 규칙 신설 | 병후가 #80 리뷰에서 누락 지적. "사람이 기억하는 것으로는 안 되는 종류"(`222369f` 메시지) |
| #79 (v0.1.5) | ok778ts123 · 09-20 16:07 | "판정 샘플" 미정의 → **조건이 처음 성립한 샘플**. `pose` · `*_stamp` · `wrench` · `sample_id` · `z_drop_m` = 첫 샘플, `force_delta_n` · `detect_stamp` = 확정 샘플 | 이슈 #69. 확정 샘플 좌표를 쓰면 `debounce_n`이 오검출 억제와 측정 편향을 같이 바꾼다(`CHANGELOG.md:62-69`) |
| #82 (v0.1.6) | ok778ts123 · 09-20 16:20 | 탐색 기준점 "별도 파라미터 없음"(#60) → scan_manager 파라미터 `search_origin_pose`(Base, x y z + quaternion) | #77 리뷰에서 현지가 계약 ↔ 코드 불일치 지적. scan_manager는 홈 TCP를 모른다. rokeyhak이 리뷰에서 "#60에서 제가 틀렸습니다" |
| #80 (v0.1.7 · .8) | rokeyhak · 09-20 17:27 | 라운드 가설(폭 최대 3.4 mm 과소) → 폐기(캘리퍼 80³, 예리). 축 평행 "판정 불가" → 2.1° ± 0.3°. 검출 편향 2.25 mm(잠정). TCP z 249.99 → 248.52(잠정), `max_descend_m` 하한 0.116 → 0.117 | T03 후속 실기, 과압 사고로 탐침 1.47 mm 단축(`CHANGELOG.md:37-54`) |
| #98 (v0.1.10) | rokeyhak · 09-21 11:09 | 6.3 실측을 한 값(37.6 Hz) → 부하 의존 표(37.6 / 49.8 Hz) + 342/340/201 ms 공백 꼬리 + 맞바꿈 · 원인 후보 | 현지 요청(09-20 저녁 통합). `stale_age_ms` · `sample_stale_ms`가 그 숫자를 근거로 쓴다(PR #98 본문) |
| #110 (v0.1.11) | rokeyhak · 09-21 14:23 | 배치 원칙 · 탐침 전제조건 절 신설. 원점 "세션 한정 초안" → 홈 바로 아래 고정 하강점. z=0 100.6 → 100.503. TCP z 248.52(잠정) → **252.12 확정**(x · y는 옛 탐침 값 임시). `search_origin_pose` 값 확정. 검출 편향 2.25 mm 무효, 2.1° 미적용 | 이슈 #108. 09-21 탐침 교체 후 실측(`realrobot-session_20260921.md`) |
| #91 (v0.1.9) | ok778ts123 · 09-21 14:47 | `target_force_n` ↔ `slide_target_force_n` 대응 + REL 기준 명시. recontact · move 속도 파라미터가 SetConfig 비대상임을 6.4에. 7.4 결과 중복 키 `scan_id` → `(scan_id, stamp)`. MQTT TBD 2건. `*_set=false` → `null`. mqtt_bridge 담당 병후 → 의석 | 이슈 #51 · #54. 코드가 이미 그렇게 구현돼 있어 문서를 맞춤(`CHANGELOG.md:26-35`) |
| #127 (v0.1.12, OPEN) | rokeyhak · 미병합 | `/contact/tare` = 하강 판정 기준 → 툴 등록 점검 + 예비 기준. CONTACT는 DESCEND마다 이동 중 F₀ 자동 재수집(그동안 CONTACT 보류). EDGE 켜기 `|F−F₀| > edge_arm_force_n` → z 멈춤 + x · y 이동 | 이슈 #109. 09-21 실기: 정지 F₀로 큐브 45 mm 위 거짓 CONTACT, 밀기 중 허공 Fx −5 N |

**눈에 띄는 패턴 — "코드가 먼저, 계약이 나중"**: v0.1.5 · .6 · .9는 계약이 코드를 이끈 게 아니라 이미 main에 있는 구현에 문서를 맞춘 변경이다.
- 결과 중복 키: mqtt_bridge `_scan_result_dedup_key` `7d5c35a`(#67, 09-20 12:04) → 계약 v0.1.9 09-21 14:47. **계약이 26.7 h 늦었다**(그동안 `ros-interfaces.md` 7.4는 `scan_id`였다)
- 첫 샘플: `detector_core.Detection.first_sample` `5499592`(#68, 09-20 12:02) → 계약 v0.1.5 16:07(+4.1 h)
- `search_origin_pose`: scan_manager #77이 09-20 12:57에 열림 → 계약 #82 16:20 → #77 병합 16:31. 계약이 11분 먼저 들어가 순서는 지켰다
- `DR_FC_MOD_REL`: robot_manager `e86256d`(#73, 09-21 09:44) → 계약 v0.1.9 14:47(+5.1 h)

---

#### 3. 설계 문서(docs/design) 동기화

##### 3-1. "README 6절 규칙"의 소재 — **미확인**
- `docs/design/README.md`는 17줄이고 절 번호가 없다. "정의서 2장 → 3~5장 → 노드 구성도 3장 연결 표 → drawio" 갱신 순서 규정은 **이 파일에 없다**. `git grep '정의서 2장\|노드 구성도 3장' origin/main` 및 전 원격 브랜치에서도 0건.
- 이 README가 실제로 규정하는 것(`docs/design/README.md:3,5,15`): ① 새 버전은 파일 이름 버전을 올리고 이전 파일은 지운다 ② **계약과 다르면 계약이 맞다**(설계 문서는 참고 자료) ③ 그림은 고친 사람이 새 버전으로 교체한다. 즉 "계약 변경 때 같이 고쳐야 한다"는 의무는 레포 어디에도 명문화돼 있지 않다.
- 아래 표는 지시문의 사슬(정의서 2장 → 3~5장 → 노드 구성도 3장 → drawio)을 점검 틀로만 썼다.

##### 3-2. 설계 문서 변경 이력
`git log origin/main -- docs/design` = **1커밋**: `8dd44c8`(PR #48, 09-19 14:31, ok778ts123). 이후 변경 0건. 반영 범위는 계약 v0.1 + v0.1.1 + #47 리뷰 반영까지(정의서 `:4`, `:1269`, `:1593`). **v0.1.2 ~ v0.1.11(10개 버전)은 설계 문서에 하나도 반영되지 않았다.**

##### 3-3. 변경별 미갱신 표
범례: ✗ = 고칠 곳이 있는데 안 고침(줄 번호) · — = 그 문서에는 해당 내용이 없어 고칠 것 없음. 6장(파라미터)은 지시문 사슬 밖이지만 실제 어긋남이 가장 많아 열을 따로 뒀다.

| 변경 | 정의서 2장 | 정의서 3~5장 | 정의서 6장 등 | 노드 구성도 3장(연결 표) | drawio |
|---|---|---|---|---|---|
| v0.1.2 TCP · r=0.225 | — | — | ✗ `:41`(팁 반지름 3 mm) · `:1120`(`tip_radius_m` 0.003) | — | — |
| v0.1.3 홈 = 관절각 | ✗ `:249`(`home_pose`) | ✗ `:973`(HOME은 `home_pose`) | ✗ `:1071`(`home_pose` double[6] m·rad) · `:1369` | —(선 변화 없음). 1.1절 `:18` · 6장 `:258`은 ✗ | ✗ node-diagram drawio에 `home_pose` 1곳 |
| v0.1.4 실측 주기 · moving 근거 | — (`:209` "50 Hz 설계 목표"는 여전히 맞음) | ✗ `:345`(`moving`의 근거 TBD [E19]) | — | — | —("50 Hz 설계 목표" 라벨은 유효) |
| v0.1.5 판정 샘플 = 첫 샘플 | — | ✗ `:352` · `:362-370`("판정에 쓴 샘플"뿐. 첫/확정 구분 없음) | ✗ `:1121`(`detect_latency_s` 0.040, 디바운스 몫 포함 여부 불명) | — | — |
| v0.1.6 `search_origin_pose` | ✗ `:252`(2.5절 scan_manager 목록에 이름 자체가 없음) | — | ✗ `:1125`(double[6] m·rad, TBD) ↔ 계약은 7원소 x y z + quaternion | —. 1.1절 `:17`은 이름만 있어 무해 | — |
| v0.1.7 · .8 라운드 폐기 · 2.1° · 편향 | — | — | —(정의서에 라운드 가설 없음) | — | — |
| v0.1.9 중복 키 · REL · 파라미터 | ✗ `:252`(`move_speed_mps` · `recontact_speed_mps` 없음) | ✗ `:112` · `:459` · `:876`(중복 방지 = `scan_id`) · `:811`(`target_force_n` 주석에 REL 기준 없음) | ✗ 6.4에 `move_speed_mps` 없음(`:1109-1127`) | —. 1.1절 `:17`에 `move_speed_mps` 없음 | — |
| v0.1.10 발행 주기 범위 | — | — | ✗ `:1090`(`stale_age_ms` 100) · `:1103`(`sample_stale_ms` 100) ↔ yaml 100/300(real) · 200/500(sim) | — | — |
| v0.1.11 배치 원칙 · TCP 252.12 | — | — | —(좌표 값은 정의서에 없음). 단 BRD `:360` · `:467`과 충돌(3-5 참고) | — | — |
| v0.1.12 (#127, 미병합) | — | ✗ `:691`(4.2 `/contact/tare` = F₀ 저장이 유일 기준) · `:78-92`(1.2 DESCEND 흐름) | ✗ 6.2에 새 파라미터 5개 없음 | ✗ `:166` L12 "외력 기준값 F₀(무접촉·정지 1~2 s)" · Mermaid `:91` | ✗ architecture v1.6의 "무접촉 자세에서 /contact/tare (1~2 s 기준값)" 카드 |

**요약**: 연결선(토픽 · 서비스 · 액션의 추가 · 삭제 · 방향)은 v0.1 이후 하나도 바뀌지 않아 **노드 구성도 3장과 drawio의 선은 지금도 맞다**. 어긋난 것은 전부 정의서 3~6장의 "뜻 · 파라미터 · 수치"와 노드 구성도 1.1절의 파라미터 이름 목록이다. #127이 들어가면 처음으로 3장 L12의 "의미 한 줄"이 틀려진다.

##### 3-4. 정의서 v1.2 ↔ 현재 contracts 어긋남 목록(이름 · 필드 · 수치)
| # | 항목 | 정의서 v1.2 | 현재 계약 / 코드 | 도입 버전 |
|---|---|---|---|---|
| 1 | 팁 반지름 | 3 mm · `tip_radius_m` 0.003 (`:41`, `:1120`) | 0.225 mm (`units-frames.md`, `real.yaml:168` 0.000225) | v0.1.2 |
| 2 | 홈 파라미터 | `home_pose` double[6] m·rad (`:1071`) | 관절각 `home_joint_deg`[6] deg (`units-frames.md:49`, `real.yaml:77`) | v0.1.3 |
| 3 | `moving` 근거 | TBD [E19] (`:345`) | 위치 변화 기반 0.3 s · 0.2 mm (`ros-interfaces.md:688-694`) | v0.1.4 |
| 4 | 판정 샘플 | "판정에 쓴 샘플" (`:352`, `:362`) | 조건이 처음 성립한 샘플 / 확정 샘플 구분 (`ros-interfaces.md:145-152`) | v0.1.5 |
| 5 | `detect_latency_s` | 0.040 (`:1121`) | 디바운스 몫 제외, yaml 0.020 (`real.yaml:162-167`) | v0.1.5 |
| 6 | `search_origin_pose` | double[6] m·rad, TBD (`:1125`) | 7원소 `x y z qx qy qz qw`, 값 확정 (`units-frames.md:49`) | v0.1.6 · .11 |
| 7 | 결과 중복 키 | `scan_id` (`:112`, `:459`, `:876`) | `(scan_id, stamp)` (`ros-interfaces.md` 7.4) | v0.1.9 |
| 8 | `move_speed_mps` | 없음 | 계약 6.4에 이름 기재, `real.yaml:142` | v0.1.9 |
| 9 | `target_force_n` | "SLIDE −z 목표 힘" (`:811`, `:1067`) | REL 기준: 첫 방향 = 접촉력 + 값, 2~4 방향 ≈ 값 (`ros-interfaces.md:69`) | v0.1.9 |
| 10 | `stale_age_ms` / `sample_stale_ms` | 100 / 100 (`:1090`, `:1103`) | real 100 / 300, sim 200 / 500 (`real.yaml:33,59`, `sim.yaml:31,79`) | v0.1.4 · .10 |
| 11 | contact_detector 파라미터 | 11개 (`:1080-1092`) | + `over_force_debounce_n` · `edge_arm_force_n` · `edge_trend_window_s` · `edge_trend_min_samples` · `tare_min_samples` · `tare_max_std_n` (`real.yaml:23-40`). `edge_force_drop_ratio` · `filter_window`는 yaml에 없음 | 담당자 재량(계약 6.4) |
| 12 | safety_monitor 파라미터 | `max_speed_mps` · `workspace_*` · `max_descend_m` · `hb_*` · `latch_levels` (`:1096-1107`) | 코드에 없음(최소판, T33 #33 OPEN). `safety_monitor/*.py`에 `workspace` · `max_speed` 0건 | 구현 미완 |
| 13 | mqtt_bridge 담당 | — | 병후 → 의석(#63), `mqtt-schema.md` 머리말은 #91에서야 정정(45.9 h 뒤) | v0.1.9 |
| 14 | 정의서 내부 불일치 | 2.5절(`:252`) scan_manager 목록에 `search_origin_pose` · `base_to_fixture` · `support_z_m` · `recontact_speed_mps` 없음 ↔ 6.4(`:1117-1125`)에는 있음 | — | #48 당시부터 |

##### 3-5. 계약 문서 자체의 미갱신(설계 문서 밖)
| 위치 | 문제 | 근거 |
|---|---|---|
| `ros-interfaces.md:115` | 3.2절에 "`moving`의 근거는 TBD(실PC 확인)"가 **남아 있다**. 같은 문서 `:688`은 "T15에서 정했다". v0.1.4(#72)가 9장만 고치고 3.2를 놓쳤다 | `3cf58e8` diff에 3.2 변경 없음 |
| `ros-interfaces.md:459` · `action/ExecuteMotion.action:5` | `OP_HOME` 주석 "홈위치(파라미터 `home_pose`)". 코드는 `home_joint_deg`. robot_manager README가 어긋남을 **알고 적어 뒀다**(`robot_manager/README.md:68-69` "계약 5.4는 home_pose라고 적었지만…") | v0.1.3 이후 미정정. 주석이라 타입 영향 없음 |
| `ros-interfaces.md:599` | "세 값은 **최대 공백**을 기준으로 잡는다"가 바로 아래 `:602-605` "한계를 올리기 전에 원인을 없애는 쪽이 먼저다"와 **반대 방향**. 현지(코멘트 09-21 10:37 · 승인 리뷰) · 병후(코멘트 10:32) 둘 다 "이 한 문장만 바꿔 달라"고 했으나 **그대로 병합됐다** | `data/pr/98.json` comments · reviews, `93a5761` |
| `ros-interfaces.md` 6.3 | 09-21 실기 주기표(전체 49.6 Hz, 최대 358 ms, 모션 중 최대 121 ms — PR #98 코멘트 rokeyhak 10:42)가 계약에 없다. 현지 리뷰: "실기 표는 v0.1.11로 따로" → v0.1.11은 #110(units-frames)이 썼고 **실기 표는 어느 버전에도 안 들어갔다**. `:610` "실기 주기는 T24 전에 다시 잰다"가 그대로 | `grep 실기 ros-interfaces.md` |
| `ros-interfaces.md:688-694` | #101(`8147d94`, 09-21 14:41)이 `moving` 판정에 "남은 점이 창의 절반도 못 덮으면 True"를 추가했는데 계약 9장 설명 · CHANGELOG에 없다. #83이 넣은 "값을 고칠 때 전원에게 알린다"는 값 변경만 다루고 판정식 변경은 다루지 않는다 | PR #101 본문 ②, 파일 목록에 contracts 없음 |
| `mqtt-schema.md:3` | 머리말에 v0.1.9 없음(1절 표 참고) | `d5c869a` |
| `docs/BRD.md:467`(TR-02 "기준 부재 2종") · `:360`("2종 이상 권장", "배치 가이드") | v0.1.11 배치 원칙 6번 "MVP 부재는 80 mm 큐브 **한 종**", "지그 없이 본드 고정"(`units-frames.md:51-57`, `:44`)과 충돌. BRD는 #48 이후 변경 없음(`git log -- docs/BRD.md`). 이슈 T31(#31 "블록 2종") · T38(#38 "블록 교체")도 그대로 열려 있다 | |
| `real.yaml:125-131`, `:145`, `:147` | 값이 채워졌는데 "TBD" 주석 블록이 그대로 남음(`# descend_speed_mps: TBD`, `# move_speed_mps: TBD`, `# recontact_speed_mps: TBD`) — 값은 `:133-143`에 있다 | #97 이후 미정리 |

---

#### 4. 파급 누락 — 계약 변경 → 영향 코드가 따라온 시각

##### 4-1. 따라온 것(걸린 시간)
| 계약 변경(병합) | 영향 코드 | 따라온 PR(병합) | 걸린 시간 |
|---|---|---|---|
| v0.1 #47 (09-19 12:28) | mock_publisher | #56 (09-19 13:37) | +1.2 h. 이후 `backend/mock_publisher` 변경 0건(`git log`) — MQTT 구조가 안 바뀌어 고칠 것 없음 |
| 〃 | FastAPI | #65 (09-19 17:22) | +4.9 h |
| 〃 | mqtt_bridge | #67 (09-20 12:04) | +23.6 h |
| 〃 | **`/robot/stop` 서버(robot_manager)** | **#101 (09-21 14:41)** | **+50.2 h. 아래 4-2 ①** |
| v0.1.2 #57 (09-19 16:14) | yaml `tip_radius_m` 0.000225 | #61 `260a502` (09-20 09:27) | +17.2 h |
| v0.1.3 #60 (09-19 17:58) | scan_manager `base_to_fixture` 파라미터 | #77 `d0e9989` (09-20 16:31) | +22.6 h |
| 〃 | robot_manager 홈(`home_joint_deg`, movej) | #73 `e86256d` (09-21 09:44) | +39.8 h |
| 〃 | yaml `home_joint_deg` 값 | #100 `983be2c` (09-21 15:14) | +45.3 h |
| v0.1.4 #72 (09-20 15:21) | scan_manager 정지 확인 `connected && !moving` | #77 (09-20 16:31) | +1.2 h |
| 〃 | safety_monitor `sample_stale_ms` 300 · `robot_status_timeout_ms` 500(9.3~9.8 Hz 근거) | #89 `3b520d1` (09-20 17:08) | +1.8 h |
| 〃 | contact_detector `stale_age_ms`(sim 200 = 97.7 ms의 2배) | #86 `eb20e0e` (09-20 17:08) | +1.8 h |
| v0.1.5 #79 (09-20 16:07) | contact_detector 이벤트 필드 배정(`contact_detector.py:252-271`) | #86 (09-20 17:08) | +1.0 h |
| 〃 | yaml `detect_latency_s` 주석(디바운스 몫 제외) | #97 `ae1c79b` (09-21 09:15) | +17.1 h |
| 〃 | mqtt-schema `contact/event` 출처 설명 | #91 (09-21 14:47) | +22.7 h |
| v0.1.6 #82 (09-20 16:20) | scan_manager `search_origin_pose`(7원소) `params.py:102` | #77 (09-20 16:31) | +0.2 h |
| 〃 | sim.yaml 값(`sim.yaml:152`) | #97 (09-21 09:15) | +16.9 h |
| v0.1.7 #80 (09-20 17:27) | yaml `edge_round_radius_m: 0.0`(라운드 없음) | #77에서 이미 0.0, 근거 주석은 #97 | — |
| v0.1.9 #91 (09-21 14:47) | scan_manager 전파표 `propagation.py:50,70` | #104 `21d4556` (09-21 14:19) | 코드가 28분 먼저 |
| 〃 | mqtt_bridge `(scan_id, stamp)` `mqtt_bridge.py:164-166` | #67 (09-20 12:04) | 코드가 26.7 h 먼저 |
| v0.1.11 #110 (09-21 14:23) | `real.yaml` `max_descend_m` 근거 · `search_origin_pose` · `base_to_fixture` 값(주석 처리) · `apply_tool_tcp.py` 기본값 | 같은 PR #110 | 0 h |

##### 4-2. 아직 안 따라온 곳 / 늦게 드러난 곳
① **`/robot/stop` 서버 부재 50.2 h (해소됨, 단 실기 미확인)** — 계약 v0.1(#47)은 `/robot/stop`을 robot_manager가 제공한다고 적었고 v0.1.4(#72)는 RobotSample · RobotStatus만 구현했다. safety_monitor(#89, 09-20 17:08)는 **없는 서비스를 21.5 h 동안 불렀다**. 09-21 실기에서 `[safety_monitor] /robot/stop 서버가 없다`로 드러나 #101(`8147d94`, 09-21 14:41)로 해소. PR #101 본문: "safety_monitor는 지금까지 로봇을 멈출 수단이 하나도 없었다". 같은 본문 "남은 것": `/robot/stop`의 실기 확인은 아직.

② **v0.1.2 → robot_manager 툴 · TCP 등록 확인: 미이행** — `units-frames.md:93` "robot_manager는 시작할 때와 탐색 전에 현재 툴 · TCP를 확인해야 한다(BRD 4.1.5)". `robot_manager/robot_manager/*.py`에 툴 · TCP 조회 호출 0건(`dsr_client.py:10` import 목록에 `GetCurrentTcp`/`GetCurrentTool` 없음). 대체 수단은 contact_detector의 tare 기반 `TOOL_REG_SUSPECT`뿐(`detector_core.py:370`, `real.yaml:41` 6.0 N). 09-21 실기에서 2회 재발 → 이슈 #123 OPEN. 계약 병합 뒤 **48 h+ 경과**.

③ **v0.1.3 → safety_monitor 작업영역: 미구현** — CHANGELOG `:80` 영향 목록에 "safety_monitor(작업영역)". `safety_monitor/*.py`에 `workspace` 0건, yaml에도 없음. T33(#33) OPEN. "부재가 없으면 팁이 작업대까지 내려간다. 목표 z 제한이 유일한 보호다"(`real.yaml:139`).

④ **v0.1.4 3.2절 TBD 잔존** — `ros-interfaces.md:115`(3-5 참고). 코드 영향은 없으나 계약을 3.2만 읽는 사람은 `moving`을 미확정으로 본다.

⑤ **v0.1.5 → `detect_latency_s` 실측 계획이 계약 정의와 어긋남** — `real.yaml:167` "T24에서 `detect_stamp − force_stamp`로 실측해 바꾼다". 그런데 v0.1.5는 그 차이를 **디바운스 지연**으로 정의했고(`ros-interfaces.md` 3.3, `CHANGELOG.md:67`), 같은 주석 `:165`는 "디바운스 몫은 빠졌다"고 적는다. 즉 그 식으로 재면 `detect_latency_s`에서 뺀 바로 그 값을 다시 넣게 된다. 실접촉 → 첫 샘플까지의 지연은 이벤트 필드만으로는 구할 수 없다. (yaml 소유: 현지)

⑥ **v0.1.8 → 2.1° 처리 방법: 결정 없음** — CHANGELOG `:41` "팀 결정이 필요하다". 이슈 · ADR 없음(열린 이슈 목록에 해당 건 0). v0.1.11이 "지금 부재에는 적용하지 않는다, 본드 고정 뒤 다시 잰다"로 미뤘다. geometry_estimator · `base_to_fixture`는 여전히 평행 이동만(`real.yaml:159`).

⑦ **v0.1.9 → 웹 DB는 `scan_id` 단일 키** — `docker/postgres/init/001_schema.sql:7,25,99`(`scan_id` PRIMARY KEY), `backend/app/db.py:88,161,240`(`ON CONFLICT (scan_id) DO UPDATE`). 계약 7.4의 주어는 mqtt_bridge라 **위반은 아니고**, UPDATE라 나중 결과가 버려지지도 않는다. 다만 재시작 시 부분 결과가 최종 결과로 **덮어써져 이력이 남지 않고**, `stamp_ms` 비교가 없어 늦게 도착한 옛 결과가 최신을 덮을 수 있다. 계약이 `(scan_id, stamp)`를 말하게 된 이유(재시작이 `scan_id`를 유지)가 웹 저장 계층에는 전달되지 않았다. (소유: 의석 → 이슈 초안 대상)

⑧ **v0.1.9 → `target_force_n` 웹 문구** — `ros-interfaces.md:69` "웹 표시 문구도 이 기준에 맞춘다". `frontend/src/`에 `target_force` · `누름` 0건 → 표시 자체가 없어 **해당 없음**. 설정 화면이 생기면 그때 적용 대상.

⑨ **v0.1.9 MQTT TBD 2건(`hb/ros` · `conn/ros` 만료 기준, retain 오래됨 기준) → 웹 미구현** — `backend/` · `frontend/src/`에 `hb/web` · `conn/web` 발행 0건(`grep` 0건), FastAPI는 `hb/ros` · `conn/ros`를 구독 목록에만 둠(`backend/app/main.py:37-38`). safety_monitor도 `/web/heartbeat`를 보지 않는다(`safety_monitor/*.py` 0건, T33 OPEN). mqtt_bridge 쪽 수신부만 있다(`mqtt_bridge.py:284,312`). v0.1부터의 공백이고 TBD가 풀려야 닫힌다.

⑩ **v0.1.10 → yaml 근거 주석이 옛 숫자에 머묾** — 값(100/300, 200/500)을 안 올린 것은 계약의 맞바꿈("올리기 전에 원인부터")과 **일치**한다. 그러나 근거 주석은 v0.1.10 이전 그대로다: `real.yaml:34,61` "실기 실측 간격 최대 29 ms … robot_manager의 실기 주기는 미측정"(↔ 같은 파일 `:109` "실기 42.8 Hz", PR #98 코멘트의 실기 최대 358 ms), `sim.yaml:32,80` "Virtual 실측 간격 최대 97.7 ms"(↔ 계약 6.3의 342 ms). yaml에 `342` 문자열 0건. sim의 `stale_age_ms` 200은 342 ms 공백에서 추세선을 버린다(`contact_detector.py:155` `max_gap_s = stale_age_ms`). 공백 **원인**은 "큐 시간 초과 아님"까지만 좁혀졌고(PR #98 코멘트 ②) 계약 6.3에는 미반영.

⑪ **v0.1.11 → 실기 START는 여전히 거절 상태(의도)** — `real.yaml:155,158`에서 `search_origin_pose` · `base_to_fixture`가 주석 처리라 scan_manager가 `INVALID_VALUE`로 거절한다. 켜는 조건 ①(#109) = PR #127(OPEN), ②(새 탐침 TCP x · y 180° 확인) = PR #122(OPEN, 절차서 · 계산 스크립트). **둘 다 미병합이라 09-21 16:41 현재 실기 자동 스캔은 돌 수 없다.** `edge_bias_offset_m` 0.0(`real.yaml:173`)은 2.25 mm 무효화와 일치(T25 재측정 대기).

##### 4-3. 열린 PR #127(v0.1.12)이 요구하는 변경
| 대상 | 요구 | #127에 들어 있나 | 남는 것 |
|---|---|---|---|
| contact_detector(`detector_core.py` +145, `contact_detector.py` +38, 시험 237줄) | 하강 자동 영점 · z 기반 EDGE 켜기 | 있음 | **소유자(현지) 패키지를 rokeyhak이 고친다.** `contact_detector/`는 CODEOWNERS에 없어 계약 경로 승인만 필수. 현지 코멘트(09-21 16:54): 보류 구간을 "끄기"가 아니라 "둔한 임계(`descend_hold_threshold_n` 6 N)"로 — 받아들이면 **계약 3.3 문구("모으는 동안 CONTACT는 보류")가 병합 전에 다시 바뀐다**. 자동 영점 실패 시 "정지 F₀ + 3 N"으로 돌아가는 것이 45 mm 위 거짓 접촉을 낸 바로 그 조합이라는 지적도 미반영 |
| yaml(`real.yaml` +11, `sim.yaml` +6) | 새 파라미터 5개 | 있음 | `edge_arm_force_n`(`real.yaml:27`)은 `edge_arm_still_window_s > 0`이면 안 쓰이는데 주석 · 값이 그대로 남는다. "`slide_target_force_n`보다 충분히 작아야" 조건(`:29`)도 죽은 문장이 된다 |
| scan_manager | "절차 변경 없음" | 코드 변경 없음 | 새 계약 조건 **보류 거리(하강 속도 × (delay + duration)) < 기준점 → 윗면 거리**를 강제하는 곳이 없다. `params.py:243-248`은 `max_descend_m` ↔ 지지면만 본다. `descend_speed_mps`는 SetConfig 대상(계약 6.4)이라 웹에서 속도를 올리면 보류 거리가 같이 늘어난다(3 mm/s → 22.5 mm, 10 mm/s → 75 mm). 재시작 경로는 원점으로 돌아간 뒤 하강하므로(`sequence.py:576-580`) 추가 위험 없음 — 확인함 |
| safety_monitor | 변경 없음 | — | 보류 구간의 유일한 보호가 `over_force_n` 30 N이다(1차 contact_detector + 2차 safety_monitor). 새 탐침 43 N/mm 기준 0.7 mm 침투(현지 코멘트). 수동 goal 30 mm 하강(#122 절차)에서는 여유 7.5 mm |
| 설계 문서 | 4.2 · L12 · architecture 카드 | 없음 | 3-3 표 마지막 행 |
| `ros-interfaces.md` 머리말 | v0.1.12 구절 | 있음 | 구절이 맺음 문장("변경은 PR + `CHANGELOG.md`로만 한다.") **뒤에** 붙었다(diff). 병합 전 위치 정정 필요 |
| 관련 미결 | — | — | 이슈 #128 OPEN "[계약] 밀기 EDGE: z는 1 mm밖에 안 떨어진다. 힘 꺾임 판정 추가 여부" — v0.1.12 직후 3.3을 또 고칠 후보 |

---

#### 5. CODEOWNERS · 브랜치 보호와 승인 실태

##### 5-1. 규칙
- `.github/CODEOWNERS`: `/ws_cobot1/src/contact_scan_interfaces/` · `/docs/contracts/` = @yujh5537 @ok778ts123. 더 구체적인 규칙이 우선: `mqtt-schema.md` = @ok778ts123 @EuiseokJeongNZ, `units-frames.md` = @rokeyhak @yujh5537. 그 밖에 `geometry_estimator/`, `/CLAUDE.md`, `/.claude/`, `/.github/`. **`contact_detector/` · `robot_manager/` · `scan_manager/`(geometry_estimator 제외) · `contact_scan_bringup/config/*.yaml` · `docs/design/`은 CODEOWNERS에 없다** → CI 통과 후 작성자가 직접 머지.
- 브랜치 보호(main, `gh api` 읽기): `require_code_owner_reviews: true`, `required_approving_review_count: 0`, **`dismiss_stale_reviews: false`**, `require_last_push_approval: false`, `enforce_admins: false`, 필수 체크 `ros` · `web`, force push · 삭제 금지.
- 보호 동작 시험 흔적: #43(일반 경로, 리뷰 없이 병합) · #44(계약 경로, 승인 없어 CLOSED) · #45(원복) — `pr_timeline.txt:2-4`.

##### 5-2. 계약 PR 승인 현황 — **코드오너 승인 없이 main에 병합된 계약 PR은 없다**
| PR | 작성자 | 닿은 오너 경로 | 승인(코드오너) | 병합자 |
|---|---|---|---|---|
| #47 | ok778ts123 | contracts 전체 · interfaces | EuiseokJeongNZ ×2 · rokeyhak · yujh5537 | 작성자 |
| #57 · #60 · #80 · #110 | rokeyhak | units-frames · CHANGELOG | yujh5537 + ok778ts123 | 작성자 |
| #62 | ok778ts123 | interfaces/package.xml | yujh5537 | 작성자 |
| #72 · #83 · #85 | rokeyhak | ros-interfaces · CHANGELOG (#85는 `.claude/`도) | yujh5537 | 작성자 |
| #79 | ok778ts123 | ros-interfaces · ContactEvent.msg | yujh5537 | 작성자 |
| #82 | ok778ts123 | units-frames · CHANGELOG | rokeyhak + yujh5537 | 작성자 |
| #98 | rokeyhak | ros-interfaces | ok778ts123 + yujh5537 | 작성자 |
| #91 | ok778ts123 | ros-interfaces · mqtt-schema · ScanConfig.msg | EuiseokJeongNZ(mqtt-schema) + yujh5537 | 작성자 |

##### 5-3. 승인 규칙의 빈틈(사례)
1. **승인 뒤 추가 커밋이 재승인 없이 병합**(`dismiss_stale_reviews: false`). `gh pr view`의 리뷰 시각 ↔ 마지막 커밋 시각(UTC → KST +9):
   - **#110**: 승인 14:05 · 14:11 → `80fc5a1` 14:15 "TCP는 z만 확정, x · y는 옛 탐침 값 임시 — 좌표를 켜는 조건 둘로" → 병합 14:23. **계약 본문의 실질 변경**이 승인 뒤에 들어갔다(커밋 제목상 리뷰 반영).
   - **#72**: 승인 15:08(현지, "17cf875 확인했습니다") → `df4dfc4` 15:14 "리뷰 반영 2: 상태 발행 전 moving 재계산, yaml robot_manager 절" → 병합 15:21.
   - **#85**: 승인 16:13 → `222369f` 16:21 `.claude/rules/contracts.md` 규칙 추가(`/.claude/`는 오너 경로) → 병합 16:33. 리뷰 본문이 요청한 내용이라 위험은 낮다.
   - **#98**: 승인 10:32 · 10:47 → 세 커밋의 committedDate가 전부 11:06(리베이스) → 병합 11:09. 승인 리뷰가 요청한 문장 수정(`ros-interfaces.md:599`)은 **반영되지 않은 채** 병합.
   - #57(`f374f5c`, 리뷰어 요청 표기 수정) · #82(main 머지 커밋)도 같은 형태지만 내용상 무해.
   - 주의: committedDate는 push 시각과 다를 수 있다(리베이스). push 시각은 미확인.
2. **#49는 main이 아닌 브랜치로 병합** — 승인자는 EuiseokJeongNZ 한 명(`contact_scan_interfaces/`의 코드오너 아님). 보호 대상이 main뿐이라 가능했다. 내용은 #47에서 코드오너 3명이 다시 봤으므로 실질 구멍은 아니다.
3. **v0.0은 PR 없이 main 직접 커밋**(`f96fdc0`) — 보호 설정 이전. `enforce_admins: false`라 레포 소유자(yujh5537)는 지금도 우회 가능(사용 사례는 `f96fdc0` 외 미확인).
4. **계약의 "뜻"을 바꾸는 코드 PR은 오너 경로를 안 거친다** — #101(`moving` 판정식, `/robot/stop` 신설: 리뷰 0건 `pr_timeline.txt:52`), #89(safety_monitor: 리뷰 0건), #86(contact_detector EDGE 판정: 리뷰 0건). 계약 문서를 안 건드리면 코드오너 승인이 필요 없다. ①의 `/robot/stop` 부재 50 h는 이 구조에서 나왔다(계약은 있었고, 구현 누락을 잡는 검사는 없었다). 현재 있는 자동 대조는 `contact_scan_interfaces/test/test_contract_sync.py`(문서 타입 전문 ↔ `.msg`) · `test_constants.py` · `contact_scan_bringup/test/test_config.py`(6.4절 이름)뿐이고, **"계약이 말한 서버 · 발행자가 실제로 떠 있는가"를 보는 시험은 없다**.

---

#### 6. 요약 (우선순위순)

1. 계약 이력 관리 자체는 양호: 계약 경로 14커밋 중 CHANGELOG 누락은 #62(메타데이터) 하나, 코드오너 무승인 병합 0건, v0.1 이후 타입 변경 0건.
2. 번호 · 표기 혼선: #82 제목 v0.1.7 ↔ CHANGELOG v0.1.6, 병합 순서 .10 → .11 → .9, #83 · #85는 번호 없이 v0.1.4에 추가, v0.1.11 · .12는 PR 번호 대신 이슈 번호, `mqtt-schema.md` 머리말에 v0.1.9 없음.
3. 설계 문서는 #48(09-19 14:31) 이후 0회 갱신 — v0.1.2~.11 미반영. 선은 맞고, 정의서 3~6장의 뜻 · 파라미터 · 수치 14항목이 어긋남. "README 6절 규칙"은 레포에 없음(미확인).
4. 계약 문서 내부 미갱신: `ros-interfaces.md:115`(moving TBD 잔존) · `:459`(`home_pose`) · `:599`(두 리뷰어가 요청한 문장 미수정) · 실기 주기표 미기재 · #101의 moving 판정식 변경 미기재 · BRD TR-02 "2종" ↔ 배치 원칙 "한 종".
5. 파급 누락: `/robot/stop` 서버 50.2 h 부재(해소, 실기 미확인) · robot_manager 툴/TCP 확인(#123 OPEN) · safety_monitor 작업영역/heartbeat(T33 OPEN) · 웹 `hb/web` 미발행 · DB `scan_id` 단일 키 · `real.yaml:167` 실측 계획이 v0.1.5 정의와 어긋남 · yaml 근거 주석이 v0.1.10 이전 숫자 · 2.1° 처리 미결정.
6. #127(v0.1.12): 리뷰 0건, 현지의 "보류 → 둔한 임계" 제안이 받아들여지면 계약 문구가 병합 전에 바뀜. 보류 거리 조건을 강제하는 코드 없음. 머리말 구절 위치 오류. 실기 START는 #127 · #122가 들어가기 전까지 거절 상태.


---

## 부록 G. PR 타임라인 (KST)

```
num|author|state|branch|created(KST)|merged/closed|hours_open|+/-|files|commits|commits_after_first_review|first_review_h|reviews|comments|title
#43|yujh5537|MERGED|test-protection-normal|09-18 15:41|09-18 15:43|0.0|+2/-0|1|1|0|-|-|0|test: 일반 경로 머지 확인
#44|yujh5537|CLOSED|test-protection-contract|09-18 15:41|09-18 15:43|0.0|+2/-0|1|1|0|-|-|0|test: 계약 경로 코드오너 승인 확인
#45|yujh5537|MERGED|chore-revert-test-line|09-18 15:43|09-18 15:44|0.0|+0/-2|1|1|0|-|-|0|chore: 브랜치 보호 확인용 주석 원복
#46|EuiseokJeongNZ|MERGED|t11-docker-compose|09-18 20:20|09-18 20:22|0.0|+497/-2|12|2|0|-|-|0|T11 docker compose
#47|ok778ts123|MERGED|t01-contract-freeze|09-18 20:43|09-19 12:28|15.8|+1908/-97|31|3|2|0.8|EuiseokJeongNZ:APPROVED,rokeyhak:APPROVED,yujh5537:COMMENTED,EuiseokJeongNZ:APPROVED,yujh5537:APPROVED|5|[T01] 계약 v0.1 동결 (인터페이스 동결 회의 결과)
#48|ok778ts123|MERGED|docs-design-v0.1|09-18 20:43|09-19 14:31|17.8|+4216/-48|12|5|1|17.6|yujh5537:APPROVED|1|[docs] BRD v3.2.0 교체, 설계 문서(docs/design) 업로드
#49|ok778ts123|MERGED|t09-interfaces|09-18 21:24|09-18 21:38|0.2|+722/-4|28|1|0|0.2|EuiseokJeongNZ:APPROVED|2|[T09] contact_scan_interfaces 패키지 (계약 v0.1)
#50|ok778ts123|MERGED|t10-scan-state-machine|09-18 21:51|09-19 14:12|16.3|+1370/-0|14|2|0|-|-|0|[T10] scan_manager 상태 기계 골격
#56|EuiseokJeongNZ|MERGED|t12-react-three-mock|09-19 13:07|09-19 13:37|0.5|+3598/-2|15|7|0|-|-|0|[T12] React·Three.js 프론트 골격, MQTT 목업 발행기
#57|rokeyhak|MERGED|t02-tool-tcp-register|09-19 13:21|09-19 16:14|2.9|+602/-5|6|5|1|1.1|yujh5537:APPROVED,ok778ts123:APPROVED|3|[T02] 실기 연결, 툴 무게·TCP 등록, 무접촉 외력 측정
#58|EuiseokJeongNZ|CLOSED|t22-fastapi-live-20260919|09-19 13:54|09-19 13:57|0.0|+350/-64|5|1|0|-|-|0|[T22] FastAPI 실시간 중계와 명령 상태 처리
#59|EuiseokJeongNZ|CLOSED|t23-live-view-20260919|09-19 13:54|09-19 13:57|0.0|+171/-442|6|1|0|-|-|0|[T23] 실시간 3D 관제와 네 독립 명령 연결
#60|rokeyhak|MERGED|t03-origin-home|09-19 14:02|09-19 17:58|3.9|+133/-7|3|5|0|3.9|yujh5537:APPROVED,ok778ts123:APPROVED|13|[T03] 작업대 원점(초안)·z=0·축 평행·홈 관절각
#61|yujh5537|MERGED|t05-bringup-skeleton|09-19 14:16|09-20 09:27|19.2|+545/-0|12|4|0|-|-|2|[T05] contact_scan_bringup 골격과 sim/real 파라미터 파일
#62|ok778ts123|MERGED|chore-maintainer-noreply|09-19 14:18|09-19 14:51|0.5|+3/-3|3|1|0|0.5|yujh5537:APPROVED|0|chore: maintainer 이메일을 GitHub noreply 주소로 변경
#63|ok778ts123|MERGED|chore-mqtt-bridge-owner|09-19 15:14|09-19 16:53|1.7|+3/-3|3|2|1|1.5|EuiseokJeongNZ:APPROVED|1|chore: T21(mqtt_bridge 구현) 담당을 병후에서 의석으로 변경
#64|ok778ts123|MERGED|t20-result-store|09-19 16:57|09-19 17:47|0.8|+3671/-0|8|2|0|-|-|0|[T20] result_store 로컬 기록
#65|EuiseokJeongNZ|MERGED|t22-fastapi-mqtt-websocket|09-19 17:15|09-19 17:22|0.1|+735/-33|3|2|0|-|-|1|[T22] FastAPI MQTT↔WebSocket 및 REST→MQTT 명령 브리지
#66|rokeyhak|MERGED|t04-api-check-log|09-19 17:21|09-21 15:45|46.4|+498/-14|3|4|4|18.8|yujh5537:COMMENTED,ok778ts123:APPROVED|10|[T04] API 호출 확인 로그 (Virtual), ws_dsr 커밋 · DRCF 버전
#67|EuiseokJeongNZ|MERGED|t21-mqtt-bridge|09-19 17:41|09-20 12:04|18.4|+1599/-0|15|1|0|18.3|ok778ts123:APPROVED|3|[T21] mqtt_bridge: MQTT 명령 6종 ↔ ROS Action/Service, 상태·샘플·이벤트·결과·로그 발행
#68|yujh5537|MERGED|t07-contact-detector-skeleton|09-20 09:35|09-20 12:02|2.5|+860/-0|14|4|0|-|-|0|[T07] contact_detector 골격과 판정 코어 (1/2: sim 입력원은 후속)
#70|yujh5537|MERGED|t17-geometry-estimator|09-20 10:20|09-20 12:01|1.7|+594/-0|5|1|0|1.4|ok778ts123:APPROVED|1|[T17] geometry_estimator와 단위 테스트 (편향 보정, 외곽 엣지·경로 후보, 직육면체, 비정상 검출)
#71|rokeyhak|MERGED|t08-sample-recorder|09-20 10:22|09-20 16:41|6.3|+129/-16|1|3|0|6.2|yujh5537:APPROVED|5|[T08] 샘플 기록기: --csv, --duration, --interval 0
#72|rokeyhak|MERGED|t15-robot-sample|09-20 10:48|09-20 15:21|4.5|+1067/-3|18|4|1|4.3|yujh5537:APPROVED|9|[T15] robot_manager: RobotSample · RobotStatus 발행
#73|rokeyhak|MERGED|t13-execute-motion|09-20 11:04|09-21 09:44|22.7|+1196/-129|11|6|0|22.6|yujh5537:APPROVED,ok778ts123:APPROVED|16|[T13] robot_manager: execute_motion Action (하강·슬라이딩·이동·홈)
#74|yujh5537|MERGED|t16-offline-analyzer|09-20 12:07|09-20 14:04|1.9|+326/-2|5|2|0|-|-|0|[T16] 오프라인 분석기 analyze_samples (기록 CSV로 실측 주기·잡음·임계×디바운스 비교)
#75|yujh5537|MERGED|t17-readme-offset-rule|09-20 12:08|09-20 14:35|2.5|+9/-0|1|1|0|0.3|ok778ts123:APPROVED|2|[T17] docs: edge_bias_offset_m 부호·단위 규약 (방향당 값)
#76|ok778ts123|MERGED|t19a-scan-sequence|09-20 12:37|09-20 15:07|2.5|+2189/-3|12|5|0|-|-|0|[T19a 1/2] scan_manager 시퀀스 순수 모듈 (params · sequence · event_matcher · geometry_adapter)
#77|ok778ts123|MERGED|t19a-scan-node|09-20 12:57|09-20 16:31|3.6|+2724/-37|13|6|0|-|-|2|[T19a 2/2] scan_manager 시퀀스 · 서버 · geometry 연결 (가짜 상대 노드로 검증)
#78|EuiseokJeongNZ|MERGED|t23-live-view-20260920|09-20 13:17|09-20 13:38|0.4|+599/-66|3|1|0|-|-|1|[T23] 3D 뷰·4버튼·단계 표시를 실데이터에 연결 (WebSocket · REST)
#79|ok778ts123|MERGED|t69-judgement-sample|09-20 13:18|09-20 16:07|2.8|+37/-15|3|1|0|2.7|yujh5537:APPROVED|2|[계약] ContactEvent "판정 샘플" 정의: 조건이 처음 성립한 샘플 (v0.1.5)
#80|rokeyhak|MERGED|t03-cube-correction|09-20 13:55|09-20 17:27|3.5|+2484/-26|10|3|2|2.8|ok778ts123:APPROVED,yujh5537:APPROVED|25|[T03 후속] 실기 측정: 옆면 2.1° 기울기, 검출 편향 2.25 mm(잠정), 라운드 가설 폐기
#81|ok778ts123|MERGED|docs-ros-domain-id-range|09-20 14:24|09-20 14:35|0.2|+2/-2|2|2|0|-|-|0|docs: ROS_DOMAIN_ID 조 내 분리 범위를 31~39로 정정
#82|ok778ts123|MERGED|t19a-units-frames-origin-pose|09-20 15:23|09-20 16:20|0.9|+8/-2|2|4|4|0.3|rokeyhak:APPROVED,yujh5537:APPROVED|2|[계약] units-frames: 탐색 기준점을 scan_manager 파라미터 search_origin_pose로 둔다 (v0.1.7)
#83|rokeyhak|MERGED|t15-followup-race|09-20 15:38|09-20 15:47|0.2|+8/-3|4|2|0|0.1|yujh5537:APPROVED|2|[T15 후속] pending_calls 경쟁 조건, qt_hmi 링크 제거, 계약 통지 문장
#84|EuiseokJeongNZ|MERGED|t28-postgresql-fastapi-db-write|09-20 15:59|09-20 16:09|0.2|+666/-7|5|2|0|-|-|1|[T28] PostgreSQL 스키마와 FastAPI 측정·이벤트 저장
#85|rokeyhak|MERGED|t15-followup-header|09-20 16:07|09-20 16:33|0.4|+3/-1|3|2|1|0.1|yujh5537:APPROVED|4|[계약] ros-interfaces 머리말에 v0.1.4 구절 기재 (누락 보완)
#86|yujh5537|MERGED|t16-detector-wiring|09-20 16:23|09-20 17:08|0.7|+796/-50|7|2|0|-|-|1|[T16] contact_detector 노드 배선과 접촉 소실(EDGE) 판정
#88|EuiseokJeongNZ|MERGED|t87-mqtt-bridge-sigint-shutdown|09-20 16:34|09-21 09:43|17.2|+1/-1|1|1|0|-|-|1|[T87] mqtt_bridge SIGINT 종료 오류 수정
#89|yujh5537|MERGED|t18-safety-monitor|09-20 16:53|09-20 17:08|0.2|+1483/-0|14|1|0|-|-|0|[T18] safety_monitor 최소판 (30 N, 하강 제한 5 mm에서 정지 요청)
#91|ok778ts123|MERGED|t51-54-contract-docs|09-20 17:14|09-21 14:47|21.6|+38/-8|4|3|3|16.5|yujh5537:COMMENTED,EuiseokJeongNZ:APPROVED,yujh5537:APPROVED|7|[계약] 문서 보완: target_force_n 대응 · recontact 파라미터 · MQTT TBD · 결과 중복 키 (v0.1.9)
#92|yujh5537|MERGED|t06-daily-reports|09-20 17:16|09-21 10:30|17.2|+407/-0|5|4|0|-|-|2|[T06][T08] 저녁 통합 기록 4건(9/18~9/21)과 TR-01 부분 실시 기록
#93|EuiseokJeongNZ|MERGED|euiseok/20260920-t29-log-panel|09-20 17:16|09-20 17:52|0.6|+428/-14|2|2|0|-|-|2|[T29] 시간순 로그 패널과 명령별 접수/거절 · 완료/실패 표시
#94|rokeyhak|MERGED|ci-dsr-msgs2|09-20 17:37|09-20 17:58|0.4|+54/-3|2|2|0|0.3|yujh5537:APPROVED,ok778ts123:APPROVED|5|[CI] dsr_msgs2 를 빌드해 robot_manager 노드 시험을 실제로 돌린다
#95|ok778ts123|MERGED|t26-stop-home-resume|09-20 17:38|09-21 11:01|17.4|+2250/-63|15|3|0|17.0|yujh5537:APPROVED|2|[T26] scan_manager 재시작: 중단 위치부터 계속 (중지 · 안전복귀 점검 포함)
#96|ok778ts123|MERGED|docs-schedule-sync-0920|09-20 17:54|09-21 09:20|15.4|+0/-0|1|1|0|-|-|0|[문서] 개발일정 엑셀을 구글드라이브 최신본(9/20)으로 갱신
#97|yujh5537|MERGED|t07-sim-source|09-20 18:09|09-21 09:15|15.1|+441/-21|9|1|0|-|-|1|[T07] sim 입력원(가상 직육면체), 샘플 공백 시 추세선 초기화, scan_manager 파라미터 채움
#98|rokeyhak|MERGED|t15-rate-loaddep|09-21 08:39|09-21 11:09|2.5|+36/-6|2|3|3|1.9|ok778ts123:APPROVED,yujh5537:APPROVED|6|[계약] 6.3 발행 주기를 부하 의존 범위로 — 두 번째 실측과 공백 꼬리 (v0.1.10)
#99|yujh5537|MERGED|t18-startup-grace|09-21 09:37|09-21 09:39|0.0|+69/-20|6|1|0|-|-|0|[T18] safety_monitor 기동 유예 — 뜨자마자 래치가 걸리던 것
#100|yujh5537|MERGED|t07-sim-reachable|09-21 10:17|09-21 15:14|5.0|+18/-5|2|1|0|-|-|3|[T07] sim 좌표를 도달 가능한 곳으로, home_joint_deg 추가 — M2 통과
#101|rokeyhak|MERGED|t15-stop-service-and-moving|09-21 11:44|09-21 14:41|2.9|+344/-7|4|2|0|-|-|5|[T15] /robot/stop 서버를 만들고, 샘플 공백 뒤 정지 오판을 막는다
#104|ok778ts123|MERGED|t19b-setconfig-propagation|09-21 12:20|09-21 14:19|2.0|+1231/-41|8|2|0|-|-|0|[T19b] scan_manager SetConfig 전파 P01~P03 (실제 노드 · Virtual 종단 검증 포함)
#106|ok778ts123|MERGED|t19b-sim-yaml-box|09-21 12:29|09-21 12:54|0.4|+42/-8|2|1|0|-|-|0|[T19b] test_sim_process 의 가상 직육면체를 sim.yaml 에서 읽는다 (#100 CI 실패 해소)
#110|rokeyhak|MERGED|t108-placement-probe-precondition|09-21 13:03|09-21 14:23|1.3|+579/-31|13|3|2|1.0|yujh5537:APPROVED,ok778ts123:APPROVED|3|[계약] 배치 원칙 · 탐침 상태 전제조건, 탐침 교체 후 TCP z 252.12 확정 (v0.1.11)
#112|EuiseokJeongNZ|MERGED|euiseok/20260921-t27-mqtt-web-integration|09-21 14:20|09-21 14:47|0.4|+71/-0|1|2|0|0.3|ok778ts123:APPROVED|1|[T27] mqtt_bridge ↔ FastAPI 실제 연결 검증 (웹 버튼으로 sim 스캔 시작·중지)
#114|rokeyhak|MERGED|t113-stop-unconfirmed-keep|09-21 14:43|09-21 14:53|0.2|+47/-1|3|1|0|-|-|2|[T15 후속] 동작 중 /robot/stop 정지 확인 실패 시 요청을 남긴다 (#113)
#116|rokeyhak|MERGED|t-home-not-blocked-by-stop|09-21 14:55|09-21 15:02|0.1|+87/-10|3|1|0|-|-|0|[T15 후속] 남은 정지 요청이 안전복귀(OP_HOME)를 막지 않게 한다 (#115)
#117|yujh5537|MERGED|t102-logger-severity|09-21 14:55|09-21 15:06|0.2|+37/-3|2|1|0|-|-|0|[버그] safety_monitor가 severity를 같은 줄에서 바꿔 죽던 것
#118|ok778ts123|MERGED|t19-failure-position|09-21 14:59|09-21 16:41|1.7|+252/-25|9|2|0|-|-|1|[T19] scan_manager 실패 기록에 정지 좌표를 남긴다 (원인 · 단계 · 위치)
#119|ok778ts123|MERGED|t19-quiet-shutdown|09-21 15:03|09-21 16:22|1.3|+119/-7|4|1|0|-|-|0|[버그] scan_manager: 모션 도중 SIGINT 에 트레이스백 없이 끝낸다 (#111 의 scan_manager 몫)
#121|rokeyhak|MERGED|t14-release-all-paths|09-21 15:14|09-21 16:26|1.2|+209/-10|3|3|0|-|-|3|[T14] 순응 · 힘 제어 해제를 모든 종료 경로에서 시험하고, 켜기 시간 초과 때 켜진 채 남던 구멍을 닫는다
#122|rokeyhak|OPEN|t30-pm-session-plan|09-21 15:18|None|OPEN|+263/-0|2|1|0|-|-|0|[T30 선행 · T24 · T25] 오후 실기 절차서와 J6 180° TCP x · y 계산 스크립트
#124|ok778ts123|MERGED|t107-node-test-flaky|09-21 15:37|09-21 16:06|0.5|+16/-5|2|1|0|-|-|0|[버그] #107 scan_manager 노드 시험: 부하에서 0.2 s 한도가 넘어 104로 실패하던 것
#127|rokeyhak|OPEN|t109-descend-tare-slide-arm|09-21 16:49|None|OPEN|+450/-20|9|1|0|-|-|2|[#109] 하강 기준과 밀기 기준을 나눈다: 하강은 이동 중 자동 영점, 밀기는 z 로 판정 켜기 (계약 v0.1.12)
```
