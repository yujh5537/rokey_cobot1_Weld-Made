# ROS 인터페이스 계약

> **[v0.2.0, 2026-09-23] phase 2(용접) 인터페이스는 `docs/phase2/weld-ros-interfaces.md` 에 있다.** 이 문서에는 phase 2 가 기존 타입에 더한 것만 표시했다: `OP_WELD_PATH=5`(RobotSample · ExecuteMotion 상수) · ReasonCode 6xx. `test_contract_sync` 는 두 문서를 합쳐 검사한다.

상태: **v0.1 동결** (2026-09-18, T01 1·2차 회의) · v0.1.1(T09, QoS 정의 위치 확정 · 타입 변경 없음) · v0.1.4(2026-09-20, T15, PR #72 · #83: 6.3절 실측 발행 주기, 9장 `RobotStatus.moving`의 근거와 파라미터 변경 통지 · 타입 변경 없음) · v0.1.5(#69, 판정 샘플 = 첫 샘플 확정 · 타입 변경 없음) · v0.1.9(#51 · #54, 문서 보완 · 타입 변경 없음) · v0.1.10(2026-09-21, 6.3절 발행 주기가 부하에 따라 달라짐 · 두 번째 실측과 공백 꼬리 추가 · 타입 변경 없음). **v0.1.12**(2026-09-21, #109, 하강 기준과 밀기 기준 분리: 하강은 최근 구간 평균(이동 기준), 밀기는 z 로 판정 켜기 · 타입 변경 없음) · **v0.1.13**(2026-09-21, #128, 힘 꺾임 EDGE 추가(기본 꺼짐) · 타입 변경 없음) · **v0.1.15**(2026-09-22, SLIDE 스텝 모드: robot_manager가 EDGE를 확정해 `/contact/event`를 낸다 · 타입 변경 없음) · **v0.1.16**(2026-09-23, #130: real 의 `sample_stale_ms` 300 → 500 · 타입 변경 없음) · **v0.1.21**(2026-09-23, T06 감사 후 팀 결정 10건: ERROR 재시작 허용 목록 · 하강 제한 2차 여유 · 안전복귀 경로 · 정지 KPI 분리 · 디바운스 정의. **타입 변경 있음**: `ReasonCode.STOP_UNCONFIRMED(407)` 추가, `RobotStatus`에 SLIDE 누름 목표 6개 추가). 변경은 PR + `CHANGELOG.md`로만 한다.
패키지: `contact_scan_interfaces` (ament_cmake, 소유 병후). 실제 `.msg`/`.srv`/`.action` 파일은 이 문서의 타입 전문을 그대로 옮긴 것이다(T09). 문서와 파일이 어긋나면 패키지의 `test/test_contract_sync.py`가 CI에서 실패한다.
출처: 인터페이스 정의서 통합본 v1.1(팀 합의)을 채택하고, T01 2차 회의 결정을 덧붙였다. 정의서와 달라진 곳은 **[v0.1 변경]** 으로 표시했다.

표기: **TBD** = 오늘 정하지 않은 것(9장). 수치는 전부 설계 출발값이며 계약이 아니다. 값은 `contact_scan_bringup/config/*.yaml`에만 둔다.

---

## 1. 공통 규칙

| 항목 | 규칙 |
|---|---|
| 노드 | 자체 노드 5개: `scan_manager` · `robot_manager` · `contact_detector` · `safety_monitor` · `mqtt_bridge`. **네임스페이스 없음**(아래 이름은 절대 이름). 패키지는 노드별(`ws_cobot1/src/README.md`). **[v0.2.0] phase 2 예외: `weld_manager` 가 6번째 노드다**(`docs/phase2/weld-ros-interfaces.md`) |
| 단위 | 길이 m · 각도 rad(자세는 quaternion) · 힘 N · 토크 N·m · 시간 s. 상세는 `units-frames.md` |
| 시각 | `builtin_interfaces/Time`, 메인 PC ROS 시계. TCP와 힘은 **취득 시각을 각각 보존**하고 동시 취득으로 보지 않는다 |
| 프레임 | 샘플 · 이벤트 · 모션 = Base(`base_link`, 가칭). `ScanResult` = 작업대 좌표(`workpiece_fixture`, 가칭). 변환은 scan_manager 한 곳(`units-frames.md`). 좌표를 쓰는 쪽은 `frame_id`를 확인한다 |
| 무효 값 **[v0.1 변경]** | 측정하지 못한 float 필드는 **`NaN`으로 채우고 짝이 되는 `*_valid=false`** 로 둔다. 0을 넣지 않는다. 수신 측은 **`*_valid`로만 판단**한다(NaN 비교 금지). 배열은 길이를 유지하고 원소를 NaN으로 채운다. Python 내부에서는 `None`, MQTT JSON에서는 `null` |
| ID 없음 | 숫자 ID는 `0` = 없음, 문자열 ID는 `""` = 없음 |
| 접수 ≠ 완료 | 모든 `accepted`/`success` 응답은 **접수·처리 여부**다. 로봇 정지의 **완료**는 `/robot/status`의 `connected && !moving`으로만 확인한다 |
| 독립 명령 | 작업 중지 · 안전복귀 · 재시작 · 안전 해제는 서로 독립이다. 중지가 홈 복귀나 재시작을 부르지 않는다 |
| Service 콜백 | 다른 노드의 완료를 콜백 안에서 동기 대기하지 않는다 |

---

## 2. 연결 표

### 2.1 Topic
| 이름 | 타입 | 발행 | 구독 | QoS | 의미 |
|---|---|---|---|---|---|
| `/robot/sample` | `RobotSample` | robot_manager | contact_detector · safety_monitor · mqtt_bridge · **scan_manager [v0.1.21]** | SENSOR | TCP pose + 외력 + 실행 중 동작. 50 Hz 설계 목표. scan_manager는 **마지막 유효 pose만** 들고 있다가 안전복귀(7.5 ①) · 재시작(7.6)의 첫 모션 목표를 만들 때 쓴다. 측정 · 판정에는 쓰지 않는다(그쪽은 `ExecuteMotion` Result의 pose가 계속 기준이다) |
| `/dsr01/joint_states` | `sensor_msgs/JointState` | 두산 `joint_state_broadcaster` · `joint_state_publisher` | mqtt_bridge | SENSOR | **표시 전용** M0609/RG2 관절 원본. mqtt_bridge가 발행원별 스냅샷을 분리해 MQTT `robot/joints` · `robot/gripper_joints`로 전달한다. 로봇 제어 입력으로 사용하지 않는다 |
| `/robot/status` | `RobotStatus` | robot_manager | scan_manager · safety_monitor · mqtt_bridge | STATE | 연결 · 동작 · 오류 · 제어 상태. 정지 완료 확인의 근거. 변경 시 + 주기 |
| `/contact/event` | `ContactEvent` | contact_detector · **robot_manager**(스텝 모드 SLIDE 의 EDGE 만, 7.2절 · v0.1.15) | robot_manager · scan_manager · mqtt_bridge | EVENT | CONTACT · EDGE · OVER_FORCE 판정. 판정 확정 즉시 1회 |
| `/scan/state` | `ScanState` | scan_manager | contact_detector · safety_monitor · mqtt_bridge | STATE | 단계 · 방향 · 진행 n/4. 변경 시 + 주기 |
| `/scan/result` | `ScanResult` | scan_manager | mqtt_bridge | STATE | 형상 결과. 작업 종료 시 1회(실패 · 중단 포함) |
| `/scan/log` | `ScanLog` | scan_manager | mqtt_bridge | LOG | 시간순 로그 |
| `/safety/status` | `SafetyStatus` | safety_monitor | scan_manager · mqtt_bridge | STATE | 안전 상태 · 래치. 변경 시 + 주기 |
| `/web/heartbeat` | `WebHeartbeat` | mqtt_bridge | safety_monitor | HEARTBEAT | MQTT `hb/web`을 **실제로 받았을 때만** 전달. 자체 생성 금지 |

### 2.2 Service
| 이름 | 타입 | 서버 | 클라이언트 | 의미 |
|---|---|---|---|---|
| `/robot/stop` | `StopRobot` | robot_manager | scan_manager · safety_monitor | 로봇 정지 요청. safety_monitor는 웹을 거치지 않고 직접 호출 |
| `/contact/tare` | `TareForce` | contact_detector | scan_manager | 외력 기준값 F₀ 설정(무접촉 · 정지). **[v0.1.12]** 툴 등록 점검과 예비 기준이다. 하강 판정은 contact_detector 가 하강 중 최근 구간의 외력 평균(이동 기준)을 쓴다(3.3) |
| `/scan/stop` | `StopScan` | scan_manager | mqtt_bridge | 작업 중지 요청 |
| `/scan/set_config` | `SetConfig` | scan_manager | mqtt_bridge | 설정 등록. 동작 중이면 거절 |
| `/safety/reset` | `ResetSafety` | safety_monitor | mqtt_bridge | 안전 래치 해제. 조건이 해소됐을 때만 성공. 로봇을 움직이지 않는다 |

### 2.3 Action
| 이름 | 타입 | 서버 | 클라이언트 | 의미 |
|---|---|---|---|---|
| `/scan/run` | `RunScan` | scan_manager | mqtt_bridge | 새 작업 시작 |
| `/scan/home` | `ReturnHome` | scan_manager | mqtt_bridge | 안전복귀 = 홈위치(시작위치)로 복귀 |
| `/scan/resume` | `Resume` | scan_manager | mqtt_bridge | 재시작. **별도 Action**(`/scan/run`의 모드 아님) |
| `/robot/execute_motion` | `ExecuteMotion` | robot_manager | scan_manager | 단위 모션 1개 |

### 2.4 표준 ROS 인터페이스 (자체 정의 없음)
SetConfig를 수락하면 scan_manager가 `rcl_interfaces/srv/SetParameters`로 다른 노드의 파라미터를 갱신한다. 대상 노드는 파라미터 콜백에서 범위를 검증하고 거절할 수 있다(실패 시 `PARAM_SET_FAILED`).

| # | 경로 | 전파하는 파라미터 |
|---|---|---|
| P01 | scan_manager → `/robot_manager/set_parameters` | `slide_target_force_n` · `drop_limit_m` |
| P02 | scan_manager → `/contact_detector/set_parameters` | `contact_threshold_n` · `edge_drop_m` · `debounce_n` · `over_force_n` |
| P03 **[v0.1 변경 · 신설]** | scan_manager → `/safety_monitor/set_parameters` | `over_force_n` · `drop_limit_m` |

`ScanConfig.target_force_n`(메시지 필드)은 P01에서 robot_manager 파라미터 **`slide_target_force_n`**으로 전파된다. 숫자는 그대로 전달된다. 나머지 항목은 필드 이름과 파라미터 이름이 같다(`drop_limit_m` 등).

**이 값의 기준 [v0.1.9].** robot_manager는 이 값을 `set_desired_force`에 **`DR_FC_MOD_REL`**로 싣는다(#73). 두산 매뉴얼 5.1.4의 정의가 "힘제어 초기의 센서값을 기준으로 상대적인 외력만 참조"이므로 **기준점은 호출 시점의 힘이고, tare 대비 절대 누름 힘이 아니다.** **SLIDE가 어디서 시작하느냐에 따라 실제 누름이 다르다.** 첫 방향은 DESCEND 접촉 자리에서 바로 밀므로 **접촉력 + 이 값**이고, 2~4 방향과 재시작은 방향 전환(7.3절)으로 윗면 `recontact_margin_m` 위에서 시작하므로 **≈ 이 값**이다. 계약이 이 필드를 "누름 목표 힘"이라 부르므로 웹 표시 문구도 이 기준에 맞춘다(절대값으로 읽히면 안 된다). REL을 유지할지 ABS로 바꿀지는 실기 결과를 보고 정한다(#73. **TBD**).

### 2.5 외부 (정의하지 않음)
두산 `dsr_msgs2`(네임스페이스 `/dsr01`)와 OnRobot RG2 드라이버는 **robot_manager만** 호출한다. 실제 서비스 이름 · 동작 여부는 `docs/env/api-check-log.md`. MQTT는 `mqtt-schema.md`.

---

## 3. 메시지 (msg)

### 3.1 RobotSample.msg **[v0.1 변경: `motion_id` · `operation` 추가]**
```
# TCP pose + 외력 통합 샘플. 각 취득 시각을 별도 보존한다 (BRD 4.1.6).
# operation: robot_manager 가 지금 실행 중인 ExecuteMotion goal 의 종류. ExecuteMotion.action 의 OP_* 와 같은 값.
uint8 OP_NONE=0
uint8 OP_MOVE_TO=1
uint8 OP_DESCEND=2
uint8 OP_SLIDE=3
uint8 OP_HOME=4
uint8 OP_WELD_PATH=5                # ExecutePath 실행 중 (phase 2). ExecuteMotion goal 에는 쓰지 않는다

uint64 sample_id                    # robot_manager 발급, 발행마다 +1
string frame_id                     # pose · wrench 의 기준 프레임 ('base_link' 가칭)
geometry_msgs/Pose pose             # TCP pose. m, quaternion
builtin_interfaces/Time pose_stamp  # get_current_posx 응답을 받은 시각
geometry_msgs/Wrench wrench         # 외력 추정. N, N·m. get_tool_force(ref=DR_BASE)
builtin_interfaces/Time force_stamp # get_tool_force 응답을 받은 시각
bool valid                          # 두 값 모두 정상 취득이면 true
uint32 motion_id                    # 실행 중인 goal 의 motion_id. 없으면 0
uint8 operation                     # 실행 중인 goal 의 종류. 없으면 OP_NONE
```
- `motion_id` · `operation`은 **robot_manager가 자기가 실행 중인 goal의 값을 직접 찍는다.** goal을 수락한 시점부터 Result를 돌려줄 때까지 유지하고, 그 밖에는 `0` / `OP_NONE`이다.
- 구독자는 `valid=false`이거나 `now − max(pose_stamp, force_stamp)`가 최신성 한계(`stale_age_ms` / `sample_stale_ms`)를 넘으면 그 샘플을 버린다.

### 3.2 RobotStatus.msg **[v0.1 변경: `force_ctrl_active` · `motion_id` · `operation` 추가 / v0.1.21: SLIDE 누름 목표 6개 추가]**
```
builtin_interfaces/Time stamp
bool connected              # dsr_controller2 서비스 응답 가능
bool moving                 # 정지 완료 = connected && !moving
bool error
uint16 error_code           # ReasonCode, 0 = 없음
bool compliance_active      # 순응 제어(task_compliance_ctrl) 켜짐
bool force_ctrl_active      # 힘 제어(set_desired_force) 켜짐
uint32 motion_id            # 실행 중인 goal. 없으면 0
uint8 operation             # RobotSample.OP_* 와 같은 값

# SLIDE 의 누름 목표. 서로 다른 세 값을 섞지 않으려고 따로 싣는다 (v0.1.21)
string slide_mode                 # 'force' = 순응 · 힘 제어(REL), 'step' = 위치 제어 스텝. 그 밖은 ''
float64 slide_force_setpoint_n    # force 모드 설정 증분 힘(DR_FC_MOD_REL). step 모드 · 모름이면 NaN
float64 slide_force_baseline_n    # 이번 SLIDE 를 시작한 시점의 기준 Fz. 모르면 NaN
float64 slide_force_estimate_n    # 추정 최종 누름 = 기준 + 설정. **추정값이며 실측이 아니다.** 모르면 NaN
float64 step_press_lo_n           # step 모드 목표 누름 ΔFz 하한. force 모드 · 모름이면 NaN
float64 step_press_hi_n           # step 모드 목표 누름 ΔFz 상한. force 모드 · 모름이면 NaN

string detail
```
- 모든 종료 경로(정상 · 취소 · 정지 · 예외)에서 `compliance_active`와 `force_ctrl_active`가 **둘 다 false**로 돌아가야 한다(BRD 4.5.2).
- `moving`의 근거(드라이버 상태 필드 vs 속도 0)는 TBD(실PC 확인).
- **누름 힘 세 값의 구분 [v0.1.21].** `slide_target_force_n`은 `DR_FC_MOD_REL`이라 "설정한 증분"이지 실제 누름이 아니다. 그래서 `force` 모드에서는 세 값을 **각각** 싣는다: ① `slide_force_setpoint_n`(설정 증분) ② `slide_force_baseline_n`(SLIDE 를 시작한 시점의 기준 Fz) ③ `slide_force_estimate_n`(① + ②, **추정**). ③을 실측으로 표시하면 안 된다 — 힘 제어 중의 조회 Fz는 참고값이다. 모르는 값은 0이 아니라 NaN이다(1장).
- **`step` 모드에서는 ①②③이 전부 NaN이다.** 스텝 모드는 REL 힘 제어를 켜지 않으므로 그 세 값은 제어 목표가 아니다. 대신 목표 누름 띠를 `step_press_lo_n` · `step_press_hi_n`으로 싣는다(7.2절). `slide_mode`가 어느 쪽인지 말해 준다.
- **채워지는 시점이 값마다 다르다 [v0.1.21].** `slide_mode` · `slide_force_setpoint_n`(force) · `step_press_lo_n` · `step_press_hi_n`(step)은 **SLIDE 가 아닐 때도 지금 설정을 싣는다** — 파라미터에서 바로 읽는 값이라 대기 중에도 "지금 이렇게 눌리도록 설정돼 있다"를 보여 준다. `slide_force_baseline_n` · `slide_force_estimate_n` **둘만** 그 SLIDE 가 도는 동안 채워진다 — 기준 Fz 는 SLIDE 가 시작돼야 잡히고, 추정 합은 그 기준이 있어야 나온다. 기준을 모르면 합도 내지 않는다(둘 다 NaN).

### 3.3 ContactEvent.msg **[v0.1 변경: `source` · `debounce_count` 추가, 무효 `z_drop_m`은 NaN]**
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
- **판정 모드는 샘플의 `operation`에서 얻는다**: `OP_DESCEND` → CONTACT만, `OP_SLIDE` → EDGE만, 그 밖(`OP_NONE` · `OP_MOVE_TO` · `OP_HOME`) → CONTACT/EDGE 판정 안 함. **OVER_FORCE는 모든 모드에서** 원시 외력 크기로 판정한다(영점에 의존하지 않음).
- **하강 기준과 밀기 기준을 나눈다 [v0.1.12, #109]** — `get_tool_force`는 센서가 아니라 모델 기반 추정이고, 그 치우침(2~3 N)은 시간이 아니라 **마지막 이동 방향과 자세**에 딸리며 멈추면 수 초~수십 초에 걸쳐 풀린다(2026-09-21 실기. 같은 자리 · 같은 자세에서 마지막 이동 방향만 다른 두 점이 2.50 N 차이). 그래서 F₀는 상수가 아니라 "그 모션, 그 자세 근처"에서만 유효하고, F₀ 하나를 하강과 밀기에 같이 쓰지 않는다.
  - **CONTACT(하강)**: DESCEND 중 F₀ 는 **최근 구간 `[t − descend_ref_window_s, t − descend_ref_lag_s]` 의 외력 평균(이동 기준)** 이다. 조건이 성립한 샘플은 구간에 넣지 않는다(기준을 얼린다). 추정값은 움직이기 시작하면 계단식으로 바뀌고 107 mm 를 내려가는 동안 자세에 따라 1~2 N 더 흐르지만(초당 약 0.2 N), 접촉은 0.1 s 안에 수 N 오르는 급변이라 가를 수 있다. 9/21 실기 하강 23 회 재생: 한 번 잡은 F₀(정지 · 이동 중)는 1~2 회 공중 거짓 CONTACT, 이동 기준은 0 회이고 윗면 z 는 같다.
  - **이동 기준이 없는 동안**(출발 뒤 `descend_ref_settle_s` · 구간 안 샘플이 `descend_ref_min_samples` 보다 적을 때) CONTACT 를 끄지 않고 `/contact/tare` 의 F₀(없으면 그 DESCEND 첫 샘플의 F)와 올린 임계 `descend_hold_threshold_n` 으로 판정한다. 끄면 그 사이에 닿았을 때 OVER_FORCE 까지 막을 것이 없다. 이렇게 확정한 CONTACT 는 더 눌린 좌표다(측정 품질 조건: 윗면이 출발점에서 하강 속도 × `descend_ref_settle_s` 보다 아래에 있어야 원래 임계로 잰다. 실기 5.5 s × 3 mm/s = 16.5 mm, 탐색 기준점 → 80 mm 큐브 윗면 107 mm)
  - **`descend_ref_settle_s` 는 `descend_ref_window_s` 이상이다.** 추정값은 출발 뒤 한 번 계단식으로 바뀌고(9/21 홈 출발 하강 22 회 모두 4.0~4.1 s, 1.4~2.6 N), 이동 기준은 계단이 구간을 다 지나갈 때까지 그 크기만큼 튄다. 3 N 으로 본 공중 최대 \|F − F₀\| 가 전부 이때(4.2~4.4 s, 최대 2.92 N) 나왔다. 계단 시각 + `descend_ref_window_s` + 여유로 둔다. 실기 5.5 s 로 재생하면 3 N 구간 공중 최대 2.04 N, 6 N 구간 최대 4.43 N
  - **한계**: 이동 기준은 느리게 오르는 접촉(부드러운 부재)을 흐름으로 흡수할 수 있다. 기준 큐브 · 탐침(43 N/mm)은 3 mm/s 에서 초당 약 130 N 이라 해당하지 않는다.
  - **EDGE(밀기)**: 판정을 켜는 "누르고 있다" 확인을 F₀ 로 하지 않는다. **z 가 멈췄고(틈을 다 메움) x · y 가 움직이는 중**이면 켠다(`edge_arm_still_window_s` · `edge_arm_still_m` · `edge_arm_travel_m`). EDGE 판정 자체는 z 추세선이다. **[v0.1.13]** `edge_force_drop_n > 0` 이면 **원시 Fz 가 최근 구간 중앙값보다 그만큼 넘게 떨어진 채 `debounce_n` 회**여도 EDGE 로 확정한다(#128, 기본 꺼짐). 둘 중 먼저 확정된 것을 낸다. 이때 `z_drop_m` 은 판정 첫 샘플의 추세선 대비 하강량(음수면 0)이고, 추세선이 없으면 `z_drop_valid = false` 다. 켜는 것은 팀 결정이다(BRD 4.1.2 는 외력 감소를 보조 신호로 둔다). 다만 판정하려면 F₀ 가 있어야 한다(보고값 `force_delta_n` 을 위해).
  - 밀기 등 DESCEND 가 아닐 때의 F₀(보고값 `force_delta_n` 용)는 마지막 CONTACT 때의 이동 기준과 `/contact/tare` 중 **나중 것**이다.
  - scan_manager 절차는 바뀌지 않는다. 준비 단계의 `/contact/tare`(정지)는 툴 등록 점검으로 그대로 부른다.
- `/scan/state`는 `scan_id` 태깅에만 쓴다.
- 판정 좌표(이 메시지)와 정지 완료 좌표(`ExecuteMotion.Result.pose`)를 혼용하지 않는다. 측정값의 출처는 판정 좌표다.
- `z_drop_m`은 편향 보정의 δ로 쓴다(임계값이 아니라 실제 하강량).

**판정 샘플의 정의 [v0.1.5 확정 · #69]** — 디바운스(연속 N 회)가 있으므로 "판정 샘플"은 **조건이 처음 성립한 샘플**(연속 구간의 첫 샘플)이다. 확정 샘플(연속 N 번째)이 아니다.

| 필드 | 어느 샘플의 값인가 |
|---|---|
| `pose` · `pose_stamp` · `wrench` · `force_stamp` · `sample_id` | **첫 샘플** (조건이 처음 성립한 샘플) |
| `z_drop_m` · `z_drop_valid` (EDGE) | **첫 샘플**의 하강량 (좌표와 같은 순간) |
| `force_delta_n` · `detect_stamp` | **확정 샘플** (연속 N 번째). BRD 9장 KPI "접촉 검출 하중 = 접촉으로 확정된 순간의 외력 크기"와 맞춘다 |
| `debounce_count` | 그대로: 판정을 확정한 연속 횟수 |

- `detect_stamp − force_stamp`가 디바운스 지연이다. 이벤트가 자기 지연을 들고 다니므로 TR-01의 "판정 지연"을 이벤트만으로 구할 수 있다.
- **측정 좌표는 `debounce_n`을 바꿔도 움직이지 않는다.** 확정 샘플의 좌표를 쓰면 디바운스 동안 더 움직인 만큼 측정값이 밀린다(50 Hz · 5 mm/s · N=3 이면 0.2 mm, N=5 면 0.4 mm. **계산값이고 실측이 아니다**). 그렇게 두면 `debounce_n` 하나가 오검출 억제와 측정 편향을 같이 바꾸어, 디바운스를 튜닝할 때마다 편향 보정 상수를 다시 재야 한다.
- CONTACT · EDGE · OVER_FORCE에 같은 정의를 쓴다.

**디바운스가 실제로 세는 것 [v0.1.21, C-7]** — `debounce_n`은 **연속 샘플 수**이지 독립된 측정 횟수가 아니다. 혼동하지 않게 사실을 적어 둔다.
- `get_tool_force`의 값은 약 10 Hz(약 94 ms)로만 갱신된다(`docs/env/api-check-log.md`). robot_manager는 그보다 빠르게(설정 50 Hz, 실기 실측 약 43 Hz) 조회해 발행하므로, **소비 측은 같은 값을 여러 샘플 연속으로 받는다.**
- 그래서 현행 `debounce_n = 3`은 사실상 "측정 1회 + 약 44 ms 대기"다. 잡음을 거르는 효과는 크지 않고 판정이 그만큼 늦는다.
- 그래도 **현행을 유지한다**(팀 결정 2026-09-22, 결정 9). 실기에서 이 값으로 검증된 기록이 있고, 바꾸면 임계 · 편향 보정을 다시 재야 한다.
- **"값이 바뀐 샘플 3회"로 바꾸지 않는다.** 오프라인 계산(130 N/s)에서 판정 순간의 참 힘 중앙 34.8 N · 최대 40.6 N — 과대 외력 30 N을 넘고 탐침이 밀리는 43 N에 닿는다.
- **스텝 모드는 별개다.** robot_manager의 스텝 EDGE는 멈춘 뒤 **새로 받은 샘플만** `step_force_samples`개 평균낸다(멈추기 전 샘플을 섞지 않는다). 그 이벤트의 `debounce_count`는 1이다(7.2절). 이 둘을 같은 규칙으로 읽지 않는다.

### 3.4 ScanState.msg
```
uint8 PHASE_IDLE=0          # 대기
uint8 PHASE_PREPARING=1     # 시작 조건 점검 · tare
uint8 PHASE_TOP_SEARCH=2    # 윗면 탐색
uint8 PHASE_EDGE_SEARCH=3   # 모서리 탐색 n/4 (밀기 + 방향 전환 이동)
uint8 PHASE_GEOMETRY=4      # 형상 생성
uint8 PHASE_DONE=5          # 완료
uint8 PHASE_ERROR=6         # 오류 (실패 · 안전 이상)
uint8 PHASE_STOPPING=7      # 중지 요청 접수 · 정지 완료 대기
uint8 PHASE_STOPPED=8       # 중단됨
uint8 PHASE_HOMING=9        # 홈 복귀 진행 (안전복귀 · 스캔 마무리 공용)
uint8 PHASE_RESUMING=10     # 재시작 진행
uint8 DIR_NONE=0
uint8 DIR_POS_X=1
uint8 DIR_NEG_X=2
uint8 DIR_POS_Y=3
uint8 DIR_NEG_Y=4

builtin_interfaces/Time stamp
string scan_id              # IDLE 이면 ""
uint8 phase
uint8 direction             # 모서리 탐색 중에만 유효
uint8 progress              # 확보한 모서리 수 n (0~4)
uint8 progress_total        # 4
uint32 motion_id            # 진행 중 ExecuteMotion goal. 없으면 0
```
- **[v0.1 변경]** `PHASE_HOMING`은 관제자의 안전복귀와 스캔 정상 완료 뒤의 마무리 복귀에 함께 쓴다(7.4절).

### 3.5 ScanResult.msg · Segment.msg **[v0.1 변경: 순서 규약 · NaN · `finished_at` 정의]**
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
**순서 규약** (geometry_estimator · ScanResult · MQTT JSON · 3D 표시가 모두 같은 순서를 쓴다):

| 항목 | 순서 |
|---|---|
| `vertices[0..3]` | 윗면. +z에서 내려다봐 **(x⁻,y⁻)부터 반시계**: 0 = (x⁻,y⁻) · 1 = (x⁺,y⁻) · 2 = (x⁺,y⁺) · 3 = (x⁻,y⁺) |
| `vertices[4..7]` | 지지면 투영. `i+4`가 `i`의 바로 아래 |
| `edges[0..3]` | 윗면 `i → (i+1)%4` |
| `edges[4..7]` | 지지면 `(i+4) → ((i+1)%4 + 4)` |
| `edges[8..11]` | 수직 `i → i+4` |
| `path_candidates[0..3]` | `edges[0..3]`과 같은 선분 · 같은 방향: 0 = y⁻ 변 · 1 = x⁺ 변 · 2 = y⁺ 변 · 3 = x⁻ 변 |
| 치수 | `width` = x · `length` = y · `height` = z |

- 비정상 형상(폭 0 이하 · 높이 음수)은 `success=false`, `reason_code=INVALID_SHAPE`.
- 원본은 result_store(메인 PC)에 먼저 저장한다. 방향별 편향 보정량은 result_store 원본에만 기록한다.

### 3.6 ScanLog.msg
```
uint8 LEVEL_INFO=0
uint8 LEVEL_WARN=1
uint8 LEVEL_ERROR=2

builtin_interfaces/Time stamp
string scan_id
uint8 level
uint8 phase                 # ScanState.PHASE_*
uint8 direction             # ScanState.DIR_*
uint32 motion_id
uint16 code                 # ReasonCode, 0 = 정보
string message
string frame_id
geometry_msgs/Pose pose     # 관련 좌표 (판정 좌표인지 정지 좌표인지 message 에 명시)
bool pose_valid
```

### 3.7 SafetyStatus.msg **[v0.1 변경: `motion_id` · `position` · `position_valid` · `stop_confirmed` 추가]**
```
uint8 LEVEL_OK=0
uint8 LEVEL_WARN=1
uint8 LEVEL_STOP=2

builtin_interfaces/Time stamp
uint8 level
uint16 reason_code          # ReasonCode 4xx. OK = 0
bool stop_required          # 이 상태에서 /robot/stop 을 요청했음
bool stop_confirmed         # 요청한 정지가 /robot/status 로 확인됨
bool latched                # true 면 scan_manager 는 시작·재시작을 거절
uint32 motion_id            # 이상 판정 시점의 RobotSample.motion_id. 없으면 0
geometry_msgs/Point position  # 이상 판정 시점의 TCP 위치 (RobotSample.frame_id 기준)
bool position_valid
string detail               # 예: "force 32.1 N > 30 N"
```
- 래치는 `/safety/reset`이 성공할 때만 풀린다. 조건이 사라져도 자동으로 풀리지 않는다.
- safety_monitor는 하드웨어 안전(E-Stop · 충돌 감지)을 대체하지 않는다.

### 3.8 WebHeartbeat.msg
```
string session_id
uint32 seq
builtin_interfaces/Time stamp           # 웹 발신 시각 (웹 PC 시계)
builtin_interfaces/Time received_stamp  # mqtt_bridge 수신 시각 (ROS 시계). 만료 판정은 이 값 기준
```

### 3.9 ScanConfig.msg
```
# *_set=true 인 항목만 적용 (부분 갱신). 값은 설계 출발값이며 실측으로 조정한다.
# 접촉 판정 → contact_detector (over_force_n 은 safety_monitor 에도)
float64 contact_threshold_n
bool    contact_threshold_set
float64 edge_drop_m
bool    edge_drop_set
uint8   debounce_n
bool    debounce_set
float64 over_force_n
bool    over_force_set
# 모션 → scan_manager 가 ExecuteMotion goal 에 실음
float64 descend_speed_mps
bool    descend_speed_set
float64 slide_speed_mps
bool    slide_speed_set
float64 max_descend_m
bool    max_descend_set
float64 max_slide_m
bool    max_slide_set
float64 motion_timeout_s
bool    motion_timeout_set
float64 lift_height_m
bool    lift_height_set
# 힘/순응 → robot_manager (drop_limit_m 은 safety_monitor 에도)
float64 target_force_n     # robot_manager 파라미터 slide_target_force_n 으로 전파 (P01). 숫자는 그대로 전달된다
                           #   기준은 DR_FC_MOD_REL: set_desired_force 호출 시점의 힘에 더해지는 값이다.
                           #   tare 대비 절대 누름 힘이 아니다. SLIDE 가 어디서 시작하느냐에 따라 실제 누름이 다르다:
                           #   첫 방향은 DESCEND 접촉 자리에서 바로 밀므로 접촉력 + 이 값,
                           #   2~4 방향과 재시작은 방향 전환(7.3)으로 윗면 recontact_margin_m 위에서 시작하므로 ~ 이 값.
                           #   REL 유지 여부는 실기 뒤에 정한다 (#73)
bool    target_force_set
float64 drop_limit_m
bool    drop_limit_set
```

---

## 4. 서비스 (srv)

### 4.1 StopRobot.srv · StopScan.srv **[v0.1 변경: `requester` 추가]**
```
# StopRobot.srv  (/robot/stop)
string request_id
string requester            # 요청한 노드 이름 ('scan_manager' | 'safety_monitor')
uint16 reason               # ReasonCode
string detail
---
bool accepted               # 접수 ≠ 정지 완료
uint16 reason_code
string detail
```
```
# StopScan.srv  (/scan/stop)
string request_id           # MQTT cmd/scan/stop 의 request_id
string requester            # 'mqtt_bridge'
uint16 reason               # 웹 요청은 STOP_REQUESTED
string detail
---
bool accepted               # 접수. 정지 완료는 /scan/state.phase == STOPPED
uint16 reason_code
string detail
```
- robot_manager 처리: `move_stop` → 순응 · 힘 제어 해제(finally) → 자동 상승 · 홈 없음.
- 이미 정지 중이어도 `accepted=true`(멱등). 드라이버 미연결이면 `accepted=false, ROBOT_DISCONNECTED`.
- scan_manager는 `/scan/stop`을 받으면 `/robot/stop` 호출과 진행 중 ExecuteMotion goal cancel을 **함께** 한다. robot_manager는 먼저 온 것으로 정지하고 나머지는 멱등 처리한다.

### 4.2 TareForce.srv **[v0.1 변경: `baseline_norm_n` · `std_norm_n` 추가]**
```
float32 duration_s          # 0 = 파라미터 tare_duration_s
string scan_id
---
bool success
geometry_msgs/Wrench offset # 저장한 기준값 F0
uint16 error                # ReasonCode, 0 = 없음
string detail
uint32 sample_count
float64 baseline_norm_n     # 무접촉 외력 크기 |F0|. 툴 무게 등록 점검(BRD 4.1.5)에 사용
float64 std_norm_n          # 구간 중 외력 크기의 표준편차
```
- scan_manager는 `/robot/status.moving=false`를 확인하고 호출한다.
- 실패 코드: `ROBOT_MOVING(304)` · `TARE_UNSTABLE(305)` · `TARE_TIMEOUT(306)` · `NO_SAMPLE(307)` · `TOOL_REG_SUSPECT(302)` · `SAMPLE_STALE(403)` · 그 밖 `TARE_FAILED(303)`.

### 4.3 SetConfig.srv
```
string request_id
ScanConfig config           # *_set = true 인 항목만 적용
---
bool success
uint16 reason_code          # BUSY / INVALID_VALUE / PARAM_SET_FAILED
string detail
ScanConfig applied          # 적용 후 전체 값 (모든 *_set = true)
```
- 동작 중(`phase ∉ {IDLE, DONE, ERROR, STOPPED}`)이면 `BUSY`로 거절한다.

### 4.4 ResetSafety.srv
```
string request_id
string detail               # 관제자 메모 (선택)
---
bool success
uint16 reason_code          # CONDITION_ACTIVE / INVALID_REQUEST
string detail
```
- 이상 조건이 아직 참이면 `CONDITION_ACTIVE`로 거절한다. 래치가 없어도 `success=true`(멱등).
- 해제 후에도 scan_manager는 시작 · 재시작 때 `latched=false`를 다시 확인한다.

---

## 5. 액션 (action)

### 5.1 RunScan.action
```
string request_id
bool use_override
ScanConfig config_override
---
string scan_id
bool success                # 명령 전체(마무리 홈 복귀 포함)의 성공 여부
uint16 reason_code
string detail
ScanResult result           # /scan/result 와 같은 내용. result.success 는 측정의 성공 여부
---
ScanState state
```
- 진행 중이면 goal 거절 `BUSY`, 래치 중이면 `SAFETY_LATCHED`, 미연결이면 `ROBOT_DISCONNECTED`.

### 5.2 ReturnHome.action
```
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
- 모션 진행 중에는 거절한다. 먼저 `/scan/stop`.
- **경로는 7.5절이다 [v0.1.21]**: 위치 확인 → 손상 의심 확인 → 수직 올림 → 도착 확인 → `OP_HOME`. 위치를 모르거나 올림이 실패하면 HOME 을 보내지 않고 `NOT_SUPPORTED(107)`로 끝낸다(사람이 펜던트로 조그한다).
- 안전 래치는 이 명령을 막지 않는다. `/robot/status` 끊김은 막는다(끊긴 로봇으로는 복귀 모션 자체가 불가능하다).

### 5.3 Resume.action
```
string request_id
string scan_id              # "" = 가장 최근 중단 작업
---
string scan_id
bool success
uint16 reason_code
string detail
ScanResult result
---
ScanState state
```
- 기존 측정값을 유지하고 중단 방향부터 잇는다. `scan_id`를 유지한다(새 작업 아님).
- 거절: `NO_RESUMABLE_SCAN` · `SAFETY_LATCHED` · `BUSY` · `ROBOT_DISCONNECTED` · `NOT_SUPPORTED`.
- **홈 안전복귀를 거친 뒤의 재접근 절차는 TBD**(BRD 6장). 확정 전까지 그 경우는 `NOT_SUPPORTED`로 거절한다. v0.1의 재시작은 "중지한 위치에서 재개"만 지원한다.
- **`ERROR`로 끝난 작업의 재시작 [v0.1.21, 9장]**: 실패 사유가 허용 목록(`SAMPLE_STALE(403)` · `ROBOT_STATUS_LOST(404)` · `STOP_UNCONFIRMED(407)`)에 있을 때만 받는다. 그 밖의 사유(`OVER_FORCE` · `DROP_LIMIT` · 알 수 없는 오류 · 목록에 없는 새 사유)는 `NOT_SUPPORTED`로 거절하고, 안전 점검 뒤 **새 START** 만 가능하다. 사람이 먼저 `/safety/reset`을 해야 하며(자동 재개 없음), 래치 · 상태 최신성 관문은 그대로 본다.

### 5.4 ExecuteMotion.action **[v0.1 변경: `OP_*` 번호 · `OP_HOME` 용도]**
```
uint8 OP_NONE=0             # goal 에는 쓰지 않는다 (RobotSample · RobotStatus 표시용)
uint8 OP_MOVE_TO=1          # 지정 좌표로 이동. 접촉 판정 없음
uint8 OP_DESCEND=2          # -z 저속 하강. CONTACT 로 정상 종료
uint8 OP_SLIDE=3            # 윗면을 누른 채 수평 이동. EDGE 로 정상 종료
uint8 OP_HOME=4             # 홈위치(파라미터 home_pose)로 이동
uint8 OP_WELD_PATH=5        # goal 에는 쓰지 않는다 (ExecutePath 실행 중 표시용, phase 2). 받으면 거절
uint8 DIR_NONE=0            # ScanState.DIR_* 와 같은 값
uint8 DIR_POS_X=1
uint8 DIR_NEG_X=2
uint8 DIR_POS_Y=3
uint8 DIR_NEG_Y=4

string scan_id
uint32 motion_id            # scan_manager 발급, scan 안에서 1부터 증가
uint8 operation
geometry_msgs/Pose target   # MOVE_TO 만 사용
string frame_id             # target 의 프레임
uint8 direction             # SLIDE 만 사용. Base 축 기준
float64 speed               # m/s
float64 max_distance        # m (DESCEND · SLIDE)
builtin_interfaces/Duration timeout
---
uint8 REASON_TARGET_REACHED=0
uint8 REASON_CONTACT=1
uint8 REASON_EDGE=2
uint8 REASON_MAX_DISTANCE=3
uint8 REASON_TIMEOUT=4
uint8 REASON_STOP_REQUESTED=5
uint8 REASON_CANCELED=6
uint8 REASON_OVER_FORCE=7
uint8 REASON_ROBOT_ERROR=8
uint8 REASON_REJECTED=9

geometry_msgs/Pose pose         # 정지 시점 pose = 중단 위치의 출처
string frame_id
builtin_interfaces/Time pose_stamp
uint8 reason
uint16 reason_code              # ReasonCode
string detail
uint64 event_id                 # 종료 원인이 된 ContactEvent. 없으면 0
float64 distance_travelled
bool compliance_released        # 순응·힘 제어 해제 확인. 항상 true 여야 한다
---
geometry_msgs/Pose pose
string frame_id
builtin_interfaces/Time pose_stamp
float64 distance_travelled
builtin_interfaces/Duration elapsed
```
- 동시에 1개만 수락한다(진행 중이면 `BUSY`).
- **이벤트 대조**: robot_manager는 `ContactEvent.motion_id`가 현재 goal과 같고, 현재 goal이 `OP_DESCEND`(CONTACT) 또는 `OP_SLIDE`(EDGE)일 때만 그 이벤트로 정지한다. `motion_id`가 0이거나 다르면, 또는 `OP_MOVE_TO` · `OP_HOME` 중이면 **정지하지 않고 로그만** 남긴다. `TYPE_OVER_FORCE`는 대조 없이 항상 우선 정지한다.
- SLIDE의 −z 목표 힘은 goal이 아니라 robot_manager 파라미터 `slide_target_force_n`이다.
- 순응 · 힘 제어를 켜는 경로는 반드시 `try/finally`로 해제하고, 모든 종료 경로에서 `compliance_released=true`를 보장한다.
- `OP_HOME`은 두 곳에서 쓴다: 관제자의 안전복귀(`/scan/home`)와 **스캔 정상 완료 뒤의 마무리 복귀**(7.4절).

---

## 6. 공통 정의

### 6.1 ReasonCode.msg (상수 전용)
`reason` · `error` · `reason_code` · `code` 필드는 모두 이 표를 쓴다. **v0.1 이후 번호는 추가만 하고 바꾸지 않는다.**

| 범위 | 코드 | 이름 | 뜻 |
|---|---|---|---|
| 0 | 0 | `OK` | 정상 / 사유 없음 |
| 1xx 요청 거절 | 100 | `BUSY` | 동작 중 |
| | 101 | `INVALID_REQUEST` | 필드 누락 · 형식 오류 · 만료 |
| | 102 | `INVALID_VALUE` | 범위 밖 설정값 |
| | 103 | `SAFETY_LATCHED` | 안전 래치 중 |
| | 104 | `ROBOT_DISCONNECTED` | 드라이버 미연결 |
| | 105 | `NO_RESUMABLE_SCAN` | 재개할 기록 없음 |
| | 106 | `DUPLICATE_REQUEST` | request_id 중복 |
| | 107 | `NOT_SUPPORTED` | 미구현 절차 |
| | 108 | `PARAM_SET_FAILED` | 다른 노드 파라미터 갱신 실패 |
| 2xx 동작 종료 | 200 | `STOP_REQUESTED` | 작업 중지 요청 |
| | 201 | `CANCELED` | Action 취소 |
| | 202 | `MAX_DISTANCE` | 최대 이동 거리 안 미접촉 · 미소실 |
| | 203 | `TIMEOUT` | 제한 시간 초과 |
| | 204 | `ROBOT_ERROR` | 드라이버 · 로봇 오류 |
| | 205 | `DROP_LIMIT` | 하강량 제한 도달 |
| 3xx 접촉 · 툴 | 300 | `NO_CONTACT` | DESCEND 미접촉 |
| | 301 | `NO_EDGE` | SLIDE 미소실 |
| | 302 | `TOOL_REG_SUSPECT` | 무접촉 외력 허용치 초과 |
| | 303 | `TARE_FAILED` | 기준값 설정 실패(아래 세분 코드에 해당하지 않는 경우) |
| | 304 | `ROBOT_MOVING` | 정지 조건 미충족 |
| | 305 | `TARE_UNSTABLE` | 구간 중 외력이 불안정 **[v0.1 추가]** |
| | 306 | `TARE_TIMEOUT` | 제한 시간 안에 샘플 수 미달 **[v0.1 추가]** |
| | 307 | `NO_SAMPLE` | `/robot/sample`이 들어오지 않음 **[v0.1 추가]** |
| 4xx 안전 | 400 | `OVER_FORCE` | 과대 외력 |
| | 401 | `OVER_SPEED` | 속도 한계 |
| | 402 | `OUT_OF_WORKSPACE` | 작업영역 · 하강 한계 |
| | 403 | `SAMPLE_STALE` | 샘플 최신성 위반 |
| | 404 | `ROBOT_STATUS_LOST` | 로봇 상태 미수신 |
| | 405 | `HB_EXPIRED` | 웹 heartbeat 만료 |
| | 406 | `CONDITION_ACTIVE` | 래치 해제 요청 시 조건이 아직 참 |
| | 407 | `STOP_UNCONFIRMED` | 정지를 요청했지만 완료(`connected && !moving`)를 확인하지 못함 **[v0.1.21 추가]** |
| 5xx 형상 | 500 | `INVALID_SHAPE` | 폭 0 이하 · 높이 음수 |
| | 501 | `INSUFFICIENT_POINTS` | 5점 미확보 |
| 6xx 용접 (phase 2) | 600 | `SCAN_ACTIVE` | 스캔이 진행 중이라 용접 시작 거절 |
| | 601 | `WELD_ACTIVE` | 용접이 진행 중이라 스캔 시작 · 재시작 거절 |
| | 602 | `NO_SCAN_RESULT` | 용접할 스캔 결과가 없거나 무효 |
| | 603 | `LINE_OUT_OF_RANGE` | `start_line` 이 0~7 밖 |
| | 604 | `PATH_REJECTED` | robot_manager 가 경로를 거절 (점 수 · 속도 · 프레임 · 작업영역) |

geometry_estimator 내부 오류 문자열은 scan_manager가 매핑한다: `GEOM_MISSING_POINT` → 501, `GEOM_NONPOSITIVE_WIDTH` · `GEOM_NEGATIVE_HEIGHT` → 500. 원문은 `detail`에 넣는다.

### 6.2 ID 규칙
| ID | 자료형 | 발급 | 형식 |
|---|---|---|---|
| `request_id` | string | FastAPI(웹 명령) / 요청 노드(로컬 정지) | UUID v4. mqtt_bridge가 중복 · 만료를 거절 |
| `scan_id` | string | scan_manager | `YYYYMMDD-HHMMSS-xxxx`(난수 4자리). result_store 파일명 · DB 키 |
| `motion_id` | uint32 | scan_manager | scan 안에서 1부터 증가. 0 = 없음 |
| `sample_id` | uint64 | robot_manager | 프로세스 내 단조 증가 |
| `event_id` | uint64 | contact_detector | 프로세스 내 단조 증가. DB 중복 키 = (`scan_id`, `event_id`) |
| `session_id` | string | FastAPI | 웹 세션 UUID |

### 6.3 QoS 프로파일
발행 · 구독 양쪽이 **같은 프로파일 정의를 import**해서 쓴다(불일치하면 연결되지 않는다).

**정의 위치 [v0.1.1 확정 · T09]**: `contact_scan_interfaces` 패키지가 설치하는 Python 모듈 **`contact_scan_qos`**. `package.xml`에는 `contact_scan_interfaces` 의존만 선언하면 된다.
```python
from contact_scan_qos import QOS_SENSOR, QOS_STATE, QOS_EVENT, QOS_LOG, QOS_HEARTBEAT
```
- 모듈 이름이 패키지 이름과 다른 이유: rosidl Python 생성기가 이미 `contact_scan_interfaces`라는 Python 패키지를 설치하므로 같은 이름으로는 설치할 수 없다(CMake 타깃 중복으로 configure 실패, 2026-09-18 Jazzy 빌드로 확인).
- 아래 표의 값은 계약이므로 ROS 파라미터로 빼지 않고 모듈에 고정한다. 값을 바꿀 때는 이 표와 모듈을 같이 바꾼다.
- 표의 이름으로 찾을 때는 `contact_scan_qos.PROFILES['SENSOR']`.

| 프로파일 | Reliability | Durability | History |
|---|---|---|---|
| `SENSOR` | BEST_EFFORT | VOLATILE | KEEP_LAST 5 |
| `STATE` | RELIABLE | TRANSIENT_LOCAL | KEEP_LAST 1 |
| `EVENT` | RELIABLE | VOLATILE | KEEP_LAST 50 |
| `LOG` | RELIABLE | VOLATILE | KEEP_LAST 100 |
| `HEARTBEAT` | BEST_EFFORT | VOLATILE | KEEP_LAST 1 |

Service · Action은 기본값. 설계 목표(샘플 50 Hz · 표시 10 Hz · heartbeat 1 Hz)는 **측정 결과가 아니다.**

**실측 — `/robot/sample` 주기는 부하에 따라 크게 달라진다. 두 번 쟀고 두 배 가까이 벌어졌다 [v0.1.10].**
`sample_rate_hz=50` · `status_rate_hz=10`, 둘 다 Virtual이다.

| 측정 | 주기 | 간격 평균 | 95% | 99% | 최대 | 샘플 |
|---|---|---|---|---|---|---|
| 2026-09-20 낮, 학민 PC 단독 (T15) | **37.6 Hz** | 24.8 ms | — | — | **97.7 ms** | 376/376 유효 |
| 2026-09-20 저녁, 통합 세션 (현지 측정) | **49.8 Hz** | 20.1 ms | 25.5 ms | 29.7 ms | 44.1 ms | 684, 손실 0 |

`/robot/status`는 **9.3~9.8 Hz**였다(낮 측정). 한 샘플의 `pose_stamp`와 `force_stamp`는 2~16 ms 떨어져 있었다.
두 값을 동시 취득으로 보면 안 된다. 설정값에 못 미치는 이유는 robot_manager가 두산 서비스를 **직렬로**
부르기 때문이다(동시 호출 시 드라이버가 서비스 응답을 멈췄다. `docs/env/api-check-log.md`).

**평균이 아니라 꼬리가 중요하다.** 통합 세션 전체에서는 위 684샘플 구간 밖에 **342 / 340 / 201 ms 공백이 세 번**
있었다(현지). `stale_age_ms`(contact_detector) · `sample_stale_ms`(safety_monitor) · EDGE 판정 창(contact_detector)의
근거를 평균 주기에 두면 이 공백에서 오판한다. 세 값은 **최대 공백**을 기준으로 잡는다.

**맞바꿈이 있다.** 342 / 340 ms 는 **당시의** `sample_stale_ms` 300 을 넘는다(지금은 아래대로 real 이 500 이다). 그 세션에 safety_monitor 가 떠 있었다면
모션도 없이 정지를 두 번 요청했을 값이다. 그렇다고 한계를 최대 공백 위로 올리면 **샘플이 실제로 끊겼을 때 알아채는
시각이 그만큼 늦어진다.** `drop_limit_m` 2차 감시(7.2)가 샘플로 돌기 때문에 하강 제한 감시도 같이 늦어진다.
그래서 **한계를 올리기 전에 공백의 원인을 없애는 쪽이 먼저다.**

**그럼에도 real 의 `sample_stale_ms` 를 300 → 500 으로 올렸다 [v0.1.16, 결정 3].** 위 원칙의 **예외**이며, 이유와 되돌릴 조건을 같이 남긴다.
- 9/21~9/22 실기에서 정지 중 약 3 s 마다 **316~365 ms 공백**이 반복됐고, 그 때문에 **goal 의 약 40 %가 `SAMPLE_STALE` 로 정지**했다(#130). 접촉 위치에서 바로 안전복귀가 나간 것도 2회 있었다. 정지가 정상 동작을 막는 상태였다.
- 기록된 공백 14개(316~365 ms 12개 · 464 ms · 687 ms) 중 300 에서는 14개 전부, **500 에서는 687 하나만** 걸린다(`safety_core` 재현).
- **687 ms 공백이 실제로 있었으므로 500 도 완전하지 않다.** 700 으로 더 올리는 것은 **지금 하지 않는다** — 데이터가 더 쌓인 뒤 검토만 한다. 코드 기본값 · sim 값도 올리지 않는다.
- 바뀌는 것은 "공백 뒤 정지를 요청하는 시점"이 0.2 s 늦어지는 것뿐이다(3 mm/s 면 0.6 mm, 5 mm/s 면 1 mm). 공백은 주로 정지 중이나 출발 직전에 난다.
- **되돌릴 조건**: #130 의 근본 원인(약 3 s 주기 지연)이 해결되면 300 으로 되돌린다. sim 은 이미 500 이라 real 과 같아지고 역전되지 않는다.

공백의 원인은 **미확인**이다. 후보는 셋이다: robot_manager 의 직렬 호출 큐(두산 서비스 한 건이 오래 걸리면 그 뒤
조회가 전부 밀린다. 342 ms 는 `service_timeout_s` 0.5 s 보다 짧아 시간 초과가 아니라 한 건의 지연일 가능성이 크다),
드라이버 응답 지연, 호스트 부하. 가르는 방법: 공백이 난 시각의 robot_manager 로그에 `응답 시간 초과` ·
`기다리다 포기한다` 경고가 있으면 큐 쪽, 없으면 드라이버나 호스트 쪽이다. T13(#73) 이후로는 모션 호출이 같은 큐에
들어가므로 공백이 더 길어질 수 있다. 실기 주기와 공백 분포는 T24 전에 다시 재고, 모션 중의 값을 따로 적는다.

### 6.4 계약에 속하는 파라미터 이름
SetConfig가 **이름으로** 전파하므로 아래 이름은 바꾸지 않는다. 값은 yaml에서 담당자가 정한다. 그 밖의 파라미터는 노드 담당자 재량이다(전체 목록은 정의서 6장).

| 노드 | 파라미터 |
|---|---|
| robot_manager | `slide_target_force_n` · `drop_limit_m` |
| contact_detector | `contact_threshold_n` · `edge_drop_m` · `debounce_n` · `over_force_n` |
| safety_monitor | `over_force_n` · `drop_limit_m` |
| scan_manager | `descend_speed_mps` · `slide_speed_mps` · `max_descend_m` · `max_slide_m` · `motion_timeout_s` · `lift_height_m` |

`over_force_n`과 `drop_limit_m`은 두 노드가 **같은 값**을 쓴다.

**SetConfig 전파 대상이 아닌 scan_manager 파라미터.** 7.3절의 `recontact_margin_m`(방향 전환 뒤 내림 목표 = 첫 접촉 z + 이 값) · `recontact_speed_mps`(그 내림의 속도. 이동 속도가 아니라 저속) · `move_speed_mps`(`OP_MOVE_TO`의 이동 속도)는 scan_manager의 파라미터다. `ScanConfig`에 없고 SetConfig로 바꿀 수 없다. 값은 `contact_scan_bringup/config/*.yaml`의 `scan_manager:` 절에 둔다. `recontact_margin_m`은 `drop_limit_m`보다 충분히 작아야 한다(7.3절).

---

## 7. 동작 규칙

### 7.1 세 정지 경로
| 경로 | 요청 | 접수 | 완료 확인 |
|---|---|---|---|
| ① 웹 작업 중지 | `cmd/scan/stop` → `/scan/stop` → `/robot/stop` + goal cancel | `StopScan.accepted` | `/robot/status` → `phase=STOPPED` |
| ② 접촉 · 엣지 · 과대 외력 판정 | `/contact/event` → robot_manager 자체 정지 | 없음 | `ExecuteMotion.Result` + `/robot/status` |
| ③ 안전 이상 | safety_monitor → `/robot/stop` (웹 경유 없음) | `StopRobot.accepted` | `/robot/status` → `SafetyStatus.stop_confirmed` |

**정지 KPI 두 가지 [v0.1.21].** 하나로 묶지 않는다. 접촉 중에는 43 N/mm × 3 mm/s = 약 129 N/s라 3 N에서 탐침이 밀리는 43 N까지 **0.31 s**다. 그래서 물리 정지에 3 s를 허용하는 표현은 두지 않는다.

| KPI | 재는 구간 | 목표 | 재는 법 |
|---|---|---|---|
| **물리 정지** | 정지 버튼 · 정지 요청 → TCP 속도가 사실상 0 | **1 s 이내**(BRD 9장 '작업 중지 반응 시간') | bag 또는 로봇 실측. 단위 · 통합 시험으로는 판정하지 않는다 |
| **STOPPED 표시** | 정지 요청 → 시스템이 완료를 확인하고 `phase=STOPPED`를 표시 | **3 s 이내** | 정지 확인 창(`stop_confirm_timeout_s`) + 상태 발행 주기 + `wait_still`. 상태 전이는 시험으로 확인할 수 있다 |

접수(`accepted`)는 둘 중 어느 것도 아니다. 완료는 `/robot/status`의 `connected && !moving`으로만 본다(1장).

### 7.2 이중 감시 (같은 기준 z, 2차는 여유만큼 뒤)
| 대상 | 1차 | 2차 |
|---|---|---|
| 과대 외력 `over_force_n` | contact_detector `TYPE_OVER_FORCE` → robot_manager 즉시 정지 | safety_monitor 독립 감시 → `/robot/stop` + 래치 |
| 하강 제한 `drop_limit_m` **[v0.1 변경 / v0.1.21 여유]** | robot_manager가 SLIDE 안에서 즉시 정지 · 순응 해제. 기준 z = `operation`이 `OP_SLIDE`로 바뀐 **첫 샘플의 z**. 한계 = `drop_limit_m`. `REASON_ROBOT_ERROR` + `DROP_LIMIT(205)` | safety_monitor가 **같은 기준 z**로 감시. 한계 = `drop_limit_m + drop_limit_margin_m` → `/robot/stop` + 래치 |

**기준 z는 두 감시가 같아야 한다.** 기준이 다르면 여유가 의미를 잃는다. 실기에서 순응 제어를 켜면 z가 약 0.7 mm 올라오므로, "실행 직전의 마지막 위치"와 "SLIDE 첫 샘플"은 같은 값이 아니다. robot_manager는 **자기가 `operation = OP_SLIDE`로 발행한 첫 유효 샘플의 z**를 기준으로 잡는다 — safety_monitor가 잡는 것과 같은 메시지의 같은 값이다. 그 샘플이 오기 전에는 실행 직전의 마지막 위치를 임시 기준으로 쓴다(감시를 끄지 않는다).

**여유(`drop_limit_margin_m`) [v0.1.21].** 이전 규칙은 "값도 기준도 같게"였다. 그러면 잡음 한 샘플로도 2차가 먼저 걸려 **1차가 정상 동작인데 래치부터 걸린다**(#53). 그래서 2차만 여유만큼 뒤로 둔다.
- `drop_limit_m`은 **여전히 두 노드가 같은 값**이다(6.4절의 쌍 검사와 `SetConfig` P03 전파는 그대로다). 여유는 safety_monitor 전용 파라미터이며 **계약 이름이 아니고 `ScanConfig`에도 없다.** 그래서 `SetConfig`로 두 노드의 `drop_limit_m`을 같은 값으로 다시 덮어도 여유는 사라지지 않는다.
- 역할: 1차 = 정상 동작의 제한(넘으면 그 SLIDE 를 실패로 끝낸다). 2차 = 1차가 막지 못했을 때의 최후 방어선(정지 + 래치).
- 경계는 **초과**다. 정확히 한계값이면 걸리지 않는다(1차 `drop > drop_limit_m`, 2차 `drop > drop_limit_m + drop_limit_margin_m`).
- **10 mm의 근거 [v0.1.21]**: 간섭 거리 D = 그리퍼 밖 탐침 길이 **12 mm**(2026-09-23 자로 실측, 현지 · 학민 · 병후)보다 2 mm 작다. 옛 9 mm 와 "탐침 길이를 손으로 재어 정했다"는 문구는 근거가 없었다(정정). 팁이 D 넘게 내려가면 그리퍼가 부재에 닿으므로 **D가 상한**이다. 여유 5 mm는 10에서 1차 5를 뺀 값이다(여유가 먼저 정해진 것이 아니다).
- **남는 조건 둘 다 미측정이다 [v0.1.21]**: 상한 `L2 + O2 < D` → O2(2차가 걸린 뒤 더 내려가는 거리) < 2 mm. 하한 `5 + O1 < L2` → O1(1차 정지 뒤 더 내려가는 거리) < 5 mm(넘으면 1차가 정상 정지할 때마다 2차가 래치되어 #53이 재발한다).
- **O를 지배하는 것은 관성이 아니라 힘 제어다 [v0.1.21]**: 9/22 실기 1123에서 `move_stop` 뒤 옆 이동은 0.12 s에 섰는데 z가 2.5 mm/s로 1.7 s 동안 **2.8 mm** 내려갔다. 그 값이면 10 + 2.8 = 12.8 > D다. #152(PR #156)가 정지 전에 힘 제어를 풀도록 고쳤고 실기 기본은 힘 제어가 없는 `step` 모드다 — **이 값은 step 모드 기준이며, `force` 모드로 되돌리면 재검토한다.** 되돌릴 조건: 모드별 O를 실측해 O2 > 1.5 mm(D의 자 측정 오차 포함)이면 L2를 9로 내린다.
- **기준 z는 윗면이 아니다 [v0.1.21]**: 기준은 `OP_SLIDE` 첫 샘플의 z, 즉 **눌린 높이**다. 모서리를 벗어나면 눌림이 풀리므로 실제 침하는 측정한 하강량보다 눌림 δp만큼 크다(위험 쪽). 반대로 2~4방향과 재시작은 `recontact_margin_m`만큼 위에서 시작해 그만큼 유리하다. D와 비교할 때 이 항을 잊지 않는다.
- **D는 고정이 아니다 [v0.1.21]**: 탐침을 다시 물리거나 바꾸면, 그리고 `units-frames.md` 탐침 상태 전제조건의 기준점 접촉 점검이 실패하면 다시 잰다. 과압으로 홀더 안으로 밀리면 TCP z와 함께 줄어든다.
- `confirm_n`을 늘려 2차를 늦추지 않는다. 늦추는 수단은 여유 하나다 — 시간으로 늦추면 빠른 하강에서 여유가 달라진다.
- 스텝 모드에서도 같다. 매 대기마다 1차를 보고, `step_press_max_m + step_drop_m < drop_limit_m`이어야 한다.

**SLIDE 스텝 모드 [v0.1.15].** robot_manager 파라미터 `slide_mode`(계약 이름 아님)가 `step`이면 `OP_SLIDE`는 순응 · 힘 제어를 켜지 않고 **위치 제어로 한 스텝(`step_coarse_m`) 가고 멈춘 뒤** 외력을 여러 샘플 평균내 판단한다. 누르는 힘 ΔFz를 `[step_follow_lo_n, step_follow_hi_n]`으로 유지하도록 z를 `step_z_m`씩 조절하고, 힘이 빠지면 최근 접촉 높이보다 `step_drop_m` 아래까지 내려가 본 뒤에도 `step_follow_lo_n` 미만일 때만 접촉 소실로 본다. `step_release_n`은 처음 누를 때의 닿음 기준이며 **real은 2026-09-23 실기에서 2.5 N으로 조정**했다. 1.5 N에서는 F0 치우침으로 윗면보다 약 1.4 mm 위에서 거짓 접촉이 발생해 −y가 `no_contact(204)`로 실패했고, 방향별 F0z는 −0.45~+1.40 N이었다(#167, #179). 모서리 소실 기준은 `step_follow_lo_n` 3.0 N이다. 최근 접촉 높이는 `step_follow_lo_n` 이상으로 누른 자리만으로 정한다. 그 뒤 `step_fine_m` 스텝으로 다시 긁어 모서리를 다듬는다(9/17 tactile_probe 프로토타입).
- **EDGE는 robot_manager가 확정한다.** `/contact/event`에 `TYPE_EDGE`를 낸다: `source = "robot_step"`, `event_id`는 contact_detector와 겹치지 않도록 2³² 이상, `pose.position` = (소실 지점 x · y, 최근 접촉 높이 z), `z_drop_m` = 소실을 확인하려고 더 내려간 깊이(항상 `z_drop_valid = true`), `force_delta_n` = 소실 판정 순간의 |ΔF|, `debounce_count = 1`. 짝 맞추기(`Result.event_id`, 5.4절)와 scan_manager 절차는 그대로다.
- 스텝 모드 SLIDE 중 contact_detector의 EDGE는 robot_manager가 정지에 쓰지 않는다. `OVER_FORCE`(1차 · 2차)와 하강 제한(기준 = SLIDE 첫 샘플 z)은 그대로 산다. `step_press_max_m + step_drop_m < drop_limit_m`이어야 한다.
- **`step_max_force_n`(12 N)과 `over_force_n`(30 N)은 다른 것이다 [v0.1.21].** 12 N은 스텝 알고리즘이 "이 정도면 뭔가 잘못됐다"고 보고 **스스로 들고 중단**하는 보수적 운용 한계이며, robot_manager 안에서만 쓰는 로컬 보호다. 30 N은 contact_detector · safety_monitor의 전역 안전 정지 · 래치 한계다(6.4절의 쌍 검사 대상). 12 N을 30 N으로 올리지 않는다 — 올리면 스텝 모드의 자체 보호가 사라진다.
- 시작 자리에서 스스로 `step_press_max_m`까지 내려가 누르므로, 7.3절의 방향 전환 뒤 `recontact_margin_m` 위에서 출발해도 닿는다. 멈춘 상태에서 판정하므로 편향 보정(BRD 4.2.4)의 속도 × 지연 항은 0이어야 한다 — scan_manager가 `slide_speed_mps`를 편향 보정에 그대로 넘기는 것은 후속 이슈다.
- 한 방향에 약 50~70 s(0.5 mm마다 멈춤). `motion_timeout_s`를 그만큼 둔다. Virtual에서는 외력이 0 근처라 돌릴 수 없다(sim은 `force`).

### 7.3 방향 전환 절차 **[v0.1 변경]**
한 방향의 밀기가 끝나면 scan_manager는 **`OP_MOVE_TO` goal을 연달아 보내** 다음 방향을 준비한다. 재하강(`OP_DESCEND`)은 하지 않는다.
1. 위로 `lift_height_m`(출발값 0.05)만큼 올린다.
2. 기준 원점 상공으로 수평 이동한다.
3. **첫 하강에서 기록한 접촉 z보다 `recontact_margin_m`(출발값 0.001) 위**까지 저속으로 내린다.
4. `OP_SLIDE`를 시작한다. 남은 틈은 SLIDE의 −z 목표 힘이 메운다.

- 이 구간은 `OP_MOVE_TO`이므로 접촉 판정을 하지 않는다. 보호 수단은 과대 외력 감시다.
- 3번의 속도는 이동 속도가 아니라 저속이어야 한다. `recontact_margin_m`과 내림 속도 `recontact_speed_mps`는 scan_manager 파라미터다(6.4절. 값은 TBD).
- 하강 제한의 기준은 SLIDE 첫 샘플의 z이므로, 틈을 메우는 하강량도 `drop_limit_m`에 포함된다. `recontact_margin_m`은 `drop_limit_m`보다 충분히 작아야 한다.

### 7.4 스캔 마무리 순서 **[v0.1 변경]**
```
EDGE_SEARCH 4/4
  → GEOMETRY : 형상 계산 → result_store 원본 저장 → /scan/result 발행
  → HOMING   : 팁 들어 올림(OP_MOVE_TO) → OP_HOME
  → DONE     : RunScan Result 반환
```
| 상황 | 처리 |
|---|---|
| 결과 발행 시점 | GEOMETRY가 끝나면 **바로** 발행한다. 복귀를 기다리지 않는다 |
| `finished_at` | GEOMETRY가 끝난 시각. 마무리 복귀 시간은 탐색 시간에 넣지 않는다 |
| 시작 명령의 완료 | DONE(복귀까지 끝난 시점). `RunScan.Result.success` |
| 마무리 복귀 실패 | 측정 결과는 그대로 유효(`ScanResult.success`는 바뀌지 않음). `phase=ERROR`, `RunScan.Result.success=false` + 사유 |
| HOMING 중 작업 중지 | 그 자리에서 정지 → `STOPPED`. 측정은 끝났으므로 재시작 대상이 아니다(`NO_RESUMABLE_SCAN`). 이후는 관제자의 안전복귀 |
| 형상 계산 실패 | 정상 완료가 아니므로 **자동 복귀하지 않는다.** `phase=ERROR` |
| 실패 · 중단으로 끝난 작업 | 자동 복귀하지 않는다 |
| 결과 중복 | `/scan/result`(GEOMETRY 끝)와 `RunScan.Result.result`(DONE)는 같은 내용이다. mqtt_bridge가 **`(scan_id, stamp)`** 로 한 번만 반영한다. 재시작은 `scan_id`를 유지하므로(5.3절) 중단 시의 부분 결과와 재시작 뒤의 최종 결과가 같은 `scan_id`로 두 번 나간다. 키가 `scan_id`뿐이면 나중 결과가 버려진다. scan_manager는 발행할 때마다 `stamp`를 새로 찍는다 |

### 7.5 안전복귀(`/scan/home`)의 경로 **[v0.1.21]**
관제자의 안전복귀는 **올림이 성공했을 때만** HOME 으로 간다. 이전에는 `OP_HOME` 하나만 보냈고, 2026-09-21 실기에서 **올림이 실패했는데 HOME 이 나간 사례가 2회** 있었다(#130). 탐침이 부재에 닿은 채 관절 복귀가 나가면 탐침 · 부재가 상한다.

```
/scan/home 접수 (사람이 누른다. 중지 · 실패가 자동으로 부르지 않는다 — 1장, CLAUDE.md 규칙 3)
  → ① 지금 TCP 위치를 아는가?        모르면 여기서 멈춘다
  → ② 손상이 의심되는 사유로 끝났는가? 그러면 여기서 멈춘다
  → ③ 수직 올림 (OP_MOVE_TO, 지금 자세 그대로 z + lift_height_m)
  → ④ 올림이 TARGET_REACHED 인가?     아니면 HOME 을 보내지 않는다
  → ⑤ OP_HOME
```
| 멈추는 조건 | 판정 | 결과 |
|---|---|---|
| ① 위치 불명 | `/robot/sample`의 마지막 유효 pose가 없거나 `pose_max_age_s`보다 오래됨 | `NOT_SUPPORTED(107)`. 사람이 펜던트로 조그한다 |
| ② 손상 의심 | 직전 실패의 `reason_code`, **또는 지금 걸려 있는 래치의 사유**가 `OVER_FORCE(400)` · `DROP_LIMIT(205)` · `OUT_OF_WORKSPACE(402)` | `NOT_SUPPORTED(107)`. 탐침 · 부재를 눈으로 보고 사람이 조그한다 |
| ④ 올림 실패 | 올림이 `TARGET_REACHED`가 아님(정지 · 시간 초과 · 오류) | 그 사유로 끝낸다. **HOME 을 보내지 않는다** |

- 올림도 HOME 과 같이 **안전 래치를 보지 않는다**(래치 때문에 돌아오지 못하면 안 된다). ②가 보는 것은 래치가 걸렸다는 사실이 아니라 **래치의 사유**다. 사유가 손상 의심 셋이 아니면 래치 중이어도 복귀한다.
- **요청하지 않은 정지의 사유는 `Result.reason_code`에서 읽는다 [v0.1.21].** safety_monitor 는 `/robot/stop`의 `reason`에 사유(205 · 400)를 싣고, robot_manager 는 그것을 `ExecuteMotion.Result.reason_code`로 돌려준다(사유가 없으면 `STOP_REQUESTED`). 판정은 `Result.reason_code` → `/safety/status`의 래치 사유 → `ROBOT_ERROR(204)` 순으로 본다. `/safety/status`의 도착 순서에 기대면 사유가 204 로 뭉개지고, 래치에만 기대면 사람이 먼저 `/safety/reset`을 누른 순간 같은 일이 생긴다.
- 올림의 자세는 지금 자세를 그대로 목표로 준다. `search_origin_pose`(TBD일 수 있다)에 기대지 않는다.
- 멈춘 경우 `ScanLog` · `ReturnHome.Result.detail`에 사유를 남긴다. **자동으로 다른 명령을 부르지 않는다.**
- 스캔 마무리 복귀(위 7.4)는 이 절차가 아니다. 그쪽은 측정이 끝난 뒤 자기 정지 좌표로 올린다.
- `step` 모드 SLIDE 안의 1 mm 들기(`step_lift_m`)도 이 절차가 아니다. 그것은 한 스텝 안의 동작이다.
- **J6 −204.84°의 실제 회전 방향은 실기에서 사람이 확인한다**(아직 확인되지 않았다).

### 7.6 재시작(`/scan/resume`)의 첫 모션 **[v0.1.21]**
재시작의 첫 모션은 **지금 TCP 가 어디 있는지를 알고 나서** 보낸다. 기록된 중단 좌표를 목표로 쓰지 않는다.

`OP_MOVE_TO`는 절대 좌표다. 중단 뒤에 사람이 펜던트로 옮겼거나, 애초에 정지를 확인하지 못했다면(`STOP_UNCONFIRMED(407)`) 기록 좌표는 지금 위치가 아니다. 그 좌표를 목표로 주면 **낮은 높이에서 기록 좌표로 되돌아가는 수평 이동**이 된다.

| 시점 | 판정 | 결과 |
|---|---|---|
| RESUME 접수 | `/robot/sample`의 마지막 유효 pose가 없거나 `pose_max_age_s`보다 오래됨 | `NOT_SUPPORTED(107)`로 **거절**한다. 기록은 그대로 남아 샘플이 돌아온 뒤 다시 RESUME 할 수 있다 |
| 첫 모션 직전 | 접수와 실행 사이에 위치를 잃음 | 그 사유로 실패한다(사람이 조그하고 새 START) |

- **재시작이 로봇을 움직인다면 그 첫 모션은 수직 올림이다.** 7.5 ③과 같다: 지금 자리에서 x · y 와 자세를 바꾸지 않고 z 만 `lift_height_m` 올린다. 팁이 무언가에 닿아 있어도 옆으로 끌지 않는다.
  - 윗면을 확정하기 전에 끝난 작업(준비 중 · 하강 중)도 같다. 그 뒤의 기준 원점 이동은 목표 z 가 더 높아 경로가 단조 상승이지만, 직선이라 **출발 순간부터 옆으로 가는 성분**이 있다. 하강 중 중지는 팁이 윗면에 닿아 있을 수 있어 그대로 옮기면 긁는다.
  - 재시작이 로봇을 움직이지 않는 경우(측정이 다 끝나 형상 계산만 남은 경우)에는 올림도 없다.
- `pose_max_age_s`는 안전복귀와 **같은 파라미터**다. 두 경로가 같은 신선도 규칙을 쓴다.
- 이 규칙은 `STOPPED` 재시작과 `ERROR` 재시작(5.3절 허용 목록)에 **모두** 적용된다.
- 올린 뒤의 절차(무접촉 tare → 기준 원점 x · y 로 이동 → 첫 접촉 z + `recontact_margin_m`까지 저속 하강)는 7.3절 방향 전환과 같다.

---

## 8. 검토안 (MVP 밖)
`/scan/calibrate`(Action) · `/calibration/result`(Topic). 환경 세팅 후 채택 여부를 검토한다. 무접촉 힘 영점 `/contact/tare`는 이것과 별개로 MVP 필수다.

---

## 9. TBD
T01 회의에서 **담당 · 기한 없이 TBD로 두기로** 했다. 정해지면 이 문서와 CHANGELOG를 같이 고친다.

- 하강 속도 · 누름 목표 힘 · `recontact_speed_mps` · `recontact_margin_m`의 **값**(이름은 6.4절에 적었다)
- tare 허용치(`tare_max_force_n` · 불안정 판정) · 외력 감소 보조 신호
- ~~`RobotStatus.moving`의 근거~~ → **T15에서 정했다.** `get_robot_state`는 Virtual에서 이동 중에도
  STANDBY(1)를 돌려줘 쓸 수 없었다(2026-09-20 실측: z 540.6 → 527.6으로 움직이는 동안 30회 모두 1).
  robot_manager는 최근 `moving_window_s`(0.3 s) 안의 TCP 위치 변화가 `moving_eps_m`(0.2 mm)를 넘으면
  이동 중으로 본다. 위치를 모르면 이동 중으로 본다(정지로 보고하면 scan_manager가 STOPPING에서 못 빠져나온다).
  실기에서 `get_robot_state`가 제대로 동작하면 다시 본다. 두산 서비스 실제 이름은 `docs/env/api-check-log.md`.
  **`moving_eps_m` · `moving_window_s`를 바꾸면 scan_manager의 정지 확인 지연(`STOPPING` → `STOPPED`)과
  safety_monitor의 `stop_confirmed` 시점이 같이 바뀐다. 값을 고칠 때는 전원에게 알린다.**
- 순응 · 힘 제어 **해제 호출이 실패했을 때** 무엇을 보고하는가(`ExecuteMotion.Result.compliance_released` · `reason_code` · `RobotStatus`의 두 플래그). 5.4절의 "항상 true 여야 한다"는 목표이며 실패 경로는 정해지지 않았다
- 정지 시 `move_stop` → 순응 · 힘 제어 해제의 순서(4.1절). 순응이 켜진 채 급정지할 때의 반동을 실기에서 확인한 뒤 확정한다
- ~~홈 복귀 경로 · 순서~~ → **7.5절에서 정했다**(v0.1.21, 결정 7): 위치 확인 → 손상 의심 확인 → 수직 올림 → 도착 확인 → HOME. 중단 위치 재접근 절차는 여전히 TBD다
- ~~이상 상태별 재시작 허용 조건~~ → **아래에서 정했다**(v0.1.21, 결정 1). `ERROR`로 끝난 작업은 **허용 목록에 있는 사유일 때만** `/safety/reset` 뒤 `/scan/resume`을 받는다.
  - 허용: `SAMPLE_STALE(403)` · `ROBOT_STATUS_LOST(404)` · `STOP_UNCONFIRMED(407)`. 셋 다 **측정값이 오염되지 않는** 사유다
  - 불허: `OVER_FORCE(400)` · `DROP_LIMIT(205)` · 충돌 · 탐침 · 부재 손상 가능성 · 알 수 없는 오류 · **목록에 없는 새 사유**. 안전 점검 · 복귀 뒤 **새 START** 만 가능하다(`NOT_SUPPORTED(107)`)
  - **자동 재개는 없다.** 사람이 `/safety/reset`을 하고 `/scan/resume`을 보내야 한다. 안전 조건이 아직 참이면 reset 이 거절되고(`CONDITION_ACTIVE(406)`), 래치가 남아 있으면 resume 도 거절된다(`SAFETY_LATCHED(103)`)
  - 기존 START · RESUME 관문(상태 최신성 · 연결 · 래치, 5.1 · 5.3)은 그대로 통과해야 한다
  - 안전복귀(`/scan/home`) 뒤에는 여전히 재시작할 수 없다(중단 위치 재접근 절차가 TBD라서)
- heartbeat 만료 시 조치(`warn`/`stop`) · 브라우저 단절 정책, 데이터 최신성 한계
- result_store 파일 형식 · 스키마
