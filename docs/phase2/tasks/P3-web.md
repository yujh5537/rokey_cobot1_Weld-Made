# P3 웹: 용접 진행 시각화

**세션 이름: P3 웹 용접 시각화**
담당: 의석 · 기한: 9/28 (목업 발행기로 통과) · 공통 절차: `_common.md`

## 이 task
스캔 화면처럼 용접도 실시간으로 보이게 한다: 8 선 표시, 지금 용접 중인 선 강조, 끝난 선 색, 로봇이 실제로 지나간 궤적(비드), 진행률, 시작 · 중지 · 안전복귀 버튼.

## 계약 (확정)
- `docs/phase2/weld-mqtt-schema.md` 전체(토픽 · JSON · 3장 웹 표시).
- 좌표: `weld/result` 는 작업대 mm(`scan/result` 와 같은 프레임), `robot/sample` 은 Base mm. 겹칠 때 `weld/result.base_to_fixture_mm` 또는 기존 `VITE_BASE_TO_FIXTURE_MM`(App.jsx `getBaseToFixtureMm`) — 어느 쪽을 쓸지 정하고 README TBD 에 답한다.

## 초기 설계 (출발점)
- FastAPI(`backend/app/main.py`): 구독에 `weld/#` 추가, `cmd/weld/start|stop|home` 발행 엔드포인트(1차 `cmd/scan/*` 와 같은 `request_id` 발급 · `schema_version: "0.2"`). DB 저장은 `weld/result` 만(선택).
- 프런트: `weld/state` 로 phase · line_index · lines_done · line_progress 표시. `scan/result.edges` 의 0~3 · 8~11 을 8 선으로 미리 그리고, `weld/result.lines[].status` 로 색 갱신. 비드: `robot/sample.operation === "WELD_PATH" && motion_id > 0` 인 샘플 위치를 `motion_id` 별 polyline 으로 누적(10 Hz, 선당 약 80 점). 시작 버튼은 `scan/state.phase` 가 IDLE · DONE · ERROR · STOPPED 일 때만 활성.
- App.jsx(1,400 줄) 분리 여부는 담당자 판단(D9).
- 목업 발행기: 1차 목업에 `weld/state` · `weld/result` · `robot/sample(WELD_PATH)` 시나리오 추가 — mqtt_bridge(P4) 보다 먼저 웹을 돌리기 위한 입력.

## 테스트
- 목업 발행기로 8 선 진행 시나리오 재생 → 강조 · 색 · 궤적 · 진행률 확인(스크린샷을 PR 에).
- `backend/app/tests/test_commands.py` 에 `cmd/weld/*` 케이스.
- 9/29: 실기 종단(P4 mqtt_bridge 머지 뒤).
