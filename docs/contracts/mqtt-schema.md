# MQTT 토픽·JSON 스키마 계약

상태: **v0.0 초안**. T01 회의에서 v0.1로 동결.
이 문서 한 장이 ROS 쪽(병후, mqtt_bridge)과 웹 쪽(의석, FastAPI)의 유일한 접점이다. 의석의 목업 발행기(`backend/mock_publisher`)는 이 스키마 그대로 발행한다.

브로커: 웹 PC의 Mosquitto 1개. 주소·포트는 `docker/.env`.

## 공통 규칙 (제안, T01에서 확정)
- 길이 mm, 힘 N (BRD 제안). 각도 단위는 **TBD**
- 시각: ISO 8601 UTC 문자열 또는 epoch ms → **TBD**. 취득 시각(`acquired_at`)과 발행 시각(`published_at`)을 구분
- 모든 메시지에 `job_id`, 명령에는 `command_id`(UUID)
- 미측정·실패는 `null`. 0을 쓰지 않는다
- 명령 토픽은 retain=false. QoS·만료·재전송은 TBD

## 토픽 트리 (초안)
| 방향 | 토픽 | 내용 |
|---|---|---|
| 웹 → ROS | `cobot/cmd/start` `cobot/cmd/stop` `cobot/cmd/home` `cobot/cmd/resume` | 명령 4종. 서로 독립 |
| ROS → 웹 | `cobot/cmd/ack` | 접수/거절 (command_id, accepted, reason) |
| ROS → 웹 | `cobot/cmd/result` | 완료/실패 (command_id, success, error_code) |
| ROS → 웹 | `cobot/state` | 현재 단계, 방향 n/4, 중단·홈·재시작 진행 상태 |
| ROS → 웹 | `cobot/sample` | TCP 위치·힘 (표시용 10 Hz 목표) |
| ROS → 웹 | `cobot/event` | 접촉/엣지/과대 외력 이벤트 |
| ROS → 웹 | `cobot/result` | 꼭짓점, 외곽 엣지·경로 후보, 치수, 적용 설정 |
| ROS → 웹 | `cobot/log` | 시간순 로그 |
| 웹 → ROS | `cobot/web/heartbeat` | 1 Hz 목표. 브로커·백엔드·브라우저 연결을 구분 |

## JSON 예시
<!-- T01 회의에서 토픽마다 예시 1개씩 채운다. 목업 발행기와 mqtt_bridge 테스트가 이 예시를 그대로 쓴다. -->

### cobot/cmd/start
```json
{ "command_id": "TBD", "issued_at": "TBD", "job_id": "TBD" }
```
