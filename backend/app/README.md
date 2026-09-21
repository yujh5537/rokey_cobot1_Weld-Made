# FastAPI MQTT/WebSocket Bridge

T22의 FastAPI는 Web UI와 Mosquitto 사이에서 실시간 상태 중계와 명령 발행을 담당한다.

## 데이터 흐름

ROS → Web:

    mqtt_bridge
      → Mosquitto
      → FastAPI MQTT subscriber
      → WebSocket /ws
      → React

Web → ROS:

    React
      → REST
      → FastAPI
      → Mosquitto
      → mqtt_bridge
      → ROS Action / Service

## MQTT 구독

FastAPI는 다음 MQTT 토픽을 구독한다.

- `robot/#`
- `scan/#`
- `contact/#`
- `safety/#`
- `cmd/ack`
- `hb/ros`
- `conn/ros`

수신한 MQTT 메시지는 다음 형식으로 WebSocket 클라이언트에 전달한다.

```json
{
  "topic": "scan/state",
  "payload": {}
}
```

WebSocket endpoint:

    /ws

## 명령 REST API

지원 명령:

    POST /commands/scan/start
    POST /commands/scan/stop
    POST /commands/scan/home
    POST /commands/scan/resume
    POST /commands/scan/set_config
    POST /commands/safety/reset

FastAPI가 각 요청마다 UUID v4 `request_id`와 `timestamp_ms`를 생성한다.

MQTT 계약 v0.1에서는 `command_id`가 아니라 `request_id`를 사용한다.

명령 상태 조회:

    GET /commands/{request_id}

## 명령 상태

Action 기반 명령:

    PUBLISHED
      → ACCEPTED
      → SUCCEEDED

거절:

    PUBLISHED
      → REJECTED

실행 실패:

    PUBLISHED
      → ACCEPTED
      → FAILED

`cmd/ack`는 접수/거절을 의미하며 작업 완료를 의미하지 않는다.

`scan/command_result`가 실제 완료/실패 결과다.

`set_config`, `safety/reset`은 Service 기반이므로 성공한 `cmd/ack`를 최종 성공으로 처리한다.

FastAPI는 상태 변경을 WebSocket의 가상 토픽 `command/status`로도 전달한다.

현재 명령 상태는 FastAPI 프로세스 메모리에 저장되므로 프로세스를 재시작하면 초기화된다.

## 테스트

