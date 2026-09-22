# frontend

React + Three.js 기반 접촉 탐색 시스템 Web UI.

## 현재 구현 범위

T29와 T36 기준으로 다음 기능을 구현한다.

---

## 실시간 상태 표시

FastAPI WebSocket `/ws`를 통해 MQTT 데이터를 수신한다.

수신하는 주요 토픽:

- `scan/state`
- `robot/sample`
- `robot/joints`
- `contact/event`
- `scan/result`
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

진행 방향과 진행도, Scan ID도 함께 표시한다.

새로운 스캔이 시작되면 이전 스캔의 형상 결과가 남아 있지 않도록
다음 조건에서 기존 `scanResult`를 초기화한다.

```text
scan/state 수신
  ├─ phase == PREPARING
  │    └─ 이전 scanResult 제거
  │
  └─ scan_id 변경
       └─ 이전 scanResult 제거
```

이를 통해 새 탐색이 시작됐는데 이전 작업의 외곽 엣지·경로 후보가
화면에 계속 남아 있는 문제를 방지한다.

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

- 실제 Doosan M0609 visual mesh
- M0609 J1~J6 실시간 관절 자세
- OnRobot RG2 visual mesh(탐침 고정 파지 자세)
- TCP [0, 0, 252.12] mm 기준 탐침 시각화
- 작업대(상판 기준 실제 높이 94 mm)
- `scan/result.vertices` 기반 동적 부재 Mesh
- 현재 TCP 팁 위치
- TCP 이동 궤적
- 접촉점
- `scan/result.edges` 일반 모서리
- `scan/result.path_candidates` 외곽 엣지·경로 후보

3D 화면 조작:

- 좌클릭 드래그: 회전
- 마우스 휠: 확대·축소
- 우클릭 드래그: 이동
- `OrbitControls` damping 적용

M0609 관절 데이터 흐름:

```text
/dsr01/joint_states
  → mqtt_bridge (20 Hz)
  → MQTT robot/joints
  → FastAPI robot/# 구독
  → WebSocket
  → React
  → Three.js joint_1~joint_6
```

M0609 visual mesh는 DoosanRobotics/doosan-robot2의 `m0609_white` COLLADA를 사용하고, RG2 visual mesh는 ABC-iRobotics/onrobot-ros2의 RG2 STL을 사용한다. 현재 웹은 이 공개 원격 asset을 읽으므로 브라우저에서 GitHub raw asset 접근이 가능해야 한다.

RG2는 이번 MVP에서 탐침을 계속 고정 파지하므로 finger feedback을 별도 MQTT 계약으로 만들지 않고 고정 자세로 렌더링한다.

표시 구분:

- 빨간 점: 현재 TCP 팁
- 파란 선: TCP 이동 궤적
- 노란 점: 접촉점
- 회색 선: 스캔 결과의 일반 모서리
- 초록 선: 외곽 엣지·경로 후보

외곽 엣지·경로 후보는 일반 모서리와 같은 위치에 겹칠 수 있으므로
초록 경로 후보는 `depthTest=false`, `renderOrder=1`로 설정해
회색 일반 모서리보다 우선해서 보이도록 한다.

---

## 3D 좌표계

### ROS / MQTT 좌표

`robot/sample`과 `contact/event`의 좌표는 `base_link` 기준이며
Web에서는 mm 단위로 전달된다.

`scan/result`의 다음 항목은 `workpiece_fixture` 기준이다.

- `edges`
- `path_candidates`
- 형상 좌표

따라서 두 데이터를 같은 Three.js 장면에 그대로 그리면
서로 다른 좌표계의 데이터를 같은 원점에 표시하게 된다.

### ROS → Three.js 축 변환

ROS 좌표계는 z-up이고 Three.js 장면은 y-up이므로 다음과 같이 변환한다.

```text
ROS / MQTT
(x, y, z)

    ↓

Three.js
(x, z, -y)
```

즉 코드에서는 공통 변환 함수를 사용한다.

```text
Three X = ROS X
Three Y = ROS Z
Three Z = -ROS Y
```

화면 표시 배율:

```text
100 mm = Three.js 1 unit
```

---

## workpiece_fixture → base_link 변환

`scan/result`는 `workpiece_fixture` 기준이고,
TCP 팁·접촉점은 `base_link` 기준이기 때문에
3D에서 두 결과를 함께 보기 위해 작업대 원점 위치를 추가한다.

