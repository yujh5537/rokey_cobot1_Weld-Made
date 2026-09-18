# 접촉 탐색 기반 외곽 엣지·경로 후보 생성 시스템

Doosan M0609 + OnRobot RG2(무센서 탐침)로 직육면체 부재를 만져 형상 좌표를 얻고, 윗면 외곽 엣지·경로 후보를 생성해 웹에서 실시간 3D로 보여주는 MVP. 교과 프로젝트 협동-1 (2026-09-18 ~ 09-22).

- 요구사항: [`docs/BRD.md`](docs/BRD.md) · 구조: [`docs/architecture.md`](docs/architecture.md) · 계약: [`docs/contracts/`](docs/contracts/)
- 작업 규칙: [`docs/conventions.md`](docs/conventions.md) · 일정·담당: GitHub Issues / Milestones
- 처음 받는 사람: [`SETUP.md`](SETUP.md)의 "팀원" 절

```
ws_cobot1/src/   ROS 2 Jazzy 자체 패키지 (메인 PC)
backend/         FastAPI, Spring Boot, MQTT 목업 발행기 (웹 PC)
frontend/        React + Three.js
docker/          Mosquitto, PostgreSQL, 백엔드 compose
docs/            BRD, 아키텍처, 계약, 결정 기록, 환경, 시험 결과
.claude/         팀 공통 Claude Code 설정·규칙·스킬
```

`ws_dsr/`(두산·RG2 드라이버)와 `DartPlatform/`은 이 레포에 없다. `docs/env/`를 따라 각자 구축한다.

<!-- 브랜치 보호 확인용 (머지 후 원복) -->
