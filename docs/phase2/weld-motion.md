# 용접 모션 정의 (phase 2)

상태: **v0.2.0 초안** (2026-09-23, 병후). 결정 D1~D18 은 `README.md`. 수치는 전부 **설계 출발값**이고 파라미터로 둔다(코드에 박지 않는다).
단위: ROS 내부 m · rad · quaternion, 두산 mm · deg(ZYZ), 웹 mm — 1차와 같다(`docs/contracts/units-frames.md`).

## 1. 용접 대상: 8 선

스캔 결과 `ScanResult.edges[12]`(작업대 좌표 `workpiece_fixture`)에 이미 있다. 새로 계산하지 않는다.
꼭짓점 순서(계약 3.5절): 윗면을 +z 에서 내려다봐 `(x−, y−)` 부터 반시계, `i + 4` 가 `i` 의 바로 아래.

| 선 | `edges[]` | 이음선 | 진행 방향 t̂ | 바깥 방향 n̂_out (두 면 법선의 합, 정규화) |
|---|---|---|---|---|
| L0 | 0 | v0 → v1 (y = y⁻ 변) | +x | −y |
| L1 | 1 | v1 → v2 (x = x⁺ 변) | +y | +x |
| L2 | 2 | v2 → v3 (y = y⁺ 변) | −x | +y |
| L3 | 3 | v3 → v0 (x = x⁻ 변) | −y | −x |
| L4 | 8 | v0 → v4 (모서리 x⁻ y⁻) | −z | (−1, −1, 0)/√2 |
| L5 | 9 | v1 → v5 (모서리 x⁺ y⁻) | −z | (+1, −1, 0)/√2 |
| L6 | 10 | v2 → v6 (모서리 x⁺ y⁺) | −z | (+1, +1, 0)/√2 |
| L7 | 11 | v3 → v7 (모서리 x⁻ y⁺) | −z | (−1, +1, 0)/√2 |

- **순서**: L0 → L1 → L2 → L3 (윗면 루프) → L4 → L5 → L6 → L7 (세로, 위 → 아래). `start_line` 부터 `end_line` 까지, 밖은 `SKIPPED`.
- **세로선의 끝**은 `v(i+4)` 가 아니라 **`z = support_z + bottom_margin_m`** 이다(받침대에 닿지 않는다. `support_z` 는 측정값이 아니라 파라미터라 신뢰하지 않는다). `WeldLine.seam` 에는 이 짧아진 선을 싣는다.
- 코너마다 정지한다(blend 없음, D8). 윗면 루프의 코너에서도 자세가 바뀌므로 어차피 정지가 필요하다.

## 2. 툴 자세 (D1 · D3)

툴 z 축(플랜지 → 팁) 방향 **d** 는 두 면의 법선을 이등분하는 면 안에서 연직에서 `tilt_deg`(θ, 출발값 45°) 만큼 바깥으로 기운다.

```
d = −( cos θ · ẑ + sin θ · n̂_out )          # 팁은 이음선을 향해 아래 · 안쪽을 본다. 자루는 위 · 바깥으로 뻗는다
x_tool = normalize( t̂ × d )                 # 위빙 방향 w 와 같다 (이음선을 가로지르는 방향)
y_tool = d × x_tool
R = [ x_tool | y_tool | d ]  → quaternion → (robot_manager 가) ZYZ deg
```

