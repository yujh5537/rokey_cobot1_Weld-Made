# API 호출 확인 로그 [E19] (T04, 담당 학민)

BRD는 "매뉴얼 설명 / 소스 확인 / 실제 PC 호출 확인 / 실기 성능 검증"을 구분한다. 이 표는 세 번째(실제 PC 호출 확인)만 기록한다. 성공했다는 것은 호출이 된다는 뜻이지 접촉 검출 성능이 검증됐다는 뜻이 아니다.

환경: 학민 PC `rokey-550XBE-350XBE` / 패키지 버전·커밋: ws_dsr `ahnisinc/cobot_rg2` @ `4d5657f` (`docs/env/versions.md`) / DRCF·DART 버전: Virtual 에뮬레이터 `doosanrobot/dsr_emulator:3.0.1`, DRCF `GF03020000`, DRFL `GL013303` (브링업 로그). **Real 컨트롤러 DRCF `GF02120100`, DRFL `GL013303`** (`sodreal` 로그 118개, `mode : real`, 2026-09-16~21. 로봇 주소는 `versions.md`)

- **Virtual 확인:** 2026-09-19, 학민 PC, Claude 실행. 팀 도메인과 분리하려고 `ROS_DOMAIN_ID=99`에서 `bringup.launch.py mode:=virtual`로 띄웠다. 스크립트 `docs/env/check_api_calls.py --steps all --move-home`
- **Real 확인:** **부분 실시**(2026-09-20~21, 학민). `check_api_calls.py`를 실기에서 돌리지는 않았고, 같은 서비스를 쓰는 robot_manager(T13 · T15)와 `probe_point.py` · `apply_tool_tcp.py`를 실기 세션에서 돌린 기록으로 Real 칸을 채웠다. 근거: `docs/test-reports/realrobot-session_20260921.md`, `docs/test-reports/T03-follow-up_20260920.md`(#80). 호출이 된다는 확인이지 성능 검증이 아니다. 남은 항목은 아래 "Real 확인 절차"를 사람이 실행한다(CLAUDE.md 규칙 1)
- 모든 서비스는 **`/dsr01/dsr_controller2/`** 아래에 있다(`/dsr01/motion/...`이 아니다). Python 래퍼 `DSR_ROBOT2.py`의 접두사도 `dsr_controller2/`다
- 호출은 래퍼 함수가 아니라 서비스를 직접 불렀다. 래퍼 함수는 응답을 시간 제한 없이 기다려 실기에서 멈춘 적이 있다(T02, `measure_idle_force.py`). 표의 "래퍼 있음"은 소스 확인[E18] 수준이다

| API / 서비스 | 호출 경로 (Python 래퍼 / service / drl_script_run) | Virtual | Real | 날짜 | 비고·로그 |
|---|---|---|---|---|---|
| get_tool_force | service `aux_control/get_tool_force` (ref=DR_BASE). 래퍼 `get_tool_force()` 있음 | 성공 | **성공** | 2026-09-19 / Real 2026-09-20~21 | 응답 4~7 ms. Virtual 값은 0 근처(±0.1 N)로, 물리 외력이 아니다. Real: robot_manager 샘플 · `probe_point.py`. **툴 미등록이면 약 12 N 치우침**(`tool-tcp-register.md`), **팔이 움직이면 외력 추정이 약 2.3 N 치우친다**(realrobot-session_20260921.md 5-2, #109). **값은 약 10 Hz(약 94 ms)로만 갱신된다** — 응답은 4~7 ms 에 오지만 같은 값이 여러 번 온다. robot_manager 는 그보다 빠르게(설정 50 Hz, 실기 실측 약 43 Hz) 조회해 발행하므로 **소비 측은 같은 값을 연속 샘플로 받는다**. 그래서 `debounce_n` 의 "연속 3 회"가 독립 측정 3 회가 아니다(계약 3.3, v0.1.21 결정 9) |
| get_current_posx | service `aux_control/get_current_posx` (ref=DR_BASE). 래퍼 있음 | 성공 | **성공** | 2026-09-19 / Real 2026-09-20~21 | `task_pos_info[0].data[:6]` = mm, deg. Real: 표시 좌표는 **등록된 TCP 로 계산**된다. 툴 · TCP 가 풀리면 플랜지 좌표가 나온다(realrobot-session_20260921.md 5-0 · 5-6) |
| amovel | service `motion/move_line`, `sync_type=1`(ASYNC). 래퍼 `amovel()` 있음 | 성공 | **성공** | 2026-09-19 / Real 2026-09-21 | +z 20 mm, 20 mm/s 요청에 16~94 ms 만에 응답(이동 완료를 기다리지 않음). 0.4 s 뒤 z +5.3 mm로 이동 중 확인. Real: robot_manager `OP_DESCEND` · `OP_MOVE_TO`. `OP_MOVE_TO` 세 번 모두 목표와 0.1 mm 이내(realrobot-session_20260921.md 5-8) |
| motion/move_stop (DR_QSTOP) | service `motion/move_stop`, `stop_mode=1`. **Python 래퍼 없음** | 성공 | **성공** | 2026-09-19 / Real 2026-09-21 | amovel 도중 호출 → z +5.5 mm(요청 20 mm)에서 멈춤, 0.5 s 사이 변화 0.0 mm. 응답 115~124 ms. **Real: ASYNC 모션이 도는 중에 불러도 드라이버가 멈추지 않았다** — 과대 외력 정지 0.5 s · 2.2 mm(5-0), `/robot/stop` 정지 8.84 mm(5-10). 병후 리뷰의 '모션 중 move_stop' 우려에 대한 실기 답이다 |
| task_compliance_ctrl / release_compliance_ctrl | service `force/task_compliance_ctrl`, `force/release_compliance_ctrl`. 래퍼 있음 | 호출 성공 | **호출 성공** | 2026-09-19 / Real 2026-09-21 | stx=[3000,3000,3000,200,200,200], ref=DR_BASE. Virtual에서 힘 제어가 정상 동작하지 않을 수 있음 [E10]. Real: robot_manager `OP_SLIDE` 두 번, 둘 다 `compliance_released true`. 순응 제어가 켜지자 0.4 s 안에 z 가 0.7 mm 올라오며 눌림이 풀렸다(realrobot-session_20260921.md 5-1). 성능(모서리 검출)은 T25 |
| set_desired_force (DR_FC_MOD_REL) / release_force | service `force/set_desired_force`(`mod=1`), `force/release_force`. 래퍼 있음(기본 mod가 ABS라 REL을 명시해야 한다) | 호출 성공 | **호출 성공 · REL 의미 실측** | 2026-09-19 / Real 2026-09-21 | Virtual: 목표 힘 0 N, dir z. 1 s 동안 위치 변화 0.0 mm. 해제는 `finally`. **mod 의미는 헤더에서 확인**(`dsr_msgs2/srv/detail/set_desired_force__struct.h`): ABS(0)=절대값, REL(1)=**호출 시점 상태 기준 상대값**. **Real: 목표 3 N 이 SLIDE 시작 시점의 기준선에 더해진다고 로그가 찍는다** — 12:01 기준선 Fz 5.31 N → 실제 누름 약 8.3 N 으로 추정(realrobot-session_20260921.md 5-12, #91 · #105). 다만 10:36 에는 기준선 9.83 N 에서 시작했는데 순응 제어가 켜지며 눌림이 풀려 밀기 중 Fz 는 0.3~1.3 N 이었다(5-1). 조회값에 지령 힘이 섞이는 것으로 보여(추정) 실제 누름은 아직 확정하지 않는다. `DR_FC_MOD_ABS` 실기 동작은 **미확인**(보고서 6절) |
| check_position_condition | service `force/check_position_condition`. 래퍼 있음 | **판정 불일치** | 미확인 (**설계에서 쓰지 않음**) | 2026-09-19 | 응답 `success`가 조건 판정 결과다(호출 실패와 구분 안 됨). 현재 z±5 mm 조건이 False. 비교값이 (x 0.634, y 0.161, z 179.89)로 고정되어 로봇을 움직여도 변하지 않았다. 아래 상세. z 급강하 판정은 contact_detector 가 `RobotSample.pose` 로 하므로(계약 2.1) 이 API 는 쓰지 않는다. Real 확인이 필요해지면 스크립트가 호출 직전 posx 6개를 같이 남긴다 |
| drl_script_run (set_external_force_reset 경유) | service `drl/drl_start`(`robot_system`=get_robot_system 값, code `set_external_force_reset()`). 래퍼 `drl_script_run()` 있음. `set_external_force_reset` 래퍼는 없음 | 호출 성공 | 미실시 | 2026-09-19 | drl_state STOP → PLAY → STOP. Virtual 외력이 0 근처라 리셋 효과는 확인할 수 없다. 설계는 이것 대신 contact_detector 의 tare(`/contact/tare`)를 쓴다. **스캔 중 금지**: `get_tool_force` 출력 자체를 바꿔 잡아 둔 tare(F₀)를 무효로 만든다(매뉴얼 5.1.9, 현지 리뷰) |
| /onrobot/sendCommand (RG2 파지) | service `/onrobot/sendCommand` (`onrobot_rg_msgs/srv/SetCommand`, `/dsr01` 밖) | 성공 (가상 노드) | 미실시 (의도) | 2026-09-19 | Virtual은 `m0609_rg2_bringup/gripper_virtual_node.py` 스텁이다. 'o' · 'c' · 숫자(rad)를 받고 message는 ''. 응답 0.7~1.4 s. 실기는 탐침 파지 중이라 열면 떨어진다. 스크립트는 실기에서 '건너뜀'으로 남긴다 |
| 샘플 실제 수신 주기 | robot_manager 순차 조회(posx → force → state) | **37.6 Hz** (10 s 376/376, 2026-09-20) | **42.8 Hz** (무접촉 정지, `idle_30s.csv` 1282행, 2026-09-20 #80) · **49.6 Hz** (robot_manager 50 Hz 설정, 17,090 샘플, 최대 공백 358 ms, 2026-09-21) | | 설정 50 Hz 와 구분한다. **부하에 따라 달라지고 꼬리(최대 공백)가 판정에 걸린다**(계약 `ros-interfaces.md` 6.3, v0.1.10) |

## check_position_condition 상세 (Virtual)

2026-09-19, 홈 자세(posx z 540.60)에서 z축(`axis=2`), ref=DR_BASE, `mode=0`(ABS).

| 조건 [min, max] | 기대 | 받음 |
|---|---|---|
| [535.6, 545.6] (현재 z ± 5) | True | **False** |
| [590.6, 600.6] | False | False |
| [-10000, 10000] | True | True |
| [-10000(DR_COND_NONE), 545.6] | True | True |
| [535.6, -10000(DR_COND_NONE)] | True | **False** |
| REL, pos=현재, [-5, 5] | True | False |
| 순응 제어 중 [535.6, 545.6] | True | False |

상한을 이분 탐색해 컨트롤러가 비교하는 값을 구하면 x 0.634, y 0.161, z 179.89다. 로봇을 +z 20 mm, +x 20 mm 움직여도 이 값은 변하지 않았다. **Virtual에서는 이 API가 TCP 위치를 반영하지 않는다.** 에뮬레이터 한정인지는 Real에서 확인한다. 참고로 `check_force_condition`은 |F| ∈ [0, 10] → True, [50, 60] → False로 기대와 맞았다.

소스(`dsr_controller2/src/dsr_controller2.cpp`의 `check_position_condition_cb`)는 `Drfl->check_position_condition_abs()`의 반환값을 `success`에 그대로 넣는다[E18].

## 두산 서비스 동시 호출 (2026-09-20 Virtual, T15에서 발견)

**동시에 부르면 안 된다.** robot_manager(T15)가 `aux_control/get_current_posx`와 `aux_control/get_tool_force`를
여러 스레드에서 동시에 부르자, `dsr_controller2`가 **모든 서비스 응답을 멈췄다.** 그 뒤로는
`ros2 service call`로 부른 조회도 응답하지 않았고, 노드를 종료해도 회복되지 않아 브링업을 다시 띄워야 했다.
컨트롤러 노드 자체는 살아 있었고(`controller_manager` 로그가 계속 나옴) `get_robot_state`만 44회 처리된 뒤 멈췄다.

- 어제(T04) 확인이 모두 성공한 것은 호출을 **하나씩 차례로** 했기 때문이다.
- robot_manager는 `posx → force → get_robot_state`를 응답을 받은 뒤 다음 것을 부르는 방식으로 잇는다.
  그 상태에서 Virtual 37.6 Hz로 10초간 유효 376/376이었다.
- 이동(`move_joint` ASYNC) 중에 조회를 이어가는 것은 문제가 없었다(모션 1건 + 조회 1건은 동시에 떠 있다).
- **Real (2026-09-21):** robot_manager 는 조회를 한 줄로 잇고, 모션(ASYNC) 1건과 `move_stop` 을 그 사이에 넣는다. 이 구조로 하루 동안 드라이버가 멈추지 않았다(17,090 샘플, `move_stop` 포함). **조회를 일부러 겹쳐 부르는 재현은 실기에서 하지 않았다** — 드라이버가 멈추면 아래처럼 소프트웨어 정지 수단이 전부 사라진다.
- 디버깅 중 `ros2 service call` 을 겹쳐 부르는 것은 구조 규칙으로 막히지 않는다. launch 가 떠 있는 동안 조회 스크립트(`probe_point.py` · `measure_idle_force.py`)를 같이 돌리지 않는다.

### 드라이버 무응답 = 소프트웨어 정지 불가 (안전 사실)
**`dsr_controller2` 가 서비스 응답을 멈추면 `/robot/stop` 도 통하지 않는다.** `/robot/stop` 은 결국 robot_manager 가 같은 드라이버에 `motion/move_stop` 을 보내는 것이고, 정지 확인에 쓰는 `/robot/status`(위치 조회)도 같이 멈춘다. 이 상태에서는 **물리 비상정지가 유일한 수단**이고, 회복은 **브링업 재시작**뿐이다(노드 종료로는 회복되지 않았다). 그래서:
- robot_manager 는 미연결이면 `/robot/stop` 을 `accepted=false` · `ROBOT_DISCONNECTED` 로 사실대로 거절한다(#101). 정지를 확인하지 못하면 `ROBOT_ERROR` 로 올리고 다음 동작을 막는다(#113). 안전복귀만 예외다(#115)
- 실기에는 **항상 비상정지 앞에 한 명**이 선다(2인 1조). 시연도 같다

## get_robot_state는 이동 중에도 STANDBY다 (2026-09-20 Virtual)

`system/get_robot_state`(`GetRobotState`, 0 INITIALIZING · 1 STANDBY · 2 MOVING · 3 SAFE_OFF)는
**이동 중에도 1(STANDBY)** 을 돌려줬다. 5 deg/s로 `move_joint`(ASYNC)를 걸어 팁 z가 540.6 → 527.6 mm로
움직이는 동안 0.2초 간격 30회 모두 1이었다.

- **Real 에서도 같다**: 이동 중 12/12 회 STANDBY(2026-09-20, #80). 실기 컨트롤러도 MOVING 을 돌려주지 않는다.
- 그래서 `RobotStatus.moving`은 이 값으로 판정할 수 없다. robot_manager는 TCP 위치 변화로 본다. **계약에 반영됐다**
  (`docs/contracts/ros-interfaces.md` 9장, v0.1.4 · #72): 최근 `moving_window_s`(0.3 s) 안의 위치 변화가 `moving_eps_m`(0.2 mm)를
  넘으면 이동 중. 샘플 공백으로 남은 점이 창의 절반도 못 덮으면 '모른다 = 이동 중'이다(#101).
- 서비스 응답 자체는 정상이므로 **연결 확인(`connected`)** 용으로는 쓴다.

## Real 확인 절차 (사람이 실행. 스크립트 실기 실행은 미실시)

T02처럼 툴 · TCP 등록이 휘발성이니 먼저 `apply_tool_tcp.py`로 등록 상태를 맞춘다. 탐침 팁이 아무것도 닿지 않은 상태에서 한다.

```bash
# 터미널 1
sod && sodreal
# 터미널 2 (로그의 "DRCF version = ..." 줄을 versions.md에 옮긴다)
sod
python3 docs/env/check_api_calls.py                     # 조회 + check_position_condition. 움직이지 않는다
python3 docs/env/check_api_calls.py --real-ok --move-home --steps amovel_stop,compliance_force,drl
```

- **스크립트는 자동 모드로 바꾼 뒤 끝날 때(예외 포함) 원래 모드로 되돌린다**(2026-09-21 수정, Virtual 에서 수동 → 자동 → 수동 확인). 되돌리기가 실패로 찍히면 펜던트에서 직접 되돌린다
- [ ] 조회 · `check_position_condition`: 현재 z±5 mm 조건이 True인가 (Virtual은 False). **설계에서 쓰지 않으므로 선택 항목.** 하면 스크립트가 남긴 '호출 직전 posx 6개'와 비교값을 여섯 성분 전부와 대조한다(Virtual 비교값 z 179.89 가 홈 ry −179.87 과 0.02 차이다 — 자세 성분과 비교할 가능성, yujh5537)
- [ ] `--move-home`: 홈 관절각으로 movej 한다. 경로에 물체가 없는지 먼저 본다. **J6 가 −204.84° 로 ±180° 밖이라 현재 자세에 따라 크게 돌 수 있다. 케이블과 주변을 먼저 확인한다**(스크립트도 경고를 찍는다)
- [x] `amovel_stop` 에 해당: ASYNC 이동 중 `move_stop` — robot_manager 로 확인(2026-09-21, 표)
- [ ] `compliance_force`: 목표 힘 0 N이라 로봇이 스스로 움직이지 않아야 한다. 움직이면 비상정지. (0 이 아닌 힘은 robot_manager SLIDE 로 확인했다)
- [x] `get_robot_state`가 이동 중 2(MOVING)를 돌려주는지 → 아니다. STANDBY 12/12 (#80)
- [ ] 동시 호출이 실기에서도 드라이버를 멈추는지 — **일부러 재현하지 않는다**(위 안전 사실). 실기에서는 조회를 겹치지 않는다
- [ ] `drl`: `set_external_force_reset()` 전후 `get_tool_force`가 0 근처로 바뀌는지. Real은 `robot_system=0`으로 부른다(스크립트가 조회해서 넣는다)
- [ ] `/onrobot/sendCommand`: 스크립트는 실기에서 거부한다(탐침 파지 중 열면 떨어진다). 탐침을 뺀 상태에서 따로 확인한다
- [ ] 결과표(스크립트 마지막 출력)를 이 문서 Real 칸에 옮긴다

## robot_manager(T13 · T14)에 넘기는 것

- 서비스 접두사는 `/dsr01/dsr_controller2/`다.
- 정지는 `motion/move_stop`(`stop_mode=1`, DR_QSTOP)을 서비스로 직접 부른다. 래퍼에 `stop()` · `move_stop()`이 없다.
- `amovel`은 `motion/move_line`의 `sync_type=1`이다. 응답이 바로 오므로 이동 중 조회 · 정지 요청을 처리할 수 있다(4.2.3). 이동 완료는 따로 확인해야 한다.
- z 급강하 판정에 `check_position_condition`을 쓰지 않는다. 적어도 Virtual에서는 위치를 반영하지 않는다. **robot_manager 는 `get_current_posx` 를 `RobotSample.pose` 로 싣기만 하고, z 급강하 비교(`edge_drop_m`)와 `/contact/event` 발행은 contact_detector 가 한다**(계약 2.1).
- `set_desired_force`는 `mod=1`(DR_FC_MOD_REL)을 명시한다. 래퍼 기본값은 ABS다.
