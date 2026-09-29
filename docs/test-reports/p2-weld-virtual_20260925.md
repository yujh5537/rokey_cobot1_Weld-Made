# phase 2 weld_manager Virtual 종단 — D33 반영 뒤 재검 (2026-09-25)

- 실행: 현지 PC(Ubuntu 24.04 · Jazzy), Claude 실행. `ROS_DOMAIN_ID=34` · `ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST`, 에뮬레이터 `dsr01_emulator`(doosanrobot/dsr_emulator:3.0.1) 1 개.
- 코드: 브랜치 `p2-weld-manager` `096f0c3`(계약 `origin/p2-contract` `2a644c7` = main `82d0fa2` 포함 위). 빌드 `build_p2/install_p2`(symlink 없음).
- 입력: `~/scan_results/sim/20260924-183049-2100/result.json`(9/24 sim 스캔, 가상 박스 100 × 60 × 40 mm). `scan_id: ""` 로 최신 성공 결과 선택.
- 절차: `sodvir` → `bringup.launch.py source:=sim`(노드 6 개, mqtt_bridge 는 이 PC 에 paho 가 없어 죽는다 — 기존과 같음) → `/scan/home` → `/weld/run`(L0~L7).
- 실기: **미실시**(9/29).

## 1. 정상 8 선 (sim.yaml 그대로, tool_roll [0, 0, 180, 180, 0, 0, 180, 180])

| 항목 | 결과 |
|---|---|
| RunWeld Result | `success=true` · reason_code 0 · weld_id `20260925-153820-2948` |
| `/weld/state` | IDLE → PREPARING → (APPROACH → WELDING → RETREAT) × 8 → HOMING → DONE. `lines_done` 8 |
| `/weld/result` · 파일 | 8 선 모두 `STATUS_DONE`, `~/scan_results/sim/20260924-183049-2100/weld/20260925-153820-2948.json` 저장 |
| 소요 | 15:38:16 → 15:42:22, **246 s**(9/24 P2-5 는 242 s) |
| 경로 점 | L0 27 / L1 17 / … (robot_manager `경로 goal 종료: 점 27/27`) |
| 경고 · 안전 이벤트 | bringup 로그 WARN · ERROR 0 건(Overrun · mqtt_bridge 제외), SAMPLE_STALE · OVER_FORCE · 래치 0 |

D33 코드(선 실패 뒤 계속)를 넣고 `run()` 을 `_run_line` 로 나눈 뒤에도 정상 흐름 · goal 수 · 결과가 9/24 와 같다.

## 2. D33 — 한 선을 일부러 도달 불가로 (tool_roll 전부 0)

9/24 P2-5 에서 `tool_roll_deg` 가 모두 0 이면 선을 옮길 때마다 툴이 같은 쪽으로 돌아 **L7 접근에서 J6 가 −360° 한계를 넘었다**(알람 9008). 실기 M1 의 "도달 불가 자세" 와 같은 부류의 204 라, 휴지 중 `ros2 param set /weld_manager tool_roll_deg "[0.0 × 8]"` 로 바꾸고 같은 goal 을 보냈다.

| 항목 | 결과 |
|---|---|
| RunWeld Result | `success=false` · reason_code **204** · detail **`L7 FAILED`** · weld_id `20260925-154306-0513` (goal 상태 ABORTED — success=false 인 Result 는 1차와 같이 abort) |
| L7 접근 1 | robot_manager: `이동이 끝났지만 목표에서 82.1 mm 떨어져 있다 (허용 3.0 mm)` → `ROBOT_ERROR(204)`. 컨트롤러 알람 9008(J6 한계) 2 건 |
| weld_manager | `L7 실패 → FAILED 로 기록하고 다음 선으로 계속한다(D33)` → `/robot/sample` 팁 z 가 z_safe 위 → **복구 이동 없이** 다음 단계. L7 이 마지막 선이라 결과 저장 → HOMING |
| 마무리 | 마무리 올림(motion 30, 서 있던 z_safe 자리) → OP_HOME(motion 31) 모두 `reason=0`. phase **DONE**, `lines_done` 7 |
| `/weld/result` · 파일 | L0~L6 `DONE`, L7 `FAILED`(reason_code 204, detail 위 문장, stop_pose 있음), `success=false`. 파일 `…/weld/20260925-154306-0513.json` |
| 소요 | 15:43:03 → 15:46:48, **225 s**(실패 선에 쓴 시간 약 1 s + 마무리) |
| 그 밖 | SAMPLE_STALE · OVER_FORCE · 래치 0. 두 번째 작업의 motion_id 는 1 부터(작업마다 새로) |

