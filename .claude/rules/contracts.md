---
paths:
  - "docs/contracts/**"
  - "ws_cobot1/src/contact_scan_interfaces/**"
---
# 계약 변경 규칙

- 계약은 v0.1(9/18 동결)부터 버전을 올리며 바꾼다. 필드 추가는 minor, 이름·타입·의미 변경은 다음 통합 빌드 전에 전원에게 알린다.
- 한 PR에서 같이 바꾼다: 계약 문서, `.msg/.srv/.action`, `docs/contracts/CHANGELOG.md`. MQTT 스키마를 바꾸면 `backend/mock_publisher`도 같이 고친다.
- 확정되지 않은 이름·필드는 문서에 `TBD` 또는 `초안`으로 표시한다. 추측으로 확정 표기하지 않는다.
- 모든 필드에 단위와 프레임을 적는다. 시각은 취득 시각인지 발행 시각인지 적는다.
- 필수 리뷰어: CODEOWNERS 참고(현지·병후, MQTT는 의석 포함).
