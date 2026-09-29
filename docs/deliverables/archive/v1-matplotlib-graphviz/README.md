# 보관: 산출물 01 · 05 · 06 첫 판 (2026-09-27, matplotlib · Graphviz)

2026-09-28 에 산출물 01 · 05 · 06 을 `docs/design` 의 옛 설계 그림 형식(drawio)으로 다시 만들면서, 그 전의 첫 판을 여기에 그대로 둔다. 지금 쓰는 판은 한 단계 위 폴더에 있다(`../../01-system-architecture.md` · `../../05-interfaces.md` · `../../06-node-graph.md` 와 각 `.drawio`).

| 파일 | 내용 |
|---|---|
| `01-system-architecture-20260927.md` · `01-system-architecture.png` · `01-system-architecture-no-phase2.png` | 01 시스템 아키텍처 v1.7 첫 판 — matplotlib 좌표 배치 그림(갈래별 요약) |
| `05-interfaces-summary-20260927.md` | 05 인터페이스 정의서 요약본(토픽 · 서비스 · 액션 표 + MQTT 표 + 대표 msg 3 개) |
| `06-node-graph-20260927.md` · `06-node-graph.dot` · `06-node-graph-no-phase2.dot` · `06-node-graph.png` · `06-node-graph-no-phase2.png` | 06 노드 구조도 v1.2 첫 판 — Graphviz(dot), 연결 61 선 |
| `figures.py` | 위 png 를 만든 스크립트. 이 폴더 안에서 그대로 돈다: `python3 docs/deliverables/archive/v1-matplotlib-graphviz/figures.py` (matplotlib · graphviz · Noto Sans CJK KR 필요) |

- 보관한 md 는 옮기면서 링크만 고쳤다: 다른 산출물 링크는 이 폴더의 같은 날짜 사본을, 계약 링크는 `../../../contracts/` · `../../../phase2/` 를 가리킨다. 본문은 9/27 그대로다.
- 두 판의 차이: 첫 판은 9/27 ~ 9/28 main 기준 요약이고, 새 판은 v1.6 · v1.1 · v1.2 설계 형식(카드 · 연결 표 · 시나리오)에 네 갈래 코드 조사(9/28)를 반영했다. 사실이 달라진 곳(예: RG2 호출 없음, phase 2 브리지 미구현, W11 · W15 정정)은 새 판의 각 문서 "바뀐 것" 표에 있다.
