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
| D12 | 담당: 병후 계약 · 문서 · 발표 / 현지 weld_manager / 학민 robot_manager / 의석 웹 |
| D13 | 계약을 먼저(오늘), 그 뒤 병렬 |
| D14 | robot_manager 추가는 담당자 판단으로 단순화 가능(movel 등) |
| D15 | safety_monitor 는 대체로 그대로 |
| D16 | weld_manager 상태기계는 scan_manager 패턴 참고, 복제 강제 없음 |
| D17 | 인터페이스 목록 채택(`weld-ros-interfaces.md`) |
| D18 | 허용오차 ±3 mm |
| D19 | 위빙은 지그재그 경유점(`ExecutePath`). `move_periodic` 은 쓰지 않는다 |
| D20 | mqtt_bridge `weld/*` 는 의석 |
| D21 | 9/23 실기 측정: 정 학민 · 부 병후. 별도 PR |

**계약 작성 중 드러난 것 → 2026-09-23 병후 결정**
- **`move_periodic` 은 직선 이동과 겹쳐 실행되지 않는다**(dsr_msgs2 `MovePeriodic.srv` 는 제자리 주기 운동). 위빙은 **지그재그 경유점**으로 만들고 robot_manager 가 `ExecutePath` 로 지난다 — **채택(D19)**. 실행은 `move_spline_task` 또는 `move_line` 반복 중 실기에서 되는 것으로.
- mqtt_bridge 의 `weld/*` 중계는 **의석(D20)**. scan_manager 의 배타 거절(601)은 병후(P5).
- 오늘 실기 측정은 **정 학민 · 부 병후(D21)**. 급하고 자세히 다뤄야 하므로 **별도 PR**(`p2-measure-0923`, `measurements-20260923.md` + `docs/env/weld_pose_check.py`)로 진행한다.

## 유지하는 규칙 (안전 · 품질)
1. 실기 로봇 명령은 사람이 직접(CLAUDE.md 규칙 1). Claude 는 Virtual · sim 만
2. 미측정 · 실패값 0 금지(규칙 4)
3. 수치는 파라미터(규칙 7). 출발값은 `weld-motion.md` 6절
4. 계약이 코드보다 우선. 타입 파일 · 문서 · CHANGELOG 를 한 PR 에서 같이 고친다(`test_contract_sync`)
5. 브랜치 `p2-<주제>`, PR 본문에 `phase 2` 표시. 15 파일 초과 시 쪼갠다

## 담당 · 산출물

| 담당 | 산출물 | 지시서 |
|---|---|---|
| 학민 | **오늘 실기 측정 M1 · M2 · M4 · M6**(정, 부 병후 · 별도 PR) → robot_manager: `/robot/execute_path` 서버, `OP_WELD_PATH` 발행, `requester='weld_manager'` 허용 | `tasks/P1-robot-manager.md` |
| 현지 | `weld_manager` 패키지(순수 경로 생성 모듈 + 상태기계 노드 + sim/Virtual 시험) · M3 · M5 | `tasks/P2-weld-manager.md` |
| 의석 | 웹: 용접 화면 · 비드 궤적 · 명령 버튼, FastAPI `weld/#` **+ mqtt_bridge `weld/*` 중계** | `tasks/P3-web.md` · `tasks/P4-bridge.md` |
| 병후 | 계약(이 디렉터리) · scan_manager 601 · 측정 보조 · 발표 | `tasks/P5-scan-guard.md` |

## 통합 순서 (9/29)
1. 실기 스캔 1회(큐브를 옮겼으면 필수) → `result.json`
2. Virtual 로 용접 종단(웹 버튼 → mqtt → weld_manager → robot_manager 에뮬레이터) 통과 확인
3. 실기: `tilt_deg=0 · weave 0 · 속도 낮게` 로 L0 한 선 → 45° 로 L0 → 8 선 전체 → 위빙 켬
4. 시연 리허설
