# M0609 실기 스캔 → 용접 모션 실행

실기 전에 같은 P1→P2→P4 흐름을 재현하려면 [Virtual 에뮬레이터 Runbook](virtual-p1-p2-p4.md)을 따른다.

기준: 2026-09-29, `p2-virtual-integration` **`b4e780c`** (P1 ExecutePath + P2 weld_manager + P4 MQTT 브리지).
이 문서의 명령은 **현장 담당자가 직접 실행**한다. `CLAUDE.md` 규칙 1에 따라 에이전트는
실기 드라이버·로봇 액션을 실행하지 않는다. 여기서 “용접”은 RG2 탐침을 이음선에서 띄워
움직이는 모션이다. 아크 출력과 용접 토치는 없다.

> 주소·계정은 `docker/.env` 의 값을 쓴다. 아래 명령 전에 `export WEB_PC=<웹 PC 주소>` · `export WEB_PC_USER=<계정>` 을 설정한다. 공개 레포라 실제 값은 적지 않는다.

[기존 README 실기 스캔 Runbook](../../README.md)의 Web PC `$WEB_PC`, M0609
`192.168.1.100`, Main PC `/home/rokey`를 출발값으로 사용한다. 현장 주소가 다르면 먼저
실제 값을 확인한다. 이 P1/P2/P4 코드는 아직 `main`에 없으므로 두 PC에 아래 Git bundle을
전달해 **같은 커밋**으로 실행한다. 기존 작업 디렉터리의 미커밋 변경은 유지한다.

## 0. 시작 전 확인과 코드 전달

- 물리 E-stop과 펜던트에 사람이 접근할 수 있고 로봇 작업영역이 비어 있는지 확인한다.
- 탐침·RG2 체결, 큐브와 작업대 위치, 로봇 주변 간섭물을 확인한다.
- **탐침 외형 실측**이 필요하다. `tool_profile_u_m`은 팁에서 툴 축을 따라 뒤로 잰
  위치이고, `tool_profile_r_m`은 각 위치부터 다음 위치까지의 최대 반폭이다. 닫힌
  RG2 핑거와 탐침 몸통을 캘리퍼로 재서 같은 개수의 배열로 기록한다. u는 0 이상
  오름차순, r은 양수이며 단위는 **m**다. 이 둘이 비어 있으면 `/weld/run`은
  `INVALID_VALUE(102)`로 거절된다. 값은 스캔 때 자동 생성되지 않는다.
- 팁 반지름 `tip_radius_m`은 `real.yaml`의 scan_manager와 weld_manager에서
  동일해야 한다. 현재 파일의 `0.002 m`는 캘리퍼 확정 전 출발값이다.

이 PC에서 만든 전달 파일: [`p1-p2-p4-integration.bundle`](../../scripts/sim/p1-p2-p4-integration.bundle).
이 파일을 **Web PC와 Main PC 모두**에 복사한다. Web PC에서는:

```bash
cd ~/collaboration/rokey_cobot1_Weld-Made
cp scripts/sim/p1-p2-p4-integration.bundle ./p1-p2-p4-integration.bundle
```

Main PC에서는 Web PC의 SSH가 열려 있다면 다음처럼 가져온다. SSH가 없다면
같은 파일을 USB 등으로 Main PC의 레포 루트에 옮긴다.

```bash
cd /home/rokey/collaboration/rokey_cobot1_Weld-Made
scp $WEB_PC_USER@$WEB_PC:~/collaboration/rokey_cobot1_Weld-Made/scripts/sim/p1-p2-p4-integration.bundle .
```

그다음 **각 PC**의 레포 루트에서 실행한다.

```bash
cd ~/collaboration/rokey_cobot1_Weld-Made
git fetch origin
git bundle verify p1-p2-p4-integration.bundle
git fetch p1-p2-p4-integration.bundle refs/heads/p2-virtual-integration
git worktree add -b p2-real-motion ../weld-made-real-motion FETCH_HEAD
cd ../weld-made-real-motion
git log -1 --oneline
# b4e780c feat(bridge): route weld commands and telemetry through MQTT
```

이미 `p2-real-motion` worktree를 만들었다면 중복으로 만들지 않는다. 두 PC 모두
`b4e780c`인지 확인한다. bundle 검증에서 선행 커밋이 없다고 나오면 레포의 `origin/main`
히스토리를 먼저 가져온다. 이 bundle은 코드 전달용이며 `main`에 머지하지 않는다.

