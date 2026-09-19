# 설계 문서 (design)

팀이 claude.ai와 회의로 만든 설계 문서의 **최신본**을 둔다. 새 버전을 올릴 때는 파일 이름의 버전을 올리고 **이전 버전 파일은 지운다**(이력은 git에 남는다).

**구속력 있는 계약은 `docs/contracts/`다.** 여기 문서와 계약이 다르면 계약이 맞다. 여기 문서는 시나리오 · 설계 배경 · 파라미터 목록 · 근거를 담는 참고 자료다.

| 파일 | 내용 | 버전 · 상태 |
|---|---|---|
| `contact-scan-interface-spec-integrated-v1.2.md` | 인터페이스 정의서 통합본(ROS 2 계약 + 웹 연동). 시나리오별 흐름, 필드별 근거, 노드별 파라미터(6장), 미확정 목록(10장), v1.1→v1.2 변경(16장) | v1.2 · T01 회의 반영 |
| `contact-scan-node-diagram-v1.1.md` | 노드 구성도(Mermaid) · 연결 표 40선 · 시나리오별 노드 순서 | v1.1 · T01 회의 반영 |
| `contact-scan-node-diagram-v1.1.drawio` | 노드 구성도 그림(위 md와 같은 그림 · 선 40개) | v1.1 · T01 회의 · #47 리뷰 반영(P03 선, 샘플의 motion_id·operation, 마무리 순서) |
| `contact-scan-node-overview-v1.2.drawio` | 노드 구조도 간략판(발표용) | v1.2 · 선 라벨 갱신(설정 전파, 실행 중 동작) |
| `contact-scan-system-architecture-v1.6.drawio` | 시스템 아키텍처 전체 그림(카드별 입력 → 처리 → 출력) | v1.6 · `/safety/reset` 포트·선, SetParameters 전파 선 3개(P01~P03), 파라미터 포트, RobotStatus 화살표 끝점 수정, 카드 문구를 계약 v0.1에 맞춤 |

drawio 파일은 [app.diagrams.net](https://app.diagrams.net)에서 연다. 그림을 고친 사람이 새 버전으로 교체한다. 2026-09-19 갱신분은 기존 그림의 XML을 스크립트로 고친 것이다(글자 수정, 포트·선 추가). 배치는 v1.3 형식을 유지했다.

관련: 요구사항은 `docs/BRD.md`(v3.2.0), BRD v3.1.0 원본(docx)은 `docs/archive/`.