현재 계약에서 `base_to_fixture`는 회전을 포함하지 않고
평행 이동만 사용한다.

```text
workpiece_fixture 좌표
        +
base_to_fixture
        ↓
base_link 좌표
```

Web에서는 다음 Vite 환경변수로 값을 전달한다.

```env
VITE_BASE_TO_FIXTURE_MM=423.56,-186.06,100.503
```

실기 기준:

```text
X = 423.56 mm
Y = -186.06 mm
Z = 100.503 mm
```

sim 기준:

```text
X = 425 mm
Y = -184 mm
Z = 400 mm
```

실기와 sim의 값이 다르므로 실행 환경에 맞는 값을 사용해야 한다.

`search_origin_pose`와 `base_to_fixture`는 같은 값이 아니므로
서로 대체해서 사용하지 않는다.

---

## Vite 환경변수 설정

Web PC에서:

```text
frontend/.env.local
```

파일을 만들고 실기 실행 시 다음 값을 설정한다.

```env
VITE_BASE_TO_FIXTURE_MM=423.56,-186.06,100.503
```

`.env.local`은 `*.local` 규칙으로 Git에 포함되지 않는다.

환경변수는 Vite 시작 시 읽으므로 값을 변경한 뒤에는
개발 서버를 다시 시작해야 한다.

```bash
cd frontend

npm run dev -- --host 0.0.0.0
```

이미 개발 서버가 실행 중이었다면 먼저 `Ctrl+C`로 종료한 뒤 다시 실행한다.

### 환경변수 미설정 처리

`VITE_BASE_TO_FIXTURE_MM`이 없거나 올바른 숫자 3개가 아니면
서로 다른 좌표계의 데이터를 잘못 겹쳐 그리지 않는다.

이 경우:

```text
scan/result 좌표 표 → 표시
3D edges            → 표시하지 않음
3D path_candidates  → 표시하지 않음
```

그리고 화면에 다음 경고를 표시한다.

```text
작업대 원점 미설정:
VITE_BASE_TO_FIXTURE_MM 값을 확인하세요.
```

즉 좌표 변환값을 모르는 상태에서 임의의 위치에 형상 결과를 표시하지 않는다.

---

## T36 외곽 엣지·경로 후보 표시

`scan/result`를 WebSocket으로 수신해 최종 형상 결과를 화면에 표시한다.

데이터 흐름:

```text
scan/result
  ├─ edges
  │   └─ Three.js 일반 모서리
  │
  └─ path_candidates
      ├─ Three.js 강조 경로
      └─ 좌표·길이 표
```

경로 후보 표에는 각 선분의 다음 정보를 mm 단위로 표시한다.

- 시작점 X/Y/Z
- 끝점 X/Y/Z
- 길이

현재 좌표·길이 표는 `path_candidates` 4개를 대상으로 한다.

`edges` 12개 전체는 3D 일반 모서리로 표시하며,
표 형태로는 표시하지 않는다.

`scan/result.success=true`인 경우에만 유효한 형상 데이터를 표시한다.

3D 표시에서는 `valid=true`인 `edges`와 `path_candidates`만 렌더링한다.

홈 복귀와 재시작 진행 상태는 기존 `scan.state` phase 표시를 사용한다.

```text
HOMING   → 홈 복귀 진행
RESUMING → 재시작 진행
```

T36에서는 별도의 홈 복귀·재시작 상태 체계를 추가하지 않고,
기존 phase 상태를 Web UI에 계속 표시하는 방식으로 완료 조건을 충족한다.

---

## T36 검증

### 정적 검증

초기 T36 구현 후 다음 검증을 수행했다.

```bash
npm run lint
npm run build
git diff --check
```

초기 구현 검증 결과:

```text
npm run lint     → 통과
npm run build    → 통과
git diff --check → 통과
```

Vite production build는 정상 완료됐으며,
Three.js가 포함된 bundle에 대해 500 kB 초과 경고가 발생했다.

좌표 변환과 이전 결과 초기화 수정 후에는 다음 검증을 다시 수행했다.

```bash
npm run lint
git diff --check
```

결과:

```text
npm run lint     → 통과
git diff --check → 통과
```

최종 PR 전 production build는 다시 실행한다.

---