- 윗면 변(L0~L3): n̂_out ⊥ ẑ 이므로 d 는 정확히 두 면 법선의 이등분 방향의 반대다.
- 세로 모서리(L4~L7): 두 면 법선의 합은 수평이므로 "이등분 + 45° 기울임" = d 는 수평 대각선과 연직의 가운데.
- θ = 0 이면 1차 스캔과 같은 수직 자세다(검산: 홈 quaternion 의 툴 z 축 = (0, 0, −1)).
- 툴 축 둘레의 회전(roll)은 손목(J6) 도달성과 세로선의 핑거 방향에 영향을 준다. **위빙 방향 w 는 roll 과 무관하게 `normalize(t̂ × d)` 로 정한다**(탐침은 축대칭). 툴 자세의 roll 은 **선별 파라미터 `tool_roll_deg[8]`**(d 둘레 회전, 출발값 전부 0)로 두어 M1 에서 막히는 선만 돌린다(현지 리뷰 6). 위 식의 x_tool 은 roll 0 의 기준 축이고, roll ≠ 0 이면 x_tool · y_tool 을 d 둘레로 그만큼 돌린 것이 툴 자세다. 참고: roll 0 에서는 윗면 루프의 ZYZ A 가 선마다 90° 씩 돈다(M1 표 90 → −180 → −90 → 0).
- **2026-09-23 좌표로 계산한 대표 자세**(두산 posx, mm · ZYZ deg, 스탠드오프 3 mm 포함)는 `measurements-20260923.md` 표 M1 에 있다. 오늘 실기에서 도달성을 확인한다.

## 3. 스탠드오프 (D2)

접촉하지 않는다. 힘 · 순응 제어를 켜지 않는다. **`standoff_m` 은 팁 구 표면과 이음선의 최단거리다**(D22, 현지 리뷰 1). 팁은 이음선에서 툴 축 반대 방향(−d)으로 물러나되, 물러나는 양 s′ 은 선의 방향에 따라 다르다.

```
r  = tip_radius_m                      # 팁 구 반지름 (스캔과 같은 값, 약 2 mm)
k  = sqrt(1 − (d · t̂)²)                # 툴 축이 이음선과 이루는 각의 sin. 윗면선 1, 세로선 sin θ
s′ = (standoff_m + r) / k − r          # 축 방향 물러남. 윗면선 = standoff_m, 세로선(45°) ≈ 5.07 mm
o  = s′ · (−d)
TCP 목표 = 이음선 위의 점 + o          # TCP 는 구 중심에서 d 방향으로 r 인 점(수직 자세의 최하단점)이라 위 식이 그대로 맞는다
```

- 왜: 축 방향으로 3 mm 만 물러나면 세로선에서는 구 표면 ↔ 이음선이 (3 + 2)·sin45° − 2 ≈ **1.5 mm** 뿐이다(9/23 폭 오차 +1.5 mm 와 같은 크기. 접촉 판정이 없는 이동이라 과대 외력 전까지 막을 것이 없다).
- 검산: 윗면선은 k = 1 이라 예전 정의와 같은 값(3 mm)이다.

## 4. 위빙 (D1)

`move_periodic` 은 **제자리 주기 운동**이라 직선 이동과 겹쳐 실행되지 않는다(dsr_msgs2 `MovePeriodic.srv`: amp · periodic · repeat 만 받는다). 그래서 위빙은 **지그재그 경유점**으로 만들고, robot_manager 가 경유점을 차례로 지난다(`ExecutePath`).

```
L' = 이음선 길이 (세로선은 bottom_margin 을 뺀 길이)
N  = max(1, ceil(L' / weave_pitch_m))
for k in 0..N:
    s_k = min(k · weave_pitch_m, L')
    a_k = 0                        if k == 0 or k == N      # 시작 · 끝은 이음선 위
        = weave_amplitude_m · (−1)^k   otherwise
    p_k = S + t̂ · s_k + o + w · a_k                         # w = x_tool
weave_amplitude_m == 0 또는 weave_pitch_m == 0 → [S + o, E' + o] 두 점 (직선)
```

- w 는 t̂ 와 d 에 모두 수직이라 "진행 방향과 수직으로, 두 면을 가로질러" 흔든다.
- 출발값 진폭 2 mm · 반주기 4 mm → 80 mm 선에 경유점 21 개, 경로 길이는 직선의 약 1.38 배(110.8 mm). 10 mm/s 면 선당 약 11 s. 접근 · 후퇴 · goal 4 개를 더하면 **8 선 약 2.5 분, 경유점마다 멈추면 약 4 분**(현지 계산. 발표 시간표용. 스캔 약 7 분은 별도).
- robot_manager 가 경유점을 `move_spline_task`(한 번 호출, 부드러움) 로 지나든 `move_line` 을 잇든(radius 로 blend) 계약은 같다: **경유점을 순서대로, `speed` 로, 마지막 점에서 정지**. 선택은 학민(D14 · D19). 오늘 실기 M4 에서 둘 중 되는 것을 본다.