계약 5.1 · 3.2 · `weld-motion.md` 5절(D33)과 같다. "z_safe 아래에서의 물러남 · 올림" 경로는 Virtual 로 만들 방법이 없어(접근 2 · 경로 도중 204 를 일으킬 수단이 없다) 가짜 robot_manager 노드 시험과 순수 시험으로만 확인했다.

> 9/26 갱신(#198, D33 좁힘): z_safe 아래의 204 는 복구 이동 뒤 **ERROR** 로 끝나게 바뀌었다(`test_failure_below_z_safe_recovers_then_errors`). 위 2절의 "z_safe 위 → 이동 없이 계속" 은 그대로다. Virtual 재실행은 하지 않았다(바뀐 경로는 Virtual 로 만들 수 없는 쪽).

정리: `docker rm -f dsr01_emulator`, 노드 종료. `tool_roll_deg` 는 노드 메모리에서만 바꿨다(yaml 은 그대로).

## 4. 9/27 재검 — 스택 C 머리 `2c70131` (독립 재검 🟡2)

9/25 기록 뒤 #198(D30 물러남 · D33 좁힘) · D34 `top_line_offset_dir` · `path_point_dwell_s` 경로 timeout · D33 판정 샘플 시각(🟡3) · 204 명시(🔵6)가 들어가 다시 돌렸다.
- 빌드: 스택 C 트리 전체를 `build_p2/install_p2` 에 새로 빌드(symlink 없음). 이 트리의 robot_manager 는 스택 base `a81cc2d` 라 **D35(#191 `7ed943c`)는 들어 있지 않다**.
- 실행: 현지 PC, Claude, `ROS_DOMAIN_ID=36` · LOCALHOST, 에뮬레이터 1 개. `/scan/home` → `/scan/run` → `/weld/run`(L0~L7, `top_line_offset_dir: tool`) → `ros2 param set /weld_manager top_line_offset_dir vertical` → `/weld/run` 다시.

| 항목 | 결과 |
|---|---|
| 스캔 | `success=true`, 약 81 s(18:09:47 → 18:11:08) |
| 용접 · `tool` | `success=true` · 8 선 `DONE` · **246 s** · weld_id `20260927-181112-6925` · 경로 점 27/17/27/17/11/11/11/11 |
| 용접 · `vertical`(D34) | `success=true` · 8 선 `DONE` · **239 s** · weld_id `20260927-181518-5568` · 경로 점 같음(오프셋만 바뀌고 경로는 그대로). 세로선은 계약대로 항상 `tool`. 접근점 좌표는 robot_manager 로그에 없어 순수 시험(`test_top_line_offset_vertical_moves_approach_straight_up`)으로 확인 |
| 안전 이벤트 | 작업 중 0 건. 기동 직후 SAMPLE_STALE 2 건(에뮬레이터 연결이 늦게 붙는 동안, 래치 403) → `/safety/reset` 뒤 시작. 기동 절차 문제이고 weld_manager 와 무관 |

기동 절차 메모(Virtual): `sodvir` 의 "Configured and activated dsr_controller2" 뒤에도 에뮬레이터 접속 재시도가 이어질 수 있다. bringup 은 `/robot/status.connected=true` 를 본 뒤 띄우고, 기동 중 래치가 걸렸으면 `/safety/reset` 으로 푼다.

## 3. 남는 것 (9/29 실기)

- 실기에서 L1 · L5 가 45° 로 도달 불가(M1, D27). D33 대로 그 두 선만 FAILED 로 남고 6 선이 DONE 인지, 실패 선의 "약 2 s"(재전송 1 회 + `arrival_grace_s` × 2)가 실제로 얼마인지.
- 세로선 bottom 을 계약 z 104.13 으로 한 자세 먼저(학민 슬롯, 손가락 끝 여유 약 15.6 mm 계산값).
- `tool_profile_u_m` · `tool_profile_r_m`(M2 캘리퍼) 를 real.yaml 에 채우기 전에는 `/weld/run` 이 102 로 거절된다.
