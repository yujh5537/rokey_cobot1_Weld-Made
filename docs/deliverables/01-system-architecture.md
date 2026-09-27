근거: `docs/architecture.md` · `docs/design/contact-scan-system-architecture-v1.6.drawio` · `docs/contracts/ros-interfaces.md` 2장 · `docs/contracts/mqtt-schema.md` 2장 · `docs/phase2/weld-ros-interfaces.md` 2장 · `docker/docker-compose.yml` · `backend/app/main.py` · `frontend/vite.config.js` (origin/main `07fa721`, 2026-09-27)

# 01. 시스템 아키텍처 (v1.7)

작성: 병후 · 2026-09-27. 그림은 `figures.py`(matplotlib)로 그렸다. 1차 원본 drawio(v1.6)는 이 PC 에서 열 수 없어 고치지 않았고, v1.7 은 그 내용 위에 현재 코드 · 계약과 phase 2 를 더해 새로 그렸다.

![시스템 아키텍처 v1.7](01-system-architecture.png)

- phase 2(용접)를 뺀 판: [`01-system-architecture-no-phase2.png`](01-system-architecture-no-phase2.png) — 9/29 에 용접을 발표에서 빼면 이 그림으로 바꾼다.
- 선 하나하나(이름 · 종류 · 타입)는 [06 노드 구조도](06-node-graph.md)에 있다. 이 그림은 갈래별 요약이다.

## 1. 구성

| 컴퓨터 | 구성요소 | 역할 | 담당 |
|---|---|---|---|
| 브라우저 | React + Three.js (Vite 5173, **Docker 밖** `npm run dev`) | 3D 형상 · 접촉점 · 로그, 버튼 6 개(작업 시작 · 작업 중지 · 안전복귀 · 재시작 · 설정 등록 · 안전 해제). FastAPI 로만 붙는다(`/commands/*` · `/ws` 프록시) | 의석 |
| 웹 PC (docker compose 4 서비스) | FastAPI :8000 | REST 명령(`/commands/scan/*` · `/commands/safety/reset`) → MQTT 발행, MQTT 구독 → WebSocket `/ws`, 측정 · 설정 · 이벤트 DB 쓰기 | 의석 |
| | Mosquitto :1883 | MQTT 브로커. 판단 · 저장하지 않고 중계만 한다 | 의석 |
| | PostgreSQL :5432 | `scan_jobs` · `measurements` · `scan_configs` · `contact_events` | 의석 |
| | Spring Boot :8080 | 작업 · 대상물 · 이력 조회 API(`/api/workpieces` · `/api/work-orders` · `/api/history/scans`). 지금 화면(React)은 부르지 않는다 | 의석 |
| 메인 PC (Ubuntu 24.04 · ROS 2 Jazzy) | mqtt_bridge | ROS 2 ↔ MQTT, 단위 변환(m → mm), NaN → `null`, 명령 ID 중복 · 만료 검사 | 의석 (T27 병후 공동) |
| | scan_manager (+ geometry_estimator · result_store 모듈) | 스캔 순서 상태기계, 중지 · 안전복귀 · 재시작 조정, SetConfig 를 다른 노드에 전파, 5 점 → 직육면체, 로컬 원본 기록 | 병후 (geometry_estimator 현지) |
| | robot_manager | 모션 · 힘/순응 제어와 그 해제, TCP · 힘 샘플 발행, 하강 제한 1차 감시. **두산 · RG2 드라이버를 부르는 유일한 노드** | 학민 |
| | contact_detector | CONTACT · EDGE · OVER_FORCE 판정, tare, 필터 · 디바운스 | 현지 |
| | safety_monitor | 과대 외력 · 하강 제한 2차, 샘플 최신성, 웹 heartbeat → 웹을 거치지 않고 정지 요청, 래치 | 현지 |
| | **weld_manager [phase 2]** | 스캔 결과의 모서리 8 개를 45° 자세 · 스탠드오프 · 위빙 경유점으로 따라간다 | 현지 (구현 PR 진행 중) |
| | 두산 드라이버 · RG2 드라이버 (제공) | `dsr_controller2`(`/dsr01`) · `onrobot_driver`. 수정하지 않는다 | — |
| 로봇 컨트롤러 | M0609 (DRCF) · RG2 · 무센서 탐침 팁 | 하드웨어 안전(비상정지 · 충돌 감지)은 여기에 있다 | — |

## 2. 데이터 흐름 (갈래)

