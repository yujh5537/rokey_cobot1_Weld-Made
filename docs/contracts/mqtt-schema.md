# MQTT 토픽·JSON 스키마 계약

상태: **v0.1 동결** (2026-09-18, T01 1차 회의 병후·의석). 변경은 PR + `CHANGELOG.md`로만 한다.
이 문서 한 장이 ROS 쪽(의석, mqtt_bridge. scan_manager 쪽 접점은 병후)과 웹 쪽(의석, FastAPI)의 유일한 접점이다. 의석의 목업 발행기(`backend/mock_publisher`)와 mqtt_bridge 테스트는 **아래 예시를 그대로** 쓴다.

브로커: 웹 PC의 Mosquitto 1개. 주소·포트는 `docker/.env`.

## 1. 공통 규칙

| 항목 | 규칙 |
|---|---|
| 구조 | ROS 메시지(`ros-interfaces.md`)와 **같은 필드 이름 · 같은 구조로 1:1**. 아래 "표기 변환"만 예외 |
| 버전 | 모든 메시지에 `"schema_version": "0.1"` |
| 단위 | 길이 **mm**, 힘 N, 토크 N·m, 속도 mm/s, 시간 s. **단위를 키 이름 끝에 붙인다**(`x_mm` · `fz_n` · `z_drop_mm` · `slide_speed_mmps`). ROS(m)에서 mm로의 변환은 **mqtt_bridge에서만** 한다 |
| 각도 | v0.1 MQTT에는 **각도 값을 싣지 않는다.** 자세는 quaternion 그대로. 화면에 deg가 필요하면 웹이 시각화 단계에서 변환한다 |
| 시각 | **epoch ms 정수(UTC)**. ROS stamp는 `*_stamp_ms` · `*_at_ms`로 각각 보존한다. mqtt_bridge가 발행 시각 `published_at_ms`를 붙인다. 웹이 보내는 메시지의 발신 시각은 `timestamp_ms` |
| enum | **문자열 이름**(접두사 제외): `"EDGE_SEARCH"` · `"POS_X"` · `"EDGE"` · `"STOP"` · `"SLIDE"` |
| 사유 코드 | `reason_code`(숫자)와 `reason`(이름)을 함께 싣는다. 다른 코드 필드도 같다(`error_code`+`error_name`, `code`+`code_name`). `robot/status`의 `error`는 이름이 아니라 ROS `RobotStatus.error`(bool)와 1:1이다 |
| 미측정값 | 값은 **`null`**, 짝이 되는 **`*_valid` 키는 항상 유지**한다(키 생략 금지). 0을 쓰지 않는다. mqtt_bridge는 ROS의 `*_valid=false`(값 NaN)를 `null`로 바꾼다 |
| 식별자 | 명령은 `request_id`(UUID v4, FastAPI 발급), 작업은 `scan_id`. `command_id` · `job_id`라는 이름은 쓰지 않는다 |
| 와일드카드 | 발행에 와일드카드를 쓰지 않는다 |

**표기 변환** (ROS 타입 → JSON)

| ROS | JSON |
|---|---|
| `geometry_msgs/Pose` | `{"x_mm","y_mm","z_mm","qx","qy","qz","qw"}` |
| `geometry_msgs/Point` | `{"x_mm","y_mm","z_mm"}` |
| `geometry_msgs/Wrench` | `{"fx_n","fy_n","fz_n","tx_nm","ty_nm","tz_nm"}` |
| `builtin_interfaces/Time` 필드 `foo_stamp` / `foo_at` / `stamp` | `foo_stamp_ms` / `foo_at_ms` / `stamp_ms` |
| `ScanConfig`의 `*_set` | 웹 → ROS: 보낸 키만 `*_set=true`로 적용. ROS → 웹: 전체 값을 싣고 `*_set`은 생략. **scan_manager가 아직 모르는 값(`*_set=false`)은 `null`** — scan_manager가 NaN으로 두고 mqtt_bridge가 `null`로 바꾼다(0을 넣지 않는다. `ros-interfaces.md` 1장 무효 값) |

