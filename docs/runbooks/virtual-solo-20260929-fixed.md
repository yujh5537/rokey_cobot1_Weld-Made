# Virtual M0609 + RViz2 + 웹 P1/P2/P4 단독 실행

기준 브랜치: `weld-web-main-p4`

이 실행은 실기 환경과 섞이지 않도록 아래 전용 값을 사용한다.

```text
ROS_DOMAIN_ID = 166
MQTT          = 127.0.0.1:1884
FastAPI       = 127.0.0.1:8001
Frontend      = 127.0.0.1:5174
Virtual DRCF  = 127.0.0.1:12345
```

> 중요: 현재 `scripts/sim/prepare_aligned_virtual.py`가 생성하는 `sim.yaml`의 `mqtt_bridge.broker_port`가 `1883`으로 들어가므로, 생성 직후 반드시 `1884`로 수정한다.  
> 이 수정이 빠지면 `/dsr01/joint_states → mqtt_bridge → robot/joints`가 실기용 MQTT `1883`으로 나가고, Virtual FastAPI는 `1884`를 보고 있어서 웹에서 M0609 관절을 수신하지 못한다.

---

## 1. 전체 실행 순서

```text
P0 weld-web-main-p4 동기화
→ P0 ROS 8패키지 build + frontend npm ci
→ P1 전용 MQTT 1884
→ P0 FastAPI 8001
→ P0 Virtual 설정 생성
→ P0 sim.yaml MQTT 포트 1884 수정
→ P2 M0609 Virtual Driver
→ P0 Virtual TCP 등록
→ P3 P1/P2/P4 ROS 노드 6개
→ P4 robot / safety / sample 확인
→ P4 robot/joints MQTT 확인
→ P4 초기 관절 HOME
→ P5 Marker
→ P6 프로젝트 RViz2
→ P7 Frontend 5174
→ 웹 용접 시작
```

---

## 2. P0 — 브랜치 + Build

### P0-1 — 브랜치 동기화

```bash
cd /home/runo/collaboration/rokey_cobot1_Weld-Made

git fetch origin
git switch weld-web-main-p4
git pull --ff-only origin weld-web-main-p4
```

### P0-2 — 공통 경로

```bash
export SIM_REPO=/home/runo/collaboration/rokey_cobot1_Weld-Made
export SIM_RUNTIME=/tmp/weld-web-aligned-runtime
export SIM_INSTALL=/tmp/weld-web-main-install
```

### P0-3 — ROS Build

```bash
source /opt/ros/jazzy/setup.bash
source /home/runo/ws_cobot_pjt/ws_dsr/install/setup.bash

cd "$SIM_REPO/ws_cobot1"

colcon build \
  --base-paths src \
  --build-base /tmp/weld-web-main-build \
  --install-base "$SIM_INSTALL" \
  --symlink-install \
  --parallel-workers 2
```

정상 기준:

```text
Summary: 8 packages finished
```

### P0-4 — Frontend 의존성

```bash
cd "$SIM_REPO/frontend"
npm ci
```

---

## 3. P1 — 전용 MQTT 1884

**새 터미널 P1. 계속 켜 둔다.**

```bash
mkdir -p /tmp/weld-web-aligned-runtime

cat > /tmp/weld-web-aligned-runtime/mosquitto.conf <<'CONF'
listener 1884 127.0.0.1
allow_anonymous true
persistence false
CONF

mosquitto -c /tmp/weld-web-aligned-runtime/mosquitto.conf
```

정상 기준:

```text
Opening ipv4 listen socket on port 1884.
mosquitto version 2.0.18 running
```

---

## 4. P0 — FastAPI 8001

기존 **P0 터미널**에서 실행한다.

```bash
export SIM_REPO=/home/runo/collaboration/rokey_cobot1_Weld-Made
```

```bash
docker build -t weld-p4-api-virtual "$SIM_REPO/backend/app"
```

