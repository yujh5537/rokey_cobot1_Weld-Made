근거: `docs/contracts/ros-interfaces.md` · `docs/contracts/mqtt-schema.md`(1차, CHANGELOG 최신 v0.1.20) · `docs/phase2/weld-ros-interfaces.md` · `docs/phase2/weld-mqtt-schema.md`(v0.2.0 · phase 2) · `ws_cobot1/src/contact_scan_interfaces/` (origin/main `7286e8e`, 2026-09-28)

# 05. 토픽 · 서비스 · 액션 인터페이스 정의서 (요약본)

작성: 병후 · 2026-09-27. **원본은 위 네 계약 문서다. 이 문서와 원본이 다르면 원본이 맞다.** 필드 전문 · QoS · 동작 규칙은 원본에 있고, 여기에는 한눈에 볼 표와 대표 메시지 3 개만 옮겼다. 노드 사이의 선은 [06 노드 구조도](06-node-graph.md).

- 타입 패키지: `contact_scan_interfaces`(msg 15 · srv 6 · action 6). `.msg` · `.srv` · `.action` 파일은 계약 문서의 타입 전문을 그대로 옮긴 것이고, 둘이 어긋나면 `test/test_contract_sync.py` 가 CI 에서 실패한다.
- 공통 규칙: ROS 내부 단위는 m · rad · N, 웹 표시는 mm(변환은 mqtt_bridge 에서만). **미측정값은 0 이 아니라 NaN + `*_valid=false`**(MQTT 에서는 `null`). 좌표는 `frame_id` 로 기준을 밝힌다.
- **phase 2(용접)** 행은 **[P2]** 로 표시했다. 계약은 main 에 있고 구현은 PR 진행 중이다(2026-09-28).
- v0.1.21(#161, 9/27 머지): scan_manager 가 `/robot/sample` 을 구독하고, `ReasonCode` 에 407 `STOP_UNCONFIRMED`, `RobotStatus` 에 SLIDE 누름 목표 필드가 더해졌다. v0.1.22(#200): MQTT 이름 표에 없는 값은 버리지 않고 `"UNKNOWN_<값>"` 으로 보낸다(`robot/sample.operation` 5 = `"WELD_PATH"`).

## 1. 토픽
| 이름 | 타입 | 발행 | 구독 | QoS | 뜻 |
|---|---|---|---|---|---|
| `/robot/sample` | RobotSample | robot_manager | contact_detector · safety_monitor · mqtt_bridge · scan_manager(v0.1.21) · [P2] weld_manager | SENSOR | TCP pose + 외력 + 실행 중 동작(`motion_id` · `operation`). scan_manager 는 **마지막 유효 pose 만** 들고 안전복귀의 올림 목표 · 재시작의 위치 확인에 쓴다(측정값은 여전히 판정 좌표) |
| `/robot/status` | RobotStatus | robot_manager | scan_manager · safety_monitor · mqtt_bridge · [P2] weld_manager | STATE | 연결 · 동작 · 오류 · 제어 상태. 정지 완료 확인의 근거 |
| `/contact/event` | ContactEvent | contact_detector · robot_manager(스텝 모드 EDGE) | robot_manager · scan_manager · mqtt_bridge | EVENT | CONTACT · EDGE · OVER_FORCE. 판정 확정 즉시 1 회 |
| `/scan/state` | ScanState | scan_manager | contact_detector · safety_monitor* · mqtt_bridge · [P2] weld_manager | STATE | 단계 · 방향 · 진행 n/4 |
| `/scan/result` | ScanResult | scan_manager | mqtt_bridge | STATE | 형상 결과. 작업 종료 시 1 회(실패 · 중단 포함) |
| `/scan/log` | ScanLog | scan_manager | mqtt_bridge | LOG | 시간순 로그 |
| `/safety/status` | SafetyStatus | safety_monitor | scan_manager · mqtt_bridge · [P2] weld_manager | STATE | 안전 상태 · 래치 |
| `/web/heartbeat` | WebHeartbeat | mqtt_bridge | safety_monitor* | HEARTBEAT | MQTT `hb/web` 을 실제로 받았을 때만 전달 |
| `/dsr01/joint_states` | sensor_msgs/JointState | 두산 드라이버 | mqtt_bridge | SENSOR | **표시 전용** 관절값. 제어 입력으로 쓰지 않는다 |
| [P2] `/weld/state` | WeldState | weld_manager | scan_manager · mqtt_bridge | STATE | 단계 · 선 번호 · 진행 |
| [P2] `/weld/result` | WeldResult | weld_manager | mqtt_bridge | STATE | 용접 결과(8 선 계획 · 상태) |
| [P2] `/weld/log` | ScanLog | weld_manager | mqtt_bridge | LOG | 시간순 로그(`scan_id` 자리에 `weld_id`) |

\* 계약에는 있지만 2026-09-28 main 의 safety_monitor 는 이 두 토픽을 구독하지 않는다(웹 heartbeat 감시 · `HB_EXPIRED` 405 미구현, `integration-audit_20260921.md` T33). mqtt_bridge 는 `/web/heartbeat` 를 발행한다.

QoS 프로파일(`contact_scan_qos` 모듈, 발행 · 구독 양쪽이 같은 정의를 import): SENSOR = BEST_EFFORT · VOLATILE · KEEP_LAST 5 / STATE = RELIABLE · TRANSIENT_LOCAL · KEEP_LAST 1 / EVENT = RELIABLE · VOLATILE · KEEP_LAST 50 / LOG = RELIABLE · VOLATILE · KEEP_LAST 100 / HEARTBEAT = BEST_EFFORT · VOLATILE · KEEP_LAST 1.

## 2. 서비스
| 이름 | 타입 | 서버 | 클라이언트 | 뜻 |
|---|---|---|---|---|
| `/robot/stop` | StopRobot | robot_manager | scan_manager · safety_monitor · [P2] weld_manager | 로봇 정지 요청. `requester` 로 누가 불렀는지 남긴다. 접수 ≠ 정지 완료 |
| `/contact/tare` | TareForce | contact_detector | scan_manager | 외력 기준값 F₀(무접촉 · 정지) |
| `/scan/stop` | StopScan | scan_manager | mqtt_bridge | 작업 중지. 홈 복귀 · 재시작을 부르지 않는다 |
| `/scan/set_config` | SetConfig | scan_manager | mqtt_bridge | 설정 등록. 동작 중이면 거절. 수락하면 아래 표준 서비스로 다른 노드에 전파 |
| `/safety/reset` | ResetSafety | safety_monitor | mqtt_bridge | 안전 래치 해제. 조건이 사라졌을 때만 성공. 로봇을 움직이지 않는다 |
| `/<node>/set_parameters` | rcl_interfaces/SetParameters | robot_manager · contact_detector · safety_monitor | scan_manager | SetConfig 전파(P01~P03) |
| [P2] `/weld/stop` | StopWeld | weld_manager | mqtt_bridge | 용접 중지 |

## 3. 액션
| 이름 | 타입 | 서버 | 클라이언트 | 뜻 |
|---|---|---|---|---|
| `/scan/run` | RunScan | scan_manager | mqtt_bridge | 새 작업 시작 |
| `/scan/home` | ReturnHome | scan_manager | mqtt_bridge | 안전복귀 = 홈(시작 위치) |
| `/scan/resume` | Resume | scan_manager | mqtt_bridge | 재시작(별도 Action). 확정 측정값을 유지하고 중단 방향부터 |
| `/robot/execute_motion` | ExecuteMotion | robot_manager | scan_manager · [P2] weld_manager | 단위 모션 1 개(`OP_MOVE_TO` · `OP_DESCEND` · `OP_SLIDE` · `OP_HOME`). Result = 정지 pose + 종료 사유 |
| [P2] `/weld/run` | RunWeld | weld_manager | mqtt_bridge | 용접 시작(`scan_id` "" = 최신 · `start_line` · `end_line`) |
| [P2] `/weld/home` | ReturnHome | weld_manager | mqtt_bridge | 용접의 안전복귀(1차 타입 재사용) |
| [P2] `/robot/execute_path` | ExecutePath | robot_manager | weld_manager | 경유점을 차례로 지나는 직선 이동(위빙 지그재그). 접촉 판정 · 힘 제어 없음 |

## 4. MQTT (웹 PC 브로커 ↔ mqtt_bridge)
길이 mm · 시각 epoch ms · enum 은 문자열 이름 · 사유는 `reason_code` + `reason` 을 함께 · 미측정값은 `null` + `*_valid` 유지. 명령은 모두 retain=false.

| 방향 | 토픽 | QoS | retain | 대응 ROS |
|---|---|---|---|---|
| 웹 → ROS | `cmd/scan/start` · `stop` · `home` · `resume` · `set_config` | 1 | false | `/scan/run` · `/scan/stop` · `/scan/home` · `/scan/resume` · `/scan/set_config` |
| 웹 → ROS | `cmd/safety/reset` | 1 | false | `/safety/reset` |
| 웹 → ROS | `hb/web` (1 Hz) · `conn/web`(LWT, retain) | 0 · 1 | false · true | `/web/heartbeat` · — |
| ROS → 웹 | `cmd/ack` | 1 | false | goal 수락/거절 · 서비스 응답 (**접수**) |
| ROS → 웹 | `scan/command_result` | 1 | false | Action Result · STOPPED 전이 (**완료/실패**) |
| ROS → 웹 | `robot/sample`(10 Hz) · `robot/joints` · `robot/gripper_joints`(20 Hz) | 0 | false | `/robot/sample` · `/dsr01/joint_states` |
| ROS → 웹 | `robot/status` · `scan/state` · `safety/status` | 1 | **true** | 같은 이름의 ROS 토픽 |
| ROS → 웹 | `scan/result` · `scan/log` · `contact/event` | 1 | false | 같은 이름의 ROS 토픽 |
| ROS → 웹 | `hb/ros`(1 Hz) · `conn/ros`(LWT, retain) | 0 · 1 | false · true | — |
| [P2] 웹 → ROS | `cmd/weld/start` · `stop` · `home` | 1 | false | `/weld/run` · `/weld/stop` · `/weld/home` |
| [P2] ROS → 웹 | `weld/state`(retain) · `weld/result` · `weld/log` · `weld/command_result` | 1 | true · false | `/weld/*` |

- 웹 명령에는 `schema_version` · `request_id`(UUID v4) · `timestamp_ms` · `payload` 가 필수다. mqtt_bridge 가 `request_id` 중복과 만료를 거절한다(**중지는 만료 검사에서 뺀다**). `schema_version` 은 스캔 토픽 "0.1", 용접 토픽 "0.2"(토픽별).

## 5. 사유 코드 (ReasonCode.msg, 범위만)
| 범위 | 뜻 | 예 |
|---|---|---|
| 0 | 정상 | `OK` |
| 1xx | 요청 거절 | 100 `BUSY` · 103 `SAFETY_LATCHED` · 104 `ROBOT_DISCONNECTED` · 105 `NO_RESUMABLE_SCAN` · 108 `PARAM_SET_FAILED` |
| 2xx | 동작 종료 | 200 `STOP_REQUESTED` · 202 `MAX_DISTANCE` · 203 `TIMEOUT` · 204 `ROBOT_ERROR` · 205 `DROP_LIMIT` |
| 3xx | 접촉 · 툴 | 300 `NO_CONTACT` · 301 `NO_EDGE` · 302 `TOOL_REG_SUSPECT` · 303~307 tare · 샘플 |
| 4xx | 안전 | 400 `OVER_FORCE` · 403 `SAMPLE_STALE` · 404 `ROBOT_STATUS_LOST` · 405 `HB_EXPIRED`(감시 미구현) · 406 `CONDITION_ACTIVE` · 407 `STOP_UNCONFIRMED`(v0.1.21) |
| 5xx | 형상 | 500 `INVALID_SHAPE` · 501 `INSUFFICIENT_POINTS` |
| [P2] 6xx | 용접 | 600 `SCAN_ACTIVE` · 601 `WELD_ACTIVE` · 602 `NO_SCAN_RESULT` · 603 `LINE_OUT_OF_RANGE` · 604 `PATH_REJECTED` |

전체 표는 `ros-interfaces.md` 6.1절. 번호는 추가만 하고 바꾸지 않는다.

## 6. 대표 메시지 3 개 (전문)

### 6.1 ContactEvent.msg — 접촉 판정 (`/contact/event`)
판정 좌표(조건이 처음 성립한 샘플)와 정지 완료 좌표를 구분한다. scan_manager 는 이 `pose` 를 측정값으로 쓴다.
```
uint8 TYPE_CONTACT=0        # 접촉 발생 확정
uint8 TYPE_EDGE=1           # 접촉 소실 확정 = BRD 의 "엣지"
uint8 TYPE_OVER_FORCE=2     # 과대 외력

uint64 event_id             # contact_detector 발급, 발행마다 +1
string scan_id              # /scan/state 에서 받은 현재 scan_id. 없으면 ""
uint32 motion_id            # 판정에 쓴 RobotSample.motion_id 를 그대로 복사
uint64 sample_id            # 판정 샘플(= 조건이 처음 성립한 샘플)의 RobotSample.sample_id
uint8 type
string source               # 'robot_force' | 'sim' | 'robot_step' (robot_manager 스텝 모드 SLIDE 의 EDGE, v0.1.15)
string frame_id             # RobotSample 과 동일
geometry_msgs/Pose pose     # 판정 샘플의 TCP pose (≠ 확정 샘플, ≠ 정지 완료 좌표)
geometry_msgs/Wrench wrench # 판정 샘플의 외력
builtin_interfaces/Time pose_stamp     # 판정 샘플의 값
builtin_interfaces/Time force_stamp    # 판정 샘플의 값
builtin_interfaces/Time detect_stamp   # 판정을 확정한 시각 (확정 샘플. 연속 N 번째)
float64 force_delta_n       # 확정 샘플의 |F − F0|. OVER_FORCE 는 원시 |F|
float64 z_drop_m            # EDGE 판정 샘플의 실제 z 하강량. 그 외 type 은 NaN
bool z_drop_valid
uint8 debounce_count        # 판정을 확정한 연속 횟수
```

### 6.2 ScanResult.msg · Segment.msg — 형상 결과 (`/scan/result`)
윗면 1 점 + 모서리 4 점 → 편향 보정 → 직육면체. 외곽 엣지 · 경로 후보 4 개는 **용접 이음 판정이 아니다.**
```
# ScanResult.msg — 미측정값은 NaN + *_valid=false (0 금지)
string scan_id
builtin_interfaces/Time stamp
bool success
uint16 reason_code          # ReasonCode. 성공 = 0
string detail
string frame_id             # 아래 좌표의 기준 ('workpiece_fixture' 가칭)

float64 z_top               # 윗면 높이 (편향 보정 후)
bool z_top_valid
float64 x_pos
bool x_pos_valid
float64 x_neg
bool x_neg_valid
float64 y_pos
bool y_pos_valid
float64 y_neg
bool y_neg_valid

float64 width               # x_pos - x_neg
float64 length              # y_pos - y_neg
float64 height              # z_top - support_z
bool dims_valid
float64 support_z
bool support_z_valid

geometry_msgs/Point[8] vertices
bool box_valid              # vertices · edges · path_candidates 유효
Segment[12] edges
Segment[4] path_candidates  # 윗면 네 변 = 외곽 엣지·경로 후보 (용접 이음 판정 아님)

ScanConfig config           # 적용 설정 스냅샷
builtin_interfaces/Time started_at
builtin_interfaces/Time finished_at   # 형상 생성(GEOMETRY)이 끝난 시각. 마무리 홈 복귀 시간은 포함하지 않는다
```
```
# Segment.msg
geometry_msgs/Point start   # m
geometry_msgs/Point end     # m
float64 length              # m
bool valid
```

### 6.3 [P2] WeldLine.msg — 용접선 1 개의 계획과 결과 (`WeldResult.lines[8]`)
한 선이 실패하면 그 선만 FAILED 로 남기고 다음 선으로 간다(D33, z_safe 위에서 난 `ROBOT_ERROR` 만).
```
# WeldLine.msg — 용접선 1개의 계획과 결과 (phase 2)
uint8 STATUS_NOT_ATTEMPTED=0   # 아직 안 함
uint8 STATUS_DONE=1            # 끝까지 지나감
uint8 STATUS_FAILED=2          # 실패 (reason_code)
uint8 STATUS_STOPPED=3         # 중지로 중단
uint8 STATUS_SKIPPED=4         # start_line 앞이라 건너뜀
uint8 index                    # 0~7 (weld-motion.md 의 표)
Segment seam                   # 이음선 = 부재 모서리 (작업대 좌표, m). 세로선은 bottom_margin 만큼 짧다
uint8 status
uint16 reason_code             # ReasonCode. 성공 = 0
string detail
geometry_msgs/Pose stop_pose   # FAILED · STOPPED 일 때 멈춘 자리 (frame_id 는 WeldResult.frame_id)
bool stop_pose_valid
builtin_interfaces/Time started_at
builtin_interfaces/Time finished_at
```

## 7. 원본 문서
| 무엇 | 문서 |
|---|---|
| ROS 타입 전문 · QoS · ID · 동작 규칙(세 정지 경로 · 이중 감시 · 방향 전환 · 마무리 순서) | [`docs/contracts/ros-interfaces.md`](../contracts/ros-interfaces.md) |
| MQTT 토픽 · JSON 예시 · 명령 처리 규칙 | [`docs/contracts/mqtt-schema.md`](../contracts/mqtt-schema.md) |
| 좌표계 · TCP · 홈 · 단위 | [`docs/contracts/units-frames.md`](../contracts/units-frames.md) |
| [P2] 용접 ROS 인터페이스 · 배타 규칙 | [`docs/phase2/weld-ros-interfaces.md`](../phase2/weld-ros-interfaces.md) |
| [P2] 용접 MQTT · 웹 표시 | [`docs/phase2/weld-mqtt-schema.md`](../phase2/weld-mqtt-schema.md) |
| [P2] 8 선 · 자세 · 스탠드오프 · 위빙 · 파라미터 | [`docs/phase2/weld-motion.md`](../phase2/weld-motion.md) |
| 변경 이력 | [`docs/contracts/CHANGELOG.md`](../contracts/CHANGELOG.md) |
