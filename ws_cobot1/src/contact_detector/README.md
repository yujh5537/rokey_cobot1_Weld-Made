# contact_detector

접촉(CONTACT) · 과대 외력(OVER_FORCE) 판정. 소유: 현지 (T07, T16). 계약: `docs/contracts/ros-interfaces.md` 3.3 · 4.2.

| 파일 | 역할 |
|---|---|
| `contact_detector/detector_core.py` | 판정 로직. **rclpy 를 import 하지 않는다.** tare(기준값 F0), 임계 · 디바운스, 과대 외력 |
| `contact_detector/contact_detector.py` | 노드. 지금은 골격(파라미터 검증 · 판정기 생성). 구독 · 발행 · tare 서비스는 아직 없다 |

아직 없는 것: `/robot/sample` 구독, `/contact/event` 발행, `/contact/tare` 서비스, 접촉 소실(EDGE) 판정, sim 입력원.

## 판정 규칙
- **CONTACT**: `operation == OP_DESCEND` 이고 tare 가 끝난 상태에서 `|F − F0| > contact_threshold_n` 인 샘플이 연속 `debounce_n` 회. `motion_id` 마다 1 회
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
`source` · `contact_threshold_n` · `edge_drop_m` · `debounce_n` · `over_force_n` (계약 이름) · `over_force_debounce_n`

## 실행
```bash
cd ~/ws_cobot_pjt/ws_cobot1 && source install/setup.bash
ros2 launch contact_scan_bringup bringup.launch.py source:=sim
python3 -m pytest src/contact_detector/test -q          # ROS 를 source 하지 않아도 판정 · 분석기 테스트는 돈다
```
