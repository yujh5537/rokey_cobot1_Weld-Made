# contact_detector

접촉(CONTACT) · 접촉 소실(EDGE) · 과대 외력(OVER_FORCE) 판정 노드. 담당: 현지 (T07, T16). 계약: [`ros-interfaces.md`](../../../docs/contracts/ros-interfaces.md) 3.1 · 3.3 · 4.2 · 6.3 · 7.2.
로봇을 움직이지 않는다. 판정만 해서 `/contact/event` 로 알리고, 정지는 robot_manager 가 한다(계약 7.1 경로 ②).

| 파일 | 역할 | rclpy |
|---|---|---|
| `contact_detector/detector_core.py` | 판정 로직: tare(기준값 F0), 하강 이동 기준, 임계 · 디바운스, EDGE(z 추세선 · 힘 꺾임), 과대 외력 | 안 씀 |
| `contact_detector/sim_source.py` | sim 입력원. 가상 직육면체와 TCP 위치로 외력 · z 를 만든다 | 안 씀 |
| `contact_detector/offline.py` | 기록 CSV 를 같은 판정 로직에 통과시키는 분석기 `analyze_samples`(실측 주기 · 무접촉 잡음 · 임계 × 디바운스 비교표) | 안 씀 |
| `contact_detector/contact_detector.py` | 노드. 구독 → 판정 → 발행, `/contact/tare` 서비스, 파라미터 콜백(SetConfig P02) | 씀 |

| 방향 | 이름 | 타입 · QoS | 계약 |
|---|---|---|---|
| 구독 | `/robot/sample` | `RobotSample` · SENSOR | 3.1 (판정 모드는 샘플의 `operation`) |
| 구독 | `/scan/state` | `ScanState` · STATE | 3.4 (`scan_id` 태깅에만 쓴다) |
| 발행 | `/contact/event` | `ContactEvent` · EVENT | 3.3 |
| 서비스 | `/contact/tare` | `TareForce` | 4.2 |
| 파라미터 | `contact_threshold_n` · `edge_drop_m` · `debounce_n` · `over_force_n` | SetConfig 전파 P02 | 2.4 · 6.4 |

