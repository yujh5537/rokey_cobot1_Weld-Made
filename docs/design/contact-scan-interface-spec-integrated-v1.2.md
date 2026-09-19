# 접촉 스캔 시스템 인터페이스 정의서 — 통합본 v1.2 (ROS 2 계약 + 웹 연동 계약)

> **문서 상태: 초안 · 실기 검증 전 · 수치는 설계 출발값**
> **v1.2 (2026-09-18)**: T01 계약 동결 회의(1차 병후·의석 / 2차 전원) 결정을 반영했다. **구속력 있는 계약은 레포의 `docs/contracts/` v0.1이며, 이 문서와 다르면 계약이 우선한다.** 이 문서는 시나리오 · 설계 배경 · 파라미터 목록 · 근거를 담는 참고 문서다. v1.1 대비 변경 목록은 16장.
> 기준 문서: BRD v3.2.0(`docs/BRD.md`) · `contact-scan-system-architecture-v1.6.drawio` (계약 v0.1 반영. 본문의 "아키텍처 v1.5"는 v1.1 작성 당시의 출처 표시다)
> 통합 출처: `contact-scan-ros2-interface-spec-v1.0.md`(ROS 2 정의서, Part 1) + `Interface_Draft_v0.11.md`(팀원 초안 · 웹 연동, Part 2). 이 통합본이 두 문서를 대체한다.
> 작성일: 2026-09-18 · 짝 문서: `contact-scan-node-diagram-v1.1.md`(노드 구성도) · `contact-scan-node-diagram-v1.1.drawio`(같은 그림) · `contact-scan-node-overview-v1.2.drawio`(간략판)

