# contact_scan_bringup

자체 노드 5 개를 한 번에 띄우는 launch 와 입력원별 파라미터 파일. 담당: 현지 (T05). 계약: [`ros-interfaces.md`](../../../docs/contracts/ros-interfaces.md) 1장(노드 이름) · 6.4(계약 파라미터 이름) · 7.2(두 노드가 같은 값).
두산 · RG2 드라이버(`sodvir` / `sodreal`)는 **여기서 띄우지 않는다.** 별도 터미널에서 사람이 띄운다.

| 파일 | 역할 |
|---|---|
| `launch/bringup.launch.py` | `source` 에 맞는 yaml 로 노드 5 개(robot_manager · contact_detector · safety_monitor · scan_manager · mqtt_bridge)를 띄운다. 설치되지 않은 패키지는 건너뛴다 |
| `config/sim.yaml` | Virtual Mode + 가상 직육면체(contact_detector 의 sim 입력원). 개발 · 저녁 통합 · 리허설 |
| `config/real.yaml` | 실기(M0609 + RG2 + 탐침). **사람이 직접 실행한다** |
| `test/test_config.py` | 두 yaml 이 계약을 지키는지 검사(ROS 없이 돈다) |
| `test/test_launch.py` | launch 파일이 읽히고 `source` 인자를 선언하는지 검사(노드는 띄우지 않는다) |