## 2. 토픽 · QoS · retain

| 방향 | 토픽 | QoS | retain | 대응 ROS | 내용 |
|---|---|---|---|---|---|
| 웹 → ROS | `cmd/scan/start` | 1 | false | `/scan/run` goal | 작업 시작 |
| 웹 → ROS | `cmd/scan/stop` | 1 | false | `/scan/stop` | 작업 중지 |
| 웹 → ROS | `cmd/scan/home` | 1 | false | `/scan/home` goal | 안전복귀 |
| 웹 → ROS | `cmd/scan/resume` | 1 | false | `/scan/resume` goal | 재시작 |
| 웹 → ROS | `cmd/scan/set_config` | 1 | false | `/scan/set_config` | 설정 등록 |
| 웹 → ROS | `cmd/safety/reset` | 1 | false | `/safety/reset` | 안전 래치 해제 |
| 웹 → ROS | `hb/web` | 0 | false | `/web/heartbeat` | 웹 생존 신호. 1 Hz 설계 목표 |
| 웹 → ROS | `conn/web` | 1 | **true** | — | 웹 연결 상태(LWT) |
| ROS → 웹 | `cmd/ack` | 1 | false | goal 수락/거절 · Service 응답 | **접수/거절.** 완료가 아니다 |
| ROS → 웹 | `scan/command_result` | 1 | false | Action Result · `STOPPED` 전이 | 명령의 **완료/실패** (start · stop · home · resume) |
| ROS → 웹 | `robot/sample` | 0 | false | `/robot/sample` | TCP · 힘. 10 Hz 다운샘플(설계 목표) |
| ROS → 웹 | `robot/status` | 1 | **true** | `/robot/status` | 연결 · 동작 · 오류 |
| ROS → 웹 | `scan/state` | 1 | **true** | `/scan/state` | 단계 · 방향 · 진행 n/4 |
| ROS → 웹 | `scan/result` | 1 | false | `/scan/result` | 형상 결과 |
| ROS → 웹 | `scan/log` | 1 | false | `/scan/log` | 시간순 로그 |
| ROS → 웹 | `contact/event` | 1 | false | `/contact/event` | 접촉 · 엣지 · 과대 외력 |
| ROS → 웹 | `safety/status` | 1 | **true** | `/safety/status` | 안전 상태 · 래치 |
| ROS → 웹 | `hb/ros` | 0 | false | — | 메인 PC 생존 신호. 1 Hz |
| ROS → 웹 | `conn/ros` | 1 | **true** | — | mqtt_bridge 연결 상태(LWT) |

- **명령은 전부 retain=false.** retain=true는 상태 3종(`robot/status` · `scan/state` · `safety/status`)과 `conn/*`뿐이다. 웹은 retain으로 받은 상태의 `stamp_ms`를 보고 오래된 값을 배제한다.
- 구독 필터: FastAPI = `robot/#` · `scan/#` · `contact/#` · `safety/#` · `cmd/ack` · `hb/ros` · `conn/ros`. mqtt_bridge = `cmd/scan/+` · `cmd/safety/reset` · `hb/web` · `conn/web`.
- mqtt_bridge 파라미터 `topic_prefix`(기본 `""`)로 전체 토픽 앞에 접두사를 붙일 수 있다. **웹(FastAPI · 목업 발행기)은 기본값, 즉 접두사 없는 토픽을 전제로 한다.** 접두사를 쓰려면 웹 쪽 설정도 같이 바꾼다.
- 검토안(MVP 밖): `cmd/scan/calibrate` · `scan/calibration/result`.

## 3. 명령 처리 규칙

