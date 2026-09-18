---
paths:
  - "backend/**"
  - "frontend/**"
  - "docker/**"
---
# 웹 규칙

- 명령 흐름: 브라우저 → FastAPI → MQTT → mqtt_bridge → scan_manager. 웹은 로봇 모션을 직접 제어하지 않고, Spring Boot는 MQTT에 명령을 쓰지 않는다.
- DB 쓰기 책임: 측정·이벤트·기준값 이력은 FastAPI, 작업·공작물·사용자는 Spring Boot. Spring Boot는 측정 이력을 읽기만 한다.
- 버튼 4개(시작·중지·안전복귀·재시작)는 서로 다른 명령을 보낸다. 재시작을 새 시작으로 처리하지 않는다.
- 명령마다 command_id를 붙이고, "접수/거절"과 "완료/실패"를 화면에서 따로 표시한다. MQTT 전달 확인을 DB 커밋 완료로 취급하지 않는다.
- 화면 문구는 "외곽 엣지·경로 후보"를 쓴다. "용접선", "용접 경로"라고 표시하지 않는다(BRD 6장 결과물의 정의).
- MQTT 스키마는 `docs/contracts/mqtt-schema.md`가 기준이다. 목업 발행기(`backend/mock_publisher`)는 이 스키마 그대로 발행한다.
- 비밀번호·토큰은 `.env`에만 둔다. 공개 레포다. `.env.example`에는 키 이름만 적는다.
