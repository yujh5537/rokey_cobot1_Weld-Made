# Real M0609 + Web 3D 단일 Web PC 통합 실행 Runbook

기준 브랜치: `main`

목적: **Web PC 한 대에서 기존 Web PC 역할 + Main PC 역할을 모두 실행**한다.

즉 아래 기능을 모두 **현재 실기 PC 한 대**에서 실행한다.

```text
M0609 Real Driver
ROS 2 contact_scan 노드
mqtt_bridge
Mosquitto
FastAPI
Spring Boot
PostgreSQL
React + Three.js
```

---

## 1. 실행 환경

```text
PC              = 현재 로그인한 실기 PC
Repo            = $HOME/rokey_cobot1_Weld-Made
Doosan ws_dsr   = $HOME/ws_cobot_pjt/ws_dsr

ROS_DOMAIN_ID   = 30
RMW             = rmw_fastrtps_cpp

MQTT Broker     = 127.0.0.1:1883
FastAPI         = 127.0.0.1:8000
Spring Boot     = 127.0.0.1:8080
Frontend        = 127.0.0.1:5173

M0609           = 192.168.1.100:12345
Driver mode     = real
ROS force source= robot_force
```

> **중요**
>
> - ROS와 Web이 같은 PC에서 실행되므로 `broker_host`는 **`127.0.0.1`**을 사용한다.
> - Virtual용 `ROS_DOMAIN_ID=166`, MQTT `1884`, API `8001`, Frontend `5174`를 사용하지 않는다.
> - 실기 파라미터는 `ws_cobot1/src/contact_scan_bringup/config/real.yaml` 기준이다.
> - Real Driver를 다시 실행했다면 START 전에 Tool/TCP를 다시 등록한다.
> - 물리 E-stop에 즉시 접근 가능한 상태에서만 실제 로봇을 움직인다.

---


# 2. 처음 Clone하는 사용자 — 경로 준비

이 문서는 사용자명이나 `/home/runo/...` 같은 절대경로에 의존하지 않는다.

권장 방식은 **홈 디렉터리에서 그대로 clone**하는 것이다.

```bash
cd "$HOME"

git clone https://github.com/yujh5537/rokey_cobot1_Weld-Made.git

cd "$HOME/rokey_cobot1_Weld-Made"
git switch main
git pull --ff-only origin main
```

그러면 모든 사용자는 동일하게 아래 경로를 사용할 수 있다.

```text
Repo          = $HOME/rokey_cobot1_Weld-Made
ws_cobot1     = $HOME/rokey_cobot1_Weld-Made/ws_cobot1
docker        = $HOME/rokey_cobot1_Weld-Made/docker
frontend      = $HOME/rokey_cobot1_Weld-Made/frontend
```

Doosan `ws_dsr`는 이 Git 저장소에 포함되지 않는 외부 의존성이다.

이 Runbook은 기본적으로 다음 위치에 `ws_dsr`가 설치되어 있다고 가정한다.

```text
$HOME/ws_cobot_pjt/ws_dsr
```

설치 여부 확인:

```bash
test -f "$HOME/ws_cobot_pjt/ws_dsr/install/setup.bash" \
  && echo "OK: ws_dsr setup found" \
  || echo "ERROR: ws_dsr install/setup.bash 경로 확인 필요"
```

다른 위치에 `ws_dsr`를 설치한 사용자는 문서의:

```bash
source "$HOME/ws_cobot_pjt/ws_dsr/install/setup.bash"
```

부분만 자신의 실제 `ws_dsr/install/setup.bash` 경로로 바꾼다.

> `rokey_cobot1_Weld-Made` 자체는 `$HOME` 아래에 clone하는 것을 권장한다.  
> 다른 위치에 clone했다면 문서의 `$HOME/rokey_cobot1_Weld-Made`만 실제 clone 경로로 바꾸면 된다.

---

# 3. 전체 실행 순서

