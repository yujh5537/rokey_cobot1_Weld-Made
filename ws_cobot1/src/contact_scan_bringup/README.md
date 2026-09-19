# contact_scan_bringup

자체 노드 5개의 launch 와 입력원별 파라미터. 소유: 현지 (T05).

```bash
# 터미널 1 (사람이 띄운다): 두산 드라이버. 이 launch 는 드라이버를 띄우지 않는다
sod && sodvir
# 터미널 2
cd ~/ws_cobot_pjt/ws_cobot1 && source install/setup.bash
ros2 launch contact_scan_bringup bringup.launch.py source:=sim
```

| `source` | 파라미터 파일 | 용도 |
|---|---|---|
| `sim` (기본) | `config/sim.yaml` | Virtual Mode + 가상 직육면체. 개발 · 저녁 통합 · 리허설 |
| `robot_force` | `config/real.yaml` | 실기. **사람이 직접 실행한다** |

- 설치되지 않은 노드 패키지는 건너뛴다. 실행 로그의 `[bringup] ... 건너뜀`으로 확인한다.
- 노드를 추가하는 담당자는 패키지 이름 = 실행 파일 이름 = 노드 이름(계약의 이름)으로 맞춘다. 다르면 `launch/bringup.launch.py`의 `NODES`를 고치는 PR을 현지에게 요청한다.
- 파라미터는 yaml 의 **자기 노드 절**에 추가한다. 수치를 코드에 넣지 않는다(CLAUDE.md 규칙 7).
- 계약 이름(`ros-interfaces.md` 6.4)과 두 노드 공유 값(`over_force_n` · `drop_limit_m`)은 `test/test_config.py`가 검사한다.
- 실기 튜닝 값은 `real.yaml`을 `tune-MMDD-*` 브랜치의 PR로 고친다.