## launch 인자
| 인자 | 값 | 기본 | 뜻 |
|---|---|---|---|
| `source` | `sim` · `robot_force` | `sim` | 접촉 판정 입력원 겸 파라미터 파일 선택(`sim.yaml` · `real.yaml`) |
| `broker_host` | 주소 | `127.0.0.1` | mqtt_bridge 가 붙을 MQTT 브로커. 환경마다 달라 yaml 에 두지 않는다(PR #179) |

- 노드 이름 = 패키지 이름 = 실행 파일 이름 = yaml 최상위 키. 다르면 파라미터가 들어가지 않는다. 노드를 추가하는 담당자는 `NODES` 를 고치는 PR 을 현지에게 요청한다
- 실행 로그 첫 줄 `[bringup] source=…, 파라미터 파일=…` 로 어떤 yaml 이 쓰였는지, `[bringup] … 건너뜀` 으로 빠진 패키지를 확인한다

## 실행
**sim (Virtual Mode, Claude 도 돌릴 수 있다)** — 2026-09-24 현지 PC(Virtual, 도메인 37)에서 아래 순서로 돌려 확인했다(홈 → 스캔 82 s, 결과 99.72 × 59.76 × 39.92 mm, 가상 박스 100 × 60 × 40 mm)
```bash
# 두 터미널 모두 같은 도메인. 조 공용(30)을 피하려면 31~39 중 빈 번호를 쓴다
export ROS_DOMAIN_ID=31 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
# 터미널 1 — 두산 에뮬레이터(docker dsr01_emulator 를 띄운다)
sod && sodvir
# 터미널 2 — 노드 5 개. robot_manager 가 dsr_msgs2 를 쓰므로 여기서도 sod 를 먼저 한다
sod && cd ~/ws_cobot_pjt/ws_cobot1 && source install/setup.bash
ros2 launch contact_scan_bringup bringup.launch.py source:=sim
# 터미널 3 — Virtual 은 관절 0° 로 뜨는데 그 자세는 특이점이라 직선 이동이 "성공"을 돌려주고도 움직이지 않는다.
#            먼저 홈(관절 이동)으로 보낸 뒤 스캔한다. 홈 없이 START 하면 첫 이동에서 204(출발 안 함)로 끝난다
ros2 action send_goal /scan/home contact_scan_interfaces/action/ReturnHome "{request_id: 'h1'}"
ros2 action send_goal /scan/run contact_scan_interfaces/action/RunScan "{request_id: 'r1'}"
# 끝나면 에뮬레이터를 치운다(PC 에 하나만)
docker rm -f dsr01_emulator
```
- `colcon build` 를 할 때도 **`sod` 를 먼저** 한다. ws_dsr 없이 빌드하면 `install/setup.bash` 가 ws_dsr 를 잇지 않아 robot_manager 가 `dsr_msgs2` 를 못 찾고 죽는다(2026-09-24 재현)
- mqtt_bridge 는 `paho-mqtt` 파이썬 패키지가 있어야 뜬다. 없으면 `ModuleNotFoundError: paho` 로 죽고 나머지 노드는 그대로 돈다(웹 없이 ROS 만 확인할 때는 무시해도 된다)
- Ctrl+C 로 끄면 노드들이 exit code −2 · 트레이스백을 남긴다(#111, 알려진 문제)
**실기 (사람만. 마지막 확인 2026-09-23, PR #179 실기 종단)**
- 순서 · 확인 사항은 루트 [README](../../../README.md) 의 실기 Runbook(PR #185)과 [`units-frames.md`](../../../docs/contracts/units-frames.md) "탐침 상태 전제조건" 의 세션 시작 점검(툴 · TCP 등록 확인 두 줄 포함)을 따른다
- `ros2 launch contact_scan_bringup bringup.launch.py source:=robot_force broker_host:=<웹 PC 주소>`
- 입회자가 비상정지 앞에 선다. 시연 중 `SAMPLE_STALE` 로 멈췄을 때는 [daily 20260923 §7](../../../docs/test-reports/daily/20260923.md)

## 파라미터 파일
각 노드의 값 · 근거는 **yaml 주석과 각 패키지 README 의 파라미터 표**에 있다(여기에 다시 적지 않는다):
[contact_detector](../contact_detector/README.md) · [safety_monitor](../safety_monitor/README.md) · [scan_manager](../scan_manager/README.md) · robot_manager(`robot_manager/README.md`) · mqtt_bridge.

**sim 과 real 이 다른 값** (2026-09-24 main 기준, 두 yaml 을 비교해 뽑았다)
| 노드 | 이름 | sim | real | 이유 |
|---|---|---|---|---|
| contact_detector | `source` | `sim` | `robot_force` | 입력원 |
| | `stale_age_ms` | 200 | 100 | Virtual 샘플 간격 최대 97.7 ms(계약 6.3) |
| | `tare_max_std_n` | 0.3 N | 1.0 N | 9/23 실기 tare RMS 0.64~0.81 N(PR #179) |
| | `sim_*` 7 개 | 가상 직육면체 | — | sim 입력원 전용 |
| safety_monitor | `robot_status_timeout_ms` | 1000 | 500 | 출발값 |
| robot_manager | `home_joint_deg` | 옛 홈(J6 −204.84°) | 새 홈(J6 −15.14°) | 9/22 작업대 교체 뒤 실기 홈만 바꿨다(계약 v0.1.18). sim 박스는 옛 홈 아래에 있다 |
| | `slide_mode` | `force` | `step` | 스텝 모드는 멈춰서 힘을 읽는다 — Virtual 은 외력이 0 이라 돌 수 없다(계약 7.2) |
| | `step_*` 21 개 · `motion_timeout_s` | 없음 | 있음 | 스텝 모드 전용 · 한 방향 50~70 s |
| | `home_speed_deg_s` | 30 | 20 | 실기는 낮춘다 |
| scan_manager | 좌표 계열(`base_to_fixture` · `search_origin_pose` · `support_z_m` · `max_descend_m` · `max_slide_m`) | 가상 박스 | 9/23 실측(잠정) | 계약 v0.1.18 |
| | 속도(`descend` · `slide` · `move` · `recontact_speed_mps`) | 5 · 10 · 50 · 5 mm/s | 3 · 5 · 30 · 2 mm/s | 실기는 느리게 |
| | `tip_radius_m` · `detect_latency_s` | 0.225 mm · 0.02 s | 2 mm · 0.0 s | 실기 탐침 약 2 mm(잠정), 스텝 모드는 지연 항 0 |
| | `result_dir` | `~/scan_results/sim` | `~/scan_results/real` | 절대경로 · 분리(#187, PR #188) |
| mqtt_bridge | `broker_port` | 없음(코드 기본) | 있음 | 브로커 주소는 launch 인자 |

## 규칙
- 수치는 yaml 의 **자기 노드 절**에만 둔다. 코드에 넣지 않는다(CLAUDE.md 규칙 7)
- 실기 튜닝 값은 `real.yaml` 을 `tune-MMDD-*` 브랜치의 PR 로 고친다. 실기 PC 에만 남은 값은 없는 값이다(`docs/conventions.md`)
- `test/test_config.py` 가 검사하는 것(CI):
  - 계약 이름(6.4)이 두 yaml 에 다 있다 · 0 이나 NaN 으로 채운 자리 표시가 없다
  - 두 노드가 같은 값이어야 하는 쌍: `over_force_n`(contact_detector · safety_monitor) · `drop_limit_m`(safety_monitor · robot_manager)
  - `contact_detector.source` 가 파일과 맞다 · `state_publish_period_s` 가 양수다
  - `result_dir` 이 절대경로(`~` 또는 `/`)이고 sim 과 real 이 다르다(PR #188)

## 실행 · 테스트
2026-09-24 에 이 PC(Ubuntu 24.04 · Jazzy)에서 실제로 돌려 통과한 명령만 적는다.
```bash
cd ~/ws_cobot_pjt/ws_cobot1
python3 -m pytest src/contact_scan_bringup/test/test_config.py -q     # ROS 없이 돈다
sod && colcon build --packages-select contact_scan_bringup && source install/setup.bash
colcon test --packages-select contact_scan_bringup && colcon test-result --verbose
```

## 알려진 문제 · 예정
| 번호 | 내용 |
|---|---|
| PR #161 | 머지 전. `real.yaml` · `sim.yaml` 에 `drop_limit_margin_m` 과 `home_pose_max_age_s` 를 더한다(실기 미검증) |
| phase 2 | `weld_manager` 노드를 6 번째로 더할 예정(`docs/phase2`, `weld_manager:` 절 · launch 인자). robot_manager 에 `path_*` 파라미터가 늘어난다 |
| — | sim 의 홈 · 박스는 옛 작업대 기준이다. sim 은 코드 경로 확인용이라 실기 좌표와 맞출 필요는 없지만, 두 홈이 다르다는 점을 알고 쓴다 |
| — | yaml 주석 몇 곳이 옛 값을 가리킨다(예: `sim_tip_radius_m` 주석의 "실측 r = 0.225 mm" 는 9/19 옛 탐침. 지금 탐침은 약 2 mm). 값은 맞고 주석만 낡았다 |
