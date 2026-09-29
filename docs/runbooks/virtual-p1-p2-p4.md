# Virtual M0609: P1 → P2 → P4 용접 모션 재실행

2026-09-29에 로컬 에뮬레이터에서 실행한 절차다. 기준 코드는
`p2-virtual-integration` **`b4e780c`**이고, ROS 2 Jazzy · DRCF Virtual ·
`ROS_DOMAIN_ID=36` · localhost discovery를 사용한다. 실행 결과는
[P1/P2 기록](../../scripts/sim/p1-p2-run.md)과
[P4 기록](../../scripts/sim/verification/p1-p2-p4-20260929/verification.json)에 남아 있다.

이 실행은 **저장된 표준 fixture** `20260921-131938-1493`을 사용한다. 부재 밑면
중심 `(425, -184, 400) mm`, 크기 `100 × 60 × 40 mm`, 위빙 ±2 mm · 반주기
4 mm · 기울기 45°다. 기존 DB 웹 시연의 scan ID `20260923-171647-5890`,
작업대 `(420.255, -156.675, 95.006) mm`, Virtual 화면용 TCP `246.98 mm`,
ROS domain 99와는 다른 배치다. **이 절차에서는 TCP를 재등록하지 않는다.**
P2의 `sim.yaml` 툴 외형 배열도 코드 경로 확인용 값이며 실측값이 아니다.

## 0. 실행 범위와 기존 프로세스 확인

기본 경로는 이 PC의 레포와 별도 worktree다. 아래 명령은 모두 **Virtual localhost**에서만
실행한다. `mode:=real` 드라이버가 보이면 실행하지 않는다. 이미 실행 중인
`dsr01_emulator`가 있으면 중복으로 띄우지 않고 그 실행의 소유자와 용도를 확인한다.

```bash
cd ~/collaboration/rokey_cobot1_Weld-Made
ps -eo pid,args | rg '[r]os2 launch .*mode:=real|[s]odreal' || true
docker ps --filter name=dsr01_emulator --format '{{.Names}} {{.Status}}'
git worktree list
```

`/tmp/weld-made-p1-p2`가 이미 있으면 HEAD만 확인한다.

```bash
git -C /tmp/weld-made-p1-p2 log -1 --oneline
# b4e780c feat(bridge): route weld commands and telemetry through MQTT
```

worktree가 없다면 로컬 `p2-virtual-integration` 브랜치에서 만든다. 브랜치도
없을 때만 [`p1-p2-p4-integration.bundle`](../../scripts/sim/p1-p2-p4-integration.bundle)을
가져온다. 기존 수정 사항을 reset/clean하지 않는다.

```bash
cd ~/collaboration/rokey_cobot1_Weld-Made
# 브랜치가 없을 때만:
git bundle verify scripts/sim/p1-p2-p4-integration.bundle
git fetch scripts/sim/p1-p2-p4-integration.bundle refs/heads/p2-virtual-integration
git branch p2-virtual-integration FETCH_HEAD
# worktree가 없을 때만:
git worktree add /tmp/weld-made-p1-p2 p2-virtual-integration
git -C /tmp/weld-made-p1-p2 log -1 --oneline
```

## 1. ROS 빌드와 시험

```bash
source /opt/ros/jazzy/setup.bash
source ~/ws_cobot_pjt/ws_dsr/install/setup.bash
cd /tmp/weld-made-p1-p2/ws_cobot1
colcon build --base-paths src \
  --build-base /tmp/weld-p1-p2-build \
  --install-base /tmp/weld-p1-p2-install \
  --symlink-install --parallel-workers 2
source /tmp/weld-p1-p2-install/setup.bash
colcon test --build-base /tmp/weld-p1-p2-build \
  --install-base /tmp/weld-p1-p2-install \
  --packages-select robot_manager weld_manager mqtt_bridge contact_scan_bringup
colcon test-result --test-result-base /tmp/weld-p1-p2-build --verbose
```

어제 클린 빌드는 8개 패키지 성공, P1/P2 관련 테스트 606개 통과,
브리지 테스트 46개와 FastAPI 테스트 9개 통과였다. 이번 실행의 결과도 위 명령으로 확인한다.

이후 **모든 ROS 터미널**에서 같은 환경을 적용한다.

```bash
source /opt/ros/jazzy/setup.bash
source ~/ws_cobot_pjt/ws_dsr/install/setup.bash
source /tmp/weld-p1-p2-install/setup.bash
export ROS_DOMAIN_ID=36
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
unset ROS_DISCOVERY_SERVER
```

## 2. fixture·설정·launch 생성