```text
T0 main 동기화 + Clean Build
→ T1 Docker 4개 서비스
→ T2 MQTT Monitor
→ T3 M0609 Real Driver
→ T4 DSR 확인 + Tool/TCP 재등록
→ T5 contact_scan bringup
→ T6 ROS / MQTT / 실기 파라미터 확인
→ T7 Frontend
→ WebSocket + M0609 관절 확인
→ START
```

---

# 4. T0 — main 동기화 + Clean Build

**터미널 T0**

## T0-1 — 최신 main

> 처음 clone한 사용자는 위의 Clone 단계를 먼저 완료한다.

```bash
cd "$HOME/rokey_cobot1_Weld-Made"

git fetch origin
git switch main
git pull --ff-only origin main
```

## T0-2 — ROS Clean Build

```bash
cd "$HOME/rokey_cobot1_Weld-Made/ws_cobot1"

rm -rf build install log

source /opt/ros/jazzy/setup.bash
source "$HOME/ws_cobot_pjt/ws_dsr/install/setup.bash"

export ROS_DOMAIN_ID=30
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp

colcon build --symlink-install
source install/setup.bash
```

## T0-3 — 실제 M0609 네트워크 확인

```bash
ping -c 3 192.168.1.100
```

정상 기준:

```text
192.168.1.100 응답 수신
```

응답이 없으면 Real Driver를 실행하지 않는다.

---

# 5. T1 — Docker 4개 서비스

**새 터미널 T1**

```bash
cd "$HOME/rokey_cobot1_Weld-Made/docker"

[ -f .env ] || cp .env.example .env

docker compose up -d --build
docker compose ps
```

정상 서비스:

```text
weld_made_mosquitto
weld_made_postgres
weld_made_fastapi
weld_made_spring
```

확인:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/db/test
curl http://127.0.0.1:8080/actuator/health
nc -vz 127.0.0.1 1883
```

정상 기준:

```text
FastAPI  :8000 정상
Postgres 연결 정상
Spring   :8080 정상
MQTT     :1883 연결 성공
```

Docker는 background로 실행되므로 T1은 계속 점유되지 않는다.

---

# 6. T2 — MQTT Monitor

**새 터미널 T2. 계속 켜 둔다.**

```bash
mosquitto_sub -h 127.0.0.1 -p 1883 \
  -t 'conn/ros' \
  -t 'hb/ros' \
  -t 'robot/status' \
  -t 'robot/joints' \
  -t 'robot/gripper_joints' \
  -t 'robot/sample' \
  -t 'scan/state' \
  -t 'scan/result' \
  -t 'scan/log' \
  -t 'contact/event' \
  -t 'safety/status' \
  -t 'cmd/ack' \
  -t 'scan/command_result' \
  -v
```

T2는 종료할 때까지 그대로 둔다.

---

# 7. T3 — M0609 Real Driver

**새 터미널 T3. 계속 켜 둔다.**

실행 전:

```text
[ ] 물리 E-stop에 즉시 접근 가능
[ ] 작업영역에 사람 없음
[ ] 작업영역에 장애물 없음
[ ] RG2 탐침 장착 확인
[ ] 티치펜던트 상태 확인
[ ] 192.168.1.100 ping 성공
```

환경:

```bash
source /opt/ros/jazzy/setup.bash
source "$HOME/ws_cobot_pjt/ws_dsr/install/setup.bash"

export ROS_DOMAIN_ID=30
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
```

Real Driver 실행:

```bash
ros2 launch m0609_rg2_bringup bringup.launch.py \
  mode:=real \
  host:=192.168.1.100 \
  port:=12345 \
  model:=m0609
```

반드시 실기 설정:

```text
mode  = real
host  = 192.168.1.100
port  = 12345
model = m0609
```

T3는 계속 켜 둔다.

---

# 8. T4 — DSR 확인 + Tool/TCP 재등록

**새 터미널 T4**

환경:

```bash
source /opt/ros/jazzy/setup.bash
source "$HOME/ws_cobot_pjt/ws_dsr/install/setup.bash"