테스트용 Python 환경에서:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest backend/app/tests -q
```

현재 테스트는 다음 상태 전이를 검증한다.

- `PUBLISHED → ACCEPTED`
- `PUBLISHED → REJECTED`
- `ACCEPTED → SUCCEEDED`
- `ACCEPTED → FAILED`
- Service 명령의 ACK 최종 성공 처리
- 요청별 서로 다른 `request_id` 생성

## T27 mqtt_bridge ↔ FastAPI 실제 통합 검증

2026-09-21 Main PC의 ROS 2 / DSR Virtual 환경과 Web PC의
Mosquitto / FastAPI / React를 실제 연결해 양방향 통신을 검증했다.

### 검증 경로

ROS → Web:

    DSR Virtual
      → robot_manager / scan_manager
      → mqtt_bridge
      → Web PC Mosquitto
      → FastAPI
      → WebSocket
      → React

Web → ROS:

    React
      → FastAPI REST
      → Web PC Mosquitto
      → mqtt_bridge
      → scan_manager
      → robot_manager
      → DSR Virtual

Main PC의 mqtt_bridge는 Web PC Broker를 사용했다.

    broker_host = <Web PC 주소>
    broker_port = 1883

### 실제 검증 결과

- `conn/ros`, `hb/ros`가 Main PC mqtt_bridge에서 Web PC Mosquitto를 거쳐 FastAPI까지 수신됨
- FastAPI `/ws` WebSocket에서 실제 `hb/ros` 메시지 수신 확인
- React `시작` 버튼으로 실제 스캔 실행
  - `cmd/scan/start`
  - `cmd/ack accepted=true`
  - `PREPARING → TOP_SEARCH → EDGE_SEARCH → DONE`
  - 진행도 `4 / 4`
  - 명령 상태 `SUCCEEDED`
- 실행 중 React `중지` 버튼으로 실제 스캔 중단
  - `cmd/scan/stop`
  - `cmd/ack accepted=true`
  - 최종 `scan/state phase=STOPPED`
  - Stop 명령 상태 `SUCCEEDED`
- 중지된 Start 명령은 `STOP_REQUESTED(200) — stopped` 결과로 종료됨
- 실제 mqtt_bridge 메시지와 `docs/contracts/mqtt-schema.md` v0.1 사이에
  스키마 차이는 발견되지 않음

### 통합 시 주의사항

동일한 ROS graph에 `/mqtt_bridge` 노드를 두 개 띄우지 않는다.

`contact_scan_bringup`에서 자동 실행된 mqtt_bridge와 별도로
Web PC Broker를 지정한 mqtt_bridge를 실행하면 동일 노드가 두 개 생길 수 있다.
실제 통합 시 Web PC Broker에 연결된 mqtt_bridge 하나만 유지한다.

현재 Stop 검증에서는 `/scan/stop`이 정상 접수되고 Action cancel을 통해
실제 로봇 동작이 중지되어 `STOPPED`까지 전이했다.

이때 ACK detail에 `/robot/stop 서버가 없다`가 표시됐다. 계약상 `/robot/stop`은
robot_manager가 제공하고, scan_manager는 중지 시 `/robot/stop` 호출과 goal cancel을
함께 한다(ros-interfaces.md 2장·4.4절). 이번 검증은 **goal cancel 경로 하나로만**
정지했다.

현재 main의 robot_manager에는 `/robot/stop` 서버가 없다(T14, 진행 중 PR 있음).
safety_monitor의 웹 비경유 정지도 이 서비스를 쓰므로, **시연 전에 반드시 들어가야 한다.**
해당 PR 머지 후 중지 경로를 다시 확인한다.

## T28 PostgreSQL 측정·이벤트 저장

FastAPI는 MQTT로 수신한 `scan/result`와 `contact/event`를 PostgreSQL에 저장한다.

데이터 흐름:

    ROS2
      → mqtt_bridge
      → Mosquitto
      → FastAPI
      → PostgreSQL

실시간 화면 전달은 기존 흐름을 유지한다.

    Mosquitto
      → FastAPI
      → WebSocket
      → React / Three.js

### PostgreSQL 테이블

T28에서는 다음 4개 테이블을 사용한다.

- `scan_jobs`
  - 한 번의 스캔 작업 정보
  - `scan_id`, 성공 여부, 사유, 시작·종료 시각 저장

- `measurements`
  - 스캔의 최종 측정 결과
  - 가로·세로·높이, 접촉 탐색 좌표, 꼭짓점·엣지·경로 후보 저장
  - `scan_jobs.scan_id`와 1:1 관계

- `contact_events`
  - 스캔 중 발생한 CONTACT, EDGE, OVER_FORCE 이벤트 저장
  - 한 스캔에서 여러 이벤트가 발생할 수 있으므로 `scan_id + event_id`로 중복을 방지

- `scan_configs`
  - 해당 스캔에 실제 적용된 설정 snapshot 저장
  - `scan_jobs.scan_id`와 1:1 관계

초기 스키마:

    docker/postgres/init/001_schema.sql

PostgreSQL 컨테이너에서는 다음 경로로 mount한다.

    /docker-entrypoint-initdb.d/001_schema.sql

**주의**: `/docker-entrypoint-initdb.d`의 초기화 스크립트는 PostgreSQL 데이터 볼륨이 비어 있을 때만 실행된다.

기존 `postgres_data` 볼륨이 이미 생성되어 있다면 새 스키마가 자동으로 적용되지 않는다.

이 경우 다음 중 하나가 필요하다.

기존 PostgreSQL 데이터를 삭제해도 되는 경우:

```bash
docker compose \
  --env-file docker/.env \
  -f docker/docker-compose.yml \
  down -v
