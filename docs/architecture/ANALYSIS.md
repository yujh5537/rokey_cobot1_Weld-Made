# Weld-Made 코드 분석 및 검증

- 저장소: https://github.com/yujh5537/rokey_cobot1_Weld-Made
- 분석 브랜치: main
- 커밋 SHA: `8933b739ee43294605e57dca07625bad2f9e8ca4`
- Archify: 3.0.1 / `bb6f126f1748a4079df1d263302466eb4333e3b0`
- 기준 사이트: https://cobot3-ws-c2-architectures.netlify.app/
- 첨부 후보본의 기존 wrapper와 원본 Archify viewer 구조를 유지했다. 이번 수정에서는 기준 사이트의 전체 git 소스를 새로 입수하지 않았다. 실행 근거를 고정 커밋과 대조했다.
- 원본 Archify HTML의 내부 JavaScript와 기능은 수정하지 않았다. iframe 높이·바깥 메뉴·테마 동기화만 기준 사이트 방식을 사용한다.
- 메뉴와 설명은 한국어, 원본 Viewer UI는 영어로 유지한다.
- 배포 및 GitHub README 수정은 수행하지 않았다.

## 코드 기준 실행 영역

| 영역 | 구성 | 구현 근거 / 범위 |
|---|---|---|
| Web PC 역할 | Mosquitto, FastAPI, PostgreSQL, Spring Boot | docker/docker-compose.yml; 실제 PC 주소·실행 여부는 확정할 수 없음 |
| Web PC 역할 | React / Three.js, Vite | frontend/src/App.jsx, vite.config.js; compose에 frontend 서비스 없음 |
| Main PC 역할 | robot_manager, contact_detector, safety_monitor, scan_manager, mqtt_bridge, weld_manager | contact_scan_bringup/launch/bringup.launch.py; 설치되지 않은 패키지는 skip |
| Main PC 역할 | 별도 두산 드라이버, 로컬 결과 파일 | launch에서 드라이버 별도 실행 명시; robot_manager/dsr_client.py, real.yaml, result_store |
| 로봇 컨트롤러 | 외부 M0609 제어 실행 영역 | 외부 구현은 repo에 없음. 내부 TCP 연결·드라이버 노드 구성은 추정해 추가하지 않음 |

두 PC 구분은 코드에 명시된 브로커 주소 주입과 실행 역할 기준이다. 관측한 PC 프로세스나 실제 배치 상태라는 뜻은 아니다. source=sim/robot_force로 입력원을 선택한다. 실제 ROS_DOMAIN_ID와 PC IP를 현재 저장소만으로 확정하지 않았다.

## 구현 / 미연결 구분

| 항목 | 상태 | 다이어그램 처리 |
|---|---|---|
| 스캔 FSM, 힘·엣지 판정, 모션·정지 | 구현 | 실제 pub/sub/service/action 방향 반영 |
| 용접 경로 실행 및 결과 파일 | 구현 | phase 2 경로 포함 |
| 실제 아크 전원 / 용접 장비 I/O | 코드 근거 없음 | 제어 연결 추가하지 않음 |
| React → FastAPI commands, FastAPI → React /ws | 구현 | HTTP/WS 경로 포함 |
| FastAPI ↔ Mosquitto, MQTT ↔ ROS 브리지 | 구현 | JSON 변환·명령 매핑 포함 |
| FastAPI → PostgreSQL 스캔·접촉 저장 | 구현 | db.py INSERT/UPSERT 대조 |
| Spring → PostgreSQL | 구현 | JPA/JDBC 및 ddl-auto=none 대조 |
| React → Spring 작업·이력 API | 현재 App.jsx에 호출 없음 | 선 없음 |
| hb/web → /web/heartbeat | 브리지 수신·발행 구현, 웹 발행자·ROS 구독자 미확인 | 완성 연결로 그리지 않음 |
| weld/result → PostgreSQL | 저장 분기 / 전용 테이블 없음 | 선·테이블 없음 |

## 네 다이어그램

