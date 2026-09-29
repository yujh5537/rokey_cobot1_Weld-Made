# 2026-09-29 실기 세션 계획 — 9/23(M1~M6) 후속 40 분

**로봇 명령: 현지. 입회 · 비상정지: 학민.**(9/29 실제. 병후 부재 #207) 오전 맨 앞. 9/23 이후 첫 실기다.

> **결과(2026-09-29)**: `docs/test-reports/realrobot-session_20260929.md`. 기준점 −0.016 mm 통과 · D34 L6 접근점 NOT REACHABLE → `vertical` · z_safe 32.5 mm · L6 · L7 roll 180(#210) · 세로선 bottom 간극 15 · 25 mm · M2 13/12/12 mm · M4 점당 0.50~0.58 s. 실기 스캔은 3 회 NEG_Y 실패, 용접은 9/23 결과로 6 선 DONE.
9/23 결과는 `measurements-20260923.md` · `docs/test-reports/m1-measurements_20260923.md`.

## 목적 — 시연 가능 여부를 정하는 값 셋

| | 지금 모르는 것 | 모르면 어떻게 되나 |
|---|---|---|
| D34 | phase 2 접근 · 후퇴점이 도달하는가 (플랜지 713~733 mm, M1 의 712 도달 · 738 실패 사이) | 9/29 시연 선 수가 6 인지 4 인지 모른다 |
| M2 | 닫힌 핑거의 **반폭 R** | 세로선 bottom 에서 핑거가 작업대에 닿는지 계산할 수 없다(여유 17.6 mm 뿐) |
| M4 | line 모드의 **점당 정지 시간**(실기) | `path_point_dwell_s` real 값이 추정치로 남는다 |

## 안전 (예외 없음)

- **툴 · TCP 등록 확인 전에는 어떤 이동 명령도 보내지 않는다.** 9/23 에 등록 누락으로 비상정지 2 회.
- 자세 사이 이동은 전부 안전 높이(z_safe 이상)를 거친다. 9/23 충돌이 "목표 위 30 mm" 에서 났다.
- 두산 서비스를 **동시에 부르지 않는다**. `measure_idle_force.py` · `probe_point.py` · `weld_pose_check.py` 를 겹쳐 돌리면
  `dsr_controller2` 가 응답을 멈추고 **브링업 재시작 말고는 복구가 없다**(`api-check-log.md` §43). `ros2 topic echo` 는 괜찮다.
- 실기 브링업이 떠 있는 동안 에뮬레이터를 띄우지 않는다.
- 이상하면 먼저 **비상정지**. 그 다음 "3~5 절 재점검"(`units-frames.md` 탐침 상태 전제조건).

## 9/28 사전 확인 (Virtual, 학민)

내일 아침에 처음 띄우다 막히는 것을 없애려고 전날 한 번 올려 봤다. 격리(`ROS_DOMAIN_ID=99` ·
`ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST`)에서 에뮬레이터 + 드라이버 + `bringup source:=sim` 까지.

| | 결과 |
|---|---|
| 작업공간 | main(`004f862`, #161 · #199 · #200 포함)으로 갱신 후 `colcon build` **7 패키지 성공** |
| 드라이버 | `dsr_controller2` 활성화 성공. 기동 중 `Overrun` 경고(900 ms)는 컨트롤러 전환 1 회뿐 |
| 여섯 노드 | `robot_manager` · `contact_detector` · `safety_monitor` · `scan_manager` · `mqtt_bridge` 전부 기동, 오류 0 |
| `/robot/status` | #161 의 새 필드 확인 — `slide_mode: force`(sim) · `slide_force_setpoint_n: 3.0` · 나머지 **NaN** |
| `safety_monitor` | `drop_limit_m=0.005 drop_limit_margin_m=0.005`(2차 10 mm) 로그 확인 |
| `/robot/sample` | 발행 확인. 다만 에뮬레이터 초기 자세는 **관절 전부 0(특이점)** 이라 팁이 z 1.035 m 다 |

⚠️ **`ros2 topic echo` 에 `--no-daemon` 을 붙이면** `/robot/sample` 이 "does not appear to be published yet ·
Could not determine the type" 로 실패한다(BEST_EFFORT 토픽). **`--no-daemon` 없이** 쓴다. 0 절의 명령은 그대로 쓰면 된다.

⚠️ 기동 직후 `scan_manager` 가 "다른 노드의 값을 읽지 못했다(safety_monitor.over_force_n · drop_limit_m)" 를 한 번 경고한다.
파라미터 되읽기 시점 문제이고 `ScanConfig` 의 그 칸이 NaN 으로 남는다는 뜻이다. 기동 순서 문제라 실기에서도 볼 수 있다 — **정상으로 본다.**

## 0. 세션 시작 점검 (3 분) — 이게 실패하면 아래 전부 무효다

```bash
# 터미널 A — 브링업. 로그에 'mode : real' 확인
sodreal

# 터미널 B — 툴 · TCP 등록 (이것 먼저. 빠지면 팁이 아니라 플랜지 좌표로 움직인다)
cd ~/ws_cobot_pjt
python3 docs/env/apply_tool_tcp.py --tcp-x 0 --tcp-y 0     # 마지막 줄 OK: ... [0.0, 0.0, 252.12]
ros2 topic echo --once --field pose.position /robot/sample  # 홈에서 z ≈ 0.294 (0.546 이면 등록 빠짐)
ros2 topic echo --once --field wrench.force /robot/sample   # |F| 1~2 N (약 12 N 이면 등록 빠짐)

# 터미널 C — 판정 좌표를 받을 준비. **하강 전에 먼저 걸어 둔다**
ros2 topic echo /contact/event --field pose.position
```

**기준점 접촉 점검** — 작업대 기준점 (524.97, −172.03) mm, 기준값 **95.006 mm**, 허용 **± 0.3 mm**
(`units-frames.md` 탐침 상태 전제조건 3 · 4. 판정 좌표를 쓰고 정지 좌표는 쓰지 않는다).

```bash
# ① 기준점 위 20 mm 로. 자세는 홈(탐침 수직) 그대로
ros2 action send_goal /robot/execute_motion contact_scan_interfaces/action/ExecuteMotion \
  "{scan_id: refchk, motion_id: 901, operation: 1, frame_id: base_link,
    target: {position: {x: 0.52497, y: -0.17203, z: 0.115},
             orientation: {x: 0.0515581, y: 0.99866999, z: 0.0, w: 0.0}},
    speed: 0.020, timeout: {sec: 60}}"

# ② 힘 접촉 하강. 2 mm/s · 임계 3.0 N (기준값을 잰 조건과 같게 맞춘다)
ros2 action send_goal /robot/execute_motion contact_scan_interfaces/action/ExecuteMotion \
  "{scan_id: refchk, motion_id: 902, operation: 2, speed: 0.002, max_distance: 0.030,
    timeout: {sec: 60}}"

# ③ 터미널 C 의 pose.position.z × 1000 을 95.006 과 비교. |차| ≤ 0.3 mm 면 통과
# ④ 통과하면 위로 뺀다 (①을 다시 보낸다. motion_id 만 903 으로)
```

- 20 mm 위에서 출발하는 이유: `descend_ref_settle_s` 5.5 s × 2 mm/s ≈ 11 mm 를 지나야 둔한 판정 구간(6 N)을 벗어난다(#127 · #182).
- **밖이면**: 탐침을 홀더 끝까지 다시 끼우고 ② 를 다시 한다. 그래도 밖이면 교체 절차(`units-frames.md`)로 가고,
  **아래 1~5 는 하지 않는다** — TCP z 가 어긋난 상태의 측정값은 쓸 수 없다.

## 1. D34 — 접근 · 후퇴점 도달성 (4 분, 접촉 없음)

```bash
python3 docs/env/weld_pose_check.py --approach --only L0,L6 --dry-run \
  --cube 377.87 460.88 -199.05 -118.41 177.77 97.01          # 먼저 좌표 · 플랜지 거리 확인
python3 docs/env/weld_pose_check.py --approach --only L0,L6 --real-ok --vel 10 \
  --cube 377.87 460.88 -199.05 -118.41 177.77 97.01 --file docs/test-reports/data/20260929_weld/d34.csv
```

**확인할 점 4 개**(전부 M1 의 빈 구간 712~738 안):

| 점 | posx [mm, deg] | 플랜지 |
|---|---|---|
| L0 ret_safe | `[460.88, -222.38, 227.77, 90, 135, -180]` | 733.4 |
| L0 ret | `[460.88, -222.38, 201.10, 90, 135, -180]` | 718.9 |
| L6 app_safe | `[477.38, -101.91, 227.77, -135, 135, -90]` | 727.7 |
| L6 app | `[477.38, -101.91, 201.10, -135, 135, -90]` | 713.2 |

같이 지나는 L0 app(668.8) · L6 ret(675.9)는 M1 검증 안이라 `s` 로 넘겨도 된다.
**합격선**: 실측 posx 가 지령과 **1 mm 안**(`ARRIVE_TOL_MM`). 두산 `success=true` 는 도달의 증거가 아니다.

- 4 개 다 도달 → **9/29 시연 6 선**(L0 · L2 · L3 · L4 · L6 · L7) 그대로.
- 하나라도 실패 → `weld_manager` 의 `top_line_offset_dir: vertical` 로 바꾼다(윗면선 오프셋을 수직 위로. 그 점이
  M1 이 실제로 도달한 712.1 이다). 코드 변경 없이 yaml 한 줄(#196 · #197, 현지).

## 2. 세로선 bottom 을 계약 z 로 + 세로 간극 캘리퍼 (12 분)

9/23 은 `--bottom-margin 20`(z 121.25)으로 돌아 **가장 빠듯한 자세를 확인하지 않았다.** 계약은 z **104.13** 이다.

```bash
python3 docs/env/weld_pose_check.py --only L4,L7 --standoff 3 --bottom-margin 5 --real-ok --vel 10 \
  --cube 377.87 460.88 -199.05 -118.41 177.77 97.01 --file docs/test-reports/data/20260929_weld/bottom.csv
```

- 4 자세(L4 · L7 의 top · bottom). 플랜지는 377~499 mm 로 도달 여유가 크다 — **여기서 볼 것은 도달이 아니라 간극이다.**
- 간극은 **캘리퍼로** 잰다(줄자 아님). 9/23 의 세로 간극 0.4~1.1 mm 는 측정 방식 문제로 미확정 처리했고, 이것이 그 재측정이다.
- 각 자세에서 **핑거 · 홀더 ↔ 작업대** 최소 거리도 같이 적는다. 설계 예상은 **17.6 mm**(핑거 끝 축 위, 맨 작업대 기준).

## 3. M2 — 툴 치수 (8 분, 2 절의 L4 bottom 자세를 그대로 두고)

로봇을 세운 채 캘리퍼로 잰다. 표는 `measurements-20260923.md` M2 절.

| 항목 | 합격선 · 비고 |
|---|---|
| 닫힌 핑거 **반폭 R** (축 → 핑거 바깥) | **R < 22 mm**(테이프 지지면 기준) · 24.9(맨 작업대 기준). `tool_profile_r_m` 출발값 |
| 홀더 최대 지름과 그 자리의 u(팁에서 뒤 거리) | `tool_profile_u_m` · `tool_profile_r_m` 한 쌍 |
| 노출 길이 = 간섭 거리 **D** | **재확인만**. 12 mm 에서 벗어나면 2 차 하강 제한 10 mm 의 근거가 흔들린다 |
| 사진 3 컷 | 전체 배치 · 탐침 · 홀더 · RG2 근접 · 45° 자세 옆 · 위 → `docs/presentation/assets/hakmin/` |

45° 에서 툴 위 한 점의 높이는 `팁 z + (u − R)·cos45°` 다. 계약 z 104.13 · 맨 작업대 95.006 에서 닿지 않을 조건이 `R < u + 12.9`.

## 4. M4 — line 모드 점당 정지 시간 (6 분)

큐브 위 **100 mm 공중**, 지그재그 11~21 점(진행 4 mm · 좌우 ±2 mm), 10 mm/s, 자세는 수직(홈) 그대로.
`ExecutePath`(#191)가 머지돼 있으면 그 액션으로, 아니면 `move_line` 반복으로 시간만 잰다.

**얻을 값**: (전체 시간 − 순수 이동 시간) ÷ 점 수 = **점당 정지 시간**.
Virtual 은 0.5 s 였다(21 점 7.5 → 18.2 s). `path_point_dwell_s` real 출발값 2.0 이 맞는지 본다.
경로 한도 = `motion_timeout_s` + 점 수 × `path_point_dwell_s` 라 이 값이 100 점 선의 여유를 정한다.

## 5. 기록 · 되돌림 (5 분)

- CSV 두 개(`d34.csv` · `bottom.csv`)와 사진을 `docs/test-reports/data/20260929_weld/` 에 넣는다.
- 홈 복귀 후 브링업 종료. `Ctrl+C` 로 노드를 끄지 않는다(정지 · 해제 없이 죽는다).
- 결과를 이 문서 아래에 이어 적고, D34 판정은 `top_line_offset_dir` 값으로 옮긴다.

## 이번에 **하지 않는** 것

- **O1 · O2**(1 차 · 2 차 하강 제한이 걸린 뒤 더 내려가는 거리, 계약 7.2 의 남은 조건 `5 + O1 < L2` · `L2 + O2 < D`).
  일부러 `DROP_LIMIT` 을 걸어야 하고 세팅까지 8 분 이상이라 40 분에 들어가지 않는다. 다음 실기로 넘긴다.
- L1 · L5(플랜지 772~804 mm, 도달 불가 확정). 접근점도 802 · 804 라 시도하지 않는다.
- 기준 큐브 재배치 · 회전 테이블(9/25 팀 결정으로 하지 않는다).
