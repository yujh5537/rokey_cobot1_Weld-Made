# safety_monitor

소프트웨어 이상 감시 → **웹을 거치지 않는** 정지 요청. 소유: 현지 (T18, T33). 계약: `docs/contracts/ros-interfaces.md` 2.1 · 3.7 · 4.4 · 7.1 ③ · 7.2.

| 파일 | 역할 |
|---|---|
| `safety_monitor/safety_core.py` | 감시 조건 · 정지 요청 상태 · 래치. **rclpy 를 import 하지 않는다** |
| `safety_monitor/safety_monitor.py` | 노드. 구독 · `/robot/stop` 비동기 호출 · `/safety/status` 발행 · `/safety/reset` |

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
- **한계는 1차보다 여유만큼 뒤다** (v0.1.19 결정 2, #53): 2차 = `drop_limit_m + drop_limit_margin_m`. real · sim 모두 1차 5 mm · 2차 9 mm.
  - 1차 = 정상 동작의 제한(넘으면 그 SLIDE 를 실패로 끝낸다). 2차 = 1차가 막지 못했을 때의 최후 방어선(정지 + 래치)
  - `drop_limit_m` 자체는 두 노드가 **같은 값**이고 쌍 검사 대상이다. `drop_limit_margin_m` 은 이 노드 전용이며 계약 이름이 아니다 — `ScanConfig` 에 없어 SetConfig 전파 대상이 아니므로, SetConfig 가 두 노드의 `drop_limit_m` 을 같은 값으로 덮어써도 여유는 남는다
  - **9 mm 의 근거**: 탐침 길이를 손으로 재어 정한 간섭 없는 안전 거리(상한)다. 여유 4 mm 는 9 에서 1차 5 를 뺀 값이다. 하한 — 1차 정지의 하강 오버슈트가 여유를 넘으면 1차가 정상 정지할 때마다 2차가 래치된다 — 은 실기 미확인이다
  - 경계는 **초과**다(정확히 한계면 걸리지 않는다). `confirm_n` 으로 늦추지 않는다 — 시간으로 늦추면 하강 속도에 따라 실제 여유가 달라진다
- 조건은 연속 `confirm_n` 회 참일 때 확정한다. 같은 조건을 되풀이해 올리지 않는다(정지 요청도 한 번만)
- **기동 직후에는 최신성을 감시하지 않는다.** 한 번도 받은 적 없는 입력은 "끊긴 것"이 아니다. 그러지 않으면 뜨자마자 래치가 걸린다
- 최신성 조건이 WARN 인 이유: 서 있는데 소식이 없는 것은 정지를 요청할 일이 아니다. 움직이는 중이면 감시가 눈이 먼 것이므로 STOP 이다

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
값은 `contact_scan_bringup/config/*.yaml` 에만 둔다. 코드에 기본값이 없어서 값이 빠지면 기동하지 않는다.

`over_force_n` · `drop_limit_m` (계약 이름. SetConfig 가 실행 중에 바꾼다) · `drop_limit_margin_m` (계약 이름 아님) · `confirm_n` · `sample_stale_ms` · `robot_status_timeout_ms` ·
`stop_confirm_timeout_s` · `stop_retry_period_s` · `status_publish_period_s` · `check_period_s`

- `over_force_n` 은 contact_detector 와, `drop_limit_m` 은 robot_manager 와 **같은 값**이어야 한다(계약 7.2). `contact_scan_bringup/test/test_config.py` 가 CI 에서 검사한다
- 래치는 파라미터로 풀 수 없다

## 이슈 #53 (1차 · 2차 동시 래치) — 결정됨 (2026-09-22, 계약 v0.1.19 결정 2)
옛 규칙("값도 기준도 같게")에서는 `DROP_LIMIT` 이 날 때마다 2차 래치도 **같은 샘플에서** 걸렸다. 1차가 정상 동작해 SLIDE 를 실패로 끝냈을 뿐인데 래치가 남아 다음 작업 시작이 막혔다.

**결정**: 기준 z 는 1차와 같게 두고, **2차만 `drop_limit_margin_m` 만큼 뒤로** 둔다(1차 5 mm · 2차 9 mm).
- 대안 ③(2차 `confirm_n = 2`)은 **기각**했다. 시간으로 늦추는 것이라 하강 속도에 따라 실제 여유가 달라진다. `confirm_n` 은 1 로 둔다.
- 선행 조건이었던 **기준 z 통일(C-9)** 을 같이 했다. 순응을 켜면 z 가 약 0.7 mm 올라와 1차("실행 직전의 마지막 위치")와 2차("SLIDE 첫 샘플")가 어긋나 있었다.
- 고정해 둔 시험: `test_safety_core.py::test_issue_53_first_stage_window_is_free_of_the_second_latch` · `::test_issue_53_second_stage_still_latches_when_the_first_fails` · `::test_margin_survives_setconfig_overwriting_drop_limit`.

## 최신성 (`sample_stale_ms`) — 500 ms (2026-09-22, 결정 3)
real 을 300 → 500 으로 올렸다. 계약 6.3 의 "한계보다 원인이 먼저"라는 지침의 **예외**다.
- 300 에서는 정지 중 약 3 s 마다 반복되는 316~365 ms 공백에 전부 걸려 **goal 의 약 40 %가 `SAMPLE_STALE` 로 정지**했다(#130).
- 기록된 공백 14 개 중 500 에서 걸리는 것은 **687 ms 하나**뿐이다. **687 이 남으므로 500 도 완전하지 않다.**
- **700 으로 더 올리지 않는다** — 데이터가 더 쌓인 뒤 검토만 한다. #130 의 근본 원인이 풀리면 300 으로 되돌린다.

## 테스트
```bash
cd ~/ws_cobot_pjt/ws_cobot1
python3 -m pytest src/safety_monitor/test/test_safety_core.py -q   # ROS 없이 돈다
source install/setup.bash && python3 -m pytest src/safety_monitor/test -q
```
노드 테스트는 가짜 robot_manager(샘플 · 상태 발행 + `/robot/stop` 서버)를 띄워 executor 를 한 스텝씩 직접 돌린다. 로봇 · 드라이버는 필요 없다.
