# T23 React + Three.js 관제 화면

T22 FastAPI와 함께 실행한다. MQTT 계약은 `docs/contracts/mqtt-schema.md` v0.1이며 길이는 mm, 좌표축은 Z-up으로 그린다.

## 실행 (저장소 루트에서)

```bash
cd frontend
npm ci
npm run dev -- --host 0.0.0.0
```

Vite의 `/api`와 `/ws` 프록시가 같은 PC의 FastAPI 8000 포트로 연결한다. 브라우저에서 Vite가 출력한 주소를 연다. 다른 FastAPI 포트는 `vite.config.js`의 두 프록시 주소를 함께 맞춘다. 배포 서버에서는 `/api`, `/ws` reverse proxy를 별도로 구성해야 한다.

화면을 먼저 연 뒤 별도 터미널에서 기존 목업을 실행한다.

```bash
python3 backend/mock_publisher/mock_publisher.py
```

## 동작

- `scan/state`: 단계, 방향, 진행 n/4. 알 수 없는 enum도 원문을 표시한다.
- `robot/sample`: 유효한 팁 위치 및 최근 1000개 궤적. 무효 값은 숫자 0으로 대체하지 않는다.
- `contact/event`: 동일 프레임 접촉점, 작업/event ID 중복 제거. 최대 200개.
- `scan/log`: 발생시각 순으로 최근 200개.
- 시작·중지·안전복귀·재시작은 독립 REST 요청. 버튼을 눌렀다는 이유로 로봇 단계를 변경하지 않는다.
- `request_id`로 접수 대기/접수/거절/완료/실패/미확정 표시. 재시작은 현재 scan_id를 유지한다.
- 화면 단절 시 자동 재접속 및 FastAPI snapshot 수신. 명령 자동 재전송 없음.

마우스 드래그로 회전, 휠로 확대한다. 파랑은 궤적, 주황은 접촉점, 민트는 팁이다.

작업대는 표시용 기준 평면이며 실측 배치가 아니다. `base_link` 샘플과 `workpiece_fixture` 결과를 임의로 겹치지 않는다. T03 변환값 확정 및 결과 형상 표시 연결은 후속 범위다. 기존 목업은 한 번의 고정 샘플이므로 긴 궤적 검증에는 여러 위치의 연속 샘플이 필요하다. 명령 ACK/완료 응답도 기존 목업에는 없다.

## 확인

```bash
npm run build
npm run lint
```

빌드·lint 통과. 브라우저 WebGL 렌더링, 실제 브로커 연속 목업과 4버튼 종단 검증은 현장 확인 전이다. 상태 취득시각과 연결 상태를 함께 표시하며, 최신성 임계값은 계약 확정 전이다. 웹 조작 정지와 물리 비상정지는 별개다.
