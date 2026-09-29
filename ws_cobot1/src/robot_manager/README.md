# robot_manager (담당: 학민)

두산 M0609 + RG2 를 부르는 **유일한** 노드다. 두산 단위(mm · deg)와 계약 단위(m · rad · quaternion)의
변환도 여기에서만 한다(`docs/contracts/units-frames.md`).

내는 것: `/robot/sample`(BEST_EFFORT) · `/robot/status` · `/robot/execute_motion`(Action) · `/robot/execute_path`(Action, phase 2 P1 — 아래 "ExecutePath") · `/robot/stop`(Service).
받는 것: `/contact/event`.

## 파일

| 파일 | 하는 일 | rclpy · 두산 |
|---|---|---|
| `conversions.py` | posx(mm · deg ZYZ) → Pose(m · quaternion), 외력 → Wrench | 쓰지 않음 |
| `motions.py` | Pose → posx 역변환, SLIDE 방향 벡터, 이동 거리, 하강 제한 | 쓰지 않음 |
| `motion_state.py` | 위치 이력으로 "움직이는가 · 움직였는가" 판정 | 쓰지 않음 |
| `step_slide.py` | **SLIDE 스텝 모드**의 순서와 판정 (아래 별도 절). 로봇을 부르는 일은 `StepIO` 뒤에 둔다 | 쓰지 않음 |
| `call_queue.py` | 두산 호출을 한 줄로 줄 세우기 · 응답 시간 초과 | 쓰지 않음 |
| `dsr_client.py` | `dsr_controller2` 서비스 클라이언트와 요청 만들기 | `dsr_msgs2` |
| `paths.py` | ExecutePath 검사(604 사유) · 경로 길이 · 진행 · posx 목록 | 쓰지 않음 |
| `path_executor.py` | ExecutePath 실행(line · spline) 과 감시 | rclpy 타입 · `dsr_msgs2` |
| `robot_manager.py` | 노드. 조회 → 발행, Action 서버, 정지 처리, `StepIO` 구현 | rclpy · `dsr_msgs2` |

`dsr_msgs2` 는 `ws_dsr` 에만 있고 CI 에는 없다. 그래서 `package.xml` 에 의존으로 넣지 않고 `dsr_client.py`
에서만 import 한다. 순수 계산 모듈과 그 시험은 두산 드라이버 없이 돈다.

## 두산 호출 규칙 (지키지 않으면 드라이버가 멈춘다)

- **한 번에 하나씩만 부른다.** `get_current_posx` 와 `get_tool_force` 를 동시에 부르자 `dsr_controller2` 가
  모든 서비스 응답을 멈췄고 브링업을 다시 띄워야 회복됐다(2026-09-20 Virtual, `docs/env/api-check-log.md`).
  조회 · 모션 · 정지를 모두 `call_queue.CallQueue` 한 줄에 넣는다.
