# 설계 문서 (design)

팀이 claude.ai와 회의로 만든 설계 문서의 **최신본**을 둔다. 새 버전을 올릴 때는 파일 이름의 버전을 올리고 **이전 버전 파일은 지운다**(이력은 git에 남는다).

**구속력 있는 계약은 `docs/contracts/`다.** 여기 문서와 계약이 다르면 계약이 맞다. 여기 문서는 시나리오 · 설계 배경 · 파라미터 목록 · 근거를 담는 참고 자료다.

| 파일 | 내용 | 버전 · 상태 |
|---|---|---|
| `contact-scan-interface-spec-integrated-v1.2.md` | 인터페이스 정의서 통합본(ROS 2 계약 + 웹 연동). 시나리오별 흐름, 필드별 근거, 노드별 파라미터(6장), 미확정 목록(10장), v1.1→v1.2 변경(16장) | v1.2 · T01 회의 반영 |
| `contact-scan-node-diagram-v1.1.md` | 노드 구성도(Mermaid) · 연결 표 40선 · 시나리오별 노드 순서 | v1.1 · T01 회의 반영 |
| `contact-scan-node-diagram-v1.0.drawio` | 노드 구성도 그림(위 md와 같은 그림) | v1.0 · **T01 변경 미반영**(P03 전파 경로, 샘플의 motion_id·operation 등) |
| `contact-scan-node-overview-v1.1.drawio` | 노드 구조도 간략판(발표용) | v1.1 · T01 변경으로 달라지는 선은 없음(P03 제외) |
| `contact-scan-system-architecture-v1.5.drawio` | 시스템 아키텍처 전체 그림 | v1.5 · **T01 변경 미반영** |

drawio 파일은 [app.diagrams.net](https://app.diagrams.net)에서 연다. 그림을 고친 사람이 새 버전으로 교체한다.

관련: 요구사항은 `docs/BRD.md`(v3.2.0), BRD v3.1.0 원본(docx)은 `docs/archive/`.
