# P1 ExecutePath → P2 weld_manager Virtual 검증

2026-09-29. 기존 웹/DB 시연 설정을 보존하기 위해 별도 worktree에서 실행했다.

## 코드와 검증 범위

- 통합 브랜치: `p2-virtual-integration`, worktree: `/tmp/weld-made-p1-p2`.
- `origin/p2-weld-manager`에 최신 `origin/p2-robot-execute-path`와 `origin/main`을 병합했다.
- 통합 HEAD: `7957f54` (로컬 커밋, 원격 push 없음).
- P1 실행 중 예외가 나면 정지를 확인한 뒤 공용 모션 슬롯을 해제하도록 보완했다.
  정지 확인이 계속 실패하면 미처리 정지 요청을 유지해 후속 경로를 거절한다.
  독립 코드 재검토에서 발견한 두 경로를 수정하고 회귀 테스트를 추가했다.
- 클린 빌드 8개 패키지 성공. 관련 4개 패키지 테스트 **606개 통과**, 실패 0개.
- Virtual localhost, ROS domain **36**. P4 MQTT·웹 연결은 이번 검증 범위에 없다.

기존 DB 시연의 domain 99, TCP 246.98 mm, 작업대 위치는 그대로 보존했다.
이번 검증은 저장된 표준 fixture `20260921-131938-1493`을 사용한다.
밑면 중심은 `(425, -184, 400) mm`, 크기는 `100 × 60 × 40 mm`다.
새 에뮬레이터 기본 TCP로 실행했으며 웹 탐침 끝 정렬이나 실기 도달성 검증은 아니다.
45° 자세, 위빙 ±2 mm, 반주기 4 mm로 윗면 4선과 세로 4선을 실행한다.

## 현재 파일

- 설치: `/tmp/weld-p1-p2-install`
- 설정: `/tmp/weld-p1-p2-runtime/sim.yaml`
- 자체 노드 launch: `/tmp/weld-p1-p2-runtime/integration.launch.py`
- 검증 스크립트: `/tmp/weld-p1-p2-runtime/verify.py`
- 로그: `/tmp/weld-p1-p2-runtime/{driver,bringup,home,verification}.log`
- 결과: `/tmp/weld-p1-p2-runtime/results/<scan_id>/weld/`
- 요약: `/tmp/weld-p1-p2-runtime/verification.json`

`/tmp` 파일은 재부팅/정리 시 사라질 수 있다. 아래는 재생성 절차다.
동일 PC에서 에뮬레이터를 중복 실행하지 않는다. 기존 프로세스와 실기 launch 유무를
먼저 확인하고, `mode:=real`이 있으면 실행하지 않는다.

## 재빌드

통합 worktree가 없으면 저장된 로컬 브랜치에서 만든다.

```bash
git worktree add /tmp/weld-made-p1-p2 p2-virtual-integration
```

```bash
source /opt/ros/jazzy/setup.bash
source ~/ws_cobot_pjt/ws_dsr/install/setup.bash
cd /tmp/weld-made-p1-p2/ws_cobot1
colcon build --base-paths src --build-base /tmp/weld-p1-p2-build \
  --install-base /tmp/weld-p1-p2-install --symlink-install --parallel-workers 2
```

모든 ROS 터미널 공통 환경:

```bash
source /opt/ros/jazzy/setup.bash
source ~/ws_cobot_pjt/ws_dsr/install/setup.bash
source /tmp/weld-p1-p2-install/setup.bash
export ROS_DOMAIN_ID=36 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
unset ROS_DISCOVERY_SERVER
```

## 설정과 저장 결과 준비

```bash
python3 - <<'PY'
from pathlib import Path
import shutil
import yaml
repo = Path('/tmp/weld-made-p1-p2')
runtime = Path('/tmp/weld-p1-p2-runtime')
result = runtime / 'results/20260921-131938-1493'
result.mkdir(parents=True, exist_ok=True)
shutil.copy(repo / 'docs/phase2/fixtures/sim_20260921-131938-1493.result.json', result / 'result.json')
config = yaml.safe_load((repo / 'ws_cobot1/src/contact_scan_bringup/config/sim.yaml').read_text())
for name in ('scan_manager', 'weld_manager'):
    config[name]['ros__parameters']['result_dir'] = str(runtime / 'results')
(runtime / 'sim.yaml').write_text(yaml.safe_dump(config, sort_keys=False))
(runtime / 'integration.launch.py').write_text('''from launch import LaunchDescription
from launch_ros.actions import Node
def generate_launch_description():
    return LaunchDescription([
        Node(package=name, executable=name, name=name, output='screen',
             parameters=['/tmp/weld-p1-p2-runtime/sim.yaml'])
        for name in ('robot_manager', 'contact_detector', 'safety_monitor',
                     'scan_manager', 'weld_manager')
    ])
''')
PY
```

