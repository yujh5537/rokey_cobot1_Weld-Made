# 가상 용접 시연(`weld_preview.py`)의 실기 적용 가능성 — 코드 기준 감사

**작성 2026-09-29. 대상 독자: 이 레포에서 작업하는 다른 LLM/에이전트.**

이 문서는 `scripts/sim/weld_preview.py`(가상 윗면 4변 용접 시연)를 실기 M0609에
적용할 수 있는지 **코드를 직접 읽어 확인한 결과**다. 추측과 확인을 구분해 적었다.

## 2026-09-29 P1/P2 통합 검증 추가

아래의 “미구현” 판정은 이 문서를 작성한 checkout 기준이다. 이후 원격
`p2-robot-execute-path`와 `p2-weld-manager`에서 구현을 확인했고, 로컬
`p2-virtual-integration` 브랜치에 최신 main과 함께 통합했다.
별도 worktree와 domain 36에서 표준 fixture로 Virtual 8선 및 홈 복귀를 완료했다.
코드·재실행 절차·결과는 [P1/P2 실행 기록](p1-p2-run.md)을 따른다.
기존 `weld_preview.py`의 sim 전용 차단과 실기 적용 제한은 그대로 유효하다.
P4와 기존 웹 연결은 이번 통합 검증에 포함하지 않았다.

## 2026-09-29 P4 연결 추가

P4 브리지를 로컬 `p2-virtual-integration` 브랜치(`b4e780c`)에 구현했다.
Virtual에서 FastAPI REST → MQTT → `/weld/run` → `weld/result`·`weld/command_result`
L0 완료를 확인했다. 기존 웹의 **용접 시작** 버튼은 `/sim-weld` 시연 경로라
P4 실기 명령은 [실기 용접 모션 Runbook](../../docs/runbooks/real-weld-motion.md)의
REST API를 사용한다. 아래 P4 “미구현” 표는 최초 작성 시점의 checkout 상태다.
실기 명령은 실행하지 않았다.

## 0. 30초 요약

| 질문 | 답 |
|---|---|
| 이 스크립트를 실기에 쓸 수 있나? | **아니다.** 코드에 하드 차단이 있고, 풀어도 안전장치 8개가 없다 |
| 왜 하드 차단이 있나? | 설계 의도가 sim 전용이다. 우회하지 마라 |
| 실기로 가는 정식 경로는? | `P1 ExecutePath` → `P2 weld_manager` → `P4 브리지`. **셋 다 미구현** |
| 버릴 코드인가? | 아니다. `plan()`의 윗면 4선 기하는 P2로 이식 가능하다(테스트로 검산됨) |
| 내가 실기 명령을 실행해도 되나? | **안 된다.** `CLAUDE.md` 규칙 1 — 실기 명령은 사람이 직접 한다 |

## 1. 용어 — "실기 용접"이 무슨 뜻인가

phase 2에서 용접은 **용접하듯 움직이는 모션**이다. 아크를 켜는 실제 용접 출력은
범위 밖이다. 이 전제를 놓치면 이후 판단이 전부 틀어진다.

- 툴은 RG2 그리퍼 + 인공눈물 탐침이다. 용접 토치가 아니다.
- `docs/phase2/README.md` D2: "**띄운다.** 스탠드오프 수 mm, 힘·순응 제어 없음."
- 즉 부재에 닿지 않고 이음선 위를 수 mm 띄워 지나간다. 접촉 판정도 없다.

## 2. 하드 차단 — 실기에서는 기동조차 안 된다

`scripts/sim/apply_virtual_tcp.py:33-48` 의 `require_virtual_driver()` 가 세 가지를
검사하고, 하나라도 어긋나면 `RuntimeError` 를 던진다.

| 검사 | 실패 시 메시지 |
|---|---|
| `dsr01_emulator` 컨테이너가 실행 중인가 | `dsr01_emulator 컨테이너가 실행 중이지 않습니다` |
| `mode:=virtual host:=127.0.0.1` launch 가 보이는가 | `localhost mode:=virtual M0609 드라이버를 확인할 수 없습니다` |
| `mode:=real` launch 가 함께 있는가 | `실기 드라이버가 함께 실행 중이므로 TCP를 변경하지 않습니다` |