1. 웹이 명령을 발행한다. `request_id`는 FastAPI가 발급한다.
2. mqtt_bridge가 검사한다.
   - 같은 `request_id`를 다시 받으면 → `cmd/ack` `accepted=false`, `DUPLICATE_REQUEST(106)`. 최근 N개를 기억한다(파라미터 `dedup_cache_size`, 출발값 100).
   - 필수 필드가 없으면 → `INVALID_REQUEST(101)`. 필수 필드는 아래 표.
   - `timestamp_ms`가 `cmd_expiry_s`(출발값 5)보다 오래됐으면 → `INVALID_REQUEST(101)`. **`cmd/scan/stop`은 만료 검사에서 제외한다**(중복 검사와 필수 필드 검사는 한다). 중지는 멱등이라 늦게 도착해도 결과가 정지뿐이고, 두 PC의 시계가 `cmd_expiry_s` 이상 어긋나 있어도(chrony 적용 전 포함) 중지가 거절되면 안 된다. `cmd/scan/home`(로봇을 움직임)과 `cmd/safety/reset`(래치를 풂)을 포함한 나머지 명령은 만료 검사를 한다.

   | 메시지 | 필수 | 선택 |
   |---|---|---|
   | 명령 6종(`cmd/scan/*` · `cmd/safety/reset`) | `schema_version` · `request_id` · `timestamp_ms` · `payload`(빈 객체 가능) | `session_id`(로그 · 추적용. 없어도 거절하지 않는다) · `cmd/scan/resume`의 `scan_id`(없으면 `""`과 같다) |
   | `hb/web` | `schema_version` · `session_id` · `seq` · `timestamp_ms` | — |
   | `conn/web` | `schema_version` · `connected` · `timestamp_ms` | — |

3. 통과하면 ROS Action goal / Service를 호출하고, 수락/거절을 `cmd/ack`로 돌려준다. **접수는 완료가 아니다.**
4. 완료/실패는 `scan/command_result`로 한 번 보낸다(`request_id`로 짝을 맞춘다).
   - start: 마무리 홈 복귀까지 끝난 시점(`RunScan` Result). 형상 데이터는 그보다 먼저 `scan/result`로 간다.
   - stop: `phase=STOPPED` 전이. home · resume: Action Result.
   - `set_config` · `safety/reset`은 Service라 즉시 끝나므로 `cmd/ack`가 곧 결과다(`command_result` 없음).
5. FastAPI는 `cmd/ack`를 제한 시간 안에 못 받으면 "미확정"으로 표시한다.
6. MQTT 전달 확인은 PostgreSQL 커밋 완료가 아니다. 저장 성공은 커밋 후에만 표시한다.

heartbeat: mqtt_bridge는 `hb/web`을 **실제로 받았을 때만** `/web/heartbeat`를 발행한다. 만료 판정은 웹 시각이 아니라 mqtt_bridge 수신 시각 기준이다. 웹 PC ↔ 메인 PC 시계 동기(chrony)는 의석이 별도 PR로 진행한다.

## 4. JSON 예시

값은 예시다. 상자 100 × 60 × 50 mm 기준.

### 4.1 웹 → ROS

#### cmd/scan/start
```json
{
  "schema_version": "0.1",
  "request_id": "3f2b8c1e-6a4d-4e0b-9a53-1c7d2f0e9b11",
  "session_id": "b7a1d2c4-0f3e-4a5b-8c6d-9e0f1a2b3c4d",
  "timestamp_ms": 1789720000123,
  "payload": {}
}
```
`payload.config_override`에 4.1의 set_config와 같은 키를 넣으면 이번 작업에만 적용한다(선택).

#### cmd/scan/stop
```json
{
  "schema_version": "0.1",
  "request_id": "0a1b2c3d-1111-4222-8333-444455556666",
  "session_id": "b7a1d2c4-0f3e-4a5b-8c6d-9e0f1a2b3c4d",
  "timestamp_ms": 1789720030000,
  "payload": { "detail": "operator stop" }
}
```