`/tmp` 파일이 사라져도 다시 만들 수 있도록 표준 결과와 별도 설정을 생성한다.
`scan_manager`와 `weld_manager`는 같은 `result_dir`을 사용한다. 여기서는
P4 브로커를 localhost `1883`으로 지정한다.

```bash
python3 - <<'PY'
from pathlib import Path
import shutil
import yaml
repo = Path('/tmp/weld-made-p1-p2')
runtime = Path('/tmp/weld-p1-p2-runtime')
result = runtime / 'results/20260921-131938-1493'
result.mkdir(parents=True, exist_ok=True)
shutil.copy(repo / 'docs/phase2/fixtures/sim_20260921-131938-1493.result.json',
            result / 'result.json')
config = yaml.safe_load(
    (repo / 'ws_cobot1/src/contact_scan_bringup/config/sim.yaml').read_text())
for name in ('scan_manager', 'weld_manager'):
    config[name]['ros__parameters']['result_dir'] = str(runtime / 'results')
config['mqtt_bridge'] = {'ros__parameters': {
    'broker_host': '127.0.0.1', 'broker_port': 1883}}
(runtime / 'sim.yaml').write_text(yaml.safe_dump(config, sort_keys=False))
(runtime / 'integration.launch.py').write_text('''from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(package=name, executable=name, name=name, output='screen',
             parameters=['/tmp/weld-p1-p2-runtime/sim.yaml'])
        for name in ('robot_manager', 'contact_detector', 'safety_monitor',
                     'scan_manager', 'weld_manager', 'mqtt_bridge')
    ])
''')
print(result / 'result.json')
print(runtime / 'sim.yaml')
PY
```

## 3. Mosquitto와 별도 FastAPI 실행

기존 Docker 백엔드가 있어도 시험 API는 **8001번 포트의 별도 컨테이너**로 띄운다.
Mosquitto가 이미 `1883`에서 실행 중이면 첫 `docker compose up`은 건너뛴다.

```bash
cd /tmp/weld-made-p1-p2/docker
[ -f .env ] || cp .env.example .env
docker compose up -d mosquitto
nc -vz 127.0.0.1 1883
```

다음 명령으로 통합 worktree의 FastAPI 코드를 별도 실행한다. 이 API는 저장된
fixture로 용접을 요청하므로 PostgreSQL 서비스가 필요하지 않다.

```bash
docker build -t weld-p4-api-virtual /tmp/weld-made-p1-p2/backend/app
docker run -d --rm --name weld_p4_api_check --network host \
  -e MQTT_HOST=127.0.0.1 -e MQTT_PORT=1883 \
  -v /tmp/weld-made-p1-p2/backend/app:/app:ro \
  weld-p4-api-virtual \
  uvicorn main:app --host 127.0.0.1 --port 8001
curl -sS http://127.0.0.1:8001/health
```

MQTT는 별도 터미널에서 관찰한다.

```bash
mosquitto_sub -h 127.0.0.1 -p 1883 -v \
  -t 'cmd/ack' -t 'robot/status' -t 'weld/state' \
  -t 'weld/result' -t 'weld/log' -t 'weld/command_result'
```

## 4. Virtual 드라이버 → 자체 노드 → 관절 홈

**터미널 A**에서 Virtual 드라이버를 시작한다. `mode:=virtual`과
`host:=127.0.0.1`을 확인한다.

```bash
ros2 launch m0609_rg2_bringup bringup.launch.py \
  mode:=virtual host:=127.0.0.1 port:=12345 model:=m0609
```

다른 ROS 터미널에서 준비를 확인한다.

```bash
docker inspect -f '{{.State.Running}} {{.Name}}' dsr01_emulator
ros2 service list | rg '/dsr01/dsr_controller2/system/set_robot_mode'
```

**터미널 B**에서 자체 노드 6개를 띄운다.

```bash
ros2 launch /tmp/weld-p1-p2-runtime/integration.launch.py
```

에뮬레이터는 모든 관절 0°의 특이 자세에서 시작한다. **터미널 C**에서 관절 홈을
한 번 실행하고 `SUCCEEDED` 및 `reason_code: 0`을 확인한다.

```bash
ros2 action send_goal /robot/execute_motion \
  contact_scan_interfaces/action/ExecuteMotion \
  "{scan_id: 'p1-p2-p4-bootstrap', motion_id: 900001, operation: 4, target: {orientation: {w: 1.0}}, frame_id: 'base_link', timeout: {sec: 30}}"
```

```bash
ros2 node list | rg 'robot_manager|contact_detector|safety_monitor|scan_manager|weld_manager|mqtt_bridge'
ros2 topic echo /robot/sample --once
ros2 topic echo /safety/status --once
ros2 topic echo /weld/state --once
```

