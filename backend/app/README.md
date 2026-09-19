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

    {
      "topic": "scan/state",
      "payload": {}
    }

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

    PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest backend/app/tests -q

현재 테스트는 다음 상태 전이를 검증한다.

- `PUBLISHED → ACCEPTED`
- `PUBLISHED → REJECTED`
- `ACCEPTED → SUCCEEDED`
- `ACCEPTED → FAILED`
- Service 명령의 ACK 최종 성공 처리
- 요청별 서로 다른 `request_id` 생성
