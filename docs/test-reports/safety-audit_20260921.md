# 안전 제약 감사: 기능·디버깅을 막는 지점 (2026-09-21, Day 4)

- **감사 기준**: `origin/main` **c9de11e**(#134 병합 직후). 스냅샷 뒤에 병합된 #135, #127, #136은 본문을 고치지 않고 [0-1절](#0-1-감사-스냅샷c9de11e-이후-바뀐-것--본문에-반영되지-않았다)에 따로 적었다.
- **목적**: 안전 제약(두산 컨트롤러, 드라이버, 자체 노드, 통신·웹) 때문에 기능 구현이나 디버깅이 막히는 지점을 코드 근거로 찾아 지도로 만든다. 안전 기능을 끄거나 우회하는 해결책은 넣지 않았다. 개선 방향은 모두 "안전 의도를 유지하면서 구현 난이도를 낮추는" 쪽이다.
- **방법**: 읽기 전용이다. c9de11e 스냅샷의 코드, 계약, 설계 문서, 시험 기록을 정독했다. 실행한 것은 둘뿐이다.
  - 순수 계산 모듈(`safety_core`, `motion_state`)로 오프라인 재현([부록 A](#부록-a-오프라인-재현-스크립트))
  - 실기 CSV 통계 분석([부록 B](#부록-b-외력-값-갱신-간격-분석))
  - ROS, Virtual, 실기 명령은 실행하지 않았다. 코드, 파라미터, 계약은 바꾸지 않았다.
- **근거 표기**: 코드와 계약의 링크는 c9de11e 고정 링크라 줄 번호가 밀리지 않는다. 두산 드라이버(`ws_dsr/`, 레포 밖)는 경로와 줄만 적었다. 버전은 `docs/env/versions.md`를 따른다. 확인 수준은 `.claude/rules/docs-wording.md`의 소스 확인[E18], 실제 PC 호출 확인[E19], 실기 기록을 구분해 적었다. **가설**은 가설로 표시했다.
- **요청·검토**: 현지(@yujh5537). 분석: Claude Code.

## 0. 지시문과 저장소가 다른 점

| 지시문 | 저장소 실제 | 처리 |
|---|---|---|
| BRD v3.1.0 | md는 **v3.2.0**. v3.1.0은 `docs/archive/`의 docx뿐이다 | v3.2.0 기준 |
| 인터페이스 정의서 통합본 v1.1 | `contact-scan-interface-spec-integrated-v1.2.md` | v1.2를 참고로 썼다. 1차 기준은 `docs/contracts/` |
| 노드 구성도 v1.0 | `contact-scan-node-diagram-v1.1.md` | v1.1 |
| 최근 증상(빈칸) | — | 9/20~21 시험 기록(`realrobot-session_20260921.md`, `daily/`, `scan_sim_t19b/`)의 증상으로 대신했다 |

### 0-1. 감사 스냅샷(c9de11e) 이후 바뀐 것 — 본문에 반영되지 않았다

| 병합 | 변경 | 본문에서 영향받는 곳 |
|---|---|---|
| #135 `85f924f` (#130) | robot_manager가 늦은 두산 응답을 서비스 이름과 시간으로 남긴다(`slow_call_warn_s` 0.15). 실기 9/21 기록: **정지 중이든 모션 중이든 약 3 s마다 한 호출이 330~365 ms 늦었다**(평소 4~20 ms) | **B-2**: 샘플 공백 원인의 1단계 근거가 생겼다. F2-5의 "모션 호출이 큐를 점유한다" 가설은 **약해졌다**(공백은 모션과 무관하게 주기적으로 난다). **C-3**: 평소에도 약 3 s마다 move_stop이 최대 약 0.36 s 줄을 설 수 있다는 정량 근거다. §4.5의 진단 로그 제안(C-3, B-2)은 일부 구현됐다 |
| #127 `22cf09b` (#109, 계약 v0.1.12) | 하강 CONTACT의 F₀를 최근 구간 외력 평균(이동 기준)으로, 출발 뒤 5.5 s는 6 N 임계로 판정한다. EDGE는 "z가 멈추고 x·y가 움직임"으로 켠다. `/contact/tare`는 툴 등록 점검과 예비 기준으로 남는다 | **B-1**(정지 tare로 허공 거짓 CONTACT)과 **§5-1**(계약끼리의 충돌)이 해소됐다. F1-2와 F2-2도 영향을 받는다. `real.yaml`의 좌표 두 줄을 켜는 조건 중 ①이 충족됐고, ②(새 탐침 TCP x·y)는 남아 있다. **C-7 관련**: 계약 v0.1.12에 "`get_tool_force`는 센서가 아니라 모델 기반 추정"이 명시됐다. `descend_ref_min_samples` 10은 샘플 수이며, 0.7 s 구간 안의 **서로 다른 힘 값은 약 7개**다(부록 B의 94 ms로 계산) |
| #136 `8c33a50` (#120) | scan_manager가 `/safety/status`와 `/robot/status`의 stamp 나이를 보고 START·RESUME을 거절한다. HOME은 `/safety/status`가 끊겨도 막지 않는다. 끊김과 회복은 `/scan/log`에 남긴다. PR 본문 정정: **TRANSIENT_LOCAL은 발행자가 죽으면 늦게 뜬 구독자에게 옛 메시지를 주지 않는다** | **D-1**이 START·RESUME 기준으로 해소됐다. **진행 중인 스캔은 계속된다**(로그만 남김). 모션 도중 safety_monitor가 죽는 경우는 남는다. L4-5, F4-4도 영향을 받는다 |

---

## 1. 저장소 구조 요약

```
ws_cobot1/src/
  contact_scan_interfaces/  msg 11 · srv 5 · action 4 · contact_scan_qos(QoS 5종 고정)
  robot_manager/            robot_manager.py · call_queue.py(두산 호출 직렬화) · dsr_client.py · motion_state.py · motions.py
  contact_detector/         contact_detector.py · detector_core.py(판정·tare) · sim_source.py(가상 직육면체)
  safety_monitor/           safety_monitor.py · safety_core.py(조건·정지추적·래치)
  scan_manager/             scan_manager.py · state_machine.py · sequence.py · propagation.py · resume.py · geometry_estimator/ · result_store/
  mqtt_bridge/              mqtt_bridge.py · command_guard.py(필수필드·중복·만료) · encoders/decoders
  contact_scan_bringup/     launch/bringup.launch.py · config/real.yaml · config/sim.yaml
backend/app (FastAPI main.py·db.py) · backend/spring · frontend/src/App.jsx · docker (mosquitto·postgres)
ws_dsr/ (레포 밖) doosan-robot2: dsr_controller2 · dsr_msgs2 · DSR_ROBOT2.py
```

| 문서의 노드 | 실제 구현 | 문서와 다른 점 |
|---|---|---|
| scan_manager | `scan_manager/scan_manager.py` | geometry_estimator와 result_store가 이 패키지 안에 있다 |
| robot_manager | `robot_manager/robot_manager.py` | `home_pose`가 아니라 `home_joint_deg`다. `/dsr01/error`를 구독하지 않는다 |
| contact_detector | `contact_detector/contact_detector.py` | 문서에 없는 `over_force_debounce_n`, `edge_arm_force_n`, `edge_trend_*`가 있다 |
| safety_monitor | `safety_monitor/safety_monitor.py` | 속도, 작업영역, z 하한, heartbeat, `latch_levels`가 **미구현**이다. 문서에 없는 `startup_grace_s`가 있다 |
| mqtt_bridge | `mqtt_bridge/mqtt_bridge.py` | 파라미터 이름이 노드 구성도(`downsample_hz`, `hb_ros_hz`)와 다르다. bringup이 파라미터를 주입하지 않는다 |
| contact_scan_interfaces | 그대로 | `/web/heartbeat`는 발행만 하고 구독자가 없다 |

누락된 노드는 없다. 모든 노드는 `bringup.launch.py` 하나로 뜨고, 두산 드라이버는 사람이 따로 띄운다.

**분석 순서**: ① 4계층 제약 전수 수집(§2) → ② F1~F6 호출 경로에 제약 ID 얹기(§3) → ③ A~D 분류와 우선순위(§4) → ④ 가설별 확인 절차(§4.5) → ⑤ 문서-코드 불일치(§5) → ⑥ 확인하지 못한 항목(§6)

---

## 2. 안전 제약 인벤토리

### L1: 두산 컨트롤러 (코드 밖, 설정 의존)
| ID | 위치 | 조건 | 동작 | 임계값·출처 | 해제 |
|---|---|---|---|---|---|
| L1-1 | [BRD.md:290](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/docs/BRD.md#L290), [ros-interfaces.md:283](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/docs/contracts/ros-interfaces.md#L283) | 물리 비상정지, 협동로봇 충돌 감지 | 컨트롤러 정지 | **설정값 기록 없음**(충돌 감도, TCP 힘·속도, 구역, 정지 범주). "본 시스템은 설정을 바꾸지 않는다" | 티치펜던트 |
| L1-2 | `ws_dsr/…/dsr_controller2/src/dsr_controller2.cpp:3071-3094` (소스 확인[E18]) | SAFE_STOP, SAFE_OFF, SAFE_STOP2, SAFE_OFF2 진입 | **제어권이 있으면 드라이버가 스스로 복구한다**(safe stop 리셋, 서보 온과 자동 모드(1회), recovery). EMERGENCY_STOP에서는 아무것도 하지 않는다 | 드라이버에 고정 | 자동. SW에는 알림이 없다 |
| L1-3 | `ws_dsr/…/dsr_msgs2/srv/GetRobotState.srv`, [dsr_client.py:75-79](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/robot_manager/robot_manager/dsr_client.py#L75) | 상태 3/5/6/9/10(SAFE_OFF, SAFE_STOP, E-STOP 등) | 코드는 `success`만 본다. 이 상태에서도 connected=true | — | — |
| L1-4 | [units-frames.md:93](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/docs/contracts/units-frames.md#L93) | 툴·TCP 등록은 수동 모드에서만 되고, `sodreal`을 다시 켜면 지워진다 | 미등록이면 외력이 11~12.5 N 치우쳐 TOOL_REG_SUSPECT 또는 OVER_FORCE | 실측(units-frames.md) | 수동 모드에서 `apply_tool_tcp.py` |
| L1-5 | [api-check-log.md:58-60](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/docs/env/api-check-log.md#L58) | dsr_controller2 무응답 | `/robot/stop`과 `/robot/status`가 같이 죽는다 | — | 물리 비상정지, 브링업 재시작 |
| L1-6 | `ws_dsr/…/dsr_controller2.cpp:2892-2921`(소스 확인[E18]) + [부록 B](#부록-b-외력-값-갱신-간격-분석) | `get_tool_force`는 모니터링 콜백(주석 "every 100 msec")이 채운 캐시를 돌려준다 | **값이 약 94 ms마다만 바뀐다.** 서로 다른 값 사이 간격은 중앙 94, p95 118, 최대 121 ms이고 같은 값이 4~5번 반복된다 | 실측 데이터: 2026-09-20 실기, 기록기 단독(`idle_30s.csv`, `descend_01.csv`). 분석은 이 감사 | — |

### L2: 드라이버·API
| ID | 위치 | 조건 | 동작 | 임계값·출처 | 해제 |
|---|---|---|---|---|---|
| L2-1 | [call_queue.py:25](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/robot_manager/robot_manager/call_queue.py#L25), [:68-84](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/robot_manager/robot_manager/call_queue.py#L68) | 두산 호출을 한 번에 1개만 보낸다 | 0.5 s가 지나면 None을 알리지만 **슬롯은 최대 5 s 잡고 있다.** 그동안 `move_stop`을 포함한 모든 호출이 대기한다 | `service_timeout_s` 0.5(yaml), `abandon_after_s` 5.0(**코드에 고정**) | 응답 또는 5 s |
| L2-2 | [motion_state.py:16-39](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/robot_manager/robot_manager/motion_state.py#L16) | moving = 0.3 s 창 안에서 0.2 mm를 넘게 움직임. 모르면 true | 정지 완료의 유일한 근거 | [real.yaml:112-116](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/contact_scan_bringup/config/real.yaml#L112) | — |
| L2-3 | [robot_manager.py:246-250](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/robot_manager/robot_manager/robot_manager.py#L246), [:264-267](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/robot_manager/robot_manager/robot_manager.py#L264) | connected = `get_robot_state` 응답 성공. 한 번 시간 초과면 false | goal 거절, 진행 중 모션 종료, `/robot/stop` 거절 | 0.5 s | 다음 조회가 성공하면 |
| L2-4 | [dsr_client.py:18](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/robot_manager/robot_manager/dsr_client.py#L18), [:99-100](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/robot_manager/robot_manager/dsr_client.py#L99) | `move_stop` | DR_QSTOP(범주 2) | — | — |
| L2-5 | [robot_manager.py:506-547](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/robot_manager/robot_manager/robot_manager.py#L506), [dsr_client.py:111-114](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/robot_manager/robot_manager/dsr_client.py#L111) | SLIDE: `task_compliance_ctrl` → `set_desired_force(REL, −z)` | 켜기 **전에** 해제 대상으로 표시한다 | 3.0 N은 REL이라 실제 누름은 약 8.3 N(추정, [realrobot-session:290-291](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/docs/test-reports/realrobot-session_20260921.md#L290)) | finally |
| L2-6 | [robot_manager.py:778-808](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/robot_manager/robot_manager/robot_manager.py#L778) | 종료 | `release_force(0.3)` → 대기 → `release_compliance` | 순서는 계약상 TBD([ros-interfaces.md:696](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/docs/contracts/ros-interfaces.md#L696)) | — |
| L2-7 | `ws_dsr/…/dsr_controller2.cpp:2384`(소스 확인[E18]) | 드라이버가 `error`(RobotError) 토픽을 낸다 | **구독자가 없다** | — | — |
| L2-8 | [sim_source.py:3-6](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/contact_detector/contact_detector/sim_source.py#L3), [api-check-log.md:14](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/docs/env/api-check-log.md#L14) | Virtual | 외력은 0 근처, 힘 제어는 효과 없음 | — | — |

### L3: 자체 소프트웨어
| ID | 위치 | 조건 | 동작 | 임계값·출처 | 해제 |
|---|---|---|---|---|---|
| L3-1 | [detector_core.py:236-245](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/contact_detector/contact_detector/detector_core.py#L236), [robot_manager.py:348-351](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/robot_manager/robot_manager/robot_manager.py#L348) | 원시 \|F\| > over_force_n, 모든 동작 | OVER_FORCE 이벤트 → 대조 없이 정지. **모션이 있을 때만** 정지한다 | 30 N, debounce 1([real.yaml:22-23](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/contact_scan_bringup/config/real.yaml#L22)), 설계 출발값 | 힘이 임계 아래로 |
| L3-2 | [detector_core.py:247-260](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/contact_detector/contact_detector/detector_core.py#L247) | OP_DESCEND에서 \|F−F₀\| > 3 N이 연속 3회 | CONTACT | [real.yaml:14,21](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/contact_scan_bringup/config/real.yaml#L14) | 동작당 1회 |
| L3-3 | [detector_core.py:262-305](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/contact_detector/contact_detector/detector_core.py#L262) | OP_SLIDE에서 누름 확인(1.5 N) 뒤, 추세선보다 0.5 mm 아래가 연속 3회 | EDGE. 샘플 공백이 stale보다 길면 추세선을 리셋한다 | [real.yaml:18,27-31](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/contact_scan_bringup/config/real.yaml#L18) | — |
| L3-4 | [contact_detector.py:190-198](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/contact_detector/contact_detector/contact_detector.py#L190) | now − max(stamp) > stale_age_ms | 샘플을 버린다. **OVER_FORCE 판정도 건너뛴다** | real 100 ms, sim 200 ms | — |
| L3-5 | [detector_core.py:365-370](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/contact_detector/contact_detector/detector_core.py#L365), [sequence.py:454-461](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/scan_manager/scan_manager/sequence.py#L454) | tare: 1.5 s 동안 n≥30, RMS≤0.3, \|F₀\|≤6. 호출 전에 정지를 확인 | 실패하면 START 실패 | [real.yaml:38-41](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/contact_scan_bringup/config/real.yaml#L38) | 새 START |
| L3-6 | [contact_detector.py:208-214](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/contact_detector/contact_detector/contact_detector.py#L208) | source=sim | F와 z를 가상값으로 교체(1차 OVER_FORCE 포함) | [sim.yaml:55,59](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/contact_scan_bringup/config/sim.yaml#L55) | — |
| L3-7 | [robot_manager.py:366-418](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/robot_manager/robot_manager/robot_manager.py#L366) | goal: 1개만, connected, 미확인 정지 요청(HOME은 예외), 값 검사 | REJECT(사유가 전달되지 않음) | — | — |
| L3-8 | [robot_manager.py:589-594](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/robot_manager/robot_manager/robot_manager.py#L589), [motions.py:75-79](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/robot_manager/robot_manager/motions.py#L75) | SLIDE에서 start_z − z > 5 mm(1차) | 정지, ROBOT_ERROR/DROP_LIMIT(205). z를 모르면 판정하지 않는다 | [real.yaml:81](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/contact_scan_bringup/config/real.yaml#L81) | — |
| L3-9 | [robot_manager.py:595-601](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/robot_manager/robot_manager/robot_manager.py#L595) | 경과 시간 > timeout | 정지 → TIMEOUT | 60 s | — |
| L3-10 | [robot_manager.py:602-604](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/robot_manager/robot_manager/robot_manager.py#L602) | connected=false | **정지 호출 없이** ROBOT_DISCONNECTED로 종료 | — | — |
| L3-11 | [robot_manager.py:608-642](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/robot_manager/robot_manager/robot_manager.py#L608) | !moving이고 (움직인 적 있음 또는 1 s 경과) | DESCEND는 NO_CONTACT, SLIDE는 NO_EDGE, MOVE_TO는 3 mm 거리 검사, **HOME은 검사 없이 성공** | arrival 1 s, 3 mm | — |
| L3-12 | [robot_manager.py:671-707](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/robot_manager/robot_manager/robot_manager.py#L671) | `/robot/stop` | connected일 때만 접수하고, 정지를 확인할 때까지 요청을 남긴다 | — | 정지 확인 또는 HOME |
| L3-13 | [robot_manager.py:752-776](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/robot_manager/robot_manager/robot_manager.py#L752), [:100](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/robot_manager/robot_manager/robot_manager.py#L100) | move_stop 뒤 !moving을 기다린다 | 확인하지 못하면 실패로 보고 | `stop_settle_s` 1.5는 **코드 기본값이고 yaml에 없다** | — |
| L3-14 | [robot_manager.py:433-445](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/robot_manager/robot_manager/robot_manager.py#L433) | goal의 모든 종료 경로 | `release_all` | — | — |
| L3-15 | [robot_manager.py:852-864](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/robot_manager/robot_manager/robot_manager.py#L852) | **프로세스 종료**(SIGINT, 크래시) | **정지도 해제도 하지 않는다** | — | — |
| L3-16 | [safety_core.py:123-139](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/safety_monitor/safety_monitor/safety_core.py#L123) | 2차 과대 외력: 원시 \|F\| > 30, 유효 샘플만 | STOP, 래치, `/robot/stop` | [real.yaml:49,51](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/contact_scan_bringup/config/real.yaml#L49) | reset |
| L3-17 | [safety_core.py:127-145](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/safety_monitor/safety_monitor/safety_core.py#L127) | 2차 하강 제한: OP_SLIDE 첫 유효 샘플 z 기준 5 mm | 위와 같음 | [real.yaml:50](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/contact_scan_bringup/config/real.yaml#L50) | reset |
| L3-18 | [safety_core.py:161-187](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/safety_monitor/safety_monitor/safety_core.py#L161) | 샘플 300 ms, 상태 500 ms 미수신. **한 번도 받지 못했으면 감시하지 않고**, 기동 후 3 s는 유예 | moving이면 STOP과 래치, 아니면 WARN | [real.yaml:52,59,63](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/contact_scan_bringup/config/real.yaml#L52) (sim은 500/1000) | 수신 재개 후 reset |
| L3-19 | [safety_monitor.py:164-171](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/safety_monitor/safety_monitor/safety_monitor.py#L164) | **새로 확정된** 조건만 처리 | 정지할지는 조건 종류 또는 **확정 순간의 moving**으로 정한다 | — | — |
| L3-20 | [safety_core.py:288-296](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/safety_monitor/safety_monitor/safety_core.py#L288) | `/safety/reset` | 활성 조건이 있으면 CONDITION_ACTIVE. 없으면 래치와 정지 추적을 지운다(정지 미확인이어도) | — | — |
| L3-21 | [safety_core.py:241-252](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/safety_monitor/safety_monitor/safety_core.py#L241) | 정지를 0.6 s 안에 확인하지 못함 | UNCONFIRMED, 2 s마다 재요청 | [real.yaml:66,70](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/contact_scan_bringup/config/real.yaml#L66) | 확인 |
| L3-22 | [safety_monitor.py:41-52](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/safety_monitor/safety_monitor/safety_monitor.py#L41) ↔ [정의서:1100-1107](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/docs/design/contact-scan-interface-spec-integrated-v1.2.md#L1100) | 속도, 작업영역, z 하한, heartbeat, latch_levels | **미구현** | TBD | — |
| L3-23 | [state_machine.py:326-335](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/scan_manager/scan_manager/state_machine.py#L326), [scan_manager.py:696-707](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/scan_manager/scan_manager/scan_manager.py#L696) | START: 휴지 phase, latched=false(수신함), connected(수신함), 필수 파라미터, 1·2차 값 일치 | SAFETY_LATCHED, ROBOT_DISCONNECTED, INVALID_VALUE, PARAM_SET_FAILED로 거절 | 좌표 2개는 **의도적으로 비워 둠**([real.yaml:148-158](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/contact_scan_bringup/config/real.yaml#L148)) | 조건이 해소되면 |
| L3-24 | [state_machine.py:310-324](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/scan_manager/scan_manager/state_machine.py#L310) | RESUME: STOPPED이고 재개점이 있으며 HOME 전 | ERROR와 HOME 뒤에는 NOT_SUPPORTED | 계약 TBD | 새 START |
| L3-25 | [scan_manager.py:810-833](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/scan_manager/scan_manager/scan_manager.py#L810) | HOME: 휴지 phase, connected, motion_timeout_s | 래치는 보지 않는다 | — | — |
| L3-26 | [sequence.py:348-355](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/scan_manager/scan_manager/sequence.py#L348), [:161-169](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/scan_manager/scan_manager/sequence.py#L161) | 모션 전 래치 확인, 우리가 요청하지 않은 정지 | FAILED(안전 사유 코드) → ERROR | — | — |
| L3-27 | [scan_manager.py:461-478](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/scan_manager/scan_manager/scan_manager.py#L461) | tare 전 정지 확인(요청 뒤에 찍힌 status로) | 실패하면 ROBOT_MOVING | 5 s | — |
| L3-28 | [sequence.py:154-158](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/scan_manager/scan_manager/sequence.py#L154) | compliance_released=false | FAILED | — | — |
| L3-29 | [scan_manager.py:1029-1065](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/scan_manager/scan_manager/scan_manager.py#L1029), [sequence.py:394-400](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/scan_manager/scan_manager/sequence.py#L394) | `/scan/stop` | STOPPING, `/robot/stop`, cancel → 5 s 안에 정지 확인 → STOPPED. 실패하면 ERROR(404) | [real.yaml:183](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/contact_scan_bringup/config/real.yaml#L183) | — |
| L3-30 | [sequence.py:90-101](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/scan_manager/scan_manager/sequence.py#L90), [ros-interfaces.md:652](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/docs/contracts/ros-interfaces.md#L652) | 방향 전환의 재접근은 OP_MOVE_TO | 접촉 판정이 없고, 보호는 과대 외력뿐이다 | recontact 1 mm, 2 mm/s | — |
| L3-31 | [propagation.py:56-59](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/scan_manager/scan_manager/propagation.py#L56), [test_config.py:20-23](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/contact_scan_bringup/test/test_config.py#L20) | over_force_n과 drop_limit_m 쌍 | yaml 정적 검사와 START 직전 되읽기로 비교 | — | — |

### L4: 통신·웹
| ID | 위치 | 조건 | 동작 | 값 | 해제 |
|---|---|---|---|---|---|
| L4-1 | [command_guard.py:54-103](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/mqtt_bridge/mqtt_bridge/command_guard.py#L54) | 필수 필드, UUIDv4, 중복(100개), 만료(stop은 제외) | cmd/ack로 거절 | 5 s | — |
| L4-2 | [main.py:395-396](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/backend/app/main.py#L395) ↔ [command_guard.py:56-57](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/mqtt_bridge/mqtt_bridge/command_guard.py#L56) | 만료 판정 = ROS PC 시계 − 웹 PC 시계 | 시계 차가 5 s를 넘으면 stop 외 명령이 전부 만료된다 | — | 시각 동기 |
| L4-3 | [mqtt_bridge.py:417-427](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/mqtt_bridge/mqtt_bridge/mqtt_bridge.py#L417), [:501-508](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/mqtt_bridge/mqtt_bridge/mqtt_bridge.py#L501) | stop 완료는 phase가 STOPPED일 때만 발행 | ERROR로 끝나거나 유휴일 때 온 stop은 완료가 발행되지 않는다 | — | — |
| L4-4 | [mqtt_bridge.py:312-324](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/mqtt_bridge/mqtt_bridge/mqtt_bridge.py#L312) | hb/web → `/web/heartbeat`, conn/web은 해석만 | **구독자가 없고, FastAPI도 hb/web을 보내지 않는다**(T33 포기, [daily/20260920.md:118](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/docs/test-reports/daily/20260920.md#L118)) | TBD | — |
| L4-5 | [contact_scan_qos:30](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/contact_scan_interfaces/contact_scan_qos/__init__.py#L30), [scan_manager.py:417-432](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/scan_manager/scan_manager/scan_manager.py#L417) | STATE = TRANSIENT_LOCAL depth 1 | 마지막 값을 **나이 확인 없이** 쓴다(→ #136에서 START·RESUME만 해소) | — | — |
| L4-6 | [App.jsx:47-62](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/frontend/src/App.jsx#L47), [:390-482](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/frontend/src/App.jsx#L390) | 웹 UI | safety/status를 표시하지 않고 reset 버튼도 없다(FastAPI 엔드포인트는 [main.py:501](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/backend/app/main.py#L501)에 있음) | — | — |
| L4-7 | [bringup.launch.py:52-63](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/contact_scan_bringup/launch/bringup.launch.py#L52), [real.yaml:186-187](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/contact_scan_bringup/config/real.yaml#L186) | mqtt_bridge 파라미터를 주입하지 않고, 설치 안 된 노드는 로그만 남기고 건너뛴다 | broker 127.0.0.1로 뜬다. safety_monitor가 빠져도 조용하다 | — | — |

---

## 3. 기능별 제약 충돌 지도

### F1 작업 시작 → tare → 윗면 하강
**경로:** React 시작 → FastAPI `/commands/scan/start` → MQTT `cmd/scan/start` → CommandGuard → `/scan/run` → `_begin_run`(상대 노드 되읽기, 쌍 비교) → `_accept_run` → `to_origin`(MOVE_TO) → `wait_still` → `/contact/tare` → `descend`(3 mm/s, 최대 120 mm) → CONTACT → robot_manager 대조와 `stop_robot` → Result → `wait_event`

**제약:** L4-1·2 → L3-23·31 → L3-7·L2-3 → L3-27·L2-2 → L3-5·L1-6 → L3-2·4 → L3-1·16·18 → L3-10·11

**예상 증상:**
1. **실기 START가 INVALID_VALUE로 거절된다.** 의도된 fail-safe다([real.yaml:148-158](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/contact_scan_bringup/config/real.yaml#L148)).
2. **정지 상태에서 tare를 잡으면 허공에서 거짓 CONTACT가 난다.** 큐브보다 45 mm 위에서 판정했다([realrobot-session:139](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/docs/test-reports/realrobot-session_20260921.md#L139)). 계약끼리도 충돌한다(§5-1). *→ #127로 해소(0-1절).*
3. **tare가 TARE_UNSTABLE 경계에 있다.** `tare_max_std_n` 0.3인데 정지 잡음이 0.29다([realrobot-session:134](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/docs/test-reports/realrobot-session_20260921.md#L134)).
4. **CONTACT가 늦고 과하게 나올 수 있다(L1-6, 가설).** 힘 값이 약 94 ms마다만 바뀌므로 디바운스 3회는 사실상 측정 1회다. 3 mm/s × 94 ms ≈ 0.28 mm를 더 내려간 뒤 판정하고, 새 탐침 강성 43 N/mm이면 약 12 N이 더 실린다(계산). 정황: z는 0.25 mm 바뀌었는데 F가 같은 줄이 있다([realrobot-session:184-188](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/docs/test-reports/realrobot-session_20260921.md#L184)).
5. **모션 경계의 샘플 공백으로 래치가 걸린다.** 실측 최대 공백은 358 ms(2026-09-21 실기, [realrobot-session:124-132](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/docs/test-reports/realrobot-session_20260921.md#L124))로, `sample_stale_ms` 300보다 길다. 여기에 robot_manager의 "모르면 moving=true"가 겹치면 SAMPLE_STALE → 래치 → `/robot/stop` → FAILED(403) → ERROR로 가고 재시작할 수 없다. **재현 A**(부록 A)로 확인했다.
6. **get_robot_state가 한 번만 시간 초과돼도 정지 없이 모션이 끝난다(L3-10).** 로봇은 최대 120 mm까지 계속 내려가고, 이때 오는 CONTACT와 OVER_FORCE는 motion=None이라 무시된다([robot_manager.py:348-356](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/robot_manager/robot_manager/robot_manager.py#L348)).

**상호작용:** 5는 A급 보수 규칙 두 개(모르면 이동 중, 이동 중 무소식은 정지)가 겹친 결과다. 기동 때 일어난 #99와 구조가 같다. `startup_grace_s`는 기동에만 적용된다.

### F2 순응 + −z 목표 힘 슬라이딩과 모서리 판정
**경로:** `_find_edge` → OP_SLIDE(5 mm/s, 60 mm) → `reject_reason`(마지막 위치 필요) → operation 태깅([robot_manager.py:426](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/robot_manager/robot_manager/robot_manager.py#L426)) → `start_slide_force` → move_line REL → `watch` → `stop_robot` → finally 해제

**제약:** L2-5·6·1, L3-3·4·8·17·1·16·18·19, L1-6

**예상 증상:**
1. **목표 3 N이 실제로는 약 8.3 N이다(REL, 추정).** 웹의 `target_force_n` 표시와 다르다.
2. **밀기 중 Fz가 0.3~1.3 N으로 읽힌다**([realrobot-session:115](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/docs/test-reports/realrobot-session_20260921.md#L115)). 조회값에 지령 힘이 섞이는 것으로 의심된다. 그렇다면 EDGE 누름 확인(1.5 N)이 성립하는지 불확실하다(가설). *→ #127이 EDGE 켜기를 z 기준으로 바꿨다.*
3. **느린 낙하(0.35 mm/s)가 추세선 0.5 s에 흡수된다.** 그래서 EDGE를 못 보고 60 mm까지 밀어 NO_EDGE로 끝난다([realrobot-session:117-118](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/docs/test-reports/realrobot-session_20260921.md#L117)). 안전 제약(추세 흡수)이 신호를 먹는 경우다. PR #128이 열려 있다.
4. **SLIDE 중 공백이 stale 100 ms를 넘으면 추세선이 리셋된다.** 약 0.5 s(≈2.5 mm) 동안 모서리를 볼 수 없다([detector_core.py:274-278](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/contact_detector/contact_detector/detector_core.py#L274), [realrobot-session:299-303](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/docs/test-reports/realrobot-session_20260921.md#L299)).
5. **"슬라이딩 시작 직후 정지"가 날 수 있다(가설).** 순응·힘을 켜는 Action 호출이 큐를 잡는 동안 샘플 조회를 건너뛴다([robot_manager.py:218-219](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/robot_manager/robot_manager/robot_manager.py#L218)). 공백이 300 ms를 넘고 moving=true면 SAMPLE_STALE 래치다. *→ #135 기록상 공백은 약 3 s 주기의 느린 응답이 주원인이어서 이 가설은 약해졌다.*
6. **하강 제한이 걸리면 1·2차가 같은 샘플에서 동시에 걸려 항상 래치된다(#53).** 그러면 ERROR로 끝나고 재시작할 수 없다(L3-24).
7. **정지(QSTOP) → release_force 램프 사이에 참조 외력이 점프할 수 있다**([dsr_client.py:117-126](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/robot_manager/robot_manager/dsr_client.py#L117)). 순서는 계약 TBD다. 실기 2회는 모두 released=true였다([api-check-log.md:18](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/docs/env/api-check-log.md#L18)).

### F3 작업 중지 (1 s KPI)
**경로:** `cmd/scan/stop`(만료 제외) → `/scan/stop` → STOPPING, `/robot/stop`, cancel → `watch`(20 ms 주기) → CallQueue → `move_stop` → !moving(≤1.5 s) → Result → finally 해제 → `wait_still`(≤5 s) → STOPPED → `scan/command_result`

**제약:** L4-1, L3-29·12·13·14·15, L2-1·2, L4-3

**시간 예산**(KPI 1 s, [BRD.md:348](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/docs/BRD.md#L348)): move_stop 응답 115~124 ms([api-check-log.md:17](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/docs/env/api-check-log.md#L17)). 실기 과대 외력 정지 0.5 s·2.2 mm([realrobot-session:94](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/docs/test-reports/realrobot-session_20260921.md#L94)), `/robot/stop` 정지 8.84 mm([realrobot-session:260](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/docs/test-reports/realrobot-session_20260921.md#L260)). "정지 확인"은 물리적으로 멈춘 뒤에도 0.3 s 창과 0.1 s 상태 주기만큼 더 걸린다.

**예상 증상:**
1. **큐가 막히면 KPI가 깨진다.** 앞선 호출이 응답하지 않으면 `move_stop`이 최대 5 s 기다린다. `call_sync`는 3 s에 포기해 ROBOT_ERROR를 내고, `move_stop`은 뒤늦게 나간다([robot_manager.py:820](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/robot_manager/robot_manager/robot_manager.py#L820)).
2. **Result가 늦어진다.** cancel과 `/robot/stop`이 같이 오면 move_stop을 두 번 보내고 정지도 두 번 기다린다([robot_manager.py:567-572](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/robot_manager/robot_manager/robot_manager.py#L567), [:737-750](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/robot_manager/robot_manager/robot_manager.py#L737)).
3. **정지 확인에 실패하면 ERROR(404)**가 되어 재시작할 수 없다.
4. **웹에 완료가 오지 않는 경우가 있다.** STOPPING에서 ERROR로 갔거나 유휴 중에 중지를 누른 경우다(L4-3).
5. **Ctrl+C는 정지가 아니다.** 노드는 죽어도 로봇은 계속 간다(sim에서 28.5 mm, [scan_sim README:66](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/docs/test-reports/data/20260921/scan_sim_t19b/README.md#L66)). 실기라면 순응·힘 제어가 켜진 채 남을 수 있다(L3-15, 가설).

### F4 안전 이상 정지 → 래치 → reset → 재시작
**경로:** safety_monitor 조건 확정 → `note`(래치) → `/robot/stop` → Result STOP_REQUESTED(안전 코드를 실음, [robot_manager.py:585-586](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/robot_manager/robot_manager/robot_manager.py#L585)) → `classify`는 우리가 요청하지 않은 정지로 보고 FAILED → **ERROR** → reset(웹 버튼 없음) → `/scan/resume` → **NOT_SUPPORTED**

**제약:** L3-16~21·24·26, L4-4·5·6

**예상 증상:**
1. **이 시나리오는 지금 구조로는 끝까지 갈 수 없다.** 안전 정지는 항상 ERROR로 끝나고([sequence.py:161-169](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/scan_manager/scan_manager/sequence.py#L161)), ERROR에서의 재시작은 TBD다([state_machine.py:311-314](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/scan_manager/scan_manager/state_machine.py#L311)). reset 뒤에 할 수 있는 것은 새 START뿐이다.
2. **CONDITION_ACTIVE가 이어질 수 있다.** 최신성 조건은 샘플이 다시 올 때까지, OVER_FORCE는 유효 샘플로 30 N 아래가 확인될 때까지 활성이다. 무효 샘플만 오면 그대로 남는다([safety_core.py:124-125](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/safety_monitor/safety_monitor/safety_core.py#L124)). 시험 기록에 실제 발생 사례는 없다.
3. **경쟁 조건(재현 B).** moving=false인 순간에 확정된 최신성 조건은 WARN만 남긴다. 곧 moving=true가 되면 level=STOP인데 latched=false, stop_required=false다. scan_manager는 latched만 보므로 계속 진행한다.
4. **safety_monitor가 죽어도 scan_manager는 마지막 `latched=false`를 믿는다.** 9/21 10:34에 실제로 일어났고, 그 뒤 하강과 SLIDE가 2차 감시 없이 돌았다([realrobot-session:122](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/docs/test-reports/realrobot-session_20260921.md#L122)). *→ #136으로 START·RESUME에서는 해소. 진행 중인 스캔은 로그만 남긴다.*
5. **reset이 정지 미확인(UNCONFIRMED) 상태에서도 성공한다.** 대신 robot_manager가 남은 정지 요청으로 막는다([robot_manager.py:388-393](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/robot_manager/robot_manager/robot_manager.py#L388)).
6. **사람이 탐침을 만지기만 해도 2차 과대 외력으로 래치된다.** 의도된 동작이고 세션 점검 중에 자주 볼 것이다. 그런데 웹에서는 래치를 볼 수도 풀 수도 없다.

### F5 안전복귀 (`/scan/home`)
**경로:** `cmd/scan/home`(만료 검사) → 휴지 phase만 허용(진행 중이면 BUSY) → `check_home` → connected 확인(래치는 무관) → OP_HOME(movej 20 deg/s) → 남은 정지 요청은 한 번 더 정지를 시도한 뒤 출발([robot_manager.py:460-470](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/robot_manager/robot_manager/robot_manager.py#L460)) → `watch`(정지 요청과 OVER_FORCE만 봄) → 도착

**제약:** L3-25·7·12·1·11, L4-1

**예상 증상:**
1. **스캔 중에는 BUSY다.** 중지 → STOPPED → 안전복귀 두 단계를 거쳐야 한다(규칙 3, A).
2. **탐침이 부재에 닿은 채 올림 없이 movej로 출발한다**([sequence.py:598-601](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/scan_manager/scan_manager/sequence.py#L598)). J6이 −204.84°라 크게 도는 경로가 나올 수 있고([real.yaml:79](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/contact_scan_bringup/config/real.yaml#L79)), 보호는 30 N뿐이다.
3. **도착을 검증하지 않는다.** 중간에 멈춰도 TARGET_REACHED로 끝나서 "복귀 완료"라고 보고한다([robot_manager.py:621-642](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/robot_manager/robot_manager/robot_manager.py#L621)).
4. **드라이버가 무응답(connected=false)이면 SW로 복귀할 수 없다(A).**

### F6 sim 입력원 / Virtual Mode
**경로:** 사람이 `sodvir` → `bringup source:=sim` → robot_manager가 Virtual을 조회 → contact_detector가 F와 z를 SimBox 값으로 교체 → 이벤트 → Virtual 로봇 정지

**제약:** L2-8, L3-6·18·10·15, L1-5

**공백:**
1. **2차 감시를 sim으로 검증할 수 없다.** safety_monitor는 원시 샘플(Virtual 힘 ≈0, z는 SLIDE 중 불변)을 본다. 그래서 2차 OVER_FORCE와 DROP_LIMIT, 1차 DROP_LIMIT, #53 동시 래치 모두 sim에서는 **절대 걸리지 않는다.**
2. **sim 낙하 속도가 실기와 140배 다르다.** sim은 50 mm/s([sim.yaml:59](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/contact_scan_bringup/config/sim.yaml#L59)), 실기는 0.35 mm/s다. sim에서 EDGE가 통과해도 실기 EDGE는 보장되지 않는다.
3. **sim의 최신성 한계가 real보다 느슨하다**(500/1000/200 vs 300/500/100). sim M2 통과가 실기의 래치 여유를 검증하지 않는다.
4. **에뮬레이터 부하(load > 16)면 드라이버가 무응답이 되고**, SAMPLE_STALE로 스캔이 중단된다([scan_sim README:68](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/docs/test-reports/data/20260921/scan_sim_t19b/README.md#L68)).
5. **특이 자세에서 move_line이 success를 돌려주고도 움직이지 않는다.** DESCEND와 SLIDE는 NO_CONTACT/NO_EDGE로 잘못 보고된다(L3-11).

---

## 4. 문제 목록 (우선순위순)

분류: **A** 필요한 안전 제약(유지) · **B** 과도하거나 문서와 불일치하거나 근거 없는 고정값 · **C** 안전 로직 버그 · **D** 계층 간 책임 중복·공백

| 순위 | ID | 분류 | 요약 | 영향 | 난이도 | 스냅샷 이후 |
|---|---|---|---|---|---|---|
| 1 | C-1 | C | 프로세스가 종료되면 정지·해제가 없다 | 실기 안전 구멍 | 중 | |
| 2 | C-2 | C | 연결이 한 번 흔들리면 정지 없이 모션이 끝난다 | 안전 구멍, F1·F2 | 하 | |
| 3 | D-1 | D | safety_monitor 생존을 확인하지 않는다 | 2차 감시 상실(실제 발생) | 하 | **#136 START·RESUME 해소** |
| 4 | D-2 | D | 두산 L1 상태가 안 보이고, 드라이버가 자동 복구한다 | 원인 추적 불가 | 중 | |
| 5 | B-1 | B | 정지 상태 tare가 계약끼리 충돌한다(#109) | 실기 START 차단 | 중 | **#127 해소** |
| 6 | B-2 | B | stale 300 ms < 실측 358 ms, moving 미상이면 래치 | F1·F2 중단 | 중 | #135 원인 계측 1단계 |
| 7 | C-3 | C | move_stop에 우선순위가 없다 | F3 KPI | 중 | #135 정량 근거 |
| 8 | C-7 | C | 힘 값이 10 Hz로 갱신돼 디바운스·최신성·지연 가정이 깨진다 | 판정 품질, overshoot | 중 | |
| 9 | B-5 | B | 30 N 대 탐침 밀림 43~46 N, 운용값이 yaml과 다르다 | 세션 무효 | 하 | |
| 10 | D-5 | D | 1·2차 동시 래치와 ERROR 재시작 TBD | F4 차단 | 팀 결정 | |
| 11 | C-4 | C | 최신성 판정 경쟁 조건 | 상태 불일치 | 하 | |
| 12 | C-5 | C | HOME 도착을 검증하지 않는다 | F5 오보 | 중 | |
| 13 | C-6 | C | L1 정지·명령 거절을 NO_CONTACT/NO_EDGE로 잘못 보고한다 | 원인 오인 | 하 | |
| 14 | B-6 | B | REL 목표 힘 3 N이 실제 약 8.3 N이다 | 누름 과다 | 팀 결정 | |
| 15 | D-7 | D | 웹에 안전 상태 표시와 reset 버튼이 없다 | F4 조작 불가 | 중 | |
| 16 | B-3 | B | `tare_max_std_n`이 잡음 경계에 있다 | tare 거절 | 하 | |
| 17 | B-4 | B | 안전 수치가 코드 기본값으로 박혀 있다 | 규칙 7 | 하 | |
| 18 | D-3 | D | web heartbeat를 아무도 감시하지 않는다 | 정책 TBD | 중 | |
| 19 | D-4 | D | 속도·작업영역·z 하한 감시가 없다 | 보호 공백 | 중 | |
| 20 | D-6 | D | 툴·TCP 등록을 확인하지 않는다 | 거짓 과대 외력, 좌표 오류 | 중 | |
| 21 | D-8 | D | sim으로 2차 감시를 시험할 수 없다 | 시험 공백 | 중 | |
| 22 | C-8 | C | 웹 stop 완료가 누락된다 | 표시 | 하 | |
| 23 | B-7 | B | moving 판정의 최소 속도가 약 0.7 mm/s다 | 느린 모션 오판 | 하 | |
| 24 | C-9 | C | 1차 하강 제한의 기준 z가 계약과 다르다 | 계약 불일치 | 하 | |
| 25 | C-10 | C | `travelled_m`이 모르는 값을 0.0으로 돌려준다 | 규칙 4 | 하 | |
| 26 | D-9 | D | mqtt_bridge 파라미터 미주입, PC 간 시계 차 | 연결·만료 | 하 | |

### 4.1 C. 안전 로직 버그
- **C-1 프로세스 종료 시 정지·해제 없음.**
  - 근거: `main`의 finally는 `destroy_node`만 한다([robot_manager.py:852-864](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/robot_manager/robot_manager/robot_manager.py#L852)). 해제는 goal의 finally에서 큐를 거쳐 하는데, context가 내려가면 응답이 오지 않는다([:810-823](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/robot_manager/robot_manager/robot_manager.py#L810)). 시험의 7개 경로에 프로세스 종료는 없다([test_node.py:641](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/robot_manager/test/test_node.py#L641)). sim에서 28.5 mm를 더 내려간 기록이 있다.
  - 영향: 규칙 2("모든 종료 경로")를 어긴다. SLIDE 중에 Ctrl+C를 누르면 힘 제어가 켜진 채 amovel이 계속될 수 있다(실기는 가설).
  - 개선: 종료 신호를 받으면 executor를 내리기 **전에** 전용 클라이언트로 `move_stop` → `release_force` → `release_compliance`를 시간 제한을 두고 동기로 부른다. 이 경로를 시험에 추가한다.
- **C-2 연결이 흔들리면 정지 없이 종료.**
  - 근거: [robot_manager.py:602-604](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/robot_manager/robot_manager/robot_manager.py#L602)는 `stop_robot`을 부르지 않는다. connected는 `get_robot_state` 한 번의 시간 초과로 false가 된다([:264-267](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/robot_manager/robot_manager/robot_manager.py#L264)). false인 동안 `/robot/stop`도 거절한다([:683-689](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/robot_manager/robot_manager/robot_manager.py#L683)).
  - 영향: DESCEND라면 최대 120 mm까지 감시 없이 내려간다.
  - 개선: 끊김 경로에서도 가능한 만큼 `move_stop`을 보내고 정지 확인까지 motion을 유지한다. connected는 N회 연속 실패로 판정한다. 확인하지 못했으면 멈췄다고 하지 않는 원칙은 그대로 둔다.
- **C-3 move_stop에 우선순위 없음.**
  - 근거: FIFO 큐이고 슬롯을 5 s까지 잡는다(L2-1). 드라이버는 move_stop만 별도 콜백 그룹에 둔다(`ws_dsr/…/dsr_controller2.cpp:2387`, `:2435`, 소스 확인[E18]). #135 기록상 평소에도 약 3 s마다 한 호출이 330~365 ms 늦다.
  - 개선: Virtual에서 동시 호출이 드라이버를 멈추지 않는지 먼저 확인한다. 그 뒤 move_stop을 새치기시키는 우선 경로를 둔다. 조회는 계속 직렬로 둔다.
- **C-4 최신성 판정 경쟁.** 정지 여부를 확정 순간에 한 번만 정한다([safety_monitor.py:164-171](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/safety_monitor/safety_monitor/safety_monitor.py#L164)). 반면 `level()`은 매번 계산한다([safety_core.py:271-280](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/safety_monitor/safety_monitor/safety_core.py#L271)). 재현 B로 확인했다. 개선: 매 주기에 "활성 최신성 조건 + moving=true"이면 한 번 정지를 요청하고 래치하도록 level과 같은 규칙을 쓴다.
- **C-5 HOME 도착 미검증.** [robot_manager.py:642](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/robot_manager/robot_manager/robot_manager.py#L642). 개선: 관절각이나 TCP를 목표와 비교해 허용치를 넘으면 ROBOT_ERROR로 낸다.
- **C-6 L1 정지를 NO_CONTACT/NO_EDGE로 오보.** 멈추기만 하면 명령한 만큼 갔다고 본다([:608-628](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/robot_manager/robot_manager/robot_manager.py#L608)). 개선: 이동 거리와 `max_distance`를 비교하고, robot_state를 함께 본다.
- **C-7 힘 10 Hz.**
  - 근거: L1-6과 부록 B. 계약은 `force_stamp`를 "응답 시각"으로 정의한다.
  - 영향: 디바운스 3회는 측정 약 1회다. `stale_age_ms`는 힘 데이터의 실제 나이를 보지 못한다. `detect_latency_s` 0.020 가정([real.yaml:162-167](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/contact_scan_bringup/config/real.yaml#L162))보다 실제 지연이 길다. 과대 외력의 overshoot도 커진다.
  - 개선: 값이 바뀔 때만 새 측정으로 세고, 디바운스를 ms 단위로 정의한다. 계약과 api-check-log에 기록한다. 임계값은 올리지 않는다.
- **C-8 웹 stop 완료 누락.** STOPPING을 벗어나는 모든 전이에서 완료를 발행하도록 제안한다.
- **C-9 1차 하강 제한 기준 z.** 코드는 실행 직전의 마지막 위치를 쓴다([robot_manager.py:423-424](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/robot_manager/robot_manager/robot_manager.py#L423)). 계약은 "OP_SLIDE 첫 샘플"이다([ros-interfaces.md:641](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/docs/contracts/ros-interfaces.md#L641)). 순응이 켜지면 z가 0.7 mm 올라오므로 차이가 생길 수 있다(가설).
- **C-10 `travelled_m`이 모르면 0.0.** [motions.py:68-72](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/robot_manager/robot_manager/motions.py#L68)가 Result의 `distance_travelled`에 들어간다. NaN이나 유효성 플래그로 바꿀 것을 제안한다.

### 4.2 D. 책임 중복·공백
- **D-1 safety_monitor 생존 미확인.** scan_manager가 캐시한 SafetyStatus를 나이 확인 없이 쓴다([scan_manager.py:422-432](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/scan_manager/scan_manager/scan_manager.py#L422)). *#136으로 START·RESUME은 해소.* 남은 것: 진행 중인 스캔 도중 감시자가 죽는 경우와, launch가 빠진 노드를 경고로 올리지 않는 것(L4-7).
- **D-2 L1 상태 비가시.** robot_state 3/5/6/9/10, `/dsr01/error`, `RobotStatus.error`(항상 False, [robot_manager.py:334-335](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/robot_manager/robot_manager/robot_manager.py#L334))가 모두 쓰이지 않는다. 여기에 드라이버 자동 복구(L1-2)까지 겹치면 보호 정지가 흔적 없이 지나갈 수 있다. 개선: 이 셋을 error와 error_code에 싣고, error면 goal을 거절한다. 드라이버 설정은 바꾸지 않는다.
- **D-5 1·2차 동시 래치 + ERROR 재시작 TBD.** 값, 기준, `confirm_n: 1`이 같아서 늘 둘이 함께 걸린다([real.yaml:57-58](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/contact_scan_bringup/config/real.yaml#L57)). 팀이 #53과 "이상 상태별 재시작 조건"([ros-interfaces.md:697](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/docs/contracts/ros-interfaces.md#L697))을 결정해야 F4가 열린다.
- **D-3 heartbeat.** 발행하는 쪽도 감시하는 쪽도 없다. 조치 정책도 TBD다([ros-interfaces.md:698](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/docs/contracts/ros-interfaces.md#L698)). 우선 표시하는 것부터 제안한다.
- **D-4 속도·작업영역·z 하한.** DESCEND의 보호는 목표 z뿐이다([real.yaml:139](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/contact_scan_bringup/config/real.yaml#L139)).
- **D-6 툴·TCP 등록.** robot_manager가 확인하지 않고 goal을 받는다([realrobot-session:212](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/docs/test-reports/realrobot-session_20260921.md#L212)).
- **D-7 웹 안전 UI.** safety/status 표시와 reset 버튼을 추가해야 한다.
- **D-8 sim에서 2차 감시.** 런타임은 바꾸지 말고, pytest에서 합성 `/robot/sample`을 넣어 시험하는 방식을 제안한다.
- **D-9 mqtt_bridge 파라미터와 PC 간 시계.** real.yaml에 mqtt_bridge 절을 추가하고, chrony 동기를 확인한다.

### 4.3 B. 과도하거나 불일치하거나 근거 없는 고정값
- **B-1** 정지 상태 tare. *#127로 해소.*
- **B-2** `sample_stale_ms` 300 < 실측 358 ms. 계약은 "한계를 올리기 전에 공백의 원인부터 없앤다"고 한다([ros-interfaces.md:601-604](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/docs/contracts/ros-interfaces.md#L601)). **값은 올리지 않는다.** #135가 원인(약 3 s 주기의 느린 응답)을 계측하기 시작했다.
- **B-5** 30 N인데 탐침은 43 N과 46 N에서 홀더 안으로 밀렸다([units-frames.md:72](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/docs/contracts/units-frames.md#L72)). 정지에는 0.5 s가 걸린다. 9/21 세션에서는 15 N과 10 N으로 낮춰 운용했지만([realrobot-session:94](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/docs/test-reports/realrobot-session_20260921.md#L94), [:211](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/docs/test-reports/realrobot-session_20260921.md#L211)) yaml은 30 N 그대로다. overshoot를 실측해 근거와 함께 yaml에 적는다.
- **B-6** REL과 ABS 중 무엇을 쓸지는 #73에서 결정한다.
- **B-3** `tare_max_std_n`은 실측 분포를 근거로 다시 정한다. 근거 없이 올리는 것이 아니다.
- **B-4** `stop_settle_s` 1.5(계약은 `stop_timeout_s` 1.0, [정의서:1076](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/docs/design/contact-scan-interface-spec-integrated-v1.2.md#L1076)), robot_manager의 `motion_timeout_s` 60, `abandon_after_s` 5.0, `LOOP_PERIOD_S`를 yaml로 옮긴다.
- **B-7** moving 최소 속도가 약 0.7 mm/s다(재현 C). 파라미터 검사에서 속도가 이 값보다 충분히 큰지 확인하고, 이 관계를 문서에 적는다.

### 4.4 A. 유지해야 할 제약 (개발 편의만 제안)

| ID | 제약 | 근거 | 편의 방안 |
|---|---|---|---|
| A-1 | 좌표가 없으면 START 거절 | [real.yaml:123-124](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/contact_scan_bringup/config/real.yaml#L123) | 빠진 이름이 거절 detail에 이미 실린다. 웹 로그에서 보이게만 한다 |
| A-2 | 1·2차 값이 다르면 START 거절 | [scan_manager.py:699-706](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/scan_manager/scan_manager/scan_manager.py#L699) | 어긋난 값을 웹에 표시한다 |
| A-3 | 미확인 정지 요청이 있으면 goal 거절 | [robot_manager.py:388-393](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/robot_manager/robot_manager/robot_manager.py#L388) | RobotStatus.detail에 남은 요청을 표시한다 |
| A-4 | SLIDE는 시작 z가 있어야 함 | [robot_manager.py:403-404](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/robot_manager/robot_manager/robot_manager.py#L403) | — |
| A-5 | compliance_released=false면 중단 | [sequence.py:154-158](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/scan_manager/scan_manager/sequence.py#L154) | — |
| A-6 | 래치는 reset으로만, 조건 해소를 확인 | [safety_core.py:288-296](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/safety_monitor/safety_monitor/safety_core.py#L288) | detail의 활성 조건을 웹에 표시한다 |
| A-7 | 모르면 moving=true | [motion_state.py:34-37](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/robot_manager/robot_manager/motion_state.py#L34) | B-2의 원인이지만 유지한다 |
| A-8 | 중지·복귀·재시작은 서로 독립 | [state_machine.py:13-15](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/scan_manager/scan_manager/state_machine.py#L13) | — |
| A-9 | stop은 만료 검사에서 제외 | [command_guard.py:96-97](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/mqtt_bridge/mqtt_bridge/command_guard.py#L96) | — |
| A-10 | HOME은 래치와 무관(#115) | — | — |
| A-11 | 과대 외력은 기동 유예 없음 | [safety_core.py:165-168](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/safety_monitor/safety_monitor/safety_core.py#L165) | — |

### 4.5 재현·확인 절차
**실행 주체.** Virtual과 sim은 사람이나 Claude가 실행할 수 있다. **실기는 사람이 직접 하고, 입회자가 비상정지 앞에서 대기한다.**

```bash
# sim: T1 sodvir → T2
cd ws_cobot1 && source install/setup.bash && ros2 launch contact_scan_bringup bringup.launch.py source:=sim
ros2 topic echo /safety/status     # level, latched, reason_code, stop_required/confirmed, detail
ros2 topic echo /robot/status      # connected, moving, compliance_active, force_ctrl_active
ros2 topic echo /contact/event ; ros2 topic echo /scan/state ; ros2 topic echo /dsr01/error
ros2 bag record /robot/sample /robot/status /safety/status /scan/state /contact/event /scan/log
```
**로그 키워드:**
- robot_manager: `응답 시간 초과`, `기다리다 포기`, `로봇 상태 조회 시간 초과`, `로봇 연결이 끊겼다`, `멈춤을 확인하지 못했다`, `응답 … ms (>`(#135)
- safety_monitor: `SAMPLE_STALE`, `정지 중이라 경고만`, `/safety/reset 거절`
- contact_detector: `샘플 간격`, `추세선을 버리고`, `묵었다. 버린다`

| 가설 | 절차 | 기대 관찰 | 진단 로그 제안(제안만) |
|---|---|---|---|
| B-2 / C-4 | **오프라인 재현 완료**([부록 A](#부록-a-오프라인-재현-스크립트), real.yaml 값) | A) 359 ms 공백이고 moving=true면 `STOP, latched=True`. B) 확정 순간 moving=false였다가 이후 true면 `STOP, latched=False, stop_required=False` | [robot_manager.py:218](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/robot_manager/robot_manager/robot_manager.py#L218)에서 조회를 건너뛸 때 현재 호출의 label과 경과 시간을 남긴다(#135로 일부 대체) |
| B-2(실측) | 9/21 bag에서 sample_id 간격이 300 ms를 넘는 곳을 `/robot/status.operation` 전이 시각과 비교 | 공백이 모션 경계나 약 3 s 주기의 느린 응답과 겹침 | 위와 같음 |
| B-7 | **오프라인 재현 완료**(부록 A) | 0.35·0.6·0.7 mm/s → moving=False, 2 mm/s → True | — |
| C-7 | **분석 완료**(2026-09-20 CSV, 부록 B). 같은 분석을 9/21 bag에도 적용 | 값 갱신 간격 약 94 ms | contact_detector에서 힘 값이 반복된 횟수를 센다 |
| C-1 | sim에서 DESCEND 중에 bringup을 Ctrl+C하고 `get_current_posx`를 반복 조회 | z가 계속 내려감(기록된 28.5 mm) | 종료 경로에 로그를 남긴다 |
| C-2 | pytest의 `_slide_rig` 패턴으로 watch 도중 `connected=False`를 주입 | `stop_robot`이 불리지 않음 | 로그에 `정지:` 없이 `ROBOT_DISCONNECTED`가 찍힘 |
| C-3 | Virtual에서 정지를 20회 반복하며 move_stop의 submit부터 send까지 시간을 측정 | 분포와 꼬리 | [call_queue.py:35-53](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/robot_manager/robot_manager/call_queue.py#L35)에 label과 대기 ms를 DEBUG로 남긴다 |
| C-5 / C-6 / D-2 | **Virtual에서만** DESCEND나 HOME 도중 다른 터미널에서 `motion/move_stop`을 직접 호출하고, `system/servo_off`로 SAFE_OFF를 유도 | NO_CONTACT 오보, HOME은 TARGET_REACHED. `/robot/status`는 connected=true, error=false. 드라이버가 자동으로 서보 온 | [robot_manager.py:248](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/robot_manager/robot_manager/robot_manager.py#L248)에서 robot_state 값을 남긴다 |
| D-1 | (#136 뒤) sim에서 스캔 도중 `pkill -INT -f safety_monitor` | 스캔은 계속되고 `/scan/log`에 끊김 WARN | — |
| C-8 | sim IDLE에서 중지를 보내고 `mosquitto_sub -t scan/command_result -v` | 해당 request_id가 오지 않음 | — |
| L4-2 | 두 PC에서 `date +%s%3N`을 비교하고 `chronyc tracking` 확인 | 차이가 5 s를 넘으면 start/home/reset이 `command expired` | — |
| B-5 | (실기, 사람) OVER_FORCE 사건 bag에서 이벤트 전후의 최대 \|F\| | overshoot = 최대값 − over_force_n | — |

---

## 5. 문서와 코드의 불일치

| # | 문서 | 코드·실측 |
|---|---|---|
| 1 | tare는 "무접촉·정지"이고 moving=false를 확인([ros-interfaces.md:45](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/docs/contracts/ros-interfaces.md#L45), [:374](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/docs/contracts/ros-interfaces.md#L374)) ↔ "하강과 같은 운동 상태"([units-frames.md:66](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/docs/contracts/units-frames.md#L66)) | 코드는 정지 상태 tare다([sequence.py:448-461](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/scan_manager/scan_manager/sequence.py#L448)). 계약끼리 충돌한다. *→ #127(계약 v0.1.12)로 정리* |
| 2 | 1차 하강 기준 = OP_SLIDE 첫 샘플([:641](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/docs/contracts/ros-interfaces.md#L641)) | 실행 직전의 마지막 위치(C-9) |
| 3 | `stop_timeout_s` 1.0([정의서:1076](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/docs/design/contact-scan-interface-spec-integrated-v1.2.md#L1076)) | `stop_settle_s` 1.5, 코드 기본값 |
| 4 | safety_monitor 감시 항목에 속도·작업영역·연결·heartbeat·latch_levels 포함([BRD.md:300](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/docs/BRD.md#L300), [정의서:1100-1107](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/docs/design/contact-scan-interface-spec-integrated-v1.2.md#L1100)) | 4종만 구현([safety_core.py:3-7](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/ws_cobot1/src/safety_monitor/safety_monitor/safety_core.py#L3)) |
| 5 | FastAPI가 hb/web을 발행하고 safety_monitor가 구독(정의서 3.8) | 둘 다 없다 |
| 6 | `home_pose`, m·rad | `home_joint_deg`, deg |
| 7 | OVER_FORCE도 같은 판정 정의(N=3, [:156](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/docs/contracts/ros-interfaces.md#L156)) | `over_force_debounce_n: 1`(계약에 없는 파라미터) |
| 8 | `force_stamp` = 응답 시각을 최신성의 근거로 씀 | 실제 힘 데이터는 약 94 ms 묵어 있을 수 있다(C-7) |
| 9 | `sample_stale_ms` 100(정의서 제안) / 300(계약 본문) / TBD(BRD) | yaml 300, 실측 공백 358 ms |
| 10 | `RobotStatus.error`, `error_code` 필드가 있음 | 항상 False/OK |
| 11 | `/scan/home`의 래치·연결 전제조건은 명시 없음 | 코드는 connected를 요구하고 래치는 무시 |
| 12 | stop 완료 = STOPPED | ERROR 경로는 정의가 없다(C-8) |
| 13 | mqtt_bridge 파라미터 `downsample_hz`, `hb_ros_hz` 등 | `sample_publish_hz`, `heartbeat_hz` 등 |
| 14 | 이벤트 대조 키 = scan_id + motion_id(정의서 962, 노드 구성도 173) | motion_id + operation(계약과 코드) |
| 15 | BRD 시나리오: 안전 정지 → reset → 재시작 | ERROR에서는 NOT_SUPPORTED(계약 TBD) |
| 16 | yaml `over_force_n` 30 N | 9/21 실기에서는 15 N과 10 N으로 운용 |
| 17 | `RobotStatus.moving` 근거 "TBD"([:115](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/docs/contracts/ros-interfaces.md#L115)) | 같은 문서 [:688](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/docs/contracts/ros-interfaces.md#L688)은 "T15에서 정했다" |
| 18 | 지시문: BRD v3.1.0, 정의서 v1.1, 노드 구성도 v1.0 | 저장소: v3.2.0, v1.2, v1.1 |

---

## 6. 확인하지 못한 가설과 실기·팀 확인 항목

| 항목 | 상태 | 확인 방법 · 주체 |
|---|---|---|
| 충돌 감지 민감도, TCP 힘·속도 한계, 안전 구역, 정지 범주, 수동 모드 250 mm/s | 저장소에 기록 없음 | 펜던트의 안전 설정 화면을 사진이나 값으로 `docs/env`에 기록 (사람) |
| DESCEND 접촉(43 N/mm)에서 충돌 감지가 걸리는지, 걸리면 어느 상태가 되는지 | 미확인 | `/dsr01/error`를 bag에 기록하고 펜던트 알람 로그 확인 (실기, 사람) |
| 실기에서도 드라이버가 자동 복구하는지(제어권이 있을 때만 동작) | 소스 확인[E18]만 | Virtual에서 servo_off로 먼저 확인하고, 실기는 사람 |
| move_stop을 다른 호출과 동시에 보내도 안전한지 | 미확인 | Virtual 실험 |
| 프로세스가 종료된 뒤 순응·힘 제어가 켜진 채 남는지 | 미확인 | `aux_control/get_control_mode`(`ws_dsr/…/dsr_controller2.cpp:2452`) (실기, 사람) |
| 힘 제어 중 조회값에 지령 힘이 섞이는지 | 추정 | 허공에서 SLIDE를 하며 Fz 기록 (실기, 사람) |
| robot_manager 50 Hz 경로에서도 힘이 10 Hz로 갱신되는지 | 2026-09-20 기록기로만 확인 | 9/21 bag에 부록 B 분석 적용 (오프라인) |
| 샘플 공백의 원인 | #135로 1단계 계측 | 어느 서비스가 약 3 s마다 늦는지 (#130) |
| 팀 결정이 필요한 것 | 열림 | 힘 꺾임 EDGE(#128), 동시 래치(#53), REL/ABS(#73), ERROR 재시작 정책, 홈 경로(올림 먼저?), heartbeat 정책, PC 간 시각 동기 |

---

## 부록 A. 오프라인 재현 스크립트

ROS와 로봇 없이 레포 루트에서 `python3 repro.py`로 돈다. 값은 `real.yaml`(c9de11e)이다. 2026-09-21 결과는 아래 주석과 같다.

```python
import sys
from collections import deque
sys.path.insert(0, 'ws_cobot1/src/safety_monitor')
sys.path.insert(0, 'ws_cobot1/src/robot_manager')
from safety_monitor.safety_core import SafetyLimits, SafetyState, StopTracker
from robot_manager import motion_state

L = SafetyLimits(30.0, 0.005, 300, 500, 1, 3.0)   # over_force, drop_limit, sample_stale_ms, status_timeout_ms, confirm_n, grace

def run(moving_at_detect, moving_later):
    s = SafetyState(L, StopTracker(0.6, 2.0))
    s.moving = moving_at_detect
    found = s.watch.check_freshness(now_s=10.0, last_sample_s=10.0 - 0.359, last_status_s=9.95, uptime_s=10.0)
    for c in found:                        # safety_monitor.react 와 같은 규칙
        if c.stops or s.moving:
            s.note(c); s.stop.request(10.0)
    s.moving = moving_later
    return s.level().name, s.latched, s.stop.required

print('A', run(True, True))    # ('STOP', True, True)    359 ms 공백 + moving=true → 래치
print('B', run(False, True))   # ('STOP', False, False)  확정 순간 moving=false → level 만 STOP

def moving_at(speed_mps, hz=42.8):
    pos = deque()
    for i in range(int(hz)):
        t = i / hz
        pos.append((t, (0.0, 0.0, -speed_mps * t)))
        motion_state.trim(pos, t, 0.3)
    return motion_state.is_moving(pos, 0.0002, 0.3)

for v in (0.00035, 0.0006, 0.0007, 0.002, 0.003):
    print('C', v * 1000, 'mm/s', moving_at(v))  # 0.35·0.6·0.7 → False, 2·3 → True
```

## 부록 B. 외력 값 갱신 간격 분석

원본: `data/20260920/idle_30s.csv`(홈 정지 30 s), `data/20260920/descend_01.csv`. 둘 다 2026-09-20 실기 기록기 단독이다. 레포 루트에서 실행한다.

```python
import csv
from collections import Counter
for fn in ('idle_30s.csv', 'descend_01.csv'):
    rows = [r for r in csv.DictReader(open(f'docs/test-reports/data/20260920/{fn}')) if r['valid'] == '1']
    F = [(r['fx_n'], r['fy_n'], r['fz_n']) for r in rows]
    T = [float(r['t_force_s']) for r in rows]
    runs, c, starts = [], 1, [T[0]]
    for i in range(1, len(F)):
        if F[i] == F[i - 1]:
            c += 1
        else:
            runs.append(c); c = 1; starts.append(T[i])
    runs.append(c)
    d = sorted(b - a for a, b in zip(starts, starts[1:]))
    print(fn, len(F), sorted(Counter(runs).items()),
          'median %.0f ms, p95 %.0f ms, max %.0f ms' % (1000 * d[len(d) // 2], 1000 * d[int(len(d) * .95)], 1000 * d[-1]))
```

| 파일 | 유효 샘플 | 같은 값 연속 길이 | 서로 다른 값 사이 간격 |
|---|---|---|---|
| `idle_30s.csv` | 1282 | 4회 219번, 5회 81번 | 중앙 94 ms, p95 118 ms, 최대 121 ms |
| `descend_01.csv` | 711 | 4회 118번, 5회 47번 | 중앙 94 ms, p95 118 ms, 최대 121 ms |

`descend_01.csv`는 z 범위가 0.07 mm라 이동 중의 위치 갱신은 이 파일로 판단할 수 없다. 이동 중에 위치가 힘보다 자주 바뀐다는 정황은 [realrobot-session:184-188](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/c9de11e053b52c921b9ef73e26307ba38059a64b/docs/test-reports/realrobot-session_20260921.md#L184)에 있다.
