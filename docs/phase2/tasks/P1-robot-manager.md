# P1 robot_manager: 경유점 경로 실행 (`/robot/execute_path`)

**세션 이름: P1 robot_manager 경로 실행**
담당: 학민 · 기한: 9/28 (Virtual 통과), 9/29 실기 · 공통 절차: `_common.md`

## 이 task
weld_manager 가 만든 경유점 목록(지그재그 위빙 포함)을 로봇이 차례로, 정해진 속도로 지나게 하는 액션 서버를 robot_manager 에 더한다. 접촉 판정도 힘 제어도 없는 "직선 이동 여러 개"다. 1차 `ExecuteMotion` 과 같은 자리를 써서 둘이 동시에 돌지 않게 한다.

## 오늘(9/23) 실기 측정 — 이 task 보다 먼저 (정 학민 · 부 병후, 별도 PR `p2-measure-0923`)
`docs/phase2/measurements-20260923.md` **M1(16 자세 도달성, `docs/env/weld_pose_check.py`) · M2 · M4(spline vs line) · M6**. 결과는 그 PR 의 표에 채운다. M1 이 없으면 연휴 중 짠 경로가 9/29 에 관절 한계로 막힐 수 있다. 실기 명령은 사람이 한다. **오늘 로봇 시간이 안 나면**: M1 은 Virtual(에뮬레이터, 관절 한계 · 특이점은 운동학이라 대부분 잡힌다)로 연휴 중 대신하고, 간섭은 M2 치수로 계산하며, 9/29 첫 30 분을 실기 M1 에 쓴다.

## 계약 (확정)
- `docs/phase2/weld-ros-interfaces.md` 5.2 `ExecutePath.action`, 2.1(`RobotSample.operation = OP_WELD_PATH(5)`), 2.2(`/robot/stop` requester `'weld_manager'`).
- goal 거절 · 종료 사유 · 도착 판정 규칙은 5.2 절의 글머리표 그대로.
- 파라미터(robot_manager): `path_max_points`(200) · `path_max_speed_mps`(0.100) · **`path_min_z_m`**(Base z 하한, 출발값 real 0.100 / sim 은 sim 박스 밑면 0.400 + 여유) · `path_acc_ratio`(4.0, 1/s). `real.yaml` · `sim.yaml` 에 주석과 함께. 순응 · 힘 제어 검사는 내부 플래그(안전망).

## 초기 설계 (출발점, 바꿔도 됨)
- `dsr_client.py`: `move_spline_task_request(posx_list, speed_mps)` 추가(`MoveSplineTask`: `pos` 는 `Float64MultiArray[]`, `pos_cnt`, `vel/acc [mm/s, deg/s]`, `ref=DR_BASE`, `mode=ABS`, `opt=CONST(1)` 검토, `sync_type=ASYNC`). M4 에서 spline 이 안 되면 `move_line_request` 를 radius 로 잇는다(`radius` 인자 추가).
- `motions.py`: `path_to_posx_list(waypoints, frame)`(quaternion→ZYZ 는 `pose_to_posx_mm_deg` 재사용), `path_length_m`, `progress_along_path(position, waypoints)` → (waypoint_index, distance) — 순수 함수, pytest.
- `robot_manager.py`: 두 번째 ActionServer `/robot/execute_path`. **`self.motion`(현재 goal 자리)을 공유**해 BUSY 판정. `run_motion` 의 watch 루프를 재사용하되 종료 조건은 "마지막 점 근처 + 정지"만. 이벤트 대조는 OVER_FORCE 만. `RobotSample.operation` 에 5 를 싣는다(`reject_reason` 의 `op > OP_HOME` 은 그대로 — ExecuteMotion 에 5 가 오면 거절).
- `motion_state.py`: `operation` 에 WELD_PATH 추가.
- spline 이 한 호출로 나가면 feedback 의 `waypoint_index` 는 진행 거리로 추정한다(계약 허용).
- 정지: 기존 `/robot/stop` 경로 그대로(`move_stop` → 정지 확인 → `REASON_STOP_REQUESTED`).

## 테스트
- 순수: `test_motions.py` 에 경로 변환 · 진행률.
- 노드: `test/test_node.py` 패턴으로 가짜 dsr 서비스 → goal 수락 · BUSY(ExecuteMotion 실행 중) · 거절 사유 5 종 · 정지 · 도착 허용치.
- **Virtual 종단**: `sodvir` 에뮬레이터 + robot_manager 만 띄우고 `ros2 action send_goal /robot/execute_path` 로 공중 지그재그 21 점(10 mm/s). `/robot/sample.operation == 5` 확인. 도메인 31~39.

## 남기는 것
- `docs/env/api-check-log.md` 에 `move_spline_task` / `move_line radius` 실제 동작(M4).
- 9/29: 실기에서 `tilt 0 · weave 0` 한 선 → 45° → 위빙 순서(README 통합 순서).
