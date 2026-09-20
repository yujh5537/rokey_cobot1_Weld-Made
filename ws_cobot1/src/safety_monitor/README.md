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
| 하강 제한 | SLIDE 중 z 가 기준보다 `drop_limit_m` 넘게 내려감 | `DROP_LIMIT(205)` | 항상 STOP |
| 샘플 최신성 | `/robot/sample` 이 `sample_stale_ms` 넘게 없음 | `SAMPLE_STALE(403)` | 움직이는 중이면 STOP, 서 있으면 WARN |
| 상태 최신성 | `/robot/status` 가 `robot_status_timeout_ms` 넘게 없음 | `ROBOT_STATUS_LOST(404)` | 〃 |

- **하강 제한의 기준 z = `operation` 이 `OP_SLIDE` 로 바뀐 첫 샘플의 z**(계약 7.2). 1차(robot_manager)와 **값도 기준도 같다.** 방향이 바뀌어 SLIDE 를 다시 시작하면 기준도 다시 잡는다
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

`over_force_n` · `drop_limit_m` (계약 이름. SetConfig 가 실행 중에 바꾼다) · `confirm_n` · `sample_stale_ms` · `robot_status_timeout_ms` ·
`stop_confirm_timeout_s` · `stop_retry_period_s` · `status_publish_period_s` · `check_period_s`

- `over_force_n` 은 contact_detector 와, `drop_limit_m` 은 robot_manager 와 **같은 값**이어야 한다(계약 7.2). `contact_scan_bringup/test/test_config.py` 가 CI 에서 검사한다
- 래치는 파라미터로 풀 수 없다

## 이슈 #53 (1차 · 2차 동시 래치)
계약 7.2 대로 값과 기준 z 를 1차와 같게 두면, `DROP_LIMIT` 이 날 때마다 2차 래치도 **같은 샘플에서** 걸린다. 그러면 관제자가 매번 안전 해제를 눌러야 한다.
`confirm_n` 을 2 이상으로 올리면 값과 기준 z 는 그대로 두면서 2차만 늦출 수 있고, 1차가 제때 멈춰 하강이 멎으면 2차는 걸리지 않는다. `test_safety_core.py::test_issue_53_second_watch_fires_on_the_same_sample_as_the_first` 가 세 경우를 고정해 두었다. **결정 전까지 `confirm_n = 1`**(안전 쪽)이다.

## 테스트
```bash
cd ~/ws_cobot_pjt/ws_cobot1
python3 -m pytest src/safety_monitor/test/test_safety_core.py -q   # ROS 없이 돈다
source install/setup.bash && python3 -m pytest src/safety_monitor/test -q
```
노드 테스트는 가짜 robot_manager(샘플 · 상태 발행 + `/robot/stop` 서버)를 띄워 executor 를 한 스텝씩 직접 돌린다. 로봇 · 드라이버는 필요 없다.