- **응답을 기다리며 콜백을 막지 않는다.** `call_async` + 콜백만 쓴다(BRD 4.2.3).
- 실패한 값은 0 으로 채우지 않는다. NaN 으로 두고 `valid=false` 로 발행한다.
- **`success=true` 를 "그 자세가 됐다"로 읽지 않는다.** 도달 불가 자세에 `move_line` 을 보내면 로봇이
  한 번도 움직이지 않은 채 `success=true` 가 8 회 연속 온다. `move_jointx` 도 같고 `motion/ikin` 은
  sol 0~7 전부 `success=true` 에 J2 = 29914° 같은 값을 준다(2026-09-23 실기, #186 M1).
  그래서 도착은 **위치로** 확인한다(아래 `arrival_tolerance_m`).
- 늦은 응답은 `slow_call_warn_s` 를 넘으면 이름 · 시간과 함께 로그에 남는다(#130 · #135). 정지 중뿐 아니라
  모션 중에도 난다.

## ExecuteMotion

| 동작 | 어떻게 실행하나 | 정상 종료 |
|---|---|---|
| `OP_MOVE_TO` | `move_line` ABS (`goal.target` 을 posx 로 역변환) | `TARGET_REACHED` |
| `OP_DESCEND` | `move_line` REL −z, 거리 `max_distance` | `CONTACT`(이벤트). 없으면 `MAX_DISTANCE` + `NO_CONTACT` |
| `OP_SLIDE` | `slide_mode` 에 따라 **force**(순응 · 힘 제어) 또는 **step**(아래) | `EDGE`(이벤트 또는 스텝 모드 확정). 없으면 `MAX_DISTANCE` + `NO_EDGE` |
| `OP_HOME` | `move_joint` ABS (`home_joint_deg`) | `TARGET_REACHED` |

- **동시에 1 개만 받는다.** 실행 중이면 goal 을 거절한다(BUSY). 미연결 · 잘못된 값도 거절한다.
- **도착은 위치로 확인한다.** 멈춘 것과 도착한 것은 다르다. 멈췄는데 목표에서 `arrival_tolerance_m` 밖이면
  `ROBOT_ERROR(204)` 다(#152). 명령 뒤 `arrival_grace_s` 가 지나도록 출발하지 않았으면 `move_stop` 뒤
  같은 명령을 `move_restart_max` 번까지 다시 보낸다(#153 → #174).
- **`/robot/stop` 은 접수만 한다(계약 4.1).** 요청은 정지를 확인할 때까지 남고, 남아 있는 동안 새 goal 을
  거절한다(`STOP_REQUESTED`).
  - 동작 중: `watch` 가 처리해 `REASON_STOP_REQUESTED` 로 끝낸다. 정지를 확인하지 못하면 `ROBOT_ERROR` 로
    끝내고 요청은 **남긴다**(#113)
  - 동작 없음: 별도 스레드가 `move_stop` 을 보내고 정지를 확인하면 지운다
  - **안전복귀(`OP_HOME`)는 남은 요청이 있어도 거절하지 않는다**(#115). 관제자가 직접 누른 명령이라 확인으로
    본다. HOME **도중에** 새로 온 정지 요청은 HOME 을 멈춘다
- **이벤트 대조**(계약 5.4): `ContactEvent.motion_id` 가 현재 goal 과 같고 동작이 맞을 때만 정지한다.
  `TYPE_OVER_FORCE` 는 대조 없이 항상 정지한다.
- **취소**: 취소 접수와 실제 정지 완료는 다르다. `move_stop` 뒤 `moving` 이 false 가 될 때까지 기다린 다음 결과를 돌려준다.
- **SLIDE 하강 제한**: 기준 z 보다 `drop_limit_m` 를 **초과**해 내려가면 정지하고 `DROP_LIMIT`(205) 로 끝낸다(계약 7.2 1차 감시. 정확히 한계면 걸리지 않는다).
  - **기준 z = 이 노드가 `operation = OP_SLIDE` 로 발행한 첫 유효 샘플의 z** 다(v0.1.21). safety_monitor(2차)가 잡는 것과 **같은 메시지의 같은 값**이다. 실행 직전의 마지막 위치를 쓰면 순응을 켜며 z 가 약 0.7 mm 올라온 만큼 두 기준이 어긋나고, 그러면 2차의 여유가 의미를 잃는다.
  - 첫 `OP_SLIDE` 샘플이 나가기 전까지는 실행 직전의 마지막 위치를 임시 기준으로 쓴다. **감시를 끄지 않는다.**
  - 2차(safety_monitor)는 같은 기준 z 에 `drop_limit_margin_m` 를 더한 값에서 걸린다(real · sim 모두 1차 5 mm · 2차 10 mm). 1차 = 정상 동작의 제한, 2차 = 최후 방어선 + 래치.
  - 스텝 모드에서도 **매 대기마다** 1차를 본다. 설정 검사가 `step_press_max_m + step_drop_m < drop_limit_m` 을 강제한다.
- **순응 · 힘 제어는 `finally` 에서 해제**한다. 해제 호출이 실패하면 `compliance_released=false` 로 사실대로 보고한다
  - **켜는 호출을 보내기 전에** 해제 대상으로 표시한다. 켜는 호출이 응답 시간 초과여도 컨트롤러는 이미 켰을 수 있어서다. 켜지 않은 것을 해제하다 실패하면 `compliance_released=false` 가 된다(모르면 해제됐다고 하지 않는다)
  - 해제 순서는 힘 제어(`release_force`) → **`release_force_time_s` 대기** → 순응 제어(`release_compliance_ctrl`). 응답이 램프보다 먼저 올 수 있어 기다린다(매뉴얼 5.1.4 예제)
  - `compliance_released=true` 는 **해제 호출이 성공했다**는 뜻이다. 실제로 위치 제어로 돌아왔는지 조회로 확인하는 것은 후속(`GetControlMode`, 실기 확인 필요)
  - 시험(`test_node.py`, T14): 예외 주입 · 취소 · 정지 요청 · 이벤트 · 시간 초과 · 하강 제한 · 정상 종료 7경로에서 해제, 켜기 시간 초과 2경우, 해제 실패 보고, 힘 제어를 안 쓰는 동작은 해제 호출 없음
  (실패 경로는 계약에서 TBD다. 성공한 것으로 적지 않는다).
- `OP_HOME` 의 목적지는 관절각(`home_joint_deg`)이다. 계약 5.4 는 `home_pose` 라고 적었지만, T03 이 홈을
  관절각으로 확정했고 `OP_HOME` 은 movej 로 간다(`units-frames.md`). 계약 이름이 아닌 파라미터라 바꿔도 된다.

## SLIDE 스텝 모드 (`step_slide.py`, 실기 기본값)

`slide_mode: step` 이면 SLIDE 를 힘 제어로 밀지 않고 **한 스텝 가고 멈춰서 힘을 읽는 방식**으로 한다.
real.yaml 의 기본값이 `step` 이고, sim 은 `force` 다(Virtual 의 외력이 0 근처라 스텝 모드를 돌릴 수 없다).

**왜 바꿨나.** 연속 힘 제어 SLIDE 는 움직이는 중의 외력 추정값이 방향마다 1.5~8.6 N 치우쳐(2026-09-22 T25)
누름을 믿을 수 없었다. 방향 전환 뒤에는 힘 제어가 누름을 더해 주지 못해 2~4 방향이 떠서 모서리를 놓쳤다(#155).
스텝 모드는 위치 제어로 가고, **멈춘 뒤 새로 받은 샘플만 평균낸 ΔFz** 만 본다.

| 단계 | 하는 일 |
|---|---|
| 0. 기준 힘 | `step_lift_m` 만큼 들고 긁을 방향으로 `step_nudge_m` 움직여 멈춘 뒤 F0 를 잰다. **마지막 이동 방향을 긁기와 같게 둔다** — 멈춘 상태에서도 마지막 이동 방향만으로 Fz 가 1.9 N 달라진다(9/21 실기 1-1) |
| 1. 누르기 | `step_press_step_m` 씩 내려가 ΔFz ≥ `step_release_n` 이면 닿음. 한계는 시작 z − `step_press_max_m` |
| 2. 긁기 | `step_coarse_m` 이동 → 누름 맞추기. ΔFz 를 `[step_follow_lo_n, step_follow_hi_n]` 로 유지하도록 z 를 `step_z_m` 씩 조절한다. 힘이 빠지면 최근 접촉 높이(중앙값)보다 `step_drop_m` 아래까지 내려가 보고, 그래도 `follow_lo` 미만일 때만 소실 후보로 본다 |
| 3. 다듬기 | 접촉 높이 + lift 로 들고, **마지막으로 제대로 누른 자리보다 한 스텝 뒤에서** 공중 F0 를 다시 잰 뒤 `step_fine_m` 씩 전진해 소실 지점을 다시 찾는다 → 모서리 |
| 4. 마무리 | `step_lift_m` 만큼 든다. 팁을 모서리에 걸쳐 두지 않는다 |

- **소실 기준은 `follow_lo_n` 이지 `release_n` 이 아니다.** 모서리를 넘으면 반지름 약 2 mm 팁이 모서리 각에
  걸려 1~2 N 이 남는데, 이 값은 F0 치우침(±0.6 N)만큼 `release_n` 을 넘나든다.
- 최근 접촉 높이는 **`follow_lo` 이상으로 누른 자리만** 쌓는다. 약한 걸침이 기준 높이를 끌어내리면 팁이
  모서리를 타고 흘러내린다.
- 실패 종류: `no_edge` · `no_contact` · `over_force` · `side_hit` · `z_drift` · `unstable`.
  가능한 한 면에서 떨어진 뒤 `StepFailure` 를 낸다.
- **δ 는 측정이 아니라 파라미터의 함수다.** 스텝 모드의 `z_drop_m` 은 `step_drop_m`(9/23 까지 0.5 mm, 9/29 #213 부터 0.8 mm)에서 잘린 값이라
  편향 보정 d = √(2rδ − δ²) 도 파라미터를 따라간다. `edge_bias_offset_m` 이 그 오차를 흡수하고,
  **판정 방식을 바꾸면 offset 을 다시 재야 한다**(#167 현지 코멘트).
- 대가: 40 mm 한 방향에 약 50~70 s 다. 전체 탐색 435 s 의 76 % 가 여기다(#180).

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

값은 `contact_scan_bringup/config/{real,sim}.yaml` 에 둔다. 아래 "실기값"은 `real.yaml` 기준이다.
**계약 이름**(`slide_target_force_n` · `drop_limit_m` · `motion_timeout_s`)은 다른 노드와 같은 값이어야 하고
`contact_scan_bringup/test/test_config.py` 가 검사한다.

### 기본

| 이름 | 실기값 | 뜻 · 근거 |
|---|---|---|
| `frame_id` | `base_link` | pose · wrench 프레임 |
| `dsr_namespace` | `dsr01` | 서비스 접두사 `/<ns>/dsr_controller2/` |
| `sample_rate_hz` | 50.0 | 조회 **시도** 주기. 설계 출발값. 실측은 Virtual 37.6 Hz · 실기 약 42.8 Hz |
| `status_rate_hz` | 10.0 | `/robot/status` 발행 주기 |
| `service_timeout_s` | 0.5 | 이 시간 안에 응답이 없으면 무효 샘플로 발행 |
| `slow_call_warn_s` | 0.15 | 이보다 늦은 두산 응답을 이름 · 시간과 함께 남긴다(#130 · #135). 0 이면 끈다 |
| `moving_eps_m` · `moving_window_s` | 0.0002 · 0.3 | "지금 움직이는가" 판정. 이 둘이 지켜 주는 최저 속도는 0.2 mm / 0.3 s ≈ 0.67 mm/s 다 |
| `moved_min_m` | 0.001 | 이만큼 넘게 가야 "움직였다"(도착 판정용) |
| `arrival_tolerance_m` | 0.003 | `OP_MOVE_TO` 도착 허용치. 멈췄는데 이 밖이면 204 (#152) |
| `arrival_grace_s` · `move_restart_max` | 1.0 · 1 | 이 시간 안에 출발하지 않으면 `move_stop` 뒤 다시 보낸다 (#153) |
| `motion_timeout_s` | 120.0 | **계약 이름.** `goal.timeout` 이 0 일 때 쓴다. 스텝 모드가 한 방향 50~70 s 라 코드 기본 60 으로는 끊긴다 |
| `stop_settle_s` | 1.5 | 정지 명령 뒤 멈춤을 기다리는 시간 |
| `feedback_period_s` | 0.1 | Action feedback 발행 주기 |

### 모션 · 안전

| 이름 | 실기값 | 뜻 · 근거 |
|---|---|---|
| `home_joint_deg` | `[-21.19, 15.24, 52.97, -0.08, 111.80, -15.14]` | `OP_HOME` 목적지(J1~J6, deg). **없으면 `OP_HOME` 을 거절한다.** 2026-09-23 새 작업대 기준(#147, `units-frames.md` v0.1.18) |
| `home_speed_deg_s` | 20.0 | `OP_HOME` 관절 속도 |
| `drop_limit_m` | 0.005 | **계약 이름.** SLIDE 첫 샘플 z 기준 하강 제한(1차). safety_monitor 와 같은 값이고, 2차는 여기에 `drop_limit_margin_m`(5 mm)을 더한 **10 mm** 에서 걸린다(계약 7.2, v0.1.21) |
| `slide_target_force_n` | 3.0 | **계약 이름.** force 모드의 −z 목표 힘. 0 이면 SLIDE 를 거절한다. **잠정값** |
| `compliance_stiffness` | `[3000, 3000, 3000, 200, 200, 200]` | `task_compliance_ctrl` 강성 |
| `release_force_time_s` | 0.3 | `release_force` 의 강성 제어 전환 시간. 응답이 램프보다 먼저 올 수 있어 기다린다 |
| `slide_mode` | `step` | `force` \| `step`. sim 은 `force` |

### 스텝 모드 (`slide_mode: step` 일 때만 읽는다)

코드에 예비값이 없다. yaml 에 없으면 첫 SLIDE 에서 거절한다.
아래는 **설계 출발값**이고, 실측으로 확정한 것만 근거를 적었다.

| 이름 | 실기값 | 뜻 · 근거 |
|---|---|---|
| `step_coarse_m` | 0.0005 | 긁기 스텝. 프로토타입 0.5 mm. **분해능은 `step_fine_m` 이 정하므로 이 값은 시간과 맞바꾼다**(#180 ②) |
| `step_fine_m` | 0.0001 | 다듬기 스텝. 모서리 반복도의 분해능 |
| `step_z_m` | 0.00005 | 누름 맞추기 z 스텝. **실측**: 새 탐침은 0.1 mm 당 약 1.4 N(t25_all.sh) → [3, 7] N 띠가 약 0.3 mm |
| `step_press_step_m` · `step_press_max_m` | 0.0001 · 0.003 | 처음 누를 때 스텝 · 최대 거리. `press_max + drop < drop_limit_m` 이어야 한다 |
| `step_lift_m` · `step_nudge_m` | 0.001 · 0.001 | 기준 힘 잴 때 드는 높이 · 긁을 방향으로 미리 움직이는 거리 |
| `step_release_n` | 2.5 | 맨 처음 누를 때만 쓰는 접촉 기준. **소실 기준이 아니다** |
| `step_follow_lo_n` · `step_follow_hi_n` | 3.0 · 7.0 | 누름 하한 · 상한. **소실 판정은 `lo` 기준** |
| `step_max_force_n` | 12.0 | 이보다 크면 들고 중단. `over_force_n`(30)보다 작다 |
| `step_side_hit_n` | 8.0 | 수평 \|ΔF\| 가 이보다 크면 물러나고 중단. 프로토타입 마찰 수평 힘 약 2.6 N |
| `step_drop_m` | 0.0005 | 힘이 빠졌을 때 최근 접촉 높이보다 이만큼 더 내려가 본다. **편향 보정 δ 가 여기서 잘린다** |
| `step_z_tol_m` · `step_max_slope_deg` | 0.001 · 5.0 | 높이 변화 한계 = max(z_tol, 긁은 거리 × tan(각)). 넘으면 탐침 밀림 · 물체 이동으로 보고 중단 |
| `step_settle_s` · `step_force_samples` | 0.15 · 3 | 멈춘 뒤 대기 · 평균낼 샘플 수. 42.8 Hz 면 3 개 ≈ 70 ms |
| `step_still_m` · `step_still_window_s` | 0.00005 · 0.15 | 멈춤 판정. posx 정지 잡음보다 커야 한다 |
| `step_move_timeout_s` | 2.0 | 한 스텝이 (거리/속도 + 이 값) 안에 멈추지 않으면 중단 |

## SLIDE 누름 목표를 상태에 싣는다 (계약 3.2, v0.1.21 결정 4)

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

## 실행 · 테스트

```bash
# 단위시험 (ROS 없이, 순수 모듈만)
cd ~/ws_cobot_pjt/ws_cobot1
python3 -m pytest src/robot_manager/test/test_step_slide.py src/robot_manager/test/test_motions.py \
                  src/robot_manager/test/test_conversions.py src/robot_manager/test/test_call_queue.py -q

# 전체 (노드 시험 포함. dsr_msgs2 가 필요하다)
sod && cd ~/ws_cobot_pjt/ws_cobot1
colcon test --packages-select robot_manager && colcon test-result --test-result-base build/robot_manager
```

| 명령 | 마지막 확인 | 결과 |
|---|---|---|
| 순수 모듈 pytest | 2026-09-24 | **81 passed** |
| `colcon test --packages-select robot_manager` | 2026-09-24 | **135 tests, 0 failures** |

```bash
# 노드 띄우기 (Virtual)
sod && sodvir                                   # 다른 터미널
source ~/ws_cobot_pjt/ws_cobot1/install/setup.bash
ros2 run robot_manager robot_manager            # 또는 contact_scan_bringup 의 launch
ros2 topic echo /robot/sample contact_scan_interfaces/msg/RobotSample --qos-reliability best_effort
```

`/robot/sample` 은 BEST_EFFORT 다. `ros2 topic echo` 는 기본이 RELIABLE 이라 옵션을 주지 않으면 아무것도 보이지 않는다.

> **실기 전용 · 마지막 확인 2026-09-23.** `sodreal` 로 띄우고 **매번** 툴 · TCP 를 등록한다
> (`python3 docs/env/apply_tool_tcp.py --tcp-x 0 --tcp-y 0` → `OK: ... [0.0, 0.0, 252.12]`).
> 빠뜨리면 좌표가 팁이 아니라 플랜지로 나오고(+252.12 mm) 외력이 약 12 N 치우친다(#123).
> 실기 명령은 사람이 직접 실행한다(CLAUDE.md 규칙 1).

## 알려진 문제

| 이슈 | 내용 | 상태 |
|---|---|---|
| #167 | 스텝 모드 소실 판정이 기준 힘 F0 에 의존해 −y 모서리가 회차마다 흔들린다 | 9/23 18:32 종단에서는 재발하지 않았다. 원인 미확정. **1차 동결 이후 코드 변경 없음** |
| #130 | 정지 중 3 s 주기 샘플 공백(300~360 ms, 최대 748 ms) | `sample_stale_ms` 500 으로 완화(#168). 원인 미확정 |
| #123 | 툴 · TCP 등록 상태를 보지 않고 goal 을 받는다 | 절차(tare 거절 · 세션 시작 점검)로 막는다. 코드 변경은 phase 2 뒤 |
| #125 | `compliance_released` 를 호출 성공이 아니라 제어 모드 조회로 판정한다 | 미착수 |
| #155 | 방향 전환 뒤 SLIDE 가 약하게 닿거나 뜬다 | 스텝 모드가 스스로 누름을 만들어 급하지 않다 |
| #180 | 전체 탐색 435 s (KPI 120 s 의 3.6 배). 76 % 가 스텝 긁기 | 팀 결정 대기 |