```bash
docker run -d --rm \
  --name weld_p4_api_check \
  --network host \
  -e MQTT_HOST=127.0.0.1 \
  -e MQTT_PORT=1884 \
  -v "$SIM_REPO/backend/app:/app:ro" \
  weld-p4-api-virtual \
  uvicorn main:app --host 127.0.0.1 --port 8001
```

확인:

```bash
docker logs --tail 20 weld_p4_api_check
```

정상 기준:

```text
Application startup complete.
Uvicorn running on http://127.0.0.1:8001
```

---

## 5. P0 — Virtual 설정 생성 + MQTT 포트 수정

같은 **P0 터미널**에서 실행한다.

```bash
export SIM_REPO=/home/runo/collaboration/rokey_cobot1_Weld-Made
export SIM_RUNTIME=/tmp/weld-web-aligned-runtime

cd "$SIM_REPO"

python3 scripts/sim/prepare_aligned_virtual.py \
  --output "$SIM_RUNTIME"
```

정상 기준:

```text
base world z=0.306 m; fixture Base z=0.094 m
/tmp/weld-web-aligned-runtime/results/20260921-131938-1493/result.json
```

### 반드시 MQTT 1884로 수정

```bash
sed -i 's/broker_port: 1883/broker_port: 1884/' \
  "$SIM_RUNTIME/sim.yaml"
```

확인:

```bash
grep -A3 '^mqtt_bridge:' "$SIM_RUNTIME/sim.yaml"
```

정상 기준:

```text
mqtt_bridge:
  ros__parameters:
    broker_host: 127.0.0.1
    broker_port: 1884
```

---

## 6. P2 — M0609 Virtual Driver

**새 터미널 P2. 계속 켜 둔다.**

```bash
source /opt/ros/jazzy/setup.bash
source /home/runo/ws_cobot_pjt/ws_dsr/install/setup.bash
source /tmp/weld-web-main-install/setup.bash

export ROS_DOMAIN_ID=166
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
unset ROS_DISCOVERY_SERVER ROS_STATIC_PEERS ROS_LOCALHOST_ONLY
```

```bash
ros2 launch m0609_rg2_bringup bringup.launch.py \
  mode:=virtual \
  host:=127.0.0.1 \
  port:=12345 \
  model:=m0609
```

정상 기준:

```text
mode : virtual
host : 127.0.0.1
port : 12345
Connected to DRCF
STATE_STANDBY
Emulator Mode
Configured and activated dsr_controller2
```

P2는 계속 켜 둔다.

---

## 7. P0 — Virtual TCP 등록

**P2가 정상 기동된 뒤** P0에서 실행한다.

```bash
export SIM_REPO=/home/runo/collaboration/rokey_cobot1_Weld-Made
export SIM_RUNTIME=/tmp/weld-web-aligned-runtime

source /opt/ros/jazzy/setup.bash
source /home/runo/ws_cobot_pjt/ws_dsr/install/setup.bash
source /tmp/weld-web-main-install/setup.bash

export ROS_DOMAIN_ID=166
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
unset ROS_DISCOVERY_SERVER ROS_STATIC_PEERS ROS_LOCALHOST_ONLY

cd "$SIM_REPO"

python3 scripts/sim/apply_virtual_tcp.py \
  --config "$SIM_RUNTIME/sim.yaml"
```

반드시 마지막 줄:

```text
OK: rg2_probe_tip, TCP−flange=246.98 mm
```

`OK`가 아니면 다음 단계로 가지 않는다.

---

## 8. P3 — P1/P2/P4 ROS 노드 6개

**새 터미널 P3. 계속 켜 둔다.**

```bash
source /opt/ros/jazzy/setup.bash
source /home/runo/ws_cobot_pjt/ws_dsr/install/setup.bash
source /tmp/weld-web-main-install/setup.bash

export ROS_DOMAIN_ID=166
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
unset ROS_DISCOVERY_SERVER ROS_STATIC_PEERS ROS_LOCALHOST_ONLY
```

```bash
ros2 launch /tmp/weld-web-aligned-runtime/integration.launch.py
```

