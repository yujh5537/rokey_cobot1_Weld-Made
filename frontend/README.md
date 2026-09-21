# frontend

React + Three.js 기반 접촉 탐색 시스템 Web UI.

## 현재 구현 범위

T29 기준으로 다음 기능을 구현한다.

### 실시간 상태 표시

FastAPI WebSocket `/ws`를 통해 MQTT 데이터를 수신한다.

수신하는 주요 토픽:

- `scan/state`
- `robot/sample`
- `contact/event`
- `scan/log`
- `command/status`

`scan/state`를 기준으로 다음 스캔 단계를 실시간 표시한다.

- `IDLE` → 대기
- `PREPARING` → 시작 준비
- `TOP_SEARCH` → 윗면 탐색
- `EDGE_SEARCH` → 모서리 탐색 n/4
- `GEOMETRY` → 형상 생성
- `DONE` → 완료
- `ERROR` → 오류
- `STOPPING` → 중지 진행
- `STOPPED` → 중단됨
- `HOMING` → 홈 복귀 진행
- `RESUMING` → 재시작 진행

진행 방향과 진행도, scan ID도 함께 표시한다.

---

## 시간순 로그 패널

`scan/log`를 WebSocket으로 수신해 발생 시각 기준으로 시간순 정렬하여 표시한다.

표시 항목:

- 발생 시각
- 로그 레벨 (`INFO`, `WARN`, `ERROR`)
- 스캔 단계 (`phase`)
- 탐색 방향 (`direction`)
- 상태/오류 코드 (`code`, `code_name`)
- 로그 메시지
- 관련 좌표 (`pose`)
- 좌표 기준 프레임 (`frame_id`)

`scan/log.stamp_ms`를 실제 사건 발생 시각으로 사용하며,
React에서 메시지를 수신한 시각과 구분한다.

좌표가 유효한 경우(`pose_valid=true`) 다음 형식으로 표시한다.

```text
X 461.80 mm / Y -20.11 mm / Z 84.41 mm
frame=base_link
```

화면 로그는 최근 100개를 유지한다.

---

## 명령 상태 이력

React 제어 명령은 FastAPI REST API를 통해 전송한다.

```text
React
  → FastAPI REST
  → MQTT
  → mqtt_bridge
  → ROS Action / Service
```

FastAPI는 명령마다 `request_id`를 발급하고,
명령 상태가 변경될 때 WebSocket 가상 토픽 `command/status`로 React에 전달한다.

Action 기반 명령의 상태 흐름:

```text
PUBLISHED
  → ACCEPTED
  → SUCCEEDED
```

거절:

```text
PUBLISHED
  → REJECTED
```

실행 실패:

```text
PUBLISHED
  → ACCEPTED
  → FAILED
```

화면에서는 명령별로 다음 정보를 표시한다.

- 명령 이름
- 접수 결과: 접수 / 거절 / 대기
- 실행 결과: 완료 / 실패 / 대기
- 상태 코드
- Request ID
- 마지막 갱신 시각

화면 표시 이름:

- `cmd/scan/start` → 시작
- `cmd/scan/stop` → 중지
- `cmd/scan/home` → 안전복귀
- `cmd/scan/resume` → 재시작

`ACCEPTED`는 명령 접수이며 실제 동작 완료를 의미하지 않는다.

실제 완료/실패는 `scan/command_result`를 수신한 뒤
각각 `SUCCEEDED`, `FAILED`로 표시한다.

---

## 3D 관제

Three.js를 사용해 다음 정보를 표시한다.

- 작업대 목업
- 직육면체 부재 목업
- 현재 TCP 팁 위치
- TCP 이동 궤적
- 접촉점

표시 구분:

- 빨간 점: 현재 TCP 팁
- 파란 선: TCP 이동 궤적
- 노란 점: 접촉점

`robot/sample`과 `contact/event`의 좌표는 `base_link` 기준이며 웹에서는 mm 단위다.

현재 3D 화면은 목업 단계이므로 화면 표시를 위해 다음 배율을 사용한다.

```text
100 mm = Three.js 1 unit
```

---

## T29 검증

### 정적 검증

프론트엔드 코드 변경 후 다음 명령으로 lint와 production build를 검증했다.

```bash
cd frontend

npm run lint
npm run build
```

검증 결과:

```text
npm run lint  → 통과
npm run build → 통과
```

Vite build 시 Three.js를 포함한 번들 크기로 인해
500 kB 이상 chunk 경고가 발생하지만 build 자체는 정상 완료된다.

### Mock 통합 검증

실제 Mosquitto, FastAPI, WebSocket, React를 사용하고
ROS 측 메시지만 Mock MQTT payload로 발행해 검증했다.

검증 흐름:

```text
Mock MQTT payload
  → Mosquitto
  → FastAPI
  → WebSocket
  → React
```

`scan/log` 검증:

- `INFO / EDGE_SEARCH / POS_X / OK`
- `ERROR / EDGE_SEARCH / POS_Y / TIMEOUT`
- X/Y/Z 좌표 표시
- `base_link` frame 표시
- 발생 시각 기준 로그 표시

명령 상태 검증:

```text
start
PUBLISHED → ACCEPTED → SUCCEEDED
```

```text
stop
PUBLISHED → REJECTED
```

```text
home
PUBLISHED → ACCEPTED → FAILED
```

FastAPI의 `GET /commands/{request_id}` 상태와
React 화면의 명령 상태가 동일한지 확인했다.

이번 검증은 실제 `ROS2 → mqtt_bridge → scan_manager`를 사용하지 않은
Mock 통합 검증이다.

실제 ROS 통합 검증은 별도 통합 단계에서 수행한다.