| 갈래 | 흐름 | 이름 (계약) |
|---|---|---|
| 명령 | 브라우저 → FastAPI → MQTT → mqtt_bridge → scan_manager | `cmd/scan/{start,stop,home,resume,set_config}` · `cmd/safety/reset` → `/scan/run` · `/scan/home` · `/scan/resume` (A) · `/scan/stop` · `/scan/set_config` · `/safety/reset` (S) |
| 표시 | 노드 → mqtt_bridge → MQTT → FastAPI → WebSocket → 화면 | `/scan/state` · `/scan/result` · `/scan/log` · `/robot/sample` · `/robot/status` · `/contact/event` · `/safety/status` → `scan/*` · `robot/*` · `contact/event` · `safety/status`. 명령의 접수는 `cmd/ack`, 완료는 `scan/command_result`(접수 ≠ 완료) |
| 모션 | scan_manager → robot_manager → 두산 드라이버 → 컨트롤러 | `/robot/execute_motion` (A, 단위 모션 1 개) · `/robot/stop` (S) · `dsr_msgs2` 서비스 · DRCF TCP/IP |
| 로봇 상태 | robot_manager → contact_detector · safety_monitor · scan_manager · mqtt_bridge | `/robot/sample`(TCP · 힘 + 실행 중 `motion_id` · `operation`) · `/robot/status`(연결 · 동작 · 오류, 정지 완료 확인의 근거) |
| 접촉 판정 | contact_detector → robot_manager(자체 정지) · scan_manager(판정 좌표 기록) | `/contact/event`. 실기 기본인 스텝 모드 SLIDE 의 EDGE 는 robot_manager 가 낸다(계약 v0.1.15) |
| 안전 | safety_monitor → robot_manager (**웹 경유 없음**) | `/robot/stop` (S) · `/safety/status` · `/web/heartbeat` · 래치 해제는 `/safety/reset` 으로만 |
| 저장 | 메인 PC 원본 + 웹 DB | result_store `progress.json` · `result.json`(재시작의 원본) / PostgreSQL(원격 조회용) |
| 관절 표시 | 두산 `joint_state_broadcaster` → mqtt_bridge → 웹 3D | `/dsr01/joint_states` → `robot/joints` · `robot/gripper_joints`. **표시 전용**, 제어 입력으로 쓰지 않는다 |

## 3. 지켜야 할 경계 (`docs/architecture.md`)
- 정지와 접촉 판정은 메인 PC 안에서 끝난다. 웹이 끊겨도 로컬 정지와 원본 보관은 동작한다.
- 작업 중지 · 안전복귀 · 재시작 · 안전 해제는 독립 명령이다. 중지는 홈 복귀나 재시작을 부르지 않는다. 실패해도 자동 홈 복귀는 없다.
- 재시작은 웹 DB 가 아니라 result_store 의 로컬 기록을 쓴다.
- 화면의 중지 버튼은 안전 등급 기능이 아니다. 최종 안전 수단은 티치펜던트 비상정지와 로봇의 충돌 감지다.

## 4. phase 2 (용접) — 더한 것과 구현 상태

계약은 v0.2.0 으로 main 에 있다(`docs/phase2/`, PR #184 · #198). **구현은 아직 main 에 없다**(2026-09-27 기준). 그림에서 주황 점선으로 구분했다.

| 더한 것 | 계약 | 구현 | 상태 (9/27) |
|---|---|---|---|
| `weld_manager` 노드 (6 번째 자체 노드) | `weld-ros-interfaces.md` · `weld-motion.md` | 현지, PR #195 → #196 → #197 | draft. Virtual 8 선 DONE 246 s(sim 가상 박스 100 × 60 × 40 mm, `docs/test-reports/p2-weld-virtual_20260925.md`, #197 브랜치) |
| `/robot/execute_path` (ExecutePath, 경유점 직선 이동) | 5.2절 | 현지, PR #191 | draft. Virtual line 모드 확인, spline 은 응답 지연으로 쓰지 않는다(D31) |
| mqtt_bridge `cmd/weld/*` · `weld/*` 중계 | `weld-mqtt-schema.md` | 의석(P4) | PR 없음 |
| 웹 용접 화면 | 같은 문서 3절 | 의석(P3) | PR 없음 |
| scan_manager 의 스캔 · 용접 배타(601) | 7.1절 | 병후(P5) | PR 없음 |

실기 확인은 2026-09-29 예정이다. 9/23 측정에서 45° 자세로 16 자세 중 12 에 도달했고 L1 · L5 는 도달하지 못했다(PR #186, 머지 전).

## 5. v1.6 → v1.7 에서 바뀐 것

| # | 바뀐 것 | 근거 |
|---|---|---|
| 1 | 웹 PC 를 실제 구성으로: Docker 4 서비스(Mosquitto · PostgreSQL · FastAPI · Spring Boot) + React 는 Docker 밖. 포트 표기 | `docker/docker-compose.yml`, `frontend/vite.config.js` |
| 2 | FastAPI 의 실제 경로(`/commands/*` · `/ws`), Spring 은 조회 API 만 있고 화면과는 아직 연결 없음 | `backend/app/main.py`, `frontend/src/App.jsx` |
| 3 | 스텝 모드 SLIDE 의 EDGE 를 robot_manager 가 발행 | 계약 v0.1.15 (PR #160) |
| 4 | `/dsr01/joint_states` → mqtt_bridge 표시 전용 중계 | 계약 v0.1.19 · v0.1.20 (PR #179) |
| 5 | phase 2: weld_manager · ExecutePath · `/weld/*` · `cmd/weld/*` (구현 PR 진행 중 표시) | 계약 v0.2.0 (PR #184 · #198) |
| 6 | 형식: drawio 대신 matplotlib 스크립트(`figures.py`). phase 2 를 뺀 판을 같은 스크립트로 만든다 | — |

그림 다시 만들기: `python3 docs/deliverables/figures.py` (matplotlib · graphviz · Noto Sans CJK KR 글꼴 필요).
