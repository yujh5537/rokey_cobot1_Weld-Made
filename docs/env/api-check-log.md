# API 호출 확인 로그 [E19] (T04, 담당 학민)

BRD는 "매뉴얼 설명 / 소스 확인 / 실제 PC 호출 확인 / 실기 성능 검증"을 구분한다. 이 표는 세 번째(실제 PC 호출 확인)만 기록한다. 성공했다는 것은 호출이 된다는 뜻이지 접촉 검출 성능이 검증됐다는 뜻이 아니다.

환경: 학민 PC `rokey-550XBE-350XBE` / 패키지 버전·커밋: ws_dsr `ahnisinc/cobot_rg2` @ `4d5657f` (`docs/env/versions.md`) / DRCF·DART 버전: Virtual 에뮬레이터 `doosanrobot/dsr_emulator:3.0.1`, DRCF `GF03020000`, DRFL `GL013303` (브링업 로그). Real 컨트롤러는 미기록

- **Virtual 확인:** 2026-09-19, 학민 PC, Claude 실행. 팀 도메인과 분리하려고 `ROS_DOMAIN_ID=99`에서 `bringup.launch.py mode:=virtual`로 띄웠다. 스크립트 `docs/env/check_api_calls.py --steps all --move-home`
- **Real 확인:** 미실시. 아래 "Real 확인 절차"를 사람이 실행한다(CLAUDE.md 규칙 1)
- 모든 서비스는 **`/dsr01/dsr_controller2/`** 아래에 있다(`/dsr01/motion/...`이 아니다). Python 래퍼 `DSR_ROBOT2.py`의 접두사도 `dsr_controller2/`다
- 호출은 래퍼 함수가 아니라 서비스를 직접 불렀다. 래퍼 함수는 응답을 시간 제한 없이 기다려 실기에서 멈춘 적이 있다(T02, `measure_idle_force.py`). 표의 "래퍼 있음"은 소스 확인[E18] 수준이다

| API / 서비스 | 호출 경로 (Python 래퍼 / service / drl_script_run) | Virtual | Real | 날짜 | 비고·로그 |
|---|---|---|---|---|---|
| get_tool_force | service `aux_control/get_tool_force` (ref=DR_BASE). 래퍼 `get_tool_force()` 있음 | 성공 | 미확인 | 2026-09-19 | 응답 4~7 ms. Virtual 값은 0 근처(±0.1 N)로, 물리 외력이 아니다 |
| get_current_posx | service `aux_control/get_current_posx` (ref=DR_BASE). 래퍼 있음 | 성공 | 미확인 | 2026-09-19 | `task_pos_info[0].data[:6]` = mm, deg |
| amovel | service `motion/move_line`, `sync_type=1`(ASYNC). 래퍼 `amovel()` 있음 | 성공 | 미확인 | 2026-09-19 | +z 20 mm, 20 mm/s 요청에 16~94 ms 만에 응답(이동 완료를 기다리지 않음). 0.4 s 뒤 z +5.3 mm로 이동 중 확인 |
| motion/move_stop (DR_QSTOP) | service `motion/move_stop`, `stop_mode=1`. **Python 래퍼 없음** | 성공 | 미확인 | 2026-09-19 | amovel 도중 호출 → z +5.5 mm(요청 20 mm)에서 멈춤, 0.5 s 사이 변화 0.0 mm. 응답 115~124 ms |
| task_compliance_ctrl / release_compliance_ctrl | service `force/task_compliance_ctrl`, `force/release_compliance_ctrl`. 래퍼 있음 | 호출 성공 | 미확인 | 2026-09-19 | stx=[3000,3000,3000,200,200,200], ref=DR_BASE. Virtual에서 힘 제어가 정상 동작하지 않을 수 있음 [E10]. 동작은 확인하지 않았다 |
| set_desired_force (DR_FC_MOD_REL) / release_force | service `force/set_desired_force`(`mod=1`), `force/release_force`. 래퍼 있음(기본 mod가 ABS라 REL을 명시해야 한다) | 호출 성공 | 미확인 | 2026-09-19 | 목표 힘 0 N, dir z. 1 s 동안 위치 변화 0.0 mm. 해제는 `finally`에서 불렀다. 0이 아닌 힘은 부르지 않았다(공중에서 로봇이 그 방향으로 움직인다) |
| check_position_condition | service `force/check_position_condition`. 래퍼 있음 | **판정 불일치** | 미확인 | 2026-09-19 | 응답 `success`가 조건 판정 결과다(호출 실패와 구분 안 됨). 현재 z±5 mm 조건이 False. 비교값이 (x 0.634, y 0.161, z 179.89)로 고정되어 로봇을 움직여도 변하지 않았다. 아래 상세 |
| drl_script_run (set_external_force_reset 경유) | service `drl/drl_start`(`robot_system`=get_robot_system 값, code `set_external_force_reset()`). 래퍼 `drl_script_run()` 있음. `set_external_force_reset` 래퍼는 없음 | 호출 성공 | 미확인 | 2026-09-19 | drl_state STOP → PLAY → STOP. Virtual 외력이 0 근처라 리셋 효과는 확인할 수 없다 |
| /onrobot/sendCommand (RG2 파지) | service `/onrobot/sendCommand` (`onrobot_rg_msgs/srv/SetCommand`, `/dsr01` 밖) | 성공 (가상 노드) | 미확인 | 2026-09-19 | Virtual은 `m0609_rg2_bringup/gripper_virtual_node.py` 스텁이다. 'o' · 'c' · 숫자(rad)를 받고 message는 ''. 응답 0.7~1.4 s. 실기 드라이버(`onrobot_rg_control`)와 다른 노드라 명령 형식을 실기에서 다시 대조한다 |
| 샘플 실제 수신 주기 | | 미측정 | 미측정 | | 설정상 50 Hz와 구분 (T08, T15) |

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