1. 시스템 아키텍쳐: Web PC / Main PC와 외부 컨트롤러 구분. SQL, MQTT JSON, ROS control, 로컬 파일 역할 표시. ↔ 라벨은 왕복 관계를 요약하며 정확한 pub/sub 방향은 통신도와 아래 등록표 참조.
2. ROS 2 통신 아키텍쳐: 커스텀 노드 6개, 외부 dsr_controller2 서비스 및 JointState 입력을 분리. 같은 방향의 여러 인터페이스는 읽기 쉬운 하나의 선으로 묶고 이름·타입 전체를 원본 Viewer의 설명 카드 및 아래 등록표에 기록했다. 응답과 feedback/result는 서비스·액션 호출의 역방향이며 별도 프로세스 연결이 아니다.
3. 전체 공정 플로우차트: START 상단 / END 하단. 스캔 대기·준비·윗면·4방향 모서리·형상·홈·DONE, 조건 거절, TIMEOUT, STOPPING/STOPPED, ERROR, 수동 RESUMING을 포함. 용접은 별도 사용자 START이며 자동 연계가 아니다. 단방향 경로를 명확히 배치하기 위해 Archify architecture IR을 사용했다.
4. ERD: 초기화 SQL의 7개 테이블, PK, 실제 FK 5개와 UNIQUE 제약. 71개 전체 컬럼·타입·NULL/default·키·제약을 Viewer 테이블 본문과 상세 카드에 표시. contact_events.scan_id는 실제 FK가 아니므로 연결하지 않았다.

## ROS 등록 코드 대조

공통 사용자 타입 패키지는 `contact_scan_interfaces`이다. msg/srv/action 구분은 정의 파일의 확장자와 동일하다. 아래 표는 AST로 실제 등록 표현식을 추출했다. 동적 표준 parameter client와 joint_state_topic 설정은 별도 설명한다.