기동 대상:

```text
robot_manager
contact_detector
safety_monitor
scan_manager
weld_manager
mqtt_bridge
```

P3는 계속 켜 둔다.

---

## 9. P4 — START 전 확인 + 초기 HOME

**새 터미널 P4.**

```bash
source /opt/ros/jazzy/setup.bash
source /home/runo/ws_cobot_pjt/ws_dsr/install/setup.bash
source /tmp/weld-web-main-install/setup.bash

export ROS_DOMAIN_ID=166
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
unset ROS_DISCOVERY_SERVER ROS_STATIC_PEERS ROS_LOCALHOST_ONLY
```

### P4-1 — Robot

```bash
ros2 topic echo /robot/status --once
```

필수:

```text
connected: true
```

### P4-2 — Safety

```bash
ros2 topic echo /safety/status --once
```

필수:

```text
latched: false
```

### P4-3 — Robot Sample

```bash
ros2 topic echo /robot/sample --once
```

필수:

```text
valid: true
```

### P4-4 — M0609 관절 MQTT 확인

```bash
mosquitto_sub -h 127.0.0.1 -p 1884 \
  -t 'robot/joints' -C 1 -v
```

정상 기준:

```text
robot/joints {"schema_version":"0.1", ... "names":["joint_1","joint_2","joint_3","joint_4","joint_5","joint_6"], ...}
```

관절 데이터 흐름:

```text
/dsr01/joint_states
→ mqtt_bridge
→ MQTT robot/joints :1884
→ FastAPI :8001
→ WebSocket
→ React
→ Three.js M0609 J1~J6
```

### P4-5 — 초기 관절 HOME

위 네 항목이 정상일 때만 실행한다.

```bash
ros2 action send_goal /robot/execute_motion \
  contact_scan_interfaces/action/ExecuteMotion \
  "{scan_id: 'virtual-bootstrap', motion_id: 900001, operation: 4, target: {orientation: {w: 1.0}}, frame_id: 'base_link', timeout: {sec: 45}}"
```

정상 기준:

```text
SUCCEEDED
reason_code: 0
```

웹 안전 위치나 용접 시작보다 **HOME을 먼저 완료한다.**

---

## 10. P5 — Virtual Marker

**새 터미널 P5. 계속 켜 둔다.**

```bash
export SIM_REPO=/home/runo/collaboration/rokey_cobot1_Weld-Made

source /opt/ros/jazzy/setup.bash
source /home/runo/ws_cobot_pjt/ws_dsr/install/setup.bash
source /tmp/weld-web-main-install/setup.bash

export ROS_DOMAIN_ID=166
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
unset ROS_DISCOVERY_SERVER ROS_STATIC_PEERS ROS_LOCALHOST_ONLY
```

```bash
python3 "$SIM_REPO/scripts/sim/markers.py" \
  --config /tmp/weld-web-aligned-runtime/sim.yaml
```

---

## 11. P6 — 프로젝트 RViz2

**새 터미널 P6. 계속 켜 둔다.**

P2에서 기본 RViz가 자동으로 열렸다면 그 창은 닫고 프로젝트 RViz만 실행한다.

```bash
export SIM_REPO=/home/runo/collaboration/rokey_cobot1_Weld-Made

source /opt/ros/jazzy/setup.bash
source /home/runo/ws_cobot_pjt/ws_dsr/install/setup.bash
source /tmp/weld-web-main-install/setup.bash

export ROS_DOMAIN_ID=166
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
unset ROS_DISCOVERY_SERVER ROS_STATIC_PEERS ROS_LOCALHOST_ONLY
```

```bash
rviz2 -d "$SIM_REPO/scripts/sim/db_sim.rviz"
```

---

## 12. P7 — Frontend 5174

**초기 HOME 성공 후 실행한다.**

새 터미널 P7:

