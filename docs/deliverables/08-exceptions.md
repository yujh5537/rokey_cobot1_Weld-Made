# 08. 예외 · 오류 리스트와 처리

근거: 레포 `docs/contracts/ros-interfaces.md` 6.1(ReasonCode) · 7.1(세 정지 경로) · 7.2(이중 감시) ·
`docs/test-reports/daily/20260923.md` §7 · `docs/test-reports/safety-audit-review_20260922.md` ·
`docs/phase2/weld-ros-interfaces.md`(6xx)
작성: 학민 · 2026-09-24 · ✔ = 실기에서 실제로 겪은 것

## 1. 정지 경로는 셋이고 서로 다르다

| 경로 | 누가 요청 | 접수 확인 | 완료 확인 | 재개 |
|---|---|---|---|---|
| ① **웹 작업 중지** | 사람 → `cmd/scan/stop` → `/scan/stop` → `/robot/stop` + goal cancel | `StopScan.accepted` | `/scan/state` → `STOPPED` | **RESUME 가능** |
| ② **판정 정지** (접촉 · 엣지 · 과대 외력) | robot_manager 자체 | 없음 | `ExecuteMotion.Result` | 정상 흐름 |
| ③ **안전 이상** | safety_monitor → `/robot/stop`(웹 경유 없음) | `StopRobot.accepted` | `SafetyStatus.stop_confirmed` | **불가 — ERROR 로 간다** |

> ①과 ③의 차이가 시연에서 제일 헷갈린다. **①은 `STOPPED` 라 재개되고, ③은 scan_manager 가
> "내가 요청하지 않은 정지"로 보아 `ERROR` 로 가므로 RESUME 이 거절된다.** 처음부터 다시 돌려야 한다.

## 2. 예외 · 오류 표

