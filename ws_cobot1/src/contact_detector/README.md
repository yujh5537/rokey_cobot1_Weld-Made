# contact_detector

접촉(CONTACT) · 접촉 소실(EDGE) · 과대 외력(OVER_FORCE) 판정. 소유: 현지 (T07, T16). 계약: `docs/contracts/ros-interfaces.md` 3.3 · 4.2.

| 파일 | 역할 |
|---|---|
| `contact_detector/detector_core.py` | 판정 로직. **rclpy 를 import 하지 않는다.** tare(기준값 F0), 임계 · 디바운스, 과대 외력 |
| `contact_detector/sim_source.py` | sim 입력원. 가상 직육면체와 TCP 위치로 외력 · z 를 만든다. **rclpy 를 import 하지 않는다** |
| `contact_detector/offline.py` | 기록한 CSV 를 같은 판정 로직에 통과시키는 분석기 (`analyze_samples`). 실측 주기, 무접촉 잡음, 임계 × 디바운스 비교표 |
| `contact_detector/contact_detector.py` | 노드. `/robot/sample`(SENSOR) 구독 → 판정 → `/contact/event`(EVENT) 발행, `/contact/tare` 서비스, `/scan/state` 로 `scan_id` 태깅. 로봇을 움직이지 않는다 |

