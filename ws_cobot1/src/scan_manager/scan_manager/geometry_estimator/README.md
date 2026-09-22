# geometry_estimator

윗면 1점 + 모서리 4점 → 편향 보정 → 윗면 사각형 · 외곽 엣지·경로 후보 4개 · 직육면체(꼭짓점 8, 모서리 12) · 가로/세로/높이.
소유: 현지 (T17). scan_manager 안의 모듈이며 노드가 아니다. **rclpy · numpy 를 import 하지 않는다.**
결과물은 외곽 엣지·경로 후보다. 용접 이음 판정이 아니다.

## 쓰는 법 (scan_manager, GEOMETRY 단계)
```python
from scan_manager.contract_enums import Direction
from scan_manager.geometry_estimator import BiasParams, EdgeObservation, TopObservation, estimate_box

params = BiasParams(tip_radius_m=..., detect_latency_s=..., edge_round_radius_m=..., edge_bias_offset_m=...)
box = estimate_box(
    top=TopObservation(z_m=..., descend_speed_mps=...),
    edges={Direction.POS_X: EdgeObservation(coordinate_m=..., z_drop_m=..., slide_speed_mps=...), ...},
    support_z_m=...,
    params=params,
)
if box.success: ...          # 예외를 던지지 않는다. 실패는 box.error 로 알린다
```

