# 최신 main + 웹 용접 효과 + P1/P2/P4 Virtual 실행

통합 브랜치 `weld-web-main-p4`는 `origin/main` (`7254dbb`) 위에 다음을 적용한다.

| 출처 | 가져온 내용 |
|---|---|
| `b4e780c` | P4 FastAPI·MQTT 브리지 (`cmd/weld/*`, `weld/*`) |
| `dbd4883`, `9a26815` | 웹 3D 용접 효과, Virtual 보조 스크립트·문서 |
| `7957f54` | ExecutePath 예외 때 정지 확인 |
| 이 통합 브랜치 | 웹 **용접 시작/중지**를 P4 API로 연결하고 8선의 실제 TCP 샘플로 불꽃·자국 표시 |

사용자가 언급한 `euiseok/20260927-docs-p1-euiseok`에는 웹 용접 코드가 없다.
웹 코드는 `euiseok/web-weld-20260929`의 `dbd4883`에 있다.
`/sim-weld` 서버는 DB 시연용 윗면 4변 프리뷰다. 이 문서의 P4는 표준 fixture의
**윗면 4선 + 세로 4선**을 실행한다. 버튼 이름은 그대로다. P4는 실기 경로에도
연결될 수 있으므로 **자동 용접은 하지 않고**, 형상이 보인 뒤 사용자가
**용접 시작**을 눌러야 한다.

## 실행

[기존 Virtual P1/P2/P4 절차](virtual-p1-p2-p4.md)의 0절에서 실기 드라이버와
기존 에뮬레이터를 확인한다. 아래의 새 빌드를 사용하고, 기존 문서의 2~4절은
다음 두 경로와 새 install 경로로 바꿔 실행한다. `mode:=virtual host:=127.0.0.1`과
`ROS_DOMAIN_ID=36`을 유지하고, 실기 드라이버가 있으면 실행하지 않는다.

```bash
REPO=/tmp/weld-web-main-p4
RUNTIME=/tmp/weld-p1-p2-runtime
```

ROS를 별도 빌드한다. `origin/main`의 P1/P2와 이 브랜치의 P4가
포함되어야 하므로 예전 `/tmp/weld-p1-p2-install`을 source하지 않는다.

```bash
source /opt/ros/jazzy/setup.bash
source ~/ws_cobot_pjt/ws_dsr/install/setup.bash
cd /tmp/weld-web-main-p4/ws_cobot1
colcon build --base-paths src \
  --build-base /tmp/weld-web-main-build \
  --install-base /tmp/weld-web-main-install \
  --symlink-install --parallel-workers 2
source /tmp/weld-web-main-install/setup.bash
export ROS_DOMAIN_ID=36 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
unset ROS_DISCOVERY_SERVER
```

[기존 절차 2절](virtual-p1-p2-p4.md#2-fixture설정launch-생성)의 Python 블록을 실행할 때
`repo = Path('/tmp/weld-web-main-p4')`로 바꾼다. `result.json`은 표준 fixture
`20260921-131938-1493`을 사용한다. 3절의 FastAPI 컨테이너는
`/tmp/weld-web-main-p4/backend/app`을 `/app`에 마운트해 포트 8001로 실행한다.
Virtual 드라이버, 6개 노드, 초기 관절 홈은 4절 그대로다.

별도 웹 터미널에서 다음을 실행한다. 5173 포트가 사용 중이면 해당 Vite 프로세스의
소유자를 확인하고, 이 실행은 5174 같은 빈 포트를 지정한다.

```bash
cd /tmp/weld-web-main-p4/frontend
npm ci
VITE_API_TARGET=http://127.0.0.1:8001 \
VITE_SIM_FIXTURE_URL=/fixtures/standard-20260921.json \
VITE_BASE_TO_FIXTURE_MM=425,-184,400 \
VITE_TABLE_ORIGIN_MM=425,-184,400 \
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

브라우저 `http://127.0.0.1:5173`에서 WebSocket 연결과 표준 부재 형상을 확인한다.
Virtual 표준 fixture의 상판·부재 밑면은 Base Z=400 mm이고, 웹 작업대 높이는
94 mm 그대로다. 로봇 모델 베이스만 화면의 작업대 바닥 Z=306 mm에 놓는다.
ROS의 `base_link`와 TCP 텔레메트리는 그대로 Base Z=0을 사용한다.
따라서 이 베이스 이동은 **화면 모델만** 306 mm 올린다. 모델 탐침 끝과
`robot/sample` TCP 표시·용접 좌표 사이에는 같은 오프셋이 남는다. 실제 TCP 정렬까지
맞추려면 fixture와 로봇 베이스의 공통 좌표계를 별도로 보정해야 한다.
초기 관절 홈 성공과 `/safety/status.latched=false`를 확인한 뒤 **용접 시작**을 누른다.
웹은 화면에 표시된 scan ID로 `/commands/weld/start`에 `start_line=0, end_line=7`을 보낸다.
불꽃과 자국은 `weld/state.phase=WELDING` 동안 들어온 `robot/sample` TCP 위치를
형상의 해당 모서리에 맞춰 그린다. **용접 중지**는 `/commands/weld/stop`이고,
중지 뒤 **안전복귀**는 `/commands/weld/home`이다. 중지가 자동 복귀를 실행하지 않는다.

API에서 직접 실행하려면 기존 절차 7절과 같은 요청을 0~7선으로 보낸다.

```bash
curl -sS -X POST http://127.0.0.1:8001/commands/weld/start \
  -H 'Content-Type: application/json' \
  -d '{"payload":{"scan_id":"20260921-131938-1493","start_line":0,"end_line":7}}'
```

반환된 `request_id`는 `/commands/<request_id>`에서 완료 상태를 확인한다.
성공 기준은 `status=SUCCEEDED`, `weld/command_result.success=true`, 결과 파일
`results/20260921-131938-1493/weld/<weld_id>.json`의 8선 `DONE`이다.

## 검증 범위

2026-09-29의 기존 `b4e780c` Virtual 실행에서 P4 8선 요청
`cd07edca-6dc1-4ddc-956d-de1c306356fb`는 `SUCCEEDED`, weld ID
`20260929-104832-0462`의 8선 모두 `DONE`이었다. 이 기록은 **이 통합 브랜치의
최신 main 기반 ROS 재실행 결과는 아니다.** 이후 이 통합 브랜치에서 웹 프록시를
통해 8선을 다시 시작했고 L0~L2는 완료됐으나 L3의 10/17점에서 **중지 요청**을
받아 `STOP_REQUESTED(200)`로 끝났다. 따라서 통합 브랜치의 8/8 완주는 아직
검증하지 않았다. 웹 빌드·lint, P4 화면 좌표 테스트 3개, ROS 테스트 593개는 통과했다. 실기 적용은 [실기 실행 문서](real-weld-motion.md)의
계측·안전 조건을 먼저 따른다.
