# T19b sim(Virtual Mode) 종단 원본 — 2026-09-21

이슈 #19 완료 조건을 **실제 노드 4개 + Virtual Mode 에뮬레이터**로 확인한 실행의 원본이다.
요약과 판정은 [이슈 #19 결과 코멘트](https://github.com/yujh5537/rokey_cobot1_Weld-Made/issues/19)와 PR #104 본문에 있다.

**M2 통과 기록 자체는 현지가 [`daily/20260921.md`](../../daily/20260921.md) 2절에 먼저 남겼다.**
이 디렉터리는 그것의 **독립 2회차 재현**이고, 거기 없는 **시나리오별 원본**(방향 전환 · 유도 실패 · motion_id 대조 · 중지 · 종료)이 목적이다.

## 환경
- 시험자: 병후 (사람 입회 없음. 실기 아님)
- 환경: **Virtual Mode**(`dsr01_emulator`) + sim 입력원. 실기 아님
- 커밋: `a42bed6` + PR #100 의 `sim.yaml`(`2e1f75f`)을 커밋 없이 덮어씀 (#100 은 그 뒤 머지됨)
- 파라미터 파일: `contact_scan_bringup/config/sim.yaml`
- `ROS_DOMAIN_ID=35`, `ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST`
- 띄운 노드: `bringup.launch.py source:=sim` (mqtt_bridge 는 이 PC 에 paho 가 없어 미설치)
- 부재: 가상 직육면체 100 x 60 x 40 mm (`sim_box_size_m`). **실물 아님**
- 좌표 기준: `docs/contracts/units-frames.md`

## 절차와 파일

| 파일 | 무엇 |
|---|---|
| `A1_run.txt` | 정상 5점 탐색 `RunScan.Result`. `success: true`, 83초 |
| `A3a.txt` | `max_descend_m 0.01` 로 줄여 유도한 미접촉 실패 → `NO_CONTACT(300)` |
| `A3b.txt` | `max_slide_m 0.005` 로 줄여 유도한 미소실 실패 → `NO_EDGE(301)` |
| `A5_run.txt` | +x 밀기 중 `/scan/stop` → `STOP_REQUESTED(200)` |
| `A7_run.txt` | 모션 도중 SIGINT (Result 를 못 받고 끝난다) |
| `state.yaml` | `/scan/state` 전체 기록. phase 전이 |
| `event.yaml` | `/contact/event` 전체 기록. `motion_id` 대조 근거 |
| `result.yaml` | `/scan/result` 발행 내용 |
| `robot_status_operation.txt` | `/robot/status` 의 `operation` 전이만 뽑은 것. **방향 전환 절차(계약 7.3) 근거** |
| `nodes.log` | 자체 노드 4개의 launch 로그 전체 |
| `records/<scan_id>/` | `result_store` 원본(`progress.json` · `result.json`). 이 실행에서 만들어진 6건 |

`/robot/status` 원본은 1.47 MB 라 넣지 않았다(10 Hz 전체 메시지). 필요한 것은 `robot_status_operation.txt` 로 뽑아 뒀다.

`robot_status_operation.txt` · `state.yaml` · `event.yaml` 은 **이 세션의 모든 실행이 이어져 있다**(A1 → A5 → A6 → A3a → A3b → A7).
A1 구간은 `4 0 1 0 2 0 3 0 1 0 1 0 1 0 3 0 1 0 1 0 1 0 3 0 1 0 1 0 1 0 3 0 1 0 4` 까지다 — 앞의 `4` 가 사전 홈,
마지막 `1 0 4` 가 마무리 들어 올림 + `OP_HOME` 이다(계약 7.4).

## 측정값

| 항목 | 가상 박스 참값 | 측정 | 오차 |
|---|---|---|---|
| 가로 (x⁺ − x⁻) | 100.00 mm | **99.78 mm** | −0.22 mm |
| 세로 (y⁺ − y⁻) | 60.00 mm | **59.74 mm** | −0.26 mm |
| 높이 (z_top − support_z) | 40.00 mm | **39.87 mm** | −0.13 mm |

`dims_valid` · `box_valid` 모두 true. 현지의 1회차(99.81 / 59.77 / 39.86)와 0.03 mm 안에서 같다.

**이 수치는 sim 모델과 편향 보정 코드가 서로 맞는다는 뜻일 뿐, 실기 치수 정확도의 근거가 아니다**(현지의 기록과 같은 단서). sim 박스는 모서리가 수학적으로 예리하고 잡음이 없다. 실기 정확도는 TR-02(T31)에서만 판정한다.

## 조건별 결과

| 이슈 #19 완료 조건 | 결과 | 원본 |
|---|---|---|
| 전체 시퀀스가 돈다 | ✅ phase `IDLE → PREPARING → TOP_SEARCH → EDGE_SEARCH → GEOMETRY → HOMING → DONE`, `/scan/result` 는 HOMING **전** 발행 | `A1_run.txt` · `state.yaml` |
| 방향 사이에 팁을 들어 기준 원점 복귀 | ✅ 방향마다 `OP_MOVE_TO` **3개**, `OP_DESCEND` **없음**(계약 7.3) | `robot_status_operation.txt` |
| 실패를 원인 · 단계 · 위치로 기록 | ⚠️ 이 실행 시점에는 **위치가 없었다.** PR #118 이 `FailureRecord.pose` 를 더해 채웠다 | `A3a.txt` · `A3b.txt` · `records/` |
| 이벤트를 `motion_id` 와 대조 | ✅ 이벤트 5건 `motion_id = 2, 3, 7, 11, 15` | `event.yaml` |

## 관찰 · 다음 조치

- **`/robot/stop` 에 서버가 없었다.** 중지는 goal cancel 로만 됐다(멈추긴 했고 순응도 풀렸다). → PR #101(T15)에서 구현됨
- **SIGINT 종료가 조용하지 않았다.** `robot_manager` · `safety_monitor` 가 `exit code -2`. → 이슈 #111. `scan_manager` 몫은 PR #119 로 끝
- **모션 도중 노드가 죽으면 로봇이 계속 간다.** SIGINT 시점 팁 z = 448.5 mm → 노드 사망 뒤 z = **420.0 mm**(= 기준점 500 − `max_descend_m` 80). 감시 없이 28.5 mm 더 내려갔다 → 팀 안건(D2)
- `safety_monitor` 가 같은 줄에서 severity 를 바꿔 죽는 결함을 여기서 찾았다 → 이슈 #102(PR #117 로 머지됨)
- **이 PC 에서 Virtual 을 띄울 때는 load average 가 3 이하일 때 시작할 것.** DRCF 에뮬레이터가 물리 4코어(i5-8265U) 중 3.6~3.7 코어를 쓰고, load 가 16 을 넘으면 `dsr_controller2` 가 `get_current_posx` · `get_tool_force` 에 응답을 멈춘다. 그러면 `SAMPLE_STALE(403)` → `/robot/stop` → 스캔 중단으로 간다. 드라이버를 내릴 때 `run_emulator` 프로세스가 남으니 같이 죽일 것
