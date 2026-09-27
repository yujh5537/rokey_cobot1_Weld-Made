# 접촉 탐색 기반 외곽 엣지·경로 후보 생성 시스템

Doosan M0609 + OnRobot RG2(무센서 탐침)로 직육면체 부재를 만져 형상 좌표를 얻고, 윗면 외곽 엣지·경로 후보를 생성해 웹에서 실시간 3D로 보여주는 MVP. 교과 프로젝트 협동-1 (2026-09-18 ~ 09-22).

- 요구사항: [`docs/BRD.md`](docs/BRD.md) · 구조: [`docs/architecture.md`](docs/architecture.md) · 계약: [`docs/contracts/`](docs/contracts/)
- 작업 규칙: [`docs/conventions.md`](docs/conventions.md) · 일정·담당: GitHub Issues / Milestones
- 처음 받는 사람: [`SETUP.md`](SETUP.md)의 "팀원" 절

```
ws_cobot1/src/   ROS 2 Jazzy 자체 패키지 (메인 PC)
backend/         FastAPI, Spring Boot, MQTT 목업 발행기 (웹 PC)
frontend/        React + Three.js
docker/          Mosquitto, PostgreSQL, 백엔드 compose
docs/            BRD, 아키텍처, 계약, 결정 기록, 환경, 시험 결과
.claude/         팀 공통 Claude Code 설정·규칙·스킬
```

`ws_dsr/`(두산·RG2 드라이버)와 `DartPlatform/`은 이 레포에 없다. `docs/env/`를 따라 각자 구축한다.

웹 백엔드 역할 분담과 Spring Boot API는 [`backend/spring/README.md`](backend/spring/README.md)를 본다.


---

# 실기 통합 실행 Runbook

기준: **2026-09-23 최신 `main`**.

현재 실기 구성에서 Web PC MQTT Broker 주소는 `172.24.0.51:1883`이다. Web PC 주소가 바뀌면 아래 `broker_host`, 브라우저 주소, 네트워크 확인 명령도 함께 바꾼다.

## 1. 전체 실행 순서

```text
두 PC main 동기화
→ Main PC clean build
→ Web PC Docker 4개 서비스
→ Web PC MQTT monitor
→ Main ↔ Web 1883 확인
→ Main PC M0609 Real Driver
→ Tool/TCP 재등록
→ contact_scan_bringup(source:=robot_force)
→ 실기 파라미터 적용값 확인
→ ROS / MQTT 확인
→ Web Frontend
→ START
```

> **중요:** 실기 파라미터는 `main`의 `real.yaml`을 기준으로 사용한다. 런타임에서 임의로 덮어쓰기보다 bringup 뒤 `ros2 param get`으로 실제 적용값을 확인한다.

## 2. Web PC — W0 / W1 / W2 / W3

### W0 — 최신 main 동기화

```bash
cd /home/runo/collaboration/rokey_cobot1_Weld-Made
git fetch origin
git switch main
git pull --ff-only origin main
git branch --show-current
git log -1 --oneline
```

### W1 — Docker

```bash
cd /home/runo/collaboration/rokey_cobot1_Weld-Made/docker
[ -f .env ] || cp .env.example .env

docker compose up -d --build
docker compose ps

curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/db/test
curl http://127.0.0.1:8080/actuator/health
nc -vz 127.0.0.1 1883
```

정상 서비스:

```text
weld_made_mosquitto
weld_made_postgres
weld_made_fastapi
weld_made_spring
```

### W2 — MQTT monitor

이 터미널은 계속 켜 둔다.

```bash
mosquitto_sub -h 127.0.0.1 -p 1883 \
  -t 'conn/ros' -t 'hb/ros' \
  -t 'robot/status' -t 'robot/joints' -t 'robot/gripper_joints' \
  -t 'scan/state' -t 'scan/result' -t 'scan/log' \
  -t 'contact/event' -t 'safety/status' \
  -t 'cmd/ack' -t 'scan/command_result' -v
```

