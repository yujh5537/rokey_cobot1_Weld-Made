# backend (담당: 의석)

- `app/` FastAPI: MQTT 구독 → WebSocket, 명령 REST → MQTT, 측정·이벤트 DB 쓰기
- `spring/` Spring Boot: 작업·공작물 관리, 측정 이력 조회 (Day 4 하루, CRUD와 조회로 최소화)
- `mock_publisher/` `docs/contracts/mqtt-schema.md` 스키마대로 가짜 데이터를 발행. 스키마가 바뀌면 같은 PR에서 고친다

CI는 `app/requirements.txt`, `app/tests/`, `spring/gradlew`가 있으면 자동으로 빌드·테스트한다.