export ROS_DOMAIN_ID=30
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
```

실제 M0609 관절 수신 확인:

```bash
ros2 topic echo /dsr01/joint_states --once
```

관절값이 수신되면 Tool/TCP 등록:

```bash
cd "$HOME/rokey_cobot1_Weld-Made"

python3 docs/env/apply_tool_tcp.py
```

반드시 마지막 줄:

```text
OK: tool=rg2_probe, tcp=rg2_probe_tip [0.0, 0.0, 252.12]
```

`OK`가 아니면 다음 단계로 가지 않는다.

> T3 Real Driver를 재시작했다면 Tool/TCP도 다시 등록한다.

---

# 9. T5 — contact_scan bringup

**새 터미널 T5. 계속 켜 둔다.**

```bash
cd "$HOME/rokey_cobot1_Weld-Made/ws_cobot1"

source /opt/ros/jazzy/setup.bash
source "$HOME/ws_cobot_pjt/ws_dsr/install/setup.bash"
source install/setup.bash

export ROS_DOMAIN_ID=30
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
```

실행:

```bash
ros2 launch contact_scan_bringup bringup.launch.py \
  source:=robot_force \
  broker_host:=127.0.0.1
```

기동 대상:

```text
robot_manager
contact_detector
safety_monitor
scan_manager
mqtt_bridge
```

같은 PC이므로 MQTT 흐름:

```text
ROS 2
→ mqtt_bridge
→ 127.0.0.1:1883
→ Mosquitto
→ FastAPI
→ WebSocket
→ React
```

T5는 계속 켜 둔다.

---

# 10. T6 — START 전 ROS / MQTT 확인

**새 터미널 T6**

환경:

```bash
cd "$HOME/rokey_cobot1_Weld-Made/ws_cobot1"

source /opt/ros/jazzy/setup.bash
source "$HOME/ws_cobot_pjt/ws_dsr/install/setup.bash"
source install/setup.bash

export ROS_DOMAIN_ID=30
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
```

## T6-1 — 자체 ROS 노드 확인

```bash
ros2 node list | grep -E 'robot_manager|contact_detector|safety_monitor|scan_manager|mqtt_bridge'
```

정상:

```text
/robot_manager
/contact_detector
/safety_monitor
/scan_manager
/mqtt_bridge
```

## T6-2 — 실기 적용 파라미터 확인

```bash
ros2 param get /contact_detector tare_max_std_n
ros2 param get /robot_manager step_release_n
```

현재 `real.yaml` 기준 기대값:

```text
tare_max_std_n = 1.0
step_release_n = 2.5
```

## T6-3 — 실제 로봇 상태 확인

```bash
ros2 topic echo /dsr01/joint_states --once
```

```bash
ros2 topic echo /robot/status --once
```

```bash
ros2 topic echo /robot/sample --once
```

```bash
ros2 topic echo /safety/status --once
```

```bash
ros2 topic echo /scan/state --once
```

START 전 핵심 기준:

```text
/dsr01/joint_states → 실제 J1~J6 수신
/robot/status       → connected: true
/robot/sample       → valid: true
/safety/status      → latched: false
/scan/state         → 정상 수신
```

---

# 11. T2 — MQTT 수신 확인

T5가 정상이라면 T2에 최소 아래가 들어와야 한다.

```text
conn/ros
hb/ros
robot/status
robot/joints
robot/gripper_joints
scan/state
safety/status
```

특히 웹 M0609 자세에 필요한 경로:

```text
/dsr01/joint_states
→ mqtt_bridge (20 Hz)
→ MQTT robot/joints
→ Mosquitto :1883
→ FastAPI
→ WebSocket
→ React
→ Three.js joint_1 ~ joint_6
```

관절만 별도로 확인하려면:

```bash
mosquitto_sub -h 127.0.0.1 -p 1883 \
  -t 'robot/joints' -C 1 -v