## Real 확인 절차 (사람이 실행, 미실시)

T02처럼 툴 · TCP 등록이 휘발성이니 먼저 `apply_tool_tcp.py`로 등록 상태를 맞춘다. 탐침 팁이 아무것도 닿지 않은 상태에서 한다.

```bash
# 터미널 1
sod && sodreal
# 터미널 2 (로그의 "DRCF version = ..." 줄을 versions.md에 옮긴다)
sod
python3 docs/env/check_api_calls.py                     # 조회 + check_position_condition. 움직이지 않는다
python3 docs/env/check_api_calls.py --real-ok --move-home --steps amovel_stop,compliance_force,drl
```

- [ ] 조회 · `check_position_condition`: 현재 z±5 mm 조건이 True인가 (Virtual은 False)
- [ ] `--move-home`: 홈 관절각으로 movej 한다. 경로에 물체가 없는지 먼저 본다
- [ ] `amovel_stop`: +z(위쪽) 20 mm를 20 mm/s로 가다가 0.4 s 뒤 `move_stop`. 도중에 멈추는지
- [ ] `compliance_force`: 목표 힘 0 N이라 로봇이 스스로 움직이지 않아야 한다. 움직이면 비상정지
- [ ] `drl`: `set_external_force_reset()` 전후 `get_tool_force`가 0 근처로 바뀌는지. Real은 `robot_system=0`으로 부른다(스크립트가 조회해서 넣는다)
- [ ] `/onrobot/sendCommand`: 스크립트는 실기에서 거부한다(탐침 파지 중 열면 떨어진다). 탐침을 뺀 상태에서 따로 확인한다
- [ ] 결과표(스크립트 마지막 출력)를 이 문서 Real 칸에 옮긴다

## robot_manager(T13 · T14)에 넘기는 것

- 서비스 접두사는 `/dsr01/dsr_controller2/`다.
- 정지는 `motion/move_stop`(`stop_mode=1`, DR_QSTOP)을 서비스로 직접 부른다. 래퍼에 `stop()` · `move_stop()`이 없다.
- `amovel`은 `motion/move_line`의 `sync_type=1`이다. 응답이 바로 오므로 이동 중 조회 · 정지 요청을 처리할 수 있다(4.2.3). 이동 완료는 따로 확인해야 한다.
- z 급강하 판정에 `check_position_condition`을 쓰지 않는다. 적어도 Virtual에서는 위치를 반영하지 않는다. `get_current_posx`로 z를 읽어 직접 비교한다. Real 결과가 나오면 다시 본다.
- `set_desired_force`는 `mod=1`(DR_FC_MOD_REL)을 명시한다. 래퍼 기본값은 ABS다.
