# safety_monitor

소프트웨어 이상 감시 → **웹을 거치지 않는** 정지 요청과 래치. 담당: 현지 (T18, T33). 계약: [`ros-interfaces.md`](../../../docs/contracts/ros-interfaces.md) 2.1 · 3.7 · 4.4 · 6.3 · 7.1 ③ · 7.2.

| 파일 | 역할 | rclpy |
|---|---|---|
| `safety_monitor/safety_core.py` | 감시 조건 · 정지 요청 상태(접수 · 확인 · 재요청) · 래치 | 안 씀 |
| `safety_monitor/safety_monitor.py` | 노드. 구독 · `/robot/stop` 비동기 호출 · `/safety/status` 발행 · `/safety/reset` 서비스 · 파라미터 콜백(SetConfig P03) | 씀 |

| 방향 | 이름 | 타입 · QoS | 계약 |
|---|---|---|---|
| 구독 | `/robot/sample` | `RobotSample` · SENSOR | 3.1 (외력 · z · `operation`) |
| 구독 | `/robot/status` | `RobotStatus` · STATE | 3.2 (정지 완료 = `connected && !moving`) |
| 발행 | `/safety/status` | `SafetyStatus` · STATE (변경 시 + 주기) | 3.7 |
| 클라이언트 | `/robot/stop` | `StopRobot` (`requester = 'safety_monitor'`) | 4.1 · 7.1 ③ |
| 서비스 | `/safety/reset` | `ResetSafety` | 4.4 |
| 파라미터 | `over_force_n` · `drop_limit_m` | SetConfig 전파 P03 | 2.4 · 6.4 |

## ⚠️ 이 노드가 할 수 없는 것
**하드웨어 안전을 대체하지 않는다**(BRD 4.5 각주, 계약 3.7). 최종 안전 수단은 티치펜던트의 물리 비상정지와 로봇 내장 충돌 감지다.

특히 **드라이버가 서비스에 응답하지 않으면 `/robot/stop` 도 `/robot/status` 도 같이 죽는다**(`docs/env/api-check-log.md`). 정지 요청도, 정지 완료 확인도 그 한 지점에서 함께 무력화된다. 그래서 이 노드는 "요청 접수"와 "정지 완료 확인"을 구분하고, 확인되지 않으면 **그 사실을 계속 STOP 으로 올린다**(`detail` 에 "물리 비상정지가 필요할 수 있다"). 화면에 그 문구가 뜨면 사람이 비상정지를 눌러야 한다.

## 감시하는 것
| 조건 | 판정 | ReasonCode | level |
|---|---|---|---|
| 과대 외력 | 원시 `\|F\| > over_force_n`. 영점(tare)에 의존하지 않는다 | `OVER_FORCE(400)` | 항상 STOP |
| 하강 제한 | SLIDE 중 z 가 기준보다 `drop_limit_m + drop_limit_margin_m` 넘게 내려감 | `DROP_LIMIT(205)` | 항상 STOP |
| 샘플 최신성 | `/robot/sample` 이 `sample_stale_ms` 넘게 없음 | `SAMPLE_STALE(403)` | 움직이는 중이면 STOP, 서 있으면 WARN |
| 상태 최신성 | `/robot/status` 가 `robot_status_timeout_ms` 넘게 없음 | `ROBOT_STATUS_LOST(404)` | 〃 |

