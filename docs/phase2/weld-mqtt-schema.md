# MQTT 토픽 · JSON (phase 2, 용접)

상태: **v0.2.0 초안** (2026-09-23, 병후). 1차 `docs/contracts/mqtt-schema.md` 위에 더한다. 공통 규칙(1장) · 명령 처리 규칙(3장: `request_id` 중복 · 필수 필드 · 만료) · 단위(mm · quaternion · epoch ms)는 1차와 같다.

## 1. 토픽

| 방향 | 토픽 | QoS | retain | 대응 ROS | 내용 |
|---|---|---|---|---|---|
| 웹 → ROS | `cmd/weld/start` | 1 | false | `/weld/run` goal | 용접 시작 (`scan_id` · `start_line` · `end_line` · `config`) |
| 웹 → ROS | `cmd/weld/stop` | 1 | false | `/weld/stop` | 용접 중지 (**만료 검사 제외**, `cmd/scan/stop` 과 같다) |
| 웹 → ROS | `cmd/weld/home` | 1 | false | `/weld/home` goal | 안전복귀 |
| ROS → 웹 | `weld/state` | 1 | **true** | `/weld/state` | 단계 · 선 번호 · 진행 |
| ROS → 웹 | `weld/result` | 1 | false | `/weld/result` | 용접 결과 (8 선 계획 · 상태) |
| ROS → 웹 | `weld/log` | 1 | false | `/weld/log` | 시간순 로그 |
| ROS → 웹 | `weld/command_result` | 1 | false | Action Result · `STOPPED` 전이 | 명령의 완료 / 실패 (start · stop · home) |
| ROS → 웹 | `cmd/ack` | 1 | false | (1차와 같다) | 접수 / 거절 |

