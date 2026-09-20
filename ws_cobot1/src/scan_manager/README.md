# scan_manager

스캔 순서(윗면 → ±X/±Y → 형상 계산 → 마무리 복귀)와 작업 중지 · 안전복귀 · 재시작을 조정하는 노드다. 담당은 병후다.
기준은 `docs/contracts/ros-interfaces.md` v0.1.1이고, 이 문서와 계약이 다르면 계약이 맞다.

| 파일 | 내용 | rclpy |
|---|---|---|
| `scan_manager/contract_enums.py` | `Phase` · `Direction` · `Reason` · `Operation` · `MotionReason`. 계약 3.4절 · 5.4절 · 6.1절 상수의 사본 | 쓰지 않음 |
| `scan_manager/state_machine.py` | 이벤트 · 전이표 · `ScanStateMachine` | 쓰지 않음 |
| `scan_manager/params.py` | 파라미터 이름 · 필수 여부 · 범위 검사, `ScanParams`. 모션 · 보정 수치에는 코드 예비값이 없다 | 쓰지 않음 |
| `scan_manager/sequence.py` | 시퀀스: `MotionPlanner`(goal 값 · 방향 전환 3단계 · 마무리 순서), `classify`(모션 결과 → 도달 · 측정 · 중지 · 실패), `ScanRunner` · `run_home`(순서. 바깥일은 `Ports` 뒤에 둔다) | 쓰지 않음 |
| `scan_manager/event_matcher.py` | `ContactEvent` ↔ `ExecuteMotion.Result` 짝 맞추기(`motion_id` 대조, `event_id` 짝, 도착 순서 무관) | 쓰지 않음 |
| `scan_manager/geometry_adapter.py` | Base → 작업대 좌표 평행 이동, `geometry_estimator` 호출, `BoxEstimate` → `ShapeResult` · `BiasCorrection`, `GEOM_*` → ReasonCode. `geometry_estimator`를 import하는 유일한 곳 | 쓰지 않음 |
| `scan_manager/result_store/` | 진행 기록 · 결과 원본의 파일 보존(T20). [README](scan_manager/result_store/README.md) | 쓰지 않음 |
| `scan_manager/geometry_estimator/` | 5점 → 편향 보정 · 직육면체(T17, 현지). [README](scan_manager/geometry_estimator/README.md) | 쓰지 않음 |
| `scan_manager/conversions.py` | msg ↔ 순수 자료형: `ContactEvent` → `Detection`, `MotionRequest` → goal, `ShapeResult` → `ScanResult`(None → NaN + `*_valid=false`), `ScanConfig` ↔ 값 | msg 타입만 |
| `scan_manager/scan_manager.py` | 노드. 서버 5개 · 구독 · 클라이언트 · `Ports` 구현 · 쓰기 스레드 · 종료 처리 | 씀 |

T19a까지 들어 있다: 시퀀스 · 서버 · geometry 연결. **검증은 테스트 안에서 띄운 가짜 상대 노드(`test/fake_peers.py`)로만 했다.** 실제 contact_detector · robot_manager와의 sim 종단 구동과 SetConfig 전파(P01~P03)는 T19b, 재시작 로직은 T26이다.

## 시퀀스 (`sequence.py`)
기준은 계약 5.4 · 7.1 · 7.3 · 7.4절과 BRD 4.2.5 · 4.2.6이다.

| 단계 | 모션 · 호출 | 다음 |
|---|---|---|
| PREPARING | `OP_MOVE_TO` 기준점(`search_origin_pose`) → 정지 확인 → `/contact/tare` | `PREPARE_DONE` |
| TOP_SEARCH | `OP_DESCEND` | CONTACT 이벤트 → 기록 → `TOP_FOUND`. 이 판정 좌표의 z가 첫 접촉 z다 |
| EDGE_SEARCH | 첫 방향은 접촉한 자리에서 바로 `OP_SLIDE`. 다음 방향부터 `OP_MOVE_TO` ×3(① 정지 좌표에서 `lift_height_m` 올림 ② 기준 원점의 x · y로 수평 이동 ③ 첫 접촉 z + `recontact_margin_m`까지 `recontact_speed_mps`로 내림) → `OP_SLIDE`. 재하강(`OP_DESCEND`)은 없다 | EDGE 이벤트 → 기록 → `EDGE_FOUND` |
| GEOMETRY | 형상 계산 → 원본 저장 → `/scan/result` 발행 | `GEOMETRY_DONE` |
| HOMING | `OP_MOVE_TO` 들어 올림 → `OP_HOME` | `HOMING_DONE` → DONE |

