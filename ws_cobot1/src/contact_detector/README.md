# contact_detector

접촉(CONTACT) · 과대 외력(OVER_FORCE) 판정. 소유: 현지 (T07, T16). 계약: `docs/contracts/ros-interfaces.md` 3.3 · 4.2.

| 파일 | 역할 |
|---|---|
| `contact_detector/detector_core.py` | 판정 로직. **rclpy 를 import 하지 않는다.** tare(기준값 F0), 임계 · 디바운스, 과대 외력 |
| `contact_detector/offline.py` | 기록한 CSV 를 같은 판정 로직에 통과시키는 분석기 (`analyze_samples`). 실측 주기, 무접촉 잡음, 임계 × 디바운스 비교표 |
| `contact_detector/contact_detector.py` | 노드. 지금은 골격(파라미터 검증 · 판정기 생성). 구독 · 발행 · tare 서비스는 아직 없다 |

아직 없는 것: `/robot/sample` 구독, `/contact/event` 발행, `/contact/tare` 서비스, 접촉 소실(EDGE) 판정, sim 입력원.

## 판정 규칙
- **CONTACT**: `operation == OP_DESCEND` 이고 tare 가 끝난 상태에서 `|F − F0| > contact_threshold_n` 인 샘플이 연속 `debounce_n` 회. `motion_id` 마다 1 회
- **OVER_FORCE**: 모든 동작에서 원시 `|F| > over_force_n` 이 연속 `over_force_debounce_n` 회. tare 와 무관. 구간마다 1 회
- `|F − F0|` 는 성분별로 뺀 뒤의 크기다(크기끼리 빼지 않는다)
- 판정 샘플 = 연속 N 번째 샘플. 연속 구간의 첫 샘플도 같이 보관해 디바운스 지연과 z 편향을 잰다
- 무효 샘플(`valid=false`)은 세지도 않고 연속 구간을 끊지도 않는다
- tare: 기준값 F0 = 성분별 평균. 불안정 판정은 `|F − F0|` 의 RMS 로 한다. 외력 크기의 표준편차(`std_norm_n`)는 방향만 바뀌는 흔들림을 놓치므로 보고용으로만 쓴다

## 파라미터
값은 `contact_scan_bringup/config/sim.yaml` · `real.yaml` 에만 둔다. 코드에 기본값이 없어서 값이 빠지면 노드가 기동하지 않는다.
`source` · `contact_threshold_n` · `edge_drop_m` · `debounce_n` · `over_force_n` (계약 이름) · `over_force_debounce_n`

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