### W3 — Frontend

M3/M4 확인 뒤 실행한다.

```bash
cd /home/runo/collaboration/rokey_cobot1_Weld-Made/frontend
npm ci

VITE_BASE_TO_FIXTURE_MM=420.255,-156.675,95.006 \
VITE_TABLE_ORIGIN_MM=420.255,-156.675,95.006 \
npm run dev -- --host 0.0.0.0
```

브라우저:

```text
http://172.24.0.51:5173
```

화면에서 WebSocket 연결, M0609 J1~J6 관절 자세, RG2, TCP 궤적·접촉점·스캔 결과를 확인한다.

## 3. Main PC — M0 / M1 / M2 / M3 / M4

### M0 — 최신 main + Clean Build + Broker 확인

```bash
cd /home/rokey/collaboration/rokey_cobot1_Weld-Made
git fetch origin
git switch main
git pull --ff-only origin main

git branch --show-current
git log -1 --oneline

cd ws_cobot1
rm -rf build install log

source /opt/ros/jazzy/setup.bash
source /home/rokey/ws_cobot_pjt/ws_dsr/install/setup.bash
export ROS_DOMAIN_ID=30
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp

colcon build --symlink-install
source install/setup.bash

ping -c 3 172.24.0.51
nc -vz 172.24.0.51 1883
```

### M1 — M0609 Real Driver

> ⚠️ 물리 E-stop에 즉시 접근할 수 있는 상태에서 작업영역의 사람·장애물을 제거하고 펜던트 상태를 확인한 뒤 실행한다.

```bash
source /opt/ros/jazzy/setup.bash
source /home/rokey/ws_cobot_pjt/ws_dsr/install/setup.bash
export ROS_DOMAIN_ID=30
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp

ros2 launch m0609_rg2_bringup bringup.launch.py \
  mode:=real host:=192.168.1.100 port:=12345 model:=m0609
```

### M2 — DSR 확인 + Tool/TCP 재등록

```bash
source /opt/ros/jazzy/setup.bash
source /home/rokey/ws_cobot_pjt/ws_dsr/install/setup.bash
export ROS_DOMAIN_ID=30
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp

ros2 topic echo /dsr01/joint_states --once

cd /home/rokey/collaboration/rokey_cobot1_Weld-Made
python3 docs/env/apply_tool_tcp.py
```

성공 기준:

```text
OK: tool=rg2_probe, tcp=rg2_probe_tip [0.0, 0.0, 252.12]
```

Real Driver를 다시 띄웠다면 START 전에 Tool/TCP를 다시 등록하고 마지막 `OK`를 확인한다.

### M3 — contact_scan bringup

```bash
cd /home/rokey/collaboration/rokey_cobot1_Weld-Made/ws_cobot1
source /opt/ros/jazzy/setup.bash
source /home/rokey/ws_cobot_pjt/ws_dsr/install/setup.bash
source install/setup.bash
export ROS_DOMAIN_ID=30
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp

ros2 launch contact_scan_bringup bringup.launch.py \
  source:=robot_force \
  broker_host:=172.24.0.51
```

기동 대상:

```text
/robot_manager
/contact_detector
/safety_monitor
/scan_manager
/mqtt_bridge
```

### M4 — 적용 파라미터 + ROS / MQTT 확인

새 터미널:

```bash
cd /home/rokey/collaboration/rokey_cobot1_Weld-Made/ws_cobot1
source /opt/ros/jazzy/setup.bash
source /home/rokey/ws_cobot_pjt/ws_dsr/install/setup.bash
source install/setup.bash
export ROS_DOMAIN_ID=30
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
```

노드 확인:

```bash
ros2 node list | grep -E 'robot_manager|contact_detector|safety_monitor|scan_manager|mqtt_bridge'
```

실기 적용값 확인:

