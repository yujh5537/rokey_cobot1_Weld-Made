# P2 weld_manager: 용접 순서 · 경로 생성 노드

**세션 이름: P2 weld_manager 노드**
담당: 현지 · 권장 기한: 9/28 (sim + Virtual 통과) · 공통 절차: `_common.md`

## 이 task
스캔 결과 파일에서 8 개 모서리를 읽어, 기울인 자세 · 스탠드오프 · 위빙 경유점을 만들고, robot_manager 에 접근 → 경로 → 후퇴 → 다음 선 순서로 명령을 보내며 상태를 `/weld/state` 로 알리는 새 패키지 `weld_manager` 를 만든다. scan_manager 의 "순수 계산은 rclpy 없이, 노드는 얇게" 구조를 참고한다(복제 강제 없음, D16).

## 계약 (확정)
- `docs/phase2/weld-motion.md` 전체(8 선 표 · 자세 식 · 스탠드오프 · 위빙 · 접근/후퇴 · 파라미터 표).
- `docs/phase2/weld-ros-interfaces.md`: 2장 연결 표, 3.1~3.4, 4.1, 5.1(시작 거절 표), 7장(배타 · 중지 · 완료 순서).
- 입력: `scan_manager.result_store.ResultStore.load_result(scan_id)`(순수 Python, import 허용) — `shape.edges[12]` · `node_params.base_to_fixture` · `support_z`. `""` 면 `scan_ids()` 최신순에서 `success=true` 첫 것.
- 출력 파일: `<result_dir>/<scan_id>/weld/<weld_id>.json`(형식은 자유, 값 규칙은 1차와 같음).

## 초기 설계 (출발점)
```
weld_manager/
  weld_manager/
    contract_enums.py   Phase · LineStatus · Reason (msg 상수 사본. test 로 msg 와 대조)
    params.py           파라미터 이름 · 범위 검사 (scan_manager/params.py 참고). 예비값 없음
    weld_path.py        [순수] 8 선 추출 · 자세(quaternion) · 스탠드오프 · 지그재그 경유점 · 접근/후퇴/z_safe · 작업영역 검사
                        입력: edges(작업대 m) · base_to_fixture · support_z · WeldParams → 출력: 선별 MotionPlan (Base 좌표)
    state_machine.py    [순수] Phase 전이표 (scan_manager 것을 줄여서. RESUME 없음)
    sequence.py         [순수] Ports 뒤에 바깥일을 두고 순서만: for line: approach1 → approach2 → path → retreat → … → home
    weld_manager.py     노드: RunWeld · ReturnHome 서버, StopWeld 서비스, 구독 3 (scan/state · robot/status · safety/status),
                        클라이언트 (execute_motion · execute_path · robot/stop), /weld/state · /weld/result · /weld/log 발행
  test/
    test_weld_path.py   식 검산: tilt 0 → 툴 z = (0,0,−1); L0 의 d = (0, .707, −.707); 위빙 점 수 · 시작/끝은 이음선 위; 세로선 끝 z = support + margin;
                        fixtures/sim_….result.json 으로 8 선 생성 · 작업영역 통과
    test_state_machine.py
    test_node_weld.py   가짜 robot_manager(scan_manager/test/fake_peers.py 참고) 로 8 선 종단 · 거절 사유 표 · 중지 · 배타(scan/state 활성)
```
- 자세 계산은 `docs/phase2/measurements-20260923.md` M1 표의 숫자와 `docs/env/weld_pose_check.py --dry-run`(PR #186) 과 같아야 한다 — 테스트로 고정. **단 스탠드오프는 D22 정의**(구 표면 ↔ 이음선, 세로선 축 방향 ≈ 5.07 mm)라 세로선 좌표는 M1 표(축 방향 3 mm)와 다르다. 그 차이도 테스트로 적는다.
- 현지 리뷰(#184)로 계약에 들어간 것: 스탠드오프 정의(D22) · 세로선 툴 외형 검사 `tool_profile_u_m` · `tool_profile_r_m`(D23 · D28) · `RunWeld.end_line`(D28) · `tool_roll_deg[8]`(D24) · 미요청 정지 = ERROR(D25) · `/robot/sample` 구독(시작 시 위치 · 툴 등록) · `weld_speed_min_mps` · 안전복귀 전 −d 물러남.
- ExecuteMotion goal 은 1차 `scan_manager/conversions.py` 의 `MotionRequest → goal` 을 참고(자세 quaternion 그대로, `frame_id=motion_frame_id`).
- `/weld/state` 발행 · 파일 쓰기는 scan_manager 처럼 쓰기 스레드 1 개 (`result_store/README.md` 마지막 절).
- `contact_scan_bringup`: `bringup.launch.py` 에 weld_manager 추가(노드 6 개), `sim.yaml` · `real.yaml` 에 `weld_manager:` 절(출발값은 `weld-motion.md` 6절, **주석에 근거**).

## 테스트 · 시뮬레이션
- 순수 pytest(ROS 없이): `python3 -m pytest src/weld_manager/test -q`.
- 노드 + 가짜 robot_manager: 8 선 완료 · 중지 · 시작 거절 9 종.
- **Virtual 종단**(P1 이 머지된 뒤, 또는 P1 브랜치 위에서): `source:=sim` bringup + 에뮬레이터, fixtures 의 sim result.json 을 `~/scan_results/sim/<scan_id>/` 에 두고(PR #188 경로) `ros2 action send_goal /weld/run`. `/weld/state` 가 IDLE→…→DONE, `/weld/result.success=true`. 도메인 31~39.
- P1 이 늦으면 가짜 `/robot/execute_path` 서버(fake_peers) 로 먼저 간다.

## 남기는 것
- 9/29 실기: fixtures 대신 그날 스캔 result.json, `tilt_deg` · `standoff_m` 은 M1 결과로 조정.
