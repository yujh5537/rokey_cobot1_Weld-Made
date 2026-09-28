근거: `docs/design/contact-scan-system-architecture-v1.6.drawio`(형식 출발) · `docs/architecture.md` · `docs/contracts/ros-interfaces.md` · `mqtt-schema.md` · `docs/phase2/weld-ros-interfaces.md` · `ws_cobot1/src/*` · `backend/app/main.py` · `backend/spring` · `frontend/src/App.jsx` · `docker/docker-compose.yml` · `docker/mosquitto/config/mosquitto.conf` (origin/main `2335057`, 2026-09-28) · 구현 PR #191 · #195 ~ #197 (머지 전)

# 01. 시스템 아키텍처 (v1.7)

> **문서 상태**: 계약 v0.1.22 · phase 2 v0.2.0 · main `2335057` 대조 (2026-09-28). 이 그림과 계약(`docs/contracts/`)이 다르면 계약이 맞다.
> **v1.7 (2026-09-28, 병후)**: 설계 그림 v1.6(9/19) 의 형식 — PC 경계 3 구역 · 카드마다 **입력 → 처리 로직 → 출력** · 화살표 색 = 데이터 갈래 — 을 그대로 쓰고, 카드 내용을 지금 코드로 다시 채웠다. 9/27 첫 판(matplotlib 요약 그림)은 `archive/v1-matplotlib-graphviz/` 에 있다.
> 짝 문서: [05 인터페이스 정의서](05-interfaces.md)(필드 · 시나리오) · [06 ROS2 노드 구조도](06-node-graph.md)(선 하나하나의 이름 · 종류 · 타입)