## 5. 접근 · 후퇴 · 선 사이 이동

```
P_app(i) = p_0(i) + approach_m · (−d_i)        # 첫 경유점에서 툴 축 뒤로 물러난 점
P_ret(i) = p_N(i) + approach_m · (−d_i)
z_safe   = z_top + travel_clearance_m           # 작업대 좌표. 선 사이 이동 높이
```

한 선 i 의 절차(모든 좌표는 weld_manager 가 Base 로 바꿔 보낸다, `+ base_to_fixture`):

| 단계 | goal | 속도 |
|---|---|---|
| 접근 1 | `ExecuteMotion OP_MOVE_TO` → (P_app(i).x, y, **z_safe**, q_i) | `travel_speed_mps` |
| 접근 2 | `OP_MOVE_TO` → P_app(i) | `approach_speed_mps` |
| 용접 | `ExecutePath` waypoints = [p_0 … p_N, P_ret(i)] | `weld_speed_mps` |
| 후퇴 | `OP_MOVE_TO` → (P_ret(i).x, y, **z_safe**, q_i) | `travel_speed_mps` |

- 첫 선 앞: 홈에서 접근 1 로 바로 간다(자세가 홈 → q_0 으로 보간된다. 이동 중 자세 변화는 z_safe 위에서만 일어난다).
- 선 사이: 후퇴(i) → 접근 1(i+1). 두 점 모두 z_safe 위라 부재를 가로질러도 된다.
- 마지막 선 뒤: 후퇴 → `OP_HOME`(마무리 복귀, DONE 에 포함).
- 세로선의 P_ret 는 바닥 근처(받침대 + `bottom_margin_m` + approach 의 수직 성분)다. 거기서 z_safe 로 곧장 올라가는 경로는 모서리에서 대각선 바깥으로 `(standoff_m + approach_m)·sin θ` 떨어져 있다(3 + 30 mm, 45° 면 약 23 mm).
- **작업영역 검사**(weld_manager): 모든 목표 z ≥ `support_z + bottom_margin_m` (작업대 좌표), x · y 는 부재에서 `workspace_margin_m` 안. 벗어나면 `PATH_REJECTED(604)` 로 시작을 거절한다. safety_monitor 는 작업영역을 보지 않는다(`OUT_OF_WORKSPACE` 미구현). robot_manager 는 Base z 하한(`path_min_z_m`) 하나를 수락 시점에 더 본다(두 겹, `weld-ros-interfaces.md` 5.2).
- **툴 외형 검사**(weld_manager, D23, 현지 리뷰 2): 윗면선(L0~L3)은 툴의 모든 점이 이등분 축 뒤쪽이라 부재와 겹칠 수 없다(roll · 핑거 폭 무관). **세로선(L4~L7)은 부재가 팁 위로도 z_top 까지 있어** 탐침 몸통 · 홀더 · RG2 핑거가 옆면이나 작업대에 닿을 수 있다. 툴 외형을 파라미터 **`tool_profile_u_m` · `tool_profile_r_m`**(같은 길이의 두 배열. u = 팁에서 축 방향 뒤 거리, R = 그 자리에서 축에서 가장 멀리 뻗은 반폭. ROS 2 파라미터는 중첩 배열이 안 돼 두 배열로 둔다. 값은 M2 캘리퍼 실측, 현지 확정)로 받아 세로선마다 검사한다:
  - 옆면: 모든 (u, R) 에 대해 **R < (s′ + u) · tan θ**. tilt 0 이면 tan θ = 0 이라 세로선은 항상 실패한다 — **"tilt 0" 시험은 L0 에만 쓴다**.
  - 작업대: 툴의 가장 낮은 점 **z_TCP + u · cos θ − R · sin θ ≥ support_z**(작업대 좌표) 를 세로선 아래 끝에서 검사한다.
  - 어기면 `PATH_REJECTED(604)` 로 시작을 거절하고 detail 에 어느 선 · 어느 (u, R) 인지 적는다. 로봇을 움직이기 전의 계산만이다.

