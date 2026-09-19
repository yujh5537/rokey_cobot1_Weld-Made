# 계약 (contracts)

모듈 사이의 약속이다. 네 명의 Claude가 같은 계약을 보고 구현해야 합칠 때 어긋나지 않는다. **코드와 계약이 다르면 계약이 맞고 코드가 버그다.** 계약이 틀렸으면 계약부터 PR로 고친다.

| 문서 | 내용 | 소유 |
|---|---|---|
| `ros-interfaces.md` | ROS Action/Service/Topic 이름, 타입, 필드 | 병후 |
| `mqtt-schema.md` | MQTT 토픽, JSON 스키마, 명령 ID, QoS | 병후·의석 |
| `units-frames.md` | 단위, 좌표계, TCP, 홈, 작업대 원점, z=0 | 학민 |
| `CHANGELOG.md` | 계약 변경 이력 | 바꾼 사람 |

## T01 동결 회의(9/18) 결과 — v0.1
정의서 통합본 v1.1(팀 합의)을 계약 v0.1로 채택하고, 1차(병후·의석) · 2차(전원) 회의 결정을 덧붙였다. 정의서와 달라진 곳은 `CHANGELOG.md`에 있다.

- [x] msg/srv/action 필드와 타입 → **확정** (`ros-interfaces.md` 3~5장: msg 8 + 하위 msg 3 · srv 5 · action 4)
- [x] 재시작 연결 방식 → **확정**: 별도 Action `/scan/resume`. 홈 복귀 후 재접근은 절차 확정 전까지 `NOT_SUPPORTED`
- [x] 동작 식별자와 작업 식별자 형식 → **확정**: `motion_id` uint32(0 = 없음), 작업 식별자는 `job_id`가 아니라 `scan_id`(`YYYYMMDD-HHMMSS-xxxx`)
- [x] 명령 ID 형식, 중복 처리, 접수/완료 구분 → **확정**: `command_id`가 아니라 `request_id`(UUID v4). 중복 · 만료는 mqtt_bridge가 거절. 접수 = `cmd/ack`, 완료 = `scan/command_result`
- [x] MQTT 토픽 트리, QoS, retain, JSON 필드 → **확정** (`mqtt-schema.md`). 명령은 retain=false
- [x] 단위 → **확정**: ROS 내부 m·rad·N, 웹 mm. 웹에는 각도 값을 싣지 않는다
- [x] 시각 표기 → **확정**: ROS는 메인 PC 시계 · 취득 시각 각각 보존, MQTT는 epoch ms + `published_at_ms`. 시계 동기는 chrony(의석, 별도 PR)
- [x] 미측정·실패 값 표기 → **확정**: ROS `NaN` + `*_valid=false`, MQTT `null` + `*_valid` 유지, Python `None`
- [x] 오류 코드 목록 → **확정**: `ReasonCode` 33개. 번호는 추가만 하고 바꾸지 않는다

### TBD로 남긴 것
회의에서 **담당 · 기한은 정하지 않고 TBD로 두기로** 했다. 목록은 각 문서 끝에 있다(`ros-interfaces.md` 9장, `mqtt-schema.md` 5장, `units-frames.md`의 좌표 값 · 미결정).