**그림 원본 [`01-system-architecture.drawio`](01-system-architecture.drawio)** — [app.diagrams.net](https://app.diagrams.net) 에서 연다. 쪽 2 개:

| 쪽 | 내용 | png |
|---|---|---|
| 1. 시스템 아키텍처 v1.7 (phase 2 포함) | 카드 13 장(웹 5 · 메인 PC 6 · 로봇 1 · phase 2 1) + 설명 쪽지 3 장 + phase 2 구현 상태 쪽지 1 장(레이어). phase 2 는 레이어 **"phase 2 (용접)"** 에 있어 끄면 1 차만 남는다 | [`01-system-architecture.png`](01-system-architecture.png) |
| 2. 시스템 아키텍처 v1.7 (1차만) | 1 쪽에서 phase 2 를 뺀 판(9/29 에 용접을 발표에서 빼면 이 그림) | [`01-system-architecture-no-phase2.png`](01-system-architecture-no-phase2.png) |

![시스템 아키텍처 v1.7](01-system-architecture.png)

**읽는 법** (v1.6 과 같다) — 두꺼운 테두리 = 그 카드가 도는 컴퓨터(분홍 웹 PC · 파랑 메인 PC · 초록 로봇 컨트롤러). 카드 안은 왼쪽 입력 → 가운데 처리 로직(번호 단계 · 살구색 마름모 = 판단) → 오른쪽 출력. 카드 사이 굵은 화살표 색 = 갈래(명령 · 표시 데이터 · 로봇 상태 · 접촉 이벤트 · 모션 · 안전 · 저장 · 업무), 카드 안 가는 회색 = 입력 → 단계 → 출력. **점선 항목 · 점선 화살표 = 계약에만 있고 코드에는 없는 것.** 머리띠 색: 회색 = 제공 · 설치 사용, 분홍 = 우리 웹 코드, 파랑 = 우리 ROS 2 노드, 주황 = phase 2. 그림 전체 크기는 5280 × 6226 px 이라 png 는 확대해서 본다.

---

## 1. 구성

| 컴퓨터 | 카드 | 역할 | 담당 |
|---|---|---|---|
| 브라우저 | React + Three.js (Vite :5173, **Docker 밖** `npm run dev`) | 버튼 5 개(**시작 · 중지 · 안전복귀 · 재시작 · 안전 해제**) → FastAPI REST. `/ws` 로 받은 상태 · 3D 로봇(관절) · 접촉점 · 결과 · 로그 표시(mm). 설정 등록 버튼은 없다(TR-05). Spring 은 부르지 않는다 | 의석 |
| 웹 PC (Docker 4 서비스) | FastAPI :8000 | REST 명령 → `request_id` 를 붙여 MQTT 발행, MQTT → WebSocket `/ws` 방송(가상 토픽 `command/status` 포함), `scan/result` · `contact/event` → DB upsert | 의석 |
| | MQTT Broker (Mosquitto 2) :1883 | 두 PC 사이 단일 중계. 판단하지 않는다. 익명 접속 · persistence(retain · QoS 1 대기 메시지 보관) | 의석 |
| | PostgreSQL 16 :5432 | 측정 4 테이블(FastAPI 가 쓴다) + 업무 3 테이블(Spring). 원격 조회용 — 재시작 원본은 메인 PC | 의석 |
| | Spring Boot :8080 | `/api/history/scans` 이력 조회 + 대상물 · 작업 등록 · 수정 · 작업 ↔ 스캔 연결(`/api/workpieces` · `/api/work-orders`). 화면과는 아직 연결 없음 | 의석 |
| 메인 PC (Ubuntu 24.04 · ROS 2 Jazzy) | safety_monitor | 감시 4 가지(과대 외력 · 하강 제한 2 차 · 샘플 끊김 · 상태 끊김) → 웹을 거치지 않고 `/robot/stop` · 래치 | 현지 |
| | scan_manager (+ geometry_estimator · result_store) | 스캔 순서 상태기계 · 중지 · 안전복귀 · 재시작 조정 · SetConfig 전파 · 5 점 → 직육면체 · 로컬 원본 | 병후 (geometry_estimator 현지) |
| | mqtt_bridge | ROS 2 ↔ MQTT · 명령 검사 · 접수(`cmd/ack`) ≠ 완료(`scan/command_result`) · m → mm · NaN → null | 의석 (T27 병후 공동) |
| | contact_detector | CONTACT · EDGE · OVER_FORCE 판정 · tare | 현지 |
| | robot_manager | 모션 · 힘/순응 제어와 그 해제 · 샘플 · 상태 발행 · 스텝 모드 모서리 탐색 · **두산 드라이버를 부르는 유일한 노드** | 학민 |
| | 제공 드라이버 | `dsr_controller2`(`/dsr01`) · `onrobot_driver`. 수정하지 않는다 | — |
| | **weld_manager [phase 2]** | 스캔 결과의 모서리 8 개를 45° · 스탠드오프 · 위빙 경유점으로 따라간다 | 현지 (구현 PR 머지 전) |
| 로봇 컨트롤러 | M0609 (DRCF) · RG2 · 무센서 탐침 팁 · 작업대 | 하드웨어 안전(비상정지 · 보호 정지 · 충돌 감지)은 여기에 있다 | — |

카드마다의 입력 · 처리 단계 · 출력은 그림에 있다. 같은 내용을 글로 읽으려면 05 의 1 장(시나리오)과 6 장(파라미터).

## 2. 데이터 흐름 (갈래 = 화살표 색)

| 갈래 | 흐름 | 이름 (계약) |
|---|---|---|
| 명령 | 브라우저 → FastAPI → MQTT → mqtt_bridge → scan_manager(안전 해제는 safety_monitor) | `/commands/*` → `cmd/scan/{start,stop,home,resume,set_config}` · `cmd/safety/reset` → `/scan/run` · `/scan/home` · `/scan/resume` (A) · `/scan/stop` · `/scan/set_config` · `/safety/reset` (S). SetConfig 전파 P01 ~ P03 도 이 갈래 |
| 표시 데이터 | 노드 → mqtt_bridge → MQTT → FastAPI → WebSocket → 화면 | `/scan/state` · `/scan/result` · `/scan/log` · `/robot/*` · `/contact/event` · `/safety/status` → `scan/*` · `robot/*` · `contact/event` · `safety/status`. 접수 `cmd/ack` · 완료 `scan/command_result` |
| 모션 | scan_manager → robot_manager → 두산 드라이버 → 컨트롤러 | `/robot/execute_motion` (A) · `/contact/tare` (S) · `dsr_msgs2` 10 개 · DRCF TCP/IP. [P2] `/robot/execute_path` |
| 로봇 상태 | robot_manager → contact_detector · safety_monitor · scan_manager · mqtt_bridge | `/robot/sample`(TCP · 힘 + 실행 중 `motion_id` · `operation`) · `/robot/status`(정지 완료의 근거) · `/dsr01/joint_states`(표시 전용) |
| 접촉 이벤트 | contact_detector(스텝 EDGE 는 robot_manager) → robot_manager · scan_manager · mqtt_bridge | `/contact/event` |
| 안전 | safety_monitor → robot_manager (**웹 경유 없음**) · scan_manager | `/robot/stop` (S) · `/safety/status`. 래치 해제는 `/safety/reset` 로만 |
| 저장 | 메인 PC 원본 + 웹 DB | result_store `progress.json` · `result.json`(재시작 원본) / FastAPI → PostgreSQL(측정) · Spring ↔ PostgreSQL(업무). [P2] weld_manager 가 `result.json` 을 읽는다 |
| 업무 | PostgreSQL → Spring | REST 조회 |

## 3. 지켜야 할 경계 (`docs/architecture.md` · 계약 1장)
- 정지와 접촉 판정은 메인 PC 안에서 끝난다. 웹이 끊겨도 로컬 정지와 원본 보관은 동작한다.
- 작업 중지 · 안전복귀 · 재시작 · 안전 해제는 독립 명령이다. 중지는 홈 복귀나 재시작을 부르지 않는다. 실패해도 자동 홈 복귀는 없다.
- 정지의 완료는 `/robot/status` 의 `connected && !moving` 으로만 본다. `accepted` 는 접수다.
- 재시작은 웹 DB 가 아니라 result_store 의 로컬 기록을 쓴다.
- 화면의 중지 버튼은 안전 등급 기능이 아니다. 최종 안전 수단은 티치펜던트 비상정지와 로봇의 충돌 감지다.

## 4. phase 2 (용접) — 더한 것과 구현 상태
계약은 v0.2.0 으로 main 에 있다(`docs/phase2/`, PR #184 · #198 · #199). **main 에 있는 구현은 scan_manager 의 601 거절(P5 #204)과 브리지 이름표 `WELD_PATH`(#200) 뿐이다**(2026-09-28). 그림에서는 주황 카드 · 주황 테두리 항목 · 레이어로 구분했다.

| 더한 것 | 계약 | 구현 | 상태 (9/28) |
|---|---|---|---|
| `weld_manager` 노드 (6 번째) | `weld-ros-interfaces.md` · `weld-motion.md` | 현지, PR #195 → #196 → #197 | 머지 전. Virtual 8 선 완주 246 s(sim 박스 100 × 60 × 40 mm, #197 브랜치의 `docs/test-reports/p2-weld-virtual_20260925.md`) |
| `/robot/execute_path` (ExecutePath) | 5.2 절 | PR #191 | 머지 전. line 모드만 쓴다(D31) · 출발점 z 검사(D35) |
| 스캔 ↔ 용접 배타 | 7.1 절 | 601: 병후 #204 **main** · 600: weld_manager #197 | 601 main · 600 머지 전 |
| mqtt_bridge `cmd/weld/*` · `weld/*` (P4) · 웹 용접 화면 (P3) | `weld-mqtt-schema.md` | 의석 | PR 없음 — 그림에서 점선(계약만) |

실기 확인은 2026-09-29 예정이다(#205 계획). 9/23 측정에서 45° 자세로 16 자세 중 12 에 도달했고 L1 · L5 는 도달하지 못했다(`docs/phase2/measurements-20260923.md`, #186). 세로선 아래 4 자세는 계약 z 보다 17.12 mm 위에서만 확인했다. 계약과 구현의 차이는 05 의 15.5 절.

## 5. 계약에는 있고 코드에는 없는 것 (그림의 점선)
| 항목 | 그림에서 | 자세히 |
|---|---|---|
| 웹의 `hb/web` · `conn/web` 발행, safety_monitor 의 `/scan/state` · `/web/heartbeat` 구독, heartbeat 만료 405 · 속도 401 · 작업영역 402 감시 | safety_monitor 입력의 점선 항목 · mqtt_bridge `/web/heartbeat` 출력 · 회색 점선 화살표 | 05 10.1 G1 ~ G3 |
| robot_manager 의 RG2 호출 · 시작 전 툴 · TCP 확인 | 제공 드라이버 카드의 점선 항목 | 05 10.1 G4 |
| 화면의 설정 등록 버튼(TR-05) | React 카드 부제 | 05 10.1 G6 |
| phase 2 의 mqtt_bridge · 웹 쪽 | 주황 점선 화살표(계약만 · 브리지 없음) | 05 15.3 |

## 6. v1.6 → v1.7 에서 바뀐 것
| # | 바뀐 것 | 근거 |
|---|---|---|
| 1 | **웹 PC 를 실제 구성으로**: Docker 4 서비스 + React 는 Docker 밖 · 포트 · FastAPI 경로 `/commands/*` · `/ws`(v1.6 의 `/api/scan/*` · `/ws/live`) · psycopg(v1.6 의 asyncpg) · Spring `/api/*` · DB 테이블 7 개(v1.6 의 `scan_result` · `scan_event` · `calibration_result` · `job` · `workpiece` · `user` 는 설계 때 이름) · React ↔ Spring 연결 삭제 · Mosquitto 설정(익명 · persistence) | `docker/` · `backend/` · `frontend/` |
| 2 | **스텝 모드 SLIDE**: robot_manager 가 긁고 멈춰 힘을 읽어 모서리를 찾고 EDGE 를 직접 발행 | 계약 v0.1.15 (PR #160) |
| 3 | **안전 감사 후속**: scan_manager 의 `/robot/sample` 구독 · 안전복귀 5 단계 · 오류 뒤 재시작 허용 403 · 404 · 407 · 정지 확인 실패 407 · 하강 제한 2 차 여유 5 mm | 계약 v0.1.21 (PR #161) |
| 4 | `/dsr01/joint_states` → mqtt_bridge → `robot/joints` · `robot/gripper_joints` (표시 전용) · 이름표 밖 값 `UNKNOWN_<n>` | 계약 v0.1.19 · v0.1.20 · v0.1.22 |
| 5 | 카드 내용을 코드 조사로 다시 씀: safety_monitor 감시 4 가지만(v1.6 의 속도 · 작업영역 · 연결 · HB 만료는 구현 없음), contact_detector 에 이동평균 필터 없음(디바운스 · 이동 기준 · 추세선), mqtt_bridge 토픽 이름표는 코드 고정, robot_manager 의 두산 서비스 10 개 · RG2 호출 없음 | 9/28 코드 조사 |
| 6 | 지운 것: `/scan/calibrate` · `/calibration/result` 검토안 항목(타입도 구현도 없다 — 05 9 장) | — |
| 7 | **phase 2**: weld_manager 카드 · robot_manager 의 ExecutePath · scan_manager 의 `/weld/state` · result.json 파일 연결 — 레이어로 끄고 켠다 | 계약 v0.2.0 (PR #184 · #198 · #199) |
| 8 | 계약과 구현이 다른 곳을 점선 항목 · 회색 점선 화살표로 표시 | 5 장 |
| 9 | 형식: v1.6 과 같은 drawio. 9/27 첫 판(matplotlib)은 보관 | `archive/v1-matplotlib-graphviz/` |

### 9/27 첫 판(matplotlib)에서 바로잡은 것
- 버튼 이름: "작업 시작 · 작업 중지" → 화면 라벨은 **시작 · 중지**.
- Spring: "조회 API 만" → 대상물 · 작업 등록 · 수정과 작업 ↔ 스캔 연결(POST · PUT)도 있다.
- Mosquitto: "저장하지 않는다" → 업무 데이터는 저장하지 않지만 persistence 로 retain · QoS 1 대기 메시지는 보관한다. 인증 없음(익명).
- `/web/heartbeat`: "mqtt_bridge 가 발행한다" → 발행 코드는 있지만 웹이 `hb/web` 을 보내지 않아 실제로는 나가지 않는다.

## 7. 그림 다시 만들기
- 작은 수정은 app.diagrams.net 에서 `01-system-architecture.drawio` 를 열어 고치고, 파일 → 내보내기 → PNG 로 같은 이름에 덮어쓴다.
- 처음 만들 때 쓴 스크립트: `python3 docs/deliverables/drawio_01.py` (카드 내용 · 선 목록이 이 파일에 있다. 색은 `drawio_lib.py`, v1.6 과 같은 값). 스크립트로 다시 만들면 손으로 고친 것은 사라진다.
- png 내보내기(Chrome · 인터넷 필요): `python3 docs/deliverables/drawio_export.py 01-system-architecture.drawio 1:01-system-architecture.png 2:01-system-architecture-no-phase2.png --scale 1`