**읽는 순서**
- **Part 1 (0~10장) — ROS 2 계약**: `contact_scan_interfaces` 패키지와 자체 노드 5개 사이의 Topic · Service · Action · 파라미터 · 공통 정의. 구현 팀(ROS)이 그대로 쓰는 부분.
- **Part 2 (11~14장) — 웹 연동 계약**: 시스템 연결 구조 · 저장 책임 · MQTT 토픽 · Web API 경계 · 공통 규칙. 웹 팀과 ROS 팀이 함께 보는 부분.
- **Part 3 (15장) — 통합 이력**: 팀원 초안 v0.11에서 무엇을 어떻게 바꿨는지.
- 미확정 항목은 **10장** 한 곳에 모아 두었다(#1~#24). 결정된 것은 "결정(날짜)"으로 표시한다. 2026-09-18 현재 결정: #1 · #6 · #16 · #17 · #18. **T01 회의로 나머지 제안(TBD) 항목도 계약 v0.1로 채택되었다**(10장 머리말). 본문의 "제안(TBD)" 표기는 v1.1 당시의 출처 표시로 남겨 둔다.

---

# Part 1 — ROS 2 계약 (contact_scan_interfaces)

---

## 0. 문서 정보

### 0.1 기준 문서와 우선순위

| 순위 | 문서 | 역할 |
|---|---|---|
| 1 | BRD v3.0.0 | 요구사항의 최상위 기준. 절 번호(4.x.x · US-xx · TR-xx · 위험 n · 6장)를 근거로 인용 |
| 2 | 시스템 아키텍처 v1.5 | 노드 5개 · 인터페이스 이름 · 필드 초안(4.7)의 직접 근거. 쪽지 ⑨의 2026-09-18 정합 결정은 되돌리지 않음 |
| 3 | v1.3→v1.4 변경 목록 | 참고용 |

세 문서가 충돌하는 곳은 임의로 고르지 않고 10장(확인 요청)에 올렸다.

### 0.2 표기 규칙 (세 가지를 섞지 않음)

| 표기 | 뜻 | 예 |
|---|---|---|
| **확정** | BRD v3.0.0에 명시된 사항 | 노드 5개, 접수 ≠ 정지 완료, 미측정값 0 금지 |
| **초안** | 아키텍처 v1.5(4.7 초안)에 명시된 이름·타입·필드. 그대로 옮김 | `/robot/sample`, `RobotSample.pose_stamp` |
| **제안(TBD)** | 이 문서에서 채운 자료형·단위·추가 필드·enum 값·QoS. 확인 전까지 계약이 아님 | `ContactEvent.detect_stamp`, QoS depth |

- 수치(3~5 N · 0.5 mm · 연속 3회 · 30 N · 5 mm · tare 1~2 s · 50 Hz · 10 Hz · 1 Hz · 120 s · 1 s · 팁 반지름 3 mm · 판정 지연 40 ms)는 **모두 설계 출발값**이며 실측 후 조정한다(BRD 12장 "수치의 성격").
- 제공 드라이버(두산 `dsr_msgs2`, OnRobot `/onrobot/sendCommand`)와 MQTT 토픽은 **정의하지 않고** 8장에 이름·방향만 적는다. 실제 이름·타입은 **[E19] 실PC 확인 필요**.
- 검토안(MVP 밖: `/scan/calibrate` · `/calibration/result`)은 9장에만 적고 MVP 목록(2~5장)에 넣지 않는다.

### 0.3 패키지 · 단위 · 프레임 규칙

| 항목 | 규칙 | 표기 |
|---|---|---|
| 정의 패키지 | `contact_scan_interfaces` (msg · srv · action 전용, 실행 노드 아님) | 확정 (BRD 4.7) |
| 실행 패키지 | **노드별 패키지**(`scan_manager` · `robot_manager` · `contact_detector` · `safety_monitor` · `mqtt_bridge` + `contact_scan_bringup`), 실행 파일명 = 노드명, 네임스페이스 없음(루트) | T01 확정(v1.1의 단일 `contact_scan` 제안을 레포 구조에 맞춰 정정) |
| 길이 · 각도 | ROS 내부 **m · rad**. 웹 표시는 mm(변환은 mqtt_bridge 또는 FastAPI) | 확정 방향 (BRD 4.7 데이터 계약 "제안") |
| 힘 · 토크 | **N · N·m** | 확정 방향 (BRD 4.7) |
| 시각 | `builtin_interfaces/Time`, ROS 시간(메인 PC 시계). 통합 샘플이라도 취득 시각을 각각 보존 | 확정 (BRD 4.1.6) |
| 프레임 | `base_link`(로봇 베이스, 가칭) · `workpiece_fixture`(작업대 좌표, 가칭). 환경 세팅 후 확정. 드라이버 posx(mm · deg) ↔ m · rad 변환은 robot_manager 단일 창구 | 확정 (BRD 6장 · 4.7) / 프레임 배정은 제안(TBD) #10 |
| 미측정값 | **0으로 넣지 않는다.** float는 `NaN` + 필드별 `*_valid=false`. 수신 측은 `*_valid`로만 판단. MQTT는 `null`, Python은 `None` (TR-10 · T01) | 확정 |

---

## 1. 입출력 정의 (시나리오별 흐름)

표기: `[웹]` = 브라우저→FastAPI→MQTT(범위 밖) · `T` Topic · `S` Service · `A` Action. 화살표 아래 줄은 그 단계를 수행하는 노드.

### 1.1 작업 시작 (US-01 · 4.1.3 · 4.1.5 · 4.2.1)

```
[웹] cmd/scan/start {request_id}
  ↓ mqtt_bridge
/scan/run (A · Goal {request_id})                       → cmd/ack(접수/거절)는 goal 수락/거절로 매핑
  ↓ scan_manager   ① 시작 조건: /robot/status(T) connected · /safety/status(T) latched=false · 동시 작업 없음
                    scan_id 발급 → /scan/state(T) phase=PREPARING
/contact/tare (S)  → success, offset(F₀), error         무접촉·정지 상태 1~2 s 평균 · 툴 등록 이상이면 실패
  ↓ scan_manager   motion_id 발급
/robot/execute_motion (A · MOVE_TO 기준점 상공) → Result {pose, reason=TARGET_REACHED}
/robot/execute_motion (A · DESCEND)             → /scan/state phase=TOP_SEARCH
  ↓ (1.2로 이어짐)
```

### 1.2 접촉 판정 — DESCEND (4.1.1 · 4.1.4 · 4.2.1)

```
robot_manager  /robot/sample (T · 50 Hz 목표) ──▶ contact_detector
(v1.2) 판정 모드 · motion_id 는 /scan/state 가 아니라 **샘플의 operation=DESCEND · motion_id** 에서 얻는다 (robot_manager 가 직접 찍음)
scan_manager   /scan/state   (T · scan_id) ──▶ contact_detector (scan_id 태깅용)
contact_detector  |F − F₀| > 3~5 N 연속 3회
  ↓ /contact/event (T · type=CONTACT, motion_id, sample_id, pose, stamps)  — 즉시
  ├─▶ robot_manager : goal의 motion_id와 대조(+ 현재 goal이 DESCEND) → move_stop → Result {정지 pose, reason=CONTACT}
  ├─▶ scan_manager  : 판정 샘플 pose로 z_top 기록 (정지 pose와 구분) → /scan/state, /scan/log
  └─▶ mqtt_bridge   : contact/event(MQTT) 표시
정지 완료 확인: robot_manager /robot/status (T) moving=false
```

### 1.3 엣지 판정 — SLIDE (4.1.2 · 4.2.2 · 4.2.6 · 4.5.4)

```
(v1.2 방향 전환 절차 — 재하강 없이 MOVE_TO 연속. 이 구간은 접촉 판정 안 함)
scan_manager  /robot/execute_motion (A · MOVE_TO ① 위로 lift_height_m(0.05) 올림)
scan_manager  /robot/execute_motion (A · MOVE_TO ② 기준 원점 상공으로 수평 이동)
scan_manager  /robot/execute_motion (A · MOVE_TO ③ 첫 접촉 z + recontact_margin_m(0.001) 까지 저속 내림)
scan_manager  /robot/execute_motion (A · SLIDE, direction=POS_X, speed, max_distance, timeout)
  robot_manager: task_compliance_ctrl + set_desired_force(−z 목표 힘 = ROS 파라미터) + amovel · 하강량 제한 5 mm
scan_manager  /scan/state (T · phase=EDGE_SEARCH, direction=POS_X, progress=0/4, motion_id)
contact_detector  z 급강하 ≥ 0.5 mm(주) + 외력 감소(보조) 연속 3회
  ↓ /contact/event (T · type=EDGE)
  ├─▶ robot_manager : motion_id 대조 → 정지 → 순응·힘 제어 해제(finally) → Result {정지 pose, reason=EDGE}
  ├─▶ scan_manager  : 판정 샘플 pose 기록(x⁺) → progress=1/4 → 다음 방향(−x · +y · −y) 반복
  └─▶ mqtt_bridge
max_distance 안에 EDGE 없음 → Result reason=MAX_DISTANCE → scan_manager 실패 처리(1.7과 같음)
4/4 완료 → (v1.2 마무리 순서)
  GEOMETRY : geometry_estimator(편향 보정 · 사각형 · 경로 후보 4 · 직육면체) → result_store 저장 → /scan/result (T) 즉시 발행
  HOMING   : 팁 들어 올림(MOVE_TO) → HOME  — 정상 완료일 때만. 실패 · 중단 · 형상 실패 시 자동 복귀 없음
  DONE     : RunScan Result 반환 → mqtt_bridge scan/command_result
  → mqtt_bridge: scan/result(MQTT) — Action Result와 중복 반영 방지(scan_id)
  마무리 복귀 실패: 측정 결과는 유효 그대로, phase=ERROR, RunScan.Result.success=false
```

### 1.4 작업 중지 — 정지 경로 ① 웹 요청 (US-04 · 4.5.1)

```
[웹] cmd/scan/stop {request_id, reason}
  ↓ mqtt_bridge
/scan/stop (S · {request_id, reason}) → accepted            ← 접수일 뿐, 정지 완료 아님
  ↓ scan_manager   진행 중 ExecuteMotion goal cancel(제안) +
/robot/stop (S · {request_id, reason=STOP_REQUESTED}) → accepted
  ↓ robot_manager  move_stop → 순응·힘 제어 해제(finally)
/robot/status (T · moving=false)  ──▶ scan_manager : 정지 **완료** 확인 → /scan/state phase=STOPPED
                                    중단 위치 = ExecuteMotion Result.pose · 확정 측정값 보존(result_store)
                                    홈 복귀 · 재시작 자동 실행 없음
  ↓ mqtt_bridge  scan/state · scan/command_result(MQTT)
```

### 1.5 안전복귀 (US-11 · 4.4.9)

```
[웹] cmd/scan/home {request_id}
  ↓ mqtt_bridge
/scan/home (A · Goal {request_id})
  ↓ scan_manager   phase=HOMING · 측정값·로그 보존
/robot/execute_motion (A · HOME)  → robot_manager: 홈위치(시작위치, 파라미터 home_pose)로 이동
  ↓ Result {pose, reason=TARGET_REACHED}
ReturnHome Result {success} → mqtt_bridge: scan/command_result(MQTT)
```

### 1.6 재시작 (US-12 · 4.4.8 · TR-08)

```
[웹] cmd/scan/resume {request_id, scan_id}
  ↓ mqtt_bridge
/scan/resume (A · Goal {request_id, scan_id})
  ↓ scan_manager   result_store 진행 기록 확인 → /safety/status latched=false 확인 →
                    기존 측정값 유지 · phase=RESUMING → 중단 방향부터 1.3 계속 (재접근 절차 TBD)
                    새 작업(RunScan)과 구분 · scan_id 유지
```

### 1.7 안전 이상 정지 — 정지 경로 ③ (4.5.3 · TR-07)

```
robot_manager  /robot/sample · /robot/status (T) ──▶ safety_monitor
scan_manager   /scan/state (T) ──▶ safety_monitor (단계별 한계)
mqtt_bridge    /web/heartbeat (T · hb/web 실수신 시에만) ──▶ safety_monitor
safety_monitor  과대 외력 30 N · 속도 · 하강/작업영역 · 샘플 stale · 로봇 연결 · HB 만료 중 하나라도 참
  ↓ /robot/stop (S · reason=4xx)  — 즉시 · 로컬 · 웹 경유 없음
  ↓ /safety/status (T · level=STOP, reason_code, stop_required=true, latched=true) — 변경 시
  ├─▶ scan_manager : 작업 중단 처리(1.4의 정지 확인과 동일) · latched면 재시작 거절
  └─▶ mqtt_bridge  : safety/status(MQTT)
정지 완료 확인: /robot/status moving=false (safety_monitor · scan_manager 모두)
```

### 1.8 설정 등록 (US-05)

```
[웹] cmd/scan/set_config {request_id, config}
  ↓ mqtt_bridge
/scan/set_config (S · {request_id, config: ScanConfig}) → {success, reason_code, applied}
  ↓ scan_manager   동작 중(phase ∉ {IDLE, DONE, ERROR, STOPPED})이면 거절 · 자체 값 갱신 ·
                    robot_manager / contact_detector / safety_monitor(v1.2 · P03) 파라미터 갱신(표준 rcl_interfaces/srv/SetParameters · 결정 #16)
```

### 1.9 과대 외력 — 정지 경로 ② 접촉 판정 (4.5.3 · 위험 4)

```
contact_detector  |F| > 30 N (모든 모드)
  ↓ /contact/event (T · type=OVER_FORCE)
  ├─▶ robot_manager : 현재 goal과 대조 없이 **우선** 정지 → Result {pose, reason=OVER_FORCE}
  ├─▶ scan_manager  : 실패 처리 · 원인·위치·단계 기록
  └─▶ mqtt_bridge
(safety_monitor도 같은 조건을 독립 감시해 /robot/stop + 래치 — **이중 경로 유지, 결정 #17**: 1차 = contact_detector 즉시 정지, 2차 = safety_monitor 래치)
```

### 1.10 안전 래치 해제 (결정 #6 · 4.5.3 · 6장)

```
[웹] cmd/safety/reset {request_id}                          ← 관제자가 원인 확인 후 "안전 해제" 버튼
  ↓ mqtt_bridge
/safety/reset (S · {request_id, detail}) → {success, reason_code}
  ↓ safety_monitor   이상 조건이 아직 참이면 거절(CONDITION_ACTIVE) · 해소됐으면 latched=false
/safety/status (T · level=OK, latched=false) ──▶ scan_manager(시작·재시작 허용) · mqtt_bridge(표시)
래치 해제는 로봇을 움직이지 않는다. 이후 안전복귀·재시작은 별도 명령.
```

---
## 2. 인터페이스 정의 (전체 목록)

모두 `contact_scan_interfaces` 패키지. 이름·타입·방향의 표기는 **초안**(아키텍처 4.7), 이 표의 존재 자체는 BRD 4.7 표에 대응하므로 **확정**이다. 검토안은 9장.

### 2.1 Topic (msg)

| # | 이름 | 타입 | 발행 | 구독 | 의미 | 절 |
|---|---|---|---|---|---|---|
| T1 | `/robot/sample` | `msg/RobotSample` | robot_manager | contact_detector · safety_monitor · mqtt_bridge | TCP pose + 외력 통합 샘플(각 취득 시각 별도). 50 Hz 설계 목표 | 3.1 |
| T2 | `/robot/status` | `msg/RobotStatus` | robot_manager | scan_manager · safety_monitor · mqtt_bridge | 연결·동작·오류. **정지 완료 확인의 근거** | 3.2 |
| T3 | `/contact/event` | `msg/ContactEvent` | contact_detector | robot_manager · scan_manager · mqtt_bridge | CONTACT · EDGE · OVER_FORCE 판정 이벤트(즉시) | 3.3 |
| T4 | `/scan/state` | `msg/ScanState` | scan_manager | contact_detector · safety_monitor · mqtt_bridge | 단계·방향·진행 n/4·motion_id | 3.4 |
| T5 | `/scan/result` | `msg/ScanResult` | scan_manager | mqtt_bridge | 최종 형상 결과(유효 플래그 포함) | 3.5 |
| T6 | `/scan/log` | `msg/ScanLog` | scan_manager | mqtt_bridge | 시간순 로그(단계·좌표·오류·시각) | 3.6 |
| T7 | `/safety/status` | `msg/SafetyStatus` | safety_monitor | scan_manager · mqtt_bridge | 안전 상태(변경 시) · 래치 | 3.7 |
| T8 | `/web/heartbeat` | `msg/WebHeartbeat` | mqtt_bridge | safety_monitor | hb/web 실수신 시에만 전달(점선) | 3.8 |

### 2.2 Service (srv)

| # | 이름 | 타입 | 서버 | 클라이언트 | 의미 | 절 |
|---|---|---|---|---|---|---|
| S1 | `/robot/stop` | `srv/StopRobot` | robot_manager | scan_manager · safety_monitor | 로봇 정지 요청. accepted = 접수, 완료는 T2 | 4.1 |
| S2 | `/contact/tare` | `srv/TareForce` | contact_detector | scan_manager | 외력 기준값 F₀ 설정(무접촉·정지 1~2 s) | 4.2 |
| S3 | `/scan/stop` | `srv/StopScan` | scan_manager | mqtt_bridge | 작업 중지 요청. accepted = 접수 | 4.3 |
| S4 | `/scan/set_config` | `srv/SetConfig` | scan_manager | mqtt_bridge | 설정 등록. 동작 중 거절 | 4.4 |
| S5 | `/safety/reset` | `srv/ResetSafety` | safety_monitor | mqtt_bridge | 안전 래치 해제(조건 해소 시만). **결정 #6(2026-09-18) 신설** | 4.5 |

### 2.3 Action (action)

| # | 이름 | 타입 | 서버 | 클라이언트 | 의미 | 절 |
|---|---|---|---|---|---|---|
| A1 | `/scan/run` | `action/RunScan` | scan_manager | mqtt_bridge | 새 작업 시작(동시 작업 제한) | 5.1 |
| A2 | `/scan/home` | `action/ReturnHome` | scan_manager | mqtt_bridge | 안전복귀 = 홈위치(시작위치). 측정값·로그 보존 | 5.2 |
| A3 | `/scan/resume` | `action/Resume` | scan_manager | mqtt_bridge | 재시작(기존 측정값 유지 · 중단 방향부터). **별도 Action 유지(결정 #1)** | 5.3 |
| A4 | `/robot/execute_motion` | `action/ExecuteMotion` | robot_manager | scan_manager | MOVE_TO · DESCEND · SLIDE · HOME 단위 모션. Result = 정지 시점 pose + 종료 사유 | 5.4 |

### 2.4 하위 메시지 (다른 메시지 안에서만 사용 · 토픽 없음) — 결정 #18(2026-09-18): 신설 확정, 이름·필드는 아래

| 타입 | 사용처 | 의미 |
|---|---|---|
| `msg/ScanConfig` | `SetConfig.Request.config` · `SetConfig.Response.applied` · `ScanResult.config` · `RunScan.Goal.config_override` | 웹에서 바꾸는 설정 묶음 + 결과의 설정 스냅샷 |
| `msg/Segment` | `ScanResult.edges[12]` · `ScanResult.path_candidates[4]` | 선분(시작·끝·길이·유효) |
| `msg/ReasonCode` | 모든 `reason` · `error` · `reason_code` · `code` 필드 | 상수 전용(필드 없음) · 공통 코드표(7.2) |

### 2.5 ROS 파라미터 (노드별 · 6장)

| 노드 | 파라미터(이름만) |
|---|---|
| robot_manager | `slide_target_force_n` · `drop_limit_m` · `sample_rate_hz` · `home_pose` · `frame_id` · `dsr_namespace` · `dsr_model` · `mode` · `rg2_grip_width_m` · `rg2_grip_force_n` |
| contact_detector | `source` · `contact_threshold_n` · `edge_drop_m` · `debounce_n` · `over_force_n` · `tare_duration_s` · `tare_max_force_n` · `filter_window` · `stale_age_ms` · `sim_box_size_m` · `sim_box_origin_m` |
| safety_monitor | `over_force_n` · `drop_limit_m`(v1.2) · `max_speed_mps` · `workspace_min_m` · `workspace_max_m` · `max_descend_m` · `sample_stale_ms` · `robot_status_timeout_ms` · `hb_timeout_s` · `latch_levels` |
| scan_manager | `descend_speed_mps` · `slide_speed_mps` · `max_descend_m` · `max_slide_m` · `motion_timeout_s` · `lift_height_m` · `recontact_margin_m`(v1.2) · `tip_radius_m` · `detect_latency_s` · `result_frame_id` · `result_dir` · `allow_concurrent` |
| mqtt_bridge | `broker_host` · `broker_port` · `client_id` · `topic_map_file` · `downsample_hz` · `hb_ros_hz` · `qos_default` |

### 2.6 외부(범위 밖 · 정의하지 않음 · 8장)

두산 `dsr_msgs2` 서비스(robot_manager → dsr_controller2) · `/onrobot/sendCommand`(robot_manager → onrobot_driver) · MQTT 토픽(mqtt_bridge ↔ Broker) · `rcl_interfaces/srv/SetParameters`(scan_manager → robot_manager · contact_detector · safety_monitor(v1.2), 결정 #16).

---

## 3. Topic

공통: 모든 Topic은 `contact_scan_interfaces/msg/*`. QoS는 7.6의 프로파일 이름으로 표기하며 **전부 제안(TBD) #9**. "단위" 열의 `—`는 단위 없음.

### 3.1 `/robot/sample` — `contact_scan_interfaces/msg/RobotSample`

| 항목 | 내용 |
|---|---|
| 종류 · 방향 | Topic · 발행 robot_manager → 구독 contact_detector · safety_monitor · mqtt_bridge |
| 의미 | TCP pose와 외력 추정(wrench)을 한 샘플로 묶은 것. **같은 메시지라도 동시 취득으로 간주하지 않고** 각 취득 시각을 보존 |
| 발행 조건 | 주기. 50 Hz 설계 목표(파라미터 `sample_rate_hz`). 실측 주기는 위험 1 시험(TR-01)으로 확인 |
| QoS 제안 | `SENSOR`: BEST_EFFORT · VOLATILE · KEEP_LAST 5 |
| 관련 | BRD 4.1.6 · 4.2.1 · 위험 1 · 위험 10 · TR-09 |

| 필드 | 자료형 | 단위 | 설명 | 표기 | 근거 |
|---|---|---|---|---|---|
| `sample_id` | `uint64` | — | robot_manager 발급, 프로세스 내 단조 증가. 0 = 미발급(7.3) | 초안(이름) / 제안(자료형) | 아키텍처 ⑨ · 4.1.6 |
| `frame_id` | `string` | — | pose의 기준 프레임. 출발값 `base_link`(가칭) | 초안 / 제안(값) | 4.1.6 · 6장 |
| `pose` | `geometry_msgs/Pose` | m · rad(quaternion) | TCP pose. 드라이버 posx(mm·deg)에서 robot_manager가 변환 | 초안 / 제안(자료형) | 4.1.6 · 4.7 데이터 계약 |
| `pose_stamp` | `builtin_interfaces/Time` | — | pose 취득 시각(get_current_posx 응답 시각) | 초안 | 4.1.6 |
| `wrench` | `geometry_msgs/Wrench` | N · N·m | 외력 추정(get_tool_force). 성분값 보존(방향 판정용) | 초안 / 제안(자료형) | 1.4 B 구현 계획 |
| `force_stamp` | `builtin_interfaces/Time` | — | wrench 취득 시각 | 초안 | 4.1.6 |
| `valid` | `bool` | — | 두 값 모두 정상 취득이면 true. false면 판정·감시에 쓰지 않음 | 초안 | 4.1.6 · 위험 10 |
| `motion_id` | `uint32` | — | **(v1.2)** robot_manager가 실행 중인 goal의 motion_id. 없으면 0 | T01 | 4.2.2 |
| `operation` | `uint8` | — | **(v1.2)** 실행 중인 goal의 종류 `OP_*`(5.4와 같은 값). 없으면 `OP_NONE` | T01 | 4.2.2 |

```
# contact_scan_interfaces/msg/RobotSample.msg
# TCP pose + 외력 통합 샘플. 각 취득 시각을 별도 보존한다 (BRD 4.1.6).
uint8 OP_NONE=0                     # (v1.2) ExecuteMotion.OP_* 와 같은 값
uint8 OP_MOVE_TO=1
uint8 OP_DESCEND=2
uint8 OP_SLIDE=3
uint8 OP_HOME=4

uint64 sample_id                    # robot_manager 발급 (7.3)
string frame_id                     # 'base_link' (가칭, 6장)
geometry_msgs/Pose pose             # m, rad
builtin_interfaces/Time pose_stamp
geometry_msgs/Wrench wrench         # N, N·m. get_tool_force(ref=DR_BASE)
builtin_interfaces/Time force_stamp
bool valid
uint32 motion_id                    # (v1.2) 실행 중인 goal. 없으면 0
uint8 operation                     # (v1.2) 실행 중인 goal 의 종류
```

규칙 메모: 구독자는 `valid=false`이거나 `now − max(pose_stamp, force_stamp) > stale_age_ms`(제안 100 ms, #12)이면 샘플을 버린다. scan_manager는 이 토픽을 구독하지 않는다(정합 #6). **(v1.2)** `motion_id` · `operation`은 robot_manager가 goal 수락부터 Result 반환까지 직접 찍는다. 이유: `EDGE_SEARCH` 단계 안에 SLIDE와 복귀 이동이 섞여 있어 phase로는 판정을 끌 수 없고, `/scan/state` 경유 태깅은 goal 직후 이벤트가 불일치로 무시될 수 있다.

### 3.2 `/robot/status` — `contact_scan_interfaces/msg/RobotStatus`

| 항목 | 내용 |
|---|---|
| 종류 · 방향 | Topic · 발행 robot_manager → 구독 scan_manager · safety_monitor · mqtt_bridge |
| 의미 | 드라이버 연결 · 동작 중 · 오류. 세 정지 경로 모두 **정지 완료는 이 토픽으로 확인** |
| 발행 조건 | 변경 시 즉시 + 주기(제안 10 Hz, 최신성 감시용) |
| QoS 제안 | `STATE`: RELIABLE · TRANSIENT_LOCAL · KEEP_LAST 1 |
| 관련 | BRD 4.5.1 · 4.2.3 · 4.5.2 · TR-07 |

| 필드 | 자료형 | 단위 | 설명 | 표기 | 근거 |
|---|---|---|---|---|---|
| `stamp` | `builtin_interfaces/Time` | — | 상태 판정 시각 | 제안(TBD) | 위험 10(최신성) |
| `connected` | `bool` | — | dsr_controller2 서비스 응답 가능 | 초안 | 4.5.1 |
| `moving` | `bool` | — | 로봇 동작 중. **정지 완료 = `connected && !moving`** | 초안 / 판정식 제안 #7 | 4.5.1 |
| `error` | `bool` | — | 드라이버/로봇 오류 상태 | 초안 / 자료형 제안 #7 | 4.5.1 |
| `error_code` | `uint16` | — | 7.2 공통 코드(0 = 없음) | 제안(TBD) #7 | 4.2.5 |
| `compliance_active` | `bool` | — | 순응 제어(task_compliance_ctrl)가 켜져 있음. 모든 종료 경로에서 false가 되어야 함 | 제안(TBD) | 4.5.2 · TR-07 |
| `force_ctrl_active` | `bool` | — | **(v1.2)** 힘 제어(set_desired_force)가 켜져 있음. 모든 종료 경로에서 false | T01 | 4.5.2 |
| `motion_id` · `operation` | `uint32` · `uint8` | — | **(v1.2)** 실행 중인 goal(RobotSample과 같은 의미) | T01 | 4.2.2 |
| `detail` | `string` | — | 사람이 읽는 부가 설명(드라이버 원문 등) | 제안(TBD) | — |

```
# contact_scan_interfaces/msg/RobotStatus.msg
builtin_interfaces/Time stamp
bool connected
bool moving                 # 정지 완료 = connected && !moving
bool error
uint16 error_code           # 7.2 공통 코드, 0 = 없음
bool compliance_active      # 순응 제어 활성 (4.5.2 확인용)
bool force_ctrl_active      # (v1.2) 힘 제어 활성
uint32 motion_id            # (v1.2) 실행 중인 goal. 없으면 0
uint8 operation             # (v1.2) RobotSample.OP_*
string detail
```

규칙 메모: `accepted`(S1·S3)는 접수이며, 정지 완료는 `moving=false`를 이 토픽에서 확인한다. `moving`의 근거(드라이버 상태 필드 vs 속도 0)는 [E19] 확인 후 확정.

### 3.3 `/contact/event` — `contact_scan_interfaces/msg/ContactEvent`

| 항목 | 내용 |
|---|---|
| 종류 · 방향 | Topic · 발행 contact_detector → 구독 robot_manager · scan_manager · mqtt_bridge |
| 의미 | 접촉(CONTACT) · 접촉 소실(EDGE) · 과대 외력(OVER_FORCE) 판정. **판정에 쓴 샘플의 좌표·시각**을 실음(정지 완료 좌표와 다름) |
| 발행 조건 | 판정 확정 즉시(주기 대기 없음). 디바운스 연속 N=3회 충족 시 1회 |
| QoS 제안 | `EVENT`: RELIABLE · VOLATILE · KEEP_LAST 50 |
| 관련 | BRD 4.1.1 · 4.1.2 · 4.1.4 · 4.2.1 · 4.2.2 · 4.5.3 · 위험 10 · TR-09 |

| 필드 | 자료형 | 단위 | 설명 | 표기 | 근거 |
|---|---|---|---|---|---|
| `event_id` | `uint64` | — | contact_detector 발급, 단조 증가(7.3) | 초안 / 제안(자료형·발급 주체) | 위험 10 · TR-10 중복 방지 |
| `scan_id` | `string` | — | `/scan/state`에서 받은 현재 scan_id(없으면 빈 문자열) | 초안 | 정합 #2 |
| `motion_id` | `uint32` | — | **(v1.2)** 판정에 쓴 `RobotSample.motion_id`를 그대로 복사. robot_manager가 goal 값과 대조 | 초안 / T01 | 4.2.2 · 정합 #2 |
| `sample_id` | `uint64` | — | 판정에 쓴 `RobotSample.sample_id` | 초안 | 4.1.6 |
| `type` | `uint8` | — | `TYPE_CONTACT=0` · `TYPE_EDGE=1` · `TYPE_OVER_FORCE=2` (7.1) | 초안(값) / 제안(상수) | 4.1 · 4.5.3 |
| `frame_id` | `string` | — | pose 프레임(RobotSample과 동일) | 제안(TBD) | 4.1.6 "좌표계 보존" |
| `pose` | `geometry_msgs/Pose` | m · rad | 판정 샘플의 TCP pose | 초안 | 4.2.1 · 4.2.2 |
| `wrench` | `geometry_msgs/Wrench` | N · N·m | 판정 샘플의 외력 | 초안 | 4.1.1 |
| `pose_stamp` | `builtin_interfaces/Time` | — | 판정 샘플의 pose 취득 시각 | 초안(`stamps`) / 분리 제안 #8 | 4.1.6 |
| `force_stamp` | `builtin_interfaces/Time` | — | 판정 샘플의 힘 취득 시각 | 초안(`stamps`) / 분리 제안 #8 | 4.1.6 |
| `detect_stamp` | `builtin_interfaces/Time` | — | contact_detector가 판정을 확정한 시각(지연 실측용) | 제안(TBD) #8 | TR-01 판정 지연 · 4.2.4 |
| `force_delta_n` | `float64` | N | `|F − F₀|` (CONTACT/EDGE 보조 신호 값). OVER_FORCE는 `|F|` | 제안(TBD) | 4.1.1 · 4.1.2 |
| `z_drop_m` | `float64` | m | EDGE 판정의 실제 z 하강량. **(v1.2)** 다른 type은 `NaN` + `z_drop_valid=false`. 편향 보정의 δ로 사용 | T01 | 4.1.2 |
| `z_drop_valid` | `bool` | — | `z_drop_m` 유효 여부 | 제안(TBD) | TR-10 |
| `source` | `string` | — | **(v1.2)** 입력원 `robot_force` \| `sim` | T01 | 4.1.6 |
| `debounce_count` | `uint8` | — | **(v1.2)** 판정을 확정한 연속 횟수 | T01 | 4.1.4 |

```
# contact_scan_interfaces/msg/ContactEvent.msg
uint8 TYPE_CONTACT=0
uint8 TYPE_EDGE=1
uint8 TYPE_OVER_FORCE=2

uint64 event_id
string scan_id
uint32 motion_id                    # (v1.2) 판정 샘플의 motion_id 복사
uint64 sample_id
uint8 type
string source                       # (v1.2) 'robot_force' | 'sim'
string frame_id
geometry_msgs/Pose pose             # 판정 샘플 좌표 (≠ 정지 완료 좌표)
geometry_msgs/Wrench wrench
builtin_interfaces/Time pose_stamp
builtin_interfaces/Time force_stamp
builtin_interfaces/Time detect_stamp
float64 force_delta_n
float64 z_drop_m                    # EDGE 외에는 NaN (v1.2)
bool z_drop_valid
uint8 debounce_count                # (v1.2)
```

규칙 메모: robot_manager는 `motion_id`가 0이거나 현재 goal과 다르면, **또는 현재 goal이 `OP_DESCEND`/`OP_SLIDE`가 아니면(v1.2)** CONTACT/EDGE를 무시하고 로그만 남긴다. `OVER_FORCE`는 대조 없이 우선 정지한다(4.5.3). 판정 좌표(이 메시지)와 정지 완료 좌표(`ExecuteMotion.Result.pose`)를 혼동하지 않는다.

### 3.4 `/scan/state` — `contact_scan_interfaces/msg/ScanState`

| 항목 | 내용 |
|---|---|
| 종류 · 방향 | Topic · 발행 scan_manager → 구독 contact_detector · safety_monitor · mqtt_bridge |
| 의미 | 상태기계의 현재 단계·방향·진행 n/4·motion_id. contact_detector는 판정 모드(하강/밀기/대기)와 이벤트 태깅에, safety_monitor는 단계별 한계에 사용 |
| 발행 조건 | 변경 시 즉시 + 주기(제안 2 Hz, 표시·최신성용) |
| QoS 제안 | `STATE`: RELIABLE · TRANSIENT_LOCAL · KEEP_LAST 1 |
| 관련 | BRD 4.4.4 · 4.4.7 · 4.2.2 · 정합 #1·#2 |

| 필드 | 자료형 | 단위 | 설명 | 표기 | 근거 |
|---|---|---|---|---|---|
| `stamp` | `builtin_interfaces/Time` | — | 상태 변경 시각 | 제안(TBD) | 4.4.3 |
| `scan_id` | `string` | — | 현재 작업. IDLE이면 빈 문자열 | 초안 | 정합 #1 |
| `phase` | `uint8` | — | 7.1 `PHASE_*` (대기·준비·윗면 탐색·모서리 탐색·형상 생성·완료·오류·중지 중·중지됨·홈 복귀·재시작) | 초안(이름) / 제안(값) | 4.4.4 |
| `direction` | `uint8` | — | 7.1 `DIR_*` (NONE · POS_X · NEG_X · POS_Y · NEG_Y). 모서리 탐색 중에만 유효 | 초안 / 제안(값) | 4.2.2 |
| `progress` | `uint8` | — | 확보한 모서리 수 n (0~4). 표시는 "n/4" | 초안 | 4.4.4 |
| `progress_total` | `uint8` | — | 4 (MVP 고정. MVP 이후 변당 2점 대비) | 제안(TBD) | 2장 MVP 이후 |
| `motion_id` | `uint32` | — | 진행 중 ExecuteMotion goal의 motion_id. 없으면 0 | 초안 | 정합 #2 |

```
# contact_scan_interfaces/msg/ScanState.msg
# phase (BRD 4.4.4 + 중단·홈 복귀·재시작 진행 상태)
uint8 PHASE_IDLE=0          # 대기
uint8 PHASE_PREPARING=1     # 시작 조건 점검 · tare
uint8 PHASE_TOP_SEARCH=2    # 윗면 탐색 (DESCEND)
uint8 PHASE_EDGE_SEARCH=3   # 모서리 탐색 n/4 (SLIDE)
uint8 PHASE_GEOMETRY=4      # 형상 생성
uint8 PHASE_DONE=5          # 완료
uint8 PHASE_ERROR=6         # 오류 (실패 · 안전 이상)
uint8 PHASE_STOPPING=7      # 중지 요청 접수 · 정지 완료 대기
uint8 PHASE_STOPPED=8       # 중단됨 (재시작 가능)
uint8 PHASE_HOMING=9        # 홈 복귀 진행 (안전복귀 · 스캔 마무리 공용, v1.2)
uint8 PHASE_RESUMING=10     # 재시작 진행 (재접근)
# direction
uint8 DIR_NONE=0
uint8 DIR_POS_X=1
uint8 DIR_NEG_X=2
uint8 DIR_POS_Y=3
uint8 DIR_NEG_Y=4

builtin_interfaces/Time stamp
string scan_id
uint8 phase
uint8 direction
uint8 progress              # n (0~4)
uint8 progress_total        # 4
uint32 motion_id            # 0 = 없음
```

규칙 메모: **(v1.2)** contact_detector의 판정 모드는 phase가 아니라 **샘플의 `operation`** 에서 얻는다 — `OP_DESCEND`→CONTACT만 · `OP_SLIDE`→EDGE만 · 그 외→판정 안 함. OVER_FORCE는 모든 모드에서 원시 외력으로 판정. `/scan/state`는 scan_id 태깅에만 쓴다. `PHASE_HOMING`은 안전복귀와 스캔 정상 완료 뒤의 마무리 복귀에 함께 쓴다.

### 3.5 `/scan/result` — `contact_scan_interfaces/msg/ScanResult`

| 항목 | 내용 |
|---|---|
| 종류 · 방향 | Topic · 발행 scan_manager → 구독 mqtt_bridge |
| 의미 | 최종 형상 결과. 실패 시에도 발행(확보한 값만 valid). RunScan/Resume Result에도 같은 내용이 실리므로 mqtt_bridge는 `scan_id`로 중복 반영 방지 |
| 발행 조건 | 작업 종료 시 1회(완료 · 실패 · 중단) |
| QoS 제안 | `STATE`: RELIABLE · TRANSIENT_LOCAL · KEEP_LAST 1 |
| 관련 | BRD 4.3.1~4.3.5 · 4.4.7 · TR-10 · 정합 #7 |

| 필드 | 자료형 | 단위 | 설명 | 표기 | 근거 |
|---|---|---|---|---|---|
| `scan_id` | `string` | — | 작업 식별자 | 초안 | 4.4.7 |
| `stamp` | `builtin_interfaces/Time` | — | 결과 생성 시각 | 제안(TBD) | 4.4.3 |
| `success` | `bool` | — | 성공·실패 | 초안 | 4.3.5 |
| `reason_code` | `uint16` | — | 실패 사유(7.2). 성공 = 0 | 제안(TBD) #5 | 4.2.5 |
| `detail` | `string` | — | 사유 설명 | 제안(TBD) | — |
| `frame_id` | `string` | — | 아래 좌표의 기준 프레임. 출발값 `workpiece_fixture`(가칭) | 제안(TBD) #10 | 4.4.7 · 4.7 "좌표 기준" |
| `z_top` · `z_top_valid` | `float64` · `bool` | m | 윗면 높이(편향 보정 후) · 유효 | 초안(유효 항목) / 제안(형식) #13 | 4.2.1 · TR-10 |
| `x_pos` · `x_pos_valid` | `float64` · `bool` | m | +x 모서리 좌표(보정 후) · 유효 | 제안(TBD) #13 | 4.2.2 · 4.2.4 |
| `x_neg` · `x_neg_valid` | `float64` · `bool` | m | −x 모서리 | 제안(TBD) #13 | 4.2.2 |
| `y_pos` · `y_pos_valid` | `float64` · `bool` | m | +y 모서리 | 제안(TBD) #13 | 4.2.2 |
| `y_neg` · `y_neg_valid` | `float64` · `bool` | m | −y 모서리 | 제안(TBD) #13 | 4.2.2 |
| `width` · `length` · `height` · `dims_valid` | `float64`×3 · `bool` | m | W(x⁺−x⁻) · L(y⁺−y⁻) · H(z_top − 지지면) · 유효 | 초안(W·L·H) / 제안(유효) | 4.3.4 · 9장 KPI |
| `support_z` · `support_z_valid` | `float64` · `bool` | m | 투영에 쓴 지지면 높이(작업대면이면 0) | 제안(TBD) | 4.3.3 |
| `vertices` | `geometry_msgs/Point[8]` | m | 꼭짓점 8(0~3 윗면, 4~7 지지면 투영). `box_valid=false`면 무시 | 초안(꼭짓점 8) / 제안(형식) | 4.3.1 · 4.3.3 |
| `box_valid` | `bool` | — | vertices·edges 유효 | 제안(TBD) #13 | TR-10 |
| `edges` | `Segment[12]` | m | 모서리 12 | 초안(모서리 12) / 결정 #18 | 4.3.3 |
| `path_candidates` | `Segment[4]` | m | 윗면 네 변 = 외곽 엣지·경로 후보(시작·끝·길이). 실제 용접 이음 판정 아님 | 초안(경로 후보 4) / 결정 #18 | 4.3.2 |
| `config` | `ScanConfig` | — | 적용 설정 스냅샷 | 초안(설정 스냅샷) / 제안(형식) #3 | 4.3.4 · 4.4.7 |
| `started_at` · `finished_at` | `builtin_interfaces/Time`×2 | — | 탐색 시작·종료 시각(탐색 시간 KPI · US-06) | 제안(TBD) | 9장 KPI · US-06 |

```
# contact_scan_interfaces/msg/ScanResult.msg
# 미측정값은 0으로 넣지 않고 *_valid=false 로 표시한다 (TR-10).
string scan_id
builtin_interfaces/Time stamp
bool success
uint16 reason_code
string detail
string frame_id                     # 'workpiece_fixture' (가칭)

float64 z_top
bool z_top_valid
float64 x_pos
bool x_pos_valid
float64 x_neg
bool x_neg_valid
float64 y_pos
bool y_pos_valid
float64 y_neg
bool y_neg_valid

float64 width                       # x_pos - x_neg
float64 length                      # y_pos - y_neg
float64 height                      # z_top - support_z
bool dims_valid
float64 support_z
bool support_z_valid

geometry_msgs/Point[8] vertices     # 0..3 윗면, 4..7 지지면 투영
bool box_valid
Segment[12] edges
Segment[4] path_candidates          # 윗면 네 변 = 외곽 엣지·경로 후보

ScanConfig config
builtin_interfaces/Time started_at
builtin_interfaces/Time finished_at   # (v1.2) 형상 생성 종료 시각. 마무리 홈 복귀 시간 제외
```

```
# contact_scan_interfaces/msg/Segment.msg  (결정 #18 · 2026-09-18)
geometry_msgs/Point start           # m
geometry_msgs/Point end             # m
float64 length                      # m
bool valid
```

**순서 규약 (v1.2 · T01)** — `vertices[0..3]` 윗면, +z에서 내려다봐 (x⁻,y⁻)부터 반시계: 0(x⁻,y⁻) · 1(x⁺,y⁻) · 2(x⁺,y⁺) · 3(x⁻,y⁺) / `vertices[4..7]` = i+4가 i의 바로 아래 / `edges[0..3]` 윗면 i→(i+1)%4 · `[4..7]` 지지면 같은 순서 · `[8..11]` 수직 i→i+4 / `path_candidates[0..3]` = `edges[0..3]`(y⁻ · x⁺ · y⁺ · x⁻ 변) / 치수 `width`=x · `length`=y · `height`=z. 무효 값은 `NaN`, 배열은 길이 유지.

규칙 메모: (1) **미측정값 0 금지** — 값 필드만 보고 판단하지 말고 반드시 `*_valid`를 본다. (2) 비정상 형상(폭 0 이하·높이 음수)은 `success=false`, `reason_code=INVALID_SHAPE`(4.3.5). (3) 원본은 `result_store`(메인 PC)에 먼저 저장하고, MQTT 전달 확인은 DB 커밋이 아니다(4.4.7).

### 3.6 `/scan/log` — `contact_scan_interfaces/msg/ScanLog`

| 항목 | 내용 |
|---|---|
| 종류 · 방향 | Topic · 발행 scan_manager → 구독 mqtt_bridge |
| 의미 | 화면 시간순 로그(단계·좌표·오류·시각). result_store의 진행 기록과 같은 항목 |
| 발행 조건 | 사건 발생 즉시 |
| QoS 제안 | `LOG`: RELIABLE · VOLATILE · KEEP_LAST 100 |
| 관련 | BRD 4.4.3 · 4.4.7 · 4.4.6 |

| 필드 | 자료형 | 단위 | 설명 | 표기 | 근거 |
|---|---|---|---|---|---|
| `stamp` | `builtin_interfaces/Time` | — | 발생 시각 | 초안(발생 시각) | 4.4.3 |
| `scan_id` | `string` | — | 관련 작업(없으면 빈 문자열) | 제안(TBD) #2 | 4.4.7 |
| `level` | `uint8` | — | `LEVEL_INFO=0` · `LEVEL_WARN=1` · `LEVEL_ERROR=2` | 제안(TBD) #2 | 4.4.3 |
| `phase` · `direction` | `uint8`×2 | — | ScanState와 같은 enum | 제안(TBD) #2 | 4.4.3 "단계" |
| `motion_id` | `uint32` | — | 관련 모션(0 = 없음) | 제안(TBD) #2 | 4.2.2 |
| `code` | `uint16` | — | 7.2 공통 코드(0 = 정보) | 제안(TBD) #2·#5 | 4.4.3 "오류" |
| `message` | `string` | — | 사람이 읽는 한 줄 | 제안(TBD) #2 | 4.4.3 |
| `frame_id` · `pose` · `pose_valid` | `string` · `geometry_msgs/Pose` · `bool` | m · rad | 관련 좌표(판정 좌표 또는 정지 좌표, message에 구분 명시) | 제안(TBD) #2 | 4.4.3 "좌표" |

```
# contact_scan_interfaces/msg/ScanLog.msg  (필드 전체 제안 #2)
uint8 LEVEL_INFO=0
uint8 LEVEL_WARN=1
uint8 LEVEL_ERROR=2

builtin_interfaces/Time stamp
string scan_id
uint8 level
uint8 phase                 # ScanState.PHASE_*
uint8 direction             # ScanState.DIR_*
uint32 motion_id
uint16 code                 # 7.2, 0 = 정보
string message
string frame_id
geometry_msgs/Pose pose
bool pose_valid
```

### 3.7 `/safety/status` — `contact_scan_interfaces/msg/SafetyStatus`

| 항목 | 내용 |
|---|---|
| 종류 · 방향 | Topic · 발행 safety_monitor → 구독 scan_manager · mqtt_bridge |
| 의미 | 소프트웨어 이상 감시 결과. `latched=true`이면 scan_manager는 새 작업·재시작을 거절 |
| 발행 조건 | 변경 시 즉시 + 주기(제안 1 Hz, 생존 확인용) |
| QoS 제안 | `STATE`: RELIABLE · TRANSIENT_LOCAL · KEEP_LAST 1 |
| 관련 | BRD 4.5.3 · 4.6 · 6장(래치 해제 TBD) · 정합 #3 |

| 필드 | 자료형 | 단위 | 설명 | 표기 | 근거 |
|---|---|---|---|---|---|
| `stamp` | `builtin_interfaces/Time` | — | 판정 시각 | 제안(TBD) | 위험 10 |
| `level` | `uint8` | — | `LEVEL_OK=0` · `LEVEL_WARN=1` · `LEVEL_STOP=2` | 초안 / 제안(값) #6 | 4.5.3 |
| `reason_code` | `uint16` | — | 7.2 코드(4xx). OK = 0 | 초안 / 제안(값) #5 | 4.5.3 |
| `stop_required` | `bool` | — | 이 상태에서 `/robot/stop`을 요청했음(또는 요청 중) | 초안 | 4.5.3 |
| `latched` | `bool` | — | 조건 해소 후에도 유지되는 래치. 해제는 `/safety/reset`(4.5, 결정 #6) | 초안 | 6장 |
| `detail` | `string` | — | 감시 항목·측정값 요약(예: "force 32.1 N > 30 N") | 제안(TBD) | 4.5.3 원인 기록 |

```
# contact_scan_interfaces/msg/SafetyStatus.msg
uint8 LEVEL_OK=0
uint8 LEVEL_WARN=1
uint8 LEVEL_STOP=2

builtin_interfaces/Time stamp
uint8 level
uint16 reason_code          # 7.2 (4xx)
bool stop_required
bool stop_confirmed         # (v1.2) 요청한 정지가 /robot/status 로 확인됨
bool latched                # true면 scan_manager는 시작·재시작 거절
uint32 motion_id            # (v1.2) 이상 판정 시점의 동작. 없으면 0
geometry_msgs/Point position  # (v1.2) 이상 판정 시점의 TCP 위치
bool position_valid         # (v1.2)
string detail
```

규칙 메모: safety_monitor는 하드웨어 안전(TP E-Stop · 충돌 감지)을 대체하지 않는다(4.5 ※). `stop_required=true`의 정지 완료도 `/robot/status`로 확인한다. `latched=true`는 `/safety/reset`(4.5)이 성공할 때만 false가 된다 — 조건이 사라져도 자동으로 풀리지 않는다.

### 3.8 `/web/heartbeat` — `contact_scan_interfaces/msg/WebHeartbeat` (점선)

| 항목 | 내용 |
|---|---|
| 종류 · 방향 | Topic · 발행 mqtt_bridge → 구독 safety_monitor |
| 의미 | 웹(FastAPI) 생존 신호. mqtt_bridge는 MQTT `hb/web`을 **실제로 수신했을 때만** 전달하고 자체 생성하지 않는다 |
| 발행 조건 | hb/web 수신 시(FastAPI 1 Hz 설계 목표) |
| QoS 제안 | `HEARTBEAT`: BEST_EFFORT · VOLATILE · KEEP_LAST 1 |
| 관련 | BRD 4.7 "웹 수신 heartbeat만 전달" · 6장(HB 만료·브라우저 단절 정책 TBD) |

| 필드 | 자료형 | 단위 | 설명 | 표기 | 근거 |
|---|---|---|---|---|---|
| `session_id` | `string` | — | 웹 세션 식별자(FastAPI 발급, 7.3) | 초안 | 아키텍처 c38 |
| `seq` | `uint32` | — | 세션 내 단조 증가 순번(누락 감지) | 초안 | 위험 10 |
| `stamp` | `builtin_interfaces/Time` | — | hb/web에 실린 발신 시각(웹 PC 시계 · 시간 기준 설정은 6장 선행조건) | 초안 | 6장 |
| `received_stamp` | `builtin_interfaces/Time` | — | mqtt_bridge 수신 시각(ROS 시계). 만료 판정은 이 값 기준 | 제안(TBD) | 6장 HB 만료 |

```
# contact_scan_interfaces/msg/WebHeartbeat.msg
string session_id
uint32 seq
builtin_interfaces/Time stamp           # 웹 발신 시각
builtin_interfaces/Time received_stamp  # mqtt_bridge 수신 시각 (ROS 시계)
```

규칙 메모: safety_monitor의 HB 만료 한계(`hb_timeout_s`)와 만료 시 조치(경고만 vs 정지)는 6장 미결정 사항 — 10장 #12·#6과 함께 확인.

---
## 4. Service

공통 규칙: 모든 응답의 `accepted`/`success`는 **접수·처리 여부**이지 물리적 완료가 아니다. 거절 시 `reason_code`(7.2 · 1xx)와 `detail`을 채운다. Service 콜백 안에서 다른 노드의 완료를 동기 대기하지 않는다(아키텍처 c229).

### 4.1 `/robot/stop` — `contact_scan_interfaces/srv/StopRobot`

| 항목 | 내용 |
|---|---|
| 종류 · 방향 | Service · 서버 robot_manager ← 클라이언트 scan_manager · safety_monitor |
| 의미 | 로봇 즉시 정지 요청. 정지 경로 ①(웹→scan_manager)과 ③(safety_monitor 직접)이 공유. 모션 Action의 cancel과 **별도 경로** |
| 처리 | move_stop(DR_QSTOP 후보) → 순응·힘 제어 해제(finally) → 자동 상승·홈 없음 |
| 관련 | BRD 4.5.1 · 4.5.2 · 4.5.3 · 4.2.3 · TR-07 |

Request

| 필드 | 자료형 | 단위 | 설명 | 표기 | 근거 |
|---|---|---|---|---|---|
| `request_id` | `string` | — | 요청 식별자(7.3). 웹 명령이면 MQTT request_id 그대로, 로컬이면 노드가 생성 | 초안 | 4.7 명령 ID |
| `reason` | `uint16` | — | 7.2 코드(예: `STOP_REQUESTED`, `OVER_FORCE`, `SAMPLE_STALE`) | 초안(이름) / 제안(자료형) #5 | 4.5.3 원인 기록 |
| `detail` | `string` | — | 부가 설명 | 제안(TBD) | — |

Response

| 필드 | 자료형 | 설명 | 표기 | 근거 |
|---|---|---|---|---|
| `accepted` | `bool` | **접수 여부.** 정지 완료는 `/robot/status.moving=false`로 확인 | 초안 | 4.5.1 |
| `reason_code` | `uint16` | 거절 사유(7.2). 접수 = 0 | 제안(TBD) | — |
| `detail` | `string` | — | 제안(TBD) | — |

```
# contact_scan_interfaces/srv/StopRobot.srv
string request_id
string requester            # (v1.2) 요청 노드 이름
uint16 reason               # 7.2
string detail
---
bool accepted               # 접수 ≠ 정지 완료 (완료는 /robot/status.moving == false)
uint16 reason_code
string detail
```

규칙 메모: 이미 정지 중이어도 `accepted=true`(멱등). 드라이버 미연결이면 `accepted=false, reason_code=ROBOT_DISCONNECTED`. 두 클라이언트의 요청이 겹치면 먼저 온 것을 처리하고 나머지도 접수한다.

### 4.2 `/contact/tare` — `contact_scan_interfaces/srv/TareForce`

| 항목 | 내용 |
|---|---|
| 종류 · 방향 | Service · 서버 contact_detector ← 클라이언트 scan_manager |
| 의미 | 무접촉·정지 안정 구간에서 1~2 s 샘플 평균 → 외력 기준값 F₀ 저장. 무접촉 외력이 허용치를 넘으면 툴 등록 이상으로 실패 |
| 관련 | BRD 4.1.3 · 4.1.5 · 1.4 B 구현 계획(set_external_force_reset 미노출 [E18] 대안) |

Request

| 필드 | 자료형 | 단위 | 설명 | 표기 | 근거 |
|---|---|---|---|---|---|
| `duration_s` | `float32` | s | 평균 구간. 0이면 파라미터 `tare_duration_s`(출발값 1.5 s, 범위 1~2 s) | 제안(TBD) | 4.1.3 |
| `scan_id` | `string` | — | 로그 대응용(없으면 빈 문자열) | 제안(TBD) | 4.4.7 |

Response

| 필드 | 자료형 | 단위 | 설명 | 표기 | 근거 |
|---|---|---|---|---|---|
| `success` | `bool` | — | 기준값 저장 성공 | 초안 | 4.1.3 |
| `offset` | `geometry_msgs/Wrench` | N · N·m | 저장한 F₀ | 초안 / 제안(자료형) | 4.1.3 |
| `error` | `uint16` | — | 7.2 코드: `TOOL_REG_SUSPECT`(4.1.5) · `SAMPLE_STALE` · `ROBOT_MOVING` · `NO_SAMPLE`. 성공 = 0 | 초안(이름) / 제안(자료형·값) #5 | 4.1.5 |
| `detail` | `string` | — | 예: "mean |F| 6.2 N > tare_max_force_n 5 N" | 제안(TBD) | — |
| `sample_count` | `uint32` | — | 평균에 쓴 샘플 수(주기 실측 보조) | 제안(TBD) | TR-01 |

```
# contact_scan_interfaces/srv/TareForce.srv
float32 duration_s          # 0 = 파라미터 tare_duration_s
string scan_id
---
bool success
geometry_msgs/Wrench offset # F0
uint16 error                # 7.2, 0 = 없음
string detail
uint32 sample_count
float64 baseline_norm_n     # (v1.2) 무접촉 외력 크기. 툴 무게 등록 점검(4.1.5)
float64 std_norm_n          # (v1.2) 구간 중 외력 크기의 표준편차
```

규칙 메모: 호출 전제(무접촉 · 정지)는 scan_manager가 `/robot/status.moving=false`로 확인하고 호출한다. contact_detector는 구간 중 `/robot/sample` stale 또는 힘 표준편차 과대이면 실패 처리(허용치 TBD).

### 4.3 `/scan/stop` — `contact_scan_interfaces/srv/StopScan`

| 항목 | 내용 |
|---|---|
| 종류 · 방향 | Service · 서버 scan_manager ← 클라이언트 mqtt_bridge |
| 의미 | 웹의 작업 중지(정지 경로 ①). scan_manager는 접수 후 `/robot/stop` 호출 + 진행 중 ExecuteMotion goal cancel(제안 #21), 정지 완료를 `/robot/status`로 확인해 `PHASE_STOPPED`로 전이 |
| 관련 | BRD 4.5.1 · US-04 · 4.4.2 · 9장 KPI(정지 1 s) |

Request / Response — `StopRobot`과 동일 구조(초안 `{request_id, reason}` → `accepted`).

```
# contact_scan_interfaces/srv/StopScan.srv
string request_id           # MQTT cmd/scan/stop 의 request_id
string requester            # (v1.2) 'mqtt_bridge'
uint16 reason               # 7.2 (웹 요청은 STOP_REQUESTED)
string detail
---
bool accepted               # 접수. 정지 완료는 /scan/state.phase == STOPPED (근거: /robot/status)
uint16 reason_code
string detail
```

규칙 메모: 작업 중이 아니어도 `accepted=true`(무해). 작업 중지는 홈 복귀·재시작을 자동 실행하지 않는다(4.5.1). mqtt_bridge는 `accepted`를 `cmd/ack`로, `PHASE_STOPPED` 전이를 `scan/command_result`로 보낸다.

### 4.4 `/scan/set_config` — `contact_scan_interfaces/srv/SetConfig`

| 항목 | 내용 |
|---|---|
| 종류 · 방향 | Service · 서버 scan_manager ← 클라이언트 mqtt_bridge |
| 의미 | 웹의 설정 등록. **동작 중 변경 거절.** 수락 시 scan_manager 자체 값 갱신 + robot_manager·contact_detector 파라미터 갱신(결정 #16: 표준 `rcl_interfaces/srv/SetParameters`, 8.4) |
| 관련 | BRD US-05 · 4.1.6 · 4.3.4(설정 스냅샷) · 정합 #5 |

Request

| 필드 | 자료형 | 설명 | 표기 | 근거 |
|---|---|---|---|---|
| `request_id` | `string` | 요청 식별자 | 초안 | 4.7 |
| `config` | `ScanConfig` | 바꿀 설정. `*_set=true`인 항목만 적용(부분 갱신) | 초안(이름) / 제안(형식) #3 | US-05 |

Response

| 필드 | 자료형 | 설명 | 표기 | 근거 |
|---|---|---|---|---|
| `success` | `bool` | 적용 여부 | 초안 | — |
| `reason_code` | `uint16` | 거절 사유: `BUSY`(동작 중) · `INVALID_VALUE` · `PARAM_SET_FAILED` | 제안(TBD) #14 | US-05 |
| `detail` | `string` | 예: "phase=EDGE_SEARCH" | 제안(TBD) #14 | — |
| `applied` | `ScanConfig` | 적용 후 전체 설정(모든 `*_set=true`) | 제안(TBD) #14 | 4.3.4 |

```
# contact_scan_interfaces/srv/SetConfig.srv
string request_id
ScanConfig config           # *_set = true 인 항목만 적용
---
bool success
uint16 reason_code          # BUSY / INVALID_VALUE / PARAM_SET_FAILED
string detail
ScanConfig applied          # 적용 후 전체 값
```

```
# contact_scan_interfaces/msg/ScanConfig.msg  (전체 제안 #3 · 값은 설계 출발값, 실측 조정)
# 접촉 판정 (contact_detector 파라미터로 전달)
float64 contact_threshold_n     # |F-F0| 접촉 임계, 출발값 3~5 N        (4.1.1)
bool    contact_threshold_set
float64 edge_drop_m             # 접촉 소실 z 급강하, 출발값 0.0005 m    (4.1.2)
bool    edge_drop_set
uint8   debounce_n              # 연속 N회, 출발값 3                      (4.1.4)
bool    debounce_set
float64 over_force_n            # 과대 외력, 출발값 30 N                  (4.5.3)
bool    over_force_set
# 모션 (scan_manager 가 ExecuteMotion goal 에 실음)
float64 descend_speed_mps       # 수직 하강 속도 (저속 등속)             (4.2.1)
bool    descend_speed_set
float64 slide_speed_mps         # 밀기 속도                               (4.2.2)
bool    slide_speed_set
float64 max_descend_m           # 하강 최대 거리 (미접촉 실패 한계)      (4.2.5)
bool    max_descend_set
float64 max_slide_m             # 밀기 최대 거리 (미소실 실패 한계)      (4.2.5)
bool    max_slide_set
float64 motion_timeout_s        # 단위 모션 제한 시간                     (4.2.5)
bool    motion_timeout_set
float64 lift_height_m           # 방향 전환 시 팁 들어 올리는 높이        (4.2.6)
bool    lift_height_set
# 힘/순응 (robot_manager 파라미터로 전달)
float64 target_force_n          # SLIDE −z 목표 힘 (값 TBD)               (4.2.2 · 정합 #5)
bool    target_force_set
float64 drop_limit_m            # 모서리 이탈 하강량 제한, 출발값 0.005 m (4.5.4)
bool    drop_limit_set
```

규칙 메모: (1) 동작 중 판정 = `ScanState.phase ∉ {IDLE, DONE, ERROR, STOPPED}` (제안 #14). (2) `applied`는 `ScanResult.config` 스냅샷과 같은 타입이라 웹이 그대로 표시·재전송할 수 있다. (3) 범위 검증 값(min/max)은 실측 후 확정.

### 4.5 `/safety/reset` — `contact_scan_interfaces/srv/ResetSafety` (결정 #6 · 2026-09-18 신설)

| 항목 | 내용 |
|---|---|
| 종류 · 방향 | Service · 서버 safety_monitor ← 클라이언트 mqtt_bridge (← MQTT `cmd/safety/reset` ← FastAPI `POST /api/safety/reset` ← 관제 화면 "안전 해제" 버튼) |
| 의미 | 관제자가 이상 원인을 확인한 뒤 안전 래치를 푼다. 감시 조건이 아직 참이면 거절. 로봇을 움직이지 않으며, 이후 안전복귀·재시작은 별도 명령 |
| 처리 | 조건 재평가 → 해소됐으면 `latched=false`, `level=OK` → `/safety/status` 즉시 발행 |
| 관련 | BRD 4.5.3(이상 상태별 허용 조건) · 6장(래치 해제 조건) · TR-07 |

Request

| 필드 | 자료형 | 설명 | 표기 | 근거 |
|---|---|---|---|---|
| `request_id` | `string` | MQTT 명령 ID(7.3) | 결정 #6 / 형식 제안 | 4.7 명령 계약 |
| `detail` | `string` | 관제자 메모(선택, 로그·DB 기록용) | 제안(TBD) | 4.4.3 |

Response

| 필드 | 자료형 | 설명 | 표기 | 근거 |
|---|---|---|---|---|
| `success` | `bool` | 해제 여부 | 결정 #6 | — |
| `reason_code` | `uint16` | 거절 사유: `CONDITION_ACTIVE`(조건 미해소) · `INVALID_REQUEST`. 성공 = 0 | 제안(TBD) #5 | 7.2 |
| `detail` | `string` | 예: "force 31.2 N still > 30 N" | 제안(TBD) | — |

```
# contact_scan_interfaces/srv/ResetSafety.srv  (결정 #6 · 2026-09-18)
string request_id
string detail               # 관제자 메모 (선택)
---
bool success
uint16 reason_code          # 7.2: CONDITION_ACTIVE / INVALID_REQUEST
string detail
```

규칙 메모: (1) 래치가 걸려 있지 않아도 `success=true`(멱등). (2) 해제 후에도 `scan_manager`는 시작·재시작 시 `/safety/status.latched=false`를 다시 확인한다. (3) 해제는 `ScanLog`(level=WARN, code=0, message="safety latch reset by operator")로 기록한다.

---

## 5. Action

공통 규칙: goal 수락/거절 = "접수/거절"(cmd/ack), Result = "완료/실패"(scan/result 또는 scan/command_result). 취소 요청 접수와 실제 정지 완료를 구분한다(4.2.3). Feedback 주기는 제안이며 표시(10 Hz)와 ROS 측정 루프(50 Hz)에 영향을 주지 않는 범위로 정한다.

### 5.1 `/scan/run` — `contact_scan_interfaces/action/RunScan`

| 항목 | 내용 |
|---|---|
| 종류 · 방향 | Action · 서버 scan_manager ← 클라이언트 mqtt_bridge |
| 의미 | 새 작업 시작. 동시 작업 제한(진행 중이면 goal 거절 `BUSY`). `latched=true`면 거절 `SAFETY_LATCHED` |
| 취소 | goal cancel = `/scan/stop`과 같은 처리(제안). 결과는 `canceled` + 확보한 값이 실린 ScanResult |
| 관련 | BRD US-01 · 4.4.2 · 4.2 · 4.3 · 9장 KPI(120 s) |

| 부 | 필드 | 자료형 | 설명 | 표기 | 근거 |
|---|---|---|---|---|---|
| Goal | `request_id` | `string` | MQTT 명령 ID(중복 실행 방지) | 제안(TBD) #20 | 4.7 명령·저장 계약 |
| Goal | `use_override` · `config_override` | `bool` · `ScanConfig` | 이번 작업에만 적용할 설정(옵션). false면 현재 설정 | 제안(TBD) #20 | US-05 |
| Result | `scan_id` | `string` | 발급된 작업 ID | 제안(TBD) #20 | 4.4.7 |
| Result | `success` · `reason_code` · `detail` | `bool` · `uint16` · `string` | 완료/실패와 사유 | 제안(TBD) #20 | 4.2.5 |
| Result | `result` | `ScanResult` | `/scan/result`와 동일 내용(중복 반영 방지는 scan_id) | 제안(TBD) #20 | 4.7 "Action 결과와 중복 방지" |
| Feedback | `state` | `ScanState` | 단계 변경 시 | 제안(TBD) #20 | 4.4.4 |

```
# contact_scan_interfaces/action/RunScan.action
# Goal
string request_id
bool use_override
ScanConfig config_override
---
# Result
string scan_id
bool success
uint16 reason_code
string detail
ScanResult result
---
# Feedback
ScanState state
```

### 5.2 `/scan/home` — `contact_scan_interfaces/action/ReturnHome`

| 항목 | 내용 |
|---|---|
| 종류 · 방향 | Action · 서버 scan_manager ← 클라이언트 mqtt_bridge |
| 의미 | 안전복귀 = **홈위치(시작위치)** 로 복귀. 작업대 원점·방향별 원점 복귀(scan 내부 MOVE_TO)와 다른 동작. 측정값·로그 보존. 작업 중(모션 진행 중)에는 거절 — 먼저 `/scan/stop` |
| 관련 | BRD US-11 · 4.4.9 · 6장(홈 좌표·복귀 경로 TBD) |

| 부 | 필드 | 자료형 | 설명 | 표기 | 근거 |
|---|---|---|---|---|---|
| Goal | `request_id` | `string` | — | 제안(TBD) | 4.7 |
| Result | `success` · `reason_code` · `detail` | — | — | 제안(TBD) | 4.4.9 |
| Result | `final_pose` · `frame_id` | `geometry_msgs/Pose` · `string` | 복귀 후 정지 pose(ExecuteMotion Result에서) | 제안(TBD) | 4.4.9 |
| Feedback | `pose` · `frame_id` | `geometry_msgs/Pose` · `string` | 진행 중 pose(제안 5 Hz) | 제안(TBD) | 4.4.4 "홈 복귀 진행 상태" |

```
# contact_scan_interfaces/action/ReturnHome.action
string request_id
---
bool success
uint16 reason_code
string detail
geometry_msgs/Pose final_pose
string frame_id
---
geometry_msgs/Pose pose
string frame_id
```

### 5.3 `/scan/resume` — `contact_scan_interfaces/action/Resume` (**결정 · 2026-09-18 확인 #1: 별도 Action 유지**)

| 항목 | 내용 |
|---|---|
| 종류 · 방향 | Action · 서버 scan_manager ← 클라이언트 mqtt_bridge |
| 의미 | 관제자 재시작. result_store 진행 기록을 확인해 **기존 측정값 유지 · 중단 방향부터** 이어서 탐색. 새 작업과 구분(scan_id 유지). `latched=true`면 거절. 안전복귀를 거친 뒤의 재접근 절차는 TBD(6장) |
| 관련 | BRD US-12 · 4.4.8 · TR-08 · 6장 |

| 부 | 필드 | 자료형 | 설명 | 표기 | 근거 |
|---|---|---|---|---|---|
| Goal | `request_id` | `string` | — | 제안(TBD) #1 필드 | 4.7 |
| Goal | `scan_id` | `string` | 재개할 작업. 빈 문자열이면 가장 최근 중단 작업(제안) | 제안(TBD) #1 필드 | 4.4.8 |
| Result | `RunScan.Result`와 동일 | | 재개 후 최종 결과 | 제안(TBD) #1 | TR-08 |
| Feedback | `state` | `ScanState` | — | 제안(TBD) #1 | 4.4.4 |

```
# contact_scan_interfaces/action/Resume.action   (별도 Action 유지 — 결정 #1 · 2026-09-18)
string request_id
string scan_id              # 빈 문자열 = 최근 중단 작업
---
string scan_id
bool success
uint16 reason_code
string detail
ScanResult result
---
ScanState state
```

규칙 메모: 거절 사유(제안) — `NO_RESUMABLE_SCAN`(기록 없음) · `SAFETY_LATCHED` · `BUSY` · `ROBOT_DISCONNECTED`. 재접근(홈에서 중단 위치 상공으로 이동 → 재하강?)은 6장 확정 전까지 구현하지 않고 `NOT_SUPPORTED`로 거절하는 것을 제안.

### 5.4 `/robot/execute_motion` — `contact_scan_interfaces/action/ExecuteMotion`

| 항목 | 내용 |
|---|---|
| 종류 · 방향 | Action · 서버 robot_manager ← 클라이언트 scan_manager |
| 의미 | 단위 모션 1개. 동시에 1개만 수락(진행 중이면 거절 `BUSY`). robot_manager는 goal의 `scan_id`·`motion_id`로 `/contact/event`를 대조해 CONTACT/EDGE에서 정상 종료, OVER_FORCE·정지 요청·취소·한계 초과에서 실패 종료. **Result.pose = 정지 시점 pose = 중단 위치 기록의 출처**(정합 #6) |
| 취소 | cancel 접수 → move_stop → 순응·힘 제어 해제(finally) → Result `reason=CANCELED`. 접수와 정지 완료 구분(4.2.3) |
| 관련 | BRD 4.2.1~4.2.6 · 4.5.1 · 4.5.2 · 4.5.4 · 정합 #2·#5·#6 |

Goal

| 필드 | 자료형 | 단위 | 설명 | 표기 | 근거 |
|---|---|---|---|---|---|
| `scan_id` | `string` | — | scan_manager 발급 | 초안 | 정합 #2 |
| `motion_id` | `uint32` | — | scan_manager 발급, 작업 내 유일 | 초안 / 제안(자료형) | 정합 #2 |
| `operation` | `uint8` | — | **(v1.2 번호 변경)** `OP_NONE=0`(goal에는 미사용) · `OP_MOVE_TO=1` · `OP_DESCEND=2` · `OP_SLIDE=3` · `OP_HOME=4` | T01 | 4.2 · 4.4.9 |
| `target` | `geometry_msgs/Pose` | m · rad | MOVE_TO 목표. DESCEND/SLIDE는 무시(현재 위치 기준), HOME은 무시(파라미터 `home_pose`, 제안 #19) | 초안 / 제안(자료형) #4 | 4.2.6 · 6장 |
| `frame_id` | `string` | — | target 프레임(출발값 `base_link`) | 제안(TBD) | 6장 |
| `direction` | `uint8` | — | SLIDE 방향 `DIR_*`(ScanState와 동일 값). DESCEND는 −z 고정, 나머지 `DIR_NONE` | 초안 / 제안(값) #4 | 4.2.2 |
| `speed` | `float64` | m/s | 직선 속도(저속 등속). 드라이버 단위(mm/s)는 robot_manager 변환 | 초안 / 제안(단위) #4 | 4.2.1 |
| `max_distance` | `float64` | m | DESCEND/SLIDE 최대 이동 거리. 초과 시 `MAX_DISTANCE`로 실패 종료 | 초안 | 4.2.5 |
| `timeout` | `builtin_interfaces/Duration` | s | 제한 시간. 초과 시 `TIMEOUT` | 초안 / 제안(자료형) | 4.2.5 |

Result

| 필드 | 자료형 | 단위 | 설명 | 표기 | 근거 |
|---|---|---|---|---|---|
| `pose` | `geometry_msgs/Pose` | m · rad | **정지 시점 pose**(판정 샘플 좌표와 다름) | 초안 | 정합 #6 · 4.2.1 |
| `frame_id` · `pose_stamp` | `string` · `builtin_interfaces/Time` | — | pose 프레임·취득 시각 | 제안(TBD) | 4.1.6 |
| `reason` | `uint8` | — | 종료 사유 `REASON_*`(아래 상수) | 초안(종료 사유) / 제안(값) #4 | 4.2.5 · 4.5 |
| `reason_code` | `uint16` | — | 7.2 공통 코드(ROBOT_ERROR 등 상세) | 제안(TBD) #5 | 4.2.5 |
| `detail` | `string` | — | — | 제안(TBD) | — |
| `event_id` | `uint64` | — | 종료 원인이 된 ContactEvent(없으면 0) | 제안(TBD) | 4.2.2 이벤트 대조 |
| `distance_travelled` | `float64` | m | 이동 거리 | 제안(TBD) | 4.2.5 |
| `compliance_released` | `bool` | — | 순응·힘 제어 해제 확인(항상 true여야 함) | 제안(TBD) | 4.5.2 · TR-07 |

Feedback

| 필드 | 자료형 | 단위 | 설명 | 표기 | 근거 |
|---|---|---|---|---|---|
| `pose` · `frame_id` · `pose_stamp` | — | m · rad | 현재 pose | 초안(정지 시점 pose 계열) / 제안 | 4.4.1 |
| `distance_travelled` | `float64` | m | — | 제안(TBD) #4 | — |
| `elapsed` | `builtin_interfaces/Duration` | s | — | 제안(TBD) #4 | — |
| 주기 | — | — | 10 Hz 제안 | 제안(TBD) #4 | — |

```
# contact_scan_interfaces/action/ExecuteMotion.action
# Goal
uint8 OP_NONE=0             # (v1.2) goal 에는 쓰지 않음
uint8 OP_MOVE_TO=1
uint8 OP_DESCEND=2
uint8 OP_SLIDE=3
uint8 OP_HOME=4
uint8 DIR_NONE=0            # ScanState.DIR_* 와 동일 값
uint8 DIR_POS_X=1
uint8 DIR_NEG_X=2
uint8 DIR_POS_Y=3
uint8 DIR_NEG_Y=4

string scan_id
uint32 motion_id
uint8 operation
geometry_msgs/Pose target   # MOVE_TO 만 사용
string frame_id
uint8 direction             # SLIDE 만 사용
float64 speed               # m/s
float64 max_distance        # m (DESCEND · SLIDE)
builtin_interfaces/Duration timeout
---
# Result
uint8 REASON_TARGET_REACHED=0   # MOVE_TO · HOME 정상
uint8 REASON_CONTACT=1          # DESCEND 정상 종료
uint8 REASON_EDGE=2             # SLIDE 정상 종료
uint8 REASON_MAX_DISTANCE=3     # 미접촉 · 미소실 실패 (4.2.5)
uint8 REASON_TIMEOUT=4
uint8 REASON_STOP_REQUESTED=5   # /robot/stop
uint8 REASON_CANCELED=6         # Action cancel
uint8 REASON_OVER_FORCE=7
uint8 REASON_ROBOT_ERROR=8
uint8 REASON_REJECTED=9         # goal 수락 후 실행 전 거절 (연결 끊김 등)

geometry_msgs/Pose pose         # 정지 시점 pose (중단 위치 출처)
string frame_id
builtin_interfaces/Time pose_stamp
uint8 reason
uint16 reason_code              # 7.2
string detail
uint64 event_id
float64 distance_travelled
bool compliance_released
---
# Feedback
geometry_msgs/Pose pose
string frame_id
builtin_interfaces/Time pose_stamp
float64 distance_travelled
builtin_interfaces/Duration elapsed
```

규칙 메모: (1) SLIDE의 −z 목표 힘은 goal 필드가 아니라 robot_manager 파라미터 `slide_target_force_n`이다(정합 #5). (2) SLIDE 중 하강량이 `drop_limit_m`(5 mm)을 넘으면 즉시 정지·`REASON_ROBOT_ERROR`+`reason_code=DROP_LIMIT`(제안). (3) 모든 종료 경로에서 `compliance_released=true`를 보장한다(finally). (4) **(v1.2)** `OP_MOVE_TO` · `OP_HOME` 중에는 CONTACT/EDGE 이벤트로 정지하지 않는다(OVER_FORCE는 항상 정지). `OP_HOME`은 관제자의 안전복귀와 스캔 정상 완료 뒤의 마무리 복귀에 함께 쓴다. SLIDE 방향은 Base 축 기준이다. (5) 2단 속도(4.2.7 Could)는 goal에 넣지 않고 향후 `speed_near_edge` 파라미터로 검토.

---
## 6. ROS 파라미터 (노드별)

모든 값은 **설계 출발값 · 제안(TBD)** 이며 실측 후 조정한다. "출처" 열은 값의 근거. `SetConfig`로 바뀌는 항목은 ★ 표시(scan_manager가 표준 `rcl_interfaces/srv/SetParameters`로 전파, 결정 #16). **★ 파라미터의 이름은 계약이다**(이름으로 전파하므로 바꾸지 않는다). 그 밖의 파라미터는 노드 담당자 재량으로 추가한다.

### 6.1 robot_manager

| 파라미터 | 자료형 | 단위 | 출발값 | 설명 | 출처 |
|---|---|---|---|---|---|
| `slide_target_force_n` ★ | double | N | TBD("낮은 누름 힘") | SLIDE −z 목표 힘(set_desired_force · DR_FC_MOD_REL) | 4.2.2 · 정합 #5 · 위험 4·5 |
| `drop_limit_m` ★ | double | m | 0.005 | 모서리 이탈 시 하강량 제한 | 4.5.4 |
| `sample_rate_hz` | double | Hz | 50 | `/robot/sample` 발행 주기 목표 | 4.7 데이터 계약 |
| `status_rate_hz` | double | Hz | 10 | `/robot/status` 주기 발행 | 제안 |
| `home_pose` | double[6] | m · rad | TBD | 홈위치(시작위치). 환경 세팅 후 확정 | 4.4.9 · 6장 · 제안 #19 |
| `frame_id` | string | — | `base_link` | 발행 pose 프레임(가칭) | 6장 |
| `dsr_namespace` · `dsr_model` | string | — | `dsr01` · `m0609` | 두산 드라이버 네임스페이스·모델 | 아키텍처 c270 |
| `mode` | string | — | `real` \| `virtual` | 드라이버 bringup 모드(virtual은 힘 제어 미동작 가능 [E10]) | 위험 2 |
| `rg2_grip_width_m` · `rg2_grip_force_n` | double | m · N | TBD | 탐침 파지 명령 값(`/onrobot/sendCommand`) | 4.6 탐침 파지 · [E18] |
| `stop_timeout_s` | double | s | 1.0 | 정지 요청 후 `moving=false` 확인 제한(KPI 정지 1 s) | 9장 KPI |

### 6.2 contact_detector

| 파라미터 | 자료형 | 단위 | 출발값 | 설명 | 출처 |
|---|---|---|---|---|---|
| `source` | string | — | `robot_force` \| `sim` | 입력원. A(rg2)는 제외 | 4.1.6 · 1.4 |
| `contact_threshold_n` ★ | double | N | 4.0 (범위 3~5) | 접촉 발생 `|F − F₀|` 임계 | 4.1.1 |
| `edge_drop_m` ★ | double | m | 0.0005 | 접촉 소실 z 급강하(주 신호) | 4.1.2 |
| `edge_force_drop_ratio` | double | — | TBD | 외력 감소 보조 신호 비율 | 4.1.2 |
| `debounce_n` ★ | int | 회 | 3 | 연속 N회 | 4.1.4 |
| `over_force_n` ★ | double | N | 30 | 과대 외력 | 4.5.3 |
| `tare_duration_s` | double | s | 1.5 (범위 1~2) | 기준값 평균 구간 | 4.1.3 |
| `tare_max_force_n` | double | N | TBD | 무접촉 외력 허용치(툴 등록 점검) | 4.1.5 |
| `filter_window` | int | 샘플 | TBD | 이동평균 창 | 위험 1·5 |
| `stale_age_ms` | int | ms | 100 | 샘플 최신성 한계 | 4.1.6 · 제안 #12 |
| `sim_box_size_m` · `sim_box_origin_m` | double[3] · double[3] | m | TBD | sim 가상 직육면체 치수·원점 | 1.4 C · US-07 |

### 6.3 safety_monitor

| 파라미터 | 자료형 | 단위 | 출발값 | 설명 | 출처 |
|---|---|---|---|---|---|
| `over_force_n` ★ | double | N | 30 | 과대 외력(contact_detector와 같은 값 유지 · 2차 감시) | 4.5.3 · 결정 #17 |
| `drop_limit_m` ★ | double | m | 0.005 | **(v1.2)** 모서리 하강량 제한 2차 감시. 기준 = `operation`이 SLIDE로 바뀐 첫 샘플의 z. robot_manager(1차)와 **값도 기준 z도 같다**. 같은 샘플에서 동시에 걸릴 때의 동작은 이슈 #53 | 4.5.4 · T01 |
| `max_speed_mps` | double | m/s | TBD | TCP 속도 한계(샘플 차분) | 4.6 |
| `workspace_min_m` · `workspace_max_m` | double[3] | m | TBD | 작업영역 상자(base_link) | 6장 제약(900 mm) |
| `max_descend_m` | double | m | TBD | 하강 한계(z 하한) | 4.6 |
| `sample_stale_ms` | int | ms | 100 | `/robot/sample` 최신성 | 위험 10 · 제안 #12 |
| `robot_status_timeout_ms` | int | ms | TBD | `/robot/status` 미수신 → 연결 이상 | 4.6 |
| `hb_timeout_s` | double | s | TBD(예 3 s) | `/web/heartbeat` 만료 | 6장 HB 만료 |
| `hb_expired_action` | string | — | `warn` \| `stop` | HB 만료 시 조치(브라우저 단절 정책 TBD) | 6장 |
| `latch_levels` | string[] | — | `["STOP"]` | 래치할 level | 6장 래치 |

### 6.4 scan_manager

| 파라미터 | 자료형 | 단위 | 출발값 | 설명 | 출처 |
|---|---|---|---|---|---|
| `descend_speed_mps` ★ | double | m/s | TBD(저속) | DESCEND 속도 | 4.2.1 |
| `slide_speed_mps` ★ | double | m/s | TBD(예 0.010, 편향 계산 예시값) | SLIDE 속도 | 4.2.2 · 1.4 |
| `max_descend_m` ★ · `max_slide_m` ★ | double | m | TBD | 미접촉·미소실 실패 한계 | 4.2.5 |
| `motion_timeout_s` ★ | double | s | TBD | 단위 모션 제한 | 4.2.5 |
| `lift_height_m` ★ | double | m | 0.05 | 방향 전환 시 팁 상승량 | 4.2.6 · T01 |
| `recontact_margin_m` | double | m | 0.001 | **(v1.2)** 방향 전환 뒤 내림 목표 = 첫 접촉 z + 이 값. `drop_limit_m`보다 충분히 작아야 함 | 4.2.6 · T01 |
| `recontact_speed_mps` | double | m/s | TBD(저속) | **(v1.2)** 방향 전환 뒤 내림 속도 | 4.2.6 · T01 |
| `tip_radius_m` | double | m | 0.003 | 편향 보정 r | 1.4 · 4.2.4 |
| `detect_latency_s` | double | s | 0.040 | 편향 보정 지연(실측 대체) | 1.4 · TR-01 |
| `result_frame_id` | string | — | `workpiece_fixture` | ScanResult 프레임(가칭) | 6장 · 제안 #10 |
| `base_to_fixture` | double[6] | m · rad | TBD | base_link → workpiece_fixture 변환 | 4.3.3 · 6장 |
| `support_z_m` | double | m | 0.0 | 지지면 높이(작업대면 = 0) | 4.3.3 |
| `search_origin_pose` | double[6] | m · rad | TBD | 탐색 기준점 상공 pose | 4.2.1 · 6장 |
| `result_dir` | string | — | TBD | result_store 경로(JSON/CSV) | 4.4.7 |
| `allow_concurrent` | bool | — | false | 동시 작업 제한 | 아키텍처 c167 |

### 6.5 mqtt_bridge

| 파라미터 | 자료형 | 단위 | 출발값 | 설명 | 출처 |
|---|---|---|---|---|---|
| `broker_host` · `broker_port` | string · int | — | TBD(웹 PC) | Mosquitto | 4.7 |
| `client_id` | string | — | `mqtt_bridge` | — | — |
| `topic_map_file` | string | — | TBD | ROS↔MQTT 토픽 맵 yaml | 아키텍처 c210 |
| `downsample_hz` | double | Hz | 10 | RobotSample 표시용 다운샘플 | 4.7 |
| `hb_ros_hz` | double | Hz | 1 | `hb/ros` 발행 | 4.7 |
| `cmd_expiry_s` | double | s | TBD | 명령 만료 검사 | 아키텍처 c38 · 위험 10 |
| `qos_default` | int | — | 1 | MQTT QoS(명령·이벤트) | 아키텍처 c101 |

---

## 7. 공통 정의

### 7.1 enum (msg 상수로 정의, 정의 위치 1곳 · 다른 메시지는 같은 값 사용) — 제안(TBD)

| enum | 정의 위치 | 값 |
|---|---|---|
| ContactEvent type | `ContactEvent.msg` | `TYPE_CONTACT=0` · `TYPE_EDGE=1` · `TYPE_OVER_FORCE=2` |
| phase | `ScanState.msg` | `PHASE_IDLE=0` · `PREPARING=1` · `TOP_SEARCH=2` · `EDGE_SEARCH=3` · `GEOMETRY=4` · `DONE=5` · `ERROR=6` · `STOPPING=7` · `STOPPED=8` · `HOMING=9` · `RESUMING=10` |
| direction | `ScanState.msg` (ExecuteMotion에 같은 값 복제) | `DIR_NONE=0` · `POS_X=1` · `NEG_X=2` · `POS_Y=3` · `NEG_Y=4` |
| operation | `ExecuteMotion.action` (RobotSample · RobotStatus에 같은 값 복제) | **(v1.2)** `OP_NONE=0` · `MOVE_TO=1` · `DESCEND=2` · `SLIDE=3` · `HOME=4` |
| motion reason | `ExecuteMotion.action` | `REASON_TARGET_REACHED=0` … `REJECTED=9` (5.4) |
| safety level | `SafetyStatus.msg` | `LEVEL_OK=0` · `WARN=1` · `STOP=2` |
| log level | `ScanLog.msg` | `LEVEL_INFO=0` · `WARN=1` · `ERROR=2` |

BRD 4.4.4 단계명 ↔ phase 매핑: 대기=IDLE · (준비=PREPARING) · 윗면 탐색=TOP_SEARCH · 모서리 탐색 n/4=EDGE_SEARCH+progress · 형상 생성=GEOMETRY · 완료=DONE · 오류=ERROR · 중단=STOPPING/STOPPED · 홈 복귀=HOMING · 재시작 진행=RESUMING.

### 7.2 오류·사유 코드 (`uint16` 공통 표) — 제안(TBD) #5

`reason` · `error` · `reason_code` · `code`(ScanLog) 필드는 모두 이 표를 쓴다. 정의 위치: `contact_scan_interfaces/msg/ReasonCode.msg`(상수만 있는 메시지, 토픽 없음 · 신설은 결정 #18, 코드 값은 제안 #5). **(v1.2 원칙) 번호는 추가만 하고 바꾸지 않는다.** `TARE_FAILED=303`은 세분 코드에 해당하지 않는 나머지 실패용으로 남긴다.

| 범위 | 코드 | 이름 | 뜻 | 근거 |
|---|---|---|---|---|
| 0 | 0 | `OK` | 정상 / 사유 없음 | — |
| 1xx 요청 거절 | 100 | `BUSY` | 동작 중(동시 작업 제한 · 설정 변경 거절) | 4.4.2 · US-05 |
| | 101 | `INVALID_REQUEST` | 필드 누락·형식 오류 | — |
| | 102 | `INVALID_VALUE` | 범위 밖 설정값 | US-05 |
| | 103 | `SAFETY_LATCHED` | 안전 래치 중 | 6장 |
| | 104 | `ROBOT_DISCONNECTED` | 드라이버 미연결 | 4.5.1 |
| | 105 | `NO_RESUMABLE_SCAN` | 재개할 기록 없음 | 4.4.8 |
| | 106 | `DUPLICATE_REQUEST` | request_id 중복 | 4.7 명령 계약 |
| | 107 | `NOT_SUPPORTED` | 미구현 절차(예: 홈 복귀 후 재접근) | 6장 |
| | 108 | `PARAM_SET_FAILED` | 다른 노드 파라미터 갱신 실패 | 결정 #16 |
| 2xx 동작 종료 | 200 | `STOP_REQUESTED` | 작업 중지 요청(웹) | 4.5.1 |
| | 201 | `CANCELED` | Action 취소 | 4.2.3 |
| | 202 | `MAX_DISTANCE` | 최대 이동 거리 안 미접촉·미소실 | 4.2.5 |
| | 203 | `TIMEOUT` | 제한 시간 초과 | 4.2.5 |
| | 204 | `ROBOT_ERROR` | 드라이버·로봇 오류 | 4.5.1 |
| | 205 | `DROP_LIMIT` | 하강량 제한 도달 | 4.5.4 |
| 3xx 접촉·툴 | 300 | `NO_CONTACT` | DESCEND 미접촉 | 4.2.5 |
| | 301 | `NO_EDGE` | SLIDE 미소실 | 4.2.5 |
| | 302 | `TOOL_REG_SUSPECT` | 무접촉 외력 허용치 초과(툴 등록 이상 의심) | 4.1.5 |
| | 303 | `TARE_FAILED` | 기준값 설정 실패(불안정·샘플 부족) | 4.1.3 |
| | 304 | `ROBOT_MOVING` | 정지 조건 미충족(tare) | 4.1.3 |
| | 305 | `TARE_UNSTABLE` | **(v1.2)** 구간 중 외력 불안정 | 4.1.3 · T01 |
| | 306 | `TARE_TIMEOUT` | **(v1.2)** 제한 시간 안에 샘플 수 미달 | 4.1.3 · T01 |
| | 307 | `NO_SAMPLE` | **(v1.2)** `/robot/sample` 미수신(v1.1의 4.2가 쓰던 이름에 번호 부여) | 4.1.3 · T01 |
| 4xx 안전 | 400 | `OVER_FORCE` | 과대 외력 | 4.5.3 |
| | 401 | `OVER_SPEED` | 속도 한계 | 4.6 |
| | 402 | `OUT_OF_WORKSPACE` | 작업영역·하강 한계 | 4.6 · 6장 |
| | 403 | `SAMPLE_STALE` | 샘플 최신성 위반 | 위험 10 |
| | 404 | `ROBOT_STATUS_LOST` | 로봇 상태 미수신 | 4.6 |
| | 405 | `HB_EXPIRED` | 웹 heartbeat 만료 | 6장 |
| | 406 | `CONDITION_ACTIVE` | 래치 해제 요청 시 이상 조건이 아직 참 | 4.5 · 결정 #6 |
| 5xx 형상 | 500 | `INVALID_SHAPE` | 폭 0 이하 · 높이 음수 등 | 4.3.5 |
| | 501 | `INSUFFICIENT_POINTS` | 5점 미확보 상태에서 형상 요청 | 4.3.1 |

```
# contact_scan_interfaces/msg/ReasonCode.msg  (상수 전용 · 제안 #5)
uint16 OK=0
uint16 BUSY=100
uint16 INVALID_REQUEST=101
uint16 INVALID_VALUE=102
uint16 SAFETY_LATCHED=103
uint16 ROBOT_DISCONNECTED=104
uint16 NO_RESUMABLE_SCAN=105
uint16 DUPLICATE_REQUEST=106
uint16 NOT_SUPPORTED=107
uint16 PARAM_SET_FAILED=108
uint16 STOP_REQUESTED=200
uint16 CANCELED=201
uint16 MAX_DISTANCE=202
uint16 TIMEOUT=203
uint16 ROBOT_ERROR=204
uint16 DROP_LIMIT=205
uint16 NO_CONTACT=300
uint16 NO_EDGE=301
uint16 TOOL_REG_SUSPECT=302
uint16 TARE_FAILED=303
uint16 ROBOT_MOVING=304
uint16 TARE_UNSTABLE=305
uint16 TARE_TIMEOUT=306
uint16 NO_SAMPLE=307
uint16 OVER_FORCE=400
uint16 OVER_SPEED=401
uint16 OUT_OF_WORKSPACE=402
uint16 SAMPLE_STALE=403
uint16 ROBOT_STATUS_LOST=404
uint16 HB_EXPIRED=405
uint16 CONDITION_ACTIVE=406
uint16 INVALID_SHAPE=500
uint16 INSUFFICIENT_POINTS=501
```

### 7.3 ID 규칙 — 제안(TBD)

| ID | 자료형 | 생성 주체 | 유일성 범위 | 형식·규칙 | 근거 |
|---|---|---|---|---|---|
| `request_id` | `string` | FastAPI(웹 명령) / 요청 노드(로컬 `/robot/stop`) | 전역 | UUID v4 문자열. 웹 명령은 MQTT 페이로드 값을 그대로 전달. mqtt_bridge는 최근 N개를 기억해 중복 거절(`DUPLICATE_REQUEST`) | 4.7 명령 계약 · 아키텍처 c38 |
| `scan_id` | `string` | scan_manager | 메인 PC 전역(재부팅 후에도) | `YYYYMMDD-HHMMSS-xxxx`(xxxx 난수 4자리) 제안. result_store 파일명과 DB `scan_result` 키로 재사용 | 4.4.7 · TR-10 |
| `motion_id` | `uint32` | scan_manager | scan_id 안에서 유일 | 작업 시작 시 1부터 단조 증가. 0 = 없음 | 정합 #2 |
| `sample_id` | `uint64` | robot_manager | 프로세스 수명 | 발행마다 +1. 0 = 미발급 | 4.1.6 |
| `event_id` | `uint64` | contact_detector | 프로세스 수명 | 발행마다 +1. 0 = 없음. DB `scan_event` 중복 방지 키는 (`scan_id`, `event_id`) | 위험 10 · TR-10 |
| `session_id` | `string` | FastAPI | 전역 | 웹 세션 UUID | 아키텍처 c38 |

### 7.4 시각 · 단위 · 프레임 규칙

| 항목 | 규칙 | 표기 |
|---|---|---|
| 시각 | 모든 `*_stamp`는 `builtin_interfaces/Time`, 메인 PC ROS 시계. 웹 PC 시계와의 시간 기준 맞춤(NTP 등)은 관제 지연 측정의 선행조건(6장) | 확정 방향 |
| 통합 샘플 | pose와 wrench는 취득 시각을 각각 보존, 동시 취득으로 간주하지 않음. 허용 시각 차이는 TBD(6장 "데이터 최신성·허용 시각 차이") | 확정 (4.1.6) |
| 판정 좌표 vs 정지 좌표 | 판정 좌표 = `ContactEvent.pose`(측정값의 출처) · 정지 좌표 = `ExecuteMotion.Result.pose`(중단 위치의 출처). 혼용 금지 | 확정 (4.2.1 · 정합 #6) |
| 단위 | m · rad · N · N·m. 드라이버 posx(mm · deg)·force 단위 변환은 robot_manager만 수행. 웹 mm 변환은 mqtt_bridge JSON 직렬화 시(T01 확정). 웹에는 각도 값을 싣지 않는다 | 확정 (4.7 · T01) |
| 프레임 | `RobotSample` · `ContactEvent` · `ExecuteMotion` = `base_link`(가칭) / `ScanResult` = `workpiece_fixture`(가칭, 작업대 좌표). base→fixture 변환은 scan_manager 파라미터. **(v1.2 확정)** T03 이후에도 샘플은 계속 Base. 조건: 배치 가이드를 Base 축과 평행하게 설치, 평행 이동만. BRD 4.7의 "프레임 변환은 robot_manager"는 두산 좌표 → `base_link` 변환을 가리킨다. 값은 환경 세팅 후 확정 | T01 |
| TCP · 힘 기준 | **(v1.2)** TCP = 팁 최하단점(접촉 z = 윗면 높이), 탐색 중 자세 수직 고정, 외력은 `get_tool_force(ref=DR_BASE)`. Fz 부호는 T08에서 확인해 기록 | T01 |
| 편향 보정 | scan_manager(geometry_estimator)가 EDGE 판정 좌표에 √(2rδ−δ²) + v·지연을 진행 방향 반대로 적용해 `ScanResult` 좌표를 만든다. `ContactEvent.pose`는 보정 전 원값 | 확정 (4.2.4 · 1.4) |

### 7.5 접수 ≠ 완료 규칙 (세 정지 경로 공통)

| 경로 | 요청 | 접수 표시 | 완료 확인 |
|---|---|---|---|
| ① 웹 작업 중지 | `cmd/scan/stop` → `/scan/stop` → `/robot/stop` | `StopScan.accepted` → `cmd/ack` | `/robot/status.moving=false` → `ScanState.phase=STOPPED` → `scan/command_result` |
| ② 접촉/엣지/과대외력 판정 | `/contact/event` → robot_manager 자체 정지 | 없음(이벤트) | `ExecuteMotion.Result` + `/robot/status.moving=false` |
| ③ 안전 이상 | safety_monitor → `/robot/stop` (웹 경유 없음) | `StopRobot.accepted` | `/robot/status.moving=false` (safety_monitor · scan_manager 각각 확인) |

정지 경로 ③이 래치를 걸면 `/safety/reset`(4.5)이 성공할 때까지 시작·재시작이 거절된다(결정 #6). 작업 중지는 홈 복귀·재시작을 자동 실행하지 않는다(4.5.1). 순응·힘 제어 해제는 모든 경로에서 finally 보장(4.5.2), `RobotStatus.compliance_active=false` · `force_ctrl_active=false`(v1.2) · `ExecuteMotion.Result.compliance_released=true`로 확인. **(v1.2)** 모서리 하강량 제한도 과대 외력과 같은 이중 감시다: 1차 robot_manager(`DROP_LIMIT`), 2차 safety_monitor(래치).

### 7.6 QoS 프로파일 — 제안(TBD) #9 · **(v1.2) 정의 위치는 `contact_scan_interfaces`가 설치하는 Python 모듈 `contact_scan_qos`(계약 v0.1.1)**

| 프로파일 | Reliability | Durability | History | 적용 |
|---|---|---|---|---|
| `SENSOR` | BEST_EFFORT | VOLATILE | KEEP_LAST 5 | `/robot/sample` |
| `STATE` | RELIABLE | TRANSIENT_LOCAL | KEEP_LAST 1 | `/robot/status` · `/scan/state` · `/scan/result` · `/safety/status` |
| `EVENT` | RELIABLE | VOLATILE | KEEP_LAST 50 | `/contact/event` |
| `LOG` | RELIABLE | VOLATILE | KEEP_LAST 100 | `/scan/log` |
| `HEARTBEAT` | BEST_EFFORT | VOLATILE | KEEP_LAST 1 | `/web/heartbeat` |
| Service · Action | 기본(RELIABLE) | — | — | 전부 |

근거: 위험 10(오래된 값·중복). TRANSIENT_LOCAL은 늦게 시작한 노드(mqtt_bridge 재접속 등)가 마지막 상태를 받게 한다. Jazzy 기본 rmw(Fast DDS)에서 실측 후 조정.

---

## 8. 범위 밖 · 외부 인터페이스 (정의하지 않음 · 이름과 방향만)

### 8.1 두산 드라이버 `doosan-robot2` (`dsr_msgs2`) — robot_manager만 호출

실행명 `dsr_controller2` · 네임스페이스 `dsr01` · 모델 `m0609`. 서비스 실제 이름·타입·인자 단위(mm · deg)와 Python 노출 여부는 **[E19] 실PC 확인 필요**(매뉴얼 [E10] · 소스 [E18]과 구분).

| 용도 | DRL/서비스 후보 | 방향 | 확인 수준 |
|---|---|---|---|
| 직선 이동(비동기) | `amovel` | robot_manager → dsr | [E10] · [E19] |
| 순응 제어 | `task_compliance_ctrl` / `release_compliance_ctrl` | → | [E10] · Virtual 미동작 가능 |
| 목표 힘 | `set_desired_force`(DR_FC_MOD_REL) / `release_force` | → | [E10] |
| 정지 | `motion/move_stop`(DR_QSTOP) — Python `stop()` 미노출 [E18] | → | [E18] · [E19] |
| TCP 위치 조회 | `get_current_posx` | → (응답 ←) | [E10] · [E18] |
| 외력 조회 | `get_tool_force` | → (응답 ←) | [E10] · [E18] |
| 위치 조건 | `check_position_condition` | → | [E10] |
| 외력 리셋 | `set_external_force_reset` — Python 미노출 [E18], `drl_script_run` 경유 확인 항목 | → | [E10] · [E18] |
| 로봇 상태 | 드라이버 상태 토픽/서비스(이름 TBD) | ← | [E19] |

### 8.2 OnRobot RG2 드라이버 (`onrobot_driver`) — robot_manager만 호출

| 용도 | 이름 | 방향 | 확인 |
|---|---|---|---|
| 탐침 파지 명령 | `/onrobot/sendCommand`(소스 근거 [E18]) | robot_manager → onrobot_driver | 실제 노드·네임스페이스 [E19]. 폭 변화는 판정에 사용하지 않음 |
| 그리퍼 상태 | `OnRobotRGInput`(폭·상태, [E18]) | ← | 파지 상실 감지 용도 검토(TBD) |

### 8.3 MQTT 토픽 (mqtt_bridge ↔ Mosquitto) — 요약. 상세는 **12장**(토픽 목록 · 명령 공통 필드 · 변환 규칙)

| 방향 | 토픽 | 대응 ROS 인터페이스 |
|---|---|---|
| 수신(구독) | `cmd/scan/start` · `stop` · `home` · `resume` · `set_config` (`cmd/scan/+`) | A1 · S3 · A2 · A3 · S4 |
| 수신(구독) | `cmd/safety/reset` | S5 (결정 #6) |
| 수신 | `hb/web` · `conn/web` | T8(실수신 시에만) · 연결 감시 |
| 발행 | `robot/sample`(10 Hz 다운샘플) · `robot/status` | T1 · T2 |
| 발행 | `scan/state` · `scan/result` · `scan/log` | T4 · T5 · T6 |
| 발행 | `contact/event` · `safety/status` | T3 · T7 |
| 발행 | `cmd/ack`(접수/거절) · `scan/command_result`(홈·재시작·중지 완료) | goal 수락/거절 · Service accepted / Action Result · STOPPED 전이 |
| 발행 | `hb/ros`(1 Hz) · `conn/ros`(LWT) | — |

규칙: 명령 retain=false · request_id 중복/만료 검사 · MQTT 전달 확인 ≠ DB 커밋(4.7).

### 8.4 표준 ROS 인터페이스 (자체 정의 없음)

| 이름 | 방향 | 용도 | 표기 |
|---|---|---|---|
| `rcl_interfaces/srv/SetParameters` (`/robot_manager/set_parameters` · `/contact_detector/set_parameters` · **`/safety_monitor/set_parameters`(v1.2 · P03: `over_force_n` · `drop_limit_m`)**) | scan_manager → robot_manager · contact_detector · safety_monitor | SetConfig 수락 시 파라미터 전파. 두 노드는 파라미터 변경 콜백에서 값 범위를 검증하고 거절할 수 있다(실패 시 `PARAM_SET_FAILED`) | **결정 #16(2026-09-18)** |

---

## 9. 검토안 (MVP 밖 · 점선) — 이름만, 필드 미기재 (제안 #15)

| 이름 | 종류 · 타입 | 방향 | 의미 | 상태 |
|---|---|---|---|---|
| `/scan/calibrate` | Action `Calibrate` | mqtt_bridge → scan_manager (← `cmd/scan/calibrate`) | 기준면 자동 접촉 측정 → 보정·저장·재사용 | 검토안. 환경 세팅 후 좌표계·기준을 정한 뒤 채택 여부·범위 검토(6장). MVP 필수 아님 |
| `/calibration/result` | Topic `CalibrationResult` | scan_manager → mqtt_bridge (→ `scan/calibration/result`) | 캘리브레이션 결과 | 검토안. FastAPI의 `calibration_result` 기준값 이력 저장이 채택을 뜻하지 않음 |

무접촉 힘 영점(`/contact/tare`, 4.1.3)은 이와 별개로 MVP에 포함된다.

---

## 10. 미확정 항목 · 확인 요청 목록

> **T01 회의 결과(2026-09-18)**: 아래 표의 (a) 제안을 **전부 계약 v0.1로 채택**했다(#11만 예외: 실행 패키지는 레포의 노드별 패키지를 유지). #22 · #24와 JSON 스키마는 1차 회의에서 확정했다(12.3). 2차 회의에서 추가로 정한 것은 16장. 수치는 여전히 설계 출발값이며, 계약에 TBD로 남긴 항목은 담당 · 기한 없이 TBD로 둔다.

프롬프트 §7의 15개 + 작성 중 발견 6개 + 팀원 초안 v0.11 고유 3개(#22~#24). 각 항목의 (a) 제안이 이 문서에 "제안(TBD)"로 반영되어 있으며, 답을 받으면 표기를 갱신한다. **결정 이력(2026-09-18): #1 (a) 별도 Action 유지 · #6 (a) `/safety/reset` 신설 · #16 (a) 표준 SetParameters · #17 (a) 이중 경로 유지 · #18 (a) 하위 msg 3개 신설.**

| # | 항목 | 이 문서의 제안(a) | 대안(b) | 근거(c) | 반영 위치 |
|---|---|---|---|---|---|
| 1 | 재시작 인터페이스 | **결정(2026-09-18): (a) 별도 Action `/scan/resume` `Resume` 채택.** Goal `{request_id, scan_id}` 필드는 제안(TBD) 유지 | — | 4.4.8 · TR-08 · 4.4.2 버튼 독립 | 5.3 |
| 2 | ScanLog 필드 | `{stamp, scan_id, level, phase, direction, motion_id, code, message, frame_id, pose, pose_valid}` | 최소형 / `rcl_interfaces/Log` | 4.4.3 · 4.4.7 | 3.6 |
| 3 | SetConfig.config | 구조체 `ScanConfig` + `*_set` 부분 갱신 | key-value 배열 / JSON 문자열 | US-05 · 4.3.4 | 4.4 |
| 4 | ExecuteMotion 세부 | target `Pose`(m·rad) · direction enum · speed m/s · reason enum · Feedback 10 Hz | posx float64[6] / speed % / 50 Hz | 3.5 단위 규칙 · 4.2 | 5.4 |
| 5 | 오류/사유 코드 | 공통 `uint16` 표 `ReasonCode.msg` (1xx~5xx) | 메시지별 enum / string | 4.2.5 · 4.5 · TR-07 | 7.2 |
| 6 | SafetyStatus.level · 래치 해제 | **결정(2026-09-18): (a) Service `/safety/reset` `ResetSafety` 신설**(mqtt_bridge → safety_monitor, MQTT `cmd/safety/reset`, FastAPI `POST /api/safety/reset`, 화면 버튼 "안전 해제"). `level` enum 값 `{OK, WARN, STOP}`은 제안(TBD) 유지 | — | 4.5.3 · 6장 | 3.7 · 4.5 · 1.10 |
| 7 | RobotStatus.error | `bool error` + `uint16 error_code` + `detail`; 정지 완료 = `connected && !moving` | bool만 / code만 | 4.5.1 | 3.2 |
| 8 | ContactEvent.stamps | `pose_stamp` · `force_stamp` · `detect_stamp` 3개 | 2개 / `Time[]` | 4.1.6 · 위험 10 · TR-01 | 3.3 |
| 9 | QoS | 7.6 프로파일(상태는 TRANSIENT_LOCAL) | 전부 RELIABLE·VOLATILE | 위험 10 | 7.6 |
| 10 | 프레임 | 샘플·이벤트·모션 `base_link`, 결과 `workpiece_fixture` | 결과도 base_link | 4.3.3 · 6장 | 7.4 |
| 11 | 패키지·실행명 | `contact_scan`, 노드명 그대로, 네임스페이스 없음 | `/contact_scan/…` | 4.7 | 0.3 |
| 12 | 샘플 주기 · stale | 50 Hz, stale > 100 ms 또는 `valid=false` | 60 ms | 4.1.6 · 위험 1 | 3.1 · 6.2 · 6.3 |
| 13 | ScanResult 유효 항목 | 필드별 `*_valid` bool | 비트마스크 / 이름 목록 | TR-10 | 3.5 |
| 14 | SetConfig 거절 | `{success, reason_code, detail, applied}`; 동작 중 = phase ∉ {IDLE, DONE, ERROR, STOPPED} | success만 | US-05 | 4.4 |
| 15 | 검토안 기재 범위 | 이름·방향·의미만 | 필드까지 | 6장 | 9장 |
| 16 | SetConfig 파라미터 전파(신규) | **결정(2026-09-18): (a) 표준 `rcl_interfaces/srv/SetParameters`** — 자체 인터페이스 신설 없음 | — | 아키텍처 c172 · 정합 #5 | 4.4 · 8.4 |
| 17 | 과대 외력 이중 경로(신규) | **결정(2026-09-18): (a) 둘 다 유지** — 1차 contact_detector(즉시 정지 · 모션 종료 사유), 2차 safety_monitor(독립 감시 · 래치). `over_force_n`은 두 노드에 같은 값 | — | 4.5.3 · 위험 4 | 1.9 · 6.3 |
| 18 | 하위 msg 신설(신규) | **결정(2026-09-18): (a) `ScanConfig` · `Segment` · `ReasonCode` 신설** — 필드 내용은 #3(`ScanConfig`) · #5(`ReasonCode` 값)에서 계속 확인 | — | 4.3.2 · 4.3.3 | 2.4 · 3.5 · 7.2 |
| 19 | HOME 목표 출처(신규) | robot_manager 파라미터 `home_pose`(goal.target 무시) | goal.target에 scan_manager가 실음 | 4.4.9 · 6장 | 5.4 · 6.1 |
| 20 | RunScan Goal/Result(신규) | Goal `{request_id, use_override, config_override}` · Result `{scan_id, success, reason_code, detail, result}` · Feedback `{state}` | Goal 비움 | 아키텍처 c38 · 4.4.2 | 5.1 |
| 21 | 작업 중지 시 goal cancel(신규) | `/robot/stop` 호출 + 진행 중 ExecuteMotion cancel 동시 | `/robot/stop`만 | 4.2.3 | 1.4 · 4.3 |
| 22 | MQTT QoS · timeout · 만료 · 재전송 정책 (v0.11) | 명령·ACK·이벤트 QoS 1 · retain=false · `cmd_expiry_s` 만료 · 상태는 시각 검증 | QoS 0 표시 토픽 / 브로커 persistent session | 아키텍처 c101 · 위험 10 | 12.3 |
| 23 | PostgreSQL ERD/DDL (v0.11) | `scan_result` · `scan_event` · `calibration_result`(FastAPI) / `job` · `workpiece` · `user`(Spring) — 컬럼은 `ScanResult` · `ContactEvent` 필드와 1:1, `*_valid` 컬럼 유지 | JSONB 한 컬럼 | 4.3.4 · TR-10 | 11.2 |
| 24 | 웹 표시 단위 변환 위치 (v0.11) | mqtt_bridge가 JSON 직렬화 시 mm로 변환 + `unit` 필드 | FastAPI에서 변환 | 4.7 데이터 계약 | 12.3 |

BRD 6장의 미결정 사항 중 이 문서가 건드리지 않은 것(홈 복귀 경로·순서 · 중단 위치 재접근 절차 · 이상 상태별 재시작 허용 조건 · 허용 시각 차이 · 브라우저 단절 정책 · 재전송·저장 확인 절차 · 좌표계·z=0·Base 변환·TCP·홈 좌표)은 환경 세팅 후 팀 확인으로 확정한다.

### BRD / 아키텍처에 되돌려 반영할 변경 제안

> **처리 결과(2026-09-19)**: R1 · R2 · R6 · R7은 BRD v3.1.0~v3.2.0에, R3~R7은 아키텍처 **v1.6** 그림에 반영했다. R3은 포트를 합치지 않고 화살표 c370의 끝점만 입력 포트(c145)로 고쳤다. v1.6에는 T01 회의 변경(16장)도 같이 들어갔다.

| # | 대상 | 내용 |
|---|---|---|
| R1 | BRD 4.7 인터페이스 표 | `/robot/sample` 수신을 "판정·감시·브리지"로(scan_manager 제외, 정합 #6) |
| R2 | BRD 4.7 · 아키텍처 쪽지 | `ScanResult`에 `frame_id`(좌표 기준) 필드 추가(4.4.7 요구 반영) |
| R3 | 아키텍처 v1.5 drawio | safety_monitor 카드의 `/robot/status` 입력 포트 2개(c143 · c145)를 1개로 합치고, 화살표 c370의 끝점을 출력 포트 c147에서 입력 포트로 수정 |
| R4 | 아키텍처 v1.5 | SetConfig의 파라미터 전파 경로(scan_manager → robot_manager · contact_detector, 표준 SetParameters)를 화살표로 추가 — **#16 결정됨** |
| R5 | 아키텍처 v1.5 · BRD 4.7 | 하위 메시지 `ScanConfig` · `Segment` · `ReasonCode`를 contact_scan_interfaces 쪽지 msg 목록에 추가 — **#18 결정됨** |
| R6 | 아키텍처 v1.5 · BRD 4.4.2/4.7 | 래치 해제 Service(`/safety/reset`) · MQTT `cmd/safety/reset` · FastAPI `POST /api/safety/reset` · 화면 "안전 해제" 버튼 추가 — **#6 결정됨** (BRD의 "독립 버튼 4개"가 "4개 + 안전 해제"로 늘어나므로 BRD 4.4.2 문구 조정 필요) |
| R7 | 아키텍처 v1.5 | contact_detector ⑤와 safety_monitor ①의 과대 외력 감시가 의도된 이중 경로임을 쪽지에 명시 — **#17 결정됨** |


---

# Part 2 — 웹 연동 계약 (Interface_Draft v0.11에서 통합)

> 11~14장은 팀원 초안 `Interface_Draft v0.11`(기준: 아키텍처 v1.4)의 1·4·5·6장을 가져와 **아키텍처 v1.5 정합 결정과 Part 1(ROS 2 계약)에 맞춰 조정**한 것이다. 조정한 곳은 15장에 목록으로 남겼다. 이 부분은 웹 PC(FastAPI · Spring Boot · PostgreSQL · React)와 메인 PC 사이의 경계이며, JSON 스키마·REST 본문의 세부는 웹 계약에서 확정한다(초안).

## 11. 시스템 연결 구조 · 저장 책임

### 11.1 연결 구조 (초안 · BRD 4.7)

```text
React + Three.js (브라우저)
  ├─ REST ───────────────▶ FastAPI          POST /api/scan/{start·stop·home·resume·set_config}
  ├─ WebSocket ◀────────▶ FastAPI          WS /ws/live (단계·TCP·힘·접촉점·결과·로그 · mm 표시)
  └─ REST ◀─────────────▶ Spring Boot      /mgmt/* (작업 · 대상물 · 이력)

FastAPI (웹 PC)
  ├─ MQTT ◀─────────────▶ Mosquitto Broker  발행 cmd/scan/* · hb/web · conn/web / 구독 robot/# scan/# contact/# safety/# cmd/ack hb/ros conn/ros
  └─ INSERT ─────────────▶ PostgreSQL       scan_result · scan_event · calibration_result

Spring Boot (웹 PC)
  └─ JPA/JDBC ◀─────────▶ PostgreSQL       job · workpiece · user 쓰기 / 측정 테이블 조회만

Mosquitto Broker (웹 PC · 중계만, 판단·저장 안 함)
  └─ MQTT ◀─────────────▶ mqtt_bridge (메인 PC)

mqtt_bridge (메인 PC · ROS 2)
  ├─ Action/Service 호출 ──▶ scan_manager      /scan/run · /scan/home · /scan/resume · /scan/stop · /scan/set_config
  ├─ Service 호출 ────────▶ safety_monitor     /safety/reset (결정 #6)
  ├─ Topic 구독 ◀───────── scan_manager        /scan/state · /scan/result · /scan/log
  │                        robot_manager       /robot/sample · /robot/status
  │                        contact_detector    /contact/event
  │                        safety_monitor      /safety/status
  └─ Topic 발행 ──────────▶ safety_monitor     /web/heartbeat (hb/web 실수신 시에만)
```

명령은 **브라우저 → FastAPI → Broker → mqtt_bridge → scan_manager → robot_manager → 제공 드라이버** 한 방향으로만 흐른다. FastAPI · Spring Boot는 로봇 모션을 직접 제어하지 않는다(BRD 4.7). mqtt_bridge가 robot_manager · contact_detector와 맺는 관계는 **Topic 구독뿐**이고, safety_monitor와는 Topic 구독 + heartbeat 발행 + `/safety/reset` 호출(결정 #6)이다. 그 밖의 Action/Service 호출은 scan_manager에만 한다(3장 · 노드 구성도 연결 표). scan_manager → robot_manager · contact_detector의 설정 전파는 표준 `rcl_interfaces/srv/SetParameters`(결정 #16)로 한다.

### 11.2 저장 책임 (확정 · BRD 4.3.4 · 4.4.7 · TR-10)

| 구성요소 | 역할 | 규칙 |
|---|---|---|
| `scan_manager` / `result_store` (메인 PC) | **원본** · 진행 기록(단계·방향·중단 위치·확정 측정값·설정 스냅샷) · 재시작 기준 데이터 | JSON/CSV. 웹 DB 저장과 구분. 파일 형식·스키마 TBD |
| FastAPI | `scan_result` · `scan_event` · `calibration_result`(기준값 이력) INSERT | `scan_id` / (`scan_id`, `event_id`) 중복 방지. 미측정값을 0으로 저장하지 않음(`*_valid` 반영). 커밋 후 저장 성공 표시 |
| Spring Boot | `job` · `workpiece` · `user` CRUD + 측정 이력 조회(US-02 · US-06) | 측정 테이블은 조회만 |
| PostgreSQL | 웹 영구 저장소 | ERD/DDL TBD (#23) |

> **MQTT 수신·전달 확인과 PostgreSQL 커밋 완료는 별개다.** 저장 성공은 커밋 후에만 표시한다. `calibration_result` 테이블이 있다고 해서 자동 캘리브레이션(검토안)이 채택된 것은 아니다.

## 12. MQTT 인터페이스 (mqtt_bridge ↔ Broker ↔ FastAPI)

토픽 이름은 아키텍처 v1.5 쪽지 "MQTT · 명령 계약" 기준(초안). JSON 스키마(`schema_version` · 필드명 · 단위)는 웹 계약에서 확정한다. 명령 retain=false.

### 12.1 토픽 목록

| 방향 | 토픽 | 발행자 | 내용 | 대응 ROS 2 (Part 1) |
|---|---|---|---|---|
| Web → Main | `cmd/scan/start` | FastAPI | 작업 시작 | `/scan/run` Action goal (5.1) |
| Web → Main | `cmd/scan/stop` | FastAPI | 작업 중지 | `/scan/stop` Service (4.3) |
| Web → Main | `cmd/scan/home` | FastAPI | 안전복귀 | `/scan/home` Action goal (5.2) |
| Web → Main | `cmd/scan/resume` | FastAPI | 재시작 | `/scan/resume` Action goal (5.3 · 결정 #1) |
| Web → Main | `cmd/scan/set_config` | FastAPI | 설정 등록 | `/scan/set_config` Service (4.4) |
| Web → Main | `cmd/safety/reset` | FastAPI | 안전 래치 해제(관제자 확인 후) | `/safety/reset` Service (4.5 · 결정 #6) |
| Web → Main | `hb/web` | FastAPI (1 Hz 설계 목표) | 웹 생존 | `/web/heartbeat` (3.8) — **실수신 시에만** 변환 |
| Web → Main | `conn/web` | FastAPI (LWT) | 연결/단절 보조 | ROS 대응 없음 (safety_monitor HB 만료 판단은 `/web/heartbeat` 기준) |
| Main → Web | `cmd/ack` | mqtt_bridge | **접수/거절** (`request_id` · accepted · reason_code · detail) | Action goal 수락/거절 · Service `accepted`/`success` |
| Main → Web | `scan/command_result` | mqtt_bridge | 명령의 **최종 완료/실패** (**시작(v1.2: 마무리 홈 복귀까지 끝난 시점)** · 홈 · 재시작 · 중지 완료) | `ReturnHome`/`Resume` Result · `ScanState.phase=STOPPED` 전이 |
| Main → Web | `robot/sample` | mqtt_bridge (10 Hz 다운샘플) | TCP·힘 표시용 | `/robot/sample` (3.1) |
| Main → Web | `robot/status` | mqtt_bridge | 연결·동작·오류 | `/robot/status` (3.2) |
| Main → Web | `scan/state` | mqtt_bridge | 단계·방향·진행 n/4 | `/scan/state` (3.4) |
| Main → Web | `scan/result` | mqtt_bridge | 최종 결과 (`scan_id`로 Action Result와 중복 방지) | `/scan/result` (3.5) · `RunScan` Result |
| Main → Web | `scan/log` | mqtt_bridge | 시간순 로그 | `/scan/log` (3.6) |
| Main → Web | `contact/event` | mqtt_bridge (즉시) | 접촉·엣지·과대 외력 | `/contact/event` (3.3) |
| Main → Web | `safety/status` | mqtt_bridge (변경 시) | 안전 상태 · 래치 | `/safety/status` (3.7) |
| Main → Web | `hb/ros` | mqtt_bridge (1 Hz) | 메인 PC 생존 | ROS 대응 없음 |
| Main → Web | `conn/ros` | mqtt_bridge (LWT) | 연결/단절 보조 | ROS 대응 없음 |
| 검토안 | `cmd/scan/calibrate` · `scan/calibration/result` | — | MVP 밖 (9장) | `/scan/calibrate` · `/calibration/result` |

구독 필터: FastAPI는 `robot/#` · `scan/#` · `contact/#` · `safety/#` + `cmd/ack` · `hb/ros` · `conn/ros`, mqtt_bridge는 `cmd/scan/+` · `cmd/safety/reset` · `hb/web` · `conn/web`. 와일드카드 발행 금지.

### 12.2 명령 공통 필드 (초안 · JSON)

| 필드 | 뜻 | 대응 ROS 필드 (7.3 ID 규칙) |
|---|---|---|
| `request_id` | 명령 1건 식별 (UUID, FastAPI 발급) | `request_id` (Goal/Request에 그대로 전달) |
| `scan_id` | 대상 작업 (resume에서 필수, 그 외 선택) | `Resume.Goal.scan_id` |
| `session_id` | 웹 세션 식별. **(v1.2)** 명령에서는 선택(없어도 거절하지 않음), `hb/web`에서만 필수 | `WebHeartbeat.session_id` |
| `timestamp` | 발신 시각 (웹 PC 시계 · 시간 기준 맞춤은 6장 선행조건) | — (mqtt_bridge가 만료 검사에 사용, `cmd_expiry_s`) |
| `payload` | 명령별 본문 (`set_config`는 `ScanConfig` 필드와 같은 키, 단위는 #24) | `SetConfig.Request.config` · `RunScan.Goal.config_override` |

규칙 — `cmd/ack`는 접수/거절이며 동작 완료가 아니다. 완료는 `scan/result` 또는 `scan/command_result`. 중복(`request_id` 재사용)·만료(`timestamp` + `cmd_expiry_s`) 명령은 mqtt_bridge가 거절하고 `cmd/ack`에 `DUPLICATE_REQUEST`/`INVALID_REQUEST`(7.2)를 실어 응답한다. 응답 대기 timeout은 FastAPI가 "미확정"으로 표시한다(아키텍처 c78).

**(v1.2 · PR #47 리뷰 반영)** `cmd/scan/stop`은 만료 검사에서 제외한다(중복 · 필수 필드 검사는 한다). 중지는 멱등이고, 두 PC의 시계가 어긋나 있어도 중지가 거절되면 안 된다. `cmd/scan/home` · `cmd/safety/reset`을 포함한 나머지 명령은 만료 검사를 한다. 명령의 필수 필드는 `schema_version` · `request_id` · `timestamp_ms` · `payload`, `hb/web`은 `schema_version` · `session_id` · `seq` · `timestamp_ms`, `conn/web`은 `schema_version` · `connected` · `timestamp_ms`다. 발신 시각 키는 `timestamp_ms`다(위 표의 `timestamp`는 v1.1 표기).

### 12.3 데이터 변환 규칙 (mqtt_bridge)

- ROS → JSON: `schema_version` · ID · 취득 시각(`*_stamp`, 각각 보존) · 단위 표기를 포함한다. 결과·이벤트는 손실 없이 전달한다.
- `robot/sample`은 표시용 10 Hz 다운샘플(설계 목표), ROS 측정 루프(50 Hz)에 영향을 주지 않는다.
- **(v1.2 · T01 1차 회의 확정)** 상세와 토픽별 JSON 예시는 `docs/contracts/mqtt-schema.md` v0.1.
  - 구조: ROS 메시지와 같은 이름 · 같은 구조로 1:1. 길이 · 힘 키에는 단위 접미사(`x_mm` · `fz_n` · `z_drop_mm`). `unit` 필드는 두지 않는다. 변환은 mqtt_bridge에서만(#24 종결).
  - enum은 문자열 이름, 사유는 `reason_code` + `reason` 병기(다른 코드 필드는 `error_code` + `error_name`, `code` + `code_name`), 모든 메시지에 `schema_version: "0.1"`.
  - 시각: epoch ms 정수(UTC). `*_stamp_ms` 각각 보존 + mqtt_bridge의 `published_at_ms`. 명령 발신 시각은 `timestamp_ms`.
  - 각도 값은 싣지 않는다. 자세는 quaternion. deg 변환은 웹이 시각화할 때 한다.
  - 미측정값: `null` + `*_valid` 키 항상 유지.
  - QoS(#22 종결): 명령 · `cmd/ack` · `scan/command_result` · `contact/event` · `scan/result` · `scan/log` = 1, `robot/sample` · `hb/*` = 0. retain=true는 상태 3종(`scan/state` · `robot/status` · `safety/status`)과 `conn/*`만, 명령은 전부 false. `topic_prefix` 기본값 `""`은 웹 쪽의 전제다. 중복 기억 개수 · `cmd_expiry_s`는 mqtt_bridge 파라미터(출발값 100개 · 5 s).
  - 웹 PC ↔ 메인 PC 시계 동기는 chrony(의석 담당).

## 13. Web API 경계 (범위 밖 · 이름과 책임만)

### 13.1 FastAPI — 실시간 제어 · 데이터 (Python 3.12 asyncio · uvicorn)

```text
POST /api/scan/start         → cmd/scan/start        응답: request_id + 접수/거절 (완료는 WS)
POST /api/scan/stop          → cmd/scan/stop
POST /api/scan/home          → cmd/scan/home
POST /api/scan/resume        → cmd/scan/resume       (body: scan_id)
POST /api/scan/set_config    → cmd/scan/set_config   (body: ScanConfig 키와 동일)
POST /api/safety/reset       → cmd/safety/reset      (결정 #6 · 응답: 접수/거절, 결과는 safety/status)
WS   /ws/live                ← 최신 상태 + 이벤트 (단계 · TCP · 힘 · 접촉점 · 결과 · 로그 · mm)
```

책임: REST 명령 → MQTT 변환(request_id 발급 · 입력 검증) · MQTT 상태/이벤트 → WebSocket(느린 클라이언트 큐 제한 · 화면 반영 200 ms KPI) · 측정·이벤트·기준값 이력 DB 쓰기 · `hb/web` 발행 · `hb/ros` 만료 감시. 로봇 모션은 직접 제어하지 않는다.

### 13.2 Spring Boot — 업무 · 이력 (Java 21 · Spring Boot 3)

```text
POST /mgmt/jobs · GET /mgmt/jobs
POST /mgmt/workpieces · GET /mgmt/workpieces
GET  /mgmt/history                      (날짜 · 대상물 · 성공/실패 필터 · 탐색/셋업 시간 · US-06)
```

책임: 작업 · 대상물 · 사용자 관리, 측정 이력 조회. 로봇 제어 경로에 참여하지 않는다.

### 13.3 React + Three.js — 관제 화면 (BRD 4.4)

독립 버튼 4개(작업 시작 · 작업 중지 · 안전복귀 · 재시작) + 설정 등록 + **안전 해제(결정 #6 · 래치 걸린 상태에서만 활성)** → FastAPI. 접수/거절(`cmd/ack`)과 완료/실패(`scan/result` · `scan/command_result`)를 구분 표시. 단계 표시는 `ScanState.phase`(7.1) ↔ BRD 4.4.4 단계명 매핑을 따른다.

## 14. 공통 규칙 (두 초안 공통 · 확정)

| # | 규칙 | 근거 | Part 1 위치 |
|---|---|---|---|
| 1 | 작업 중지 · 안전복귀 · 재시작은 **서로 다른 명령**이다. 중지는 홈 복귀·재시작을 자동 실행하지 않는다 | BRD 4.4.2 · 4.5.1 | 1.4 · 1.5 · 1.6 |
| 2 | 요청 **접수**(`accepted` · `cmd/ack`)와 실제 **정지 완료**를 구분한다. 완료는 `/robot/status.moving=false`로 확인한다 | BRD 4.5.1 · 4.2.3 | 7.5 |
| 3 | 재시작은 새 스캔이 아니다. 기존 측정값·진행 기록을 유지하고 중단 방향부터 잇는다(`scan_id` 유지) | BRD 4.4.8 · TR-08 | 5.3 |
| 4 | TCP와 힘이 같은 `RobotSample`에 있어도 `pose_stamp` · `force_stamp`를 각각 보존하고 동시 취득으로 간주하지 않는다 | BRD 4.1.6 | 3.1 · 7.4 |
| 5 | 실패·미측정값을 정상값 0으로 저장하지 않는다(`*_valid` 플래그) — ROS · MQTT · DB 모두 | BRD TR-10 · 4.4.7 | 3.5 · 11.2 |
| 6 | safety_monitor의 로컬 정지는 웹/MQTT를 거치지 않고 `/robot/stop`을 직접 요청한다. 걸린 래치는 관제자의 `/safety/reset`(웹 경유)으로만 풀린다 | BRD 4.5.3 · 6장 | 1.7 · 1.10 · 4.1 · 4.5 |
| 7 | 자동 캘리브레이션 Action은 MVP 필수 인터페이스에서 제외한다(검토안) | BRD 6장 | 9장 |
| 8 | 제공 드라이버 · MQTT · REST의 실제 이름·타입은 이 문서가 정의하지 않는다. [E18]/[E19]·웹 계약에서 확정 | BRD 6장 제약 | 8장 · 12장 · 13장 |

---

# Part 3 — 통합 이력

## 15. Interface_Draft v0.11 대비 조정 목록

팀원 초안(아키텍처 **v1.4** 기준)을 v1.5 정합 결정(아키텍처 쪽지 ⑨ · 2026-09-18)과 이 문서 Part 1에 맞춰 바꾼 곳이다. 이름·방향이 같은 인터페이스 16개는 그대로다.

| # | 항목 | v0.11 | 통합본 | 이유 |
|---|---|---|---|---|
| 1 | 기준 아키텍처 | v1.4 | v1.5 | 카드 간 필드 정합 반영 |
| 2 | `RobotSample` 프레임 필드 | `frame` | `frame_id` | 정합 #4 · ROS 관례(`std_msgs/Header.frame_id`) |
| 3 | `ScanState` 진행 | `completed_edges` · `total_edges` | `progress` · `progress_total` | 정합 #1 "progress(n/4)" |
| 4 | `ExecuteMotion` Goal | `scan_id` · `motion_id` 없음 | 포함. Result에 정지 pose · 종료 사유 | 정합 #2 · #6 (중단 위치 출처) |
| 5 | `ContactEvent` 시각 | `pose_stamp` · `force_stamp` | + `detect_stamp` (제안 #8) | 판정 지연 실측(TR-01) |
| 6 | `ScanResult` 유효성 | `valid` 1개 | 필드별 `*_valid` (제안 #13) + `frame_id` | TR-10 · BRD 4.4.7 좌표 기준 |
| 7 | `TareForce` Request | 없음 | `duration_s` · `scan_id` (제안) | 4.1.3 구간 지정 · 로그 대응 |
| 8 | `SetConfig` Response | `success` | + `reason_code` · `detail` · `applied` (제안 #14) | 거절 사유 표시(US-05) |
| 9 | `RobotStatus` | 3필드 | + `stamp` · `error_code` · `compliance_active` · `detail` (제안 #7) | 4.5.2 해제 확인 · 최신성 |
| 10 | `StopScan`/`StopRobot` Response | `accepted` | + `reason_code` · `detail` (제안) | 거절 사유 |
| 11 | `ScanLog` | 세부 TBD | 필드 제안(#2) | 4.4.3 |
| 12 | 하위 msg | 없음 | `ScanConfig` · `Segment` · `ReasonCode` (결정 #18) | 구조체 표현 |
| 13 | 연결 구조의 mqtt_bridge ↔ 노드 관계 | "ROS 2 ↔ 4개 노드"로 뭉뚱그림 | Action/Service는 scan_manager만, 나머지는 Topic 구독(+heartbeat 발행) | 노드 구성도 연결 표와 일치 |
| 14 | MQTT 매핑표 | 12행 | + `cmd/ack` · `scan/command_result` · `hb/web`→`/web/heartbeat` · 검토안 | 접수/완료 경로 명시 |
| 15 | 미확정 목록 | 9개(이름만) | Part 1 10장 21개 + v0.11 고유 3개(#22~#24) 병합, 제안·대안·근거 첨부 | — |
| 16 | 자료형 · enum · 코드 · QoS · 파라미터 | 전부 TBD | Part 1에서 제안(TBD)로 채움 | 구현 계약용 |
| 17 | 래치 해제 · 설정 전파 · 과대 외력 이중 경로 | 언급 없음 | `/safety/reset` 신설(#6) · 표준 SetParameters(#16) · 이중 경로 유지(#17) — 2026-09-18 결정 | 비어 있던 자리 |

v0.11에서 그대로 가져온 것: 11.1 연결 구조(조정 #13 제외) · 11.2 저장 책임 · 12.1 토픽 이름 · 12.2 명령 공통 필드 · 13장 REST/WS 경로 · 14장 공통 규칙 1~7.

## 16. v1.1 → v1.2 변경 목록 (T01 계약 동결 회의 · 2026-09-18)

계약의 기준은 `docs/contracts/` v0.1이다. 아래는 그 결정을 이 문서에 되돌려 반영한 곳이다.

| # | 항목 | v1.1 | v1.2 | 이유 | 위치 |
|---|---|---|---|---|---|
| 1 | 모션 맥락 | contact_detector가 `/scan/state`의 phase · motion_id로 판정 모드와 태깅 값을 얻음 | `RobotSample` · `RobotStatus`에 `motion_id` · `operation` 추가. robot_manager가 직접 찍고 contact_detector는 샘플에서 얻음 | `EDGE_SEARCH` 안에 SLIDE와 복귀 이동이 섞여 있어 복귀 중 거짓 접촉을 막을 수 없음. goal 직후 이벤트가 옛 motion_id로 태깅되면 불일치로 무시되어 정지하지 않음 | 1.2 · 3.1~3.4 |
| 2 | `OP_*` 번호 | MOVE_TO=0 … HOME=3 | NONE=0 · MOVE_TO=1 · DESCEND=2 · SLIDE=3 · HOME=4. MOVE_TO · HOME 중에는 CONTACT/EDGE로 정지하지 않음 | 0을 "없음"으로 통일 | 5.4 · 7.1 |
| 3 | 제어 플래그 | `compliance_active` 1개 | `compliance_active` + `force_ctrl_active` | 켜고 끄는 호출이 따로라 해제를 각각 검증 | 3.2 · 7.5 |
| 4 | HOME 용도 · 마무리 | HOME은 안전복귀 전용. 4/4 뒤 결과 발행으로 종료 | 정상 완료 시 GEOMETRY(계산 · 저장 · 결과 발행) → HOMING → DONE. `finished_at` = GEOMETRY 종료. 실패 · 중단 · 형상 실패 시 자동 복귀 없음 | 팀 결정. 결과는 복귀를 기다리지 않고 먼저 전달 | 1.3 · 3.4 · 3.5 · 5.4 |
| 5 | 방향 전환 | "원점 복귀 · 팁 들어 올림"만 기재 | MOVE_TO 연속: 올림(`lift_height_m` 0.05) → 수평 이동 → 첫 접촉 z + `recontact_margin_m`(0.001)까지 저속 내림 → SLIDE. 재하강 판정 없음 | 접촉 높이에 딱 맞춘 복귀는 충돌 우려 | 1.3 · 6.4 |
| 6 | 하강 제한 | robot_manager 단독 | 이중 감시(1차 robot_manager · 2차 safety_monitor 래치, 같은 값). 전파 경로 P03 신설(`over_force_n` · `drop_limit_m`) | 결정 #17과 같은 구조. v1.1은 safety_monitor `over_force_n`이 ★인데 전파 경로가 없었음 | 6.3 · 7.5 · 8.4 |
| 7 | 추가 필드 | — | `ContactEvent.source` · `debounce_count` / `TareForce` `baseline_norm_n` · `std_norm_n` / `StopRobot` · `StopScan` `requester` / `SafetyStatus` `motion_id` · `position` · `position_valid` · `stop_confirmed` | 현지 요청. 추가만 하는 변경 | 3.3 · 3.7 · 4.1~4.3 |
| 8 | ReasonCode | 30개 | +`TARE_UNSTABLE=305` · `TARE_TIMEOUT=306` · `NO_SAMPLE=307`. 번호는 추가만 | tare 실패 세분. `NO_SAMPLE`은 v1.1이 이름만 쓰고 번호가 없었음 | 7.2 |
| 9 | 무효 값 | `*_valid` 플래그(값은 미지정, `z_drop_m`은 0) | `NaN` + `*_valid=false`. MQTT `null`, Python `None` | 0 금지 규칙과의 모순 제거 | 0.3 · 3.3 · 3.5 |
| 10 | 순서 규약 | "0~3 윗면, 4~7 지지면"까지 | 꼭짓점 (x⁻,y⁻)부터 반시계, 엣지 · 경로 후보 순서, 치수 이름 | 계산 · 메시지 · 3D 표시의 순서 통일 | 3.5 |
| 11 | 프레임 · TCP | 프레임 배정은 제안, TCP · 힘 기준 없음 | 샘플은 계속 Base, 결과만 scan_manager가 변환(가이드 평행 설치 조건). TCP = 팁 최하단점, 자세 수직 고정, 힘 `DR_BASE` | T02 · T03 전에 기준 확정 | 7.4 |
| 12 | 패키지 | 단일 `contact_scan` 제안 | 레포의 노드별 패키지 | 레포가 이미 그렇게 구성됨 | 0.3 |
| 13 | MQTT · 웹 경계 | #22 · #24 · JSON 스키마 TBD | 1차 회의로 확정(12.3). 시작 명령의 완료도 `scan/command_result` | — | 12.1 · 12.3 |

| 14 | PR #47 리뷰 반영 | — | `cmd/scan/stop` 만료 검사 제외 · 필수 필드(`session_id`는 명령에서 선택) · `error_code`+`error_name` · retain 상태 3종 · 하강 제한 1차 기준 z = 2차와 같음 · QoS 정의 위치 `contact_scan_qos` | 리뷰(현지 · 학민 · 의석) | 6.3 · 7.6 · 12.2 · 12.3 |

계약에 TBD로 추가된 것: 순응 · 힘 제어 해제 실패 시 보고, `move_stop` → 해제 순서의 실기 확인. 후속 이슈: #51~#55.

재시작: 홈 안전복귀를 거친 뒤의 재접근 절차는 여전히 TBD이며, 확정 전까지 그 경우는 `NOT_SUPPORTED`로 거절한다(5.3, v1.1 제안을 채택).

