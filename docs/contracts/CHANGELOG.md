# 계약 변경 이력

형식: `버전 (날짜, PR) - 무엇을 왜. 영향받는 모듈`

## v0.1.21 (2026-09-23, T06 감사 후 팀 결정 10건 + 2차 하강 제한 재결정)
**타입 변경 있음**(번호 · 필드 **추가**만. 기존 번호 · 필드는 그대로다): `ReasonCode` 에 `STOP_UNCONFIRMED(407)`, `RobotStatus` 에 SLIDE 누름 목표 6개(`slide_mode` · `slide_force_setpoint_n` · `slide_force_baseline_n` · `slide_force_estimate_n` · `step_press_lo_n` · `step_press_hi_n`). 영향: scan_manager(재시작 허용 목록 · 안전복귀 경로) · safety_monitor(2차 하강 제한 여유 · 최신성 500 ms) · robot_manager(1차 하강 제한 기준 z · 상태의 누름 세 값) · mqtt_bridge(`robot/status` JSON 6개) · contact_detector(문서만).

입력: `docs/test-reports/safety-audit-review_20260922.md`(§7 "팀 결정이 필요한 항목" 10건)과 그 입력이 된 감사 보고서(PR #144, 아직 병합되지 않았다). 결정 전문과 근거는 `docs/decisions/0004-safety-audit-decisions.md` 에 있다.

- **결정 1 · ERROR 재시작(9장 TBD 해소).** `ERROR` 로 끝난 작업은 **허용 목록**(`SAMPLE_STALE 403` · `ROBOT_STATUS_LOST 404` · `STOP_UNCONFIRMED 407`)일 때만 `/safety/reset` 뒤 `/scan/resume` 을 받는다. `OVER_FORCE` · `DROP_LIMIT` · 알 수 없는 오류 · **목록에 없는 새 사유**는 `NOT_SUPPORTED` 로 거절하고 새 START 만 가능하다. 자동 재개는 없다. 기존 관문(래치 · 상태 최신성 · 연결)은 그대로 본다. "정지 미확인"이 `ROBOT_STATUS_LOST(404)` 에 섞여 있던 것을 새 코드 **407** 로 갈랐다 — 허용 목록을 사유로 판단하려면 사유가 갈려 있어야 한다
- **결정 2 재결정 (2026-09-23) · 2차 한계 9 → 10 mm.** 간섭 거리 **D = 그리퍼 밖 탐침 길이 12 mm**(자로 실측, 현지 · 학민 · 병후)를 새로 재어, `drop_limit_margin_m` 을 0.004 → **0.005**(2차 = 10 mm)로 바꿨다. 옛 9 mm 와 "탐침 길이를 손으로 재어 정했다"는 근거 문구는 사실이 아니었다(정정). 남는 조건 둘 다 **미측정**이다: 상한 `L2 + O2 < D`(O2 < 2 mm) · 하한 `5 + O1 < L2`(O1 < 5 mm). O 를 지배하는 것은 관성이 아니라 힘 제어이고(9/22 실기 1123: 정지 뒤 z 가 2.8 mm 내려감, #152 · PR #156 이 고쳤다), **이 값은 힘 제어가 없는 step 모드 기준이다.** 되돌릴 조건과 D 재측정 규칙은 `ros-interfaces.md` 7.2 · ADR 0004 결정 2 에 적었다.
- **결정 2 · 하강 제한 여유(7.2, #53).** `drop_limit_m` 은 두 노드가 **같은 값**(쌍 검사 유지). safety_monitor 에만 `drop_limit_margin_m`(계약 이름 아님, `ScanConfig` 에 없음)을 두어 2차 한계를 `drop_limit_m + margin` 으로 한다. real · sim 모두 1차 5 mm · 2차 **10 mm**(9/22 결정은 9 mm 였고 9/23 에 재결정했다 — 아래 항목). `SetConfig` 가 두 노드의 `drop_limit_m` 을 같은 값으로 덮어도 여유는 남는다. `confirm_n` 으로 늦추지 않는다
  - **선행 조건이었던 기준 z 통일을 같이 했다(C-9).** robot_manager 의 1차 기준 z 를 "실행 직전의 마지막 위치"에서 **"자기가 `OP_SLIDE` 로 발행한 첫 유효 샘플의 z"** 로 바꿨다. safety_monitor 가 잡는 것과 **같은 메시지의 같은 값**이다. 순응을 켜면 z 가 약 0.7 mm 올라와 두 기준이 어긋나 있었다
- **결정 3 · 최신성(6.3 예외).** **이 항목만 시연 전에 v0.1.16(#168)로 먼저 나갔다.** real 의 `sample_stale_ms` 300 → **500**. #130 에서 316~365 ms 공백이 반복돼 goal 의 약 40 %가 `SAMPLE_STALE` 로 멈췄다. 500 이면 기록된 공백 14개 중 687 ms 하나만 걸린다. **700 은 지금 올리지 않는다**(데이터가 쌓이면 검토만). #130 원인이 풀리면 300 으로 되돌린다. "한계보다 원인이 먼저"라는 지침의 예외임을 6.3 에 적었다
- **결정 4 · force/REL 표시.** `force` 모드의 누름은 설정 증분(`slide_target_force_n`, `DR_FC_MOD_REL`) · SLIDE 시작 기준 Fz · 추정 최종 힘(둘의 합) **세 값이 다른 것**이다. 자유 문자열에 섞지 않고 `RobotStatus` 필드로 갈라 싣는다. 추정값은 이름으로 추정임을 밝힌다(`slide_force_estimate_n`). **`step` 모드에서는 세 값이 NaN** 이고 목표 누름 띠(`step_press_lo_n` · `step_press_hi_n`)를 싣는다. 실기 기본은 `step`, sim 은 `force`
- **결정 5 · EDGE.** PR #160(v0.1.15)의 스텝 모드 방식을 승인한다. 이 버전에서 로직을 바꾸지 않았다
- **결정 6 · 중지 KPI(7.1).** **물리 정지 1 s 이내**(BRD 9장 그대로)와 **STOPPED 표시 3 s 이내**(신설)를 나눴다. 물리 정지에 3 s 를 허용하는 표현은 두지 않는다. 물리 정지 시간은 bag · 실기로만 판정한다
- **결정 7 · 안전복귀(7.5 신설, 9장 TBD 해소).** 위치 확인 → 손상 의심 확인 → 수직 올림 → **도착 확인** → `OP_HOME`. 위치 불명 · 올림 실패 · 손상 의심(`OVER_FORCE` · `DROP_LIMIT` · `OUT_OF_WORKSPACE`)이면 HOME 을 보내지 않고 사람이 펜던트로 조그한다. #130 에서 올림이 실패했는데 HOME 이 나간 사례가 2회 있었다. 올림도 래치를 보지 않는다
- **결정 8 · 과대 외력.** 전역 `over_force_n` **30 N 유지**. 스텝 모드의 `step_max_force_n` 12 N 은 **다른 것**(알고리즘이 스스로 들고 중단하는 로컬 보호)이며 그대로 둔다. 7.2 에 둘의 차이를 적고, real.yaml 의 "over_force_n(15)" 주석을 30 으로 바로잡았다
- **결정 9 · 디바운스(3.3).** `debounce_n = 3` **현행 유지**. 다만 `get_tool_force` 가 약 10 Hz 로만 갱신되므로 "연속 샘플 3회"가 독립 측정 3회가 아니라는 사실을 적었다. "값 변화 3회"로 바꾸지 않는다(오프라인 계산에서 판정 순간 참 힘 중앙 34.8 N). 스텝 모드의 "멈춘 뒤 새 샘플만 평균 · `debounce_count = 1`" 은 별개라고 명시했다
- **결정 10 · #141 기준점.** 작업환경 물리 재구성으로 해결. **수치는 바꾸지 않았다** — 확정된 새 실측값이 레포 · 이슈 · PR 어디에도 없어 추측하지 않는다

## v0.1.20 (2026-09-23, T41 · #179)
`mqtt-schema.md`의 M0609/RG2 표시용 관절 스트림을 발행원 기준으로 분리했다. 영향: mqtt_bridge · frontend · mock_publisher.
- 실측 종단에서 `/dsr01/joint_states` publisher가 2개임을 확인했다: `/dsr01/joint_state_broadcaster`는 M0609 J1~J6 6축, `/dsr01/joint_state_publisher`는 M0609 6축 + RG2 6축 합성 스냅샷
- `robot/joints`는 정확히 M0609 6축인 스냅샷만 사용한다. 12축 합성 메시지가 M0609 웹 자세를 번갈아 덮지 않게 한다
- 새 `robot/gripper_joints`는 합성 스냅샷에서 RG2 6축만 추려 QoS 0 · retain=false로 발행한다
- 두 토픽 모두 표시 전용이다. 로봇/그리퍼 제어 입력으로 사용하지 않는다
- 9/23 실기 통합값을 동결점에 반영: real `tare_max_std_n=1.0`(tare RMS 0.636~0.813 N에서 0.3 N이 두 번 TARE_UNSTABLE), `step_release_n=2.5`(1.5 N에서 F0 치우침으로 윗면 위 거짓 접촉 후 −y no_contact(204)). sim은 가상 외력이므로 기존 0.3 N을 유지한다
- 웹 모델은 pinned M0609 URDF의 `link_6 -> tool0` 고정 RPY와 m0609_rg2_bringup의 `tool0 -> rg2_base_link` 장착 RPY를 반영한다

## v0.1.19 (2026-09-23, T41 · #179)
`mqtt-schema.md`에 웹 M0609 디지털 트윈 표시용 **`robot/joints`**를 추가했다. 영향: mqtt_bridge · FastAPI(`robot/#` 기존 구독으로 자동 전달) · frontend · mock_publisher.
- ROS 원본은 Doosan `joint_state_broadcaster`의 `/dsr01/joint_states` (`sensor_msgs/JointState`). mqtt_bridge가 기본 20 Hz로 다운샘플해 QoS 0 · retain=false로 발행한다
- payload는 `names[]`와 같은 인덱스의 `positions_rad[]`, `stamp_ms`, `published_at_ms`를 가진다. 자세 quaternion 규칙은 그대로이며 관절각만 rad 예외로 추가한다
- `robot/joints`는 **표시 전용**이다. 웹에서 역으로 로봇 제어에 사용하지 않는다
- RG2는 현재 탐침 고정 파지 운용이라 웹에서는 고정 자세로 표시한다. RG2 폭 피드백 토픽 계약은 추가하지 않았다

## v0.1.18 (2026-09-23, #147 · #142 새 작업대 · 새 홈 · 좌표 잠정)
**타입 변경 없음.** 2026-09-22 작업대 교체(눌림 발견) 뒤 학민 실측값으로 `units-frames.md` 와 real 값을 바꾼다. **좌표 계열은 잠정**(z=0 1 점, 테이프 두께 · 부재 캘리퍼 미확정)이고, 확정되면 `support_z_m` · z=0 두 줄만 후속으로 고친다.
- 홈 관절각 **[-21.19, 15.24, 52.97, -0.08, 111.80, -15.14] deg**(J6 을 ±180° 안으로). 옛 홈과 그 팁 좌표 · 높이는 무효. 홈은 좌표 기준이 아니다
- z=0 **95.006 mm**(1 점, (524.97, −172.03)). 탐침 상태 전제조건의 기준점 · 기준값도 같이 바꿨다
- 작업대 원점 **(420.255, −156.675, 95.006)** = 부재 윗면 중심 + 작업대 표면. `search_origin_pose` = 그 위 윗면 + 40 mm(218.0), 자세는 새 홈(수직). `max_descend_m` 0.120 → 0.050
- 팁 반지름 0.225 → **약 2 mm**(9/21 교체분, 캘리퍼 확정 전). 교체 절차의 "같은 제품이라 그대로" 가정이 틀렸음을 적었다. TCP [0, 0, 252.12] 는 유지(탐침을 9/21 뒤 바꾸지 않았다)
- `support_z_m` 0 → 0.002(테이프 두께 잠정). real `detect_latency_s` 0.020 → 0.0(스텝 모드는 멈춘 뒤 EDGE 확정, v0.1.15 7.2 후속)
- 세션 시작 점검 2 에 **START 전 툴 · TCP 등록 확인 두 줄**을 넣었다(2026-09-23 등록 누락 비상정지 2 회)
- 배치 원칙 1 · 2 · 6 은 바뀌었다는 표시만 하고 #147 에서 다시 쓴다
영향: robot_manager(`home_joint_deg`) · scan_manager(좌표 · 편향 보정, real 값만). 번호: #161 은 v0.1.21 이다(#179 가 v0.1.19 · v0.1.20 을 쓴다).

## v0.1.16 (2026-09-23, #130 최신성 한계)
**타입 변경 없음.** real 의 `sample_stale_ms` 를 300 → 500 으로 올렸다(6.3절). 6.3 의 "한계를 올리기 전에 원인을 없앤다"는 원칙의 **예외**이며, 이유 · 남는 위험(687 ms 공백) · 되돌릴 조건을 6.3 과 real.yaml 주석에 같이 남겼다. 코드 기본값과 sim 값은 바꾸지 않았다(sim 은 이미 500). 영향: safety_monitor(실기 값만).

## v0.1.15 (2026-09-22, SLIDE 스텝 모드)
타입 변경 없음. `ros-interfaces.md` 2.1 의 `/contact/event` 발행자에 robot_manager 를 더하고, 7.2 에 **SLIDE 스텝 모드**를 적었다. 영향: robot_manager(`slide_mode` · `step_*` 파라미터, `step_slide.py`) · contact_detector(스텝 모드 SLIDE 에서는 EDGE 를 내도 쓰이지 않는다) · scan_manager(절차 · 짝 맞추기 변경 없음. `motion_timeout_s` 120 s) · mqtt_bridge(`source` 값 `robot_step` 추가). `ContactEvent.msg` · 2.1 메시지 정의의 `source` 주석에 `robot_step` 을 더했다(주석만, 타입 · 빌드 영향 없음).
- 9/22 실기: 힘 제어 밀기는 방향별 실제 누름이 1.5~8.6 N(같은 6 N 설정), 방향 전환 뒤 떠서 모서리를 놓침(#155), 가짜 EDGE(#154), 옆 이동 명령 누락(#153), 가짜 도착(#152). 뿌리가 같다 — 움직이는 중에 힘을 읽고 누름을 힘 제어에 맡긴다
- 9/17 `tactile_probe/edge_scan.py` 프로토타입(같은 M0609)은 위치 제어로 한 스텝 가고 멈춘 뒤 힘을 읽어 z 를 맞추며 긁어 원점 + 네 방향을 한 번에 끝냈다(`~/tactile_probe_logs/scan_20260917_171305.csv`). 이것을 robot_manager `slide_mode: step` 으로 옮겼다. `force` 는 기존 그대로
- 스텝 모드의 EDGE 는 "힘 빠짐 → 더 내려가 보기 → 확정 → 가는 스텝 다듬기"가 동작과 한 몸이라 robot_manager 가 확정하고 `/contact/event` 로 낸다(`source robot_step`, `event_id ≥ 2³²`, `z_drop_valid` 항상 true). 짝 맞추기와 scan_manager 절차는 그대로
- 소실 기준은 `step_follow_lo_n`(3 N)이다. `step_release_n`은 처음 누를 때의 닿음 기준으로만 쓴다. **v0.1.15 당시 출발값은 1.5 N**이었고, 9/23 실기 통합에서 F0 치우침으로 윗면보다 약 1.4 mm 위 거짓 접촉 후 −y `no_contact(204)`가 발생해 real 값을 **2.5 N**으로 조정했다(v0.1.20, #179). 9/22 18:2x 실기에서는 모서리를 넘은 반지름 약 2 mm 팁이 모서리 각에 걸려 ΔFz 1~2 N 이 남고, 기준 힘 F0 이 실행마다 ±0.6 N 흔들려 당시 1.5 N을 넘나들었다. 다듬기는 윗면 위로 들고 마지막으로 3 N 이상 누른 자리보다 한 스텝 뒤에서 긁는 방향으로 들어와 F0 을 다시 재고 다시 누른다(18:40 네 방향 성공)
- 후속: 편향 보정의 속도 × 지연 항(스텝 모드는 0 이어야 한다, scan_manager), `edge_bias_offset_m` 을 스텝 모드 기준으로 다시 잰다(T30)

## v0.1.14 (2026-09-21, 새 탐침 TCP x · y, #137)
타입 변경 없음. `units-frames.md`의 탐침 TCP x · y 를 옛 탐침 값 (−1.30, 3.71)에서 **(0, 0)** 으로 확정했다. 영향: robot_manager · contact_detector 가 발행하는 모든 Base x · y(컨트롤러 TCP 등록값을 따른다) · `apply_tool_tcp.py` 기본값 · 실기 세션 절차. (v0.1.13 은 #132 에 예약돼 있어 번호가 머지 순서와 다를 수 있다.)
- **측정**: J6 관절만 +180° 돌려도 팁이 작업대 십자 위에 그대로 있었다(옛 값이면 7.8 mm 옮겨 간다). TCP [0, 0, 252.12] 로 툴 z 축 90° 회전해도 팁이 제자리였다. 새 TCP 로 읽은 홈 팁 x · y 가 홈 플랜지 x · y 와 0.14 mm 안. 눈 정밀도로 약 ±0.25 mm. 원본: `docs/env/tool-tcp-register.md` 9절
- **이전 기록**: 2026-09-21 새 탐침으로 기록한 절대 x · y 는 홈 자세에서 실제보다 (−1.25, −3.73) mm 어긋나 있다. 폭 · 길이 · z 는 영향 없음
- **값을 바꾸지 않은 것**: 작업대 원점 (423.56, −186.06) · 기준점 (525.19, −172.09) · `search_origin_pose` · `base_to_fixture` 는 옛 탐침(피벗 ±1 mm)으로 잰 실제 위치라 그대로다. 새 탐침의 홈 팁 x · y 는 (424.40, −183.22)로 원점과 2.96 mm 떨어진다(v0.1.11 의 0.87 mm 는 틀린 TCP 로 읽은 값). 홈 → 기준점 이동이 약 3 mm 가 된다
- `search_origin_pose` · `base_to_fixture` 를 켜는 조건 ②(TCP x · y 확인)가 끝났다. ①(#109)도 PR #127 로 끝났다(9/21 18:38 실기 홈 출발 하강 6 회 공중 거짓 CONTACT 0 회(`890a8de`, bag `docs/test-reports/data/20260921_pm/bag_t30_1838`), 머지본의 `descend_ref_settle_s` 5.5 s 는 bag 6 개 재생으로 확인). 켤 때는 TCP 를 [0, 0, 252.12] 로 등록한 세션이어야 한다

## v0.1.13 (2026-09-21, 힘 꺾임 EDGE, #128)
타입 변경 없음. `ros-interfaces.md` 3.3 의 EDGE 규칙에 **힘 꺾임**을 더했다. 기본 꺼짐. 영향: contact_detector(판정 · 파라미터 4개 추가) · scan_manager(편향 보정의 δ가 작아진다, 아래) · 실기 절차.
- 2026-09-21 실기 밀기 4회를 기록에서 다시 넣었다: z 추세선 방식은 **한 번도 EDGE 를 내지 못했다**. 모서리 뒤 z 가 일정 속도(0.2~0.35 mm/s, 한 번은 2 mm/s)로 떨어져 추세선이 기울기를 따라간다. 반면 Fz 는 모서리에서 0.4 s 안에 약 2~4 N 꺾인다
- `edge_force_drop_n > 0` 이면: 판정을 켠 뒤 원시 Fz 가 `[t − edge_force_window_s, t − edge_force_lag_s]` 중앙값보다 `edge_force_drop_n` 넘게 낮은 샘플이 연속 `debounce_n` 회면 EDGE. SLIDE 시작 뒤 `edge_force_settle_s` 동안은 보지 않는다. z 추세선과 둘 중 먼저 확정된 것을 낸다
- 재생 결과(1.0 N): 464.43 · 464.53 · 464.59 · 466.70 (기대 463.56, 마지막은 눌린 채 시작한 1회)
- `z_drop_m`: 힘으로 확정하면 판정 첫 샘플의 추세선 대비 하강량(음수면 0, 실기 0~0.1 mm). 추세선이 없으면 `z_drop_valid = false`. **scan_manager 편향 보정(`bias.py` `overshoot_m`)이 δ 로 쓰므로 켜기 전에 병후 확인이 필요하다**
- 켜는 것은 팀 결정이다. BRD 4.1.2 는 z 급강하를 주 신호, 외력 감소를 보조 신호로 둔다
- 새 contact_detector 파라미터(계약 이름 아님): `edge_force_drop_n`(0 = 끔) · `edge_force_window_s` · `edge_force_lag_s` · `edge_force_settle_s`

## v0.1.12 (2026-09-21, 하강 · 밀기 기준 분리, #109)
타입 변경 없음. `ros-interfaces.md`의 **`/contact/tare` 설명(2장)과 판정 규칙(3.3)**을 고쳤다. 영향: contact_detector(판정 · 파라미터 7개 추가) · scan_manager(절차 변경 없음) · 실기 절차.
- 2026-09-21 실기: 외력 추정값이 마지막 이동 방향 · 자세에 따라 2~3 N 치우친다. 정지 F₀ 로 하강하면 큐브 45 mm 위에서 거짓 CONTACT(5-2), 이동 중 F₀ 는 판정 오차 0.016 mm(5-5 · 5-8), 다른 자세의 F₀ 는 1.4 mm 만에 거짓 접촉(5-11). 밀기 중에는 허공에서도 Fx −5 N(5-1)
- **하강**: DESCEND 중 F₀ 를 **최근 구간 [t − 1.0, t − 0.3] s 의 외력 평균(이동 기준)** 으로 둔다(`descend_ref_window_s` · `descend_ref_lag_s` · `descend_ref_min_samples`). 조건 성립 중에는 구간을 얼린다. 처음 안(DESCEND 뒤 6 s 에 한 번 이동 중 F₀ 를 잡고 실패하면 다시 모으는 방식)은 9/21 17 시 54 분 실기에서 한 번 잡은 F₀ 가 23 s 뒤 3.15 N 흘러 **윗면 38 mm 위 거짓 CONTACT** 를 냈다(자세에 따른 흐름). 실기 하강 23 회 재생: 한 번 잡는 방식(정지 · 이동 중)은 1~2 회 거짓 CONTACT, 이동 기준은 0 회 · 윗면 z 같음
- **출발 뒤 `descend_ref_settle_s`(실기 5.5 s)**: 출발 약 4 s 뒤의 계단식 치우침이 이동 기준 구간을 지나갈 때까지 둔한 판정으로 본다. 1 s 로 두면 계단이 3 N 임계에 그대로 보였다(9/21 홈 출발 22 회 모두 4.0~4.1 s, 공중 최대 2.92 N · 여유 0.08 N). 5.5 s 재생: 3 N 구간 공중 최대 2.04 N, 6 N 구간 4.43 N(yujh5537 리뷰, PR #127)
- **이동 기준이 없는 동안**(출발 뒤 `descend_ref_settle_s` · 공백 뒤) CONTACT 를 끄지 않고 `/contact/tare` F₀(없으면 DESCEND 첫 샘플의 F)와 `descend_hold_threshold_n`(실기 6.0 N)으로 판정한다(현지 · 병후 리뷰, PR #127). 끄면 그 사이 닿았을 때 OVER_FORCE(30 N)까지 막을 것이 없다
- `get_tool_force` 치우침은 마지막 이동 방향 · 자세에 딸린다. F₀ 는 "그 모션, 그 자세 근처"에서만 유효하다(3.3 에 한 문장). DESCEND 가 아닐 때 F₀ 는 마지막 CONTACT 의 이동 기준과 `/contact/tare` 중 나중 것
- 접촉 임계 `contact_threshold_n` 3 N 은 유지한다(TR-01 검출 하중 5 N 이하. 학민 결정)
- **밀기**: EDGE 판정을 켜는 조건을 `|F − F₀| > edge_arm_force_n` 에서 **z 멈춤 + x · y 이동**으로 바꿨다. 하강용 F₀ 를 밀기에 쓰면 옆 이동 이력 때문에 닿기 전에 켜져, 2~4 방향의 틈을 메우는 동안 판정을 쉬게 하는 보호가 사라졌다
- `/contact/tare`(정지)는 툴 등록 점검(`TOOL_REG_SUSPECT`)과 예비 기준으로 남는다. scan_manager 절차는 바뀌지 않는다
- 새 contact_detector 파라미터(계약 이름 아님): `descend_ref_window_s` · `descend_ref_lag_s` · `descend_ref_min_samples` · `descend_ref_settle_s` · `descend_hold_threshold_n` · `edge_arm_still_window_s` · `edge_arm_still_m` · `edge_arm_travel_m`. 값은 설계 출발값이며 실기에서 조정한다

## v0.1.11 (2026-09-21, 배치 원칙 · 탐침 전제조건, #108)
타입 변경 없음. `units-frames.md`에 **배치 원칙**과 **탐침 상태 전제조건** 절을 새로 두고, 2026-09-21 탐침 교체 뒤의 실측으로 z 계열 값을 확정했다. 영향: scan_manager(`search_origin_pose` · `base_to_fixture` · `max_descend_m` 범위) · geometry_estimator(`edge_bias_offset_m`) · T24 · T25 · T30 · 실기 세션 절차. (v0.1.9는 #91에 예약돼 있어 번호가 머지 순서와 다를 수 있다.)
- **배치 원칙(학민 결정)**: 홈 관절각은 바꾸지 않는다 · 부재는 홈 바로 아래 하강점이 윗면 안에 오게 놓는다(위치는 조금 달라도 된다) · 변은 작업대 테이프선에 평행 · **본드로 고정** · MVP 부재는 80 mm 큐브 한 종. "낮은 부재는 홈을 낮춘다"는 삭제하고 "부재 높이가 `max_descend_m`을 정한다"로 바꿨다(0.120이면 h ≥ 72.3 mm)
- **작업대 원점 재정의**: "2026-09-19 큐브 윗면 가운데, 세션 한정, 가이드 설치 시 재정의" → **홈 바로 아래 고정 하강점**. x · y 값(423.56, −186.06)은 그대로다(9/21 홈 팁 x · y와 0.87 mm, 홈 재현성 0.5~0.7 mm)
- **z=0 = 100.503 mm**(100.6에서 변경). 작업대 기준점 (525.19, −172.09)의 힘 접촉 판정 좌표. 9/20 100.503, 9/21 새 탐침 100.519. 탐침 점검 기준점과 같은 점이다
- **TCP z = 252.12 확정**(248.52 잠정에서). 탐침 교체 뒤 기준점 접촉으로 구했다. **x · y(−1.30, 3.71)는 옛 탐침 값을 임시로 쓴다**(새 탐침은 재지 않음. 절대 좌표에 그대로 들어가므로 좌표를 켜기 전에 180° 회전으로 확인). 파생값: 홈 팁 z 287.84(작업대 위 187.34) · 홈→큐브 윗면 107.44 · `max_descend_m` 하한 0.113 · 상한 0.1823. `real.yaml`의 0.120은 범위 안이라 바꾸지 않았다. 교차 검증: 큐브 높이 79.9 mm(캘리퍼 80)
- **탐침 밀림 · 마모를 오차 가정에서 뺐다.** 매 세션 시작 · 과대 외력 뒤에 기준점을 찍어 허용치(초안 0.3 mm) 안이어야 좌표가 유효하다. 교체 절차를 적었다. 홈 팁 z로는 탐침 길이를 알 수 없다는 점을 명시했다
- **`search_origin_pose` 값**: `[0.42356, -0.18606, 0.28784, 0.9999791452, 0.0064576733, -0.0000833683, -0.0000257908]`(홈 팁 위치 · 자세). **`real.yaml`에는 켜지 않았다.** 켜는 조건: ① 정지 상태 tare가 하강 중 거짓 접촉을 내는 문제(#109) 해결, ② 새 탐침 TCP x · y 180° 회전 확인
- **검출 편향 2.25 mm(v0.1.8) 무효**: 밀린 탐침(11 N/mm)으로 잰 값이다. 새 탐침(43 N/mm)으로 T25에서 다시 잰다
- **축 평행 2.1°(v0.1.8)는 지금 부재에 적용하지 않는다**: 고정하지 않은 큐브의 값이고 9/21에 그 큐브가 밀렸다. 본드 고정 뒤 다시 잰다. 테이프선과 Base 축의 평행도는 TBD
- 근거: `docs/test-reports/realrobot-session_20260921.md` 0-1 · 5-4 ~ 5-12

## v0.1.10 (2026-09-21, T15 후속, PR #98)
타입 변경 없음. `ros-interfaces.md` 6.3절의 **실측 발행 주기**를 한 번 측정값에서 **부하 의존 범위**로 바꿨다. 영향: contact_detector(`stale_age_ms` · EDGE 판정 창) · safety_monitor(`sample_stale_ms`) — 셋 다 이 숫자를 근거로 쓴다.
- 2026-09-20 저녁 통합 세션에서 현지가 다시 재니 `/robot/sample` **49.8 Hz**(평균 20.1 ms, 95% 25.5, 99% 29.7, 최대 44.1 ms, 684샘플 손실 0). 낮의 37.6 Hz / 최대 97.7 ms와 두 배 가까이 벌어진다. 같은 Virtual이라 부하에 좌우되는 값이다
- 통합 세션 전체에서는 **342 / 340 / 201 ms 공백이 세 번** 있었다. 평균이 아니라 이 꼬리가 EDGE 판정과 최신성 한계에 걸린다
- 그래서 6.3에 "부하에 따라 크게 달라진다"를 명시하고 두 측정을 표로 나란히 두었다. 최신성 한계와 판정 창은 **최대 공백** 기준으로 잡는다
- **맞바꿈을 같이 적었다.** 342 / 340 ms 는 지금의 `sample_stale_ms` 300 을 넘는다(safety_monitor 가 떠 있었다면 모션 없이 정지 요청 두 번). 한계를 올리면 실제 끊김 감지와 `drop_limit_m` 2차 감시가 그만큼 늦어지므로, **한계를 올리기 전에 공백의 원인을 없애는 쪽이 먼저**다
- 공백의 원인은 미확인. 후보(robot_manager 직렬 호출 큐 · 드라이버 · 호스트 부하)와 가르는 방법(공백 시각의 robot_manager `응답 시간 초과` 경고 유무)을 적었다. T13(#73) 이후 모션 호출이 같은 큐에 들어가 더 길어질 수 있다
- 실기 주기와 공백 분포는 T24 전에 다시 잰다

## v0.1.9 (2026-09-20, #51 · #54, PR #91)
타입 변경 없음. 계약의 빈틈 7건을 문서에 채웠다. 필드 이름 · 타입 · 순서 · 상수값은 그대로다. 영향: scan_manager(파라미터 선언 · 결과 발행) · robot_manager(P01) · mqtt_bridge · 웹.
- **#51** `ScanConfig.target_force_n` ↔ robot_manager 파라미터 `slide_target_force_n` 대응을 2.4절과 3.9절 주석에 적었다. 숫자는 그대로 전달되지만 **기준이 `DR_FC_MOD_REL`(호출 시점의 힘에 더해지는 값)이라 tare 대비 절대 누름 힘이 아니다** — 실제 누름은 SLIDE 시작 위치에 달렸다(첫 방향 = 접촉력 + 이 값, 2~4 방향 · 재시작 = ≈ 이 값)(#91 리뷰: 학민 · 현지). REL 유지 여부는 실기 뒤 확정(TBD). 머리말 상태 줄에도 v0.1.9 구절을 적었다
- **#54** `recontact_margin_m` · `recontact_speed_mps` · `move_speed_mps`가 **SetConfig 전파 대상이 아닌 scan_manager 파라미터**임을 6.4절에 적었다. 7.3절 · 9장 TBD의 "내림 속도"도 이름으로 바꿨다. 값은 여전히 TBD다
- **#54** `mqtt-schema.md` 5장 TBD 2건: `hb/ros` · `conn/ros`의 만료 판정 기준 필드(두 메시지에 `stamp_ms`가 없다. LWT는 `published_at_ms`가 접속 시각이라 그대로 못 쓴다), retain 상태의 "오래된 값" 기준 시간
- 7.4절 **결과 중복 키를 `scan_id` → `(scan_id, stamp)`** 로 고쳤다. 재시작이 `scan_id`를 유지하므로(5.3절) 부분 결과와 최종 결과가 같은 `scan_id`로 두 번 나간다. main의 mqtt_bridge가 이미 이 키로 구현돼 있다(`_scan_result_dedup_key`)
- `contact/event` 예시에 필드별 출처(판정 샘플 / 확정 샘플)를 한 줄 달아 v0.1.5(#79)와 연결했다
- `ScanConfig`에서 **scan_manager가 모르는 값(`*_set=false`)은 `null`** 로 나간다고 2장 변환표에 적었다. 구현이 이미 그렇다(`encode_scan_config`의 `non_finite_to_none`). 0을 넣지 않는다는 1장 무효 값 규칙과 같은 취지다
- `mqtt-schema.md` 머리말의 mqtt_bridge 담당을 병후 → **의석**으로 고쳤다(2026-09-19 T21 이전, PR #63). T27 접점은 병후 · 의석 공동이다
- 번호: PR #98(v0.1.10)이 먼저 머지됐다. #98이 v0.1.9를 비워 두어 이 PR이 그 자리에 들어간다(파일에서는 v0.1.10 아래)

## v0.1.8 (2026-09-20, T03 후속 실기, PR #80)
타입 변경 없음. 축 평행을 **실측값 2.1°**로 채웠다. 영향: scan_manager(결과 변환) · geometry_estimator(꼭짓점 · 경로 후보) · T30.
- 큐브 옆면 5점 터치로 변 직선을 구했다: `x = 0.03625 · y + 468.955`, 잔차 0.21 mm 이하. **2.1° ± 0.3°(1σ)**, 95% 구간 약 1.3~2.8°
- 치수에는 0.05 mm 이하로 들어오지만 꼭짓점 · 경로 후보 좌표에는 **축당 최대 1.45 mm**(꼭짓점 변위 2.05 mm) 남는다
- `base_to_fixture`는 계약상 평행 이동만 다룬다(2장). 2°를 어떻게 처리할지는 팀 결정이 필요하다
- 접촉 소실 검출이 진짜 변보다 약 **2.25 mm** 바깥에서 걸린다(원측정값). 사고 당시 탐침 길이를 몰라 보정하지 않는다. **잠정**이며 누름 힘이 정해진 뒤 T25에서 다시 잰다
- 그 편향에는 TCP x · y 미확인이 남는다. 3절(30~37° 기울임)과 4절(수직)의 자세가 달라 상쇄되지 않는다. **2.25 ± 0.6 mm**, 폭 과대 추정 **4.5 ± 1.2 mm**. 최소로 잡아도 3.3 mm 라 BRD ±3 mm 밖이다(현지 계산)
- 과압 사고로 탐침이 **1.47 mm 짧아졌다**. TCP z를 248.52로 잠정 조정하고 파생값(탐색 기준점 · `max_descend_m` 하한 · 상한)을 다시 계산했다. x · y는 미확인
- **z 계열 값은 전부 잠정이다**: z=0 100.6 · 홈 팁 높이 190.84 · 홈→윗면 111.92 · `max_descend_m` 0.117 · 0.1858. TCP z 248.52 에 종속된다. "탐침이 되돌아왔다"는 확인되지 않았고(`table_check_after_fix` 가 그 전과 0.004 mm 차이), 9/19 와 9/20 은 작업대의 **다른 자리**를 재서 두 평균을 뺀 계산이 평탄을 가정한다. 다음 세션에 9/19 의 두 점을 같은 자리에서 다시 찍어 확정한다
- **`max_descend_m` 하한을 0.116 → 0.117 m로 올렸다.** 홈은 관절각으로 정의되므로 탐침이 짧아지면 플랜지 시작 위치는 그대로인 채 팁만 1.47 mm 올라간다. 같은 윗면에 닿으려면 플랜지가 그만큼 더 내려가야 한다(110.49 → 111.92 mm). 하한이 실제 필요 거리보다 작으면 첫 하강이 접촉 전에 `MAX_DISTANCE`로 끝난다
- 근거: `docs/test-reports/T03-follow-up_20260920.md`

## v0.1.7 (2026-09-20, T03 정정, PR #80)
타입 변경 없음. `units-frames.md`의 **기준 큐브 모서리 라운드 가설을 폐기**했다. 영향: T24 · T25(`edge_drop_m` 판정) · T30(정확도 시험) · BRD 4.2.4 편향 보정 검토.
- 캘리퍼 실측: **80 × 80 × 80 mm, 모서리 예리** (2026-09-20 / 학민)
- 따라서 "라운드 폭 최대 1.7 mm", "폭 · 길이 최대 3.4 mm 과소 추정"은 폐기한다
- 2026-09-19 "모서리 4점"은 꼭짓점이 아니라 팁 접촉부가 윗면에 온전히 닿도록 안쪽으로 들어가 찍은 점이다. 변당 오프셋 1.69 mm로 계산이 맞는다(80 − 2 × 1.69 = 76.6 = 실측 변 평균). 이 네 점을 꼭짓점 좌표로 쓰지 않는다. 네 점 평균인 원점 x · y에서는 상쇄되므로 원점 값은 그대로다
- 모서리 z가 안쪽 점보다 0.9 mm 낮은 것은 미해결로 남긴다

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
