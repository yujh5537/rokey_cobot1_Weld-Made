# 계약 변경 이력

형식: `버전 (날짜, PR) - 무엇을 왜. 영향받는 모듈`

## v0.1.2 (2026-09-19, T02, PR #TBD)
타입 변경 없음. `units-frames.md`의 좌표 값 중 **툴 무게 · 무게중심**, **탐침 TCP 오프셋(최하단점)**, **팁 반지름**을 실측해 적었다. 근거는 `docs/env/tool-tcp-register.md`. 영향: robot_manager(T13) · contact_detector(T07, T16) · 모서리 편향 보정(r 사용) · 임계값 튜닝(T24).
- 툴: 1.3 kg, 무게중심 (0, 31.08, 29.84) mm. 펜던트에 있던 값이다
- TCP(최하단점): [-1.30, 3.71, 250.21] mm. 피벗 보정 14자세로 구 중심 [-1.30, 3.71, 249.76]을 구하고 r을 더했다. 불확도는 약 ±1 mm다
- 팁 반지름 r: 0.45 mm. 탐침이 인공눈물 용기로 바뀌어 설계 출발값 3 mm를 대체한다
- 새로 적은 사실: ROS로 등록한 툴 · TCP는 `sodreal`을 다시 켜면 지워진다. 툴이 없을 때 무접촉 외력은 11~12.5 N, 등록 뒤에는 2.1~2.9 N(최대 3.7 N)이었다. robot_manager가 시작할 때와 탐색 전에 현재 툴 · TCP를 확인해야 한다
- 실측값은 코드 상수가 아니라 `real.yaml` 파라미터로 둔다고 상태 줄에 적었다

## v0.1.1 (2026-09-18, T09, PR #49)
타입 변경 없음(msg/srv/action은 v0.1 그대로). `ros-interfaces.md` 6.3절의 TBD였던 **QoS 프로파일 정의 위치**를 확정했다. 영향: Topic을 발행 · 구독하는 자체 노드 5개.
- 위치: `contact_scan_interfaces` 패키지가 설치하는 Python 모듈 `contact_scan_qos`. 사용: `from contact_scan_qos import QOS_SENSOR`(`QOS_STATE` · `QOS_EVENT` · `QOS_LOG` · `QOS_HEARTBEAT`). 의존 선언은 `contact_scan_interfaces` 하나로 충분하다
- 이유: rosidl 생성기가 `contact_scan_interfaces`라는 Python 패키지를 이미 설치해 같은 이름으로는 설치할 수 없다(빌드로 확인). 별도 패키지는 의존 선언이 늘고 새 이슈가 필요해 택하지 않았다
- 값은 6.3절 표 그대로이며 모듈에 고정한다(yaml 파라미터 아님)
- 9장 TBD에서 "QoS 프로파일 정의 위치(T09)"를 지웠다

## v0.1 (2026-09-18, 동결 회의 T01, PR #47)
최초 동결. 팀 합의 문서인 인터페이스 정의서 통합본 v1.1(BRD v3.1.0 기준)을 계약으로 채택하고, T01 1차(병후·의석) · 2차(전원) 회의 결정을 덧붙였다. 영향: 전 모듈.

**v0.0 초안에서 바뀐 이름**
- `command_id` → `request_id`, `job_id` → `scan_id`
- MQTT 토픽 `cobot/cmd/start` 류 → `cmd/scan/start` 류(19개). `set_config` · `safety/reset` · `robot/status` · `safety/status` · `hb/*` · `conn/*` 추가
- `RobotSample`: `float64[6]` → `geometry_msgs/Pose` · `Wrench`, `tcp_stamp` → `pose_stamp`
- `/robot/sample` 구독자에서 scan_manager 제외(중단 위치는 `ExecuteMotion.Result.pose`)
- 재시작 = 별도 Action `/scan/resume`, 안전 래치 해제 = Service `/safety/reset` 신설

