# robot_manager (담당: 학민)

두산 M0609 + RG2를 부르는 **유일한** 노드다. 두산 단위(mm · deg)와 계약 단위(m · rad · quaternion)의
변환도 여기에서만 한다(`docs/contracts/units-frames.md`).

| 상태 | 내용 |
|---|---|
| T15 | `/robot/sample` · `/robot/status` 발행 |
| T13 (이 PR) | `/robot/execute_motion` Action (DESCEND · SLIDE · MOVE_TO · HOME) |
| T14 | `/robot/stop`(move_stop 서비스 서버), 예외 주입 테스트 |
| phase 2 P1 (현지) | `/robot/execute_path` Action — 용접 경유점 경로 (line · spline). 아래 "ExecutePath" |

## 구조
| 파일 | 하는 일 | ROS · 두산 의존 |
|---|---|---|
| `conversions.py` | posx(mm · deg ZYZ) → Pose(m · quaternion), 외력 → Wrench | 없음 (ROS 없이 테스트) |
| `motions.py` | Pose → posx 역변환, SLIDE 방향 벡터, 이동 거리, 하강 제한 | 없음 |
| `motion_state.py` | 위치 변화로 이동 여부 판정 | 없음 |
| `call_queue.py` | 두산 호출을 한 줄로 줄 세우기 | 없음 |
| `dsr_client.py` | `dsr_controller2` 서비스 클라이언트 | `dsr_msgs2` |
| `paths.py` | ExecutePath 검사(604 사유) · 경로 길이 · 진행 · posx 목록 | 없음 |
| `path_executor.py` | ExecutePath 실행(line · spline) 과 감시 | rclpy 타입, `dsr_msgs2` |
| `robot_manager.py` | 노드. 조회 → 발행 | rclpy, `dsr_msgs2` |

`dsr_msgs2`는 `ws_dsr`에만 있고 CI에는 없다. 그래서 `package.xml`에 의존으로 넣지 않고 노드에서만
import한다. 순수 계산 모듈과 그 테스트는 두산 드라이버 없이 돈다.

## 실행
```bash
sod                                     # ws_dsr
source ~/ws_cobot_pjt/ws_cobot1/install/setup.bash
ros2 run robot_manager robot_manager    # 또는 contact_scan_bringup 의 launch
ros2 topic echo /robot/sample contact_scan_interfaces/msg/RobotSample --qos-reliability best_effort
```
`/robot/sample`은 BEST_EFFORT다. `ros2 topic echo`는 기본이 RELIABLE이라 옵션을 주지 않으면 아무것도 보이지 않는다.

## 두산 호출 규칙 (지키지 않으면 드라이버가 멈춘다)
- **한 번에 하나씩만 부른다.** `get_current_posx`와 `get_tool_force`를 동시에 부르자 `dsr_controller2`가
  모든 서비스 응답을 멈췄고, 브링업을 다시 띄워야 회복됐다(2026-09-20 Virtual). 그래서 조회를
  `posx → force → (주기적으로) get_robot_state` 한 줄로 잇는다. T13의 모션 호출도 이 줄에 넣는다.
- **응답을 기다리며 콜백을 막지 않는다.** `call_async` + 콜백만 쓴다(BRD 4.2.3).
- 실패한 값은 0으로 채우지 않는다. NaN으로 두고 `valid=false`로 발행한다.

## ExecuteMotion (T13)

| 동작 | 어떻게 실행하나 | 정상 종료 |
|---|---|---|
| `OP_MOVE_TO` | `move_line` ABS (goal.target 을 posx 로 역변환) | `TARGET_REACHED` |
| `OP_DESCEND` | `move_line` REL −z, 거리 `max_distance` | `CONTACT` (이벤트). 없으면 `MAX_DISTANCE` + `NO_CONTACT` |
| `OP_SLIDE` | 순응 제어 → −z 목표 힘(`slide_target_force_n`) → `move_line` REL 방향 | `EDGE` (이벤트). 없으면 `MAX_DISTANCE` + `NO_EDGE` |
| `OP_HOME` | `move_joint` ABS (`home_joint_deg`) | `TARGET_REACHED` |

