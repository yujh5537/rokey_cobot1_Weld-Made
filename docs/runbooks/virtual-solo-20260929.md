# Virtual M0609 + RViz2 + 웹 P1/P2/P4 단독 실행

기준 코드: 로컬 `weld-web-main-p4` 브랜치의 `4a6efe1`. 이 문서는 실기 팀과 동시에 켜도 섞이지 않도록 Virtual ROS domain `166`, localhost MQTT `1884`, API `8001`, 웹 `5174`를 사용한다. 모든 로봇 명령은 `mode:=virtual host:=127.0.0.1` 드라이버에만 보낸다. 팀 실기용 MQTT `1883`과 웹 `5173`은 사용하지 않는다.

저장된 scan ID `20260921-131938-1493`을 불러온다. 작업대와 부재 밑면은 World Z `400 mm`, M0609 베이스는 World Z `306 mm`, ROS Base 기준 부재 밑면은 `94 mm`다. Virtual TCP `246.98 mm`는 웹 정렬용이다.

## 1. 재부팅 후 코드와 실행 파일 준비

원격 `origin/weld-web-main-p4`를 별도 영구 경로에 받는다. 이미 받은 경우에는 `git -C "$SIM_REPO" pull --ff-only`로 갱신한다. 실행 중인 다른 브랜치의 작업 폴더는 바꾸지 않는다.

```bash
SIM_REPO=/home/runo/collaboration/rokey_cobot1_Weld-Made-weld-p4
git clone --branch weld-web-main-p4 --single-branch \
  https://github.com/yujh5537/rokey_cobot1_Weld-Made.git "$SIM_REPO"
SIM_RUNTIME=/tmp/weld-web-aligned-runtime
SIM_INSTALL=/tmp/weld-web-main-install
```

각 새 터미널에서 `SIM_REPO`, `SIM_RUNTIME`, `SIM_INSTALL`을 다시 설정한다.

ROS 빌드와 웹 의존성 설치:

```bash
source /opt/ros/jazzy/setup.bash
source /home/runo/ws_cobot_pjt/ws_dsr/install/setup.bash
cd "$SIM_REPO/ws_cobot1"
colcon build --base-paths src --build-base /tmp/weld-web-main-build \
  --install-base "$SIM_INSTALL" --symlink-install --parallel-workers 2
cd "$SIM_REPO/frontend"
npm ci
```

이후 모든 ROS 터미널에 다음 환경을 적용한다.

```bash
source /opt/ros/jazzy/setup.bash
source /home/runo/ws_cobot_pjt/ws_dsr/install/setup.bash
source /tmp/weld-web-main-install/setup.bash
export ROS_DOMAIN_ID=166 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
unset ROS_DISCOVERY_SERVER ROS_STATIC_PEERS ROS_LOCALHOST_ONLY
```

## 2. 전용 MQTT와 API

별도 터미널에서 Mosquitto를 실행하고 켜 둔다.

```bash
mkdir -p /tmp/weld-web-aligned-runtime
cat > /tmp/weld-web-aligned-runtime/mosquitto.conf <<'CONF'
listener 1884 127.0.0.1
allow_anonymous true
persistence false
CONF
mosquitto -c /tmp/weld-web-aligned-runtime/mosquitto.conf
```

새 터미널에서 전용 API를 실행한다.

```bash
docker build -t weld-p4-api-virtual $SIM_REPO/backend/app
docker run -d --rm --name weld_p4_api_check --network host \
  -e MQTT_HOST=127.0.0.1 -e MQTT_PORT=1884 \
  -v $SIM_REPO/backend/app:/app:ro \
  weld-p4-api-virtual \
  uvicorn main:app --host 127.0.0.1 --port 8001
```

## 3. 부재와 ROS 설정 생성

```bash
cd $SIM_REPO
python3 scripts/sim/prepare_aligned_virtual.py \
  --output /tmp/weld-web-aligned-runtime
```

이 명령이 `sim.yaml`, `integration.launch.py`, 저장된 `result.json`을 만든다. 기존 결과 디렉터리를 지우지 않는다.

## 4. Virtual 드라이버와 TCP

ROS 환경을 적용한 **터미널 A**:

```bash
ros2 launch m0609_rg2_bringup bringup.launch.py \
  mode:=virtual host:=127.0.0.1 port:=12345 model:=m0609
```

드라이버 서비스가 올라온 뒤, 자체 노드를 띄우기 **전에** 다른 ROS 터미널에서 TCP를 등록한다.

```bash
cd $SIM_REPO
python3 scripts/sim/apply_virtual_tcp.py \
  --config /tmp/weld-web-aligned-runtime/sim.yaml
```

