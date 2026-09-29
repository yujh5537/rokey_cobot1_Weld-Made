# weld_manager — 스캔 결과로 용접 모션 (phase 2, 6번째 노드)

스캔이 남긴 `result.json`(직육면체 모서리 12 개)에서 용접선 8 개(윗면 4 + 세로 4)를 읽어, 두 면의 법선을 이등분하는 45° 자세 · 스탠드오프 · 지그재그 위빙 경유점을 만들고, robot_manager 에 **접근 1 → 접근 2 → 경로(`ExecutePath`) → 후퇴**를 선마다 보낸다. 접촉하지 않는다(힘 · 순응 제어 없음). 계약은 `docs/phase2/`(`weld-motion.md` · `weld-ros-interfaces.md`)이고 코드보다 우선한다. 담당 현지.

## 구조

| 파일 | rclpy | 내용 |
|---|---|---|
| `weld_manager/weld_path.py` | 없음 | 8 선 추출 · 자세(quaternion) · 스탠드오프(D22) · 위빙 경유점 · 접근/후퇴/z_safe · 작업영역 · 툴 외형 검사(D23). 입력 작업대 좌표(m) → 출력 Base 좌표 `WeldPlan` |
| `weld_manager/sequence.py` | 없음 | `WeldRunner`(선 순서 · 판정 · 결과 · 마무리 홈) · `HomeRunner`(안전복귀) · `classify()`. 바깥일은 `Ports` 뒤 |
| `weld_manager/state_machine.py` | 없음 | `WeldState.phase` 전이표. 재시작(RESUME) 없음(D7) |
| `weld_manager/params.py` | 없음 | 파라미터 이름 · 필수 · 범위 검사. **모션 수치에 코드 예비값 없음**(규칙 7) |
| `weld_manager/weld_record.py` | 없음 | 결과 원본 `<result_dir>/<scan_id>/weld/<weld_id>.json` (임시 파일 → fsync → replace) |
| `weld_manager/contract_enums.py` | 없음 | msg 상수 사본. `test_contract_match.py` 가 msg 와 대조 |
| `weld_manager/conversions.py` | 있음 | 순수 자료 ↔ msg (NaN · 시각 0 규칙) |
| `weld_manager/weld_manager.py` | 있음 | 노드. 위 모듈을 ROS 에 잇기만 한다 |
| `test/fake_peers.py` | 있음 | 가짜 robot_manager · scan_manager · safety_monitor (노드 시험용) |

`scan_manager.result_store`(순수 Python)를 import 해 스캔 결과를 읽는다. DSR API 는 부르지 않는다(robot_manager 만).

## 입출력 (계약 `weld-ros-interfaces.md`)

| 방향 | 이름 | 타입 | 절 |
|---|---|---|---|
| 서버 | `/weld/run` | `RunWeld` (scan_id `""` = 최신 성공 결과, `start_line` · `end_line` 생략 불가) | 5.1 |
| 서버 | `/weld/home` | `ReturnHome` (안전복귀: 툴 축 뒤 물러남 → z_safe → OP_HOME) | 7.2 |
| 서비스 | `/weld/stop` | `StopWeld` (휴지 중에는 `/robot/stop` 을 부르지 않는다) | 4.1 · 7.2 |
| 클라이언트 | `/robot/execute_motion` · `/robot/execute_path` · `/robot/stop` | robot_manager | 5.2 |
| 구독 | `/scan/state`(배타 600) · `/robot/status` · `/safety/status`(래치) · `/robot/sample`(시작 위치 · 툴 등록 · D33 복구 출발점) | | 2 · 7.1 |
| 발행 | `/weld/state`(변경 + 주기) · `/weld/result`(끝날 때 한 번, 홈 복귀보다 먼저) · `/weld/log` | | 3 · 7.3 |

## 동작 규칙 (계약과 같다)