```bash
ros2 param get /contact_detector tare_max_std_n
ros2 param get /robot_manager step_release_n
```

현재 실기 기준 기대값:

```text
tare_max_std_n = 1.0
step_release_n = 2.5
```

ROS 확인:

```bash
ros2 topic echo /dsr01/joint_states --once
ros2 topic echo /robot/status --once
ros2 topic echo /robot/sample --once
ros2 topic echo /scan/state --once
```

이 시점에 Web PC W2에서도 최소 다음 항목을 확인한다.

```text
conn/ros
hb/ros
robot/status
robot/joints
robot/gripper_joints
scan/state
safety/status
```

## 4. START 전 최종 체크

```text
[ ] Web Docker 4개 서비스 정상
[ ] Web MQTT monitor 수신 중
[ ] Main ↔ Web 1883 연결 정상
[ ] M0609 Real Driver 정상
[ ] /dsr01/joint_states 수신
[ ] Tool/TCP apply_tool_tcp.py 마지막 줄 OK
[ ] 자체 ROS 2 노드 5개 기동
[ ] tare_max_std_n = 1.0
[ ] step_release_n = 2.5
[ ] Web에서 robot/joints 수신
[ ] 브라우저 WebSocket 연결 정상
[ ] 물리 E-stop 접근 가능
[ ] 작업영역 사람/장애물 없음
```

전부 확인한 뒤 브라우저에서 **START**를 누른다.

```text
React
→ FastAPI
→ MQTT
→ mqtt_bridge
→ scan_manager
→ robot_manager
→ M0609
```

정상 실행에서는 W2에서 `cmd/ack`, `scan/state`를 먼저 확인하고, 탐색 중 `scan/log`, `contact/event`, 완료 시 `scan/result`, `scan/command_result`를 확인한다.

## 5. 안전 명령

```text
START      새 스캔 시작
STOP       현재 작업 중지
HOME       안전복귀
RESUME     기존 측정값을 유지하고 중단 작업 재시작
```

STOP은 HOME 또는 RESUME을 자동 실행하지 않는다. 웹 STOP은 소프트웨어 정지 명령이며 물리 E-stop을 대체하지 않는다.

## 6. 종료 순서

```text
로봇 정지 확인
→ Frontend Ctrl+C
→ contact_scan bringup Ctrl+C
→ M0609 Real Driver Ctrl+C
→ 필요 시 Docker compose down
```

Web PC:

```bash
cd /home/runo/collaboration/rokey_cobot1_Weld-Made/docker
docker compose down
```

일반 종료에서는 PostgreSQL/Mosquitto 볼륨을 보존하기 위해 `docker compose down -v`를 사용하지 않는다.

## 7. 빠른 문제 확인

### Web PC에 MQTT가 안 들어올 때

```bash
# Main PC
ping -c 3 172.24.0.51
nc -vz 172.24.0.51 1883
```

M3의 `broker_host:=172.24.0.51`도 확인한다.

### `/dsr01/joint_states`가 없을 때

- M1 Real Driver가 실행 중인지 확인
- `ROS_DOMAIN_ID=30`
- `RMW_IMPLEMENTATION=rmw_fastrtps_cpp`
- `/home/rokey/ws_cobot_pjt/ws_dsr/install/setup.bash` source 여부 확인

### Tool/TCP가 실패할 때

```bash
cd /home/rokey/collaboration/rokey_cobot1_Weld-Made
python3 docs/env/apply_tool_tcp.py
```

마지막 줄이 `OK`가 아니면 START하지 않는다.

### 브라우저 형상 위치가 맞지 않을 때

```text
VITE_BASE_TO_FIXTURE_MM=420.255,-156.675,95.006
VITE_TABLE_ORIGIN_MM=420.255,-156.675,95.006
```

환경변수를 변경했다면 Vite 개발 서버를 종료한 뒤 다시 실행한다.