### 입력
| 값 | 출처 | 비고 |
|---|---|---|
| `TopObservation.z_m` | CONTACT `ContactEvent.pose.position.z` (판정 좌표. 정지 완료 좌표가 아니다) | |
| `TopObservation.descend_speed_mps` | 그 DESCEND goal 의 `speed` | |
| `EdgeObservation.coordinate_m` | EDGE `ContactEvent.pose.position` 에서 **진행 축의 값** (±X 는 x, ±Y 는 y) | 다른 축 값은 쓰지 않는다(축 평행 전제, BRD 6장) |
| `EdgeObservation.z_drop_m` | `ContactEvent.z_drop_m` (`z_drop_valid=false` 면 `None`) | 임계값이 아니라 실제 하강량 δ. **`None` 이면 d = 0 으로 보정한다**(아래, #146) |
| `EdgeObservation.slide_speed_mps` | 그 SLIDE goal 의 `speed` | |
| `support_z_m` | 지지면 높이. 작업대 좌표면 0 (units-frames.md: z=0 = 작업대 표면) | |
| `BiasParams` | scan_manager 파라미터 (아래) | 코드에 기본값이 없다 |

- **프레임**: 입력 좌표와 `support_z_m` 은 같은 프레임이어야 하고 출력도 그 프레임이다. 이 모듈은 변환하지 않는다.
  `ScanResult` 는 작업대 좌표이므로, 호출 전에 판정 좌표(Base)에서 `base_to_fixture` 를 뺀다(평행 이동만, units-frames.md).
- 미측정은 `None` 이다. 0 · NaN 을 넣지 않는다(NaN 이 들어오면 미측정으로 처리한다).

### 출력 `BoxEstimate`
필드 이름은 `ScanResult.msg` · `result_store.ShapeResult` 와 같다: `z_top` · `x_pos` · `x_neg` · `y_pos` · `y_neg` · `support_z`,
`width`(x) · `length`(y) · `height`(z) · `dims_valid`, `vertices[8]` · `edges[12]` · `path_candidates[4]` · `box_valid`. 순서 규약은 계약 3.5절.
- 무효인 값은 `None` 이고 배열 길이는 유지한다. `ShapeResult` 로 옮길 때 `Measured.of(v)` / `Measured.missing()`, `SegmentRecord(...)` 로 감싼다
- `bias_corrections[Direction]` · `top_correction`: `raw_coordinate_m` · `correction_m` · `corrected_m` · `valid` · `inputs` · `detail`.
  `result_store.BiasCorrection(raw_coordinate_m, correction_m, valid, inputs)` 에 그대로 넣을 수 있다
- 실패해도 얻은 값(`z_top`, 일부 `x_pos` …)은 채워서 돌려준다

| `error` | 뜻 | ReasonCode |
|---|---|---|
| `''` | 성공 | `OK` |
| `GEOM_MISSING_POINT` | 5점 · 지지면 중 없는 값이 있다. **속도를 몰라 보정할 수 없는 경우도 포함한다**(보정 없이 통과시키지 않는다). 하강량 δ 만 모르는 것은 실패가 아니다(d = 0, 아래). 음수 · inf 인 δ 는 여기다. `detail` 에 어느 값인지 적는다 | `INSUFFICIENT_POINTS(501)` |
| `GEOM_NONPOSITIVE_WIDTH` | 가로 또는 세로가 0 이하 | `INVALID_SHAPE(500)` |
| `GEOM_NEGATIVE_HEIGHT` | 높이가 0 이하 (0 도 포함한다) | `INVALID_SHAPE(500)` |

## 편향 보정 (`bias.py`)
```
모서리:  corrected = raw − (진행 방향 부호) x [ d − R + v·t + offset ]
           d = √(2(R + r)δ − δ²)      δ < R + r
           d = R + r                  δ ≥ R + r   (팁이 모서리를 완전히 벗어남)
           d = 0                      δ 모름      (z_drop_valid=false. 힘 꺾임 EDGE, #146)
윗면:    z_top = raw + v_descend·t
```
- r `tip_radius_m`, t `detect_latency_s`, R `edge_round_radius_m`, offset `edge_bias_offset_m`, δ `z_drop_m`, v 밀기 속도
- R = 0 이면 BRD 1.4 의 식 √(2rδ − δ²) + v·t 다. BRD 예시(r 3 mm, δ 0.5 mm, 10 mm/s, 40 ms → 약 2.1 mm)는 테스트에 있다
- **δ ≥ R + r 에서 고정하는 이유**: 구 중심이 모서리를 (R + r) 만큼 지나면 접촉 법선이 수평이 되어 팁이 더는 모서리에 얹혀 있지 않다.
  식을 그대로 쓰면 그 뒤로는 d 가 도로 작아지고(덜 보정), δ > 2(R + r) 에서는 제곱근 안이 음수다.
  실측 r = 0.225 mm 에서 `edge_drop_m` 출발값 0.5 mm 가 이 구간이다. BRD 1.4 에는 이 경우가 없다(ADR 후보)
- 팁이 벗어난 뒤 δ 에 닿을 때까지 수평으로 더 간 거리는 식으로 알 수 없다. `edge_bias_offset_m`(기준 블록 실측, T30)에 들어간다
  - **`edge_bias_offset_m` 은 방향당 값이다. 폭 차이가 아니다.** offset 을 0 으로 두고 잰 뒤
    `edge_bias_offset_m = (추정 폭 − 캘리퍼스 폭) ÷ 2` (세로도 같다). 2 로 나누지 않으면 그만큼 과보정한다
  - 부호: 진행 방향으로 더 나간 거리가 +. 추정 폭이 캘리퍼스보다 크면 +, 작으면 −
  - 이 거리는 δ 가 클수록 길다(더 오래 내려앉는다). 그리고 δ < R + r 이면 팁이 아직 모서리에 얹혀 있으므로 0 이다.
    그래서 offset 은 **그 `edge_drop_m` · 밀기 속도 · 누름 힘에서만** 맞는 값이다. 이 중 하나를 바꾸면 다시 잰다
  - R 과 offset 을 가르는 법: `edge_drop_m` 을 팁 반지름보다 작게 두고 재면 offset 몫이 없다. 그때 남는 폭 오차
    `2 x (d − R + v·t)` 에서 v·t 는 밀기 속도를 둘로 바꿔 재면 기울기로 분리되고, 나머지가 R 이다.
    예리한 모서리(R = 0)와 R = 1.7 mm 는 δ = 0.2 mm 에서 폭으로 약 2.1 mm 차이가 난다(계산값).
    그만큼 작은 하강량을 실기에서 안정적으로 판정할 수 있는지는 확인하지 않았다(T25)
- **δ 를 모를 때 d = 0 으로 두는 이유 (#146)**: 힘 꺾임 EDGE(#128)는 z 추세선 없이도 확정되고, 그때 `z_drop_valid = false` 다.
  예전처럼 실패로 두면 한 방향 때문에 네 방향을 다 잰 스캔 전체가 501 로 끝난다.
  - d 는 0 ~ (R + r) 이므로 d = 0 가정의 오차는 **방향당 최대 R + r**(R = 0, r = 0.225 mm 면 0.225 mm)이다. 시험으로 고정했다
  - 힘 꺾임은 구가 모서리를 막 넘기 시작할 때 나므로 d ≈ 0 이 실제에 가깝다(2026-09-21 힘 경로 재생 4 회 · 실기 1 회: δ 0 ~ 0.10 mm → d 0 ~ 0.19 mm, #132 학민)
  - **δ 를 0 으로 저장하지 않는다**(규칙 4). `inputs['z_drop_m']` 은 `None` 그대로 남는다. 0 은 보정식의 기하 항이다
  - 남는 계통 몫은 offset 이 가져간다. 그래서 힘 꺾임을 쓰면 **offset 도 힘 꺾임을 켠 상태로** 잰다(T25)
- **R(모서리 둥글림)**: 둥근 부분은 공칭 모서리보다 R 안쪽에서 시작하므로 보정량이 음수가 될 수 있다(R 1.7 mm · δ 0.5 mm → −0.41 mm).
  블록의 R 은 아직 재지 않았다. **모따기(C)는 다루지 않는다**
- 판정 지연 t 에 디바운스 몫이 들어가는지는 `ContactEvent` 의 "판정 샘플" 정의(이슈 #69)에 달려 있다

## scan_manager 에 필요한 파라미터 (yaml 의 `scan_manager:` 절)
`tip_radius_m` · `detect_latency_s` (정의서 6.4 의 이름) · `edge_round_radius_m` · `edge_bias_offset_m` (신규) · `support_z_m` · `base_to_fixture`.
sim 에서는 `tip_radius_m` 을 contact_detector 의 `sim_tip_radius_m` 과 같은 값으로 둔다.

## 테스트
```bash
cd ~/ws_cobot_pjt/ws_cobot1 && python3 -m pytest src/scan_manager/test/test_geometry_estimator.py -q    # ROS 없이 돈다
```
기대값은 참값 블록(캘리퍼스 치수에 해당)에서 정방향 모델로 판정 좌표를 만들고, 추정 결과가 참값으로 돌아오는지로 잡는다.