- 측정값의 출처는 판정 좌표(`ContactEvent.pose`)다. 정지 좌표(`ExecuteMotion.Result.pose`)는 따로 기록한다.
- **좌표는 `frame_id`를 확인하고 쓴다**(계약 1장). `motion_frame_id`와 다른 프레임의 이벤트는 측정값으로 받지 않고(`frame_id_mismatch`로 무시), 다른 프레임의 `Result.pose`로는 다음 모션을 만들지 않는다(실패).
- 정의서 1.1절은 tare → 기준점 이동 순서다. 여기서는 기준점으로 간 뒤 그 자리에서 tare를 한다(측정을 시작할 자세 · 위치에서 F₀를 잡는다). 계약 4.2절은 "`moving=false`를 확인하고 호출한다"만 정한다.
- **스캔의 모든 모션(마무리 복귀 포함)은 보내기 전에 안전 래치를 본다.** 모션 사이(tare · 기록 · 형상 계산 중)에 래치가 걸렸으면 `SafetyStatus.reason_code`로 실패한다. 모션 중의 래치는 로봇 정지의 Result로 잡힌다. 관제자의 안전복귀(`/scan/home`)는 래치가 막지 않는다.
- **실패 · 중지 · 형상 계산 실패에서는 모션을 더 보내지 않는다.** 자동 홈 복귀는 없다(계약 7.4절). `test/test_sequence.py`가 고정한다.

모션 결과의 판정(`classify`):

| `ExecuteMotion.Result` | 판정 |
|---|---|
| 서버 없음 · goal 응답 없음 / goal 거절 | 실패 `ROBOT_DISCONNECTED(104)` / `ROBOT_ERROR(204)` + "goal rejected"(ROS 2의 거절에는 사유가 없어 추측하지 않는다) |
| `compliance_released=false` | 실패. Result의 코드, 없으면 `ROBOT_ERROR`. 계약 9장 TBD |
| `REASON_STOP_REQUESTED` · `REASON_CANCELED` | `/scan/stop`을 접수했으면 중지 경로. 아니면(예: safety_monitor의 정지) 실패: 래치 중이면 `SafetyStatus.reason_code`, 아니면 `ROBOT_ERROR` |
| 중지 접수 뒤에 도달 · 측정으로 끝남 | 중지 경로. 그때 도착한 측정값은 기록하지 않고 로그만 남긴다(방침은 T26) |
| 중지 접수 뒤에 **실패 사유**로 끝남(`OVER_FORCE` · `ROBOT_ERROR` · `MAX_DISTANCE` · `TIMEOUT` · 해제 실패 · goal 거절) | **실패(ERROR).** 중지를 접수했어도 사실을 가리지 않는다. STOPPED로 보내면 재시작 대상이 된다 |
| `REASON_CONTACT`(DESCEND) · `REASON_EDGE`(SLIDE) | `event_id`의 이벤트를 `event_wait_timeout_s`까지 기다린다. 오지 않으면 **측정값 없이 통과시키지 않고** 실패 `TIMEOUT(203)`. `event_id=0`이면 `ROBOT_ERROR` |
| `REASON_MAX_DISTANCE` | `NO_CONTACT(300)` / `NO_EDGE(301)` |
| `REASON_TIMEOUT` · `REASON_OVER_FORCE` | `TIMEOUT(203)` · `OVER_FORCE(400)` |
| `REASON_ROBOT_ERROR` · `REASON_REJECTED` | Result의 `reason_code` 그대로(`DROP_LIMIT(205)` 포함) |

중지 경로: 정지 완료 확인(`Ports.wait_still`, 요청보다 뒤에 찍힌 `/robot/status`) → `record_stop` → `STOP_CONFIRMED`. 확인하지 못하면 `ROBOT_STATUS_LOST(404)`로 ERROR.

