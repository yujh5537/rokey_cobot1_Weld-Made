# DB 성공 스캔을 Virtual M0609·RViz2·웹에서 재현

이 문서는 로봇이 없는 환경에서 다른 개발자나 LLM이 동일한 시뮬레이션을 다시
실행하기 위한 절차다. 원본 DB scan ID는 `20260923-171647-5890`이다.

## 고정 설정

- 저장 프로필: [`db_success_20260923.yaml`](db_success_20260923.yaml)
- 작업대 상판/부재 밑면 중심(Base): `(420.255, -156.675, 95.006) mm`
- 가상 부재: `82.860178 × 80.600340 × 80.860821 mm`
- Virtual 전용 TCP Z: `246.98 mm`
- ROS: Jazzy, `ROS_DOMAIN_ID=99`, localhost discovery
- 웹: `http://127.0.0.1:5173`
- 런타임 파일과 로그: `/tmp/weld-made-db-sim`

가상 컨트롤러는 재기동할 때 TCP 등록을 잃는다. 웹 M0609 모델의 탐침 끝과
`contact/event` 접촉점을 맞추려면 스캔 노드를 시작하기 전에 TCP를 다시 등록한다.
246.98 mm는 Virtual 화면 정렬값이며 실기 TCP 설정에는 사용하지 않는다.

## LLM 실행 안전 규칙

1. 이 절차는 `mode:=virtual host:=127.0.0.1`에서만 실행한다.
2. `mode:=real`, `sodreal`, 실기 IP가 보이면 중단하고 어떤 명령도 보내지 않는다.
3. `~/ws_cobot_pjt/ws_dsr` 소스는 수정하지 않는다.
4. 로컬 변경, `backup-bashrc/`, 빌드 디렉터리를 삭제하거나 `git clean/reset`하지 않는다.
5. TCP 등록은 `apply_virtual_tcp.py`로 실행한다. 이 스크립트는 로컬 DRCF 컨테이너와
   Virtual launch를 확인하고, 실기 launch가 함께 있으면 거절한다.
6. 드라이버 → TCP 등록 → 자체 노드 순서를 지킨다. 자체 노드가 실행 중일 때 TCP를
   다시 등록하면 두산 서비스 호출이 겹칠 수 있다.

## 이 PC의 경로

```bash
REPO=~/collaboration/rokey_cobot1_Weld-Made
DSR=~/ws_cobot_pjt/ws_dsr
RUNTIME=/tmp/weld-made-db-sim
```

## 1. 사전 점검

레포 루트에서 실행한다. 출력에 `mode:=real`이 있으면 즉시 중단한다.

```bash
cd ~/collaboration/rokey_cobot1_Weld-Made
pgrep -af 'mode:=real|sodreal' || true

test -f /opt/ros/jazzy/setup.bash
test -f ~/ws_cobot_pjt/ws_dsr/install/setup.bash
test -d frontend/node_modules
```

백엔드가 없으면 시작한다.

```bash
docker compose -f docker/docker-compose.yml up -d
docker ps --format '{{.Names}} {{.Status}}' | sort
```

## 2. ROS 빌드와 실행 설정 생성

```bash
cd ~/collaboration/rokey_cobot1_Weld-Made/ws_cobot1
source /opt/ros/jazzy/setup.bash
source ~/ws_cobot_pjt/ws_dsr/install/setup.bash
colcon build   --base-paths src   --build-base build_virtual   --install-base install_virtual   --symlink-install   --parallel-workers 2

cd ~/collaboration/rokey_cobot1_Weld-Made
mkdir -p /tmp/weld-made-db-sim
python3 scripts/sim/prepare_db_success_config.py   --output /tmp/weld-made-db-sim/sim.yaml   --web-env-output /tmp/weld-made-db-sim/web.env
```

생성된 `sim.yaml`은 현재 `main` 계열의 기본 파라미터에 DB 성공 스캔의 부재 치수,
위치, 속도를 덮어쓴다. 결과 저장 경로는 `/tmp/weld-made-db-sim/results`다.

모든 ROS 터미널에서 아래 환경을 동일하게 사용한다.

```bash
source /opt/ros/jazzy/setup.bash
source ~/ws_cobot_pjt/ws_dsr/install/setup.bash
source ~/collaboration/rokey_cobot1_Weld-Made/ws_cobot1/install_virtual/setup.bash
export ROS_DOMAIN_ID=99
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
unset ROS_DISCOVERY_SERVER
```

## 3. Virtual M0609 드라이버 실행

별도 터미널에서 실행한다.

```bash
ros2 launch m0609_rg2_bringup bringup.launch.py   mode:=virtual host:=127.0.0.1 port:=12345 model:=m0609
```