## 1. Web PC: 브로커·백엔드·모니터

Web PC의 `weld-made-real-motion`에서 실행한다. 기존 Docker 데이터 볼륨을 지우지 않는다.

```bash
cd ~/collaboration/weld-made-real-motion/docker
if [ -f ~/collaboration/rokey_cobot1_Weld-Made/docker/.env ]; then
  cp ~/collaboration/rokey_cobot1_Weld-Made/docker/.env .env
else
  cp .env.example .env
fi
# .env의 POSTGRES_PASSWORD 등 현장값을 확인한다.
docker compose up -d --build mosquitto postgres fastapi spring
docker compose ps
curl -sS http://127.0.0.1:8000/health
nc -vz 127.0.0.1 1883
```

별도 터미널에서 MQTT를 계속 관찰한다. `weld/state`는 retain이라 구독 직후 마지막
상태가 보인다.

```bash
mosquitto_sub -h 127.0.0.1 -p 1883 -v \
  -t 'conn/ros' -t 'robot/status' -t 'scan/state' -t 'scan/result' \
  -t 'safety/status' -t 'cmd/ack' -t 'scan/command_result' \
  -t 'weld/state' -t 'weld/result' -t 'weld/log' -t 'weld/command_result'
```

웹 3D 화면을 같이 보려면 Vite를 별도 터미널에서 띄운다. 좌표는 현장 배치와
`real.yaml`의 `base_to_fixture`를 맞춰야 한다. 현재 웹의 **용접 시작** 버튼은 기존
로컬 `/sim-weld` 시연용이므로 **실기 P4 명령에는 사용하지 않는다**. 실기 용접 모션은
아래 REST 명령으로 요청한다.

```bash
cd ~/collaboration/weld-made-real-motion/frontend
npm ci
VITE_BASE_TO_FIXTURE_MM=420.255,-156.675,95.006 \
VITE_TABLE_ORIGIN_MM=420.255,-156.675,95.006 \
npm run dev -- --host 0.0.0.0
```

## 2. Main PC: 실측 파라미터와 빌드

**실기 연결 전** Main PC의 `weld-made-real-motion`에서 실행한다. 프로필 값을 묻는
프롬프트에는 현장에서 측정한 u/r 배열을 **m 단위 쉼표 구분**으로 입력한다.
임의의 숫자나 Virtual TCP `246.98 mm`를 복사하지 않는다.

```bash
cd /home/rokey/collaboration/weld-made-real-motion
read -rp 'tool_profile_u_m (m, 쉼표 구분): ' WELD_TOOL_U_M
read -rp 'tool_profile_r_m (m, 쉼표 구분): ' WELD_TOOL_R_M
export WELD_TOOL_U_M WELD_TOOL_R_M
python3 - <<'PY'
import math, os
from pathlib import Path
import yaml

def numbers(name):
    values = [float(v.strip()) for v in os.environ[name].split(',')]
    if not values or not all(math.isfinite(v) for v in values):
        raise SystemExit(f'{name}: 실측 유한값이 필요합니다')
    return values
u, r = numbers('WELD_TOOL_U_M'), numbers('WELD_TOOL_R_M')
if len(u) != len(r) or u[0] < 0 or any(b <= a for a, b in zip(u, u[1:])) or any(v <= 0 for v in r):
    raise SystemExit('u/r 길이가 같고, u는 0 이상 증가, r은 모두 양수여야 합니다')
p = Path('ws_cobot1/src/contact_scan_bringup/config/real.yaml')
text = p.read_text()
for key, values in (('tool_profile_u_m', u), ('tool_profile_r_m', r)):
    marker = f'    # {key}:'
    matches = [line for line in text.splitlines() if line.startswith(marker)]
    if len(matches) != 1:
        raise SystemExit(f'{key}: 원본 주석 줄을 찾을 수 없습니다. 원본 파일을 확인하세요')
    replacement = f'    {key}: ' + yaml.safe_dump(values, default_flow_style=True).strip()
    text = text.replace(matches[0], replacement, 1)
p.write_text(text)
print('실측 툴 외형 저장:', list(zip(u, r)))
PY
```