- **하강 제한의 기준 z = `operation` 이 `OP_SLIDE` 로 바뀐 첫 샘플의 z**(계약 7.2). 1차(robot_manager)와 **기준 z 는 같다** — robot_manager 도 자기가 `OP_SLIDE` 로 발행한 첫 유효 샘플의 z 를 쓴다(같은 메시지의 같은 값). 방향이 바뀌어 SLIDE 를 다시 시작하면 기준도 다시 잡는다
- **한계는 1차보다 여유만큼 뒤다** (v0.1.21 결정 2, #53): 2차 = `drop_limit_m + drop_limit_margin_m`. real · sim 모두 1차 5 mm · 2차 10 mm.
  - 1차 = 정상 동작의 제한(넘으면 그 SLIDE 를 실패로 끝낸다). 2차 = 1차가 막지 못했을 때의 최후 방어선(정지 + 래치)
  - `drop_limit_m` 자체는 두 노드가 **같은 값**이고 쌍 검사 대상이다. `drop_limit_margin_m` 은 이 노드 전용이며 계약 이름이 아니다 — `ScanConfig` 에 없어 SetConfig 전파 대상이 아니므로, SetConfig 가 두 노드의 `drop_limit_m` 을 같은 값으로 덮어써도 여유는 남는다
  - **10 mm 의 근거** (2026-09-23 재결정): 간섭 거리 D = 그리퍼 밖 탐침 길이 **12 mm**(자로 실측)보다 2 mm 작다. 팁이 D 넘게 내려가면 그리퍼가 부재에 닿는다. 여유 5 mm 는 10 에서 1차 5 를 뺀 값이다. 옛 9 mm 와 그 근거 문구는 사실이 아니었다(ADR 0004 결정 2)
  - **남는 조건 둘 다 미측정**: 상한 `L2 + O2 < D`(O2 < 2 mm) · 하한 `5 + O1 < L2`(O1 < 5 mm, 넘으면 #53 재발). O 를 지배하는 것은 관성이 아니라 힘 제어이고(9/22 실기 1123: 정지 뒤 z 가 2.8 mm 내려감), 이 값은 힘 제어가 없는 **step 모드 기준**이다
  - 경계는 **초과**다(정확히 한계면 걸리지 않는다). `confirm_n` 으로 늦추지 않는다 — 시간으로 늦추면 하강 속도에 따라 실제 여유가 달라진다
- 조건은 연속 `confirm_n` 회 참일 때 확정한다. 같은 조건을 되풀이해 올리지 않는다(정지 요청도 한 번만)
- **기동 직후에는 최신성을 감시하지 않는다.** 한 번도 받은 적 없는 입력은 "끊긴 것"이 아니고, 기동 뒤 `startup_grace_s` 동안도 보지 않는다. 9/21 종단 실행에서 기동 직후 샘플이 508 ms 끊겼고 그때 robot_manager 는 '위치를 모르면 이동 중'이라 moving=true 여서, 뜨자마자 래치가 걸렸다(PR #99). **과대 외력 · 하강 제한은 유예하지 않는다**
- 최신성 조건이 WARN 인 이유: 서 있는데 소식이 없는 것은 정지를 요청할 일이 아니다. 움직이는 중이면 감시가 눈이 먼 것이므로 STOP 이다

**아직 감시하지 않는 것**(계약 · 아키텍처에는 있다)
- 웹 heartbeat(`/web/heartbeat`, 계약 2.1 의 구독자는 safety_monitor) — **미구현**. 만료 시 조치(`warn`/`stop`)가 계약 9장 TBD 라 붙이지 않았다(T33, #33)
- 작업영역 `OUT_OF_WORKSPACE(402)` — 미구현. phase 2 경로의 z 하한은 robot_manager `path_min_z_m` 이 본다

## 정지 요청 (계약 7.1 ③)
```
조건 확정 → /robot/stop 비동기 호출 → accepted (접수)
         → /robot/status 의 connected && !moving (완료 확인)
         → 제한 시간 초과면 UNCONFIRMED 로 올리고 느린 주기로 다시 요청
```
- **응답을 기다리지 않는다.** robot_manager 의 핸들러가 `move_stop` 을 동기로 부르므로, 기다리면 감시 노드까지 같이 멈춘다(계약 1장)
- **재시도는 느리게 한다.** 드라이버가 응답하지 않는 원인이 호출 과부하일 수 있다. 세게 두드리면 더 나빠진다
- `accepted` 는 접수일 뿐이다. `stop_confirmed` 가 완료다

## 래치
- STOP 조건이 확정되면 래치를 건다. **조건이 사라져도 자동으로 풀리지 않는다**(계약 3.7). `latched=true` 면 scan_manager 가 시작 · 재시작을 거절한다
- `/safety/reset` 으로만 푼다. **조건이 아직 참이면 `CONDITION_ACTIVE(406)` 로 거절한다.** 래치가 없어도 성공이다(멱등). 로봇을 움직이지 않는다
- 래치를 건 첫 원인을 `reason_code` · `motion_id` · `position` 에 유지한다(나중 조건이 덮어쓰지 않는다)

## 파라미터
값은 [`contact_scan_bringup/config/sim.yaml`](../contact_scan_bringup/config/sim.yaml) · [`real.yaml`](../contact_scan_bringup/config/real.yaml) 의 `safety_monitor:` 절에만 둔다. **코드에 기본값이 없다** — 빠지면 기동하지 않는다. 래치는 파라미터로 풀 수 없다.
★ = 계약 이름(SetConfig 가 실행 중에 바꾼다). `over_force_n` 은 contact_detector 와, `drop_limit_m` 은 robot_manager 와 **같은 값**이어야 한다(계약 7.2, `contact_scan_bringup/test/test_config.py` 가 검사).

| 이름 | sim | real | 성격 | 근거 · 실측 |
|---|---|---|---|---|
| ★ `over_force_n` | 30 N | 30 N | 출발값 · 팀 결정 유지 | BRD 4.5. 9/22 팀 결정 8(30 N 유지, ADR 0004) |
| ★ `drop_limit_m` | 5 mm | 5 mm | 출발값 | 기준 z = `OP_SLIDE` 첫 샘플의 z(계약 7.2) |
| `drop_limit_margin_m` | 5 mm | 5 mm | 팀 결정(계약 이름 아님) | 2차 한계 = `drop_limit_m` + 이 값 = **10 mm**. 간섭 거리 D 12 mm 아래(9/23 재결정, 계약 v0.1.21 결정 2, 아래 #53) |
| `confirm_n` | 1 | 1 | 팀 결정 | #53 대안 ③(2차 `confirm_n = 2`) 기각 → 1(아래) |
| `startup_grace_s` | 3.0 s | 3.0 s | 출발값 | 9/21 기동 직후 508 ms 공백(PR #99) |
| `sample_stale_ms` | 500 | **500** | **실측 조정**(real, 300 → 500) | 300 에서 goal 의 약 40 % 가 `SAMPLE_STALE` 로 정지(2026-09-22 실기 17:54, #130 기록). 기록된 공백 14 개 중 500 은 687 ms 하나만 걸린다. 계약 6.3 "한계보다 원인이 먼저"의 **예외**, #130 이 풀리면 300 으로 되돌린다(PR #168, 계약 v0.1.16) |
| `robot_status_timeout_ms` | 1000 | 500 | 출발값 | Virtual `/robot/status` 9.3~9.8 Hz(계약 6.3). 실기 주기는 미측정 |
| `stop_confirm_timeout_s` | 0.6 s | 0.6 s | 출발값 | robot_manager `moving_window_s` 0.3 + 상태 간격 약 0.13 + 왕복 ≈ 0.45 s. TR-08(T32) 미실시 |
| `stop_retry_period_s` | 2.0 s | 2.0 s | 출발값 | 드라이버 과부하를 피해 느리게(`api-check-log.md`) |
| `status_publish_period_s` · `check_period_s` | 1.0 s · 0.05 s | 같음 | 출발값 | — |

## 이슈 #53 (1차 · 2차 동시 래치) — 결정됨 (2026-09-22, 계약 v0.1.21 결정 2)
옛 규칙("값도 기준도 같게")에서는 `DROP_LIMIT` 이 날 때마다 2차 래치도 **같은 샘플에서** 걸렸다. 1차가 정상 동작해 SLIDE 를 실패로 끝냈을 뿐인데 래치가 남아 다음 작업 시작이 막혔다.

**결정**: 기준 z 는 1차와 같게 두고, **2차만 `drop_limit_margin_m` 만큼 뒤로** 둔다(1차 5 mm · 2차 **10 mm**. 2026-09-22 에는 9 mm 였고 9/23 에 간섭 거리 D = 12 mm 실측으로 재결정했다 — 위 파라미터 절).
- 대안 ③(2차 `confirm_n = 2`)은 **기각**했다. 시간으로 늦추는 것이라 하강 속도에 따라 실제 여유가 달라진다. `confirm_n` 은 1 로 둔다.
- 선행 조건이었던 **기준 z 통일(C-9)** 을 같이 했다. 순응을 켜면 z 가 약 0.7 mm 올라와 1차("실행 직전의 마지막 위치")와 2차("SLIDE 첫 샘플")가 어긋나 있었다.
- 고정해 둔 시험: `test_safety_core.py::test_issue_53_first_stage_window_is_free_of_the_second_latch` · `::test_issue_53_second_stage_still_latches_when_the_first_fails` · `::test_margin_survives_setconfig_overwriting_drop_limit`.

## 최신성 (`sample_stale_ms`) — 500 ms (2026-09-22, 결정 3)
real 을 300 → 500 으로 올렸다. 계약 6.3 의 "한계보다 원인이 먼저"라는 지침의 **예외**다.
- 300 에서는 정지 중 약 3 s 마다 반복되는 316~365 ms 공백에 전부 걸려 **goal 의 약 40 %가 `SAMPLE_STALE` 로 정지**했다(#130).
- 기록된 공백 14 개 중 500 에서 걸리는 것은 **687 ms 하나**뿐이다. **687 이 남으므로 500 도 완전하지 않다.**
- **700 으로 더 올리지 않는다** — 데이터가 더 쌓인 뒤 검토만 한다. #130 의 근본 원인이 풀리면 300 으로 되돌린다.

## 실행 · 테스트
2026-09-24 에 이 PC(Ubuntu 24.04 · Jazzy)에서 실제로 돌려 통과한 명령만 적는다.
```bash
cd ~/ws_cobot_pjt/ws_cobot1
python3 -m pytest src/safety_monitor/test/test_safety_core.py -q     # ROS 없이 돈다
sod && colcon build --packages-up-to safety_monitor && source install/setup.bash   # sod 먼저(bringup README)
colcon test --packages-select safety_monitor && colcon test-result --verbose   # 노드 시험 포함
```
노드 시험은 가짜 robot_manager(샘플 · 상태 발행 + `/robot/stop` 서버)를 띄워 executor 를 한 스텝씩 직접 돌린다. 로봇 · 드라이버는 필요 없다. 도메인은 `contact_scan_testing` 이 31~39 에서 빈 번호를 고른다(#126 — 격리 전에는 `colcon test` 가 실기 도메인에 가짜 메시지를 넣었다).
- 실기 전용(마지막 확인 2026-09-23, #179 실기 종단): bringup `source:=robot_force` 로 함께 뜬다. 시연 중 `SAMPLE_STALE` 로 멈췄을 때의 대응은 [daily 20260923 §7](../../../docs/test-reports/daily/20260923.md)

## 알려진 문제 (2026-09-24 열린 이슈 · PR)
| 번호 | 내용 |
|---|---|
| #130 | `/robot/sample` 약 3 s 주기 316~365 ms 공백(원인 미확인). 500 ms 예외의 이유이고, 687 ms 공백은 500 에서도 정지한다 |
| #53 | 1차 · 2차 하강 제한 동시 래치. 팀 결정은 PR #161 에 있고 머지 전 |
| #120 | 감시자가 죽어도 아무도 모른다. scan_manager 쪽은 `/safety/status` 가 끊기면 START 를 거절하도록 고쳤다(PR #136). 웹 표시는 남았다 |
| #33 | T33 확장(데이터 최신성은 됨, heartbeat 미구현) |
| PR #161 | 재시작 정책 · 이중 하강 제한 · 안전복귀 — 43 파일, 실기 미검증, 머지 전 |