## 실행 · 테스트
```bash
cd ws_cobot1
python3 -m pytest src/scan_manager/test -q     # ROS를 source하지 않은 셸. ROS가 필요한 테스트는 skip된다
source /opt/ros/jazzy/setup.bash               # ws_dsr 없이 빌드된다
colcon build --symlink-install --packages-up-to scan_manager && source install/setup.bash
colcon test --packages-select scan_manager && colcon test-result --verbose
ros2 run scan_manager scan_manager             # 로봇 · 드라이버 연결 없이 단독 실행. 파라미터가 없어 START 는 거절된다
ros2 launch contact_scan_bringup bringup.launch.py source:=sim   # yaml 을 읽는다. 자체 노드만 뜬다
```
**시뮬레이션 테스트**는 두 단계다. ① `test_node_scan.py`: 노드를 테스트 프로세스 안에 만들어 서버 · 실패 · 중지 경로와 운영 시나리오(설정 → 스캔 중 중지 → 안전복귀 → 새 스캔)를 본다. ② `test_sim_process.py`: **실제 `scan_manager` 프로세스에 bringup의 `sim.yaml`을 `--params-file`로 주고** 전체 스캔을 돌려, `main()`(executor · 종료 처리)과 yaml의 값(기준점 · `max_descend_m` · `max_slide_m` · `base_to_fixture` · `tip_radius_m`)이 가상 직육면체에서 실제로 동작하는지 본다. `sim.yaml`의 `detect_latency_s`는 TBD라 테스트 전용 임의값을 덮어쓴다. 가짜 상대 노드는 상자까지의 거리가 `max_distance`를 넘으면 `REASON_MAX_DISTANCE`로 끝낸다.
두 테스트 모두 `ROS_DOMAIN_ID`를 따로 잡고 가짜 `/robot/execute_motion` · `/contact/tare` · `/robot/stop` 서버와 가짜 `/contact/event` · `/robot/status` · `/safety/status` 발행기를 같은 프로세스에 띄운다. 로봇 · 드라이버 · Virtual Mode를 쓰지 않는다.

## 파라미터
값은 `contact_scan_bringup/config/*.yaml`의 `scan_manager:` 절에 둔다. **모션 · 보정 수치에는 코드 예비값이 없다.** 값이 없어도 노드는 기동해 IDLE로 있고, 필수(●) 항목이 비어 있으면 START를 `INVALID_VALUE(102)`로 거절하며 detail에 빠진 이름을 나열한다. 안전복귀(HOME)는 `motion_timeout_s` · `stop_confirm_timeout_s` · `server_wait_timeout_s`만 본다(측정 파라미터가 비었다고 홈 복귀를 막지 않는다). 기동 로그에도 나온다. yaml의 수치는 sim 전용 가상값이거나 설계 출발값이며 실측값이 아니다.

