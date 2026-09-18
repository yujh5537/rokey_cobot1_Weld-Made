# ADR-0002: 웹 연동은 MQTT + FastAPI + Spring Boot + PostgreSQL

- 날짜: 2026-09-18 / 근거: BRD v3.0.0 4.7절, 12장 / 상태: 채택 (rosbridge·roslibjs 안을 대체)

## 결정
브라우저 → FastAPI → Mosquitto → mqtt_bridge → scan_manager. FastAPI는 실시간 통신·명령·측정 DB 쓰기, Spring Boot는 업무 데이터와 이력 조회. 정지·접촉 판정은 메인 PC에서 처리한다.

## 영향
ROS와 웹의 접점은 `docs/contracts/mqtt-schema.md` 한 장이다. 의석은 이 스키마의 목업 발행기로 ROS 진행과 무관하게 개발한다.
