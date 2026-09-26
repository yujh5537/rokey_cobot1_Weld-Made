# P4 mqtt_bridge `weld/*` 중계

**세션 이름: P4 bridge weld 중계**
담당: 의석(D20) · 권장 기한: 9/28 (순서: 브리지 표 PR → P3 목업 발행기 → P4 → P3 본체) · 공통 절차: `_common.md`

## 이 task
웹의 용접 명령을 ROS 액션 · 서비스로, weld_manager 의 상태 · 결과 · 로그를 MQTT 로 옮긴다(1차 스캔 중계와 같은 구조). scan_manager 쪽 배타 거절(601)은 P5(병후).

## 계약 (확정)
- `docs/phase2/weld-mqtt-schema.md` 1 · 2장. `docs/phase2/weld-ros-interfaces.md` 2장(연결 표) · 5.1(RunWeld) · 4.1(StopWeld).
- 1차 `docs/contracts/mqtt-schema.md` 3장(명령 처리 규칙)은 그대로 적용. `cmd/weld/stop` 은 만료 검사 제외.

## 먼저 떼어 낼 작은 PR (P1 앞, README 머지 순서 0)
`ROBOT_OPERATION_NAMES[5] = "WELD_PATH"`, 표에 없는 코드 · 이름은 버리지 말고 `UNKNOWN_<n>`(#90), 1차 `docs/contracts/mqtt-schema.md` 1장에 그 규칙 한 줄(의석이 코드오너). 이것이 없으면 P1 이 `operation=5` 를 싣는 순간 main 의 mqtt_bridge 가 `robot/sample` 을 통째로 버린다.

## 초기 설계
- `mqtt_bridge/encoders.py`: `WELD_PHASE_NAMES` · `WELD_LINE_STATUS_NAMES`, `encode_weld_state/result/line/config`, `ROBOT_OPERATION_NAMES[5] = "WELD_PATH"`, `REASON_NAMES` 에 6xx 5 개. 표에 없는 코드는 버리지 말고 `"UNKNOWN_<n>"` 으로(#90).
- `decoders.py`: `cmd/weld/start` payload(`scan_id` · `start_line` · `config` mm→m, `*_set`).
- `command_guard.py`: `cmd/weld/+` 필수 필드 · 만료 예외 목록에 `cmd/weld/stop` · **토픽별 `schema_version`**(용접 "0.2", 스캔 "0.1").
- FastAPI: retain 상태 4 종(`robot/status` · `scan/state` · `safety/status` · `weld/state`)의 마지막 값 스냅샷 캐시(브라우저 새로고침 대비. 의석이 P3 앞에 먼저). 계약 변경 없음.
- `mqtt_bridge.py`: 구독 `cmd/weld/+`, 클라이언트 `/weld/run` · `/weld/home`(action) · `/weld/stop`(service), 구독 `/weld/state` · `/weld/result` · `/weld/log`, 발행 `weld/state(retain)` · `weld/result` · `weld/log` · `weld/command_result`.

## 테스트
- 이 PC 에는 paho 가 없다(`local-env-gaps`). 1차 mqtt_bridge 테스트 방식(가짜 MQTT 클라이언트)을 그대로 쓴다.
- Virtual 종단은 P2 · P3 머지 뒤 9/29 전 저녁에 한 번(브로커가 있는 PC 에서).