| 노드 | 등록 | 이름 | 타입 | 소스 줄 |
|---|---|---|---|---|
| robot_manager | create_publisher | `/robot/sample` | `RobotSample` | `ws_cobot1/src/robot_manager/robot_manager/robot_manager.py:381` |
| robot_manager | create_publisher | `/contact/event` | `ContactEvent` | `ws_cobot1/src/robot_manager/robot_manager/robot_manager.py:383` |
| robot_manager | create_publisher | `/robot/status` | `RobotStatus` | `ws_cobot1/src/robot_manager/robot_manager/robot_manager.py:385` |
| robot_manager | create_subscription | `/contact/event` | `ContactEvent` | `ws_cobot1/src/robot_manager/robot_manager/robot_manager.py:386` |
| robot_manager | create_service | `/robot/stop` | `StopRobot` | `ws_cobot1/src/robot_manager/robot_manager/robot_manager.py:421` |
| robot_manager | ActionServer | `/robot/execute_motion` | `ExecuteMotion` | `ws_cobot1/src/robot_manager/robot_manager/robot_manager.py:422` |
| robot_manager | ActionServer | `/robot/execute_path` | `ExecutePath` | `ws_cobot1/src/robot_manager/robot_manager/robot_manager.py:428` |
| contact_detector | create_publisher | `/contact/event` | `ContactEvent` | `ws_cobot1/src/contact_detector/contact_detector/contact_detector.py:140` |
| contact_detector | create_subscription | `/robot/sample` | `RobotSample` | `ws_cobot1/src/contact_detector/contact_detector/contact_detector.py:141` |
| contact_detector | create_subscription | `/scan/state` | `ScanState` | `ws_cobot1/src/contact_detector/contact_detector/contact_detector.py:142` |
| contact_detector | create_service | `/contact/tare` | `TareForce` | `ws_cobot1/src/contact_detector/contact_detector/contact_detector.py:146` |
| safety_monitor | create_publisher | `/safety/status` | `SafetyStatus` | `ws_cobot1/src/safety_monitor/safety_monitor/safety_monitor.py:86` |
| safety_monitor | create_subscription | `/robot/sample` | `RobotSample` | `ws_cobot1/src/safety_monitor/safety_monitor/safety_monitor.py:87` |
| safety_monitor | create_subscription | `/robot/status` | `RobotStatus` | `ws_cobot1/src/safety_monitor/safety_monitor/safety_monitor.py:88` |
| safety_monitor | create_client | `/robot/stop` | `StopRobot` | `ws_cobot1/src/safety_monitor/safety_monitor/safety_monitor.py:89` |
| safety_monitor | create_service | `/safety/reset` | `ResetSafety` | `ws_cobot1/src/safety_monitor/safety_monitor/safety_monitor.py:90` |
| scan_manager | create_publisher | `/scan/state` | `ScanState` | `ws_cobot1/src/scan_manager/scan_manager/scan_manager.py:229` |
| scan_manager | create_publisher | `/scan/result` | `ScanResult` | `ws_cobot1/src/scan_manager/scan_manager/scan_manager.py:230` |
| scan_manager | create_publisher | `/scan/log` | `ScanLog` | `ws_cobot1/src/scan_manager/scan_manager/scan_manager.py:231` |
| scan_manager | create_subscription | `/robot/status` | `RobotStatus` | `ws_cobot1/src/scan_manager/scan_manager/scan_manager.py:240` |
| scan_manager | create_subscription | `/robot/sample` | `RobotSample` | `ws_cobot1/src/scan_manager/scan_manager/scan_manager.py:244` |
| scan_manager | create_subscription | `/safety/status` | `SafetyStatus` | `ws_cobot1/src/scan_manager/scan_manager/scan_manager.py:246` |
| scan_manager | create_subscription | `/contact/event` | `ContactEvent` | `ws_cobot1/src/scan_manager/scan_manager/scan_manager.py:248` |
| scan_manager | create_subscription | `/weld/state` | `WeldState` | `ws_cobot1/src/scan_manager/scan_manager/scan_manager.py:251` |
| scan_manager | ActionClient | `/robot/execute_motion` | `ExecuteMotion` | `ws_cobot1/src/scan_manager/scan_manager/scan_manager.py:253` |
| scan_manager | create_client | `/contact/tare` | `TareForce` | `ws_cobot1/src/scan_manager/scan_manager/scan_manager.py:255` |
| scan_manager | create_client | `/robot/stop` | `StopRobot` | `ws_cobot1/src/scan_manager/scan_manager/scan_manager.py:256` |
| scan_manager | create_service | `/scan/stop` | `StopScan` | `ws_cobot1/src/scan_manager/scan_manager/scan_manager.py:281` |
| scan_manager | create_service | `/scan/set_config` | `SetConfig` | `ws_cobot1/src/scan_manager/scan_manager/scan_manager.py:284` |
| scan_manager | ActionServer | `/scan/run` | `RunScan` | `ws_cobot1/src/scan_manager/scan_manager/scan_manager.py:277` |
| scan_manager | ActionServer | `/scan/home` | `ReturnHome` | `ws_cobot1/src/scan_manager/scan_manager/scan_manager.py:278` |
| scan_manager | ActionServer | `/scan/resume` | `Resume` | `ws_cobot1/src/scan_manager/scan_manager/scan_manager.py:279` |
| mqtt_bridge | create_subscription | `/robot/sample` | `RobotSample` | `ws_cobot1/src/mqtt_bridge/mqtt_bridge/mqtt_bridge.py:237` |
| mqtt_bridge | create_subscription | `/robot/status` | `RobotStatus` | `ws_cobot1/src/mqtt_bridge/mqtt_bridge/mqtt_bridge.py:251` |
| mqtt_bridge | create_subscription | `/scan/state` | `ScanState` | `ws_cobot1/src/mqtt_bridge/mqtt_bridge/mqtt_bridge.py:256` |
| mqtt_bridge | create_subscription | `/scan/result` | `ScanResult` | `ws_cobot1/src/mqtt_bridge/mqtt_bridge/mqtt_bridge.py:261` |
| mqtt_bridge | create_subscription | `/scan/log` | `ScanLog` | `ws_cobot1/src/mqtt_bridge/mqtt_bridge/mqtt_bridge.py:266` |
| mqtt_bridge | create_subscription | `/contact/event` | `ContactEvent` | `ws_cobot1/src/mqtt_bridge/mqtt_bridge/mqtt_bridge.py:271` |
| mqtt_bridge | create_subscription | `/safety/status` | `SafetyStatus` | `ws_cobot1/src/mqtt_bridge/mqtt_bridge/mqtt_bridge.py:276` |
| mqtt_bridge | create_publisher | `/web/heartbeat` | `WebHeartbeat` | `ws_cobot1/src/mqtt_bridge/mqtt_bridge/mqtt_bridge.py:290` |
| mqtt_bridge | ActionClient | `/scan/run` | `RunScan` | `ws_cobot1/src/mqtt_bridge/mqtt_bridge/mqtt_bridge.py:291` |
| mqtt_bridge | ActionClient | `/scan/home` | `ReturnHome` | `ws_cobot1/src/mqtt_bridge/mqtt_bridge/mqtt_bridge.py:292` |
| mqtt_bridge | ActionClient | `/scan/resume` | `Resume` | `ws_cobot1/src/mqtt_bridge/mqtt_bridge/mqtt_bridge.py:293` |
| mqtt_bridge | create_client | `/scan/stop` | `StopScan` | `ws_cobot1/src/mqtt_bridge/mqtt_bridge/mqtt_bridge.py:294` |
| mqtt_bridge | create_client | `/scan/set_config` | `SetConfig` | `ws_cobot1/src/mqtt_bridge/mqtt_bridge/mqtt_bridge.py:295` |
| mqtt_bridge | create_client | `/safety/reset` | `ResetSafety` | `ws_cobot1/src/mqtt_bridge/mqtt_bridge/mqtt_bridge.py:296` |
| mqtt_bridge | ActionClient | `/weld/run` | `RunWeld` | `ws_cobot1/src/mqtt_bridge/mqtt_bridge/mqtt_bridge.py:297` |
| mqtt_bridge | ActionClient | `/weld/home` | `ReturnHome` | `ws_cobot1/src/mqtt_bridge/mqtt_bridge/mqtt_bridge.py:298` |
| mqtt_bridge | create_client | `/weld/stop` | `StopWeld` | `ws_cobot1/src/mqtt_bridge/mqtt_bridge/mqtt_bridge.py:299` |
| mqtt_bridge | create_subscription | `/weld/state` | `WeldState` | `ws_cobot1/src/mqtt_bridge/mqtt_bridge/mqtt_bridge.py:283` |
| mqtt_bridge | create_subscription | `/weld/result` | `WeldResult` | `ws_cobot1/src/mqtt_bridge/mqtt_bridge/mqtt_bridge.py:284` |
| mqtt_bridge | create_subscription | `/weld/log` | `ScanLog` | `ws_cobot1/src/mqtt_bridge/mqtt_bridge/mqtt_bridge.py:285` |
| weld_manager | create_publisher | `/weld/state` | `WeldState` | `ws_cobot1/src/weld_manager/weld_manager/weld_manager.py:137` |
| weld_manager | create_publisher | `/weld/result` | `WeldResult` | `ws_cobot1/src/weld_manager/weld_manager/weld_manager.py:138` |
| weld_manager | create_publisher | `/weld/log` | `ScanLog` | `ws_cobot1/src/weld_manager/weld_manager/weld_manager.py:139` |
| weld_manager | create_subscription | `/scan/state` | `ScanState` | `ws_cobot1/src/weld_manager/weld_manager/weld_manager.py:146` |
| weld_manager | create_subscription | `/robot/status` | `RobotStatus` | `ws_cobot1/src/weld_manager/weld_manager/weld_manager.py:148` |
| weld_manager | create_subscription | `/safety/status` | `SafetyStatus` | `ws_cobot1/src/weld_manager/weld_manager/weld_manager.py:150` |
| weld_manager | create_subscription | `/robot/sample` | `RobotSample` | `ws_cobot1/src/weld_manager/weld_manager/weld_manager.py:152` |
| weld_manager | ActionClient | `/robot/execute_motion` | `ExecuteMotion` | `ws_cobot1/src/weld_manager/weld_manager/weld_manager.py:154` |
| weld_manager | ActionClient | `/robot/execute_path` | `ExecutePath` | `ws_cobot1/src/weld_manager/weld_manager/weld_manager.py:155` |
| weld_manager | create_client | `/robot/stop` | `StopRobot` | `ws_cobot1/src/weld_manager/weld_manager/weld_manager.py:156` |
| weld_manager | create_service | `/weld/stop` | `StopWeld` | `ws_cobot1/src/weld_manager/weld_manager/weld_manager.py:164` |
| weld_manager | ActionServer | `/weld/run` | `RunWeld` | `ws_cobot1/src/weld_manager/weld_manager/weld_manager.py:162` |
| weld_manager | ActionServer | `/weld/home` | `ReturnHome` | `ws_cobot1/src/weld_manager/weld_manager/weld_manager.py:163` |