```

정상 예:

```text
robot/joints {"schema_version":"0.1", ... "names":["joint_1","joint_2","joint_3","joint_4","joint_5","joint_6"], ...}
```

---

# 12. T7 — Frontend 5173

**T6와 MQTT 확인까지 끝난 후 새 터미널 T7에서 실행한다.**

```bash
cd "$HOME/rokey_cobot1_Weld-Made/frontend"

npm ci
```

실기 좌표 적용:

```bash
VITE_BASE_TO_FIXTURE_MM=420.255,-156.675,95.006 \
VITE_TABLE_ORIGIN_MM=420.255,-156.675,95.006 \
npm run dev -- --host 0.0.0.0
```

같은 PC 브라우저:

```text
http://127.0.0.1:5173
```

다른 PC에서 이 실기 PC의 웹에 접속할 경우 먼저 실기 PC의 LAN IPv4를 확인한다.

```bash
hostname -I
```

출력된 주소 중 **같은 LAN에서 접근 가능한 IPv4**를 사용한다.

```text
http://<WEB_PC_IP>:5173
```

예를 들어 LAN IP가 `192.168.0.50`이면:

```text
http://192.168.0.50:5173
```

웹에서 확인:

```text
[ ] WebSocket 연결
[ ] 실제 M0609 J1~J6 자세 갱신
[ ] RG2 표시
[ ] TCP 위치 / 궤적
[ ] scan.state 표시
```

실기 좌표:

```text
VITE_BASE_TO_FIXTURE_MM = 420.255,-156.675,95.006
VITE_TABLE_ORIGIN_MM    = 420.255,-156.675,95.006
```

---

# 13. START 전 최종 체크

```text
[ ] T1 Docker 4개 서비스 정상
[ ] T2 MQTT Monitor 실행 중

[ ] T3 M0609 Real Driver 실행 중
[ ] mode:=real
[ ] host:=192.168.1.100
[ ] /dsr01/joint_states 실제 관절 수신

[ ] T4 Tool/TCP 마지막 줄 OK
[ ] tool = rg2_probe
[ ] tcp = rg2_probe_tip [0.0, 0.0, 252.12]

[ ] T5 ROS 노드 5개 실행 중
[ ] source:=robot_force
[ ] broker_host:=127.0.0.1

[ ] tare_max_std_n = 1.0
[ ] step_release_n = 2.5

[ ] /robot/status connected: true
[ ] /robot/sample valid: true
[ ] /safety/status latched: false

[ ] MQTT conn/ros 수신
[ ] MQTT hb/ros 수신
[ ] MQTT robot/status 수신
[ ] MQTT robot/joints 수신
[ ] MQTT scan/state 수신
[ ] MQTT safety/status 수신

[ ] 브라우저 WebSocket 연결 정상
[ ] 웹 M0609 J1~J6가 실제 로봇과 같이 움직임

[ ] 물리 E-stop 접근 가능
[ ] 작업영역 사람 없음
[ ] 작업영역 장애물 없음
```

전부 확인한 뒤 브라우저에서 **START**를 누른다.

---

# 14. 실제 실행 데이터 흐름

명령:

```text
React :5173
→ FastAPI :8000
→ MQTT :1883
→ mqtt_bridge
→ scan_manager
→ robot_manager
→ M0609 Real Driver
→ 실제 M0609
```

상태:

```text
실제 M0609
→ /dsr01/joint_states
→ mqtt_bridge
→ robot/joints
→ Mosquitto
→ FastAPI
→ WebSocket
→ React / Three.js
```

스캔 실행:

```text
START 직후
→ cmd/ack
→ scan/state

탐색 중
→ scan/log
→ contact/event
→ robot/status
→ robot/joints