외력 감소(보조 신호)는 쓰지 않는다(이슈 #16 코멘트에 근거).

## sim 입력원 (`source: sim`)
Virtual Mode 에서는 힘 제어가 동작하지 않고 외력도 0 근처라(BRD 위험 2, `api-check-log.md`), 실제 샘플만으로는
접촉도 소실도 일어나지 않는다. 그래서 **샘플의 외력과 z 를 가상 모델의 값으로 바꿔서** 판정기에 넣는다.
**x · y 는 실제 로봇 값을 그대로 쓴다** — 치수는 Virtual 로봇이 실제로 이동한 거리에서 나온다. 이벤트에도 바꾼 값을 싣는다.

| 팁이 박스 경계를 지난 거리 d | 팁이 닿을 수 있는 높이 |
|---|---|
| d ≤ 0 (윗면 위) | `z_top` |
| 0 < d < r (모서리에 얹힘) | `z_top − (r − √(r² − d²))` — geometry_estimator 보정식의 **정방향** |
| d ≥ r (완전히 벗어남) | 박스 밑면(지지면). 팁이 옆면을 따라 내려간다 |

- `OP_SLIDE` 중에는 순응 제어가 팁을 표면에 붙여 둔다고 본다. 목표 침투(`sim_slide_press_n` / 강성)를 유지하되
  **내려가는 속도를 `sim_fall_speed_mps` 로 제한한다.** 그 밖에서는 팁이 로봇이 지시한 z 에 그대로 있다
- 외력 = 침투 깊이 × `sim_stiffness_n_per_m`, Base 기준 +z
- 샘플의 `frame_id` 가 `sim_box_frame_id` 와 다르면 판정하지 않고 경고한다
- **`sim_tip_radius_m` 은 scan_manager 의 `tip_radius_m` 과 같아야 치수가 복원된다**
- 합격 기준: `test_sim_source.py::test_full_scan_recovers_the_virtual_box` 가 sim → 판정 → 편향 보정이
  가상 박스 치수(100 × 60 × 40 mm)를 0.4 mm 안에서 복원하는지 본다

## 판정 규칙
- **CONTACT**: `operation == OP_DESCEND` 이고 tare 가 끝난 상태에서 `|F − F0| > contact_threshold_n` 인 샘플이 연속 `debounce_n` 회. `motion_id` 마다 1 회
- **EDGE**: `operation == OP_SLIDE` 이고 tare 가 끝난 상태에서
  1. `|F − F0| > edge_arm_force_n` 이 연속 `debounce_n` 회 → "누르고 있다" 확인. 그 뒤부터 판정한다
  2. TCP z 가 **최근 `edge_trend_window_s` 구간의 추세선**(직선 맞춤)보다 `edge_drop_m` 넘게 내려간 샘플이 연속 `debounce_n` 회 → 확정. `motion_id` 마다 1 회
  - 밀기 시작 z 대비 누적 하강량으로 재지 않는다. 모서리가 아닌데 z 가 내려가는 경우가 셋 있다: SLIDE 시작 때 틈(`recontact_margin_m`)을 메우는 하강(계약 7.3), 기울어진 윗면(0.87° 면 80 mm 에 1.2 mm), 탐침이 홀더 안으로 서서히 밀리는 것(PR #80). 앞의 것은 1 이, 뒤의 둘은 2 가 거른다
  - **가를 수 없는 것**: 탐침이 한 번에 툭 미끄러져 들어가면 모서리와 같은 모양이다(테스트에 한계로 고정해 두었다). 기구 쪽에서 막아야 한다
  - 추세선에는 최근 `debounce_n` 개 샘플을 넣지 않고 기다리게 한다(임계 직전의 내려앉는 샘플이 기준선을 끌어내리지 않게). 조건이 성립한 동안에는 기준선을 얼린다
  - `z_drop_m` = 판정 샘플에서 추세선보다 내려간 양(편향 보정의 δ)
  - 누름 확인 직후 곧바로 모서리가 오면 늦게 잡히고 `z_drop_m` 이 작게 실린다. 밀기는 모서리에서 충분히 떨어져 시작한다
- **OVER_FORCE**: 모든 동작에서 원시 `|F| > over_force_n` 이 연속 `over_force_debounce_n` 회. tare 와 무관. 구간마다 1 회
- `|F − F0|` 는 성분별로 뺀 뒤의 크기다(크기끼리 빼지 않는다)
- **판정 샘플 = 조건이 처음 성립한 샘플**(연속 구간의 첫 샘플). ContactEvent 의 `pose` · `pose_stamp` · `wrench` · `force_stamp` · `sample_id` 에 싣는다
  - `detect_stamp` 는 연속 N 번째(확정) 샘플의 시각이다. `detect_stamp − force_stamp` 가 디바운스 지연이다
  - `force_delta_n` 은 확정 샘플의 값이다(검출 하중. BRD 9장 "접촉으로 확정된 순간의 외력")
  - 확정 샘플의 좌표를 쓰면 디바운스 동안 더 움직인 만큼 측정값이 밀린다(50 Hz · 5 mm/s · N=3 이면 0.2 mm)
  - **계약 3.3 의 "판정 샘플" 정의가 확정될 때까지 초안이다**
- `motion_id` 가 0(없음)으로 오는 동안에는 외력이 임계 아래로 내려오면 다시 판정한다. 0 이 아닌 `motion_id` 에서는 외력이 출렁여도 1 회만 낸다
- 무효 샘플(`valid=false`)은 세지도 않고 연속 구간을 끊지도 않는다
- tare: 기준값 F0 = 성분별 평균. 불안정 판정은 `|F − F0|` 의 RMS 로 한다. 외력 크기의 표준편차(`std_norm_n`)는 방향만 바뀌는 흔들림을 놓치므로 보고용으로만 쓴다

## 파라미터
값은 `contact_scan_bringup/config/sim.yaml` · `real.yaml` 에만 둔다. 코드에 기본값이 없어서 값이 빠지면 노드가 기동하지 않는다.
`source` · `contact_threshold_n` · `edge_drop_m` · `debounce_n` · `over_force_n` (계약 이름. SetConfig 가 실행 중에 바꾸며, 범위를 벗어나면 거절한다. 기준값 F0 는 유지된다) ·
`over_force_debounce_n` · `edge_arm_force_n` · `edge_trend_window_s` · `edge_trend_min_samples` · `stale_age_ms` · `tare_duration_s` · `tare_min_samples` · `tare_max_std_n` · `tare_max_force_n`

`source: sim` 일 때만: `sim_box_frame_id` · `sim_box_origin_m`(밑면 중심) · `sim_box_size_m` · `sim_stiffness_n_per_m` · `sim_tip_radius_m` · `sim_fall_speed_mps` · `sim_slide_press_n`

## 샘플 최신성 · 경고
- `now − max(pose_stamp, force_stamp) > stale_age_ms` 인 샘플은 버린다(계약 3.1). 샘플 간격이 `stale_age_ms` 를 넘으면 경고한다(판정은 바꾸지 않는다). 샘플이 비는 동안에는 접촉도 하강도 볼 수 없다
- **샘플이 `stale_age_ms` 넘게 끊기면 EDGE 추세선과 대기 버퍼를 버리고 다시 쌓는다**(경고). 공백을 사이에 둔 두 점을
  같은 추세에 넣으면 그사이 하강이 '정상 추세'로 흡수되어 늦은 좌표로 EDGE 를 확정하거나 아예 놓친다
  (Virtual 실측 342 ms 공백, 2026-09-20). 판정이 몇 샘플 늦어지는 대신 틀린 좌표를 내지 않는다
- DESCEND · SLIDE 인데 `motion_id` 가 0 이면 경고한다(robot_manager 는 그 이벤트로 정지하지 않는다). SLIDE 인데 tare 전이면 경고한다
- `ros2 topic echo /robot/sample` 은 `--qos-reliability best_effort` 가 필요하다

## tare (`/contact/tare`)
구간(`duration_s`, 0 이면 `tare_duration_s`) 동안의 유효 샘플로 F0 를 구한다. 실패하면 기준값을 바꾸지 않는다.
`NO_SAMPLE`(샘플 없음) · `TARE_TIMEOUT`(`tare_min_samples` 미달) · `TARE_UNSTABLE`(`|F − F0|` RMS > `tare_max_std_n`) · `TOOL_REG_SUSPECT`(`|F0|` > `tare_max_force_n`, BRD 4.1.5) · `BUSY`(진행 중).
응답의 `offset.torque` 는 쓰지 않으므로 NaN 이다. 서비스는 구간이 끝날 때까지 코루틴으로 기다리며 그동안 샘플 콜백은 계속 돈다

## 실행
```bash
cd ~/ws_cobot_pjt/ws_cobot1 && source install/setup.bash
ros2 launch contact_scan_bringup bringup.launch.py source:=sim
python3 -m pytest src/contact_detector/test -q          # ROS 를 source 하지 않아도 판정 · 분석기 테스트는 돈다
```

## 오프라인 분석 (T08 · T24)
```bash
ros2 run contact_detector analyze_samples idle_01.csv descend_01.csv \
    --tare-seconds 1.5 --thresholds 2 3 4 5 --debounce 1 3 5 --over-force 30
```
CSV 머리줄: `t_pose_s,t_force_s,x_mm,y_mm,z_mm,fx_n,fy_n,fz_n,valid`
- `t_*_s` 는 각 조회의 응답을 받은 시각, 위치는 Base 기준 TCP(`*_mm` 또는 `*_m`), 힘은 `get_tool_force(ref=DR_BASE)`
- 조회에 실패한 줄은 0 으로 채우지 말고 `valid=0` 으로 남긴다
- 파일 앞 `--tare-seconds` 동안은 무접촉 · 정지 상태여야 한다
- 무접촉 기록을 넣으면 "CONTACT 확정 수" 열이 그 임계 · 디바운스 조합의 거짓 접촉 횟수다