| 상황 | 감지 노드 | 코드 | 로봇 동작 | 화면 | 관제자 조치 | 실기 |
|---|---|---|---|---|---|---|
| 동작 중 새 goal | robot_manager | `BUSY(100)` | 없음 | 거절 표시 | 끝날 때까지 기다린다 | |
| 필수 파라미터 없음 · 범위 밖 | 각 노드 | `INVALID_VALUE(102)` | 없음 | 거절 | yaml 확인. `slide_target_force_n` · `home_joint_deg` · `step_*` 가 없으면 그 동작만 거절된다 | ✔ |
| 안전 래치 중 START | scan_manager | `SAFETY_LATCHED(103)` | 없음 | 래치 표시 | 웹 **안전 해제**(#164) 후 재시도 | ✔ |
| 드라이버 미연결 | robot_manager | `ROBOT_DISCONNECTED(104)` | 없음 | 연결 끊김 | 랜선 · 브링업 확인 후 재기동 | ✔ |
| 사람이 누른 작업 중지 | scan_manager | `STOP_REQUESTED(200)` | 감속 정지 | `STOPPED` | 재개 또는 안전복귀 | ✔ |
| 최대 거리까지 미접촉 | robot_manager → scan_manager | `MAX_DISTANCE(202)` → `NO_CONTACT(300)` | 정지 | 실패 | 부재 유무 · 기준점 높이 확인 | ✔ |
| 최대 거리까지 미소실 | 〃 | `MAX_DISTANCE(202)` → `NO_EDGE(301)` | 정지 | 실패 | 방향 전환 뒤 떠서 출발했는지 확인 | ✔ |
| **멈췄는데 목표에서 벗어남** | robot_manager | `ROBOT_ERROR(204)` | 정지 확인 | 실패 | 드라이버 응답 지연(#130) 로그 확인. **두산 `success` 는 도착의 증거가 아니다** | ✔ |
| **SLIDE 하강량 제한** | robot_manager(1차) · safety_monitor(2차) | `DROP_LIMIT(205)` | 즉시 정지 | 래치 | **팁이 모서리 밖 아래에 있다.** +Z 조그만으로 부족할 수 있으니 옆면 접촉부터 확인하고 부재 **바깥쪽**으로 먼저 뗀다 | ✔ |
| 툴 · TCP 미등록 | contact_detector(tare) | `TOOL_REG_SUSPECT(302)` | START 거절 | 실패 | `apply_tool_tcp.py` 재등록 후 재시도 | ✔ |
| tare 중 외력 불안정 | contact_detector | `TARE_UNSTABLE(305)` | START 거절 | 실패 | 진동원 제거 후 재시도 | |
| `/robot/sample` 없음 | scan_manager | `NO_SAMPLE(307)` | START 거절 | 실패 | robot_manager 기동 확인 | |
| **과대 외력** | contact_detector · safety_monitor (둘 다 30 N) | `OVER_FORCE(400)` | 즉시 정지 + 래치 | 래치 | **탐침 상태부터 본다**(밀림 · 휨). 이 표가 아니라 `units-frames.md` 탐침 전제조건 | ✔ |
| **샘플 최신성 위반** | safety_monitor (`sample_stale_ms` 500) | `SAMPLE_STALE(403)` | 즉시 정지 + 래치 | 래치 | **아래 3 절 순서대로** | ✔ |
| 로봇 상태 미수신 | safety_monitor | `ROBOT_STATUS_LOST(404)` | 정지 + 래치 | 래치 | robot_manager 확인 | |
| 웹 heartbeat 만료 | safety_monitor | `HB_EXPIRED(405)` | 정지 | 표시 | 웹 연결 확인 | |
| 래치 해제 요청인데 조건이 아직 참 | safety_monitor | `CONDITION_ACTIVE(406)` | 없음 | 거절 | 원인이 사라져야 풀린다 | ✔ |
| 5점 미확보 | scan_manager | `INSUFFICIENT_POINTS(501)` | — | 실패 | 실패한 방향 확인 | ✔ |
| 표에 없는 코드 | mqtt_bridge | `UNKNOWN_<n>` | — | 원문 표시 | 계약 표 갱신 (#90) | |
| *(phase 2)* 경로 goal 거절 | robot_manager | `PATH_REJECTED(604)` | 없음 | 거절 | 경유점 z · 속도 · 점 수 확인 | 미실시 |

## 3. `SAMPLE_STALE(403)` 대응 — 시연에서 가장 자주 나온다

전체 절차는 `docs/test-reports/daily/20260923.md` §7(병후)이 정본이다. 요약만 둔다.

1. **입회자가 눈으로** 로봇이 멈췄는지 본다. 멈추지 않으면 **즉시 비상정지**
2. 사유 확인. **403 이면 이 순서, 400 · 205 면 탐침 점검부터**
3. 팁 위치 판단 — 윗면 위 / 모서리 근처 / 공중
4. **펜던트 수동 모드**로 Base 좌표계 **+Z 30~50 mm 수직 조그**(관절 조그 아님). 공중이면 생략
5. **자동 모드로 되돌리고 제어권을 넘긴 뒤 툴 · TCP 등록 유지를 확인한다.** 풀렸으면 START 하지 않는다
6. 웹 **안전 해제** → **안전복귀** → **START(처음부터)**

**하지 말 것**: 4 번 없이 안전복귀 · 팁이 닿은 채 옆으로 조그 · 5 번 없이 웹 명령 · `Ctrl+C` 로 노드 종료 ·
시연 중 `sample_stale_ms` 변경.

**시간 예산**: 복구 1~2 분 + 새 스캔 약 5 분. 9/22 기록으로 스캔 4~5 회에 한 번꼴이라
시연 순서에 **재시도 1 회분(약 7 분)** 여유를 둔다.

## 4. 남은 구멍

| 내용 | 이슈 |
|---|---|
| `sample_stale_ms` 500 으로도 막지 못하는 공백이 있다(9/22 기록 699 · 748 ms 2 건) | #130 |
| `compliance_released=true` 는 **해제 호출 성공**이라는 뜻이고 실제 제어 모드 조회는 아직 없다 | #125 |
| tare 를 거치지 않는 수동 goal(`OP_MOVE_TO` · `OP_HOME`)은 툴 미등록을 막지 못한다 | #123 |
| main 의 안전복귀는 올리지 않고 바로 `OP_HOME` 을 보낸다(PR #161 미머지, 실기 미검증이라 시연 전 머지 안 함) | #161 |