#### cmd/scan/home
```json
{
  "schema_version": "0.1",
  "request_id": "1b2c3d4e-2222-4333-8444-555566667777",
  "session_id": "b7a1d2c4-0f3e-4a5b-8c6d-9e0f1a2b3c4d",
  "timestamp_ms": 1789720040000,
  "payload": {}
}
```

#### cmd/scan/resume
```json
{
  "schema_version": "0.1",
  "request_id": "2c3d4e5f-3333-4444-8555-666677778888",
  "session_id": "b7a1d2c4-0f3e-4a5b-8c6d-9e0f1a2b3c4d",
  "timestamp_ms": 1789720050000,
  "scan_id": "20260918-172640-4821",
  "payload": {}
}
```
`scan_id`가 `""`이면 가장 최근 중단 작업이다.

#### cmd/scan/set_config
```json
{
  "schema_version": "0.1",
  "request_id": "3d4e5f60-4444-4555-8666-777788889999",
  "session_id": "b7a1d2c4-0f3e-4a5b-8c6d-9e0f1a2b3c4d",
  "timestamp_ms": 1789719990000,
  "payload": {
    "contact_threshold_n": 4.0,
    "slide_speed_mmps": 10.0
  }
}
```
보낸 키만 적용된다. 쓸 수 있는 키는 4.2의 `cmd/ack` `applied`와 같다.

#### cmd/safety/reset
```json
{
  "schema_version": "0.1",
  "request_id": "4e5f6071-5555-4666-8777-88889999aaaa",
  "session_id": "b7a1d2c4-0f3e-4a5b-8c6d-9e0f1a2b3c4d",
  "timestamp_ms": 1789720100000,
  "payload": { "detail": "원인 확인: 부재 오배치" }
}
```

#### hb/web
```json
{
  "schema_version": "0.1",
  "session_id": "b7a1d2c4-0f3e-4a5b-8c6d-9e0f1a2b3c4d",
  "seq": 1042,
  "timestamp_ms": 1789720002000
}
```

#### conn/web
```json
{ "schema_version": "0.1", "connected": true, "timestamp_ms": 1789719900000 }
```
LWT는 같은 구조에 `"connected": false`.

### 4.2 ROS → 웹

#### cmd/ack (거절 예)
```json
{
  "schema_version": "0.1",
  "request_id": "3f2b8c1e-6a4d-4e0b-9a53-1c7d2f0e9b11",
  "accepted": false,
  "reason_code": 103,
  "reason": "SAFETY_LATCHED",
  "detail": "",
  "published_at_ms": 1789720000150
}
```

#### cmd/ack (set_config 수락 예 — `applied`에 적용 후 전체 값)
```json
{
  "schema_version": "0.1",
  "request_id": "3d4e5f60-4444-4555-8666-777788889999",
  "accepted": true,
  "reason_code": 0,
  "reason": "OK",
  "detail": "",
  "applied": {
    "contact_threshold_n": 4.0,
    "edge_drop_mm": 0.5,
    "debounce_n": 3,
    "over_force_n": 30.0,
    "descend_speed_mmps": 5.0,
    "slide_speed_mmps": 10.0,
    "max_descend_mm": 80.0,
    "max_slide_mm": 150.0,
    "motion_timeout_s": 30.0,
    "lift_height_mm": 50.0,
    "target_force_n": 5.0,
    "drop_limit_mm": 5.0
  },
  "published_at_ms": 1789719990040
}
```

#### scan/command_result
```json
{
  "schema_version": "0.1",
  "request_id": "0a1b2c3d-1111-4222-8333-444455556666",
  "scan_id": "20260918-172640-4821",
  "success": true,
  "reason_code": 200,
  "reason": "STOP_REQUESTED",
  "detail": "",
  "published_at_ms": 1789720030410
}
```