## 6. 파라미터 (weld_manager, `contact_scan_bringup/config/{sim,real}.yaml` 의 `weld_manager:` 절)

| 이름 | 출발값 | 뜻 | WeldConfig |
|---|---|---|---|
| `weld_speed_mps` | 0.010 | 용접선 위 속도 | ○ |
| `travel_speed_mps` | 0.050 | 선 사이(z_safe) 이동 속도 | ○ |
| `approach_speed_mps` | 0.020 | 접근 2 · 후퇴 속도 | |
| `standoff_m` | 0.003 | 스탠드오프 | ○ |
| `weave_amplitude_m` | 0.002 | 위빙 진폭 | ○ |
| `weave_pitch_m` | 0.004 | 위빙 반주기 | ○ |
| `tilt_deg` | 45.0 | 기울임 | ○ |
| `tool_roll_deg` | [0 × 8] | 선별 툴 축 둘레 회전(도달성 · 핑거 방향 조정, D24) | |
| `tip_radius_m` | 0.002 | 팁 구 반지름. scan_manager 와 같은 값(스탠드오프 정의, 3절) | |
| `tool_profile_u_m` · `tool_profile_r_m` | (M2 실측) | 툴 외형: 팁 뒤 거리 u 와 그 자리의 최대 반폭 R, 같은 길이 두 배열 (5절 외형 검사) | |
| `weld_speed_min_mps` | 0.002 | 용접 · 접근 속도 하한. robot_manager 의 이동 판정(0.3 s · 0.2 mm ≈ 0.67 mm/s)보다 커야 한다(#152 거짓 도착) | |
| `approach_m` | 0.030 | 접근 · 후퇴 거리 | |
| `travel_clearance_m` | 0.050 | z_safe = z_top + 이 값 | |
| `bottom_margin_m` | 0.005 | 세로선 끝 = support_z + 이 값 | |
| `workspace_margin_m` | 0.100 | 부재 밖 허용 범위 (x · y) | |
| `path_tolerance_m` | 0.003 | ExecutePath 마지막 점 도착 허용치 (D18 ±3 mm) | |
| `motion_timeout_s` | 120.0 | 단위 goal 제한 | |
| `result_dir` | data | scan_manager 와 같은 값이어야 한다 (result_store 를 읽는다). 현지의 `result_dir` 절대경로 · sim/real 분리 PR 이 들어오면 그 값으로 바꾼다(`""` = 최신 성공 결과가 sim 결과를 고르지 않게) | |
| `result_frame_id` · `motion_frame_id` | workpiece_fixture · base_link | 1차와 같다 | |
| `state_publish_period_s` | 1.0 | /weld/state 주기 | |
| `scan_state_timeout_s` | 5.0 | /scan/state 가 이보다 오래됐으면 시작 거절 | |

robot_manager 쪽: `path_max_points`(출발값 200) · `path_max_speed_mps`(0.100, 넘으면 604) · **`path_min_z_m`**(Base z 하한, 경유점 하나라도 아래면 604. 출발값 0.100 = 작업대 0.095 + 테이프 0.002 + 여유 0.003) · `path_acc_ratio`(4.0, 단위 1/s: 가속 [mm/s²] = 이 값 × 속도 [mm/s], 1차 `move_line_request` 의 `acc = 4 × vel` 과 같음).

## 7. 오늘 실기에서 정해야 하는 것

`measurements-20260923.md`(별도 PR `p2-measure-0923`, 정 학민 · 부 병후) M1~M6. 특히 M1(기울인 자세 도달성)과 M2(손가락 아래 탐침 노출 길이)가 없으면 연휴 중 코드가 9/29 에 안 맞을 수 있다.
