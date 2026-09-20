# 계약 변경 이력

형식: `버전 (날짜, PR) - 무엇을 왜. 영향받는 모듈`

## v0.1.6 (2026-09-20, T19a, PR #82)
타입 변경 없음. `units-frames.md`의 **탐색 기준점** 행에서 "별도 파라미터를 두지 않는다"를 "scan_manager 파라미터 `search_origin_pose`(Base, x y z + quaternion)로 둔다"로 바꿨다. PR #77(T19a 2/2) 리뷰에서 현지가 계약과 코드의 불일치를 지적했다. 영향: scan_manager(T19a · T19b), `contact_scan_bringup/config/*.yaml`의 `scan_manager:` 절.
- 이유: scan_manager는 홈 자세의 TCP를 모른다(홈은 robot_manager의 관절각이고 scan_manager는 `/robot/sample`을 구독하지 않는다). `OP_MOVE_TO`의 목표에는 자세가 필요한데 자세(수직 고정)는 홈과 `base_to_fixture`만으로 나오지 않는다
- 값을 정하는 규칙은 그대로다: x · y = 작업대 원점, z = 첫 하강을 시작할 높이(초안: 홈 팁 높이), 자세 = 탐침 수직. 자세는 quaternion으로 적는다(두산 ZYZ 오일러와 혼동하지 않게)
- `max_descend_m` 조건(하한 · 상한)은 바꾸지 않았다. 값은 여전히 TBD다
- 번호: main은 v0.1.5(PR #79, 머지됨)다. 팀에서 합의한 순서(#79 → #82 → #80)로 배정했다 — **v0.1.6 = 이 PR**, **v0.1.7 · v0.1.8 = PR #80**(T03 후속, 두 항목), **v0.1.9 = 후속 PR**(#51 · #54). PR #80도 같은 행(홈 팁 높이 수치)을 고치므로 나중에 머지되는 쪽이 rebase한다
## v0.1.5 (2026-09-20, #69, PR #79)
타입 변경 없음. `ros-interfaces.md` 3.3절의 **"판정 샘플"** 을 **조건이 처음 성립한 샘플**(연속 구간의 첫 샘플)로 확정하고, `ContactEvent` 필드별로 어느 샘플의 값인지 적었다. 주석만 바뀌었고 필드 이름 · 타입 · 순서 · 상수값은 그대로다. 영향: contact_detector(T16 배선에서 고르는 필드) · scan_manager/geometry_estimator(`detect_latency_s`의 뜻에서 디바운스 몫이 빠진다) · mqtt_bridge · 웹(`pose`의 뜻만 달라진다). robot_manager는 이벤트를 정지 트리거로만 쓰므로 영향 없음.
- 첫 샘플: `pose` · `pose_stamp` · `wrench` · `force_stamp` · `sample_id` · `z_drop_m`(EDGE). 확정 샘플: `force_delta_n` · `detect_stamp`. `debounce_count`는 그대로
- 왜: 확정 샘플의 좌표를 쓰면 `debounce_n` 하나가 오검출 억제와 측정 편향을 같이 바꾼다. 실기에서 디바운스를 튜닝할 때마다 편향 보정 상수(T30)를 다시 재야 한다. 첫 샘플로 두면 측정 좌표가 디바운스 설정과 무관해진다
- 편향 크기는 50 Hz · 5 mm/s에서 N=3이면 0.2 mm, N=5면 0.4 mm다. **계산값이고 실측이 아니다**
- `detect_stamp − force_stamp`가 디바운스 지연이 되어 TR-01의 "판정 지연"을 이벤트만으로 구할 수 있다
- CONTACT · EDGE · OVER_FORCE에 같은 정의를 쓴다. main의 `detector_core.Detection`은 두 샘플을 모두 들고 있어 CONTACT · OVER_FORCE가 이미 이 배정과 같다. EDGE는 아직 구현 전이다
- 번호: v0.1.4(PR #72)가 머지된 main 위로 rebase했다. 같은 시기에 열린 계약 PR(#80 T03 후속 · #82 units-frames)과는 머지 순서로 번호를 맞춘다

## v0.1.4 (2026-09-20, T15, PR #72)
타입 변경 없음. `ros-interfaces.md`의 **실측 발행 주기**와 **`RobotStatus.moving`의 근거**를 채웠다. 영향: scan_manager(정지 완료 판단) · contact_detector · safety_monitor(샘플 주기 가정).
- 실측(Virtual): `/robot/sample` 37.6 Hz, `/robot/status` 9.3~9.8 Hz. 설정값 50 · 10 Hz에 못 미친다. 두산 서비스를 직렬로 불러야 해서다(동시 호출 시 드라이버가 응답을 멈췄다)
- `moving`: `get_robot_state`가 Virtual에서 이동 중에도 STANDBY를 돌려줘 쓸 수 없다. 최근 0.3 s 안의 TCP 위치 변화가 0.2 mm를 넘으면 이동 중으로 본다. 위치를 모르면 이동 중으로 본다
- TBD 목록에서 "실측 발행 주기(T15)"와 "`RobotStatus.moving`의 근거"를 지웠다
- **(PR #83 추가)** `moving_eps_m` · `moving_window_s`를 바꾸면 scan_manager의 정지 확인 지연과 safety_monitor의 `stop_confirmed` 시점이 같이 바뀐다. 값을 고칠 때는 전원에게 알린다
- **(PR #85 추가)** `ros-interfaces.md` 머리말 상태 줄에 v0.1.4 구절이 빠져 있었다. 문서를 고치면서 머리말을 같이 갱신하지 않은 누락이고, 내용 변경은 없다 (병후 지적, PR #80 리뷰)

## v0.1.3 (2026-09-19, T03, PR #60)
타입 변경 없음. `units-frames.md`의 **z=0**, **작업대 원점(초안)**, **축 평행**, **홈 관절각**, **탐색 기준점 높이(초안)**를 실측 · 계산해 적었다. 측정 원본은 `docs/env/origin-home-register.md`. 측정은 모두 플랜지 posx(`get_current_tool_flange_posx`)를 읽고, TCP [-1.30, 3.71, 249.99]를 적용해 팁 위치로 바꿨다. TCP 적용 상태에 영향을 받지 않도록 이렇게 했다. 영향: scan_manager(`base_to_fixture`, 결과 변환) · robot_manager(홈) · safety_monitor(작업영역) · sim 가상 직육면체.
- z=0 = 작업대 표면, Base z 100.6 mm. 기준 큐브(80 mm) 윗면은 180.7 mm로, 차이 80.1 mm가 캘리퍼 값과 맞는다
- 작업대 원점(초안) = 큐브 윗면 가운데 x · y + z=0 = (423.56, -186.06, 100.6) mm. 2026-09-19 세션 한정이고, 가이드를 설치하면 가이드 모서리 기준으로 다시 정의한다
- 축 평행: 판정 불가. 큐브 모서리 찍기로는 정렬을 판정할 수 없다. 1~2° 회전은 치수에 0.05 mm 이하, 꼭짓점 · 경로 후보 좌표에 축당 0.7~1.4 mm
- 홈 관절각 [-24.14, 17.03, 51.68, -0.18, 111.39, -204.84] deg. 안전복귀 경로는 TBD, J6가 ±180° 밖
- 탐색 기준점 높이(초안): 첫 하강은 홈 팁 높이(작업대 위 189.4 mm)에서 시작하고 별도 파라미터를 두지 않는다. 방향 전환은 `ros-interfaces.md` 7.3을 따른다. `max_descend_m` 하한 0.116 m(홈 → 80 mm 큐브 윗면 접촉 실측 110.49 mm + 여유 5 mm), 상한 < 0.189 m − 안전 여유. 하한은 계산값 109.4 mm 대신 접촉 실측값으로 잡아 0.115에서 0.116으로 바꿨다
- 리뷰 반영(PR #60): 원점 y를 -187.1(T02 피벗 고정점)에서 네 모서리 가운데 -186.06으로 정정해 정의와 값을 맞췄다. 축 평행을 판정 불가로 바꿨다. 윗면 10점 산포(179.3~181.5)를 적었다. 기준 큐브 모서리 라운드 가설(폭 최대 약 3.4 mm 과소 추정 가능, 상한)을 추가했다. 측정 원본을 PR 본문에서 `docs/env/origin-home-register.md`로 옮겼다. 2차 리뷰: 탐색 기준점의 "z_top 확정 후 윗면 위 30 mm"를 빼고 계약 7.3을 따르게 했다. `max_descend_m`에 여유와 상한을 적었다. "평행 여부는 T03에서 확인한다" 문구를 판정 불가 결론에 맞췄다

## v0.1.2 (2026-09-19, T02, PR #57)
타입 변경 없음. `units-frames.md`의 좌표 값 중 **툴 무게 · 무게중심**, **탐침 TCP 오프셋(최하단점)**, **팁 반지름**을 실측해 적었다. 근거는 `docs/env/tool-tcp-register.md`. 영향: robot_manager(T13) · contact_detector(T07, T16) · 모서리 편향 보정(r 사용) · 임계값 튜닝(T24).
- 툴: 1.3 kg, 무게중심 (0, 31.08, 29.84) mm. 펜던트에 있던 값이다
- TCP(최하단점): [-1.30, 3.71, 249.99] mm. 피벗 보정 14자세로 구 중심 [-1.30, 3.71, 249.76]을 구하고 r(0.225)을 더했다(249.985를 반올림). 불확도는 약 ±1 mm다
- 팁 반지름 r: 0.225 mm(지름 0.45 mm 실측). 탐침이 인공눈물 용기로 바뀌어 설계 출발값 3 mm를 대체한다
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