#### robot/sample
```json
{
  "schema_version": "0.1",
  "sample_id": 48211,
  "frame_id": "base_link",
  "pose": { "x_mm": 412.35, "y_mm": -20.10, "z_mm": 85.02, "qx": 0.0, "qy": 1.0, "qz": 0.0, "qw": 0.0 },
  "pose_stamp_ms": 1789720001020,
  "wrench": { "fx_n": 0.4, "fy_n": -0.2, "fz_n": -3.9, "tx_nm": 0.01, "ty_nm": 0.0, "tz_nm": 0.0 },
  "force_stamp_ms": 1789720001024,
  "valid": true,
  "motion_id": 7,
  "operation": "SLIDE",
  "published_at_ms": 1789720001030
}
```

#### robot/status
```json
{
  "schema_version": "0.1",
  "stamp_ms": 1789720001000,
  "connected": true,
  "moving": true,
  "error": false,
  "error_code": 0,
  "error_name": "OK",
  "compliance_active": true,
  "force_ctrl_active": true,
  "motion_id": 7,
  "operation": "SLIDE",
  "slide_mode": "force",
  "slide_force_setpoint_n": 3.0,
  "slide_force_baseline_n": 5.3,
  "slide_force_estimate_n": 8.3,
  "step_press_lo_n": null,
  "step_press_hi_n": null,
  "detail": "",
  "published_at_ms": 1789720001003
}
```
**SLIDE 누름 목표 6개 [ROS 계약 v0.1.16, 3.2절].** 서로 다른 세 값을 한 자리에 섞지 않는다.

| 필드 | 뜻 | 화면에 쓸 때 |
|---|---|---|
| `slide_mode` | `"force"`(순응 · 힘 제어, REL) / `"step"`(위치 제어 스텝) / `""`(모름) | 지금 어느 방식인지 먼저 보여 준다 |
| `slide_force_setpoint_n` | **설정한 증분 힘**(`DR_FC_MOD_REL`) | "설정" 이라고 쓴다. 실제 누름이 아니다 |
| `slide_force_baseline_n` | 이번 SLIDE 를 **시작한 시점의 기준 Fz** | "시작 기준" |
| `slide_force_estimate_n` | 위 둘의 합 = **추정 최종 누름** | **"추정"이라고 반드시 표시한다.** 실측으로 쓰면 안 된다 |
| `step_press_lo_n` · `step_press_hi_n` | `step` 모드의 **목표 누름 ΔFz 띠** | `step` 모드에서 이 띠를 보여 준다 |

- **`step` 모드에서는 힘 세 값이 `null` 이다.** 스텝 모드는 REL 힘 제어를 켜지 않으므로 그 값들은 제어 목표가 아니다. `null` 을 0 으로 그리지 않는다(2장의 무효 값 규칙).
- 반대로 `force` 모드에서는 `step_press_*` 가 `null` 이다.
- 모르는 값(SLIDE 중이 아님 · 기준 Fz 미수신)도 `null` 이다.

#### scan/state
```json
{
  "schema_version": "0.1",
  "stamp_ms": 1789720001000,
  "scan_id": "20260918-172640-4821",
  "phase": "EDGE_SEARCH",
  "direction": "POS_X",
  "progress": 0,
  "progress_total": 4,
  "motion_id": 7,
  "published_at_ms": 1789720001004
}
```