- **시작 거절 표**(5.1)를 순서대로 본다: BUSY · 파라미터 없음(102) · `/scan/state` 없음/오래됨(101) · 스캔 진행 중(600) · 래치(103) · 로봇 연결 없음(104) · 결과 없음(602) · 선 범위(603) · 덮어쓰기 값(102) · 샘플 없음(307) · 툴 미등록 의심(302) · 작업영역 · 툴 외형(604). 거절은 phase 를 바꾸지 않고 Result 로 준다.
- **D30**(9/26 갱신, #198): 시작 때 팁이 z_safe 아래면 거절하지 않고 툴 축 뒤(−d)로 `approach_m` 물러난 뒤(`approach_speed_mps`) 같은 x · y · 현재 자세로 z_safe 까지 올린다(`travel_speed_mps`). D33 복구 · 안전복귀와 같은 순서.
- **D33 선 실패 뒤 계속**(`continue_on_line_failure`, 출발값 true. 9/26 좁힘, #198): 한 선의 goal(접근 1 · 2 · 경로 · 후퇴)이 `ROBOT_ERROR(204)` 로 끝나면 그 선을 `FAILED` 로 적고 `/robot/sample` 로 팁 위치를 본다. **z_safe 위**(여유 `path_tolerance_m` — 후퇴점 도착도 그 허용치로 판정되므로)면 도달 불가 · 출발 안 함으로 보고 이동 없이 **다음 선의 접근 1**. **z_safe 아래**(원인 모름 · 접촉 가능성)면 툴 축 뒤(−d)로 `approach_m` 물러난 뒤 같은 x · y 로 z_safe 까지 올리는 복구만 하고 **ERROR**(뒤 선 NOT_ATTEMPTED). 팁 위치를 모르면 · 복구 이동이 실패하면 ERROR. **204 만이다** — 정지 · 취소 · 과대 외력 · 시간 초과 · 래치 · 604 는 그대로 ERROR · STOPPED. 끝까지 갔는데 FAILED 가 있으면 phase 는 DONE, 마무리 홈 복귀는 그대로 하고, `WeldResult.success=false` · `reason_code` = 첫 FAILED 선의 코드 · `detail` = `L1,L5 FAILED`. RunWeld `Result.success` 도 false. 같은 선을 다시 시도하지 않는다. 근거: 9/23 M1(#186)에서 L1 · L5 가 45° 자세로 도달 불가(D27).
- **정지**: `/weld/stop` 만 STOPPED 다. 요청하지 않은 정지(웹 스캔 중지 · safety_monitor)는 ERROR(D25). 정지 완료는 요청 뒤에 찍힌 `/robot/status` 의 `connected && !moving` 으로만 본다.
- 어떤 실패든 자동 복귀 · 자동 재시도는 없다(D33 의 복구 이동은 "다음 선을 보낼 수 있는 높이로 올리는 것"이지 재시도가 아니다). 실행 중 파라미터 변경은 거절한다.
- 결과 · 파일에서 모르는 값은 null 이다(0 으로 채우지 않는다, 규칙 4). `stop_pose` 는 그 선을 끝낸 goal 의 Result 좌표만 쓴다.

## 파라미터

이름 · 출발값 · 뜻은 계약 `docs/phase2/weld-motion.md` 6절이 원본이고, 값은 `contact_scan_bringup/config/{sim,real}.yaml` 의 `weld_manager:` 절에만 있다(근거는 그 파일의 주석). 특히:

- `result_dir` · `tip_radius_m` 은 scan_manager 와 **같은 값**이어야 한다(`test_config` 가 검사).
- `tool_profile_u_m` · `tool_profile_r_m` 은 M2(#186) 캘리퍼 실측값이다. **real.yaml 에는 실측 전이라 없고, 없으면 `/weld/run` 을 102 로 거절한다.** 세로선(L4~L7)의 툴 외형 검사에만 쓰인다. 9/29 학민 슬롯에서 재면 채운다(간섭 거리 D 12 mm 기준, `tool-tcp-register.md`).
- `tool_roll_deg[8]`: sim 은 `[0, 0, 180, 180, 0, 0, 180, 180]`(모두 0 이면 L7 에서 J6 −360° 한계, 알람 9008). real 은 M1 확인 전 0 유지.
- **`tilt_line_offset_deg[8]`**(D38, #218): 선별 기울임. real 은 L1 −30(→ 15°): 45° 면 손목 중심이 어깨에서 826 mm 로 팔 길이 779 mm 밖(9/29 roll 3 종 모두 1206). L5 는 어떤 값으로도 안 되어 시연 제외. 세로선은 낮추면 핑거가 옆면에 닿아 계획 단계에서 거절된다.
- **`target_shift_m[x, y, z]`**(D37, #216) · **`standoff_line_offset_m[8]`**(D36): 9/29 실기 띄움 보정. 순서는 **평행 이동 먼저**(−y 쪽 선 멀고 +y 쪽 선 가까움 = 부재 자리 치우침, real +y 3.5 mm) → 그래도 선마다 남는 차이를 선별 보정으로. 선별 합 ≤ 0 은 102. 둘 다 `ros2 param set /weld_manager …` 로 실기 중 바꿔 볼 수 있다(yaml 은 뒤에).
- `path_tolerance_m`: robot_manager 가 line 의 중간 점에도 쓴다(D32). ≤ 0 · NaN 은 604.
- **`top_line_offset_dir`**(D34, `tool` 기본 / `vertical`): 윗면선(L0~L3)의 접근 · 후퇴점을 툴 축 뒤(−d)로 둘지 수직 위(+z)로 둘지. 세로선은 항상 `tool`. 9/29 맨 앞 2 자세(L0 후퇴점 · L6 접근 1)가 도달 불가면 real.yaml 한 줄을 `vertical` 로 바꾼다 — 코드 변경 없음.
- **`path_point_dwell_s`**: `ExecutePath.timeout = motion_timeout_s + 경유점 수 × 이 값`. line 모드는 점마다 정지 확인(`arrival_grace_s`)이 붙어 100 점 · 120 s 고정이면 실기에서 초과한다(학민 #191). sim 0.5(Virtual 실측) · real 2.0(설계 출발값, 미실측).

## 실행

```bash
# 순수 시험 (ROS 없이). 디렉터리로 주면 contact_scan_interfaces 가 없는 셸에서는 첫 모듈 스킵에 수집이 끊기므로 파일을 나열한다
cd ws_cobot1 && python3 -m pytest src/weld_manager/test/test_{weld_path,sequence,state_machine,params,weld_record}.py -q
# colcon (별도 build/install base 권장. build_p2 는 symlink 없이 만든 트리라 --symlink-install 을 주지 않는다)
sod && colcon build --build-base build_p2 --install-base install_p2 --packages-select contact_scan_interfaces weld_manager contact_scan_bringup
source install_p2/setup.bash && colcon test --build-base build_p2 --install-base install_p2 --packages-select weld_manager contact_scan_bringup
```

Virtual 종단(도메인 31~39 중 조용한 번호, `ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST`, 에뮬레이터 1 개):

```bash
sodvir                                                            # 터미널 1 (에뮬레이터 + 두산 드라이버)
ros2 launch contact_scan_bringup bringup.launch.py source:=sim    # 터미널 2 (노드 6 개)
ros2 action send_goal /scan/home contact_scan_interfaces/action/ReturnHome "{request_id: h1}"   # 홈 먼저 (특이점 회피)
ros2 action send_goal /scan/run contact_scan_interfaces/action/RunScan "{request_id: s1}"       # 약 80 s → ~/scan_results/sim/<scan_id>/result.json
ros2 action send_goal /weld/run contact_scan_interfaces/action/RunWeld "{request_id: w1, scan_id: '', start_line: 0, end_line: 7}" --feedback
ros2 topic echo /weld/state    # IDLE → PREPARING → (APPROACH → WELDING → RETREAT) × 8 → HOMING → DONE
```

스캔 없이 보려면 `docs/phase2/fixtures/sim_20260921-131938-1493.result.json` 을 `~/scan_results/sim/20260921-131938-1493/result.json` 으로 복사한다.

## 확인 수준

| 항목 | 상태 |
|---|---|
| 순수 시험 206 · 노드 시험(가짜 robot_manager) 14 | 통과 (2026-09-25, 현지 PC) |
| Virtual 종단 8 선(45° · 위빙 · sim 픽스처 박스 100 × 60 × 40) | **통과** 2026-09-24 (P2-5, 242 s, 경로 점 27/17/27/17/11/11/11/11, 안전 이벤트 0). D33 반영 뒤 재검은 아래 기록 |
| 실기 (2026-09-29, 명령 현지 · 입회 학민) | **6 선 DONE**(L0 · L2 · L3 · L4 · L6 · L7), L1 · L5 는 도달 불가로 FAILED 뒤 계속(D33). 위빙 L3 · L7 DONE. 점당 정지 0.50~0.58 s. 안전 이벤트 0. 입력은 9/23 스캔(오늘 스캔은 NEG_Y 실패). 스탠드오프 y 치우침 3~4 mm 관찰. `docs/test-reports/realrobot-session_20260929.md` |

## 9/29 실기 통합 순서 (README 가 아니라 `docs/phase2/README.md` "통합 순서" 가 원본. 여기는 weld_manager 쪽 보탬)

1. 세션 시작 점검(탐침 상태 전제조건, `units-frames.md`) → 실기 스캔 1 회 → `result.json` 확인.
2. **학민 30~35 분 슬롯 먼저**: M2 캘리퍼 3 항목(→ `tool_profile_*`) · **세로선 bottom 을 계약 z 104.13 으로 한 자세**(작업대 여유가 가장 좁은 자리, 학민 계산 손가락 끝 약 15.6 mm · #191 리뷰 ③) · M4 line 실기 1 회 · 배치 사진.
3. 1 단계(반드시 성공): `tilt_deg=0 · weave 0 · 속도 낮게` 로 **L0 만**(`start_line=0, end_line=0`) → 45° 로 L0 → `end_line=3`.
4. 2 단계(조건부): 세로선 L4~L7(툴 외형 검사 통과한 선만) → 위빙 켬. L1 · L5 는 FAILED 로 기록되고 계속된다(D33). 입회자는 비상정지 앞에 선다.
5. 실기에서 나온 값은 `tune-0929-weld-*` 브랜치로 따로 PR.

## 알려진 문제 · 의존

- robot_manager `on_path_goal_request` 의 순응 · 힘 제어 검사는 해제 *호출 성공* 플래그다(#125 전까지). 호출은 성공했는데 실제로 안 풀린 경우를 이 안전망이 통과시킨다. ExecutePath 는 100 mm/s 까지라 1차 SLIDE 보다 대가가 크다(학민 #191 리뷰 ④).
- 노드를 다시 띄운 뒤 아직 용접을 한 번도 계획하지 않았으면 `/weld/home` 은 z_safe 를 몰라 **물러난 뒤 바로 OP_HOME(관절 이동)** 이다. `/weld/home` 은 스캔 진행 여부를 보지 않는다(계약 7.1 에 요구 없음). 9/29 관제자는 자세를 보고 누른다(독립 재검 🔵9).
- D33 의 z_safe 판정 · 복구 출발점은 실패한 goal 의 Result **뒤에 찍힌** `/robot/sample` 만 쓴다(`sample_timeout_s` 안에 없으면 위치 모름 → ERROR). 멈추기 전 샘플로 "z_safe 위" 를 잘못 판정하지 않게 한다(독립 재검 🟡3).
- `/weld/home` 에서 현재 위치를 모르면(샘플 없음) 물러남 · 올림 없이 OP_HOME 만 보낸다 — 기울인 자세에서 곧장 관절 이동이 나가므로 관제자가 보고 누른다(7.2).
- 브리지 `weld/*` 중계(P4, 의석) · 브리지 operation/reason 표 PR(머지 순서 0 번)이 아직 없다. 그 전까지 웹 없이 `ros2 action send_goal` 로 시연한다.