`/robot/sample.valid=true`, 안전 상태 `latched=false`, 로봇 `connected=true`를 확인한
뒤 다음 명령을 실행한다.

## 5. P1 ExecutePath: 공중 지그재그 21점

이 단계는 홈 위치의 현재 TCP 자세를 읽어 **같은 높이의 공중**에서 x 40 mm,
y ±2 mm 지그재그를 한 goal로 보낸다. P2도 내부에서 ExecutePath를 사용하지만,
P1을 직접 확인하려면 다음을 실행한다. 앞 절의 Virtual·안전 상태 확인 뒤에만
실행한다.

```bash
python3 - <<'PY'
from copy import deepcopy
import time
import rclpy
from rclpy.action import ActionClient
from rclpy.qos import qos_profile_sensor_data
from contact_scan_interfaces.action import ExecutePath
from contact_scan_interfaces.msg import RobotSample

rclpy.init()
node = rclpy.create_node('p1_virtual_check')
seen = {'sample': None}
node.create_subscription(RobotSample, '/robot/sample',
    lambda msg: seen.update(sample=msg), qos_profile_sensor_data)
end = time.monotonic() + 10
while time.monotonic() < end:
    rclpy.spin_once(node, timeout_sec=.2)
    if seen['sample'] is not None and seen['sample'].valid:
        break
else:
    raise RuntimeError('유효한 /robot/sample 없음')

goal = ExecutePath.Goal()
goal.weld_id = 'p1-virtual-check'
goal.motion_id = 1
goal.frame_id = 'base_link'
goal.speed = .01
goal.path_tolerance_m = .003
goal.timeout.sec = 90
for i in range(21):
    pose = deepcopy(seen['sample'].pose)
    pose.position.x += i * .002
    pose.position.y += 0 if i in (0, 20) else (.002 if i % 2 else -.002)
    goal.waypoints.append(pose)
client = ActionClient(node, ExecutePath, '/robot/execute_path')
assert client.wait_for_server(timeout_sec=10)
sent = client.send_goal_async(goal)
rclpy.spin_until_future_complete(node, sent, timeout_sec=10)
handle = sent.result()
assert handle and handle.accepted
finished = handle.get_result_async()
rclpy.spin_until_future_complete(node, finished, timeout_sec=100)
assert finished.done(), 'ExecutePath timeout: 로봇 상태를 확인할 것'
result = finished.result().result
print('reason_code:', result.reason_code, 'waypoints_done:', result.waypoints_done)
assert result.reason_code == 0 and result.waypoints_done == 21
node.destroy_node()
rclpy.shutdown()
PY
```

정상 결과는 `reason_code: 0`, `waypoints_done: 21`이다.

## 6. P2 weld_manager: 윗면 4선 + 세로 4선

표준 fixture의 8선을 한 번에 실행한다. 기본 sim 설정은 45°·위빙 ±2 mm·
반주기 4 mm다. 어제 완료까지 약 수 분 걸렸다. `RUN_WELD`가 끝난 뒤
`result.success=true`와 선별 8개 `DONE`을 확인한다.

```bash
ros2 action send_goal /weld/run contact_scan_interfaces/action/RunWeld \
  "{request_id: 'p2-virtual-8-lines', scan_id: '20260921-131938-1493', start_line: 0, end_line: 7}" --feedback
```

```bash
ls -lt /tmp/weld-p1-p2-runtime/results/20260921-131938-1493/weld/
ros2 topic echo /weld/state --once
```

`/weld/state.phase=DONE`, 결과 파일의 `success=true`, L0~L7 모두 `DONE`이어야 한다.
이 표준 배치의 성공은 기존 DB 배치의 L1·L5 도달성이나 실기 탐침 간섭을 증명하지
않는다.

## 7. P4: 웹 API → MQTT → ROS → 결과

P2가 끝나 홈으로 복귀하고 안전 상태가 정상일 때 **L0 한 선**을 Web API로 보낸다.
다음 API는 위에서 띄운 별도 FastAPI `8001`을 사용한다. 현재 웹의
**용접 시작** 버튼은 `/sim-weld` 시연 경로이므로 P4 확인에는 이 API를 쓴다.

```bash
WEB=http://127.0.0.1:8001
WELD_REPLY=$(curl -sS -X POST "$WEB/commands/weld/start" \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"p4-virtual","payload":{"scan_id":"20260921-131938-1493","start_line":0,"end_line":0}}')
printf '%s\n' "$WELD_REPLY" | python3 -m json.tool
WELD_REQUEST_ID=$(printf '%s' "$WELD_REPLY" | \
  python3 -c 'import json,sys; print(json.load(sys.stdin)["request_id"])')
```

