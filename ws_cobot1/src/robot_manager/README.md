# robot_manager (담당: 학민)

두산 M0609 + RG2를 부르는 **유일한** 노드다. 두산 단위(mm · deg)와 계약 단위(m · rad · quaternion)의
변환도 여기에서만 한다(`docs/contracts/units-frames.md`).

| 상태 | 내용 |
|---|---|
| T15 | `/robot/sample` · `/robot/status` 발행 |
| T13 (이 PR) | `/robot/execute_motion` Action (DESCEND · SLIDE · MOVE_TO · HOME) |
| T14 | `/robot/stop`(move_stop 서비스 서버), 예외 주입 테스트 |

## 구조
| 파일 | 하는 일 | ROS · 두산 의존 |
|---|---|---|
| `conversions.py` | posx(mm · deg ZYZ) → Pose(m · quaternion), 외력 → Wrench | 없음 (ROS 없이 테스트) |
| `motions.py` | Pose → posx 역변환, SLIDE 방향 벡터, 이동 거리, 하강 제한 | 없음 |
| `motion_state.py` | 위치 변화로 이동 여부 판정 | 없음 |
| `call_queue.py` | 두산 호출을 한 줄로 줄 세우기 | 없음 |
| `dsr_client.py` | `dsr_controller2` 서비스 클라이언트 | `dsr_msgs2` |
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
- **SLIDE 하강 제한**: 기준 z 보다 `drop_limit_m` 를 **초과**해 내려가면 정지하고 `DROP_LIMIT`(205) 로 끝낸다(계약 7.2 1차 감시. 정확히 한계면 걸리지 않는다).
  - **기준 z = 이 노드가 `operation = OP_SLIDE` 로 발행한 첫 유효 샘플의 z** 다(v0.1.17). safety_monitor(2차)가 잡는 것과 **같은 메시지의 같은 값**이다. 실행 직전의 마지막 위치를 쓰면 순응을 켜며 z 가 약 0.7 mm 올라온 만큼 두 기준이 어긋나고, 그러면 2차의 여유가 의미를 잃는다.
  - 첫 `OP_SLIDE` 샘플이 나가기 전까지는 실행 직전의 마지막 위치를 임시 기준으로 쓴다. **감시를 끄지 않는다.**
  - 2차(safety_monitor)는 같은 기준 z 에 `drop_limit_margin_m` 를 더한 값에서 걸린다(real · sim 모두 1차 5 mm · 2차 9 mm). 1차 = 정상 동작의 제한, 2차 = 최후 방어선 + 래치.
  - 스텝 모드에서도 **매 대기마다** 1차를 본다. 설정 검사가 `step_press_max_m + step_drop_m < drop_limit_m` 을 강제한다.
- **순응 · 힘 제어는 `finally` 에서 해제**한다. 해제 호출이 실패하면 `compliance_released=false` 로 사실대로 보고한다
  - **켜는 호출을 보내기 전에** 해제 대상으로 표시한다. 켜는 호출이 응답 시간 초과여도 컨트롤러는 이미 켰을 수 있어서다. 켜지 않은 것을 해제하다 실패하면 `compliance_released=false` 가 된다(모르면 해제됐다고 하지 않는다)
  - 해제 순서는 힘 제어(`release_force`) → **`release_force_time_s` 대기** → 순응 제어(`release_compliance_ctrl`). 응답이 램프보다 먼저 올 수 있어 기다린다(매뉴얼 5.1.4 예제)
  - `compliance_released=true` 는 **해제 호출이 성공했다**는 뜻이다. 실제로 위치 제어로 돌아왔는지 조회로 확인하는 것은 후속(`GetControlMode`, 실기 확인 필요)
  - 시험(`test_node.py`, T14): 예외 주입 · 취소 · 정지 요청 · 이벤트 · 시간 초과 · 하강 제한 · 정상 종료 7경로에서 해제, 켜기 시간 초과 2경우, 해제 실패 보고, 힘 제어를 안 쓰는 동작은 해제 호출 없음
  (실패 경로는 계약에서 TBD다. 성공한 것으로 적지 않는다).