마지막 줄은 `OK: rg2_probe_tip, TCP−flange=246.98 mm`여야 한다. 이 스크립트는 Virtual 드라이버·에뮬레이터를 확인하고 로컬 실기 드라이버가 있으면 거절한다.

## 5. P1/P2/P4 ROS 노드와 초기 관절 홈

ROS 환경을 적용한 **터미널 B**:

```bash
ros2 launch /tmp/weld-web-aligned-runtime/integration.launch.py
```

`robot_manager`, `contact_detector`, `safety_monitor`, `scan_manager`, `weld_manager`, `mqtt_bridge`가 실행된다. 에뮬레이터는 관절 0°의 특이 자세로 시작하므로, **웹 안전 위치나 시작 버튼보다 관절 홈을 먼저** 실행한다. ROS 환경을 적용한 **터미널 C**:

```bash
ros2 topic echo /robot/status --once
ros2 topic echo /safety/status --once
ros2 action send_goal /robot/execute_motion \
  contact_scan_interfaces/action/ExecuteMotion \
  "{scan_id: 'virtual-bootstrap', motion_id: 900001, operation: 4, target: {orientation: {w: 1.0}}, frame_id: 'base_link', timeout: {sec: 45}}"
```

연결 상태 `connected: true`, 안전 래치 `latched: false`, 홈 액션 `SUCCEEDED`와 `reason_code: 0`을 확인해야 웹에서 모션을 시작할 수 있다.

## 6. RViz2와 웹

드라이버가 기본 RViz 창을 자동으로 띄웠다면 그 창을 닫고, ROS 환경을 적용한 별도 터미널에서 프로젝트 장면을 실행한다.

```bash
python3 $SIM_REPO/scripts/sim/markers.py \
  --config /tmp/weld-web-aligned-runtime/sim.yaml
```

```bash
rviz2 -d $SIM_REPO/scripts/sim/db_sim.rviz
```

웹 터미널:

```bash
cd $SIM_REPO/frontend
VITE_API_TARGET=http://127.0.0.1:8001 \
VITE_SIM_FIXTURE_URL=/fixtures/standard-20260921-aligned.json \
VITE_FIXTURE_ORIGIN_WORLD_MM=425,-184,400 \
VITE_TABLE_ORIGIN_MM=425,-184,400 \
npm run dev -- --host 127.0.0.1 --port 5174 --strictPort
```

브라우저 주소: **http://127.0.0.1:5174**. 홈 성공 후 웹 **용접 시작**을 한 번 누르면 `API 8001 → MQTT 1884 → mqtt_bridge → weld_manager → ExecutePath` 순서로 동작한다. 버튼을 눌렀다면 같은 용접을 ROS 액션으로 중복 요청하지 않는다. **용접 중지**는 자동 홈 복귀를 하지 않는다.

이 부재 배치의 과거 8선 실행에서는 L1·L5가 도달성 문제로, L7이 경로 오차로 실패했다. 8선 전체 성공을 완료 조건으로 간주하지 않는다. 결과 JSON은 `/tmp/weld-web-aligned-runtime/results/20260921-131938-1493/weld/`에 기록된다.

## 7. 종료

모션이 멈춘 뒤 웹 → 프로젝트 RViz·마커 → 자체 ROS 노드 → Virtual 드라이버 터미널 순으로 Ctrl+C를 누른다. 마지막에 이 실행의 API와 MQTT 터미널만 종료한다.

```bash
docker stop weld_p4_api_check
```

팀 실기용 프로세스와 Docker 서비스는 종료하지 않는다.

## 2026-09-29 재부팅 후 실행 기록

`/tmp/weld-web-p4-fresh`에 로컬 `weld-web-main-p4`를 복원하고 ROS 8개 패키지 빌드, 웹 의존성 설치, 전용 Mosquitto/API, Virtual 드라이버, TCP 등록, 자체 ROS 노드 6개, 프로젝트 RViz2·마커, 웹을 실행했다. TCP 등록은 `246.98 mm`로 성공했다. 기동 직후 운영체제 네트워크 인터페이스 조회가 잠시 `rtnl_dumpit`에서 대기했지만 풀렸다. `/robot/sample.valid=true`, `/safety/status.latched=false`를 확인한 뒤 초기 관절 홈 액션 `motion_id=900002`가 `SUCCEEDED`, `reason_code=0`으로 완료됐다. `http://127.0.0.1:5174`에서 웹이 응답한다. 모션 중 robot_manager 서비스 큐 충돌을 막는 기존 수정을 로컬 커밋 `4a6efe1`로 복원하고 자체 노드만 재시작했다. 시뮬레이션 프로세스는 실행한 상태로 남겼고, 웹 용접 버튼은 누르지 않았다.