`scan_manager`는 `/{robot_manager,contact_detector,safety_monitor}/{set_parameters,get_parameters}`에 rcl_interfaces/srv/SetParameters, GetParameters client를 만든다. 대상 노드의 표준 rclpy parameter server로 전파하며 순서는 safety_monitor → contact_detector → robot_manager이다. 자기 몫의 모션 설정은 직접 적용한다. 설정 불일치는 START/RESUME 보호 조건에서 거절한다.

`mqtt_bridge`는 joint_state_topic 기본값 `/dsr01/joint_states`의 sensor_msgs/msg/JointState를 구독한다. 현재 저장소의 외부 드라이버/종합 joint publisher를 단일 노드로 확정하지 않았다.

robot_manager → dsr_controller2: `/dsr01/dsr_controller2/` 아래 aux_control/get_current_posx:GetCurrentPosx, aux_control/get_tool_force:GetToolForce, system/get_robot_state:GetRobotState, motion/move_line:MoveLine, motion/move_joint:MoveJoint, motion/move_spline_task:MoveSplineTask, motion/move_stop:MoveStop, force/task_compliance_ctrl:TaskComplianceCtrl, force/release_compliance_ctrl:ReleaseComplianceCtrl, force/set_desired_force:SetDesiredForce, force/release_force:ReleaseForce. 타입 접두사는 dsr_msgs2/srv. 서비스 응답은 driver → robot_manager이다.