### Mock 통합 검증

Web PC에서 실제 Mosquitto, FastAPI, WebSocket, React를 실행하고
ROS 측 데이터만 Mock MQTT payload로 발행해 T36 화면 동작을 검증했다.

검증 흐름:

```text
Mock MQTT
  → Mosquitto
  → FastAPI
  → WebSocket
  → React / Three.js
```

검증 결과:

- `scan/result` 수신 확인
- 결과 좌표 프레임 `workpiece_fixture` 표시 확인
- `path_candidates` 4개의 시작점/끝점/길이 표 표시 확인
- 일반 모서리와 외곽 엣지·경로 후보 3D 렌더링 확인
- 외곽 엣지·경로 후보의 초록색 강조 표시 확인
- 초록 후보선이 회색 일반 모서리 위에 표시되는 것 확인
- `HOMING` 수신 시 `홈 복귀 진행` 표시 확인
- `RESUMING` 수신 시 `재시작 진행` 표시 확인
- FastAPI WebSocket 연결 상태 표시 확인
- `VITE_BASE_TO_FIXTURE_MM` 미설정 시 경고 및 3D 결과 숨김 확인
- `VITE_BASE_TO_FIXTURE_MM` 설정 후 fixture 결과의 평행 이동 적용 확인
- `PREPARING` 수신 시 이전 scan 결과 표 제거 확인
- `PREPARING` 수신 시 이전 edges/path candidates 3D 결과 제거 확인
- 새로운 `scan_id`가 들어올 때 이전 scan 결과 초기화 확인

Mock `scan/result`의 경로 후보 길이는 다음과 같이 표시됐다.

```text
1: 100.00 mm
2:  60.00 mm
3: 100.00 mm
4:  60.00 mm
```

새 스캔 시작 검증에서는 다음 MQTT 상태를 발행했다.

```text
phase   = PREPARING
scan_id = 20260921-new-scan-test
```

화면에서는 다음과 같이 변경됐다.

```text
현재 단계 → 시작 준비
Phase     → PREPARING
Scan ID   → 20260921-new-scan-test

이전 경로 후보 표         → 제거
이전 일반 edges          → 제거
이전 path_candidates     → 제거
```

---

### Mock 좌표 검증의 한계

Mock publisher의 `robot/sample`, `contact/event`, `scan/result` 좌표는
하나의 실제 접촉 상황을 재현하도록 만들어진 데이터가 아니다.

예를 들어 Mock 접촉점은 `base_link` 기준으로 다음 위치다.

```text
X = 461.80 mm
Y = -20.11 mm
Z = 84.41 mm
```

반면 Mock 경로 후보 첫 점은 `workpiece_fixture` 기준:

```text
X = 0 mm
Y = 0 mm
Z = 50 mm
```

이고 실기 `base_to_fixture`를 적용하면 Base 기준:

```text
X = 423.56 mm
Y = -186.06 mm
Z = 150.503 mm
```

가 된다.

따라서 Mock 화면에서 TCP·접촉점과 경로 후보가 정확히 겹치지 않는 것은
현재 좌표 변환 코드의 오류를 의미하지 않는다.

이번 Mock 검증에서 확인한 것은:

```text
ROS → Three.js 축 변환 적용
workpiece_fixture → base_link 평행 이동 적용
환경변수 유무에 따른 안전한 표시 처리
```

까지다.

실제 접촉점과 스캔 결과 형상이 동일 위치에 정렬되는지는
실제 ROS2 → mqtt_bridge → Web 통합 환경에서 추가 검증해야 한다.

---

## 3D 목업 주의사항

현재 화면의 작업대와 직육면체 부재 Mesh는
UI 개발을 위한 고정 목업이다.

```text
작업대 목업
직육면체 부재 목업
```

은 실제 `base_link`의 절대 위치에 맞춰 배치된 디지털 트윈이 아니다.

반면 다음 데이터는 실제 전달 좌표를 기반으로 표시한다.

```text
robot/sample
contact/event
scan/result.edges
scan/result.path_candidates
```

따라서 `base_to_fixture`를 적용하면 실시간 좌표 데이터가
화면의 고정 목업과 떨어져 보일 수 있다.

이는 현재 목업 단계에서는 정상이며,
실제 장비 배치와 동일한 3D 모델 정렬은 별도 작업 범위다.

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

---

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