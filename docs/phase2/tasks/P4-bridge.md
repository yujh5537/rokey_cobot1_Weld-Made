# P4 mqtt_bridge `weld/*` 중계

**세션 이름: P4 bridge weld 중계**
담당: 의석(D20) · 기한: 9/27 (P3 웹과 같은 사람이므로 P3 목업 발행기 뒤에) · 공통 절차: `_common.md`

## 이 task
웹의 용접 명령을 ROS 액션 · 서비스로, weld_manager 의 상태 · 결과 · 로그를 MQTT 로 옮긴다(1차 스캔 중계와 같은 구조). scan_manager 쪽 배타 거절(601)은 P5(병후).

## 계약 (확정)
- `docs/phase2/weld-mqtt-schema.md` 1 · 2장. `docs/phase2/weld-ros-interfaces.md` 2장(연결 표) · 5.1(RunWeld) · 4.1(StopWeld).
- 1차 `docs/contracts/mqtt-schema.md` 3장(명령 처리 규칙)은 그대로 적용. `cmd/weld/stop` 은 만료 검사 제외.

## 초기 설계
- `mqtt_bridge/encoders.py`: `WELD_PHASE_NAMES` · `WELD_LINE_STATUS_NAMES`, `encode_weld_state/result/line/config`, `ROBOT_OPERATION_NAMES[5] = "WELD_PATH"`, `REASON_NAMES` 에 6xx 5 개. 표에 없는 코드는 버리지 말고 `"UNKNOWN_<n>"` 으로(#90).
- `decoders.py`: `cmd/weld/start` payload(`scan_id` · `start_line` · `config` mm→m, `*_set`).
- `command_guard.py`: `cmd/weld/+` 필수 필드 · 만료 예외 목록에 `cmd/weld/stop`.
- `mqtt_bridge.py`: 구독 `cmd/weld/+`, 클라이언트 `/weld/run` · `/weld/home`(action) · `/weld/stop`(service), 구독 `/weld/state` · `/weld/result` · `/weld/log`, 발행 `weld/state(retain)` · `weld/result` · `weld/log` · `weld/command_result`.

## 테스트
- 이 PC 에는 paho 가 없다(`local-env-gaps`). 1차 mqtt_bridge 테스트 방식(가짜 MQTT 클라이언트)을 그대로 쓴다.
- Virtual 종단은 P2 · P3 머지 뒤 9/29 전 저녁에 한 번(브로커가 있는 PC 에서).
