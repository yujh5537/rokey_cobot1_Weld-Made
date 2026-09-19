# ws_cobot1/src 패키지

| 패키지 | 빌드 타입 | 담당 | 이슈 |
|---|---|---|---|
| `contact_scan_interfaces` | ament_cmake (rosidl) | 병후 | T09 |
| `robot_manager` | ament_python | 학민 | T13~T15 |
| `contact_detector` | ament_python | 현지 | T07, T16 |
| `safety_monitor` | ament_python | 현지 | T18, T33 |
| `scan_manager` (+ `geometry_estimator/`, `result_store/`) | ament_python | 병후 (geometry_estimator는 현지) | T10, T17, T19, T20, T26 |
| `mqtt_bridge` | ament_python | 의석 (T27은 병후와 공동) | T21, T27 |
| `contact_scan_bringup` | ament_python (launch, config) | 현지 | T05 |

## 골격 만들기 (Day 1, 각 담당자)
```bash
cd ws_cobot1/src
ros2 pkg create contact_scan_interfaces --build-type ament_cmake --license Apache-2.0
ros2 pkg create robot_manager   --build-type ament_python --node-name robot_manager   --dependencies rclpy contact_scan_interfaces --license Apache-2.0
ros2 pkg create contact_detector --build-type ament_python --node-name contact_detector --dependencies rclpy contact_scan_interfaces --license Apache-2.0
ros2 pkg create safety_monitor  --build-type ament_python --node-name safety_monitor  --dependencies rclpy contact_scan_interfaces --license Apache-2.0
ros2 pkg create scan_manager    --build-type ament_python --node-name scan_manager    --dependencies rclpy contact_scan_interfaces --license Apache-2.0
ros2 pkg create mqtt_bridge     --build-type ament_python --node-name mqtt_bridge     --dependencies rclpy contact_scan_interfaces --license Apache-2.0
ros2 pkg create contact_scan_bringup --build-type ament_python --license Apache-2.0
```
만든 뒤 각 패키지의 `test/test_copyright.py`, `test_flake8.py`, `test_pep257.py`는 지운다.

## 구조 규칙
- DSR_ROBOT2 / dsr_msgs2 / RG2 드라이버 의존은 `robot_manager`에만 둔다. CI에는 두산 드라이버가 없으므로, 다른 패키지가 이것을 import하면 CI가 깨진다.
- `scan_manager/scan_manager/geometry_estimator/`는 rclpy를 import하지 않는다.
- 파라미터는 `contact_scan_bringup/config/`에 입력원별로 둔다: `sim.yaml`, `real.yaml`. 실기 튜닝 값은 `real.yaml`을 PR로 고친다.
- launch 인자 `source:=sim|robot_force` 하나로 전체 흐름을 전환한다(US-07).
- 실행 중 생성되는 측정 원본은 `ws_cobot1/data/`(gitignore)에 쓴다.

## 빌드
```bash
sod                                   # ws_dsr 오버레이 (robot_manager 실행에 필요)
cd ~/ws_cobot_pjt/ws_cobot1
colcon build --symlink-install
source install/setup.bash
```