LLM이 비대화형 셸에서 실행할 때는 다음처럼 분리 실행하고 로그를 남긴다.

```bash
setsid -f bash -lc 'source /opt/ros/jazzy/setup.bash; source ~/ws_cobot_pjt/ws_dsr/install/setup.bash; source ~/collaboration/rokey_cobot1_Weld-Made/ws_cobot1/install_virtual/setup.bash; export ROS_DOMAIN_ID=99 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST; unset ROS_DISCOVERY_SERVER; exec ros2 launch m0609_rg2_bringup bringup.launch.py mode:=virtual host:=127.0.0.1 port:=12345 model:=m0609' </dev/null >/tmp/weld-made-db-sim/driver.log 2>&1
```

준비 확인:

```bash
docker inspect -f '{{.State.Running}} {{.Name}}' dsr01_emulator
ros2 service list | grep /dsr01/dsr_controller2/system/set_robot_mode
```

## 4. Virtual TCP 등록

드라이버 서비스가 준비된 뒤 자체 노드를 시작하기 전에 실행한다.

```bash
cd ~/collaboration/rokey_cobot1_Weld-Made
python3 scripts/sim/apply_virtual_tcp.py   --config /tmp/weld-made-db-sim/sim.yaml
```

성공 기준은 마지막 줄이다.

```text
OK: rg2_probe_tip, TCP−flange=246.98 mm (설정 246.98 mm)
```

## 5. 스캔 노드와 MQTT 브리지 실행

이 launch 하나가 `robot_manager`, `contact_detector`, `safety_monitor`,
`scan_manager`, `mqtt_bridge`를 함께 실행한다.

```bash
ros2 launch contact_scan_bringup bringup.launch.py   source:=sim   config_file:=/tmp/weld-made-db-sim/sim.yaml   broker_host:=127.0.0.1
```

LLM 비대화형 실행:

```bash
setsid -f bash -lc 'source /opt/ros/jazzy/setup.bash; source ~/ws_cobot_pjt/ws_dsr/install/setup.bash; source ~/collaboration/rokey_cobot1_Weld-Made/ws_cobot1/install_virtual/setup.bash; export ROS_DOMAIN_ID=99 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST; unset ROS_DISCOVERY_SERVER; exec ros2 launch contact_scan_bringup bringup.launch.py source:=sim config_file:=/tmp/weld-made-db-sim/sim.yaml broker_host:=127.0.0.1' </dev/null >/tmp/weld-made-db-sim/bringup.log 2>&1
```

## 6. DRCF 초기 자세 만들기

새로 생성된 `dsr01_emulator`는 모든 관절이 0도인 특이 자세에서 시작한다. 이 상태에서
스캔이나 웹 **안전 위치**를 먼저 실행하면 첫 직선 이동이 DRCF 알람 `2/3509`로
거부될 수 있다. 스캔 노드가 준비된 뒤 아래 관절 홈 동작을 한 번 실행한다.

```bash
ros2 action send_goal /robot/execute_motion \
  contact_scan_interfaces/action/ExecuteMotion \
  "{scan_id: 'virtual-bootstrap', motion_id: 900001, operation: 4, target: {orientation: {w: 1.0}}, frame_id: 'base_link', direction: 0, speed: 0.0, max_distance: 0.0, timeout: {sec: 30, nanosec: 0}}"
```

`Goal finished with status: SUCCEEDED`, `reason: 0`, `reason_code: 0`을 모두 확인한다.
이 동작은 `sim.yaml`의 `home_joint_deg`를 사용하는 관절 이동이다. 초기 자세를 만들기
전에는 웹 **시작** 또는 **안전 위치** 버튼을 누르지 않는다.

## 7. RViz2 부재 마커와 화면 실행

각각 별도 터미널에서 실행한다.

```bash
python3 scripts/sim/markers.py --config /tmp/weld-made-db-sim/sim.yaml
rviz2 -d scripts/sim/db_sim.rviz
```

LLM 비대화형 실행:

```bash
setsid -f bash -lc 'source /opt/ros/jazzy/setup.bash; source ~/ws_cobot_pjt/ws_dsr/install/setup.bash; source ~/collaboration/rokey_cobot1_Weld-Made/ws_cobot1/install_virtual/setup.bash; export ROS_DOMAIN_ID=99 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST; unset ROS_DISCOVERY_SERVER; exec python3 ~/collaboration/rokey_cobot1_Weld-Made/scripts/sim/markers.py --config /tmp/weld-made-db-sim/sim.yaml' </dev/null >/tmp/weld-made-db-sim/markers.log 2>&1

setsid -f bash -lc 'source /opt/ros/jazzy/setup.bash; source ~/ws_cobot_pjt/ws_dsr/install/setup.bash; source ~/collaboration/rokey_cobot1_Weld-Made/ws_cobot1/install_virtual/setup.bash; export ROS_DOMAIN_ID=99 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST DISPLAY=:1; unset ROS_DISCOVERY_SERVER; exec rviz2 -d ~/collaboration/rokey_cobot1_Weld-Made/scripts/sim/db_sim.rviz' </dev/null >/tmp/weld-made-db-sim/rviz.log 2>&1
```

