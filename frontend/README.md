# frontend (담당: 의석)

React + Three.js 기반 Web UI.

현재 구현 범위:

- 시작 버튼
- 중지 버튼
- 안전복귀 버튼
- 재시작 버튼
- 현재 단계 표시
- 진행 방향 표시
- 진행도 표시
- Three.js 3D 작업대
- 직육면체 부재 표시
- 시간순 로그 표시

화면 문구는 "외곽 엣지·경로 후보"를 사용한다.

## 설치

```bash
cd frontend
npm install
```

## 개발 서버 실행

```bash
npm run dev -- --host 0.0.0.0
```

기본 주소:

```text
http://localhost:5173
```

## Production Build 확인

```bash
npm run build
```

CI에서는 다음 명령으로 설치와 빌드를 확인한다.

```bash
npm ci
npm run build
```

따라서 `package-lock.json`을 반드시 커밋한다.

## 현재 상태

현재 버튼은 React 내부 상태를 변경하는 UI 테스트 단계이다.

아직 FastAPI 또는 MQTT 명령과 직접 연결되어 있지 않다.

MQTT 목업 데이터는 `backend/mock_publisher/`에서 별도로 발행한다.