- **동시에 1개만 받는다.** 실행 중이면 goal 을 거절한다(BUSY). 미연결 · 잘못된 값도 거절한다.
- **`/robot/stop` 은 접수만 한다(계약 4.1).** 요청은 정지를 확인할 때까지 남고, 남아 있는 동안 새 goal 을 거절한다(`STOP_REQUESTED`).
  - 동작 중: `watch` 가 처리해 `REASON_STOP_REQUESTED` 로 끝낸다. 수락 직후 · 실행 전에 온 요청도 `watch` 의 첫 확인에서 처리된다. 정지를 확인하지 못하면 `ROBOT_ERROR` 로 끝내고 요청은 **남긴다**(동작 없음 경로와 같다, #113)
  - 동작 없음: 별도 스레드가 `move_stop` 을 보내고, 정지를 확인하면 지운다. 확인하지 못하면 남겨 goal 을 계속 거절한다
  - 동작이 끝나는 사이에 온 요청: 결과는 그대로 두고 `finally` 에서 정지를 확인한 뒤 지운다
  - 지울 때는 자기가 처리한 요청일 때만 지운다(그 사이 새로 온 요청은 남긴다)
  - **안전복귀(`OP_HOME`)는 남은 요청이 있어도 거절하지 않는다**(#115). 관제자가 직접 누른 명령이라 확인으로 본다. 출발 전에 `move_stop` 으로 정지를 한 번 더 시도하고 **수락 시점에 남아 있던 요청만** 지운다. 확인에 실패해도 오류 로그를 남기고 출발한다. HOME **도중에** 새로 온 정지 요청은 HOME 을 멈춘다
  - 그 밖의 동작이 `STOP_REQUESTED` 로 거절되면: 안전복귀를 누르거나, 멈춘 것을 눈으로 확인한 뒤 `/robot/stop` 을 다시 부른다(정지 스레드가 다시 확인하고, 확인되면 지운다). 드라이버 무응답이면 물리 비상정지 → robot_manager 재기동
- **이벤트 대조**(계약 5.4): `ContactEvent.motion_id` 가 현재 goal 과 같고 동작이 맞을 때만 정지한다.
  `TYPE_OVER_FORCE` 는 대조 없이 항상 정지한다.
- **취소**: 취소 접수와 실제 정지 완료는 다르다. `move_stop` 뒤 `moving` 이 false 가 될 때까지 기다린 다음 결과를 돌려준다.
- **SLIDE 하강 제한**: 첫 샘플 z 기준으로 `drop_limit_m` 를 넘으면 정지하고 `DROP_LIMIT`(205) 로 끝낸다(계약 7.2 1차 감시).
- **순응 · 힘 제어는 `finally` 에서 해제**한다. 해제 호출이 실패하면 `compliance_released=false` 로 사실대로 보고한다
  - **켜는 호출을 보내기 전에** 해제 대상으로 표시한다. 켜는 호출이 응답 시간 초과여도 컨트롤러는 이미 켰을 수 있어서다. 켜지 않은 것을 해제하다 실패하면 `compliance_released=false` 가 된다(모르면 해제됐다고 하지 않는다)
  - 해제 순서는 힘 제어(`release_force`) → **`release_force_time_s` 대기** → 순응 제어(`release_compliance_ctrl`). 응답이 램프보다 먼저 올 수 있어 기다린다(매뉴얼 5.1.4 예제)
  - `compliance_released=true` 는 **해제 호출이 성공했다**는 뜻이다. 실제로 위치 제어로 돌아왔는지 조회로 확인하는 것은 후속(`GetControlMode`, 실기 확인 필요)
  - 시험(`test_node.py`, T14): 예외 주입 · 취소 · 정지 요청 · 이벤트 · 시간 초과 · 하강 제한 · 정상 종료 7경로에서 해제, 켜기 시간 초과 2경우, 해제 실패 보고, 힘 제어를 안 쓰는 동작은 해제 호출 없음
  (실패 경로는 계약에서 TBD다. 성공한 것으로 적지 않는다).
- `OP_HOME` 의 목적지는 관절각(`home_joint_deg`)이다. 계약 5.4 는 `home_pose` 라고 적었지만, T03 이 홈을
  관절각으로 확정했고 `OP_HOME` 은 movej 로 간다(`units-frames.md`). 계약 이름이 아닌 파라미터라 바꿔도 된다.

## ExecutePath (phase 2 P1)
계약 `docs/phase2/weld-ros-interfaces.md` 5.2 · 6장, 결정 D31. weld_manager 가 보낸 경유점(위빙 지그재그 포함)을 차례로 지난다.
접촉 판정 · 힘 제어는 없다. 실행 중 `/robot/sample.operation = OP_WELD_PATH(5)`, `motion_id = goal.motion_id`.

| `path_mode` | 어떻게 | 확인 수준 |
|---|---|---|
| `line` (기본) | 점마다 `move_line` ABS ASYNC(amovel) → 멈춤 · 도착 확인 → 다음 점. **점마다 선다**(D8 허용) | amovel 은 1차에서 실기 확인. 경로로는 Virtual 확인(2026-09-24): 21 점 18.2 s, 점 통과 0.0 mm, 점마다 약 0.5 s 멈춤 |
| `spline` | 첫 점까지 amovel 직선(계약 "첫 점까지도 직선") → 나머지를 `move_spline_task` ASYNC(amovesx, opt=CONST) 한 번 | **Virtual 호출 확인(2026-09-24): 쓰지 않는다.** ASYNC 인데 응답이 점당 약 25~32 ms 늦고(21 점 0.5~0.67 s, 100 점 2.4~3.2 s) 그동안 샘플이 끊겨 SAMPLE_STALE 에 걸린다(`docs/env/api-check-log.md`) |

- **goal 자리를 ExecuteMotion 과 같이 쓴다.** 어느 한쪽이 실행 중이면 다른 쪽도 BUSY 로 거절. 미연결 · 처리 안 된 정지 요청 ·
  순응 · 힘 제어가 켜진 상태(안전망) · `path_*` 파라미터가 없거나 못 쓰는 값도 거절(`GoalResponse.REJECT`)
- **경로 자체의 문제는 수락한 뒤** 움직이지 않고 `REASON_REJECTED` + `PATH_REJECTED(604)` 로 끝낸다(ROS 2 거절에는 사유를 실을 수 없다):
  빈 목록 · `path_max_points` 초과 · 속도 ≤ 0 또는 `> path_max_speed_mps` · 프레임이 `frame_id` 가 아님 · 값이 숫자가 아님 ·
  `path_tolerance_m ≤ 0` · **경유점 하나라도 `z < path_min_z_m`**(수락 시점에 전부 본다)
- **이동 명령이 실패하거나 응답이 늦으면 세우고 확인한 뒤** 204 로 끝낸다. 컨트롤러는 늦게 받아 움직이고 있을 수 있다(Virtual 에서 spline 100 점이 "실패" 뒤 실행된 것을 확인)
- 구간마다 1차 `watch` 와 같은 규칙으로 본다: 위치로 확인된 이동(`moved_min_m`)만 "움직였다", 명령 뒤 `arrival_grace_s` 안에
  출발하지 않으면 `move_stop` 뒤 다시 보낸다(`move_restart_max`, #153), **멈췄는데 목표에서 `path_tolerance_m` 밖이면 `ROBOT_ERROR(204)`**
  (중간 점도 같은 허용치). 취소 · `/robot/stop` · 과대 외력 · 시간 초과는 `stop_robot` 으로 멈춤까지 확인한다
- 접촉 이벤트(CONTACT · EDGE)로는 멈추지 않는다. `on_event` 가 `goal.operation` 을 읽으므로 goal 자리에는
  `operation = OP_WELD_PATH` 를 가진 어댑터(`PathGoal`)를 넣는다(기존 `on_event` 무수정)
- Result `waypoints_done` 은 line 이면 센 값, spline 이면 위치로 추정한 값(계약 허용). `distance_travelled` 는 출발점부터 경로를 따라 잰 거리
- **드라이버 주의**(소스 확인 2026-09-24, `dsr_controller2.cpp` 458~583행): ASYNC `move_line` 은 `radius` 를 버린다(블렌딩 없음).
  `move_spline_task` 는 요청을 검사하지 않는다 — 100 점 고정 배열, `pos.at(i)` 를 `pos_cnt` 번, 점마다 `data[0..5]`.
  `dsr_client.move_spline_request` 가 세 가지를 모두 막는다

| 파라미터 (계약 이름, 기본값 없음) | sim / real | 설명 |
|---|---|---|
| `path_mode` | `line` / `line` | `line` \| `spline` |
| `path_max_points` | 100 / 100 | spline 이면 100 을 넘을 수 없다(드라이버 배열) |
| `path_max_speed_mps` | 0.100 / 0.100 | 경로 속도 상한 [m/s] |
| `path_min_z_m` | 0.403 / 0.100 | Base z 하한 [m]. sim 박스 밑면 + 3 mm / 작업대 표면 0.095 + 테이프 2 mm + 여유 3 mm(계약 출발값) |
| `path_acc_ratio` | 4.0 / 4.0 | 가속 = 이 값 × 속도 [1/s] |

시험: `test_paths.py`(순수) · `test_dsr_path_requests.py`(요청 메시지) · `test_node_path.py`(가짜 팔로 노드 전체: 거절 · 604 · line 완주 ·
operation 5 · 정지 · 과대 외력 · 접촉 이벤트 무시 · 취소 · 시간 초과 · 재출발 · 도중 정지 · spline).

## 파라미터
| 이름 | 기본값 | 설명 |
|---|---|---|
| `frame_id` | `base_link` | pose · wrench 프레임 (가칭) |
| `dsr_namespace` | `dsr01` | 서비스 접두사 `/<ns>/dsr_controller2/` |
| `sample_rate_hz` | 50.0 | 조회 시도 주기. 실측은 37.6 Hz (Virtual) |
| `status_rate_hz` | 10.0 | `/robot/status` 발행 주기 |
| `service_timeout_s` | 0.5 | 이 시간 안에 응답이 없으면 무효 샘플로 발행 |
| `moving_eps_m` | 0.0002 | 이동 판정 문턱 |
| `moving_window_s` | 0.3 | 이동 판정 창 |
| `slide_target_force_n` | 0.0 | **계약 이름.** SLIDE −z 목표 힘. 0 이면 SLIDE 를 거절한다 |
| `drop_limit_m` | 0.005 | **계약 이름.** SLIDE 하강 제한. safety_monitor 와 같은 값 |
| `home_joint_deg` | (없음) | `OP_HOME` 목적지 관절각 6개. 없으면 `OP_HOME` 을 거절한다 |
| `home_speed_deg_s` | 20.0 | `OP_HOME` 관절 속도 |
| `compliance_stiffness` | [3000, 3000, 3000, 200, 200, 200] | `task_compliance_ctrl` 강성 |
| `motion_timeout_s` | 60.0 | goal.timeout 이 0 일 때 쓰는 제한 시간 |
| `stop_settle_s` | 1.5 | 정지 명령 후 멈춤을 기다리는 시간 |
| `feedback_period_s` | 0.1 | Action feedback 발행 주기 |

계약 이름(`slide_target_force_n` · `drop_limit_m`)의 값은 `contact_scan_bringup/config/*.yaml`에 둔다(T05, 현지). `slide_target_force_n` 과 `home_joint_deg` 는 yaml 에 값이 들어와야 SLIDE · HOME 이 동작한다.