#### contact/event
```json
{
  "schema_version": "0.1",
  "event_id": 12,
  "scan_id": "20260918-172640-4821",
  "motion_id": 7,
  "sample_id": 48230,
  "type": "EDGE",
  "source": "robot_force",
  "frame_id": "base_link",
  "pose": { "x_mm": 461.80, "y_mm": -20.11, "z_mm": 84.41, "qx": 0.0, "qy": 1.0, "qz": 0.0, "qw": 0.0 },
  "wrench": { "fx_n": 0.3, "fy_n": -0.1, "fz_n": -1.1, "tx_nm": 0.0, "ty_nm": 0.0, "tz_nm": 0.0 },
  "pose_stamp_ms": 1789720002400,
  "force_stamp_ms": 1789720002404,
  "detect_stamp_ms": 1789720002431,
  "force_delta_n": 1.2,
  "z_drop_mm": 0.61,
  "z_drop_valid": true,
  "debounce_count": 3,
  "published_at_ms": 1789720002436
}
```
`type`이 `CONTACT` · `OVER_FORCE`이면 `"z_drop_mm": null, "z_drop_valid": false`.
`pose` · `wrench` · `pose_stamp_ms` · `force_stamp_ms` · `sample_id` · `z_drop_mm`는 **판정 샘플**(조건이 처음 성립한 샘플, 연속 구간의 첫 샘플)의 값이고, `force_delta_n` · `detect_stamp_ms`는 **확정 샘플**(연속 N번째)의 값이다. `detect_stamp_ms − force_stamp_ms`가 디바운스 지연이다(`ros-interfaces.md` 3.3절).

