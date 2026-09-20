# contact_detector

접촉(CONTACT) · 접촉 소실(EDGE) · 과대 외력(OVER_FORCE) 판정. 소유: 현지 (T07, T16). 계약: `docs/contracts/ros-interfaces.md` 3.3 · 4.2.

| 파일 | 역할 |
|---|---|
| `contact_detector/detector_core.py` | 판정 로직. **rclpy 를 import 하지 않는다.** tare(기준값 F0), 임계 · 디바운스, 과대 외력 |
| `contact_detector/offline.py` | 기록한 CSV 를 같은 판정 로직에 통과시키는 분석기 (`analyze_samples`). 실측 주기, 무접촉 잡음, 임계 × 디바운스 비교표 |
| `contact_detector/contact_detector.py` | 노드. `/robot/sample`(SENSOR) 구독 → 판정 → `/contact/event`(EVENT) 발행, `/contact/tare` 서비스, `/scan/state` 로 `scan_id` 태깅. 로봇을 움직이지 않는다 |

아직 없는 것: sim 입력원(가상 직육면체). 지금은 `source` 가 무엇이든 샘플의 외력 · 위치를 그대로 판정한다. 외력 감소(보조 신호)는 쓰지 않는다.

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

## 샘플 최신성 · 경고
- `now − max(pose_stamp, force_stamp) > stale_age_ms` 인 샘플은 버린다(계약 3.1). 샘플 간격이 `stale_age_ms` 를 넘으면 경고한다(판정은 바꾸지 않는다). 샘플이 비는 동안에는 접촉도 하강도 볼 수 없다
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