| 이름 | 형 | 필수 | 범위 | 뜻 |
|---|---|---|---|---|
| `state_publish_period_s` | double | — (출발값 1.0) | > 0 | `/scan/state` 주기 발행 간격. 상태가 바뀌면 이 주기와 상관없이 바로 발행한다. 0 이하면 노드가 기동하지 않는다 |
| `descend_speed_mps` · `slide_speed_mps` | double | ● | > 0 | 계약 이름. `OP_DESCEND` · `OP_SLIDE` 속도 |
| `max_descend_m` · `max_slide_m` | double | ● | > 0. `max_descend_m`은 기준점에서 지지면까지의 거리(`search_origin_pose.z` − `base_to_fixture.z` − `support_z_m`) 미만 | 계약 이름. 미접촉 · 미소실 실패 한계. 하강 한계가 지지면에 닿으면 부재가 없을 때 작업대 면을 윗면으로 잡는다(`units-frames.md`). 안전 여유 값은 TBD |
| `motion_timeout_s` | double | ● | > 0 | 계약 이름. 단위 모션 제한 시간. tare 응답을 기다리는 한도로도 쓴다 |
| `lift_height_m` | double | ● | > 0 | 계약 이름. 방향 전환 · 마무리 때 팁 상승량 |
| `move_speed_mps` | double | ● | > 0 | `OP_MOVE_TO` 속도(기준점 이동, 방향 전환의 올림 · 수평 이동, 마무리 들어 올림). robot_manager는 `OP_HOME`이 아닌 goal의 `speed <= 0`을 거절한다 |
| `recontact_margin_m` | double | ● | > 0, `lift_height_m` 미만 | 방향 전환 뒤 내림 목표 = 첫 접촉 z + 이 값. `drop_limit_m`보다 충분히 작아야 한다(계약 7.3절) |
| `recontact_speed_mps` | double | ● | > 0 | 방향 전환 뒤 내림 속도(저속) |
| `search_origin_pose` | double[7] | ● | 단위 quaternion | 탐색 기준점 상공. Base, `x y z qx qy qz qw`. 오일러로 두지 않는다(두산 ZYZ 규약과 헷갈린다) |
| `base_to_fixture` | double[3] | ● | 유한 | 작업대 원점의 Base 좌표. 평행 이동만(`units-frames.md`) |
| `support_z_m` | double | ● | 유한 | 지지면 높이(작업대 좌표). **0이 정당한 값이다** |
| `tip_radius_m` | double | ● | > 0 | 편향 보정 r. 반지름이다. sim에서는 `contact_detector.sim_tip_radius_m`과 같아야 한다 |
| `detect_latency_s` | double | ● | ≥ 0 | 편향 보정 지연 t. 뜻은 이슈 #69의 결정에 달려 있다 |
| `edge_round_radius_m` | double | ● | ≥ 0 | 부재 모서리 둥글림 R. 예리하면 0 |
| `edge_bias_offset_m` | double | ● | 유한(음수 가능) | 실측 나머지 편향. 스칼라 하나, 방향당 값, 진행 방향 + |
| `result_dir` | string | ● | 빈 문자열 아님 | result_store 경로. **상대 경로는 노드를 띄운 셸의 현재 디렉터리 기준**이다(`ws_cobot1`에서 launch하면 `ws_cobot1/data`, gitignore). `~`를 쓸 수 있다 |
| `event_wait_timeout_s` | double | ● | > 0 | Result가 가리킨 `ContactEvent`를 기다리는 한도 |
| `stop_confirm_timeout_s` | double | ● | > 0 | 정지 완료(`connected && !moving`)를 기다리는 한도. Result가 끝내 오지 않을 때의 대비(`motion_timeout_s` + 이 값)에도 쓴다 |
| `server_wait_timeout_s` | double | ● | > 0 | 상대 서버의 미기동 판단 |
| `result_frame_id` · `motion_frame_id` | string | — (`workpiece_fixture` · `base_link`) | | 프레임 이름(가칭) |
| `direction_order` | string[] | — (`POS_X, NEG_X, POS_Y, NEG_Y`) | 네 방향을 한 번씩 | 모서리 탐색 순서. **기동할 때만 읽는다**(상태 기계가 순서를 들고 있다). 나머지는 START 때마다 읽는다 |

실행에 쓰는 값 = yaml 파라미터 ← `/scan/set_config`로 받은 값 ← `RunScan.config_override`(`use_override=true`일 때, 그 작업에만). scan_manager가 직접 쓰는 것은 계약의 모션 6개뿐이고, 나머지 6개(`contact_threshold_n` · `edge_drop_m` · `debounce_n` · `over_force_n` · `target_force_n` · `drop_limit_m`)는 **받아서 보관만 한다**(전파 P01~P03은 T19b). 그 노드에 전파하기 전에는 실제로 적용된 값이 아니고 다른 노드의 현재 값도 모르므로, `SetConfig.applied` · `ScanResult.config` · 기록의 `config`에서 이 6개는 `NaN` + `*_set=false`다. SetConfig 응답의 detail에 "보관만(미전파, T19b)"로 이름을 밝힌다(웹이 안전 임계값이 바뀐 것으로 읽지 않게). 0을 채우지 않는다. `debounce_n`은 uint8이라 NaN을 실을 수 없으므로 `debounce_set`으로만 판단한다.

## 서버
노드가 뜨자마자 5개가 준비된다. 상대 노드가 없어도 된다(mqtt_bridge가 `server_is_ready()`로 본다).