```bash
cd /home/runo/collaboration/rokey_cobot1_Weld-Made/frontend

VITE_API_TARGET=http://127.0.0.1:8001 \
VITE_SIM_FIXTURE_URL=/fixtures/standard-20260921-aligned.json \
VITE_FIXTURE_ORIGIN_WORLD_MM=425,-184,400 \
VITE_TABLE_ORIGIN_MM=425,-184,400 \
npm run dev -- --host 127.0.0.1 --port 5174 --strictPort
```

브라우저:

```text
http://127.0.0.1:5174
```

---

## 13. START 전 최종 체크

```text
[ ] P1 Mosquitto 1884 실행 중
[ ] FastAPI 8001 실행 중
[ ] sim.yaml mqtt_bridge broker_port = 1884
[ ] P2 M0609 Virtual Driver 실행 중
[ ] Virtual TCP 246.98 mm OK
[ ] P3 ROS 노드 6개 실행 중
[ ] /robot/status → connected: true
[ ] /safety/status → latched: false
[ ] /robot/sample → valid: true
[ ] MQTT 1884에서 robot/joints 수신
[ ] 초기 HOME → SUCCEEDED
[ ] reason_code: 0
[ ] P5 Marker 실행 중
[ ] P6 프로젝트 RViz 정상
[ ] P7 http://127.0.0.1:5174 접속 정상
[ ] 웹에서 M0609 J1~J6 관절 자세 갱신
```

전부 확인한 뒤 웹에서 **용접 시작**을 한 번만 누른다.

```text
React :5174
→ FastAPI :8001
→ MQTT :1884
→ mqtt_bridge
→ weld_manager
→ ExecutePath
→ robot_manager
→ Virtual M0609
```

웹 버튼을 눌렀다면 같은 용접을 ROS Action으로 중복 요청하지 않는다.

---

## 14. 실행 결과

저장된 scan ID:

```text
20260921-131938-1493
```

결과 위치:

```text
/tmp/weld-web-aligned-runtime/results/20260921-131938-1493/weld/
```

과거 8선 실행에서는:

```text
L1  도달성 문제
L5  도달성 문제
L7  경로 오차
```

가 있었으므로 8선 전체 성공을 완료 조건으로 간주하지 않는다.

---

## 15. 종료 순서

```text
모션 정지 확인
→ P7 Frontend Ctrl+C
→ P6 RViz Ctrl+C
→ P5 Marker Ctrl+C
→ P3 integration.launch.py Ctrl+C
→ P2 Virtual Driver Ctrl+C
→ P1 Mosquitto Ctrl+C
→ FastAPI Docker 종료
```

FastAPI 종료:

```bash
docker stop weld_p4_api_check
```

Virtual DRCF emulator가 남아 있으면:

```bash
docker stop dsr01_emulator
```

팀 실기용 `1883`, `8000`, `5173` 및 팀 실기용 Docker 서비스는 종료하지 않는다.

---

## 16. 빠른 문제 확인

### 웹에서 M0609 관절이 안 움직일 때

먼저:

```bash
mosquitto_sub -h 127.0.0.1 -p 1884 \
  -t 'robot/joints' -C 1 -v
```

수신이 없으면:

```bash
grep -A3 '^mqtt_bridge:' /tmp/weld-web-aligned-runtime/sim.yaml
```

반드시:

```text
broker_host: 127.0.0.1
broker_port: 1884
```

이어야 한다.

`1883`이면 수정 후 **P3 `integration.launch.py`만 재시작**한다.

```bash
sed -i 's/broker_port: 1883/broker_port: 1884/' \
  /tmp/weld-web-aligned-runtime/sim.yaml
```

### MQTT 1884 실행 시 `Address already in use`

이전 Virtual Mosquitto가 남아 있는 상태다.

```bash
fuser -k 1884/tcp
```

그 뒤 P1을 다시 실행한다.

### FastAPI 8001이 남아 있을 때

```bash
docker stop weld_p4_api_check
```

### Virtual DRCF 12345가 남아 있을 때

```bash
docker stop dsr01_emulator
```