**정의서 v1.1과 달라진 곳 (2차 회의)** — 정의서 v1.2에 반영 요청
1. `RobotSample` · `RobotStatus`에 `motion_id` · `operation` 추가. robot_manager가 실행 중인 goal의 값을 직접 찍는다. contact_detector는 판정 모드를 `operation`에서 얻고 `motion_id`를 샘플에서 복사한다. 이유: `EDGE_SEARCH` 안에 밀기와 복귀 이동이 섞여 있어 phase로는 판정을 끌 수 없고, `/scan/state` 경유 태깅은 goal 직후 이벤트가 불일치로 무시될 수 있다. 영향: robot_manager · contact_detector · safety_monitor
2. `OP_*` 번호 변경: `NONE=0 · MOVE_TO=1 · DESCEND=2 · SLIDE=3 · HOME=4`. `OP_MOVE_TO` · `OP_HOME` 중에는 CONTACT/EDGE 이벤트로 정지하지 않는다
3. `RobotStatus.compliance_active`를 `compliance_active` · `force_ctrl_active`로 분리
4. `OP_HOME`을 스캔 정상 완료 뒤의 마무리 복귀에도 쓴다. 순서: GEOMETRY(계산 · 저장 · 결과 발행) → HOMING → DONE. `finished_at`은 GEOMETRY 종료 시각. 실패 · 중단 · 형상 계산 실패 시에는 자동 복귀하지 않는다. 영향: scan_manager · 웹 단계 표시
5. 방향 전환은 재하강 없이 `OP_MOVE_TO` 연속(올림 → 이동 → 접촉 z + `recontact_margin_m`까지 내림) 후 SLIDE
6. 하강 제한 `drop_limit_m`을 이중 감시(1차 robot_manager, 2차 safety_monitor · 래치). SetConfig 전파 경로 P03(scan_manager → safety_monitor) 신설: `over_force_n` · `drop_limit_m`
7. 추가 필드: `ContactEvent.source` · `debounce_count`, `TareForce` 응답 `baseline_norm_n` · `std_norm_n`, `StopRobot` · `StopScan` 요청 `requester`, `SafetyStatus.motion_id` · `position` · `position_valid` · `stop_confirmed`
8. `ReasonCode` 추가: `TARE_UNSTABLE=305` · `TARE_TIMEOUT=306` · `NO_SAMPLE=307`. 원칙: 번호는 추가만 하고 바꾸지 않는다
9. 무효 float는 `NaN` + `*_valid=false`(정의서의 "`z_drop_m`은 다른 type에서 0"을 대체)
10. 꼭짓점 · 엣지 · 경로 후보의 순서 규약과 치수 이름(`width` = x · `length` = y) 확정
11. 프레임: 샘플 · 이벤트 · 모션은 계속 Base, scan_manager가 결과만 변환. 조건: 가이드를 Base 축과 평행하게 설치, 평행 이동만. TCP = 팁 최하단점, 탐색 중 자세 수직 고정, 힘은 `DR_BASE`
12. 실행 패키지는 정의서의 단일 `contact_scan`이 아니라 레포의 노드별 패키지를 유지

**MQTT (1차 회의)**: ROS와 1:1 구조 · 단위 접미사 키 · enum 문자열 · `reason_code`+`reason` · `schema_version` / 시각 epoch ms · `published_at_ms` / 각도 값 없음(quaternion) / QoS · retain 표 / 미측정 `null` + `*_valid` 유지 / 명령 완료는 `scan/command_result`(start는 위 4번에 따라 마무리 복귀까지 끝난 시점)

**TBD**: 담당 · 기한을 정하지 않고 TBD로 둔다(회의 결정). 목록은 각 문서 끝.

**리뷰 반영 (2026-09-19, PR #47 머지 전)** — 타입 변경 없음
- `mqtt-schema.md` 3장: `cmd/scan/stop`을 만료 검사에서 제외(중복 · 필수 필드 검사는 유지). 시계가 어긋나도 중지는 거절되면 안 된다. `home` · `safety/reset`은 만료 검사 유지. 영향: mqtt_bridge
- `mqtt-schema.md` 3장: 필수 필드 표 추가. `session_id`는 명령에서 선택, `hb/web`에서만 필수. 영향: FastAPI 발행부 · 목업 발행기 · mqtt_bridge
- `mqtt-schema.md` 1장: 코드 필드 표기를 `error_code`+`error_name`으로 정정(4.2절 예시가 맞았다). 2장: retain 상태 "4종" → 3종 정정, `topic_prefix` 기본값이 웹 쪽 전제임을 명시
- `ros-interfaces.md` 7.2절: 하강 제한 1차(robot_manager)의 기준 z를 2차와 같게 명시. 9장 TBD에 "순응 · 힘 제어 해제 실패 시 보고"와 "`move_stop` → 해제 순서의 실기 확인" 추가

## v0.0 (2026-09-18)
- BRD v3.0.0 4.7절의 초안 표를 옮겨 적음. 확정 아님.