## MQTT 대조

모두 UTF-8 JSON 객체이다. 브리지의 topic_prefix 파라미터가 있으면 아래 이름 앞에 붙는다. 명령은 request_id, payload 및 명령별 scan_id/weld_id 등을 사용하고, 결과 인코더는 schema_version 및 published_at_ms를 포함한다. 정확한 필드·ROS 정의는 지정 커밋의 encoders.py, decoders.py, weld_codec.py 및 msg/srv/action 파일 참조. evidence/source-excerpts.txt와 interface-registry.json에는 실행 근거를 기록했다.

| 경로 | 이름 | 방향 |
|---|---|---|
| 스캔 시작 | cmd/scan/start → /scan/run:RunScan | FastAPI → Broker → mqtt_bridge → scan_manager |
| 홈 | cmd/scan/home → /scan/home:ReturnHome | 동일 |
| 재개 | cmd/scan/resume → /scan/resume:Resume | 동일 |
| 중단 | cmd/scan/stop → /scan/stop:StopScan | 동일 |
| 설정 | cmd/scan/set_config → /scan/set_config:SetConfig | 동일 |
| 용접 | cmd/weld/start/home/stop → /weld/run:RunWeld, /weld/home:ReturnHome, /weld/stop:StopWeld | FastAPI → Broker → mqtt_bridge → weld_manager |
| 안전 reset | cmd/safety/reset → /safety/reset:ResetSafety | FastAPI → Broker → mqtt_bridge → safety_monitor |
| 접수 | cmd/ack | mqtt_bridge → Broker → FastAPI → React /ws |
| 명령 결과 | scan/command_result, weld/command_result | mqtt_bridge → Broker → FastAPI → React /ws |
| 샘플·관절 | robot/sample, robot/joints, robot/gripper_joints | ROS 입력 → mqtt_bridge → Broker → FastAPI → React /ws |
| 상태 | robot/status, scan/state, weld/state, safety/status | ROS 입력 → mqtt_bridge → Broker → FastAPI → React /ws |
| 결과·로그·접촉 | scan/result, scan/log, weld/result, weld/log, contact/event | 동일; DB 저장은 scan/result 및 contact/event만 |
| 연결 | hb/ros, conn/ros | mqtt_bridge → Broker → FastAPI |
| Web heartbeat | hb/web, conn/web | 브리지 수신만 구현 확인. 생산자는 연결하지 않음 |

QoS/retain은 bridge 호출에서 확인: robot/sample, joints, gripper_joints 및 hb/ros는 QoS 0, non-retained. robot/status, scan/state, weld/state, safety/status와 conn/ros는 QoS 1 retained. 결과, 로그, 접촉, ack, command_result는 QoS 1 non-retained. FastAPI는 해당 wildcard 토픽을 QoS 1로 구독한다. JSON 송수신과 ROS 메시지는 같은 타입이 아니며 bridge가 인코딩/디코딩한다.

## 수정된 공정 의미 및 새 검증

CHANGELOG.md의 A–H 표와 VALIDATION_SUMMARY.md를 참조하십시오. 용접 204 낮은 팁 복구 성공은 다음 선 진행이 아니라 ERROR입니다. 결과는 홈 복귀 전에 저장·발행됩니다. 407 whitelist만으로 RESUME을 허용하지 않습니다.
