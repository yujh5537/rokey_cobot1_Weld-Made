# robot_manager (담당: 학민)

두산 M0609 + RG2를 부르는 **유일한** 노드다. 두산 단위(mm · deg)와 계약 단위(m · rad · quaternion)의
변환도 여기에서만 한다(`docs/contracts/units-frames.md`).

| 상태 | 내용 |
|---|---|
| T15 (이 PR) | `/robot/sample` · `/robot/status` 발행 |
| T13 | `execute_motion` Action (DESCEND · SLIDE · MOVE_TO · HOME) |
| T14 | `/robot/stop`, 순응 · 힘 제어 `finally` 해제 |

## 구조
| 파일 | 하는 일 | ROS · 두산 의존 |
|---|---|---|
| `conversions.py` | posx(mm · deg ZYZ) ↔ Pose(m · quaternion), 외력 → Wrench | 없음 (ROS 없이 테스트) |
| `motion_state.py` | 위치 변화로 이동 여부 판정 | 없음 |
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

계약 이름(`slide_target_force_n` · `drop_limit_m`)은 T13에서 쓴다. 값은 `contact_scan_bringup/config/*.yaml`에 둔다.
