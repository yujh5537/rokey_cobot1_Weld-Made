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

계약 5.1 · 3.2 · `weld-motion.md` 5절(D33)과 같다. "z_safe 아래에서의 물러남 · 올림" 경로는 Virtual 로 만들 방법이 없어(접근 2 · 경로 도중 204 를 일으킬 수단이 없다) 가짜 robot_manager 노드 시험(`test_failure_below_z_safe_recovers_by_backing_off_and_lifting`)과 순수 시험으로만 확인했다.

정리: `docker rm -f dsr01_emulator`, 노드 종료. `tool_roll_deg` 는 노드 메모리에서만 바꿨다(yaml 은 그대로).

## 3. 남는 것 (9/29 실기)

- 실기에서 L1 · L5 가 45° 로 도달 불가(M1, D27). D33 대로 그 두 선만 FAILED 로 남고 6 선이 DONE 인지, 실패 선의 "약 2 s"(재전송 1 회 + `arrival_grace_s` × 2)가 실제로 얼마인지.
- 세로선 bottom 을 계약 z 104.13 으로 한 자세 먼저(학민 슬롯, 손가락 끝 여유 약 15.6 mm 계산값).
- `tool_profile_u_m` · `tool_profile_r_m`(M2 캘리퍼) 를 real.yaml 에 채우기 전에는 `/weld/run` 이 102 로 거절된다.