`real.yaml`의 `base_to_fixture`, `tip_radius_m` 두 절,
`weld_manager.tool_roll_deg`, `top_line_offset_dir`, `robot_manager.path_min_z_m`을
현장 측정과 [phase 2 도달성 기록](../phase2/measurements-20260923.md)에 맞춰
검토한다. **L1·L5는 9/23 배치의 45° 자세에서 도달하지 못했다.** L0 후퇴점과
L6 접근 1의 도달성은 실기에서 아직 확인되지 않았다. 접근점이 막히면 문서 D34에
따라 `top_line_offset_dir: vertical`을 검토한다. 수치를 고친 뒤 다시 빌드·재기동한다.

```bash
source /opt/ros/jazzy/setup.bash
source /home/rokey/ws_cobot_pjt/ws_dsr/install/setup.bash
cd /home/rokey/collaboration/weld-made-real-motion/ws_cobot1
colcon build --base-paths src --build-base build_p2_real \
  --install-base install_p2_real --symlink-install --parallel-workers 2
source install_p2_real/setup.bash
colcon test --build-base build_p2_real --install-base install_p2_real \
  --packages-select robot_manager weld_manager mqtt_bridge contact_scan_bringup
colcon test-result --test-result-base build_p2_real --verbose
```

## 3. Main PC: 실기 드라이버 → TCP → 자체 노드

이하 로봇 명령은 현장 담당자가 직접 실행한다. 각 ROS 터미널에서 동일한 환경을 설정한다.

```bash
source /opt/ros/jazzy/setup.bash
source /home/rokey/ws_cobot_pjt/ws_dsr/install/setup.bash
source /home/rokey/collaboration/weld-made-real-motion/ws_cobot1/install_p2_real/setup.bash
export ROS_DOMAIN_ID=30
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
```

먼저 Web PC 브로커와 로봇의 실제 주소를 확인한다.

```bash
nc -vz $WEB_PC 1883
ping -c 3 192.168.1.100
```

**터미널 A**, 실기 드라이버:

```bash
ros2 launch m0609_rg2_bringup bringup.launch.py \
  mode:=real host:=192.168.1.100 port:=12345 model:=m0609
```

드라이버가 완전히 준비된 뒤 **터미널 B**, Tool/TCP 재등록:

```bash
cd /home/rokey/collaboration/weld-made-real-motion
python3 docs/env/apply_tool_tcp.py
# 마지막 줄 OK: tool=rg2_probe, tcp=rg2_probe_tip [0.0, 0.0, 252.12] 확인
```

탐침을 교체·재파지했다면 [TCP 보정 절차](../env/tool-tcp-register.md)와
[README의 x/y 확인](../../README.md)을 따른다. `apply_tool_tcp.py`의 마지막 줄이
OK가 아니면 이동 명령으로 넘어가지 않는다. 그 뒤 **터미널 C**:

```bash
ros2 launch contact_scan_bringup bringup.launch.py \
  source:=robot_force broker_host:=$WEB_PC
```

별도 **터미널 D**에서 6개 노드와 실측 파라미터를 확인한다.

```bash
ros2 node list | rg 'robot_manager|contact_detector|safety_monitor|scan_manager|mqtt_bridge|weld_manager'
ros2 action list | rg '/robot/execute_path|/weld/run|/weld/home'
ros2 param get /weld_manager tool_profile_u_m
ros2 param get /weld_manager tool_profile_r_m
ros2 param get /weld_manager tilt_deg
ros2 param get /robot_manager path_min_z_m
ros2 topic echo /robot/status --once
ros2 topic echo /safety/status --once
```

Web PC 모니터에는 `conn/ros`, `robot/status`, `scan/state`, `safety/status`,
`weld/state`가 보여야 한다. `connected=true`, `latched=false`인지 확인한다.

## 4. Web PC: 스캔하여 이번 부재의 scan ID 확보

큐브가 움직였으면 반드시 새 스캔을 쓴다. 현장 사람이 스캔을 시작한다.
Web PC 터미널에서:

```bash
WEB=http://127.0.0.1:8000
SCAN_REPLY=$(curl -sS -X POST "$WEB/commands/scan/start" \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"real-weld","payload":{}}')
printf '%s\n' "$SCAN_REPLY" | python3 -m json.tool
SCAN_REQUEST_ID=$(printf '%s' "$SCAN_REPLY" | python3 -c 'import json,sys; print(json.load(sys.stdin)["request_id"])')
```

