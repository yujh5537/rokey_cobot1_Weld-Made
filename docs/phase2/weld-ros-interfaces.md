# ROS 인터페이스 (phase 2, 용접)

상태: **v0.2.0 초안** (2026-09-23, 병후). 1차 계약 `docs/contracts/ros-interfaces.md` 위에 **더하는** 문서다. 공통 규칙(1장) · ID(6.2) · QoS(6.3) · 세 정지 경로(7.1)는 1차와 같다.
**타입 전문(3~5장)은 `contact_scan_interfaces` 의 파일과 같아야 한다.** `test_contract_sync` 가 이 문서와 1차 문서를 합쳐 검사한다. ReasonCode 표는 1차 문서 6.1절에만 둔다(6xx 추가).

## 1. 원칙 (1차와 다른 점만)

- **자체 노드는 6 개다**: 1차 5 개 + `weld_manager`. 1차 계약 1장의 "자체 노드 5개"와 `.claude/rules/ros2-nodes.md` 의 예외다(각각 한 줄로 표시).
- phase 2 는 BRD · 1차 계약의 구속을 받지 않는다. 다만 다음은 유지한다(안전 · 품질): 실기 명령은 사람이(CLAUDE.md 규칙 1) · 미측정값 0 금지(규칙 4) · 수치는 파라미터(규칙 7) · **계약이 코드보다 우선**.
- 힘 · 순응 제어를 **켜지 않는다**(D2). 그래서 규칙 2(try/finally 해제)는 용접 경로에 해당하지 않는다. robot_manager 의 `ExecutePath` 는 **자기 내부 플래그**(`/robot/status` 의 `compliance_active` · `force_ctrl_active` 를 만드는 그 값)가 켜져 있으면 goal 을 거절한다(`BUSY`). 이 검사는 켜는 경로가 없는데도 **남아 있으면 안 되는 상태를 잡는 안전망**이다(1차 SLIDE 의 해제 실패 뒤 등). 컨트롤러에 조회(`GetControlMode`)하지 않는다(#125 와 같은 이유로 1차와 같은 근거를 쓴다).
- **스캔과 용접은 배타적이다**(D6). 3.3절.

## 2. 연결 표 (추가분)

### 2.1 Topic
| 이름 | 타입 | 발행 | 구독 | QoS | 의미 |
|---|---|---|---|---|---|
| `/weld/state` | `WeldState` | weld_manager | scan_manager · mqtt_bridge | STATE | 단계 · 선 번호 · 진행. 변경 시 + 주기 |
| `/weld/result` | `WeldResult` | weld_manager | mqtt_bridge | STATE | 용접 결과. 작업 종료 시 1회(실패 · 중단 포함) |
| `/weld/log` | `ScanLog` | weld_manager | mqtt_bridge | LOG | 시간순 로그. `scan_id` 자리에 `weld_id`, `phase` 는 WeldState.PHASE_*, `direction` 은 0 |
| `/scan/state` | `ScanState` | scan_manager | **weld_manager** (추가) | STATE | 스캔이 휴지인지 본다 |
| `/robot/status` | `RobotStatus` | robot_manager | **weld_manager** (추가) | STATE | 정지 완료 확인 |
| `/safety/status` | `SafetyStatus` | safety_monitor | **weld_manager** (추가) | STATE | 래치면 시작 거절 |
| `/robot/sample` | `RobotSample` | robot_manager | **weld_manager** (추가) | SENSOR | 시작 시 현재 팁 위치(z_safe 위인지 · 첫 접근 1 의 출발점)와 툴 등록 확인(무접촉 \|F\| 가 크면 미등록, 9/23 비상정지 2 회 원인). 용접 중에는 쓰지 않는다 |

`/robot/sample.operation` 은 `ExecutePath` 실행 중 `OP_WELD_PATH(5)` 다. `motion_id` 는 그 goal 의 값.

### 2.2 Service
| 이름 | 타입 | 서버 | 클라이언트 | 의미 |
|---|---|---|---|---|
| `/weld/stop` | `StopWeld` | weld_manager | mqtt_bridge | 용접 중지 요청. weld_manager 는 `/robot/stop`(requester `'weld_manager'`) 을 부른다 |
| `/robot/stop` | `StopRobot` | robot_manager | scan_manager · safety_monitor · **weld_manager** (추가) | 1차와 같다. `requester` 에 `'weld_manager'` 허용 |

### 2.3 Action
| 이름 | 타입 | 서버 | 클라이언트 | 의미 |
|---|---|---|---|---|
| `/weld/run` | `RunWeld` | weld_manager | mqtt_bridge | 용접 시작 |
| `/weld/home` | `ReturnHome` | weld_manager | mqtt_bridge | 안전복귀(1차 타입 재사용). `OP_HOME` 을 robot_manager 에 보낸다 |
| `/robot/execute_path` | `ExecutePath` | robot_manager | weld_manager | 경유점 경로 1개 |
| `/robot/execute_motion` | `ExecuteMotion` | robot_manager | scan_manager · **weld_manager** (추가) | 접근 · 후퇴 · 안전 높이 이동은 `OP_MOVE_TO`, 홈은 `OP_HOME` |

## 3. 메시지 (msg)

### 3.1 WeldConfig.msg
```
# WeldConfig.msg — 용접 설정 (phase 2). *_set=true 인 항목만 적용 (부분 갱신, ScanConfig 와 같은 규약)
# 값은 설계 출발값이며 실측으로 조정한다. 기본값은 weld_manager 파라미터(contact_scan_bringup/config/*.yaml)
float64 weld_speed_mps        # 용접선 위 TCP 속도
bool    weld_speed_set
float64 travel_speed_mps      # 선 사이 이동(안전 높이) 속도
bool    travel_speed_set
float64 standoff_m            # 팁이 이음선에서 툴 축 방향으로 물러나는 거리 (접촉하지 않는다)
bool    standoff_set
float64 weave_amplitude_m     # 위빙 진폭 (이음선 기준 ±). 0 이면 직선
bool    weave_amplitude_set
float64 weave_pitch_m         # 위빙 반주기 간격 (진행 방향). 0 이면 직선
bool    weave_pitch_set
float64 tilt_deg              # 툴 축이 연직에서 바깥으로 기우는 각. 두 면의 법선을 이등분하는 면 안에서 기운다
bool    tilt_set
```
- `RunWeld.config_override` 로 받은 값은 그 작업에만 적용한다. 파라미터는 바꾸지 않는다(1차 SetConfig 전파는 쓰지 않는다).
- 범위 밖(속도 < `weld_speed_min_mps`, 진폭 < 0, tilt 0~80° 밖) 이면 `INVALID_VALUE(102)`. **속도 상한은 weld_manager 가 검사하지 않는다**(D29): 상한의 주인은 robot_manager(`path_max_speed_mps`)이고, 넘는 값은 첫 `ExecutePath` 에서 `PATH_REJECTED(604)` 로 끝난다(그 전의 접근 이동 두 번은 `travel_speed_mps` · `approach_speed_mps` 로 나간다). 1차도 같다: scan_manager 는 하한(> 0)만 보고 robot_manager 가 `speed <= 0` 을 거절했다.

### 3.2 WeldState.msg
```
# WeldState.msg — 용접 진행 상태 (phase 2). 변경 시 + 주기 발행 (STATE QoS)
uint8 PHASE_IDLE=0          # 대기
uint8 PHASE_PREPARING=1     # 시작 조건 점검 · 결과 읽기 · 경로 생성
uint8 PHASE_APPROACH=2      # 안전 높이 이동 · 접근점 하강
uint8 PHASE_WELDING=3       # 용접선 위 이동 (ExecutePath)
uint8 PHASE_RETREAT=4       # 후퇴 · 안전 높이 상승
uint8 PHASE_DONE=5          # 완료 (마무리 홈 복귀 포함)
uint8 PHASE_ERROR=6         # 오류 (실패 · 안전 이상)
uint8 PHASE_STOPPING=7      # 중지 요청 접수 · 정지 완료 대기
uint8 PHASE_STOPPED=8       # 중단됨
uint8 PHASE_HOMING=9        # 홈 복귀 진행 (안전복귀 · 마무리 공용)
uint8 LINE_NONE=255         # line_index 가 없을 때
builtin_interfaces/Time stamp
string weld_id              # IDLE 이면 ""
string scan_id              # 용접 대상 스캔 결과
uint8 phase
uint8 line_index            # 진행 중인 용접선 0~7. 없으면 LINE_NONE
uint8 line_total            # 8
uint8 lines_done            # 완료한 용접선 수
float32 line_progress       # 진행 중인 선 안의 진행률 0.0~1.0 (WELDING 에서만 유효, 그 밖은 0)
uint32 motion_id            # 진행 중 ExecuteMotion · ExecutePath goal. 없으면 0
```
- 전이: IDLE → PREPARING → (APPROACH → WELDING → RETREAT) × 선 → HOMING → DONE. 실패 → ERROR. STOP → STOPPING → STOPPED. 안전복귀 → HOMING → (원래 휴지 phase 로) 1차와 같다.
- `line_progress` = 진행 거리 / 선 길이. `ExecutePath.Feedback.distance_travelled` 로 계산한다.
- **재시작은 없다**(D7). STOPPED · ERROR 뒤에는 `start_line` 을 지정한 새 START 로 이어 간다.

### 3.3 WeldLine.msg
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

### 3.4 WeldResult.msg
```
# WeldResult.msg — 용접 결과 (phase 2). 작업 종료 시 1회 (실패 · 중단 포함). 미측정값은 NaN + *_valid=false
string weld_id
string scan_id
builtin_interfaces/Time stamp
bool success                   # 8 선(start_line 부터) 전부 DONE
uint16 reason_code             # ReasonCode. 성공 = 0
string detail
string frame_id                # seam · stop_pose 의 프레임 ('workpiece_fixture')
geometry_msgs/Vector3 base_to_fixture   # 이 결과가 쓴 작업대 원점의 Base 좌표 (m). 웹이 Base 샘플과 겹쳐 그릴 때 쓴다
uint8 start_line
uint8 end_line
WeldLine[8] lines
WeldConfig config              # 적용 설정 스냅샷 (전부 *_set=true)
builtin_interfaces/Time started_at
builtin_interfaces/Time finished_at
```
- `lines[i].seam` 은 계획한 이음선(작업대 좌표). 세로선은 `bottom_margin_m` 만큼 짧다(`weld-motion.md` 1절).
- `base_to_fixture` 는 용접에 쓴 `result.json` 의 `node_params.base_to_fixture` 그대로다. 웹은 이 값으로 Base 의 `robot/sample` 을 작업대 좌표로 옮겨 비드를 그린다.
- 파일 보존: weld_manager 는 `<result_dir>/<scan_id>/weld/<weld_id>.json` 에 결과를 원본으로 남긴다(형식은 담당자 안. 스캔 result.json 과 같은 값 규칙: `null` + `*_valid=false`, 0 금지).

## 4. 서비스 (srv)

### 4.1 StopWeld.srv
```
# StopWeld.srv  (/weld/stop)
string request_id           # MQTT cmd/weld/stop 의 request_id
string requester            # 'mqtt_bridge'
uint16 reason               # 웹 요청은 STOP_REQUESTED
string detail
---
bool accepted               # 접수. 정지 완료는 /weld/state.phase == STOPPED
uint16 reason_code
string detail
```
- 휴지 phase(IDLE · DONE · ERROR · STOPPED)에서는 `accepted=false`, `BUSY` 가 아니라 **`OK` 로 "멈출 것이 없다"** 를 돌려준다(1차 StopScan 과 같은 규칙).

## 5. 액션 (action)

### 5.1 RunWeld.action
```
# RunWeld.action  (/weld/run)
string request_id
string scan_id              # 용접할 스캔 결과. "" = result_store 의 가장 최근 성공 결과
uint8 start_line            # 0~7. 이 선부터 순서대로. 앞 선은 SKIPPED
uint8 end_line              # 0~7, start_line 이상. 이 선까지. 뒤 선은 SKIPPED. 웹 기본값 7 (goal 에서 0 이면 "0번 선까지"다 — 생략이 아니다)
bool use_override
WeldConfig config_override
---
string weld_id
bool success                # 명령 전체(마무리 홈 복귀 포함)의 성공 여부
uint16 reason_code
string detail
WeldResult result           # /weld/result 와 같은 내용. result.success 는 용접선의 성공 여부
---
WeldState state
```
시작 거절 사유(순서대로 검사):
| 조건 | reason_code |
|---|---|
| weld_manager 가 휴지가 아니다 | `BUSY(100)` |
| `/scan/state` 가 없거나 `scan_state_timeout_s` 보다 오래됐다 | `INVALID_REQUEST(101)` + detail |
| `/scan/state.phase` 가 휴지(IDLE · DONE · ERROR · STOPPED)가 아니다 | `SCAN_ACTIVE(600)` |
| `/safety/status.latched` | `SAFETY_LATCHED(103)` |
| `/robot/status` 없음 · `connected=false` | `ROBOT_DISCONNECTED(104)` |
| `scan_id` 의 `result.json` 이 없다 · `success=false` · `box_valid=false` · `""` 인데 성공 결과가 하나도 없다 | `NO_SCAN_RESULT(602)` |
| `start_line > 7` · `end_line > 7` · `end_line < start_line` | `LINE_OUT_OF_RANGE(603)` |
| `config_override` 범위 밖 (속도 < `weld_speed_min_mps` 포함) | `INVALID_VALUE(102)` |
| `/robot/sample` 이 없다 | `NO_SAMPLE(307)` |
| 무접촉 \|F\| > `tool_check_max_force_n`(출발값 6.0, contact_detector 의 `tare_max_force_n` 과 같은 근거) | `TOOL_REG_SUSPECT(302)` |
| 생성한 경로가 작업영역 밖, 또는 세로선 툴 외형 검사(`tool_profile_u_m` · `tool_profile_r_m`, `weld-motion.md` 5절) 실패 | `PATH_REJECTED(604)` |

- `end_line` 은 **생략할 수 없다**(uint8 의 0 은 "L0 까지"다). mqtt_bridge 가 payload 에 없으면 7 을 넣는다. `start_line..end_line` 밖의 선은 `SKIPPED`. "tilt 0 으로 L0 만"은 `start_line=0 · end_line=0`.
- `scan_id == ""` 이면 **result_store 의 가장 최근(`scan_id` 사전순) `success=true` 결과**다. 진행 중 기록(progress.json)만 있는 작업은 후보가 아니다.
- `WeldResult.success` 는 `start_line..end_line` 의 선이 전부 DONE 일 때다.
- Result 의 `success` 는 마무리 홈 복귀까지 포함한다. `result.success` 는 용접선만 본다(1차 RunScan 과 같은 구분).

### 5.2 ExecutePath.action
```
# ExecutePath.action  (/robot/execute_path) — 경유점을 차례로 지나는 직선 이동. 접촉 판정 없음, 힘 · 순응 제어 없음
string weld_id
uint32 motion_id            # weld_manager 발급. ExecuteMotion 과 같은 번호 공간
uint8 line_index            # 관측용 (WeldState.line_index)
geometry_msgs/Pose[] waypoints   # 차례로 지날 TCP pose. 마지막 점에서 정지한다. 첫 점까지도 직선으로 간다
string frame_id             # waypoints 의 프레임
float64 speed               # m/s (TCP 직선 속도)
float64 path_tolerance_m    # 마지막 점 도착 허용치. 넘으면 ROBOT_ERROR
builtin_interfaces/Duration timeout
---
uint8 REASON_TARGET_REACHED=0   # ExecuteMotion.REASON_* 와 같은 값
uint8 REASON_TIMEOUT=4
uint8 REASON_STOP_REQUESTED=5
uint8 REASON_CANCELED=6
uint8 REASON_OVER_FORCE=7
uint8 REASON_ROBOT_ERROR=8
uint8 REASON_REJECTED=9
geometry_msgs/Pose pose         # 정지 시점 pose
string frame_id
builtin_interfaces/Time pose_stamp
uint8 reason
uint16 reason_code              # ReasonCode
string detail
float64 distance_travelled
uint16 waypoints_done           # 지난 경유점 수 (spline 이면 진행 거리로 추정)
---
geometry_msgs/Pose pose
string frame_id
builtin_interfaces/Time pose_stamp
float64 distance_travelled
uint16 waypoint_index           # 향하고 있는 경유점
builtin_interfaces/Duration elapsed
```
- 동시에 1개만 수락한다. **`ExecuteMotion` 과 같은 자리**를 쓴다: 어느 한쪽이 실행 중이면 다른 쪽도 `BUSY`. `/robot/stop` 이 걸려 있으면 거절(1차 규칙과 같다).
- 거절(`REASON_REJECTED` · `PATH_REJECTED(604)`): `waypoints` 가 비었다 · `path_max_points` 초과 · `speed ≤ 0` 또는 `> path_max_speed_mps` · `frame_id ≠ robot_manager.frame_id` · **경유점 하나라도 `z < path_min_z_m`**(Base, robot_manager 파라미터. 수락 시점에 전부 검사한다) · 순응 · 힘 제어가 켜져 있다(→ `BUSY`).
- **작업영역은 두 겹이다.** weld_manager 가 먼저 작업대 좌표로 거른다(`weld-motion.md` 5절: z ≥ `support_z + bottom_margin_m`, x · y 는 부재 ± `workspace_margin_m`). robot_manager 는 Base 좌표의 **z 하한 하나**(`path_min_z_m`)만 본다 — 경유점이 잘못 와도 `path_max_speed_mps`(0.100, 밀기의 20 배)로 작업대에 박히지 않게 하는 마지막 울타리다(학민 리뷰). 출발값은 작업대 표면 `base_to_fixture.z`(0.095) + 테이프 2 mm + 여유 3 mm ≈ **0.100 m**. `real.yaml` 에서 좌표를 켤 때 같이 채운다.
- 실행: 현재 위치에서 첫 점까지, 그리고 점 사이를 **직선**으로 `speed` 로 지난다. 구현(`move_spline_task` 한 번 / `move_line` 반복 + radius)은 robot_manager 담당의 선택이다. 어느 쪽이든 **점 사이에서 멈추지 않는 것**이 목표지만, 멈춰도 계약 위반은 아니다(D8 코너 정지 허용).
- 종료: 마지막 점에서 정지 확인(1차 `arrival_grace_s` · `moving` 판정과 같다). 마지막 점과의 거리 > `path_tolerance_m` 이면 `REASON_ROBOT_ERROR` + `ROBOT_ERROR(204)`.
- 접촉 이벤트로 멈추지 않는다. `TYPE_OVER_FORCE` 는 1차와 같이 항상 정지(`REASON_OVER_FORCE`).
- `RobotSample.operation = OP_WELD_PATH`, `motion_id = goal.motion_id` 를 실행 중 내내 발행한다(웹 비드 궤적의 근거).
- Feedback 은 `/robot/sample` 주기와 같거나 느리게(10 Hz 이상 필요 없다).

## 6. 공통 정의 (추가분)

- ReasonCode 6xx: `SCAN_ACTIVE 600` · `WELD_ACTIVE 601` · `NO_SCAN_RESULT 602` · `LINE_OUT_OF_RANGE 603` · `PATH_REJECTED 604` (표는 1차 문서 6.1절).
- robot_manager 파라미터(계약 이름): `path_max_points`(200) · `path_max_speed_mps`(0.100) · `path_min_z_m`(Base z 하한, 출발값 0.100) · `path_acc_ratio`(4.0, **단위 1/s**: 가속 [mm/s²] = 이 값 × 속도 [mm/s]. 1차 `dsr_client.move_line_request` 의 `acc = 4 × vel` 과 같은 규칙).
- `weld_id`: `scan_id` 와 같은 형식 `YYYYMMDD-HHMMSS-xxxx`(벽시계). `motion_id`: weld 안에서 1부터 증가. `ExecuteMotion` 과 `ExecutePath` 가 같은 번호 공간을 쓴다.
- 파라미터 이름(계약에 속함): `weld-motion.md` 6절의 표. weld_manager 의 `tool_check_max_force_n`(6.0) · `weld_state_timeout_s`(scan_manager, 5.0) 포함.
- **null 규칙(1차와 다른 점)**: `WeldState.line_index` 는 `LINE_NONE(255)` 이 "없음"이고 `*_valid` 짝이 없다. MQTT 에서는 `null` 단독이다. `WeldLine.stop_pose` 는 ROS 에서는 `stop_pose_valid` 짝이 있지만 MQTT 에서는 `null` 단독으로 싣는다(`weld-mqtt-schema.md`).

## 7. 동작 규칙

### 7.1 배타 규칙 (D6)
| 누가 | 무엇을 볼 때 | 거절 |
|---|---|---|
| weld_manager | `/scan/state.phase` 가 휴지가 아니다 | START → `SCAN_ACTIVE(600)` |
| scan_manager | `/weld/state.phase` 가 휴지(IDLE · DONE · ERROR · STOPPED)가 아니다 | START · RESUME → `WELD_ACTIVE(601)`. 안전복귀(`/scan/home`)는 막지 않는다 |
| robot_manager | 다른 goal 실행 중 | 어느 서버든 `BUSY(100)` |

`/weld/state` 가 한 번도 오지 않았으면(weld_manager 미기동) scan_manager 는 용접이 없다고 본다(1차 동작 유지). **마지막 `/weld/state.stamp` 가 `weld_state_timeout_s`(출발값 5.0)보다 오래됐어도 용접이 없다고 본다** — TRANSIENT_LOCAL 이라 weld_manager 가 WELDING 중에 죽으면 마지막 값이 남아 스캔이 영영 601 로 막히기 때문이다(현지 리뷰 5. weld_manager 의 `scan_state_timeout_s` 와 대칭).

### 7.2 중지 · 안전복귀 (D7)
- `/weld/stop` → STOPPING → `/robot/stop` → `/robot/status` 로 정지 확인 → STOPPED. 재시작은 없다. 중지 · 안전복귀 · 시작은 서로를 부르지 않는다(1차 규칙 3).
- **STOPPED 는 `/weld/stop` 을 경유한 정지뿐이다**(D25, 현지 리뷰 4). weld_manager 가 요청하지 않은 정지(웹의 스캔 중지 버튼이 부르는 `/robot/stop`, safety_monitor 의 정지)로 goal 이 `REASON_STOP_REQUESTED` · `REASON_CANCELED` 로 끝나면 **ERROR** 다(1차 scan_manager 와 같은 분류). 사유는 래치 중이면 `SafetyStatus.reason_code`, 아니면 `ROBOT_ERROR(204)` + detail.
- `/weld/home` 은 휴지 phase 에서만 받는다. **정지 좌표를 알면 먼저 그 자세의 툴 축 뒤(−d)로 `approach_m` 물러난 뒤** `OP_MOVE_TO` 로 z_safe 까지 올리고 `OP_HOME`(현지 리뷰 3: 세로선 도중에 멈췄으면 팁이 모서리선에서 1.5~3 mm 떨어진 채 위 꼭짓점을 스치며 올라간다). 현재 위치를 모르면(정지 좌표 없음) 물러남 · 올림 없이 `OP_HOME` 만 보낸다 — 이때 기울인 자세에서 곧장 관절 이동이 나가므로 **관제자가 보고 누른다**.
- safety_monitor 의 정지(OVER_FORCE · SAMPLE_STALE …)는 1차와 같이 goal Result 로 잡혀 ERROR 가 된다. 래치 해제는 `/safety/reset`.

### 7.3 용접 완료 순서
마지막 선 후퇴 → `/weld/result` 발행 · 파일 저장 → HOMING(`OP_MOVE_TO` z_safe → `OP_HOME`) → DONE. 결과는 홈 복귀보다 먼저 나간다(1차 7.4 와 같다).

## 8. TBD
- `ExecutePath` 실행 방식(spline / line + radius): 오늘 실기 M4 결과로 학민이 정한다.
- 기울인 자세의 손목 도달성(`tool_roll_deg` 필요 여부): 오늘 M1.
- 웹 비드 궤적을 Base → 작업대로 옮길 때 `WeldResult.base_to_fixture` 를 쓸지, 프런트의 `VITE_BASE_TO_FIXTURE_MM` 을 그대로 쓸지: 의석.
