# robot_manager (담당: 학민)

두산 M0609 + RG2 를 부르는 **유일한** 노드다. 두산 단위(mm · deg)와 계약 단위(m · rad · quaternion)의
변환도 여기에서만 한다(`docs/contracts/units-frames.md`).

내는 것: `/robot/sample`(BEST_EFFORT) · `/robot/status` · `/robot/execute_motion`(Action) · `/robot/stop`(Service).
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
- **취소**: 취소 접수와 정지 완료는 다르다. `move_stop` 뒤 `moving` 이 false 가 될 때까지 기다린 다음 결과를 낸다.
- **SLIDE 하강 제한**: 첫 샘플 z 기준으로 `drop_limit_m` 를 넘으면 `DROP_LIMIT(205)` 로 끝낸다(계약 7.2 1차 감시).
- **순응 · 힘 제어는 `finally` 에서 해제**한다. 켜는 호출을 **보내기 전에** 해제 대상으로 표시한다(응답 시간
  초과여도 컨트롤러는 이미 켰을 수 있다). 해제 순서는 `release_force` → `release_force_time_s` 대기 →
  `release_compliance_ctrl`. `compliance_released=true` 는 **해제 호출이 성공했다**는 뜻이고, 실제 제어 모드
  조회로 확인하는 것은 후속이다(#125).
- `OP_HOME` 의 목적지는 관절각(`home_joint_deg`)이다. 계약 5.4 는 `home_pose` 라고 적었지만 T03 이 홈을
  관절각으로 확정했다(`units-frames.md`).

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
- **δ 는 측정이 아니라 파라미터의 함수다.** 스텝 모드의 `z_drop_m` 은 `step_drop_m`(0.5 mm)에서 잘린 값이라
  편향 보정 d = √(2rδ − δ²) 도 파라미터를 따라간다. `edge_bias_offset_m` 이 그 오차를 흡수하고,
  **판정 방식을 바꾸면 offset 을 다시 재야 한다**(#167 현지 코멘트).
- 대가: 40 mm 한 방향에 약 50~70 s 다. 전체 탐색 435 s 의 76 % 가 여기다(#180).

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
| `drop_limit_m` | 0.005 | **계약 이름.** SLIDE 첫 샘플 z 기준 하강 제한. safety_monitor 와 같은 값 |
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