#### scan/result (성공)
꼭짓점 · 엣지 순서는 `ros-interfaces.md` 3.5절 규약을 따른다.
```json
{
  "schema_version": "0.1",
  "scan_id": "20260918-172640-4821",
  "stamp_ms": 1789720061200,
  "success": true,
  "reason_code": 0,
  "reason": "OK",
  "detail": "",
  "frame_id": "workpiece_fixture",
  "z_top_mm": 50.0, "z_top_valid": true,
  "x_pos_mm": 100.0, "x_pos_valid": true,
  "x_neg_mm": 0.0, "x_neg_valid": true,
  "y_pos_mm": 60.0, "y_pos_valid": true,
  "y_neg_mm": 0.0, "y_neg_valid": true,
  "width_mm": 100.0, "length_mm": 60.0, "height_mm": 50.0, "dims_valid": true,
  "support_z_mm": 0.0, "support_z_valid": true,
  "vertices": [
    { "x_mm": 0.0, "y_mm": 0.0, "z_mm": 50.0 },
    { "x_mm": 100.0, "y_mm": 0.0, "z_mm": 50.0 },
    { "x_mm": 100.0, "y_mm": 60.0, "z_mm": 50.0 },
    { "x_mm": 0.0, "y_mm": 60.0, "z_mm": 50.0 },
    { "x_mm": 0.0, "y_mm": 0.0, "z_mm": 0.0 },
    { "x_mm": 100.0, "y_mm": 0.0, "z_mm": 0.0 },
    { "x_mm": 100.0, "y_mm": 60.0, "z_mm": 0.0 },
    { "x_mm": 0.0, "y_mm": 60.0, "z_mm": 0.0 }
  ],
  "box_valid": true,
  "edges": [
    { "start": { "x_mm": 0.0, "y_mm": 0.0, "z_mm": 50.0 }, "end": { "x_mm": 100.0, "y_mm": 0.0, "z_mm": 50.0 }, "length_mm": 100.0, "valid": true },
    { "start": { "x_mm": 100.0, "y_mm": 0.0, "z_mm": 50.0 }, "end": { "x_mm": 100.0, "y_mm": 60.0, "z_mm": 50.0 }, "length_mm": 60.0, "valid": true },
    { "start": { "x_mm": 100.0, "y_mm": 60.0, "z_mm": 50.0 }, "end": { "x_mm": 0.0, "y_mm": 60.0, "z_mm": 50.0 }, "length_mm": 100.0, "valid": true },
    { "start": { "x_mm": 0.0, "y_mm": 60.0, "z_mm": 50.0 }, "end": { "x_mm": 0.0, "y_mm": 0.0, "z_mm": 50.0 }, "length_mm": 60.0, "valid": true },
    { "start": { "x_mm": 0.0, "y_mm": 0.0, "z_mm": 0.0 }, "end": { "x_mm": 100.0, "y_mm": 0.0, "z_mm": 0.0 }, "length_mm": 100.0, "valid": true },
    { "start": { "x_mm": 100.0, "y_mm": 0.0, "z_mm": 0.0 }, "end": { "x_mm": 100.0, "y_mm": 60.0, "z_mm": 0.0 }, "length_mm": 60.0, "valid": true },
    { "start": { "x_mm": 100.0, "y_mm": 60.0, "z_mm": 0.0 }, "end": { "x_mm": 0.0, "y_mm": 60.0, "z_mm": 0.0 }, "length_mm": 100.0, "valid": true },
    { "start": { "x_mm": 0.0, "y_mm": 60.0, "z_mm": 0.0 }, "end": { "x_mm": 0.0, "y_mm": 0.0, "z_mm": 0.0 }, "length_mm": 60.0, "valid": true },
    { "start": { "x_mm": 0.0, "y_mm": 0.0, "z_mm": 50.0 }, "end": { "x_mm": 0.0, "y_mm": 0.0, "z_mm": 0.0 }, "length_mm": 50.0, "valid": true },
    { "start": { "x_mm": 100.0, "y_mm": 0.0, "z_mm": 50.0 }, "end": { "x_mm": 100.0, "y_mm": 0.0, "z_mm": 0.0 }, "length_mm": 50.0, "valid": true },
    { "start": { "x_mm": 100.0, "y_mm": 60.0, "z_mm": 50.0 }, "end": { "x_mm": 100.0, "y_mm": 60.0, "z_mm": 0.0 }, "length_mm": 50.0, "valid": true },
    { "start": { "x_mm": 0.0, "y_mm": 60.0, "z_mm": 50.0 }, "end": { "x_mm": 0.0, "y_mm": 60.0, "z_mm": 0.0 }, "length_mm": 50.0, "valid": true }
  ],
  "path_candidates": [
    { "start": { "x_mm": 0.0, "y_mm": 0.0, "z_mm": 50.0 }, "end": { "x_mm": 100.0, "y_mm": 0.0, "z_mm": 50.0 }, "length_mm": 100.0, "valid": true },
    { "start": { "x_mm": 100.0, "y_mm": 0.0, "z_mm": 50.0 }, "end": { "x_mm": 100.0, "y_mm": 60.0, "z_mm": 50.0 }, "length_mm": 60.0, "valid": true },
    { "start": { "x_mm": 100.0, "y_mm": 60.0, "z_mm": 50.0 }, "end": { "x_mm": 0.0, "y_mm": 60.0, "z_mm": 50.0 }, "length_mm": 100.0, "valid": true },
    { "start": { "x_mm": 0.0, "y_mm": 60.0, "z_mm": 50.0 }, "end": { "x_mm": 0.0, "y_mm": 0.0, "z_mm": 50.0 }, "length_mm": 60.0, "valid": true }
  ],
  "config": {
    "contact_threshold_n": 4.0,
    "edge_drop_mm": 0.5,
    "debounce_n": 3,
    "over_force_n": 30.0,
    "descend_speed_mmps": 5.0,
    "slide_speed_mmps": 10.0,
    "max_descend_mm": 80.0,
    "max_slide_mm": 150.0,
    "motion_timeout_s": 30.0,
    "lift_height_mm": 50.0,
    "target_force_n": 5.0,
    "drop_limit_mm": 5.0
  },
  "started_at_ms": 1789720000200,
  "finished_at_ms": 1789720061200,
  "published_at_ms": 1789720061210
}
```