- `OP_HOME` 의 목적지는 관절각(`home_joint_deg`)이다. 계약 5.4 는 `home_pose` 라고 적었지만, T03 이 홈을
  관절각으로 확정했고 `OP_HOME` 은 movej 로 간다(`units-frames.md`). 계약 이름이 아닌 파라미터라 바꿔도 된다.

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
| `drop_limit_m` | 0.005 | **계약 이름.** SLIDE 하강 제한(1차). safety_monitor 와 같은 값. 2차는 거기에 `drop_limit_margin_m`(4 mm)을 더한 9 mm 다 |
| `home_joint_deg` | (없음) | `OP_HOME` 목적지 관절각 6개. 없으면 `OP_HOME` 을 거절한다 |
| `home_speed_deg_s` | 20.0 | `OP_HOME` 관절 속도 |
| `compliance_stiffness` | [3000, 3000, 3000, 200, 200, 200] | `task_compliance_ctrl` 강성 |
| `motion_timeout_s` | 60.0 | goal.timeout 이 0 일 때 쓰는 제한 시간 |
| `stop_settle_s` | 1.5 | 정지 명령 후 멈춤을 기다리는 시간 |
| `feedback_period_s` | 0.1 | Action feedback 발행 주기 |

계약 이름(`slide_target_force_n` · `drop_limit_m`)의 값은 `contact_scan_bringup/config/*.yaml`에 둔다(T05, 현지). `slide_target_force_n` 과 `home_joint_deg` 는 yaml 에 값이 들어와야 SLIDE · HOME 이 동작한다.

## SLIDE 누름 목표를 상태에 싣는다 (계약 3.2, v0.1.17 결정 4)

`slide_target_force_n` 은 `DR_FC_MOD_REL` 이라 **"설정한 증분"** 이지 실제 누름이 아니다. 실제 누름은 SLIDE 가
어디서 시작하느냐에 따라 달라진다(9/22 실기 방향별 1.5~8.6 N). 그래서 세 값을 한 자리에 섞지 않고 `RobotStatus` 에
각각 싣는다.

| 필드 | `force` 모드 | `step` 모드 |
|---|---|---|
| `slide_mode` | `"force"` | `"step"` |
| `slide_force_setpoint_n` | 설정 증분(`slide_target_force_n`) | **NaN** |
| `slide_force_baseline_n` | `set_desired_force` 를 부른 시점의 Fz | **NaN** |
| `slide_force_estimate_n` | 기준 + 설정 = **추정** 최종 누름 | **NaN** |
| `step_press_lo_n` · `step_press_hi_n` | NaN | 목표 누름 ΔFz 띠(`step_follow_lo_n` ~ `step_follow_hi_n`) |

- **`slide_force_estimate_n` 을 실측으로 표시하면 안 된다.** 힘 제어 중의 조회 Fz 는 1 N 안팎이 나와 "실측 누름"으로
  쓰면 오히려 오해를 부른다. 그래서 "실측 누름"이라는 값은 만들지 않는다.
- 기준선을 모르면 `baseline` 과 `estimate` 가 **NaN** 이다. 0 으로 채우면 "설정값 = 실제 누름"이라는 거짓이 된다(규칙 4).
- **`step` 모드에서는 REL 세 값이 제어 목표가 아니다.** 스텝 모드는 순응 · 힘 제어를 아예 켜지 않는다.
- mqtt_bridge 가 NaN → `null` 로 바꿔 `robot/status` 로 보낸다(`docs/contracts/mqtt-schema.md`).

**`step_max_force_n`(12 N)과 `over_force_n`(30 N)은 다른 것이다** (결정 8). 12 N 은 스텝 알고리즘이 스스로 들고
중단하는 보수적 **운용** 한계이며 이 노드 안에서만 쓴다. 30 N 은 contact_detector · safety_monitor 의 전역 **안전**
정지 · 래치 한계다. **12 를 30 으로 올리지 않는다** — 올리면 스텝 모드의 자체 보호가 사라진다.
