# fixtures — 용접 개발 입력

| 파일 | 출처 | 비고 |
|---|---|---|
| `sim_20260921-131938-1493.result.json` | sim 입력원 종단(T19b, 2026-09-21), `docs/test-reports/data/20260921/scan_sim_t19b/` | 100 × 60 × 40 mm 가상 박스. `node_params.base_to_fixture = [0.425, -0.184, 0.4]`. 연휴 중 weld_manager · 웹 개발용 |
| `real_<scan_id>.result.json` | **2026-09-23 실기 스캔 (M3, 아직 없음)** | 약 81 mm 큐브. 9/29 용접 리허설의 실제 입력 |

`weld_manager` 는 `<result_dir>/<scan_id>/result.json` 을 읽으므로, 개발 중에는 `data/<scan_id>/result.json` 으로 복사해 둔다:
```bash
mkdir -p ws_cobot1/data/20260921-131938-1493 && cp docs/phase2/fixtures/sim_20260921-131938-1493.result.json ws_cobot1/data/20260921-131938-1493/result.json
```