외력 감소(보조 신호)는 기본으로 쓰지 않는다(이슈 #16 코멘트). 켜는 스위치는 `edge_force_drop_n`(#128, 기본 0 = 끔).

## 실기 구성에서 맡는 것 (2026-09-23 기준)
- **CONTACT(하강)**: 이 노드가 확정한다. 실기 · sim 모두
- **EDGE(밀기)**: 실기 `real.yaml` 은 robot_manager `slide_mode: step` 이다. 이때 EDGE 는 **robot_manager 가 멈춰서 힘을 읽고 확정**해 `/contact/event`(`source = "robot_step"`)로 내고, 이 노드의 EDGE 는 정지에 쓰이지 않는다(계약 v0.1.15 · 7.2). 이 노드의 EDGE 판정은 `slide_mode: force` 와 sim 에서 쓰인다
- **OVER_FORCE**: 모든 동작에서 이 노드가 1차로 판정하고 robot_manager 가 대조 없이 즉시 정지한다. 2차는 safety_monitor 다(계약 7.2)
- 실기 외력 값은 샘플 주기(약 43 Hz)와 달리 **약 94 ms(10 Hz)마다만 바뀐다**(9/20 `idle_30s.csv` · `descend_01.csv` 분석, 두산 `OnMonitoringDataCB` 100 ms 캐시). `debounce_n: 3` 은 사실상 힘 측정 1 회이고, 판정이 최대 약 120 ms 늦어질 수 있다(3 mm/s 면 0.3 mm. 계산값). robot_manager 50 Hz 경로에서 같은지는 **미확인**

## sim 입력원 (`source: sim`)
Virtual Mode 에서는 힘 제어가 동작하지 않고 외력도 0 근처라(BRD 위험 2, `api-check-log.md`), 실제 샘플만으로는
접촉도 소실도 일어나지 않는다. 그래서 **샘플의 외력과 z 를 가상 모델의 값으로 바꿔서** 판정기에 넣는다.
**x · y 는 실제 로봇 값을 그대로 쓴다** — 치수는 Virtual 로봇이 실제로 이동한 거리에서 나온다. 이벤트에도 바꾼 값을 싣는다.

| 팁이 박스 경계를 지난 거리 d | 팁이 닿을 수 있는 높이 |
|---|---|
| d ≤ 0 (윗면 위) | `z_top` |
| 0 < d < r (모서리에 얹힘) | `z_top − (r − √(r² − d²))` — geometry_estimator 보정식의 **정방향** |
| d ≥ r (완전히 벗어남) | 박스 밑면(지지면). 팁이 옆면을 따라 내려간다 |

- `OP_SLIDE` 중에는 순응 제어가 팁을 표면에 붙여 둔다고 본다. 목표 침투(`sim_slide_press_n` / 강성)를 유지하되
  **내려가는 속도를 `sim_fall_speed_mps` 로 제한한다.** 그 밖에서는 팁이 로봇이 지시한 z 에 그대로 있다
- 외력 = 침투 깊이 × `sim_stiffness_n_per_m`, Base 기준 +z
- 샘플의 `frame_id` 가 `sim_box_frame_id` 와 다르면 판정하지 않고 경고한다
- **`sim_tip_radius_m` 은 scan_manager 의 `tip_radius_m` 과 같아야 치수가 복원된다**
- 합격 기준: `test_sim_source.py::test_full_scan_recovers_the_virtual_box` 가 sim → 판정 → 편향 보정이
  가상 박스 치수(100 × 60 × 40 mm)를 0.4 mm 안에서 복원하는지 본다

## 판정 규칙
- **하강 기준과 밀기 기준을 나눈다 (#109).** 외력 추정값은 마지막 이동 방향 · 자세에 따라 2~3 N 치우친다(2026-09-21 실기 1-1 · 5-2 · 5-11). 정지 F0 로 하강하면 허공에서 거짓 CONTACT 가 나고, 하강용 F0 를 밀기에 쓰면 옆 이동 이력(허공에서도 Fx −5 N) 때문에 닿기 전에도 `|F − F0|` 가 수 N 이다
- **CONTACT**: `operation == OP_DESCEND` 이고 기준값이 있는 상태에서 `|F − F0| > contact_threshold_n` 인 샘플이 연속 `debounce_n` 회. `motion_id` 마다 1 회
  - `descend_ref_window_s > 0` 이면 **DESCEND 의 F0 는 최근 구간 `[t − descend_ref_window_s, t − descend_ref_lag_s]` 의 외력 평균(이동 기준)** 이다. 조건이 성립한 샘플은 구간에 넣지 않는다(닿는 힘이 기준을 끌어올리지 않게). 추정값은 움직이기 시작하면 계단식으로 바뀌고 자세에 따라 계속 흐르지만(초당 약 0.2 N) 접촉은 0.1 s 안에 수 N 오르는 급변이다
    - 9/21 실기 하강 23 회 재생: 한 번 잡은 F0(홈 정지 · 하강 중 1회)는 1~2 회 공중 거짓 CONTACT(윗면 38 · 44 · 78 mm 위), 이동 기준은 0 회이고 윗면 z 는 같다. 공중 최대 `|F − F0|` 2.92 N(도중에 멈춘 하강), 홈 출발 정상 하강 2.26 N
    - 샘플 공백으로 구간을 비우지 않는다. 시간 창이라 오래된 샘플은 저절로 빠진다
  - **이동 기준이 없는 동안**(출발 뒤 `descend_ref_settle_s`(5.5 s. 출발 약 4 s 뒤 계단식 치우침이 구간을 지나갈 때까지), 구간 안 샘플이 `descend_ref_min_samples` 보다 적을 때) **CONTACT 를 끄지 않고 둔하게 본다**: `/contact/tare` 의 F0(없으면 이번 DESCEND 첫 샘플의 F)와 `descend_hold_threshold_n`(6 N). 끄면 그 사이에 닿았을 때 과대 외력(30 N)까지 막을 것이 없다(현지 리뷰, PR #127). 이렇게 확정한 CONTACT 는 로그에 경고로 남는다(더 눌린 좌표)
  - 한계: 느리게 오르는 접촉(부드러운 부재)은 흐름으로 흡수될 수 있다. 직선으로 오르는 힘이면 |F − F0| 가 기울기 × (window_s + lag_s)/2 = 0.65 s 에서 멈추므로, **약 4.6 N/s(= 3.0 / 0.65)보다 느리면 CONTACT 가 나지 않는다**(settle 안은 F0 고정이라 6 N 에서 잡힌다). 기울기 = 접촉 강성 × 하강 속도. 9/21 실기 CONTACT 20 회: 이론 43 N/mm × 3 mm/s ≈ 130 N/s, 3 N 을 넘은 힘 갱신 구간 중앙값 105 N/s, 보수적 평균(0.5 → 3 N) 최소 15 N/s. 창 · 임계 · 하강 속도를 바꾸면 다시 본다(#139, `test_slow_contact_boundary`)
  - `/contact/tare`(정지)는 툴 등록 점검(`TOOL_REG_SUSPECT`)과 둔한 판정의 기준으로 남는다. DESCEND 가 아닐 때(밀기의 보고값 `|F − F0|`)는 마지막 CONTACT 의 이동 기준과 `/contact/tare` 중 **나중 것**을 쓴다
  - 하강 중에 파라미터를 바꾸면 detector 를 새로 만들어 구간을 다시 쌓는다(그동안 둔한 판정). 이미 닿아 있을 때는 바꾸지 않는다
- **EDGE**: `operation == OP_SLIDE` 이고 기준값이 있는 상태에서(판정을 켜는 조건은 F0 를 쓰지 않지만, F0 가 하나도 없으면 EDGE 를 판정하지 않는다. 보고값 `force_delta_n` 때문)
  1. "누르고 있다" 확인. 그 뒤부터 판정한다
     - `edge_arm_still_window_s > 0`(실기 · sim 기본): 최근 그 구간 동안 **z 가 `edge_arm_still_m` 안에 머물고 x · y 가 `edge_arm_travel_m` 넘게 움직였으면** 켠다. F0 를 쓰지 않는다. 틈을 다 메우면 z 가 멈추기 때문이다. x · y 조건이 없으면 힘 제어를 켜는 동안(팁이 떠 있는데 z 도 멈춰 있다) 너무 일찍 켜진다
     - `edge_arm_still_window_s <= 0`: 이전 방식 `|F − F0| > edge_arm_force_n` 이 연속 `debounce_n` 회
  2. TCP z 가 **최근 `edge_trend_window_s` 구간의 추세선**(직선 맞춤)보다 `edge_drop_m` 넘게 내려간 샘플이 연속 `debounce_n` 회 → 확정. `motion_id` 마다 1 회
  - 밀기 시작 z 대비 누적 하강량으로 재지 않는다. 모서리가 아닌데 z 가 내려가는 경우가 셋 있다: SLIDE 시작 때 틈(`recontact_margin_m`)을 메우는 하강(계약 7.3), 기울어진 윗면(0.87° 면 80 mm 에 1.2 mm), 탐침이 홀더 안으로 서서히 밀리는 것(PR #80). 앞의 것은 1 이, 뒤의 둘은 2 가 거른다
  - **가를 수 없는 것**: 탐침이 한 번에 툭 미끄러져 들어가면 모서리와 같은 모양이다(테스트에 한계로 고정해 두었다). 기구 쪽에서 막아야 한다
  - 추세선에는 최근 `debounce_n` 개 샘플을 넣지 않고 기다리게 한다(임계 직전의 내려앉는 샘플이 기준선을 끌어내리지 않게). 조건이 성립한 동안에는 기준선을 얼린다
  - **추세선의 한계(#128)**: 모서리 뒤 z 가 **일정 속도로** 떨어지면 추세선이 그 기울기를 따라가 조건이 성립하지 않는다. 2026-09-21 실기 밀기 4회 모두 EDGE 가 안 나왔다(떨어지는 속도 0.2~0.35 mm/s, 한 번은 2 mm/s)
  3. **힘 꺾임(`edge_force_drop_n > 0` 일 때, 기본 꺼짐)**: 1 로 판정을 켠 뒤, 원시 Fz 가 `[t − edge_force_window_s, t − edge_force_lag_s]` 구간의 중앙값보다 `edge_force_drop_n` 넘게 낮은 샘플이 연속 `debounce_n` 회 → 확정. F0 를 쓰지 않는다. SLIDE 시작 뒤 `edge_force_settle_s` 동안은 보지 않는다(눌린 채 시작하면 순응이 켜진 뒤 1 s 가까이 Fz 가 풀린다). 2 와 3 중 먼저 확정된 것을 내고, 로그에 `EDGE(z)` · `EDGE(force)` 로 남긴다
     - 실기 밀기 4회 재생(1.0 N): 판정 x 464.43 · 464.53 · 464.59 · 466.70 (기대 모서리 463.56. 마지막은 9.8 N 으로 눌린 채 시작한 1회). 모서리 앞 잡음은 중앙값보다 최대 0.65 N 낮았다
     - 힘 꺾임으로 확정하면 그 순간의 z 하강(`z_drop_m`)은 0~0.1 mm 로 작다. 음수는 0 으로 싣는다. 추세선이 없으면 `z_drop_valid = false`
     - 공백(`stale_age_ms`)이 나면 기준 구간도 버린다. 꺾임이 공백 안에서 끝나면 힘으로는 놓친다
  - `z_drop_m` = 판정 샘플에서 추세선보다 내려간 양(편향 보정의 δ)
  - 누름 확인 직후 곧바로 모서리가 오면 늦게 잡히고 `z_drop_m` 이 작게 실린다. 밀기는 모서리에서 충분히 떨어져 시작한다
- **OVER_FORCE**: 모든 동작에서 원시 `|F| > over_force_n` 이 연속 `over_force_debounce_n` 회. tare 와 무관. 구간마다 1 회
- `|F − F0|` 는 성분별로 뺀 뒤의 크기다(크기끼리 빼지 않는다)
- **판정 샘플 = 조건이 처음 성립한 샘플**(연속 구간의 첫 샘플). ContactEvent 의 `pose` · `pose_stamp` · `wrench` · `force_stamp` · `sample_id` 에 싣는다
  - `detect_stamp` 는 연속 N 번째(확정) 샘플의 시각이다. `detect_stamp − force_stamp` 가 디바운스 지연이다
  - `force_delta_n` 은 확정 샘플의 값이다(검출 하중. BRD 9장 "접촉으로 확정된 순간의 외력")
  - 확정 샘플의 좌표를 쓰면 디바운스 동안 더 움직인 만큼 측정값이 밀린다(50 Hz · 5 mm/s · N=3 이면 0.2 mm)
  - 이 정의는 계약 v0.1.5(#69)에서 확정됐다
- `motion_id` 가 0(없음)으로 오는 동안에는 외력이 임계 아래로 내려오면 다시 판정한다. 0 이 아닌 `motion_id` 에서는 외력이 출렁여도 1 회만 낸다
- 무효 샘플(`valid=false`)은 세지도 않고 연속 구간을 끊지도 않는다
- tare: 기준값 F0 = 성분별 평균. 불안정 판정은 `|F − F0|` 의 RMS 로 한다. 외력 크기의 표준편차(`std_norm_n`)는 방향만 바뀌는 흔들림을 놓치므로 보고용으로만 쓴다

## 파라미터
값은 [`contact_scan_bringup/config/sim.yaml`](../contact_scan_bringup/config/sim.yaml) · [`real.yaml`](../contact_scan_bringup/config/real.yaml) 의 `contact_detector:` 절에만 둔다. **코드에 기본값이 없다** — 값이 빠지면 노드가 기동하지 않는다.
계약 이름 넷(★)은 SetConfig 가 실행 중에 바꾼다. 범위를 벗어나면 거절하고, 기준값 F0 는 유지된다.
"성격"은 1차 관례대로 가른다: **출발값** = 설계에서 정한 값(실측 아님) · **실측 조정** = 실기 기록을 근거로 바꾼 값 · **재생 확인** = 실기 기록을 판정기에 다시 넣어 고른 값.

| 이름 | sim | real | 성격 | 근거 · 실측 |
|---|---|---|---|---|
| `source` | `sim` | `robot_force` | — | BRD 4.1.6 |
| ★ `contact_threshold_n` | 3.0 N | 3.0 N | 출발값(3~5 N 하한) | 무접촉 외력 크기 표준편차 최대 0.50 N(9/19, PR #57). **실측 검출 하중(2026-09-23 학민 실기, 하강 2 mm/s · 큐브 윗면 1 점 반복): 임계 3.0 → 평균 4.49 N · 10 회 중 2 회 5 N 초과, 임계 2.0 → 평균 2.76 N · 0/7 초과**(TR-01_20260923, PR #181 머지 전) |
| ★ `edge_drop_m` | 0.5 mm | 0.5 mm | 출발값 | BRD 1.4 예시 값. 실기는 스텝 모드라 이 노드의 EDGE 를 쓰지 않는다(위) |
| ★ `debounce_n` | 3 | 3 | 출발값 | 실기에서는 힘 측정 약 1 회에 해당(위 94 ms) |
| ★ `over_force_n` | 30 N | 30 N | 출발값 · 팀 결정 유지 | BRD 4.5. safety_monitor 와 같은 값(`test_config.py` 가 검사) |
| `over_force_debounce_n` | 1 | 1 | 출발값(안전 쪽) | 한 샘플로 즉시 |
| `edge_arm_force_n` | 1.5 N | 1.5 N | 출발값 | 실기 무접촉 30 s `|F − F0|` 최대 0.447 N(9/20 `idle_30s.csv`). `edge_arm_still_window_s > 0` 이면 쓰지 않는다 |
| `edge_trend_window_s` · `edge_trend_min_samples` | 0.5 s · 10 | 0.5 s · 10 | 출발값 | 42.7 Hz 에서 0.5 s 약 21 개 |
| `stale_age_ms` | 200 | 100 | 출발값 | real: 기록기 단독 간격 최대 29 ms(9/20). sim: Virtual 간격 최대 97.7 ms(계약 6.3)의 2 배. 2026-09-23 학민 실기 공백 141~160 ms 관측(TR-01_20260923) |
| `tare_duration_s` · `tare_min_samples` | 1.5 s · 30 | 1.5 s · 30 | 출발값 | BRD 4.1.3 |
| `tare_max_std_n` | 0.3 N | **1.0 N** | **실측 조정**(real) | 2026-09-23 실기 통합(기준점 tare) RMS 0.636~0.813 N 에서 0.3 N 이 두 번 `TARE_UNSTABLE` → 1.0(PR #179, 계약 v0.1.20) |
| `tare_max_force_n` | 6.0 N | 6.0 N | 출발값 | 툴 등록 `|F0|` 1.81~3.7 N, 미등록 11~12.5 N(9/19~20) 사이 |
| `descend_ref_window_s` · `descend_ref_lag_s` · `descend_ref_min_samples` | 1.0 s · 0.3 s · 10 | 같음 | **재생 확인** | 2026-09-21 학민 실기 하강 23 회를 판정기에 재생: 한 번 잡은 F0 는 공중 거짓 CONTACT 1~2 회, 이동 기준 0 회(PR #127, 계약 v0.1.12) |
| `descend_ref_settle_s` · `descend_hold_threshold_n` | 5.5 s · 6.0 N | 같음 | **재생 확인** | 2026-09-21 학민 실기 홈 출발 하강 22 회의 계단식 치우침 4.0~4.1 s(bag 재생). 5.5 s 재생 시 3 N 구간 공중 최대 2.04 N, 6 N 구간 4.43 N(PR #127). **9/23 실기에서 6 N 구간이 뚫림 → #182** |
| `edge_arm_still_window_s` · `edge_arm_still_m` · `edge_arm_travel_m` | 0.2 s · 0.1 mm · 0.5 mm | 같음 | 출발값 | #109 |
| `edge_force_drop_n` | 0(끔) | 0(끔) | 출발값 | 켤 때 1.0 N: 2026-09-21 학민 실기 밀기 4 회 재생 464.43 · 464.53 · 464.59 · 466.70(기대 463.56)(PR #132, 계약 v0.1.13) |
| `edge_force_window_s` · `edge_force_lag_s` · `edge_force_settle_s` | 0.5 · 0.1 · 1.5 s | 같음 | 출발값 | PR #132 |
| `sim_box_frame_id` · `sim_box_origin_m` · `sim_box_size_m` | `base_link` · (0.425, −0.184, 0.400) m · 0.10 × 0.06 × 0.04 m | — | 가상값 | 홈 근처(관절 0 은 특이점, 9/21 확인) |
| `sim_stiffness_n_per_m` · `sim_fall_speed_mps` · `sim_slide_press_n` | 20000 N/m · 0.05 m/s · 3.0 N | — | 가상값 | 3 N 에서 침투 0.15 mm |
| `sim_tip_radius_m` | 0.225 mm | — | 가상값 | scan_manager sim `tip_radius_m` 과 같아야 한다(치수 복원 조건). 실기 탐침은 약 2 mm(계약 v0.1.18) |

## 샘플 최신성 · 경고
- `now − max(pose_stamp, force_stamp) > stale_age_ms` 인 샘플은 버린다(계약 3.1). 샘플 간격이 `stale_age_ms` 를 넘으면 경고한다(판정은 바꾸지 않는다). 샘플이 비는 동안에는 접촉도 하강도 볼 수 없다
- **샘플이 `stale_age_ms` 넘게 끊기면 EDGE 추세선과 대기 버퍼를 버리고 다시 쌓는다**(경고). 공백을 사이에 둔 두 점을
  같은 추세에 넣으면 그사이 하강이 '정상 추세'로 흡수되어 늦은 좌표로 EDGE 를 확정하거나 아예 놓친다
  (Virtual 실측 342 ms 공백, 2026-09-20). 판정이 몇 샘플 늦어지는 대신 틀린 좌표를 내지 않는다
- DESCEND · SLIDE 인데 `motion_id` 가 0 이면 경고한다(robot_manager 는 그 이벤트로 정지하지 않는다). SLIDE 인데 tare 전이면 경고한다
- `ros2 topic echo /robot/sample` 은 `--qos-reliability best_effort` 가 필요하다

## tare (`/contact/tare`)
구간(`duration_s`, 0 이면 `tare_duration_s`) 동안의 유효 샘플로 F0 를 구한다. 실패하면 기준값을 바꾸지 않는다.
`NO_SAMPLE`(샘플 없음) · `TARE_TIMEOUT`(`tare_min_samples` 미달) · `TARE_UNSTABLE`(`|F − F0|` RMS > `tare_max_std_n`) · `TOOL_REG_SUSPECT`(`|F0|` > `tare_max_force_n`, BRD 4.1.5) · `BUSY`(진행 중).
응답의 `offset.torque` 는 쓰지 않으므로 NaN 이다. 서비스는 구간이 끝날 때까지 코루틴으로 기다리며 그동안 샘플 콜백은 계속 돈다

## 실행 · 테스트
2026-09-24 에 이 PC(Ubuntu 24.04 · Jazzy)에서 실제로 돌려 통과한 명령만 적는다. 실기 명령은 사람이 친다(CLAUDE.md 규칙 1).
```bash
# 단위 · 판정 · 분석기 · sim 입력원 시험 — ROS 를 source 하지 않아도 돈다
cd ~/ws_cobot_pjt/ws_cobot1
python3 -m pytest src/contact_detector/test -q
# 노드 시험까지 (빌드 · source 뒤. 도메인은 contact_scan_testing 이 31~39 에서 고른다)
sod && colcon build --packages-up-to contact_detector && source install/setup.bash   # sod 먼저(bringup README)
colcon test --packages-select contact_detector && colcon test-result --verbose
# sim 종단 (Virtual 없이 노드만) — bringup README 참고
ros2 launch contact_scan_bringup bringup.launch.py source:=sim
```
- 실기 전용(마지막 확인 2026-09-23, #179 실기 종단): `ros2 launch contact_scan_bringup bringup.launch.py source:=robot_force broker_host:=<웹 PC>`
- `ros2 topic echo /robot/sample` 은 `--qos-reliability best_effort` 가 필요하다

## 오프라인 분석 (T08 · T24)
```bash
ros2 run contact_detector analyze_samples idle_01.csv descend_01.csv \
    --tare-seconds 1.5 --thresholds 2 3 4 5 --debounce 1 3 5 --over-force 30
```
CSV 머리줄: `t_pose_s,t_force_s,x_mm,y_mm,z_mm,fx_n,fy_n,fz_n,valid`
- `t_*_s` 는 각 조회의 응답을 받은 시각, 위치는 Base 기준 TCP(`*_mm` 또는 `*_m`), 힘은 `get_tool_force(ref=DR_BASE)`
- 조회에 실패한 줄은 0 으로 채우지 말고 `valid=0` 으로 남긴다
- 파일 앞 `--tare-seconds` 동안은 무접촉 · 정지 상태여야 한다
- 무접촉 기록을 넣으면 "CONTACT 확정 수" 열이 그 임계 · 디바운스 조합의 거짓 접촉 횟수다

## 알려진 문제 (2026-09-24 열린 이슈)
| 이슈 | 내용 |
|---|---|
| #182 | 하강 settle 5.5 s 구간의 6 N 둔한 판정이 공중 치우침에 뚫린다 — 9/23 실기 거짓 접촉 3/10 |
| #154 | 힘 꺾임 EDGE: 옆 이동이 늦게 출발하면 출발 흔들림이 가짜 EDGE 가 된다(기본 꺼짐이라 실기 영향 없음) |
| #130 | `/robot/sample` 약 3 s 주기 공백 — 이 노드는 공백 동안 판정하지 못한다(간격 경고) |
| #16 · #24 | T16 · TR-01 상위 이슈. TR-01 은 PR #181(9/23 실측)로 완결 예정 |
| — | 검출 하중 KPI(개별 회차 5 N 이하)는 임계 3.0 에서 2/10 불합격, 2.0 에서 합격(TR-01_20260923). 임계를 바꿀지는 팀 결정 전 |
