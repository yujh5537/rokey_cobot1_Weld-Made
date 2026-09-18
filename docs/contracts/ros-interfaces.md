# ROS 인터페이스 계약

상태: **v0.0 초안** (BRD v3.0.0 4.7절 표를 옮긴 것. T01 회의에서 v0.1로 동결)
패키지: `contact_scan_interfaces` (ament_cmake, 소유 병후)

## 연결 표
| 역할 | 이름 (초안) | 종류 | 송신 → 수신 | 상태 |
|---|---|---|---|---|
| 스캔 실행 | `/scan/run` | Action | mqtt_bridge → scan_manager | 초안 |
| 홈 안전복귀 | `/scan/home` | Action | mqtt_bridge → scan_manager | 초안 |
| 재시작 | TBD | TBD | mqtt_bridge → scan_manager | **TBD (T01)** |
| 작업 중지 | `/scan/stop` | Service | mqtt_bridge → scan_manager | 초안 |
| 설정 변경 | `/scan/set_config` | Service | mqtt_bridge → scan_manager | 초안. 실행 중 변경 정책 TBD |
| 개별 모션 | `/robot/execute_motion` | Action | scan_manager → robot_manager | 초안 |
| 정지 | `/robot/stop` | Service | scan_manager, safety_monitor → robot_manager | 초안. 웹을 경유하지 않음 |
| 힘 영점 | `/contact/tare` | Service | scan_manager → contact_detector | 초안 |
| TCP·힘 샘플 | `/robot/sample` (`RobotSample`) | Topic | robot_manager → contact_detector, safety_monitor, scan_manager, mqtt_bridge | 초안 |
| 로봇 상태 | `/robot/status` | Topic | robot_manager → (상세 설계) | 초안 |
| 접촉·엣지 이벤트 | `/contact/event` | Topic | contact_detector → robot_manager, scan_manager, mqtt_bridge | 초안 |
| 단계·결과·로그 | `/scan/state`, `/scan/result`, `/scan/log` | Topic | scan_manager → mqtt_bridge (상태는 판정·감시에도) | 초안 |
| 감시 상태 | `/safety/status` | Topic | safety_monitor → scan_manager, mqtt_bridge | 초안 |
| 웹 heartbeat | `/web/heartbeat` | Topic | mqtt_bridge → safety_monitor | 초안 |

두산 드라이버의 네임스페이스는 `/dsr01`이다. 자체 노드의 네임스페이스 사용 여부는 T01에서 정한다.

## 타입 정의
<!-- T01 회의 결과를 아래에 채운다. 필드마다 단위·프레임·시각의 의미를 적는다. -->

### RobotSample.msg (초안 뼈대)
```
# TCP와 힘은 취득 시각이 다르다. 같은 메시지라고 동시 취득으로 보지 않는다 (BRD 4.1.6)
builtin_interfaces/Time tcp_stamp      # TCP 취득 시각
builtin_interfaces/Time force_stamp    # 힘 취득 시각
string frame_id                        # 좌표 기준 (units-frames.md)
float64[6] tcp_pose                    # TBD: 단위·자세 표현
float64[6] tool_force                  # TBD: 단위·기준 좌표
bool tcp_valid
bool force_valid
uint32 motion_id                       # 현재 실행 중인 동작. 없으면 0
```

### ContactEvent.msg, ScanState.msg, ScanResult.msg, ExecuteMotion.action, RunScan.action
TBD (T01)

## QoS
TBD. 설계 목표는 샘플 50 Hz 수집, 화면 10 Hz 표시, heartbeat 1 Hz이며 **측정 결과가 아니다**. 실제 발행 주기는 T15에서 실측해 여기에 적는다.