호출 지점 2곳 — 둘 다 통과해야 한다.

- `scripts/sim/weld_preview.py:237` — 서버 기동 시 (`main()`)
- `scripts/sim/weld_preview.py:126` — 용접 시작 시 (`start()`)

**이 차단을 제거하거나 우회하는 변경을 하지 마라.** 이슈에 명시되지 않은 한
안전 장치를 푸는 것은 `CLAUDE.md` 규칙 1·6 위반이다.

## 3. 차단을 풀어도 실기에 쓸 수 없는 이유 8개

전부 코드/문서에서 확인했다. "확인" = 파일을 읽어 검증, "문서" = 계약 문서의 결정.

| # | 빠진 것 | 근거 | 실기에서 무슨 일이 나는가 | 상태 |
|---|---|---|---|---|
| 1 | **45° 툴 자세** | `scripts/sim/weld_preview.yaml` `tilt_deg: 0.0` | 기본값이 수직이다. 시나리오는 45°(D1·D3). 게다가 M1(#186)에서 **L1·L5 는 45° 로 도달 불가**(플랜지 한계 689~761 mm, 기울기·롤·재배치로 해결 안 됨) — D27 | 확인 + 문서 |
| 2 | **툴 외형 간섭 검사** | `docs/phase2/measurements-20260923.md` M2 | M2 는 2026-09-26 에 정정되어 45° 여유가 "약 49 mm" 가 아니라 **약 17 mm** 다. 탐침 자루·RG2 손가락이 큐브·작업대에 닿는지 보는 검사(D23 `tool_profile_u_m`·`tool_profile_r_m`)가 없다 | 문서 |
| 3 | **도달성·작업영역 사전 검사** | `weld_preview.py:23-58` (`plan()`) | `plan()` 은 기하만 계산한다. 관절 한계·특이점은 이동이 실패한 뒤에야 드러난다 | 확인 |
| 4 | **좌표 출처가 sim 프로필** | `weld_preview.py` `--config` 기본값 `/tmp/weld-made-db-sim/sim.yaml` | 실기는 `real.yaml` 의 `base_to_fixture` 와 **그 순간의 실제 큐브 위치**를 써야 한다. sim.yaml 은 DB 스캔 값으로 덮어쓴 파일이다 | 확인 |
| 5 | **ROS 파라미터가 아니다** | `contact_scan_bringup/config/real.yaml` 에 `weld_manager:` 절 없음 (scan_manager 의 `weld_state_timeout_s` 만 있다) | 수치가 별도 YAML 에 있어 bringup 파라미터 체계 밖이다 — `CLAUDE.md` 규칙 7 | 확인 |
| 6 | **결과 기록** | `weld_preview.py` 에 `/weld/result`·`/weld/log` 발행 없음 | `weld/<weld_id>.json` 도 없다. 실기 실행을 사후 추적할 수 없다 | 확인 |
| 7 | **D25 (미요청 정지 = ERROR)** | `weld_preview.py:185-221` (`run()`) | `InterruptedError` → `STOPPED`, 그 밖 → `ERROR` 로만 나눈다. weld_manager 가 요청하지 않은 정지를 구분하지 않는다 | 확인 + 문서 |
| 8 | **MQTT 계약 우회** | `weld_preview.py:267` `ThreadingHTTPServer(('127.0.0.1', 8766), …)` | 웹 → 로컬 HTTP 직결이라 `cmd/weld/*` 계약(`docs/phase2/weld-mqtt-schema.md`)을 타지 않는다. 배포·감사 대상 경로가 아니다 | 확인 |

### 3.1 오해하기 쉬운 지점 — 스탠드오프는 윗면에서 문제없다

D22 는 `standoff_m` 을 "팁 구 표면 ↔ 이음선 최단거리"로 정의하고, 축 방향 물러남을
`s′ = (standoff_m + r)/k − r`, `k = sqrt(1 − (d·t̂)²)` 로 준다.

**윗면 변(L0~L3)은 `d·t̂ = 0` 이라 `k = 1` 이고 `s′ = standoff_m` 이다.**
tilt 0° 든 45° 든 마찬가지다(`weld-motion.md` 3절 검산: "윗면선은 k = 1 이라 예전
정의와 같은 값(3 mm)이다").

즉 **현재 구현(축 방향 `standoff_m` 그대로)은 윗면 4선에서 D22 와 정확히 일치한다.**
D22 가 문제되는 건 세로선(45° 에서 축 방향 ≈ 5.07 mm)뿐이고, 세로선은 애초에
구현 대상이 아니다(§4). 이걸 "버그"로 보고 고치려 들지 마라.

## 4. 현재 구현 범위 — 8선 중 윗면 4선만

`weld_preview.py:34` 가 `shape['edges'][:4]` 로 자른다. `weld-motion.md` 1절의 8선 표에서:

| 선 | `edges[]` | 구현 |
|---|---|---|
| L0~L3 (윗면 루프) | 0~3 | **있음** |
| L4~L7 (세로 모서리) | 8~11 | **없음** |

세로선을 넣으려면 §3.1 의 D22 스탠드오프와 D4 `bottom_margin_m`(받침대 위에서 끝냄),
D23 툴 외형 검사가 함께 필요하다.

## 5. 미구현 상태 — 정식 경로의 세 조각

`docs/phase2/tasks/` 가 정한 담당별 task 중 용접 본체는 셋 다 아직 없다.

| task | 산출물 | 확인 결과 |
|---|---|---|
| **P1** | `robot_manager` 의 `ExecutePath` (D31 line 모드, `path_point_dwell_s`) | `ws_cobot1/src/robot_manager/` 전체에 `ExecutePath` 참조 **0건** |
| **P2** | `weld_manager` 패키지 (`RunWeld`·`StopWeld`·`/weld/state`·`/weld/result`) | `ws_cobot1/src/weld_manager` **디렉터리 자체가 없음** |
| **P4** | `mqtt_bridge` 의 `cmd/weld/*`·`weld/*` | 이름표만 있다 — `mqtt_bridge/encoders.py:18` `5: "WELD_PATH"`, `:36` `601: "WELD_ACTIVE"` 등 |

`contact_scan_bringup/launch/bringup.launch.py:26-32` 의 `NODES` 는 5개
(`robot_manager`·`contact_detector`·`safety_monitor`·`scan_manager`·`mqtt_bridge`)로
`weld_manager` 가 없다.

반면 **인터페이스 계약은 이미 완비**돼 있다(PR #184, v0.2.0). `contact_scan_interfaces` 에
`WeldState`·`WeldLine`·`WeldConfig`·`WeldResult` msg, `RunWeld`·`ExecutePath` action,
`StopWeld` srv 가 모두 있다. 즉 **타입을 새로 만들 필요는 없고, 노드만 없다.**

## 6. 그대로 재사용할 수 있는 것

실기 작업을 시작할 때 이것들은 다시 만들지 마라.

| 자산 | 위치 | 왜 믿을 수 있나 |
|---|---|---|
| `robot_manager` 의 `ExecuteMotion` 계층 | `ws_cobot1/src/robot_manager/` | 스캔 실기 종단 3회 연속 성공(PR #179). 실기에서 검증된 코드다 |
| `plan()` 의 윗면 4선 기하 | `weld_preview.py:23-58` | 자세·스탠드오프·위빙 경유점. `test_weld_preview.py` 4개 테스트 통과. §3.1 대로 D22 와 일치 |
| 안전 신선도 확인 + goal 취소 구조 | `weld_preview.py:116-124` (`ready()`), `:141-157` (`wait()`) | 20 ms 마다 `/robot/sample`·`/safety/status`·`/scan/state` 나이를 보고 취소한다 |
| 스캔·용접 배타 (601) | `scan_manager` (PR #204, main 에 있음) | `weld_preview` 가 `/weld/state` 를 발행하면 scan_manager 가 START·RESUME 을 `WELD_ACTIVE(601)` 로 거절한다 |

## 7. 실기로 가는 순서

1. **P1 `ExecutePath`** — 경유점 전체를 goal 하나로. 지금은 점마다 `ExecuteMotion` 을
   보내 **점당 약 0.48 s 오버헤드**가 붙는다(실측, `README.md` "위빙 밀도와 실행 시간").
   D31 은 spline 사용 불가(응답 지연으로 SAMPLE_STALE), `line` 모드만이다.
2. **P2 `weld_manager`** — `docs/phase2/tasks/P2-weld-manager.md` 의 초기 설계를 따른다.
   `weld_path.py` 의 출발점으로 `plan()` 을 이식하고, 세로선 4개·D22·D23·`start_line`/
   `end_line`·`continue_on_line_failure`(D33)를 추가한다.
3. **P4 브리지** — `cmd/weld/*`·`weld/*`. 웹을 로컬 HTTP 에서 MQTT 로 되돌린다.

D27 이 정한 9/29 기대치: **윗면 3선(L0·L2·L3) + 세로 3선(L4·L6·L7)**, **L1·L5 는
FAILED 로 기록**(45° 도달 불가).

## 8. 절대 하지 말 것

1. **실기 명령을 실행하지 않는다.** `sodreal`, `mode:=real`, 실기에 연결된 상태의
   `ros2 service call`/`ros2 action send_goal` 은 사람이 직접 한다(`CLAUDE.md` 규칙 1).
   LLM 은 Virtual(`sodvir`)과 sim 입력원만 실행한다.
2. `require_virtual_driver()` 를 제거·우회·조건 완화하지 않는다(§2).
3. Virtual TCP `246.98 mm` 를 실기 TCP 로 쓰지 않는다. 이 값은 **웹 화면 정렬용**이고,
   실기 등록값은 `rg2_probe_tip` = `[0, 0, 252.12]` 다(`real.yaml:148`,
   `docs/env/tool-tcp-register.md`).
4. `docs/contracts/`·`docs/phase2/`·`contact_scan_interfaces/` 는 이슈에 명시된 경우에만
   고친다(`CLAUDE.md` 규칙 5).

## 9. 이 문서에서 확인하지 못한 것

정직하게 남겨둔다. 추측으로 메우지 마라.

- **에뮬레이터 적체 원인 미확인.** 2026-09-28 에 `dsr01_emulator` 의 DRCF TCP 소켓
  송신 큐가 2.46 MB 까지 적체되어 `/robot/sample` 이 끊기고 `SAMPLE_STALE(403)` 래치가
  걸렸다. 드라이버 재기동으로 해소했다. "점별 `ExecuteMotion` 과다 호출이 원인"이라는
  가설은 이후 2.6배 촘촘한 설정(경유점 220개)으로 정상 완주해 **근거가 약해졌다.**
  원인은 여전히 미확인이다. 재현되면 `ss` 큐와 `docker logs dsr01_emulator` 를
  시점별로 대조할 것.
  - 참고: 에뮬레이터의 **400 % CPU 는 정상**이다. 새로 띄운 직후 유휴 상태에서도
    400 % 다. 이상 징후로 오판하지 마라.
- **45° 자세의 Virtual 동작 여부.** DB 배치에서 45° 로 L0 는 성공했으나 L1 접근이
  `ROBOT_ERROR(204)` 로 실패했다(기존 M1 기록과 같은 문제). 다른 배치에서 어떤지는
  확인하지 않았다.
- **실기에서의 위빙 실행 시간.** 실측은 Virtual 값(기본 설정 199 s)뿐이다.

## 10. 관련 문서

| 문서 | 내용 |
|---|---|
| `scripts/sim/README.md` | 이 시연의 실행 절차, 위빙 밀도와 실행 시간 표 |
| `docs/phase2/README.md` | 결정 D1~D35. 특히 D2(띄운다) · D22 · D27 · D31 · D33 |
| `docs/phase2/weld-motion.md` | 8선 표 · 자세 식 · 스탠드오프 · 위빙 · 파라미터 표 |
| `docs/phase2/weld-ros-interfaces.md` | 토픽·서비스·액션 타입, 시작 거절 사유, 배타 규칙 |
| `docs/phase2/tasks/P2-weld-manager.md` | `weld_manager` 초기 설계와 테스트 요구 |
| `docs/phase2/measurements-20260923.md` | M1 도달성 · M2 툴 치수(2026-09-26 정정) |
| `CLAUDE.md` | 절대 규칙 7개. 특히 규칙 1(실기) · 5(계약) · 6(범위) · 7(파라미터) |