## 실행

공통 환경을 적용한 별도 터미널에서 각각 실행한다. 에뮬레이터와 드라이버 서비스가
준비된 뒤 자체 노드를 시작한다. 기존 DB 시연용 TCP 등록 절차를 섞지 않는다.

```bash
ros2 launch m0609_rg2_bringup bringup.launch.py mode:=virtual host:=127.0.0.1 port:=12345 model:=m0609
```

```bash
ros2 launch /tmp/weld-p1-p2-runtime/integration.launch.py
```

새 에뮬레이터는 영점 특이 자세이므로 관절 홈부터 실행한다.

```bash
ros2 action send_goal /robot/execute_motion contact_scan_interfaces/action/ExecuteMotion \
  "{scan_id: 'p1-p2-bootstrap', motion_id: 900001, operation: 4, target: {orientation: {w: 1.0}}, frame_id: 'base_link', timeout: {sec: 30}}"
```

홈 `SUCCEEDED`와 `reason_code=0`, 유효한 `/robot/sample`, 안전 상태 `latched=false`를
확인한 뒤 P2 8선을 실행한다. P2는 내부에서 P1 ExecutePath를 호출한다.

```bash
ros2 action send_goal /weld/run contact_scan_interfaces/action/RunWeld \
  "{request_id: 'p2-virtual-check', scan_id: '20260921-131938-1493', start_line: 0, end_line: 7}" --feedback
```

완료 기준은 action `SUCCEEDED`, `success=true`, `reason_code=0`, 결과의 8개 선 모두
`DONE`이다. 실패하면 로그와 저장 결과를 확인하고 안전 차단을 우회하지 않는다.
종료할 때는 자체 노드와 드라이버 터미널을 Ctrl+C로 종료한다.

## 실행 결과

- P1: 한 goal의 경유점 **21/21 완료**, `reason_code=0`.
- P2 weld ID: `20260929-023312-1710`, `success=true`, `reason_code=0`.
- **L0~L7 모두 DONE(8/8)**, 마무리 홈 복귀 후 `PHASE_DONE` 확인.
- 실행 중 `OP_WELD_PATH` 샘플 10,076개 수신(P1 단독 시험 포함).
- [결과 요약](verification/p1-p2-20260929/verification.json),
  [실행 로그](verification/p1-p2-20260929/verification.log),
  [자동 테스트 결과](verification/p1-p2-20260929/tests.log).
- 최종 예외 정지 실패 보완은 자동 테스트와 독립 코드 리뷰로 검증했다.
  정상 모션 실행 중 오류를 강제로 주입하지 않았다.
- 기존 DB 배치에서의 L1·L5 도달성 및 실제 탐침 외형 간섭은 이 실행으로 검증되지 않는다.
- 검증 완료 후 자체 노드·가상 드라이버를 종료했다.

## P4 후속 검증 (2026-09-29)

P4 브리지를 같은 통합 브랜치 `b4e780c`에 추가했다. Virtual에서
`POST /commands/weld/start`(L0) → `cmd/ack.accepted=true` →
`weld/result.lines[0].status=DONE` → `weld/command_result.success=true` →
`GET /commands/<request_id>.status=SUCCEEDED`를 확인했다.
[검증 JSON](verification/p1-p2-p4-20260929/verification.json),
[실행 로그](verification/p1-p2-p4-20260929/verification.log).
새 Virtual 세션에서 `/commands/weld/home` 성공과 이동 중 `/commands/weld/stop`의
`STOPPED` 완료도 확인했다([중지 기록](verification/p1-p2-p4-20260929/stop.log),
[안전복귀 로그](verification/p1-p2-p4-20260929/home.log)).
브리지 테스트 46개, FastAPI 테스트 9개가 통과했다.
실기 명령 순서는 [실기 용접 모션 Runbook](../../docs/runbooks/real-weld-motion.md)에 적었다.