| 이름 | 처리 |
|---|---|
| `/scan/run` | 시작 조건(BUSY → 파라미터 → 래치 → 연결)을 확인하고 시퀀스를 돈다. **기록(`begin_scan`)이 디스크에 만들어진 것을 확인한 뒤에 첫 모션을 보낸다**(못 만들면 로봇을 움직이지 않고 ERROR). `scan_id`가 이미 있는 기록과 겹치면 다시 발급한다. Result는 DONE · ERROR · STOPPED에서 돌려준다. `success`는 명령 전체(마무리 복귀 포함), `result.success`는 측정의 성공 여부다 |
| `/scan/home` | 휴지 phase에서만. `OP_HOME` 하나를 보낸다(경로 · 순서는 TBD). 안전 래치도, 측정 파라미터 누락도, **기록 실패(디스크 오류 등)도** 복귀를 막지 않는다(기록 실패는 ERROR 로그). 작업 기록이 있으면 `record_home_requested` · `record_home_finished`를 남긴다. `motion_timeout_s`가 없으면 거절된다(`real.yaml`은 TBD라 실기에서 먼저 채워야 한다) |
| `/scan/resume` | **T26 전까지 `NOT_SUPPORTED(107)`.** 상태 기계에 묻지 않으므로 phase가 바뀌지 않는다 |
| `/scan/stop` | `/robot/stop` 호출과 진행 중 goal cancel을 **함께** 보내고 접수를 바로 돌려준다. 정지 완료 확인 · 중단 위치 기록 · `STOP_CONFIRMED`는 시퀀스 스레드가 한다. **홈 복귀 · 재시작을 부르지 않는다.** 멈출 작업이 없어도 `/robot/stop`은 보낸다(멱등). `/robot/stop`의 응답은 기다리지 않되, 접수되지 않았으면 WARN 로그를 남긴다. START · HOME의 접수와 겹치지 않게 명령 접수 락을 쥐고 처리하고, 시퀀스는 goal을 보내기 직전에 작업 락 안에서 중지를 한 번 더 본다(중지 접수 뒤에 goal이 나가지 않는다) |
| `/scan/set_config` | 동작 중이면 `BUSY`, 범위 밖이면 `INVALID_VALUE`(같이 온 정상값도 적용하지 않는다). `*_set`인 항목만 적용. 전파는 T19b |

**goal 거절 방식.** ROS 2의 goal reject에는 사유 필드가 없고, main의 mqtt_bridge는 reject를 `BUSY`로 고정해 낸다. 그래서 **goal은 항상 accept하고, 거절할 요청은 phase를 바꾸지 않은 채 바로 Result(`success=false`, `reason_code`=1xx, `scan_id=""`)로 끝낸다(abort).** 실제 사유(`SAFETY_LATCHED` · `INVALID_VALUE` …)가 `scan/command_result`로 웹에 간다. 계약 5.1~5.3절의 "거절" 문구와 다르므로 계약 문서 PR에서 문구를 맞춘다. 거절 처리는 `ScanManager._reject` 한 곳에 있다.
Action의 cancel 요청은 받지 않는다. 작업 중지는 `/scan/stop` 하나로 한다(정지 확인과 중단 위치 기록이 거기에 묶여 있다). Feedback은 보내지 않는다(같은 내용이 `/scan/state`에 있다).

## 발행
| 토픽 | 시점 |
|---|---|
| `/scan/state` | 상태가 바뀔 때 + 주기. 주기 발행이 방금 나간 변경을 옛 상태로 덮어쓰지 않게 순번으로 거른다 |
| `/scan/result` | 작업 종료 시 1회. 정상이면 GEOMETRY 끝(복귀를 기다리지 않는다, `finished_at`도 그 시각). 실패 · 중단이면 확보한 값만 유효하고 나머지는 `NaN` + `*_valid=false`(좌표는 작업대 프레임). 거절된 명령의 `RunScan.Result.result`도 전부 `NaN`이다. `stamp`는 발행할 때마다 새로 찍는다(mqtt_bridge의 중복 제거 키). 마무리 복귀가 실패해도 다시 발행하지 않는다 |
| `/scan/log` | 시작 · 측정 확정 · 무시한 이벤트 · 거절 · 실패(원인 · 단계 · 위치) · 중지. 좌표가 판정 좌표인지 정지 좌표인지 message에 적는다. `pose`는 원본(`ContactEvent.pose` · `ExecuteMotion.Result.pose`)을 자세까지 그대로 싣고, `Result.pose`가 채워지지 않았으면(`pose_stamp=0`. 계약에 유효 플래그가 없어 이렇게 읽는다) 정지 좌표로 쓰지 않으며, 관련 좌표가 없으면 위치 · 자세 모두 `NaN` + `pose_valid=false`다 |

`result.json`(원본)은 GEOMETRY에서만 쓴다(성공 또는 형상 계산 실패). 모션 실패 · 중단으로 끝난 작업은 `/scan/result`만 발행하고 원본을 쓰지 않는다. 원본은 한 번만 쓸 수 있어서, 재시작(T26)이 끝까지 간 뒤에 쓸 자리를 남겨 둔다.