## 8. 웹 실행

`web.env`의 두 좌표를 반드시 Vite 시작 전에 적용한다.

```bash
cd ~/collaboration/rokey_cobot1_Weld-Made/frontend
set -a
source /tmp/weld-made-db-sim/web.env
set +a
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

LLM 비대화형 실행:

```bash
setsid -f bash -lc 'cd ~/collaboration/rokey_cobot1_Weld-Made/frontend; set -a; source /tmp/weld-made-db-sim/web.env; set +a; exec npm run dev -- --host 127.0.0.1 --port 5173 --strictPort' </dev/null >/tmp/weld-made-db-sim/frontend.log 2>&1
```

## 9. 실행 검증

```bash
curl -I http://127.0.0.1:5173/
ros2 node list | sort
ros2 topic list | rg '^/(robot/sample|scan/state|safety/status|db_sim/markers)$'
tail -30 /tmp/weld-made-db-sim/bringup.log
```

필수 노드는 `/robot_manager`, `/contact_detector`, `/safety_monitor`,
`/scan_manager`, `/mqtt_bridge`, `/db_sim_scene`이다. 웹과 ROS 연결이 정상이면 웹에서
로봇 관절, 탐침 위치, 현재 단계를 실시간으로 볼 수 있다.

## 10. 스캔 실행

웹의 **시작** 버튼을 누른다. API로 실행할 때는 다음을 사용한다.

```bash
curl -sS -X POST http://127.0.0.1:5173/commands/scan/start   -H 'Content-Type: application/json'   -d '{"session_id":"db-sim","payload":{}}'
```

반환된 `request_id`의 완료 상태는 다음 API로 확인한다.

```bash
curl -sS http://127.0.0.1:5173/commands/<request_id>
```

정상 결과는 `status=SUCCEEDED`, `scan/result.success=true`다. 측정 치수는 가상 부재
`82.86 × 80.60 × 80.86 mm`에 근접해야 한다. 이 결과는 가상 모델 재측정 검증이며
실기 정확도 근거가 아니다.

## 11. 문제 해결

- 웹에 로봇만 보이고 부재가 없으면 `markers.py`와 `/db_sim/markers`를 확인한다.
- 웹 접촉점과 탐침 끝이 약 247 mm 어긋나면 Virtual TCP가 등록되지 않은 것이다.
  자체 노드를 중지한 후 4절을 다시 실행한다.
- 작업대와 부재 높이가 다르면 `web.env` 두 값과 `sim.yaml`의
  `base_to_fixture`, `sim_box_origin_m`이 모두 `(0.420255, -0.156675, 0.095006)`인지 본다.
- 웹이 연결되지 않으면 Mosquitto, FastAPI, `mqtt_bridge`, Vite 순서로 상태를 확인한다.
- 첫 스캔 또는 **안전 위치**가 `ROBOT_ERROR(204)`와 DRCF 알람 `2/3509`로 실패하면
  직선 이동을 반복하지 말고 6절의 관절 홈 동작을 먼저 실행한다.
- `ROS_LOCALHOST_ONLY is deprecated` 경고는 실행 실패가 아니다.
- `contact_scan_interfaces` 빌드 중 `/* within comment` 경고는 현재 알려진 생성 코드
  경고이며 빌드 Summary가 성공이면 실행 가능하다.

## 12. 종료

무작정 `pkill`하지 않는다. 먼저 대상 PID와 명령을 확인하고 이 문서로 시작한 프로세스만
`SIGINT`로 종료한다. 드라이버 launch를 종료하면 `dsr01_emulator`도 정리된다.

```bash
pgrep -af 'm0609_rg2_bringup|contact_scan_bringup|scripts/sim/markers.py|scripts/sim/db_sim.rviz|vite.*5173'
kill -INT <확인한 PID들>
```

Docker 백엔드까지 종료할 때만 다음을 실행한다.

```bash
docker compose -f docker/docker-compose.yml down
```

## 검증 기록

- 2026-09-28 정렬 검증: 윗면 접촉점과 웹 탐침 끝 약 0.27 mm, 모서리 접촉점
  약 1–2 mm. 모서리 잔차는 가상 접촉 모델의 하강을 DRCF 팔 자세가 그대로
  재현하지 않는 데서 주로 발생한다.
- 2026-09-28 안전 해제 검증: Virtual 31 N 과대 외력에서 래치와 정지 확인 후
  웹 `cmd/safety/reset` 결과 `SUCCEEDED`, 최종 `latched=false`.
- 2026-09-28 전체 재실행 검증: 새 DRCF 영점 자세에서 6절 관절 홈 동작이
  `reason_code=0`으로 성공했다. 이후 웹 요청
  `281c5ae3-3d54-4977-bcb1-78fdb9b566b9`가 97초 만에 `SUCCEEDED`했다.
  DB scan ID는 `20260928-195546-6092`, 접촉점은 5개이며 측정값은
  `82.770 × 80.430 × 80.756 mm`, `dims_valid=true`, `box_valid=true`다.


## 윗면 모서리 가상 용접 (위빙)

웹에서 새 스캔이 완료되고 오브젝트와 초록색 경로가 생성된 뒤 1.5초 후,
해당 scan ID의 저장 결과에 있는 윗면
네 변(L0→L1→L2→L3)을 가상 M0609가 자동으로 따라간다.
이미 생성된 결과를 다시 용접할 때는 **용접 시작**을 누른다. **용접 중지**는 현재 이동을
취소하며 자동 복귀하지 않는다. 기존 스캔 버튼 이름은 유지한다.

먼저 위 ROS 환경을 source한 터미널에서 다음 서버를 실행한다.

```bash
python3 scripts/sim/weld_preview.py
```

서버는 `127.0.0.1:8766`에서만 수신한다. Vite의 `/sim-weld` 프록시로 웹과 연결한다.
로컬 Virtual DRCF 확인, 최신 로봇·스캔·안전 상태 확인을 통과해야 시작한다.
진행 중 `/weld/state`를 발행하여 새 스캔 시작을 막는다.
`--config`, `--results`로 런타임 설정과 결과 디렉터리를 지정할 수 있다.

설정 파일: [`weld_preview.yaml`](weld_preview.yaml).

- 진폭 ±2 mm, 반주기 간격 4 mm, 용접 속도 10 mm/s.
- 툴 기울기 0°(수직), 스탠드오프 3 mm, 이동 높이 윗면 +30 mm.
- 각 변의 시작·끝은 위빙 중심선으로 돌아온다. 변 사이에는 상승 후 이동한다.
- 네 변을 완료하면 홈으로 복귀한다. 이동 실패 시 오류를 표시하고 다음 변으로 넘어가지 않는다.
- `ExecuteMotion`의 점별 이동으로 구현하므로 각 지그재그 꼭짓점에서 짧게 정지한다.
- 불꽃은 TCP에서 스탠드오프를 뺀 윗면 위치에 표시한다. 용접 자국은 실제 수신한
  TCP 이동을 사용하며 카메라 회전에도 부재에 붙어 있다. 새 용접 시작 시 자국을 초기화한다.
- 사용자 제공 ArcWelding 코드의 주황색 불꽃, 중력, 잔광과 식는 자국을 Three.js로 적용했다.
- 현재 범위는 가상 윗면 네 변이다. 세로 모서리, 실기 용접 출력은 포함하지 않는다.

검증 명령 (위 ROS 환경에서):

```bash
python3 scripts/sim/test_weld_preview.py
curl -sS http://127.0.0.1:5173/sim-weld/state
```

웹은 현재 표시 중인 성공 스캔 ID를 `/sim-weld/start`에 보낸다. 임의의 가장 최근
파일을 자동 선택하지 않으므로, 화면의 부재와 다른 스캔을 따라가지 않는다.

현재 DB 배치에서는 45° 자세로 L0는 성공했지만 L1 접근이 204로 실패했다.
기존 M1 도달성 기록과 같은 문제이며, 위치 정렬을 유지하기 위해 가상 시연 기본값은
수직 자세로 둔다. 위빙 진폭과 간격은 원래 시나리오 값을 유지한다.

용접 서버 로그: `/tmp/weld-made-db-sim/weld.log`. 서버 기동 전에 생성된 과거 결과는
자동 재실행하지 않으며, 웹이 새 스캔의 PREPARING부터 DONE까지 관찰한 경우만 자동 시작한다.

가상 서버는 ROS Jazzy의 `rclpy`, 프로젝트 메시지 외에 Python `numpy`, `scipy`,
`PyYAML`을 사용한다(현재 PC에 설치됨). HTTP는 로컬 개발 Vite 프록시용이며
배포 서버나 실기 제어 API가 아니다.