```

이후 다시 컨테이너를 기동하면 초기화 스크립트가 실행된다.

기존 PostgreSQL 데이터를 유지해야 하는 경우:

```bash
docker compose \
  --env-file docker/.env \
  -f docker/docker-compose.yml \
  exec -T postgres \
  psql -U contact_scan -d contact_scan \
  < docker/postgres/init/001_schema.sql
```

`001_schema.sql`은 `CREATE TABLE IF NOT EXISTS`를 사용하므로 동일 스키마에 다시 실행해도 된다.

### scan/result 저장

`scan/result`를 수신하면 `save_scan_result()`가 하나의 DB transaction 안에서 다음 데이터를 저장한다.

    scan/result
      ├─ scan_jobs
      ├─ measurements
      └─ scan_configs

같은 `scan_id`가 다시 들어오면 `ON CONFLICT`로 기존 결과를 갱신한다.

중단 후 재시작은 기존 `scan_id`를 유지하므로 새 작업을 만들지 않고 같은 작업 결과를 갱신한다.

### contact/event 저장

`contact/event`를 수신하면 `save_contact_event()`가 `contact_events`에 저장한다.

    contact/event
      → FastAPI
      → save_contact_event()
      → contact_events

동일한 `(scan_id, event_id)`가 다시 들어오면 기존 행을 갱신해 중복 이벤트 저장을 방지한다.

### 미측정값과 정상 0 구분

MQTT 계약에 따라 미측정값은 `null`로 전달하고 PostgreSQL에는 `NULL`로 저장한다.

예:

    x_neg_mm = 0.0
    x_neg_valid = true

위 값은 정상적으로 측정된 `0 mm`이다.

반면:

    y_pos_mm = null
    y_pos_valid = false

위 값은 미측정 상태이며 PostgreSQL에는 `NULL`로 저장한다.

따라서 정상 값 `0`과 미측정 `NULL`을 구분한다.

### MQTT 수신과 DB commit 구분

MQTT 메시지를 FastAPI가 수신한 것과 PostgreSQL 저장 완료는 같은 의미가 아니다.

정상 흐름:

    MQTT received
      → DB transaction
      → COMMIT
      → DB 저장 성공

저장 실패:

    MQTT received
      → DB transaction 실패
      → 저장 실패 로그
      → DB에는 결과를 저장하지 않음

FastAPI 로그는 두 상태를 구분한다.

정상 저장:

    [MQTT] received ...
    [DB] scan/result committed ...

저장 실패:

    [MQTT] received ...
    [DB] scan/result save failed ...

### Mock 연동 검증

T28에서는 실제 Mosquitto, FastAPI, PostgreSQL 컨테이너를 사용하고 MQTT payload만 Mock으로 발행해 연동을 검증했다.

검증 경로:

    mosquitto_pub
      → Mosquitto
      → FastAPI on_message()
      → save_scan_result() / save_contact_event()
      → PostgreSQL

검증 항목:

- `scan/result`가 `scan_jobs`, `measurements`, `scan_configs`에 저장되는지 확인
- `contact/event`가 `contact_events`에 저장되는지 확인
- 정상 `0.0`과 미측정 `NULL`이 구분되는지 확인
- `pose`, `wrench`가 JSONB로 저장되는지 확인
- 필수 필드가 없는 MQTT 메시지는 수신되더라도 DB에 저장되지 않는지 확인

이 검증은 실제 ROS2 노드에서 발생한 데이터가 아니라 Mock MQTT payload를 이용한 웹/DB 연동 검증이다.