스캔을 지켜보고 완료 후:

```bash
curl -sS "$WEB/commands/$SCAN_REQUEST_ID" | python3 -m json.tool
SCAN_ID=$(curl -sS "$WEB/commands/$SCAN_REQUEST_ID" | \
  python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["status"]=="SUCCEEDED"; print(d["result"]["scan_id"])')
printf '이번 scan ID: %s\n' "$SCAN_ID"
```

Main PC에서 해당 `scan_id`의 `result.json`이 있는지 확인한다. 두 PC의 `SCAN_ID`
값을 일치시킨다. `""`(최신 결과 자동 선택) 대신 **방금 검증한 ID**를 쓴다.

```bash
SCAN_ID='Web PC에서 확인한 실제 scan ID'
test -f "$HOME/scan_results/real/$SCAN_ID/result.json"
```

## 5. Web PC: 용접 모션을 단계별로 실행

각 요청 직후 MQTT 모니터의 `cmd/ack`, `weld/state`, `weld/result`,
`weld/command_result`를 보고, 아래 조회에서 `SUCCEEDED` 또는 실패 이유를 확인한다.
`weld/result` 파일은 Main PC의
`~/scan_results/real/<scan_id>/weld/<weld_id>.json`에 저장된다.

먼저 **L0 한 선**, 수직·직선·5 mm/s로 접근과 복귀를 확인한다. 진폭과 pitch가 모두
0이면 직선이다. 이것은 실기 motion 명령이므로 로봇 앞에서 담당자가 직접 실행한다.

```bash
WELD_REPLY=$(curl -sS -X POST "$WEB/commands/weld/start" \
  -H 'Content-Type: application/json' \
  -d "{\"session_id\":\"real-weld\",\"payload\":{\"scan_id\":\"$SCAN_ID\",\"start_line\":0,\"end_line\":0,\"config\":{\"tilt_deg\":0,\"weave_amplitude_mm\":0,\"weave_pitch_mm\":0,\"weld_speed_mm_s\":5}}}")
printf '%s\n' "$WELD_REPLY" | python3 -m json.tool
WELD_REQUEST_ID=$(printf '%s' "$WELD_REPLY" | python3 -c 'import json,sys; print(json.load(sys.stdin)["request_id"])')
```

완료 후 확인:

```bash
curl -sS "$WEB/commands/$WELD_REQUEST_ID" | python3 -m json.tool
```

`status=SUCCEEDED`, `result.success=true`, `weld/result.lines[0].status=DONE`,
`weld/state.phase=DONE`을 확인한다. 다음 단계는 **45° L0 한 선**, 위빙 없이
접근·후퇴와 툴 간섭을 확인한다. 명령 형식은 위와 같고 config만
`"tilt_deg":45`로 바꾼다.

45° L0 확인 명령:

```bash
WELD_REPLY=$(curl -sS -X POST "$WEB/commands/weld/start" \
  -H 'Content-Type: application/json' \
  -d "{\"session_id\":\"real-weld\",\"payload\":{\"scan_id\":\"$SCAN_ID\",\"start_line\":0,\"end_line\":0,\"config\":{\"tilt_deg\":45,\"weave_amplitude_mm\":0,\"weave_pitch_mm\":0,\"weld_speed_mm_s\":5}}}")
WELD_REQUEST_ID=$(printf '%s' "$WELD_REPLY" | python3 -c 'import json,sys; print(json.load(sys.stdin)["request_id"])')
# 모션 종료 뒤
curl -sS "$WEB/commands/$WELD_REQUEST_ID" | python3 -m json.tool
```

L0 두 자세가 통과하고 툴 외형·도달성을 확인한 뒤 **위빙 L0 한 선**을 실행한다:

```bash
WELD_REPLY=$(curl -sS -X POST "$WEB/commands/weld/start" \
  -H 'Content-Type: application/json' \
  -d "{\"session_id\":\"real-weld\",\"payload\":{\"scan_id\":\"$SCAN_ID\",\"start_line\":0,\"end_line\":0,\"config\":{\"tilt_deg\":45,\"weave_amplitude_mm\":2,\"weave_pitch_mm\":4,\"weld_speed_mm_s\":10}}}")
WELD_REQUEST_ID=$(printf '%s' "$WELD_REPLY" | python3 -c 'import json,sys; print(json.load(sys.stdin)["request_id"])')
curl -sS "$WEB/commands/$WELD_REQUEST_ID" | python3 -m json.tool
```