## executor · 스레드
`MultiThreadedExecutor`(스레드 수는 CPU 수, 최소 4). 콜백 그룹은 넷이다: 구독(`/robot/status` · `/safety/status` · `/contact/event`, 순서 보장), Action 서버(Reentrant), Service 서버, 클라이언트(Reentrant). 쓰기 전용 스레드 1개가 result_store의 모든 쓰기를 넣은 순서대로 한다.

시퀀스는 `/scan/run`의 execute 콜백 안에서 돌며 executor 스레드 하나를 차지한다. 교착이 없는 이유:
- 시퀀스 스레드는 **락을 쥔 채 기다리지 않는다.** 상대 노드의 응답은 `add_done_callback`이 세우는 `threading.Event`로 기다리고, 콜백 안에서 spin하지 않는다. 그 완료 콜백 · 구독 · `/scan/stop`은 다른 그룹이라 남은 스레드에서 돈다.
- 상태 기계의 `on_change`(락 안)는 발행과 쓰기 큐 투입만 한다. 디스크 쓰기 · 서비스 호출 · 대기가 없어서 `/scan/stop`의 `request(STOP)`이 디스크를 기다리지 않는다.
- 락의 순서는 한 방향이다: (명령 접수 락 →) 작업 락 → 상태 기계 락 → 발행 락. 주기 발행은 상태 기계 락을 놓은 뒤에 발행 락을 잡는다.
- `/scan/stop` 콜백은 아무것도 기다리지 않는다(`call_async` · `cancel_goal_async`).
- 상태 전이(`notify`)는 작업 락 안에서 한다. `/scan/stop`이 "접수 직전의 Snapshot"을 뜨고 STOP을 요청하는 사이에 전이가 끼지 않아 중단 기록이 실제와 같다.
- **추적하지 못하는 모션을 남기지 않는다.** goal 응답이 `server_wait_timeout_s` 안에 오지 않거나 Result가 끝내 오지 않으면 실패로 끝내면서 `/robot/stop`(멱등)을 요청하고, 늦게 수락된 goal은 바로 취소한다. 수락된 goal을 두고 예외로 빠져나갈 때도 취소한다. 홈 복귀 · 재시작은 부르지 않는다.
- 모든 기다림에는 파라미터로 준 한도가 있고, 종료 요청이 오면 바로 빠져나온다.

종료: SIGINT가 두 번 와도(launch의 Ctrl-C) 트레이스백 없이 코드 0으로 끝난다. 큐에 남은 기록을 디스크에 쓴 뒤 닫는다. **모션 도중에 노드가 죽으면 robot_manager는 그 모션을 끝까지(`max_distance` · `timeout`) 실행한다.** 종료할 때 `/robot/stop`을 보내지 않는다(context가 이미 내려가 있다) → T19b에서 다룬다.

## 상태 기계

### 입력
입력은 두 종류다. 이름은 T19 · T26이 그대로 쓰도록 고정한다.

**Command** — 관제자 명령. `sm.request(Command.X, conditions=..., scan_id=...)`. 허용되지 않으면 예외 없이 `Outcome(accepted=False, reason=<ReasonCode>)`를 돌려준다. 그 값을 goal 거절 · Service 응답에 그대로 싣는다.

| Command | 대응 인터페이스 | 필요한 입력 |
|---|---|---|
| `START` | `/scan/run` goal | `scan_id`(새로 발급, 필수) · `conditions` |
| `STOP` | `/scan/stop` | 없음 |
| `HOME` | `/scan/home` goal | `conditions` |
| `RESUME` | `/scan/resume` goal | `scan_id`(goal 값, `""` = 가장 최근 중단 작업) · `conditions` |
| `SET_CONFIG` | `/scan/set_config` | 없음. phase는 바뀌지 않고 접수 여부만 판정한다 |

`Conditions(robot_connected, safety_latched)`는 명령 시점의 `/robot/status.connected`와 `/safety/status.latched`다. `None`은 "아직 받지 못함"이고 거절 사유가 된다.

**Signal** — 노드 내부의 진행 보고. `sm.notify(Signal.X)`. 현재 phase에서 허용되지 않으면 `InvalidTransition`을 던진다. 조용히 무시하지 않는다. 경합(예: 중지 직후에 도착한 EDGE)을 어떻게 다룰지는 호출 측이 정한다.