MQTT 모니터에 `cmd/ack.accepted=true`, `weld/state`의 PREPARING→…→DONE,
`weld/result.lines[0].status=DONE`, `weld/command_result.success=true`가 나온다.
마지막에 API도 확인한다.

```bash
curl -sS "$WEB/commands/$WELD_REQUEST_ID" | python3 -m json.tool
```

정상 상태는 `status=SUCCEEDED`다. 실제 검증 ID는
`85f23c39-213f-49ef-9f2f-b32e4797fb89`, weld ID는
`20260929-024702-0837`이었다.

### 중지·안전복귀 확인

중지 확인 시에는 **새** L0 요청을 보낸다. MQTT 모니터에서 이 요청의
`weld/state.phase=WELDING`을 본 다음 stop을 보낸다.

```bash
STOP_TEST_REPLY=$(curl -sS -X POST "$WEB/commands/weld/start" \
  -H 'Content-Type: application/json' \
  -d '{"payload":{"scan_id":"20260921-131938-1493","start_line":0,"end_line":0}}')
printf '%s\n' "$STOP_TEST_REPLY" | python3 -m json.tool
# 새 weld ID의 WELDING 상태를 확인한 뒤:
STOP_REPLY=$(curl -sS -X POST "$WEB/commands/weld/stop" \
  -H 'Content-Type: application/json' -d '{"payload":{}}')
STOP_REQUEST_ID=$(printf '%s' "$STOP_REPLY" | \
  python3 -c 'import json,sys; print(json.load(sys.stdin)["request_id"])')
curl -sS "$WEB/commands/$STOP_REQUEST_ID" | python3 -m json.tool
```

`STOPPING → STOPPED`, stop 요청의 `status=SUCCEEDED`, `reason_code=200`을
확인한다. 중지는 홈 복귀를 자동으로 실행하지 않는다. 로봇이 멈춘 뒤 필요할 때만
별도로 안전복귀를 요청한다.

```bash
HOME_REPLY=$(curl -sS -X POST "$WEB/commands/weld/home" \
  -H 'Content-Type: application/json' -d '{"payload":{}}')
HOME_REQUEST_ID=$(printf '%s' "$HOME_REPLY" | \
  python3 -c 'import json,sys; print(json.load(sys.stdin)["request_id"])')
curl -sS "$WEB/commands/$HOME_REQUEST_ID" | python3 -m json.tool
```

각 GET을 모션 종료 뒤 다시 조회해 최종 상태를 확인한다. 어제 새 Virtual 세션에서
이동 중 stop의 `STOPPED`와 home의 `SUCCEEDED`를 확인했다.

## 8. 종료

이 문서로 시작한 프로세스만 종료한다. P1/P2/P4 자체 노드 터미널, Virtual
드라이버 터미널 순서로 Ctrl+C를 누른다. 그 뒤 이 문서로 띄운 별도 API만 종료한다.

```bash
docker stop weld_p4_api_check
```

드라이버 종료 후에도 **이번 실행의** `dsr01_emulator`가 남아 있을 때만 정리한다.
기존 Mosquitto를 쓰고 있었다면 그대로 둔다.

```bash
docker ps --filter name=dsr01_emulator --format '{{.Names}} {{.Status}}'
docker rm -f dsr01_emulator
```

## 9. 빠른 문제 확인

- 드라이버를 띄우기 전 `mode:=real`이 보이면 이 절차를 멈춘다.
- 첫 이동에서 DRCF `2/3509`가 나면 4절 관절 홈 성공 여부를 확인한다.
- 시작이 `NO_SCAN_RESULT(602)`이면 fixture 경로와 `scan_manager`·`weld_manager`
  `result_dir`이 같은지 확인한다.
- 웹 요청이 `NOT_SUPPORTED`이면 `weld_manager`, `mqtt_bridge`, 브로커와 8001 API
  실행 상태를 확인한다.
- `SAMPLE_STALE(403)` 또는 `ROBOT_DISCONNECTED(104)`면 이동 요청을 반복하지
  않는다. 드라이버와 `/robot/sample`을 확인한다. 어제 오래 켜둔 에뮬레이터가
  끊겨 home 요청이 104로 실패했고, 새 Virtual 세션에서 home을 다시 성공시켰다.
- DB 웹 시연의 표면/탐침 정렬이 필요하면 이 절차의 fixture와 TCP를 섞지 말고
  [DB 시연 Runbook](../../scripts/sim/README.md)을 따른다.