- 구독 필터 추가: mqtt_bridge = `cmd/weld/+`. FastAPI = `weld/#`.
- `robot/sample.operation` 에 문자열 **`"WELD_PATH"`** 가 추가된다(`OP_WELD_PATH=5`). 웹은 이 값이고 `motion_id > 0` 인 샘플의 위치를 이어 비드 궤적으로 그린다.
- `reason` 이름에 6xx 가 추가된다: `SCAN_ACTIVE` · `WELD_ACTIVE` · `NO_SCAN_RESULT` · `LINE_OUT_OF_RANGE` · `PATH_REJECTED`. (1차 이슈 #90: 표에 없는 코드를 조용히 버리지 않게 같이 손본다.)
- 웹 → ROS 필수 필드는 1차 명령과 같다(`schema_version` · `request_id` · `timestamp_ms` · `payload`). **`schema_version` 은 토픽별이다**(원칙): 용접 토픽(`cmd/weld/*` · `weld/*`)은 "0.2", 스캔 토픽은 그대로 "0.1". mqtt_bridge 의 command_guard 는 토픽별 허용 버전으로 검사한다(의석). 3차가 붙어도 같은 방식이다.
- **null 규칙(1차와 다른 점)**: `weld/state.line_index` 와 `weld/result.lines[].stop_pose` 는 `null` 단독이다(1차의 `null` + `*_valid` 쌍이 아니다). 그 밖의 숫자 필드는 1차 규칙 그대로.

## 2. JSON 예시

### cmd/weld/start
```json
{
  "schema_version": "0.2",
  "request_id": "5e2f…",
  "timestamp_ms": 1790000000000,
  "session_id": "web-…",
  "payload": {
    "scan_id": "",              // "" = 가장 최근 성공 스캔
    "start_line": 0,            // 0~7. 없으면 0
    "end_line": 7,              // 0~7, start_line 이상. 없으면 7 (mqtt_bridge 가 채운다). "L0 만" = start 0 · end 0
    "config": {                 // 선택. 있는 키만 *_set=true 로 실린다 (mm · mm/s · deg)
      "weld_speed_mm_s": 10.0,
      "travel_speed_mm_s": 50.0,
      "standoff_mm": 3.0,
      "weave_amplitude_mm": 2.0,
      "weave_pitch_mm": 4.0,
      "tilt_deg": 45.0
    }
  }
}
```

### cmd/weld/stop · cmd/weld/home
`payload` 는 빈 객체. 그 밖은 1차 `cmd/scan/stop` · `cmd/scan/home` 과 같다.

### weld/state (retain)
```json
{
  "schema_version": "0.2",
  "stamp_ms": 1790000001000,
  "weld_id": "20260929-101500-0042",
  "scan_id": "20260929-100200-0017",
  "phase": "WELDING",           // IDLE PREPARING APPROACH WELDING RETREAT DONE ERROR STOPPING STOPPED HOMING
  "line_index": 2,              // null 이면 없음 (LINE_NONE)
  "line_total": 8,
  "lines_done": 2,
  "line_progress": 0.43,
  "motion_id": 9,
  "published_at_ms": 1790000001004
}
```

### weld/result
```json
{
  "schema_version": "0.2",
  "weld_id": "20260929-101500-0042",
  "scan_id": "20260929-100200-0017",
  "stamp_ms": 1790000090000,
  "success": true,
  "reason_code": 0,
  "reason": "OK",
  "detail": "",
  "frame_id": "workpiece_fixture",
  "base_to_fixture_mm": {"x": 420.255, "y": -156.675, "z": 95.006},
  "start_line": 0,
  "end_line": 7,
  "lines": [
    {
      "index": 0,
      "seam": {"start": {"x": -40.5, "y": -42.1, "z": 83.0}, "end": {"x": 41.8, "y": -42.1, "z": 83.0}, "length_mm": 82.3, "valid": true},
      "status": "DONE",         // NOT_ATTEMPTED DONE FAILED STOPPED SKIPPED
      "reason_code": 0, "reason": "OK", "detail": "",
      "stop_pose": null,        // FAILED · STOPPED 일 때만 {position, orientation}
      "started_at_ms": 1790000010000, "finished_at_ms": 1790000019000
    }
    // … index 1~7
  ],
  "config": {"weld_speed_mm_s": 10.0, "travel_speed_mm_s": 50.0, "standoff_mm": 3.0,
             "weave_amplitude_mm": 2.0, "weave_pitch_mm": 4.0, "tilt_deg": 45.0},
  "started_at_ms": 1790000005000,
  "finished_at_ms": 1790000090000,
  "published_at_ms": 1790000090004
}
```
- 좌표는 작업대 좌표 mm(1차 `scan/result` 와 같은 프레임). 비드 궤적(`robot/sample`, Base mm)을 겹쳐 그릴 때 `base_to_fixture_mm` 을 뺀다.

### weld/log
1차 `scan/log` 와 같은 형식. `scan_id` 자리에 `weld_id`, `phase` 는 WeldState 이름, `direction` 은 `"NONE"`.

### weld/command_result
1차 `scan/command_result` 와 같은 형식. `scan_id` 대신 `weld_id`.
- start: 마무리 홈 복귀까지 끝난 시점(`RunWeld` Result). 결과는 그보다 먼저 `weld/result` 로 간다.
- stop: `phase=STOPPED` 전이. home: Action Result.

## 3. 웹 표시 (D9)
- 8 선 표시(`weld/result` 가 오기 전에는 `scan/result.edges[0..3, 8..11]` 로 미리 그린다), 현재 선(`weld/state.line_index`) 강조, 완료 선(`lines_done` 또는 `weld/result.lines[].status`) 색.
- 비드 궤적: `robot/sample` 중 `operation == "WELD_PATH"` 인 샘플의 위치 누적(10 Hz 다운샘플이라 선당 약 80 점).
- 진행률: `lines_done / line_total` 과 `line_progress`.
- 버튼: 용접 시작(scan_id · start_line) · 중지 · 안전복귀. 스캔이 휴지가 아니면 시작을 비활성화(거절 이유 600 이 오면 표시).