| Signal | 보내는 시점 |
|---|---|
| `PREPARE_DONE` | 시작 조건 점검과 tare가 끝났다 |
| `TOP_FOUND` | 윗면 접촉을 확보했다 |
| `EDGE_FOUND` | 모서리 1개를 확보했다 |
| `GEOMETRY_DONE` | 형상 계산 · 원본 저장 · `/scan/result` 발행이 끝났다 |
| `HOMING_DONE` | 홈 복귀가 끝났다(마무리 · 안전복귀 공용) |
| `STOP_CONFIRMED` | `/robot/status`로 `connected && !moving`을 확인했다 |
| `RESUME_READY` | 재시작 준비가 끝났다 |
| `FAILED` | 실패 · 안전 이상. `reason_code`(0이 아닌 ReasonCode)가 필수다 |

### 전이도
```mermaid
stateDiagram-v2
    [*] --> IDLE
    IDLE --> PREPARING: START
    DONE --> PREPARING: START
    ERROR --> PREPARING: START
    STOPPED --> PREPARING: START

    PREPARING --> TOP_SEARCH: PREPARE_DONE
    TOP_SEARCH --> EDGE_SEARCH: TOP_FOUND (0/4)
    EDGE_SEARCH --> EDGE_SEARCH: EDGE_FOUND (n < 4, 다음 방향)
    EDGE_SEARCH --> GEOMETRY: EDGE_FOUND (4/4)
    GEOMETRY --> HOMING: GEOMETRY_DONE (마무리 복귀)
    HOMING --> DONE: HOMING_DONE (마무리 복귀)

    state "동작 중: PREPARING · TOP_SEARCH · EDGE_SEARCH · GEOMETRY · HOMING · RESUMING" as ACTIVE
    ACTIVE --> STOPPING: STOP
    ACTIVE --> ERROR: FAILED
    STOPPING --> STOPPED: STOP_CONFIRMED
    STOPPING --> ERROR: FAILED

    STOPPED --> RESUMING: RESUME
    RESUMING --> ACTIVE: RESUME_READY (중단됐던 단계)

    state "휴지: IDLE · DONE · ERROR · STOPPED" as REST
    REST --> HOMING: HOME (안전복귀)
    HOMING --> REST: HOMING_DONE (안전복귀, 출발했던 phase)
```
`ACTIVE` · `REST`는 그림을 줄이려고 묶은 것이며 phase가 아니다. 위쪽의 phase들과 같은 것이다.

### 전이표
표에 없는 조합은 허용되지 않는다. Command는 거절하고 Signal은 `InvalidTransition`이다. 코드의 `COMMAND_TRANSITIONS` · `SIGNAL_TRANSITIONS`가 이 표이며, 테스트가 11개 phase × 전 이벤트를 전수 확인한다.

| 현재 phase | 이벤트 | 다음 phase | 비고 |
|---|---|---|---|
| IDLE · DONE · ERROR · STOPPED | `START` | PREPARING | 새 `scan_id`, progress 0. 이전 재개 지점 · 실패 사유를 버린다 |
| IDLE · DONE · ERROR · STOPPED | `SET_CONFIG` | 그대로 | 접수만 한다 |
| IDLE · DONE · ERROR · STOPPED | `HOME` | HOMING | 안전복귀. 이 시점부터 그 작업의 재시작은 `NOT_SUPPORTED` |
| PREPARING · TOP_SEARCH · EDGE_SEARCH · GEOMETRY · HOMING · RESUMING | `STOP` | STOPPING | 접수 ≠ 정지 완료 |
| STOPPING · IDLE · DONE · ERROR · STOPPED | `STOP` | 그대로 | 멱등 접수 |
| STOPPED | `RESUME` | RESUMING | 재개 지점이 있을 때만 |
| PREPARING | `PREPARE_DONE` | TOP_SEARCH | |
| TOP_SEARCH | `TOP_FOUND` | EDGE_SEARCH | 0/4, 첫 방향 |
| EDGE_SEARCH | `EDGE_FOUND` | EDGE_SEARCH 또는 GEOMETRY | progress +1. 4/4면 GEOMETRY |
| GEOMETRY | `GEOMETRY_DONE` | HOMING | 마무리 복귀(7.4절) |
| HOMING | `HOMING_DONE` | DONE 또는 출발했던 휴지 phase | 마무리 복귀 → DONE, 안전복귀 → 출발 phase |
| STOPPING | `STOP_CONFIRMED` | STOPPED | |
| RESUMING | `RESUME_READY` | PREPARING · TOP_SEARCH · EDGE_SEARCH · GEOMETRY | 중단됐던 단계. progress · 방향 · `scan_id` 유지 |
| PREPARING · TOP_SEARCH · EDGE_SEARCH · GEOMETRY · HOMING · RESUMING · STOPPING | `FAILED` | ERROR | 자동 홈 복귀 없음. `sm.failure`에 사유 · 실패한 phase |

