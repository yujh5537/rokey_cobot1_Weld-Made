# frontend

React + Three.js 기반 접촉 탐색 시스템 Web UI.

## 현재 구현 범위

T23 기준으로 다음 기능을 구현한다.

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