완료
→ scan/result
→ scan/command_result
```

---

# 15. 웹 명령

```text
START     새 스캔 시작
STOP      현재 작업 중지
HOME      안전복귀
RESUME    기존 측정값 유지 후 중단 작업 재시작
```

```text
STOP ≠ HOME ≠ RESUME
```

STOP은 HOME 또는 RESUME을 자동 실행하지 않는다.

웹 STOP은 소프트웨어 정지이며 물리 E-stop을 대체하지 않는다.

---

# 16. 종료 순서

먼저 실제 로봇 모션이 완전히 멈춘 것을 확인한다.

```text
M0609 모션 정지 확인
→ T7 Frontend Ctrl+C
→ T5 contact_scan bringup Ctrl+C
→ T3 M0609 Real Driver Ctrl+C
→ T2 MQTT Monitor Ctrl+C
→ 필요 시 Docker 종료
```

Docker 종료:

```bash
cd "$HOME/rokey_cobot1_Weld-Made/docker"

docker compose down
```

일반 종료에서는 볼륨을 보존하기 위해:

```text
docker compose down -v
```

는 사용하지 않는다.

---

# 17. 빠른 문제 확인

## 17-1. 웹에서 M0609 관절이 안 움직일 때

### 1단계 — ROS

```bash
ros2 topic echo /dsr01/joint_states --once
```

```text
수신 안 됨
→ T3 Real Driver 확인

수신 됨
→ MQTT 확인
```

### 2단계 — MQTT

```bash
mosquitto_sub -h 127.0.0.1 -p 1883 \
  -t 'robot/joints' -C 1 -v
```

```text
수신 안 됨
→ T5 mqtt_bridge 확인
→ broker_host:=127.0.0.1 확인

수신 됨
→ FastAPI / WebSocket / React 확인
```

---

## 17-2. MQTT Broker 연결 실패

```bash
nc -vz 127.0.0.1 1883
```

안 되면:

```bash
cd "$HOME/rokey_cobot1_Weld-Made/docker"
docker compose ps
```

`weld_made_mosquitto` 상태를 확인한다.

---

## 17-3. `/dsr01/joint_states`가 없을 때

```text
T3 Real Driver 실행 중?
        ↓
mode:=real?
        ↓
host:=192.168.1.100?
        ↓
ROS_DOMAIN_ID=30?
        ↓
RMW_IMPLEMENTATION=rmw_fastrtps_cpp?
        ↓
ws_dsr setup.bash source?
        ↓
192.168.1.100 통신 정상?
```

---

## 17-4. Tool/TCP 실패

```bash
cd "$HOME/rokey_cobot1_Weld-Made"

python3 docs/env/apply_tool_tcp.py
```

반드시:

```text
OK: tool=rg2_probe, tcp=rg2_probe_tip [0.0, 0.0, 252.12]
```

가 나와야 한다.

---

## 17-5. 웹 형상 위치가 맞지 않을 때

T7 실행값:

```text
VITE_BASE_TO_FIXTURE_MM=420.255,-156.675,95.006
VITE_TABLE_ORIGIN_MM=420.255,-156.675,95.006
```

변경했다면 T7을 `Ctrl+C`로 종료 후 다시 실행한다.

---

# 18. 단일 PC 실기 / Virtual 구분

## 현재 단일 Web PC 실기

```text
ROS_DOMAIN_ID = 30
MQTT          = 127.0.0.1:1883
FastAPI       = 127.0.0.1:8000
Frontend      = 127.0.0.1:5173
M0609         = 192.168.1.100:12345
mode          = real
source        = robot_force
TCP           = 252.12 mm
```

## Virtual 단독 실행

```text
ROS_DOMAIN_ID = 166
MQTT          = 127.0.0.1:1884
FastAPI       = 127.0.0.1:8001
Frontend      = 127.0.0.1:5174
M0609         = 127.0.0.1:12345
mode          = virtual
```

**실기 실행 중 Virtual 환경값을 섞지 않는다.**