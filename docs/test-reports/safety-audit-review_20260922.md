# 감사 보고서 × 팀 회의 결정 검토 (2026-09-22, origin/main 5ac5652 기준)

- **기준 커밋**: `origin/main` **5ac5652**(2026-09-22 01:34Z, #143). 그 뒤에 병합된 #131과 #145는 본문을 고치지 않고 [0-1절](#0-1-기준5ac5652-이후-바뀐-것--본문에-반영되지-않았다)에 따로 적었다.
- **입력 자료**:
  - 감사 보고서 `docs/test-reports/safety-audit_20260921.md`. c9de11e 기준이며 PR #144로 아직 열려 있다.
  - 감사 보고서에 대한 팀 회의 메모. 레포 밖이며 요청자가 붙여 넣었다.
- **목적**:
  - 해결된 감사 항목을 걸러 낸다.
  - 회의 결정의 파급과 적용 가능성을 판정한다.
  - 회의에서 다루지 않은 미해결 항목이 팀 방침으로 커버되는지 본다.
  - 팀 방침에 맞춘 추가 완화안을 추천한다.
- **검토 전제(팀 방침)**:
  - ① MVP로 F1~F5가 끝까지 동작하는 것이 최우선이다.
  - ② 통신 지연으로 생기는 문제는 보류한다.
  - ③ 모든 실습에서 사람이 티칭 펜던트를 들고 감시한다(비상정지 대기).
- **방법**: 읽기 전용이다. 저장소, 이슈, PR은 건드리지 않았다. ROS, Virtual, 실기 명령도 실행하지 않았다. 직접 실행한 것은 순수 모듈(`detector_core`, `safety_core`)과 9/20 실기 CSV로 한 오프라인 계산뿐이다([부록 A](#부록-a-오프라인-계산-스크립트)).
- **요청·검토**: 현지(@yujh5537). 분석: Claude Code.

**읽는 법**
- **링크**: 코드와 문서 링크는 5ac5652 고정 링크라 줄 번호가 밀리지 않는다. 레포 밖 경로(`ws_dsr/`, `docs/_local/`)는 텍스트로만 적었다.
- **약어**: RM `robot_manager.py`, CQ `call_queue.py`, SC `safety_core.py`, SMN `safety_monitor.py`, DC `detector_core.py`, SM `scan_manager.py`, ST `state_machine.py`, SEQ `sequence.py`, RY `real.yaml`, SY `sim.yaml`, ROS `ros-interfaces.md`, RS `realrobot-session_20260921.md`
- **문서 버전**: BRD v3.2.0, `ros-interfaces` v0.1.12(`units-frames` v0.1.14), 정의서 v1.2, 노드 구성도 v1.1. 문서끼리 다르면 `docs/contracts/`를 따랐다.

---

## §0 기준 커밋과 c9de11e 이후 변경

**HEAD `5ac5652`**(2026-09-22 01:34Z, #143). c9de11e 이후 병합은 5건이다.

| PR | 커밋 | 핵심 | 감사 항목 영향 |
|---|---|---|---|
| #135 | `85f924f` | 늦은 두산 응답을 서비스 이름·시간으로 기록(`slow_call_warn_s` 0.15, [RY:132](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/ws_cobot1/src/contact_scan_bringup/config/real.yaml#L132), [CQ:74](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/ws_cobot1/src/robot_manager/robot_manager/call_queue.py#L74)) | B-2·C-3 진단만. 동작은 그대로 |
| #127 | `22cf09b` | 하강 F₀를 이동 기준으로, 출발 뒤 5.5 s는 6 N 임계로 판정. EDGE 켜기를 z 조건으로(계약 v0.1.12, [ROS:141](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/docs/contracts/ros-interfaces.md#L141)) | **B-1·F1-2 해결**, F2-2 부분 해결 |
| #136 | `8c33a50` | START·RESUME 때 `/safety/status`·`/robot/status`의 stamp 나이 확인([ST:360-381](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/ws_cobot1/src/scan_manager/scan_manager/state_machine.py#L360), [RY:211-212](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/ws_cobot1/src/contact_scan_bringup/config/real.yaml#L211)) | **D-1·F4-4 부분 해결** |
| #138 | `95bbb22` | 새 탐침 TCP x·y를 (0,0)으로 확정(계약 v0.1.14) | F1-1의 켜는 조건 ② 충족 |
| #143 | `5ac5652` | 웹이 `scan/result`로 엣지를 그림 | D-7은 **그대로**(safety 처리 없음) |

**지정 PR·이슈 상태**(5ac5652 시점)

| 번호 | 상태 | 비고 |
|---|---|---|
| #53 | 이슈 OPEN | 하강 제한 1·2차 동시 래치. 결정 없음 |
| #73 | PR 병합(9/21) | REL 유지 여부는 여전히 "실기 뒤 결정"(ScanConfig 주석). #105도 OPEN |
| #99 | PR 병합(감사 전) | 기동 유예 |
| #109 | 이슈 CLOSED | #127로 해결 |
| #115 | 이슈 CLOSED | 남은 정지 요청이 HOME을 막지 않음 |
| #127 | PR 병합 | 실기 9/21 18:38, 홈 출발 하강 6회에서 공중 거짓 CONTACT 0회([CHANGELOG:10](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/docs/contracts/CHANGELOG.md#L10)) |
| #128 | **이슈** OPEN | ⚠ 감사 보고서가 "PR #128"이라 쓴 것은 오류다. 구현은 **PR #132(OPEN, 기본 꺼짐)** |

**감사 뒤 새로 생긴 안전·통신 관련 항목**

| 번호 | 상태 | 요지 |
|---|---|---|
| #130 | OPEN | 정지 중 약 3 s마다 316~365 ms 공백. goal 수락 뒤 1.0~1.3 s에도 난다 → **goal의 약 40%가 SAMPLE_STALE로 정지**(17:54 실기). 접촉 위치에서 바로 안전복귀가 나간 것 2회. robot_manager에는 3 s 주기 작업이 없다(코멘트) |
| #120 | OPEN | 감시자 생존. #136은 `Refs`만 걸어 부분 해결 |
| #123 | OPEN | 툴·TCP 등록 확인(D-6) |
| #125 | OPEN | compliance_released를 제어 모드 조회로 판정. `GetControlMode`로는 구분이 안 될 수 있다는 코멘트 |
| #133 | OPEN(5ac5652 시점) | ERROR로 끝난 stop의 완료 통지 누락(C-8). → 0-1절: #145로 해결 |
| #139 / PR #140 | OPEN | 이동 기준 CONTACT의 느린 접촉 경계 약 4.6 N/s |
| #141 | OPEN | 새 탐침 하강점과 `base_to_fixture`가 2.96 mm 어긋남 |
| #142 | OPEN | 좌표 켜기, M4 종단 |
| #111 | OPEN | SIGINT exit −2 |
| #33 | OPEN | heartbeat |

**감사 인용 줄 번호 재매김**(변경된 파일만. 나머지 파일은 줄 번호 그대로)

| 파일 | 옛(c9de11e) → 새(5ac5652) |
|---|---|
| RM | 100→102 · 218→222 · 246-250→250-254 · 264-267→268-271 · 334-335→338-339 · 348-356→352-360 · 366-418→370-422 · 388-393→392-397 · 423-424→427-428 · 426→430 · 433-445→437-449 · 460-470→464-474 · 506-547→510-551 · 567-572→571-576 · 585-586→589-590 · 589-594→593-598 · 595-601→599-605 · **602-604→606-608** · 608-642→612-646 · 642→646 · 671-707→675-711 · 683-689→687-693 · 737-750→741-754 · 752-776→756-780 · 778-808→782-812 · 810-823→814-827 · 820→824 · **852-864→856-868** |
| CQ | 25(내용 변경: `slow_s` 추가) · 35-53→40-58 · 68-84→83-99 |
| DC | 236-245→337-346 · 247-260→348-368(내용 변경) · 262-305→370-414(내용 변경) · 274-278→382-387 · 365-370→516-521 |
| `contact_detector.py` | 190-198→212-220 · 208-214→230-236 |
| ST | 310-324→344-358 · 311-314→**345-348** · 326-335→360-381(내용 변경) |
| SM | 417-432→424~(내용 변경: 끊김 관문, 450-488) · 461-478→519-536 · 696-707→754-765 · 810-833→868-891 · 1029-1065→1087-1123 |
| RY | 49→69 · 50→70 · 51→71 · 52→72 · 57-58→77-78 · 59→**79** · 63→83 · 66→86 · 70→90 · 79→99 · 81→101 · 112-116→134-138 · 123-124→145-146 · 139→161 · 148-158→**170-180** · 162-167→184-189 · 183→205 · 186-187→215-216 |
| SY | 55→64 · 59→68 |
| ROS | 45(내용 변경) · 156→164 · 283→291 · 374→382 · 601-604→**609-612** · 641→649 · 652→660 · 688→696 · 696-698→704-706 |
| `App.jsx` | 390-482→443-565(내용 변경) |

### 0-1. 기준(5ac5652) 이후 바뀐 것 — 본문에 반영되지 않았다

| 병합 | 변경 | 본문에서 영향받는 곳 |
|---|---|---|
| #131 (2026-09-22 02:05Z) | 통합 감사 보고서 `integration-audit_20260921.md` 추가(문서만) | 없음 |
| #145 `cc64cbc` (2026-09-22 02:48Z, #133) | mqtt_bridge 수정 세 가지. ① 모르는 `debounce_n`을 `null`로 보낸다. ② STOPPING → ERROR로 끝난 stop을 `success=false`로 완료 통지한다. ③ 멈출 것이 없을 때 누른 stop은 곧바로 완료하고, 다른 작업의 STOPPED에 붙지 않는다. **sim·Virtual 확인은 하지 않았다**(PR 본문) | **C-8·F3-4·L4-3·§5-12가 해결**됐다(sim 미확인). §1 표의 C-8·F3-4·§5-12 판정, §4의 C-8 행 |

---

## §1 감사 항목 상태표

### 감사 §4 문제 26건
| ID | 판정 | 근거 |
|---|---|---|
| C-1 | 미해결 | [RM:856-868](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/ws_cobot1/src/robot_manager/robot_manager/robot_manager.py#L856) 그대로. #111은 트레이스백만 다룬다 |
| C-2 | 미해결 | [RM:606-608](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/ws_cobot1/src/robot_manager/robot_manager/robot_manager.py#L606), [:687-693](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/ws_cobot1/src/robot_manager/robot_manager/robot_manager.py#L687) 그대로 |
| C-3 | 미해결(근거 보강) | FIFO와 5 s 점유는 그대로([CQ:25](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/ws_cobot1/src/robot_manager/robot_manager/call_queue.py#L25), [:83-99](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/ws_cobot1/src/robot_manager/robot_manager/call_queue.py#L83)). #135가 "약 3 s마다 330~365 ms 늦음"을 실측으로 남겼다 |
| C-4 | 미해결 | [SMN:164-171](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/ws_cobot1/src/safety_monitor/safety_monitor/safety_monitor.py#L164) 그대로. 재현 B 유효 |
| C-5 | 미해결 | [RM:646](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/ws_cobot1/src/robot_manager/robot_manager/robot_manager.py#L646) |
| C-6 | 미해결 | [RM:612-632](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/ws_cobot1/src/robot_manager/robot_manager/robot_manager.py#L612) |
| C-7 | 미해결(근거 확정) | 디바운스는 여전히 샘플 수로 센다([DC:365](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/ws_cobot1/src/contact_detector/contact_detector/detector_core.py#L365)). 9/21 17시 bag(robot_manager 50 Hz 경로)에서도 "힘 값이 약 5 샘플마다 바뀐다"(#130 코멘트 1) |
| C-8 | 미해결 → **0-1절: #145로 해결** | #133 수용, 5ac5652 시점에는 미수정 |
| C-9 | 미해결 | [RM:427-428](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/ws_cobot1/src/robot_manager/robot_manager/robot_manager.py#L427) |
| C-10 | 미해결 | [motions.py:68-72](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/ws_cobot1/src/robot_manager/robot_manager/motions.py#L68) |
| D-1 | **부분 해결** | #136으로 START·RESUME은 막힌다. **진행 중인 스캔은 계속되고**(로그만, [SM:475-488](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/ws_cobot1/src/scan_manager/scan_manager/scan_manager.py#L475)) 웹 표시도 없다. #120 OPEN |
| D-2 | 미해결 | [RM:252](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/ws_cobot1/src/robot_manager/robot_manager/robot_manager.py#L252), [:338-339](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/ws_cobot1/src/robot_manager/robot_manager/robot_manager.py#L338) |
| D-3 | 미해결 | #33 OPEN |
| D-4 | 미해결 | — |
| D-5 | 미해결 | #53 OPEN, [ST:345-348](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/ws_cobot1/src/scan_manager/scan_manager/state_machine.py#L345) |
| D-6 | 미해결 | #123 OPEN |
| D-7 | 미해결 | [App.jsx:443-565](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/frontend/src/App.jsx#L443)에 `safety/status` 처리가 없다. #143은 결과 표시만 추가 |
| D-8 | 미해결 | — |
| D-9 | 미해결 | [RY:215-216](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/ws_cobot1/src/contact_scan_bringup/config/real.yaml#L215)가 여전히 주석 |
| B-1 | **해결** | #127. 실기 6회 거짓 CONTACT 0. 남은 제약: 출발 뒤 5.5 s는 6 N 판정([RY:55](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/ws_cobot1/src/contact_scan_bringup/config/real.yaml#L55), [:60](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/ws_cobot1/src/contact_scan_bringup/config/real.yaml#L60)), 느린 접촉 경계(#139) |
| B-2 | 미해결(심각도 상향) | [RY:79](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/ws_cobot1/src/contact_scan_bringup/config/real.yaml#L79) = 300. #130: goal 약 40% 정지 |
| B-3 | 미해결(위험은 낮음, §3 M1) | [RY:40](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/ws_cobot1/src/contact_scan_bringup/config/real.yaml#L40) = 0.3 |
| B-4 | 미해결 | [RM:102](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/ws_cobot1/src/robot_manager/robot_manager/robot_manager.py#L102) `stop_settle_s`는 여전히 코드 기본값 |
| B-5 | 미해결 | [RY:22](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/ws_cobot1/src/contact_scan_bringup/config/real.yaml#L22), [:69](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/ws_cobot1/src/contact_scan_bringup/config/real.yaml#L69) = 30 N |
| B-6 | 미해결 | #73의 결정 문구가 "실기 뒤". #105 OPEN |
| B-7 | 미해결 | `motion_state.py` 그대로 |

### 감사 §3 F1~F6 증상
| 증상 | 판정 | 근거·비고 |
|---|---|---|
| F1-1 START INVALID_VALUE | 부분 | 켜는 조건 ①(#127)과 ②(#138)는 충족. **#141 결정과 #142 작업이 남았다**([RY:170-180](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/ws_cobot1/src/contact_scan_bringup/config/real.yaml#L170)) |
| F1-2 정지 tare 거짓 CONTACT | 해결 | #127 |
| F1-3 TARE_UNSTABLE 경계 | 미해결 | 실측으로는 여유가 있다(M1) |
| F1-4 CONTACT 지연·과대 | 미해결 | C-7 |
| F1-5 경계 공백 래치 | 미해결 | #130 |
| F1-6 연결 흔들림 무감시 하강 | 미해결 | C-2 |
| F2-1 REL 3 N ≠ 실제 | 미해결 | B-6 |
| F2-2 누름 확인 1.5 N | 부분 해결 | EDGE 켜기가 z 조건으로 바뀌었다(`edge_arm_still_*`). 힘 숫자의 의미 문제는 남는다 |
| F2-3 느린 낙하 흡수 | 미해결 | PR #132 OPEN(재생 4회, 실기 1회 성공, 기본 꺼짐) |
| F2-4 공백 때 추세 리셋 | 미해결 | [DC:382-387](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/ws_cobot1/src/contact_detector/contact_detector/detector_core.py#L382) |
| F2-5 SLIDE 시작 직후 정지 | 미해결, **가설 수정** | 원인은 "모션 호출이 큐를 점유"가 아니라 정지 중 약 3 s 주기의 드라이버 쪽 지연으로 보인다(#130 코멘트 1: robot_manager에 3 s 작업이 없음). 증상은 실제로 발생했다 |
| F2-6 동시 래치 | 미해결 | #53 |
| F2-7 정지 → 해제 순서 | 판단 불가 | 실기 2회 정상, 순서는 TBD([ROS:704](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/docs/contracts/ros-interfaces.md#L704)) |
| F3-1~5 | 미해결 | C-3 / 중복 정지 / ERROR / #133 / C-1. F3-4는 → **0-1절: #145로 해결** |
| F4-1 F4 불성립 | 미해결 | D-5, [ST:345-348](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/ws_cobot1/src/scan_manager/scan_manager/state_machine.py#L345) |
| F4-2 CONDITION_ACTIVE 지속 | 미해결 | 실제 발생 사례 없음 |
| F4-3 경쟁 조건 | 미해결 | C-4 |
| F4-4 감시자 사망 | 부분 해결 | #136 |
| F4-5 reset이 미확인 정지에서도 성공 | 미해결 | — |
| F4-6 웹 래치 표시 | 미해결 | D-7 |
| F5-1 / F5-4 | 유지(A) | — |
| F5-2 올림 없는 movej | 미해결, **실제 발생** | #130: 접촉 위치에서 안전복귀 2회 |
| F5-3 HOME 도착 미검증 | 미해결 | C-5 |
| F6-1~5 | 미해결 | sim 낙하 50 mm/s 그대로([SY:68](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/ws_cobot1/src/contact_scan_bringup/config/sim.yaml#L68)) |

### 감사 §5 문서-코드 불일치 18건
| # | 판정 | 비고 |
|---|---|---|
| 1 tare 정지 vs 운동 | **해결** | 계약 v0.1.12([ROS:45](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/docs/contracts/ros-interfaces.md#L45), [:141](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/docs/contracts/ros-interfaces.md#L141)): tare는 툴 점검과 예비 기준, 하강은 이동 기준 |
| 8 force_stamp와 실제 데이터 나이 | 부분 | "모델 기반 추정"은 명시됐다. **10 Hz 갱신은 계약·api-check-log 어디에도 없다** |
| 11 `/scan/home` 전제조건 | 미해결, 오히려 벌어짐 | #136이 HOME의 `/robot/status` 끊김 거절을 추가했는데 계약 5.2([ROS:438](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/docs/contracts/ros-interfaces.md#L438))에는 없다 |
| 12 stop 완료 = STOPPED | 미해결 → **0-1절: #145로 해결** | ERROR 경로 완료 통지 |
| 2~7, 9, 10, 13~17 | 미해결 | 변화 없음. 6번 `home_pose`는 [ROS:467](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/docs/contracts/ros-interfaces.md#L467), 17번은 [ROS:115](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/docs/contracts/ros-interfaces.md#L115)와 [:696](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/docs/contracts/ros-interfaces.md#L696) |
| 18 버전 | 기록 | BRD v3.2.0, 정의서 v1.2, 노드 구성도 v1.1 |

**해결되어 이후 단계에서 빼는 것:** B-1, F1-2, §5-1

---

## §2 미해결 항목 분류

**분류 기준.** (a) 통신·드라이버 기인이라 보류 / (b) 우리 코드의 로직 결함 / (c) 설계·팀 결정 필요 / (d) 운용 규칙으로 대체 가능

| 분류 | 항목 |
|---|---|
| (a) | F6-4(에뮬레이터 부하), **B-2의 공백 발생 자체**, C-3에서 "드라이버가 느린 것" 자체 |
| (b) | C-1, **C-2**, **C-3의 처리 방식**, **C-4**, C-5, C-6, C-8, C-9, C-10, D-1 잔여(웹 표시), D-2, D-6(#123), D-7, D-8, B-4, **B-2의 반응 방식**, F3-2, F5-2의 올림 성공 확인, F6-2(sim 낙하 속도) |
| (c) | D-5 / F4-1 / F4-5, #53, B-5(운용 한계값), B-6(#73), **C-7(디바운스 정의)**, F2-3·4(#132 켜기, ADR), F2-7, F3-3, F5-2(계약 7.4 홈 경로), D-1 잔여(진행 중 사망 시 동작), D-3, D-4 |
| (d) | L4-2·D-9(시계 동기 점검), D-6(시작 전 등록 확인), B-3(발생 시 조정), F4-2(조건 해소 확인 절차), D-3·D-4(MVP 범위 밖으로 운용) |

**통신 지연처럼 보이지만 실제로는 (b)인 것**
- **C-2 → (b).** 시간 초과(통신)는 계기일 뿐이다. 문제는 한 번의 실패를 곧바로 connected=false로 확정하고([RM:268-271](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/ws_cobot1/src/robot_manager/robot_manager/robot_manager.py#L268)), 그 순간 `move_stop`도 부르지 않고 motion을 놓는 처리([RM:606-608](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/ws_cobot1/src/robot_manager/robot_manager/robot_manager.py#L606))다. 연속 N회 실패로 판정하고 가능한 만큼 정지를 시도하면 우리 코드로 고칠 수 있다. **방침 2(통신 보류)의 대상이 아니다.**
- **C-3 → (b), 원인 일부는 (a).** 드라이버가 느린 것은 (a)다. 하지만 FIFO에 정지 우선순위가 없는 것, 슬롯을 5 s 잡는 것(`abandon_after_s` 고정값), 중복 정지는 우리 설계다. #135 실측(약 3 s마다 최대 365 ms)을 보면, 평소에도 정지가 최대 약 0.36 s 줄을 서는 창이 3 s마다 생긴다.
- **C-4 → (b), 통신과 무관.** 통신 없이 순수 모듈로 재현했다(감사 보고서 재현 B). 판정 규칙이 두 곳(`react`와 `level`)에서 다를 뿐이다.
- **B-2 → 원인은 (a), 반응은 (b).** 공백은 정지 중에만 약 3 s 주기로 나고, robot_manager에는 그런 주기 작업이 없다(#130 코멘트). 그래서 감사의 "우리 큐 점유" 가설은 **약해졌다**. 다만 두 가지를 확인해야 한다.
  - #135의 real.yaml 주석은 "정지 중·모션 중 모두 늦었다"고 쓰고, #130은 "움직이기 시작한 뒤엔 공백 없음"이라고 써서 서로 어긋난다.
  - 샘플을 한 줄로 조회하는 구조에서는 호출 하나가 늦으면 곧바로 샘플 공백이 된다.
  
  반응 쪽은 우리 규칙의 결과다. "모르면 이동 중"과 "이동 중 무소식은 STOP + 래치"가 겹쳐, 실제로는 서 있는 로봇에 래치를 건다. 이 부분은 고칠 수 있다.
- **C-7 → 사실은 (a), 정의는 (c), 구현은 (b).** 10 Hz 갱신은 컨트롤러 동작이다. 샘플 수로 셀지 값 변화로 셀지는 우리가 정할 문제이고, 계약 [ROS:164](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/docs/contracts/ros-interfaces.md#L164)("같은 정의")도 바꿔야 한다. 오프라인 계산 결과는 아래와 같다(부록 A, 선형 강성 모델이며 가설).

| 디바운스 방식 (130 N/s = 43 N/mm × 3 mm/s) | 판정 지연 중앙/최대 | 판정 순간 참 힘 중앙/최대 |
|---|---|---|
| 현행: 샘플 3회 | 111 / 156 ms | 17.4 / 23.2 N |
| 값 변화 1회 | 67 / 111 ms | 11.7 / 17.4 N |
| 값 변화 2회 | 156 / 200 ms | 23.2 / 29.0 N |
| **값 변화 3회** | **244 / 289 ms** | **34.8 / 40.6 N** (과대 외력 30 N 초과, 탐침 밀림 43 N에 근접) |

  → **"값 변화 N=3"으로 바꾸면 안 된다.** 현행 "샘플 3회"는 사실상 "측정 1회 + 44 ms 대기"다. 노이즈를 거르는 효과는 없고 지연만 44 ms 늘린다. 선택지는 "값 변화 1회로 명시"(더 빠르지만 스파이크에 취약)와 "현행 유지 + 문서화" 둘이다. 판단에는 9/21 하강 23회를 다시 재생해 보는 것이 필요하다(c).

---

## §3 회의 결정 검토

### 회의 메모 구분
| 메모 문장 | 구분 |
|---|---|
| F1-3 "=> 0.5N으로 완화" | **결정** M1 |
| F1-5 "=> 500ms로 늘림" | **결정** M2 |
| F2-1 "-> 실측값 표기로 변경" | **결정** M3 |
| F2-3·F2-4 "->"(빈칸) | **미결정** M4 |
| F2-6 "하강 제한은 두 겹입니다…" | 앞부분은 감사 내용을 풀어 옮긴 것. 마지막 문장 "1차를 2차보다 약간 작게"가 **잠정 결정** M5 |
| "3·4번은… 5·6번은… 전자저울 실험을 가장 먼저" | 앞부분은 분류 해설. "실험 먼저"가 **결정** M6 |
| F3 "정지 경로 특별 취급… KPI 3초" | **결정** M7, M8 |
| "=> 사람이 펜던트로 래치 해제" | **결정** M9 |
| F5-2 "해결 방향은 명세에 힌트…" | 명세 7.4를 옮긴 부분 + **결정** M10 |
| F5-3 "관절각 비교…" | **결정** M11 |
| D-5 "래치가 뭔가요?… 비유" | 설명을 옮긴 것(아래처럼 오해가 있음). "논의 필요"는 **미결정** M12 |

### 메모에서 바로잡을 것
1. **D-5 설명의 오해.** 래치 해제 방법은 이미 정해져 있다(`/safety/reset` + 조건 해소, [units-frames:99](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/docs/contracts/units-frames.md#L99)). TBD인 것은 두 가지다.
   - ① 하강 제한마다 래치를 걸 것인지(#53)
   - ② ERROR 뒤 재시작 조건([ROS:705](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/docs/contracts/ros-interfaces.md#L705))
   
   그리고 F4를 막는 것은 "이중"이 아니다. **안전 사유로 끝난 실패는 1차만 걸려도 ERROR가 되고, ERROR에서는 RESUME이 안 된다**([SEQ:161-169](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/ws_cobot1/src/scan_manager/scan_manager/sequence.py#L161), [ST:345-348](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/ws_cobot1/src/scan_manager/scan_manager/state_machine.py#L345)). 이중 래치를 없애도 F4는 열리지 않는다.
2. **M3의 전제.** 웹은 지금 힘을 **아예 표시하지 않는다**. `robot/sample`에서 위치만 쓴다([App.jsx:483-495](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/frontend/src/App.jsx#L483)). RS:291은 웹에서 **입력한** 3 N 이야기다. 또 8.3 N은 "기준선 + 3"으로 낸 **추정값**이고, 10:36 기록은 밀기 중 Fz 0.3~1.3 N으로 이와 맞지 않는다([RS:115](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/docs/test-reports/realrobot-session_20260921.md#L115)).
3. **M1의 전제.** 0.29 N은 "홈에서 80 s 동안의 Fz 표준편차"다([RS:134](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/docs/test-reports/realrobot-session_20260921.md#L134)). tare 판정 지표인 "1.5 s 창의 |F−F₀| RMS"와 다르다.
4. **M2는 #130 선택지 A와 같다.** 다만 A는 "감독 시험 동안만 `param set`, yaml은 그대로"였다.
5. **M5는 하강 제한만 말한다.** D-5 설명은 과대 외력(30 N) 쌍을 말한다. 두 쌍 모두 같은 구조다(아래 M5).

### 결정별 판정
| # | 현재 상태 | 판정 |
|---|---|---|
| M1 | 0.3 그대로 | **조건부 적용** |
| M2 | 300 그대로. #130 선택지 A | **조건부 적용** |
| M3 | 웹에 힘 표시가 없음 | **수정 후 적용** |
| M4 | PR #132 OPEN | 미결정 → 선택지 제시 |
| M5 | #53 OPEN | **수정 후 적용** |
| M6 | 미실시 | **그대로 적용**(조건 있음) |
| M7 | 없음 | **수정 후 적용**(2단계) |
| M8 | BRD 1 s | **수정 후 적용** |
| M9 | — | **기각 후 대안** |
| M10 | 없음. #130에서 실제 발생 | **수정 후 적용** |
| M11 | 없음 | **그대로 적용** |
| M12 | #53 OPEN | §7로 |
| M13 | 전제 | **부분 수용** |

**M1: tare_max_std_n 0.3 → 0.5**
- **근거 데이터**: 9/20 홈 정지 CSV를 1.5 s 창 114개로 나눠 계산하니 RMS 중앙 0.047 N, 최대 0.199 N이었다(부록 A). 9/21 tare 3회는 0.143, 0.214, 0.110 N이다([RS:137](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/docs/test-reports/realrobot-session_20260921.md#L137), [:181](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/docs/test-reports/realrobot-session_20260921.md#L181), [:221](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/docs/test-reports/realrobot-session_20260921.md#L221)). 모두 0.3 아래다.
- **기능 파급**: 지금 데이터로는 풀 증상이 없다. 다만 "움직인 직후 치우침이 수 초에서 수십 초에 걸쳐 풀린다"는 계약 서술([ROS:141](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/docs/contracts/ros-interfaces.md#L141))을 보면, 이동 직후 tare가 0.3을 넘을 가능성은 남는다(9/21 bag으로 분포 미확인).
- **안전 파급**: #127 뒤로 tare F₀는 판정의 주 기준이 아니다. 출발 뒤 5.5 s의 6 N 판정, SLIDE 보고값, 툴 점검에만 쓴다. RMS 0.5에서 평균의 불확도는 약 0.5/√15 ≈ 0.13 N(힘 값 15개)이다. 3 N·6 N 임계에 비하면 무시할 수 있다. **유일한 손실은 "정지·무접촉이 아니었던 tare"를 거르는 힘이 약해지는 것**인데, `wait_still`과 |F₀| ≤ 6 N이 남아 있다.
- **연쇄 영향**: 계약 이름이 아니고 쌍 검사 대상도 아니다. sim은 Virtual 외력이 ≈0이라 영향이 없다.
- **조건**: TARE_UNSTABLE이 실제로 난 세션에서만 올리고, 그때 RMS 값과 날짜를 yaml 주석에 남긴다. 미리 올릴 근거는 아직 없다.

**M2: sample_stale_ms 300 → 500**
- **계산**: 기록된 공백 14개(316~365 ms 12개, 464, 687) 가운데 300에서는 14개가 모두 걸리고, **500에서는 687만 걸린다**(`safety_core` 재현, 부록 A). #130은 "500이어도 464가 걸린다"고 썼는데, 규칙상으로는 걸리지 않는다. 측정 방식이 다른지 확인해야 한다(가설).
- **기능 파급**: F1-5와 F2-5(goal의 약 40% 정지)는 대부분 풀린다. **F2-4(contact_detector의 `stale_age_ms` 100, [RY:33](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/ws_cobot1/src/contact_scan_bringup/config/real.yaml#L33))는 별개라 풀리지 않는다.** 687 ms급 공백은 여전히 정지·래치로 이어지고, 래치 → ERROR → 재시작 불가 구조도 그대로다.
- **안전 파급**: 공백 동안에는 1차와 2차가 모두 앞을 보지 못한다. 이것은 한계값과 무관하다. 바뀌는 것은 "공백 뒤 정지를 요청하는 시점"이 0.2 s 늦어지는 것뿐이다(3 mm/s면 0.6 mm, 5 mm/s면 1 mm). 공백은 주로 정지 중이나 출발 직전에 나므로(#130) 실제 위험 증가는 작다.
- **연쇄 영향**:
  - 계약: 값 자체는 계약이 아니다([ROS:7](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/docs/contracts/ros-interfaces.md#L7)). 하지만 "한계를 올리기 전에 원인부터 없앤다"는 지침([ROS:609-612](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/docs/contracts/ros-interfaces.md#L609), [CHANGELOG:41](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/docs/contracts/CHANGELOG.md#L41))과 어긋나므로, 예외라는 사실을 CHANGELOG에 한 줄 남기는 것이 맞다.
  - real의 `robot_status_timeout_ms` 500([RY:83](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/ws_cobot1/src/contact_scan_bringup/config/real.yaml#L83))과 같아지고, sim(500/1000/200)과 역전되지 않는다. 쌍 검사 대상이 아니다.
- **조건**: ① 감독 운용일 때만(`param set` 또는 감독 모드 플래그), ② real.yaml 주석에 #130 링크와 원복 조건, ③ #130 원인을 고치면 300으로 되돌린다.

**M3: 웹에 실측값 표시**
- **현재**: 웹은 힘을 표시하지 않는다. 기준선 Fz는 robot_manager 로그에만 남는다([RM:522-531](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/ws_cobot1/src/robot_manager/robot_manager/robot_manager.py#L522)).
- **문제**: "실측"을 조회 Fz로 정의하면 힘 제어 중에는 1 N 안팎이 보여서 오히려 오해를 부른다(F2-2). 저울 실험(M6)과 REL/ABS 결정(#73)이 먼저다.
- **수정안**: 세 값을 **나란히** 표시한다.
  - 설정(REL 증분) 3.0 N
  - SLIDE 시작 기준선 Fz
  - 추정 누름 = 기준선 + 설정("추정"이라고 표시)
  
  조회 Fz는 "힘 제어 중에는 참고용"이라고 표시한다. 계약 변경 없이 하려면 robot_manager가 기준선을 `RobotStatus.detail`(자유 문자열)에 실으면 된다(`robot/status`로 이미 웹에 간다). M6 이후 "실측"의 정의를 확정한다.

**M4: F2-3·F2-4 (미결정)**
- **PR #132**를 병합하고 켜면 F2-3은 풀린다(재생 4회, 실기 1회에서 x 464.4~466.7). 선행 조건 두 가지가 있다.
  - bias.py PR: `z_drop_valid=false`일 때 ValueError가 나지 않게 하는 것
  - ADR: BRD 4.1.2는 z 급강하가 주 신호다
  
  F2-4는 #132도 공백이 나면 힘 기준 구간을 버리므로 **풀리지 않는다**.
- **선택지**:
  - ① #132 병합 + 선행 조건 뒤 1.0 N으로 켜기 **(추천)**
  - ② EDGE용 공백 허용치를 `stale_age_ms`에서 떼어 별도 파라미터(예: `edge_max_gap_s` 0.25)로 두기. 샘플 폐기 기준(100 ms)은 그대로 둔다. F2-4용이며 ①과 함께 쓴다
  - ③ z 추세선만 조정하기: #132 본문에 따르면 0.2 mm·2 s로도 못 잡았고 0.1 mm에서는 거짓 EDGE가 났다 **(비추천)**

**M5: 하강 제한 1차 < 2차**
- **계약**: 7.2는 "값도 기준도 같게"를 요구한다([ROS:649-651](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/docs/contracts/ros-interfaces.md#L649)). #53을 결정하고 계약을 개정해야 한다.
- **C-9를 먼저 맞춰야 한다.** 1차 기준 z는 실행 직전의 마지막 위치이고 2차는 SLIDE 첫 샘플이다. 순응이 켜지면 z가 0.7 mm 올라온다([RS:115](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/docs/test-reports/realrobot-session_20260921.md#L115)). 기준이 다르면 1 mm 안팎의 여유는 의미가 없어진다.
- **"1차 ≤ 2차" 쌍 규칙만 바꾸면 깨진다.** ScanConfig의 `drop_limit_m`은 하나이고, SetConfig P03이 두 노드에 **같은 값**을 보낸다([propagation.py:38](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/ws_cobot1/src/scan_manager/scan_manager/propagation.py#L38)). SetConfig를 한 번 하면 여유가 사라진다.
- **수정안**:
  - `drop_limit_m`은 두 노드가 같은 값을 유지한다. 그래서 쌍 검사([propagation.py:56](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/ws_cobot1/src/scan_manager/scan_manager/propagation.py#L56), [test_config.py:20-23](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/ws_cobot1/src/contact_scan_bringup/test/test_config.py#L20))는 그대로 둔다.
  - safety_monitor에만 `drop_limit_margin_m`(예: 0.001, 계약 이름 아님)을 추가해 2차 판정을 `drop_limit_m + margin`으로 한다.
  - `confirm_n`은 1로 둔다(늦추는 수단은 여유 하나로).
  - 과대 외력 쌍(L3-1과 L3-16)도 같은 구조이지만 **과대 외력은 래치가 맞다**고 본다(장비 손상 영역).
- **한계**: M5만으로는 F4가 열리지 않는다(1차 DROP_LIMIT도 ERROR).

**M6: 전자저울 실험을 먼저**
- 조건:
  - 실기 절차서를 따르고, 입회자는 비상정지 대기
  - 저울 정격이 운용 과대 외력(10~15 N)보다 커야 함
  - 저울 자체의 강성 때문에 힘 제어의 거동이 큐브와 다를 수 있다는 점을 기록
  - 기준선 Fz, 설정값, 저울 값, 조회 Fz(힘 값이 약 94 ms마다 바뀐다는 점 포함)를 같은 시각축에 기록
  - 가능하면 REL과 ABS를 모두 기록
- M3, B-6, 누름 확인 임계의 근거가 된다.

**M7: 정지 경로 특별 취급**
- **1단계(지금 가능, Virtual 확인 불필요)**:
  - 대기열 **맨 앞으로 새치기**한다. 동시성은 바뀌지 않고 여전히 한 줄이다.
  - cancel과 `/robot/stop`의 **중복 정지를 합친다**(최근 정지가 확인됐으면 두 번째 `move_stop`은 건너뜀).
- **2단계(현재 호출을 무시하고 병행 전송)**: Virtual에서 "동시 호출이 드라이버를 멈추지 않는지" 확인한 **뒤에만** 한다. 동시 조회로 드라이버가 멈춘 이력이 있다([api-check-log.md:58](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/docs/env/api-check-log.md#L58)).
- **한계**: 1단계만으로는 "현재 호출이 느린" 창(최대 약 0.36 s, 드라이버가 멈추면 5 s)이 남는다.

**M8: 중지 KPI 1 s → 3 s**
- **3 s 동안의 이동 거리**: DESCEND 9 mm, SLIDE 15 mm, 재접근 6 mm, MOVE_TO와 올림 90 mm, HOME movej 60°(J1 반경 약 0.46 m면 팁이 최대 약 480 mm, 상한 추정).
- 접촉 중이라면 43 N/mm × 3 mm/s = 129 N/s라서 **0.31 s면 탐침이 밀리는 43 N에 닿는다.** KPI를 3 s로 두는 것은 받아들일 수 없는 영역이 있다.
- **수정안**: KPI를 둘로 나눈다.
  - ① **물리 정지**(버튼 클릭부터 TCP 속도 ≈0까지, bag에서 측정) ≤ 1 s는 유지한다.
  - ② **STOPPED 표시**(정지 확인 창 0.3 s, 상태 주기, `wait_still` 포함) ≤ 3 s로 새로 둔다.
- BRD 5장([BRD:348](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/docs/BRD.md#L348))과 9장([BRD:438](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/docs/BRD.md#L438))은 직접 고치지 않고, 팀 합의 뒤 새 버전으로 바꿔야 한다(문서 표현 규칙).

**M9: 펜던트로 래치 해제**
- **SW 래치**(safety_monitor)는 `/safety/reset` 서비스로만 풀린다([SMN:205-213](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/ws_cobot1/src/safety_monitor/safety_monitor/safety_monitor.py#L205)). **펜던트로는 풀 수 없다.**
- 펜던트가 다루는 것은 **L1**(비상정지 해제, 보호 정지)이다. 그런데 이 영역도 막힌 곳이 있다.
  - 드라이버는 제어권을 쥔 채 펜던트의 제어권 요청을 **거절**한다(`ws_dsr/…/dsr_controller2.cpp:3117-3119`, 소스 확인[E18]).
  - SAFE_STOP 같은 보호 정지는 드라이버가 **스스로** 복구한다(`:3071-3094`, 감사 L1-2).
  - SAFE_OFF에서 서보 온은 브링업 초기에 **한 번만** 하고, ROS에는 `servo_on` 서비스가 없다. 그래서 브링업을 다시 시작해야 회복된다(`docs/_local/DRL_실습_트러블슈팅.md` C-1, 레포 밖).
  - 사람의 조작과 드라이버의 자동 복구가 겹칠 여지가 있다(가설).
- **래치를 풀어도 ERROR → RESUME NOT_SUPPORTED는 남는다.**
- **대안**: 펜던트 비상정지 → 눈으로 확인 → L1 회복(필요하면 브링업 재시작) → 탐침 점검 → `/safety/reset`(웹 버튼 D-7, 없으면 사람이 CLI) → 새 START. 아래 §6 절차다.

**M10: 안전복귀 전 수직 올림**
- **현재**: `run_home`은 OP_HOME 하나만 보낸다([SEQ:598-601](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/ws_cobot1/src/scan_manager/scan_manager/sequence.py#L598)). 정상 마무리는 올림 뒤 HOME이다([SEQ:492-497](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/ws_cobot1/src/scan_manager/scan_manager/sequence.py#L492)). #130에서 **올림이 실패했는데 HOME이 나간 사례가 2회** 있다.
- **수정안**:
  - ① 올림이 TARGET_REACHED일 때만 HOME으로 진행하고, 실패하면 멈추고 사람에게 넘긴다.
  - ② 정지 위치를 모르면 올리지 말고 사람이 펜던트로 조그한다.
  - ③ 올림도 HOME처럼 래치를 보지 않게 한다(A-10 일관성).
  - ④ J6 −204.84°와 실제 회전 방향은 실기에서 사람이 확인한다.
- 계약 7.4와 9장 "홈 복귀 경로" TBD를 개정해야 한다.

**M11: HOME 도착 검증**
- `aux_control/get_current_posj`가 있다(`ws_dsr/…/dsr_controller2.cpp:2454`). 직렬 큐에 넣고, 허용치 `home_arrival_tolerance_deg`를 yaml에 둔다.
- 같은 방식으로 C-6(DESCEND·SLIDE 이동 거리 검증)도 함께 고치는 것을 권한다.

**M13: 펜던트 감시가 커버하는 범위**
| 범위 | 내용(사람 반응 1~2 s 가정) |
|---|---|
| **커버됨**(눈에 보이고 느림) | DESCEND 3~6 mm, SLIDE 5~10 mm, 재접근 2~4 mm, MOVE_TO와 올림 30~60 mm, HOME 20~40°(팁 최대 약 160~320 mm). 경로 이상, 부재 끌림, 큐브 밀림(19 mm) |
| **커버 안 됨: 사람보다 빠른 장비 손상** | 접촉 중 힘 상승 129 N/s(DESCEND), 86 N/s(재접근). 3 N에서 43 N까지 0.31~0.47 s → **B-5, SW 과대 외력 한계만이 막는다** |
| **커버 안 됨: 보이지 않는 SW 상태** | D-1(진행 중 감시자 사망), C-4(level=STOP인데 latched=false로 진행), C-2(연결 판정 이후 무감시), D-2(L1 정지를 NO_CONTACT로 오보) |
| **커버 안 됨: 종료 뒤 상태** | C-1(프로세스 종료 뒤 순응·힘 제어가 켜진 채 남을 가능성) |
| **커버 안 됨: 측정값 오염** | C-7(판정 지연에 따른 편향), 툴 등록 풀림(D-6) |

  **최소 보완**:
  - 두 번째 사람(화면 담당)이 안전 상태와 로그 표시를 본다(D-7, #120 웹 표시).
  - 시작 전 점검에 툴·TCP, 감시자 생존, 시계를 넣는다(§6).
  - Ctrl+C 금지 규칙과, 먼저 중지를 확인하는 절차를 둔다(C-1).
  - 과대 외력 운용값을 yaml에 기록한다(B-5).
  - 종료 후 제어 모드를 확인한다(#125).

---

## §4 회의에서 다루지 않은 미해결 항목

| 항목 | 방침으로 커버되는가 | 필요한 것 |
|---|---|---|
| B-1 | 해결됨(#127) | 대신 **F1-1이 #141·#142로 남았다**. #141(2.96 mm 기준점)은 결정해야 한다 |
| C-1 Ctrl+C·크래시 | **안 됨**(b). 펜던트로는 "순응이 켜져 있는지"가 보이지 않는다 | 운용: 먼저 중지 → STOPPED 확인 → 종료. 코드: 종료 훅에서 정지·해제 |
| C-2 연결 흔들림 | **통신 보류 대상이 아님**(b). DESCEND에서 최대 120 mm 무감시 | 연속 N회 판정 + 정지 시도(하) |
| D-1 잔여 | 부분. 감시자가 진행 중에 죽으면 사람은 모른다 | 웹 표시(#120), 진행 중 동작 결정(c) |
| B-5 30 N / 운용 15·10 N | **안 됨**. 사람보다 빠르다 | 운용값을 yaml에 기록하고, overshoot 실측으로 결정 |
| D-2 L1 비가시 | 부분. 사람은 로봇이 멈춘 것은 보지만 SW 결과는 오보다 | robot_state와 `/dsr01/error`를 error에 싣기(중) |
| D-7 웹 안전 UI | 안 됨. F4 절차를 사람이 실행할 수단이 없다 | 표시 + reset 버튼(FastAPI 엔드포인트는 [main.py:501](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/backend/app/main.py#L501)에 있음) |
| L4-2 시계 차 | 운용으로 가능(d) | 시작 전 chrony 확인 |
| F4 전체 | 안 됨. 구조 문제 | §7-1 결정 |
| C-4 경쟁 | 안 됨(보이지 않는 상태) | 판정 규칙 통일(하) |
| C-6·C-10 | 부분 | 이동 거리 검증, NaN |
| C-8 | 표시 문제 | #133 처리 → **0-1절: #145로 해결** |
| C-9 | M5의 선행 조건 | 1차 기준 z를 계약대로 |
| B-4·B-7 | — | yaml 이관, 속도 하한 검사 |
| D-3·D-4 | 운용으로 가능(d) | MVP 범위 밖이라고 명시(§5-7) |
| D-6(#123) | 부분 | 시작 전 등록 확인 |
| D-8·F6-2·F6-3 | — | sim에 실기형 프로파일(낙하 0.35~2 mm/s), 합성 샘플 시험 |
| F3-3 | 안 됨 | §5-3 |
| F2-7 | 판단 불가 | 실기 기록 누적 |

---

## §5 추가 완화안

**공통 틀.** real.yaml에 `supervised_mode: true`를 두고, 켜져 있으면 기동 로그와 `SafetyStatus.detail`·`RobotStatus.detail`(자유 문자열)로 웹에 표시하고 실습 기록에 남긴다. 계약은 바꾸지 않는다.

| # | 완화안 | 풀리는 것 | 사람이 볼 것 | 남는 위험 | 영향 파일·난이도 | 개정 필요 | 추천 |
|---|---|---|---|---|---|---|---|
| 1 | 감독 모드에서 SAMPLE_STALE·상태 최신성을 **2단계**로: 한계 초과는 WARN(래치·정지 없음), 긴 한계(예: 1.5 s) 초과는 STOP + 래치 | F1-5, F2-5(687 ms 포함) | 화면의 WARN, 로봇 움직임 | 공백 동안 1·2차 모두 못 본다(한계값과 무관) | SC·SMN·RY / 중 | CHANGELOG에 예외 기록 | **조건부**(#130 원인 수정 전까지). M2보다 넓게 덮는다 |
| 2 | goal 수락 뒤 짧은 유예(예: 1.5 s) | #130 패턴 | 출발 순간 | 출발 순간의 실제 끊김 | SMN / 중 | 같음 | 조건부. 1을 택하면 불필요 |
| 3 | 정지 확인 실패 시 "STOPPED + 정지 미확인 경고" | F3-3 | 로봇이 멈췄는지 눈으로 | 움직이는 로봇에 RESUME. 단 robot_manager의 미확인 정지 관문(A-3)이 새 goal을 막는다 | ST·SEQ / 중 | **계약 상태표** 개정 | 조건부 |
| 4 | 재시작 허용 사유 목록: 403·404·정지 미확인만 reset 뒤 RESUME 허용. OVER_FORCE·DROP_LIMIT은 탐침 점검 후 새 START | F4 일부 | reset 전 현장 확인 | 사유 분류가 틀리면 오염된 기준으로 재개 | ST(FAILED가 재개점을 지운다, [ST:431](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/ws_cobot1/src/scan_manager/scan_manager/state_machine.py#L431))·resume.py / 중 | 계약 9장 TBD 해소 | **추천**(§7-1) |
| 5 | 쌍 검사를 "1차 ≤ 2차"로 | — | — | SetConfig P03이 같은 값을 보내 여유가 사라진다 | propagation·test_config / 하 | 7.2 | **비추천**. 대신 M5 수정안(`drop_limit_margin_m`) |
| 6 | 명령 만료 5 s 확대 | L4-2 | — | 재연결 뒤 옛 START가 늦게 실행될 수 있음 | CG / 하 | mqtt-schema | **비추천**. 대신 시작 전 chrony 점검 **추천** |
| 7 | heartbeat, 속도·작업영역·z 하한 감시를 MVP 범위 밖으로 명시하고 운용 규칙으로 대체 | D-3·D-4 정리 | 브라우저 단절 시 펜던트 감시 | 웹이 끊겨도 로봇은 계속 | 문서 / 하 | BRD 6장·계약 9장에 "MVP 제외" | **추천** |
| 8 | tare 방식 추가 완화 | — | — | 툴 등록 점검(TOOL_REG_SUSPECT)이 사라지면 D-6의 유일한 방어선이 없어진다 | — | — | **비추천**(#127로 충분) |
| 9 | connected를 N회 연속 실패로 판정 + 끊김 경로에서도 `move_stop` 시도 | C-2, 거짓 ROBOT_DISCONNECTED | — | 판정 N 샘플만큼 늦음 | RM / 하 | 없음 | **추천**(완화이면서 안전 강화) |
| 10 | EDGE 공백 허용치를 `stale_age_ms`에서 분리 | F2-4 | 밀기 중 모서리 | 공백 전후 추세를 잇는 판정 오차 | DC·RY / 하 | 없음 | 조건부(M4 ②) |

**유지할 선에 대한 의견.** 제시된 목록에 동의한다. 여기에 넷을 더 두기를 권한다.
- ① "모르면 moving=true"(A-7)와 미확인 정지 관문(A-3): 정지 완료 판단의 근거다.
- ② 툴 등록 점검(tare |F₀| ≤ 6)
- ③ **과대 외력 한계는 올리지 않는다.** 사람보다 빠른 영역이다.
- ④ HOME에 넣는 올림 단계도 래치를 보지 않는다.

---

## §6 펜던트 감시 실습 운용 규칙 초안

**역할과 위치**
- **감시자**: 펜던트를 들고 로봇 작업 반경 밖에서 탐침과 큐브가 모두 보이는 자리에 선다. 비상정지에서 손을 떼지 않는다.
- **화면 담당**: `/safety/status`, `/scan/log`, 로봇 상태를 본다. 감시자와 말로 즉시 소통한다.
- **실기 명령**: 사람만 친다(CLAUDE.md 규칙 1).

**시작 전 점검**(실습 기록에 남김)
1. **툴·TCP**: `apply_tool_tcp.py`의 마지막 줄이 `OK`인지, `rg2_probe`·`rg2_probe_tip`인지 확인. `sodreal`을 다시 켰다면 반드시 다시 확인한다([units-frames:93](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/docs/contracts/units-frames.md#L93)).
2. **탐침 상태**: 기준점 접촉이 ±0.3 mm 안인지([units-frames:63-68](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/docs/contracts/units-frames.md#L63)). 큐브는 본드로 고정.
3. **safety_monitor 생존**: `/safety/status`가 약 1 Hz로 오는지, stamp가 최신인지, `/scan/log`에 끊김 WARN이 없는지.
4. **시계 동기**: 두 PC의 `chronyc tracking` 오프셋이 1 s 미만인지.
5. **운용 힘 한계**: 이번 세션의 `over_force_n` 값을 기록한다(yaml과 다르면 이유도). `supervised_mode`나 `param set` 같은 완화를 켰는지도 기록한다.

**동작 중 감시 포인트**
| 동작 | 볼 것 | 즉시 비상정지 |
|---|---|---|
| DESCEND | 윗면에서 멈추는지 | 윗면을 지나 계속 내려감, 탐침 휨 |
| SLIDE | 큐브가 밀리지 않는지, 모서리에서 떨어지는지 | 큐브 이동, 모서리를 지나 5 mm 넘게 진행 |
| 재접근·올림 | 저속인지, 올림이 끝났는지 | 올림 없이 수평 이동이나 HOME 시작 |
| HOME | 먼저 올라가는지, J6 회전, 케이블 | 탐침이 부재에 닿은 채 출발 |

화면 담당은 WARN, SAMPLE_STALE, "정지 확인 실패", "끊김" 로그가 나오면 바로 소리 내어 알린다.

**이상 시 절차**
1. 감시자가 펜던트 비상정지를 누른다.
2. 상태를 확인한다: 펜던트 알람, `/robot/status`, `/safety/status`, 탐침 상태.
3. L1을 회복한다: 비상정지 해제. SAFE_OFF에서 움직이지 않으면 **브링업을 다시 시작**한다(사람).
4. 과대 외력이나 충돌 뒤라면 탐침 점검 1~5를 다시 한다.
5. SW 래치를 해제한다: 웹 reset(D-7 이후) 또는 사람이 `/safety/reset`. CONDITION_ACTIVE면 원인부터 해소한다.
6. 복귀: STOPPED면 재시작할 수 있다. ERROR면 안전복귀(올림 확인) 뒤 **새 START**를 한다.

---

## §7 팀 결정이 필요한 항목

| # | 결정 | 선택지 | 추천 |
|---|---|---|---|
| 1 | ERROR 재시작 정책(F4, 계약 9장) | ① 현행(새 START만) / ② 사유별 허용(403·404·정지 미확인) / ③ 모든 안전 사유를 사람 확인 뒤 허용 | **②** |
| 2 | #53 하강 제한 래치 | ① 현행 동시 래치 / ② 2차에 `drop_limit_margin_m` / ③ 2차 `confirm_n` 2 | **②**(C-9를 먼저 맞춤) |
| 3 | 최신성 완화 | ① M2(500, 감독 한정) / ② §5-1 2단계 / ③ goal 유예 | 지금은 **①**, #130 원인이 늦게 풀리면 ② |
| 4 | REL/ABS(#73) | ① REL 유지 + 세 값 표시 / ② ABS / ③ M6 뒤 결정 | **③ → ①** |
| 5 | EDGE 힘 꺾임(#132) | ① bias PR·ADR 뒤 켜기 / ② 꺼 둠 | **①** |
| 6 | 중지 KPI | ① 물리 정지 1 s 유지 / ② STOPPED 표시 3 s 신설 / ③ 물리 3 s | **① + ②** |
| 7 | 안전복귀 경로 | ① 현행 / ② 올림 성공 확인 뒤 HOME / ③ 위치 불명이면 사람이 조그 | **② + ③** |
| 8 | 운용 과대 외력 | ① 30 N 유지 / ② 15 N을 근거와 함께 yaml에 / ③ 10 N | **②**(overshoot 실측 뒤) |
| 9 | 디바운스 정의(C-7) | ① 현행 유지 + 문서화 / ② 값 변화 1회 + ms 조건 / ③ 값 변화 N=3 | **①**, 재생 뒤 ② 검토. **③은 불가** |
| 10 | #141 기준점 | 옛 값 유지 / 새 하강점 | 학민과 결정(TR-02 ±3 mm와 같은 크기) |

---

## §8 개정이 필요한 문서·파라미터

| 대상 | 내용 |
|---|---|
| BRD(새 버전으로 교체) | KPI 정의(물리 정지와 STOPPED)([BRD:348](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/docs/BRD.md#L348), [:438](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/docs/BRD.md#L438)), MVP 제외 목록(heartbeat·속도·작업영역), 4.5.4 여유 |
| `ros-interfaces.md` + CHANGELOG | 7.2(여유), 9장(재시작 조건, 홈 경로), 7.4(안전복귀 올림), 3.3·[:164](https://github.com/yujh5537/rokey_cobot1_Weld-Made/blob/5ac5652eb4b14bc052181d32511ad197d707bc58/docs/contracts/ros-interfaces.md#L164)(디바운스 정의), 6.3(M2 예외), 5.2(#136 HOME 관문 반영), 상태표(§5-3 선택 시) |
| `api-check-log.md` | `get_tool_force` 값 갱신 약 94 ms(10 Hz) |
| 정의서 v1.2 | 참고 문서. 1100-1107의 "MVP 제외" 표기만 |
| real.yaml | `tare_max_std_n`(조건부), `sample_stale_ms`(감독 한정), `over_force_n` 운용값, `supervised_mode`, `drop_limit_margin_m`, `home_arrival_tolerance_deg`, `stop_settle_s` 이관, mqtt_bridge 절 |
| sim.yaml | 같은 키 추가(sim ≥ real 관계 유지), 실기형 낙하 프로파일 |
| `test_config.py`·`propagation.py` | 여유를 파라미터로 두면 **변경 없음**. `supervised_mode`의 real 기본값 검사를 추가 |
| README(robot_manager, contact_detector, scan_manager) | 동작 변경 부분 |

---

## §9 확인하지 못한 것과 확인 방법

| 항목 | 방법 · 주체 |
|---|---|
| 9/21 bag의 공백 분포 꼬리(464·687 ms의 정체), 이동 직후 tare RMS | bag을 가진 사람이 오프라인으로 분석(bag은 레포 밖) |
| #135의 "모션 중에도 늦음"과 #130의 "모션 중 공백 없음"의 불일치 | #135 로그 대조 · 사람 |
| `move_stop`을 병행 전송해도 드라이버가 멈추지 않는지 | Virtual |
| 펜던트로 보호 정지·서보 온을 할 수 있는지(드라이버가 제어권 요청을 거절함) | 실기 · 사람 |
| 프로세스 종료 뒤 순응이 남는지(`GetControlMode`로 구분되는지, #125) | 실기 · 사람 |
| 힘 제어 중 조회값의 의미 | M6 저울 실험 · 실기 |
| 과대 외력 overshoot | OVER_FORCE 사건 bag · 오프라인 |
| HOME의 J6 회전 방향 | 실기 · 사람 |
| C-7 디바운스 선택지의 실측 영향 | 9/21 하강 23회 재생 · 오프라인 |
| L1 설정값(충돌 감도, TCP 한계, 수동 250 mm/s) | 펜던트 화면 기록 · 사람 |
| #145의 stop 완료 통지 동작 | sim 종단(PR 본문상 미확인) |

---

## 부록 A. 오프라인 계산 스크립트

ROS와 로봇 없이 레포 루트에서 `python3 review_calc.py`로 돈다. 쓰는 모듈(`detector_core`, `safety_core`)은 5ac5652와 cc64cbc가 같다. 2026-09-22 결과는 아래 표와 같다(C-7의 표는 난수 시드 0, 2000회).

```python
import csv, random, sys
sys.path.insert(0, 'ws_cobot1/src/contact_detector'); sys.path.insert(0, 'ws_cobot1/src/safety_monitor')
from contact_detector.detector_core import (TareAccumulator, TareConfig, ContactDetector, DetectorConfig, Sample, OP_DESCEND)
from safety_monitor.safety_core import SafetyLimits, ConditionWatch

# ---- M1: 1.5 s 창 tare RMS 분포 (2026-09-20 실기, 기록기 단독, 홈 정지 30 s) ----
rows = [r for r in csv.DictReader(open('docs/test-reports/data/20260920/idle_30s.csv')) if r['valid'] == '1']
T = [float(r['t_force_s']) for r in rows]; F = [(float(r['fx_n']), float(r['fy_n']), float(r['fz_n'])) for r in rows]
rms, t0 = [], T[0]
while t0 + 1.5 <= T[-1]:
    acc = TareAccumulator(TareConfig(30, 99.0, 99.0))
    for t, f in zip(T, F):
        if t0 <= t < t0 + 1.5:
            acc.add(Sample(0, t, t, (0, 0, 0), f))
    rms.append(acc.result().std_vector_n); t0 += 0.25
q = sorted(rms)
print(f'M1 창 {len(q)}개: RMS 중앙 {q[len(q)//2]:.3f} · 최대 {q[-1]:.3f} N (0.3 초과 {sum(x>0.3 for x in q)}, 0.5 초과 {sum(x>0.5 for x in q)})')

# ---- M2: 공백 길이별 SAMPLE_STALE 판정 (safety_core.check_freshness) ----
gaps = [316, 338, 344, 347, 347, 349, 352, 353, 357, 358, 360, 365, 464, 687]   # #130, RS 샘플 간격 표
for lim in (300, 500):
    w = ConditionWatch(SafetyLimits(30.0, 0.005, lim, 500, 1, 3.0))
    hit = [g for g in gaps if w.check_freshness(10.0, 10.0 - g / 1000, 10.0, 10.0) or w.active.pop('SAMPLE_STALE', None)]
    print(f'M2 sample_stale_ms={lim}: 걸리는 공백 {hit}')

# ---- C-7: 힘 값 약 94 ms 갱신에서 디바운스 방식별 판정 시점 (선형 강성 모델, 가설) ----
def trial(rate_n_s, mode, n, rng):
    det = ContactDetector(DetectorConfig(3.0, n, 30.0, 1)); det.set_baseline((0.0, 0.0, 0.0))
    phase, t_cross = rng.uniform(0, 0.094), 1.0          # 참 힘이 t=1.0 s 에 3 N 을 넘는다
    held, last, t, sid = 0.0, None, 0.0, 0
    while t < 3.0:
        k = int((t - phase) // 0.094)                    # 힘 캐시 갱신 번호
        fresh = k != last
        if fresh:
            last = k
            held = max(0.0, rate_n_s * (phase + k * 0.094 - (t_cross - 3.0 / rate_n_s)))
        if mode == 'samples' or fresh:                   # 'values' = 값이 바뀐 샘플만 센다
            sid += 1
            if det.update(Sample(sid, t, t, (0, 0, 0), (0.0, 0.0, held), True, 1, OP_DESCEND)):
                return t - t_cross, rate_n_s * (t - (t_cross - 3.0 / rate_n_s))
        t += 1 / 45.0                                    # 샘플 약 45 Hz
rng = random.Random(0)
for rate in (130.0, 24.0):                               # 43 N/mm × 3 mm/s, PR #140 의 보수적 중앙값
    for mode, n in (('samples', 3), ('values', 1), ('values', 2), ('values', 3)):
        res = [trial(rate, mode, n, rng) for _ in range(2000)]
        lat = sorted(r[0] for r in res); frc = sorted(r[1] for r in res)
        print(f'C-7 {rate:>5.0f} N/s {mode:>7} N={n}: 지연 중앙 {1000*lat[1000]:.0f} · 최대 {1000*lat[-1]:.0f} ms, '
              f'판정 순간 참 힘 중앙 {frc[1000]:.1f} · 최대 {frc[-1]:.1f} N')
```

| 계산 | 결과 |
|---|---|
| M1 | 창 114개: RMS 중앙 0.047 · 최대 0.199 N (0.3 초과 0, 0.5 초과 0) |
| M2 | 300 ms: 14개 모두 걸림 / 500 ms: 687만 걸림 |
| C-7, 24 N/s | 샘플 3회: 5.7 / 6.7 N · 값 변화 1회: 4.6 / 5.7 N · 2회: 6.7 / 7.8 N · 3회: 8.9 / 9.9 N (판정 순간 참 힘 중앙/최대) |
| C-7, 130 N/s | §2 표 |
