# T22 FastAPI 실시간 연결

`docs/contracts/mqtt-schema.md` v0.1을 그대로 사용한다. 이슈의 `command_id` 문구보다 동결 계약의 `request_id`가 우선한다.

## 실행

저장소 루트에서 기존 `docker/.env` 설정을 사용한다.

```bash
docker compose -f docker/docker-compose.yml up -d --build mosquitto postgres fastapi
curl http://127.0.0.1:8000/health
```

프런트와 WebSocket을 먼저 연결한 뒤 별도 터미널에서 기존 목업을 실행한다.

```bash
python3 backend/mock_publisher/mock_publisher.py
```

목업 의존성은 해당 폴더 README를 따른다. 현재 목업은 5종 데이터를 한 번 발행하며, 명령 ACK/완료를 응답하는 로봇 시뮬레이터가 아니다. 이 목업만 켠 경우 버튼 요청은 접수 대기 후 미확정으로 표시되는 것이 정상이다.

## 웹 API

- `POST /api/scan/start`, `/stop`, `/home`, `/resume`: JSON `{}` 또는 `{"session_id":"...", "scan_id":"..."}`. `scan_id`는 resume에서만 전달한다.
- 응답 HTTP 202: FastAPI가 MQTT 발행 요청을 넣은 상태 `pending`. 로봇 접수를 의미하지 않는다.
- `GET /api/commands/{request_id}`: 현재 프로세스의 명령 상태 조회.
- `/ws/live`: `{topic,payload,received_at_ms,retained}`. 원본 JSON의 필드/단위/취득시각/null을 유지한다.
- 최초 `web/snapshot`: `mqtt_connected`, 최근 상태 `latest`, 최근 명령 `commands`.
- `web/connection`: 브로커 연결 상태. `web/command`: 요청 상태 변경.

명령 상태: `pending → accepted/rejected → completed/failed`. ACK 제한시간 초과 또는 MQTT 단절은 `unknown`이며 자동 재전송하지 않는다. 늦게 도착한 응답으로 갱신 가능하다. 완료가 ACK보다 먼저 도착해도 늦은 ACK로 완료 상태를 되돌리지 않는다. `scan/result`는 형상 결과이므로 명령 완료로 취급하지 않는다. `scan/command_result`로만 완료를 확인한다.

`ACK_TIMEOUT_S` 기본 5초는 웹 응답 대기 설정이다. 로봇 정지/heartbeat/데이터 최신성 정책을 정하는 값이 아니다. retained 상태는 원본 시각과 retain 표시를 전달한다. 실제 최신성 한계는 계약상 TBD이므로 현재 상태라고 자동 판정하지 않는다.

MQTT 콜백은 asyncio 루프로 인계한다. WebSocket 수신 큐는 256개로 제한하며 느린 클라이언트는 1013 종료 후 재접속한다. 이벤트/로그는 영구 저장하지 않으며 재접속 시 재생하지 않는다. 명령은 메모리 최대 1000개이며 서버 재시작 시 소실된다. 단일 Uvicorn worker로 실행한다.

## 검증 및 남은 범위

```bash
python -m pip install -r backend/app/requirements.txt pytest
python -m pytest backend/app/tests -q
```

6개 테스트: 접수/완료 분리, 역순 응답, 미확정/늦은 거절, 잘못된 JSON/null, 단절/느린 클라이언트, 4종 REST 계약, WebSocket 초기 상태.

실제 Mosquitto/ROS 종단 연결·지연·실기 정지는 현장 검증 전이다. `hb/web`/`conn/web` 생명주기와 브라우저 단절 조치는 별도 계약 결정 후 추가한다. 측정 DB 쓰기·업무 관리·로컬 재시작 기록은 이 T22 변경에 포함하지 않는다. 기존 `/db/test`, `/mqtt/test`, `/health`를 유지한다.