### 거절 사유
값은 계약 6.1절 ReasonCode와 같다. 여러 조건에 걸리면 위에서부터 먼저 걸린 것을 돌려준다.

| Command | 판정 순서 |
|---|---|
| `START` | `BUSY`(100) → `SAFETY_LATCHED`(103) → `ROBOT_DISCONNECTED`(104) |
| `SET_CONFIG` | `BUSY` |
| `HOME` | `BUSY` → `ROBOT_DISCONNECTED`. 안전 래치는 막지 않는다 |
| `RESUME` | `BUSY` → `NO_RESUMABLE_SCAN`(105) 또는 `NOT_SUPPORTED`(107) → `SAFETY_LATCHED` → `ROBOT_DISCONNECTED` |
| `STOP` | 거절 없음 |

`RESUME`의 105 · 107:

| 상황 | 사유 |
|---|---|
| IDLE · DONE | `NO_RESUMABLE_SCAN` |
| 마무리 HOMING 중에 중지된 작업(7.4절) | `NO_RESUMABLE_SCAN` |
| goal의 `scan_id`가 중단된 작업과 다르다 | `NO_RESUMABLE_SCAN` |
| 중지 뒤에 안전복귀(`HOME`)를 접수했다(끝까지 갔는지와 무관, 5.3절) | `NOT_SUPPORTED` |
| ERROR(이상 상태별 재시작 허용 조건이 TBD, 9장) | `NOT_SUPPORTED` |

### 세 명령은 독립이다
- `STOP`은 STOPPING으로만 간다. STOPPING에서 갈 수 있는 곳은 STOPPED(`STOP_CONFIRMED`)와 ERROR(`FAILED`)뿐이다.
- STOPPED를 떠나는 Signal은 없다. 관제자의 `START` · `HOME` · `RESUME`만 STOPPED를 떠나게 한다.
- 실패(ERROR)도 자동으로 홈 복귀하지 않는다.
- 이 세 가지는 `test/test_commands.py`가 전이표 수준에서 고정한다.

### 상태 필드
| 필드 | 규칙 |
|---|---|
| `scan_id` | IDLE에서만 `""`. DONE · ERROR · STOPPED에서도 유지한다 |
| `direction` | EDGE_SEARCH에서만 값이 있다. 그 밖은 `NONE`. 순서는 +X → −X → +Y → −Y(생성자 인자 `direction_order`로 바꿀 수 있다) |
| `progress` | 확보한 모서리 수. 다음 `START` 전까지 유지한다. `progress_total`은 4 |
| `motion_id` | `sm.set_motion_id()`로 넣는다. 휴지 phase에 들어가면 0으로 돌아간다 |

### 사용 예
```python
from scan_manager.contract_enums import Reason
from scan_manager.state_machine import Command, Conditions, ScanStateMachine, Signal

sm = ScanStateMachine(on_change=publish)      # 상태가 바뀔 때마다 Snapshot으로 publish 호출
cond = Conditions(robot_connected=True, safety_latched=False)

out = sm.request(Command.START, conditions=cond, scan_id='20260918-210000-0001')
if not out.accepted:
    reject_goal(int(out.reason), out.detail)   # 예: 100 BUSY
sm.notify(Signal.PREPARE_DONE)                 # → TOP_SEARCH
sm.notify(Signal.TOP_FOUND)                    # → EDGE_SEARCH 0/4 +X
sm.notify(Signal.EDGE_FOUND)                   # → EDGE_SEARCH 1/4 −X
sm.notify(Signal.FAILED, reason_code=Reason.NO_EDGE, detail='max_distance')   # → ERROR
```