#### scan/result (실패 · 중단 — 확보한 값만 유효)
구조는 위와 같다. 미측정 항목은 `null` + `*_valid=false`이고, 배열은 통째로 `null`이다.
```json
{
  "schema_version": "0.1",
  "scan_id": "20260918-172640-4821",
  "stamp_ms": 1789720041200,
  "success": false,
  "reason_code": 301,
  "reason": "NO_EDGE",
  "detail": "direction=NEG_X",
  "frame_id": "workpiece_fixture",
  "z_top_mm": 50.0, "z_top_valid": true,
  "x_pos_mm": 100.0, "x_pos_valid": true,
  "x_neg_mm": null, "x_neg_valid": false,
  "y_pos_mm": null, "y_pos_valid": false,
  "y_neg_mm": null, "y_neg_valid": false,
  "width_mm": null, "length_mm": null, "height_mm": null, "dims_valid": false,
  "support_z_mm": 0.0, "support_z_valid": true,
  "vertices": null,
  "box_valid": false,
  "edges": null,
  "path_candidates": null,
  "config": {
    "contact_threshold_n": 4.0,
    "edge_drop_mm": 0.5,
    "debounce_n": 3,
    "over_force_n": 30.0,
    "descend_speed_mmps": 5.0,
    "slide_speed_mmps": 10.0,
    "max_descend_mm": 80.0,
    "max_slide_mm": 150.0,
    "motion_timeout_s": 30.0,
    "lift_height_mm": 50.0,
    "target_force_n": 5.0,
    "drop_limit_mm": 5.0
  },
  "started_at_ms": 1789720000200,
  "finished_at_ms": 1789720041200,
  "published_at_ms": 1789720041210
}
```

#### scan/log
```json
{
  "schema_version": "0.1",
  "stamp_ms": 1789720002440,
  "scan_id": "20260918-172640-4821",
  "level": "INFO",
  "phase": "EDGE_SEARCH",
  "direction": "POS_X",
  "motion_id": 7,
  "code": 0,
  "code_name": "OK",
  "message": "edge +x 판정 좌표 기록",
  "frame_id": "base_link",
  "pose": { "x_mm": 461.80, "y_mm": -20.11, "z_mm": 84.41, "qx": 0.0, "qy": 1.0, "qz": 0.0, "qw": 0.0 },
  "pose_valid": true,
  "published_at_ms": 1789720002445
}
```

#### safety/status
```json
{
  "schema_version": "0.1",
  "stamp_ms": 1789720002500,
  "level": "STOP",
  "reason_code": 400,
  "reason": "OVER_FORCE",
  "stop_required": true,
  "stop_confirmed": false,
  "latched": true,
  "motion_id": 7,
  "position": { "x_mm": 430.12, "y_mm": -20.10, "z_mm": 84.98 },
  "position_valid": true,
  "detail": "force 32.1 N > 30 N",
  "published_at_ms": 1789720002503
}
```

#### hb/ros
```json
{ "schema_version": "0.1", "seq": 5120, "published_at_ms": 1789720002000 }
```

#### conn/ros
```json
{ "schema_version": "0.1", "connected": true, "published_at_ms": 1789719800000 }
```
LWT는 같은 구조에 `"connected": false`(브로커가 대신 발행하므로 `published_at_ms`는 접속 시각이다).

## 5. TBD
- 예시의 설정값(속도 · 힘 · 거리)은 전부 자리 표시다. 실제 값은 yaml 파라미터와 실측으로 정한다.
- FastAPI의 `cmd/ack` 대기 제한 시간, WebSocket 메시지 형식, PostgreSQL ERD/DDL(웹 쪽 문서에서 정한다).
- heartbeat 만료 시 조치 · 브라우저 단절 정책(BRD 6장).
- `hb/ros` · `conn/ros`의 **만료 판정 기준 필드**. 두 메시지에는 `stamp_ms`가 없고 `published_at_ms`만 있다. 발신 측 `published_at_ms`로 볼지 수신 측이 받은 시각으로 볼지 정해야 한다. `conn/ros`의 LWT는 브로커가 대신 발행해 `published_at_ms`가 *접속 시각*이므로 만료 판정에 그대로 쓸 수 없다. `hb/web`은 mqtt_bridge 수신 시각 기준으로 이미 정해져 있다(3장).
- retain으로 받은 상태(`robot/status` · `scan/state` · `safety/status`)를 "오래된 값"으로 보는 **기준 시간**(2장). 웹 TBD와 같이 정한다.