한 선이 끝난 뒤 결과를 다시 확인한다. 나머지는 **실측 배치에서 도달 가능하고
툴 간섭 검사를 통과한 선만** 같은 형식의 `start_line`·`end_line`을 같은 번호로
설정해 한 선씩 진행한다. 9/23 배치에서 L1·L5는 45°로 도달 불가였으며,
L7의 J6 롤은 현장 확인 전까지 실행 범위에 넣지 않는다. 전 구간 확인 후에만
`start_line=0,end_line=7`로 전체 시나리오를 요청한다. 이 경우 L1·L5가
`FAILED`이고 다른 선이 `DONE`이면 전체 `success=false`가 정상적인 부분 결과다.

모든 필요한 선의 접근 자세·툴 간섭·J6 롤을 확인한 뒤 **전체 8선 시나리오**를
실행할 때는 다음 명령을 쓴다. 이 단계는 L1·L5가 `FAILED`로 남을 수 있으므로
`weld/result`의 선별 상태를 확인한다.

```bash
WELD_REPLY=$(curl -sS -X POST "$WEB/commands/weld/start" \
  -H 'Content-Type: application/json' \
  -d "{\"session_id\":\"real-weld\",\"payload\":{\"scan_id\":\"$SCAN_ID\",\"start_line\":0,\"end_line\":7,\"config\":{\"tilt_deg\":45,\"weave_amplitude_mm\":2,\"weave_pitch_mm\":4,\"weld_speed_mm_s\":10}}}")
WELD_REQUEST_ID=$(printf '%s' "$WELD_REPLY" | python3 -c 'import json,sys; print(json.load(sys.stdin)["request_id"])')
# 모션 종료 뒤
curl -sS "$WEB/commands/$WELD_REQUEST_ID" | python3 -m json.tool
WELD_ID=$(curl -sS "$WEB/commands/$WELD_REQUEST_ID" | \
  python3 -c 'import json,sys; print(json.load(sys.stdin)["result"]["weld_id"])')
printf 'weld ID: %s\n' "$WELD_ID"
```

Main PC에서 `WELD_ID`를 같은 값으로 두고 기록 파일을 확인한다.

```bash
SCAN_ID='위에서 확인한 실제 scan ID'
WELD_ID='Web PC에서 확인한 실제 weld ID'
python3 -m json.tool "$HOME/scan_results/real/$SCAN_ID/weld/$WELD_ID.json"
```

모션 중지와 안전복귀는 **서로 별도 명령**이다. 중지는 자동 복귀하지 않는다.

```bash
curl -sS -X POST "$WEB/commands/weld/stop" \
  -H 'Content-Type: application/json' -d '{"session_id":"real-weld","payload":{}}'
# /weld/state가 STOPPED이고 로봇 정지가 확인된 뒤 필요한 경우에만:
curl -sS -X POST "$WEB/commands/weld/home" \
  -H 'Content-Type: application/json' -d '{"session_id":"real-weld","payload":{}}'
```

물리적인 급박한 상황에서는 펜던트·E-stop을 사용한다. 안전 래치가 걸렸다면
원인과 로봇 정지 상태를 확인하기 전에는 재시작하지 않는다.

## 6. 종료와 검증 범위

모션과 로봇 정지를 확인한 뒤 Vite → 자체 노드 → 드라이버 순서로 각 터미널에서
Ctrl+C로 종료한다. Docker는 필요할 때만 `docker compose down`으로 종료하며
`-v`는 쓰지 않는다.

Virtual 검증은 2026-09-29에 P1 21/21점, P2 8/8선, P4 REST→MQTT→ROS→MQTT
L0 완료(`weld_id=20260929-024702-0837`)를 확인했다. 새 Virtual 세션에서
`/commands/weld/home`은 `SUCCEEDED`, L0 이동 중 `/commands/weld/stop`은
`STOPPING → STOPPED`와 `SUCCEEDED`를 확인했다. 브리지 테스트 46개,
FastAPI 테스트 9개가 통과했다. 실기에서의 L0 후퇴점·L6 접근 1 도달성과
툴 외형 값, 위빙 실행 시간은 아직 측정되지 않았다.
