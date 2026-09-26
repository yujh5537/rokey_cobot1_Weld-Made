# phase 2 — 스캔 결과로 용접 모션 (2026-09-23 ~ 09-29)

1차(접촉 탐색 스캔, PR #179 로 실기 종단 3회 연속 성공)에 이어, **스캔으로 얻은 직육면체의 모서리 8 개를 따라 용접하듯 움직이는** 2차 프로젝트다. 도구는 그대로(M0609 · RG2 · 인공눈물 탐침), 접촉하지 않고 띄워서 간다.

이 디렉터리는 phase 2 의 **계약**이다. 1차 계약(`docs/contracts/`)의 구속은 받지 않지만, 1차 위에 **더하는** 방식이라 1차 문서를 같이 본다.

| 문서 | 내용 |
|---|---|
| `weld-motion.md` | 8 선 정의 · 툴 자세(45° 이등분) · 스탠드오프 · 위빙(지그재그 경유점) · 접근/후퇴 · 파라미터 표 |
| `weld-ros-interfaces.md` | 토픽 · 서비스 · 액션, 타입 전문(`contact_scan_interfaces` 와 동기화 검사), 시작 거절 사유, 배타 규칙 |
| `weld-mqtt-schema.md` | `cmd/weld/*` · `weld/*` 토픽과 JSON, 웹 표시 |
| `measurements-20260923.md` | **오늘 실기로 재야 하는 것**(연휴 전 마지막 기회). 별도 PR `p2-measure-0923` |
| `tasks/` | 담당별 지시서 P1~P5 |
| `fixtures/` | 실기 스캔 `result.json`(오늘 복사) — 연휴 중 오프라인 개발 입력 |

## 결정 (2026-09-23 병후)

| # | 결정 |
|---|---|
| D1 | 툴은 두 면의 법선을 이등분하도록 기울여 진행하고, 진행 방향과 수직으로 파형(위빙)을 그린다 |
| D2 | **띄운다.** 스탠드오프 수 mm, 힘 · 순응 제어 없음 |
| D3 | 세로 모서리도 D1 + 45° 기울임 |
| D4 | 세로선 하단은 `bottom_margin_m` 을 두고 받침대 위에서 끝낸다 |
| D5 | `RunWeld` goal 에 `scan_id`("" = 최신), result_store 에서 읽는다 |
| D6 | 스캔 · 용접은 배타. 스캔이 휴지가 아니면 용접 거절, 용접 중이면 스캔 거절 |
| D7 | 재시작 없음. 대신 `start_line` |
| D8 | 순서 윗면 4 변 루프 → 세로 4 개(위 → 아래). 코너마다 정지. 속도는 스캔처럼 느릴 필요 없다 |
| D9 | 웹: 8 선 · 현재 선 강조 · 완료 선 색 · 비드 궤적(robot/sample 누적) · 진행률. App.jsx 분리는 담당자 판단 |
| D10 | 같은 레포, `weld_manager` 패키지 + `docs/phase2/`. 1차 규약에서 유연하게 |
| D11 | 일정: 9/23 계획 + 필수 실기 측정 → 9/24~28 연휴(비대면, 로봇 없음) → 9/29 실기 적용 · 완성 |
| D12 | 담당: 병후 계약 · 문서 · 발표 / 현지 weld_manager **+ robot_manager `ExecutePath`(P1, 9/24 학민 → 현지. 리뷰 학민)** / 학민 1차 최적화 · 측정 · P1 리뷰 / 의석 웹 · 브리지 |
| D13 | 계약을 먼저(오늘), 그 뒤 병렬 |
| D14 | robot_manager 추가는 담당자 판단으로 단순화 가능(movel 등) |
| D15 | safety_monitor 는 대체로 그대로 |
| D16 | weld_manager 상태기계는 scan_manager 패턴 참고, 복제 강제 없음 |
| D17 | 인터페이스 목록 채택(`weld-ros-interfaces.md`) |
| D18 | 허용오차 ±3 mm |
| D19 | 위빙은 지그재그 경유점(`ExecutePath`). `move_periodic` 은 쓰지 않는다 |
| D20 | mqtt_bridge `weld/*` 는 의석 |
| D21 | 9/23 실기 측정: 정 학민 · 부 병후. 별도 PR |
| D22 | `standoff_m` = 팁 구 표면 ↔ 이음선 최단거리(세로선은 축 방향 약 5.07 mm) |
| D23 | 세로선 툴 외형 검사(`tool_profile_m`, M2 실측)로 겹치면 604 거절 |
| D24 | `tool_roll_deg` 는 선별 8개 배열. 위빙 방향은 roll 과 무관 |
| D25 | weld_manager 가 요청하지 않은 정지는 STOPPED 가 아니라 ERROR |
| D26 | 이 최초 계약 PR(#184, 30 파일)은 규칙 5 의 예외. 이후 PR 은 15 파일 |
| D27 | 9/29 단계: 윗면 4 선 = 반드시 성공, 세로선 · 위빙 = 조건부 → **M1(9/23, #186): L1 · L5 는 45° 자세로 도달 불가**(플랜지 한계 689~761 mm, 기울기 · 롤 · 재배치로 해결 안 됨). 9/29 기대는 윗면 3 선(L0 · L2 · L3) + 세로 3 선(L4 · L6 · L7), L1 · L5 는 FAILED 로 기록(D33) |
| D28 | `RunWeld.end_line` 추가(기본 7, 생략 불가). 툴 외형 파라미터 이름 `tool_profile_u_m` · `tool_profile_r_m` |
| D29 | weld_manager 는 속도 상한을 검사하지 않는다. 상한은 robot_manager `path_max_speed_mps` → 604 |
| D30 | 시작 때 팁이 z_safe 아래면 거절하지 않고 **툴 축 뒤(−d)로 `approach_m` 물러난 뒤 z_safe 까지 수직 상승** 뒤 시작(9/26 갱신: D33 복구 · 7.2 안전복귀와 같은 순서. 현지 #184 리뷰). 자세 허용치 `orientation_tolerance_deg` 는 여유 있게(15°) |
| D31 | `ExecutePath` 는 `path_mode` line(기본, 점마다 정지) / spline. `move_line`+radius 블렌딩은 비동기에서 불가(드라이버 소스 확인). `path_max_points` 100. **소스 확인에 그치지 말고 호출 확인까지 한다** → 호출 확인 결과(현지 9/24 Virtual, #191): **spline 은 응답이 점당 약 30 ms 늦어 호출 줄이 막히고 샘플이 끊긴다(SAMPLE_STALE). 쓰지 않는다.** 코드 · 파라미터는 남기되 기본 · 실기 모두 line |
| D33 | **한 선이 실패하면 그 선만 FAILED 로 기록하고 다음 선으로 계속한다**(병후 9/25, 학민 #184 리뷰 ①). 계속하는 실패 = 그 선의 goal(접근 1 · 2 · ExecutePath · 후퇴)이 `ROBOT_ERROR(204)` 로 끝났고 **그때 팁이 z_safe 위에 있는 경우**(도달 불가 · 출발 안 함 — 이전 후퇴점에 그대로 서 있다. 판정 `z ≥ z_safe − path_tolerance_m`, 9/26). **z_safe 아래에서 난 204(원인 모름 · 접촉 가능성)는 복구 이동 뒤 ERROR** 로 끝낸다(9/26 좁힘, 현지 #184 리뷰). 정지 · 취소 · 과대 외력 · 시간 초과 · 래치는 그대로 ERROR · STOPPED. 파라미터 `continue_on_line_failure`(true). 타입 변경 없음(`WeldLine.STATUS_FAILED` · `WeldResult.success=false`) |
| D34 | **접근 · 후퇴점 도달성(학민 9/26)**: M1 은 목표 위 수직 자세만 확인했고, phase 2 접근 · 후퇴점(툴 축 뒤 30 mm + z_safe)은 플랜지가 더 멀리 나가 L0 후퇴점 733 · L6 접근 1 729 mm 가 M1 의 도달 712 · 실패 738 사이 빈 구간이다(학민 계산, 레포 미기록). **9/29 실기 맨 앞에 두 자세(L0 후퇴점 · L6 접근 1, movel · 접촉 없음, 약 2 분)를 확인**하고, 실패하면 윗면선 오프셋을 수직 위로 바꾼다 — 파라미터 `top_line_offset_dir`(`tool` 기본 / `vertical`, weld-motion 6절)로 현지가 미리 준비, 9/29 는 yaml 전환만 |
| D32 | `path_tolerance_m` 은 마지막 점뿐 아니라 line 모드의 **중간 점 도착 판정에도** 쓴다(멈춘 자리가 그 점에서 허용치 밖이면 204). `≤ 0` · NaN 은 604 로 거절(현지 해석 9/24, 병후 채택 9/25) |

**계약 작성 중 드러난 것 → 2026-09-23 병후 결정**
- **`move_periodic` 은 직선 이동과 겹쳐 실행되지 않는다**(dsr_msgs2 `MovePeriodic.srv` 는 제자리 주기 운동). 위빙은 **지그재그 경유점**으로 만들고 robot_manager 가 `ExecutePath` 로 지난다 — **채택(D19)**. 실행은 `move_spline_task` 또는 `move_line` 반복 중 실기에서 되는 것으로.
- mqtt_bridge 의 `weld/*` 중계는 **의석(D20)**. scan_manager 의 배타 거절(601)은 병후(P5).
- 오늘 실기 측정은 **정 학민 · 부 병후(D21)**. 급하고 자세히 다뤄야 하므로 **별도 PR**(`p2-measure-0923`, `measurements-20260923.md` + `docs/env/weld_pose_check.py`)로 진행한다.

## 유지하는 규칙 (안전 · 품질)
1. 실기 로봇 명령은 사람이 직접(CLAUDE.md 규칙 1). Claude 는 Virtual · sim 만
2. 미측정 · 실패값 0 금지(규칙 4)
3. 수치는 파라미터(규칙 7). 출발값은 `weld-motion.md` 6절
4. 계약이 코드보다 우선. 타입 파일 · 문서 · CHANGELOG 를 한 PR 에서 같이 고친다(`test_contract_sync`)
5. 브랜치 `p2-<주제>`, PR 본문에 `phase 2` 표시. 15 파일 초과 시 쪼갠다(최초 계약 PR #184 는 예외, D26)
6. 자체 노드는 6 개(1차 5 + `weld_manager`). `.claude/rules/ros2-nodes.md` · 1차 계약 1장의 예외

## 담당 · 산출물

| 담당 | 산출물 | 지시서 |
|---|---|---|
| 학민 | **9/23 실기 측정 M1 · M2 · M4 · M6**(정, 부 병후 · 별도 PR #186) → 1차 개선(#167 · #123 · #125 · **#193** 정 학민 · 부 현지) · P1 리뷰 · 9/29 실기 30~35 분(M2 캘리퍼 · 세로선 bottom 계약 z 1 자세 · M4 실기 1 회 · 배치 사진) | (#186 · #193) |
| 현지 | **P1**(9/24 학민 → 현지): robot_manager `/robot/execute_path` 서버, `OP_WELD_PATH` 발행, `requester='weld_manager'` 허용(PR #191) → `weld_manager` 패키지(순수 경로 생성 모듈 + 상태기계 노드 + sim/Virtual 시험) · M3 · M5 | `tasks/P1-robot-manager.md` · `tasks/P2-weld-manager.md` |
| 의석 | 웹: 용접 화면 · 비드 궤적 · 명령 버튼, FastAPI `weld/#` **+ mqtt_bridge `weld/*` 중계** | `tasks/P3-web.md` · `tasks/P4-bridge.md` |
| 병후 | 계약(이 디렉터리) · scan_manager 601 · 측정 보조 · 발표 | `tasks/P5-scan-guard.md` |

## 머지 순서 (연휴 중)
0. **브리지 operation/reason 표 PR**(의석, 작은 PR): `ROBOT_OPERATION_NAMES[5]=WELD_PATH` · 표에 없는 코드는 `UNKNOWN_<n>` · 1차 `mqtt-schema.md` 1장에 그 규칙 한 줄. **P1 보다 먼저** — 없으면 P1 이 `operation=5` 를 싣는 순간 main 의 mqtt_bridge 가 `robot/sample` 을 통째로 버린다
1. P1 robot_manager → P2 weld_manager(가짜 서버로 먼저 가능) → P4 브리지 · P3 웹(목업 발행기로 먼저 가능) → P5

## 통합 순서 (9/29, D27)
1. 실기 스캔 1회(큐브를 옮겼으면 필수) → `result.json`
2. Virtual 로 용접 종단(웹 버튼 → mqtt → weld_manager → robot_manager 에뮬레이터) 통과 확인
3. 실기 **1단계(반드시 성공)**: 윗면 4 선. `tilt_deg=0 · weave 0 · 속도 낮게` 로 **L0 만**(`start_line=0 · end_line=0`. tilt 0 은 세로선에 못 쓴다) → 45° 로 L0 → L0~L3(`end_line=3`)
4. 실기 **2단계(조건부)**: 세로선 L4~L7(M1 도달성 · M2 외형 검사 통과한 선만) → 위빙 켬
5. 시연 리허설
