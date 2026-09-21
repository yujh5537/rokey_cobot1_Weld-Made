# 실기 세션 절차 · 기록 (2026-09-21 오후) — T30 선행(TCP x·y) · T24 · T25

- 시험자 / 입회(비상정지 대기): 학민 / (이름) — **2인 1조. 입회자는 비상정지에서 손을 떼지 않는다**
- 환경: **실기** · main `983be2c` 이후(#101 `/robot/stop` · #114 · #116 안전복귀 · #117 safety_monitor 수정 · #100 `home_joint_deg` 포함) · `real.yaml`
- 부재: 기준 큐브 80 × 80 × 80 mm, **테이프선에 맞춰 본드로 고정**(units-frames.md v0.1.11 배치 원칙)
- 좌표 기준: `docs/contracts/units-frames.md` v0.1.11 (TCP z 252.12, z=0 100.503)
- 원본: `docs/test-reports/data/20260921_pm/`

> 로봇 명령은 사람이 실행한다(CLAUDE.md 규칙 1). 이 문서의 명령은 Claude 가 인터페이스 정의와 대조해 적었고, **실기에서 돌려 본 것은 아니다.**

## 순서와 이유
| 순서 | 항목 | 일정 ID | 왜 이 순서인가 |
|---|---|---|---|
| 0 | 준비 (빌드 · 툴/TCP 등록) | | |
| 1 | **새 탐침 TCP x · y** (J6 180°) | T30 선행 | 실기 좌표값(`search_origin_pose` · `base_to_fixture`)을 켜는 조건 ②. **launch 를 띄우기 전에** 한다 — `probe_point.py` 를 robot_manager 조회와 겹쳐 부르면 드라이버가 멈출 수 있다 |
| 2 | 탐침 점검 (기준점 접촉) | 전제조건 | units-frames.md '탐침 상태 전제조건'. 이후 모든 좌표가 이 점검을 통과해야 유효하다 |
| 3 | TR-01: 같은 점 10회 접촉 | **T24** | 9/20 지연 |
| 4 | 네 방향 밀기 · 모서리 검출 · 편향 | **T25** | 9/20 지연. 큐브가 이제 고정돼 있다 |
| — | 전체 탐색 · TR-02 · TR-08 | T30 · T31 · T32 | **아직 못 한다**: `/scan/run` 은 실기 좌표값이 꺼져 있어 거절된다. 켜려면 #109(정지 tare 거짓 접촉) 해결 + 1번 결과 반영이 먼저다 |

## 0. 준비
```bash
cd ~/ws_cobot_pjt && git pull --ff-only && git log --oneline -1   # 983be2c 이후인지
cd ws_cobot1 && cbc                                                 # 빌드 + source
# 터미널 A
sod && sodreal
# 터미널 B (launch 는 아직 띄우지 않는다)
sod && cd ~/ws_cobot_pjt
python3 docs/env/apply_tool_tcp.py          # 마지막 줄 OK: tcp=rg2_probe_tip [-1.3, 3.71, 252.12]
mkdir -p docs/test-reports/data/20260921_pm
```
- [ ] `apply_tool_tcp.py` 마지막 줄 `OK`, TCP z **252.12** (기본값이 #110 에서 바뀌었다)
- [ ] 큐브가 테이프선에 맞춰 본드로 붙어 있다. 손으로 밀어 움직이지 않는다
- [ ] 탐침 눈 · 손 점검: 맞춤선, 팁 닳음 · 휨, 유격, 홀더 스토퍼

## 1. 새 탐침 TCP x · y (J6 180°, launch 끄고)
원리 · 계산: `docs/env/tcp_xy_from_180.py` 머리말. 표시 팁 좌표는 등록된 TCP 로 계산되므로 같은 자세에서는 x · y 오차가 안 보인다. J6 만 180° 돌리면 오차의 두 배만큼 팁이 벗어난다.

1. 작업대 빈 자리(큐브에서 50 mm 이상)에 가는 펜 십자 표시를 붙인다
2. 펜던트로 팁을 표시 중심 바로 위 **0.5~1 mm** 에 맞춘다(돋보기). 탐침 수직
   ```bash
   python3 docs/env/probe_point.py --label xy_0 --file docs/test-reports/data/20260921_pm/tcp_xy.csv
   ```
3. **J6 만 +180°** 조그한다(−204.84° 쪽이면 −24.84° 방향으로. −180° 로 돌리면 한계를 넘는다). 케이블 확인
4. **Base x · y 평행 이동만으로** 팁을 다시 표시 중심 위에 맞춘다. 자세 · 높이는 건드리지 않는다
   ```bash
   python3 docs/env/probe_point.py --label xy_180 --file docs/test-reports/data/20260921_pm/tcp_xy.csv
   python3 docs/env/tcp_xy_from_180.py docs/test-reports/data/20260921_pm/tcp_xy.csv --tcp -1.30 3.71 252.12
   ```
5. 보정량이 0.3 mm 를 넘으면 새 값으로 등록하고 1~4 를 한 번 더 해 0.3 mm 안인지 본다
   ```bash
   python3 docs/env/apply_tool_tcp.py --tcp-x <새 x> --tcp-y <새 y> --tcp-z 252.12 --note "09-21 J6 180° x·y"
   ```
6. J6 를 원래대로 되돌린다

| | x | y | z | 회전 · 잔차 |
|---|---|---|---|---|
| xy_0 | | | | |
| xy_180 | | | | |
| 보정량 dx · dy | | | | |
| 재확인 보정량 | | | | |

- 결과 TCP x · y: ( , ) — 0.3 mm 안이면 (−1.30, 3.71) 유지

## 2. 탐침 점검 — 작업대 기준점 (525.19, −172.09)
```bash
# 터미널 C: launch (실기)
sod && cd ~/ws_cobot_pjt/ws_cobot1 && source install/setup.bash
ros2 launch contact_scan_bringup bringup.launch.py source:=robot_force
# 터미널 D: 첫 접촉 방어선을 낮춘다(실행 중 값만. 두 노드가 같아야 한다)
ros2 param set /contact_detector over_force_n 15.0
ros2 param set /safety_monitor over_force_n 15.0
# 터미널 E: 기록
cd ~/ws_cobot_pjt/docs/test-reports/data/20260921_pm
ros2 bag record -o bag_pm /robot/sample /robot/status /contact/event /safety/status
# 터미널 F: 이벤트 보기
ros2 topic echo /contact/event
```
- [ ] `ros2 node info /robot_manager` 에 `/robot/stop` 서버가 있다
- [ ] safety_monitor 가 떠 있다(#117 로 첫 정지 조건에서 죽던 것이 고쳐졌다)

명령(터미널 G). **먼저 위치를 찍는다**(`ros2 topic echo --once /robot/sample`). 안전복귀 → 옆으로 → 아래로 → 하강 중 tare.
`lift` 는 **접촉 · 밀기 뒤 안전복귀 전에 항상** 쓴다. 닿거나 모서리 밖에 있는 팁에서 바로 관절 이동을 보내면 경로가 비스듬해 부재를 긁을 수 있다(계약 7.3 의 올림과 같은 이유). 위치 읽기는 격리 도메인에서 가짜 샘플로 확인했다. 실기 첫 사용 때 출력된 x y z 가 맞는지 보고 보낸다:
```bash
G=/robot/execute_motion; T=contact_scan_interfaces/action/ExecuteMotion
Q="orientation: {x: 0.9999791452, y: 0.0064576733, z: -0.0000833683, w: -0.0000257908}"   # 홈 자세 (units-frames.md 49행)
lift() {   # $1 = motion_id. 지금 팁 위치에서 z 만 50 mm 올린다. 실패하면 1 을 돌려준다(반복을 멈춘다)
  IFS=, read x y z < <(ros2 topic echo --once --csv --field pose.position /robot/sample)
  echo "지금 팁 x=$x y=$y z=$z → z+0.05 로 올린다"
  out=$(ros2 action send_goal $G $T "{scan_id: 'pm', motion_id: $1, operation: 1, frame_id: 'base_link', speed: 0.01, target: {position: {x: $x, y: $y, z: $(python3 -c "print($z+0.05)")}, $Q}}")
  echo "$out" | tail -8
  echo "$out" | grep -q "^ *reason: 0$" || { echo "!! 올림 실패 — 안전복귀하지 않는다. 펜던트로 올린다"; return 1; }
}
ros2 action send_goal $G $T "{scan_id: 'pm', motion_id: 1, operation: 4}"
ros2 action send_goal $G $T "{scan_id: 'pm', motion_id: 2, operation: 1, frame_id: 'base_link', speed: 0.03, target: {position: {x: 0.52519, y: -0.17209, z: 0.28784}, $Q}}"
ros2 action send_goal $G $T "{scan_id: 'pm', motion_id: 3, operation: 1, frame_id: 'base_link', speed: 0.03, target: {position: {x: 0.52519, y: -0.17209, z: 0.130}, $Q}}"
# 하강을 백그라운드로 보내고 5 s 뒤 tare (출발 약 4 s 뒤 외력 추정이 계단식으로 치우친다. 5-2)
ros2 action send_goal $G $T "{scan_id: 'pm', motion_id: 4, operation: 2, speed: 0.003, max_distance: 0.031}" &
sleep 5; ros2 service call /contact/tare contact_scan_interfaces/srv/TareForce "{duration_s: 0.0}"
wait
# 기준점 바로 위 홈 높이로 올린다. lift(50 mm)로는 z 약 150 mm 라 큐브 윗면(180.4)보다 낮아,
# 다음 안전복귀가 큐브 쪽을 지나갈 수 있다
ros2 action send_goal $G $T "{scan_id: 'pm', motion_id: 5, operation: 1, frame_id: 'base_link', speed: 0.01, target: {position: {x: 0.52519, y: -0.17209, z: 0.28784}, $Q}}"
```
- 30 mm 를 3 mm/s 로 약 10 s. **main 코드**에서는 손 tare(1.5 s)가 접촉 전에 끝난다. 판정이 실패해도 `max_distance` 0.031 이라 작업대 아래 0.5 mm 에서 멈춘다
- **#127(하강 중 자동 영점) 코드로 할 때는 이 문장이 틀린다.** 자동 영점은 출발 6 s 뒤부터 모으고, 그동안(보통 7.5 s, 최악 10.5 s = 31.5 mm)은 CONTACT 를 올린 임계(6 N)로 본다. 작업대까지 29.5 mm 라 최악이면 6 N 판정(더 눌린 좌표)이 된다. 손 tare 는 필요 없다. 이 점검은 main 코드로 하거나, 출발 높이를 더 올린다(z 0.150 이면 49.5 mm)
- **판정 좌표**(`/contact/event` 의 `pose.position.z`)를 쓴다. 정지 좌표(Result.pose)는 판정 뒤 눌린 만큼 낮다(작업대 0.29 mm)

| 판정 z [mm] | 기준값 | 차 | 허용치 | 판정 |
|---|---|---|---|---|
| | 100.503 | | 0.3 (초안) | |

- 통과 못 하면: 탐침을 다시 끝까지 끼우고 반복 → 그래도 밖이면 교체 절차(units-frames.md)
- **이 뒤 과대 외력 정지가 나면 이 점검을 다시 한다**(이벤트 점검)

## 3. TR-01 (T24): 큐브 윗면 같은 점 10회
홈은 큐브 중심 바로 위다. 매회 안전복귀 → 하강(백그라운드) → **8 s 뒤 tare** → CONTACT.
```bash
for i in $(seq 1 10); do
  ros2 action send_goal $G $T "{scan_id: 'pm', motion_id: $((100+2*i)), operation: 4}"
  ros2 action send_goal $G $T "{scan_id: 'pm', motion_id: $((101+2*i)), operation: 2, speed: 0.003, max_distance: 0.113}" &
  sleep 8; ros2 service call /contact/tare contact_scan_interfaces/srv/TareForce "{duration_s: 0.0}"
  wait; lift $((150+i)) || break
done
```
- 한 회 약 45 s(107 mm ÷ 3 mm/s + 복귀). **한 줄씩 끝나는 것을 보고** 다음으로 간다. 이상하면 Ctrl-C 후 `/robot/stop`
- `max_distance` 0.113 = 계약 하한(홈 → 윗면 107.44 + 5). 판정이 실패해도 5.6 mm 안에서 과대 외력 15 N 이 멈춘다

| 회 | 판정 z [mm] | force_delta_n [N] | tare \|F0\| · rms | 비고 |
|---|---|---|---|---|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |
| 4 | | | | |
| 5 | | | | |
| 6 | | | | |
| 7 | | | | |
| 8 | | | | |
| 9 | | | | |
| 10 | | | | |
| **평균 · σ** | | | | |

- 합격(BRD TR-01): 접촉 검출 하중 **5 N 이하**. 반복성 σ(TR-02 기준 0.3 mm)도 같이 본다
- 예상: 윗면 z ≈ 180.40(units-frames.md, 9/21 새 탐침)

## 4. T25: 네 방향 밀기 · 모서리 검출
방향마다: 안전복귀 → 하강 + tare(3번과 같다) → CONTACT 직후 밀기 → **수직으로 50 mm 올림** → 다음 방향. 방향 코드 `1 +x · 2 −x · 3 +y · 4 −y`.

**밀기가 끝나면 팁은 큐브 밖 · 윗면보다 약간 아래에 있다.** 그래서 안전복귀 전에 `lift`(2번에서 정의)로 먼저 올린다.
```bash
for d in 1 2 3 4; do
  ros2 action send_goal $G $T "{scan_id: 'pm', motion_id: $((200+3*d)), operation: 4}"
  ros2 action send_goal $G $T "{scan_id: 'pm', motion_id: $((201+3*d)), operation: 2, speed: 0.003, max_distance: 0.113}" &
  sleep 8; ros2 service call /contact/tare contact_scan_interfaces/srv/TareForce "{duration_s: 0.0}"
  wait
  ros2 action send_goal $G $T "{scan_id: 'pm', motion_id: $((202+3*d)), operation: 3, direction: $d, speed: 0.005, max_distance: 0.06}"
  lift $((250+d)) || break
done
ros2 action send_goal $G $T "{scan_id: 'pm', motion_id: 299, operation: 4}"
```
- robot_manager 로그 `SLIDE 시작: DR_FC_MOD_REL 기준선 Fz=` 값을 적는다(실제 누름 = 기준선 + 3 N, #91 · #105)
- contact_detector 경고 `샘플 공백으로 EDGE 추세선을 버리고` 가 모서리 근처에서 나면 그 방향은 **다시 한다**(9/21 오전 5-12)
- 밀기가 `MAX_DISTANCE`(모서리 못 찾음)로 끝나도 올림은 한다. 올림 뒤에 안전복귀가 나간다

| 방향 | EDGE 판정 좌표 (진행 축) [mm] | z_drop_m | 기준선 Fz [N] | 공백 경고 | 결과 |
|---|---|---|---|---|---|
| +x | | | | | |
| −x | | | | | |
| +y | | | | | |
| −y | | | | | |

계산:
- 가로 = x⁺ − x⁻ = , 세로 = y⁺ − y⁻ = (캘리퍼 80 mm)
- 방향당 편향 `edge_bias_offset_m` = (추정 폭 − 80) ÷ 2 = (geometry_estimator README 규약, #75). **#80 의 2.25 mm 는 무효**(밀린 탐침)라 이 값이 처음 유효한 측정이다
- 큐브 중심 = ((x⁺ + x⁻)/2, (y⁺ + y⁻)/2) → 작업대 원점(423.56, −186.06)과의 차

## 끝
- [ ] 안전복귀 · bag 종료 · 결과를 이 문서에 채운다
- [ ] 1번 결과로 TCP x · y 를 바꿨으면 `units-frames.md` 45행 · `apply_tool_tcp.py` 기본값 PR
- [ ] 4번 편향을 `real.yaml` `edge_bias_offset_m` 에 넣을지(T30) 팀과 정한다

## 관찰 · 다음 조치
-
