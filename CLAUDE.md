# 접촉 탐색 기반 외곽 엣지·경로 후보 생성 시스템 (MVP 9/18~9/22)

M0609 + RG2(무센서 탐침)로 직육면체를 만져 윗면 1점·모서리 4점을 얻고, 외곽 엣지·경로 후보와 직육면체를 계산해 웹에 3D로 보여준다. 기준 문서는 `docs/BRD.md`(v3.0.0)이다.

## 레포 구조
- `ws_cobot1/src/` ROS 2 Jazzy 자체 패키지 (메인 PC). 패키지·담당은 `ws_cobot1/src/README.md`
- `backend/app` FastAPI, `backend/spring` Spring Boot, `frontend/` React+Three.js, `docker/` compose (웹 PC)
- `docs/contracts/` 모듈 간 계약. **코드보다 이 문서가 우선한다**
- `ws_dsr/`, `DartPlatform/`은 레포 밖(gitignore). 두산·RG2 제공 드라이버는 수정하지 않는다

## 명령
```bash
# ROS (ws_dsr을 먼저 source: alias sod)
cd ws_cobot1 && colcon build --symlink-install && source install/setup.bash
colcon test && colcon test-result --verbose
python3 -m pytest src/scan_manager/test -q        # 순수 계산 모듈, ROS 없이 실행
# 웹
docker compose -f docker/docker-compose.yml up -d
cd frontend && npm ci && npm run dev
```

## 절대 규칙
1. **실기 로봇 명령을 실행하지 않는다.** `sodreal`, `mode:=real`, 실기에 연결된 상태의 `ros2 service call`/`ros2 action send_goal`은 사람이 직접 한다. Claude는 Virtual Mode(`sodvir`)와 sim 입력원만 실행한다.
2. 순응·힘 제어를 켜는 코드는 반드시 `try/finally`로 해제한다(BRD 4.5.2). 예외 경로를 포함한 모든 종료 경로에서 해제되는지 테스트를 같이 쓴다.
3. 작업 중지·안전복귀·재시작은 서로 독립된 명령이다. 중지가 홈 복귀나 재시작을 자동으로 부르게 만들지 않는다.
4. 실패·미측정값을 0으로 저장하지 않는다. `None`/`NaN`/유효성 플래그로 구분한다.
5. `docs/contracts/`와 `contact_scan_interfaces/`는 이슈에 명시된 경우에만 고친다. 고칠 때는 계약 문서·인터페이스 패키지·`docs/contracts/CHANGELOG.md`를 한 PR에서 같이 바꾼다.
6. 이슈의 "수정 범위" 밖 파일은 고치지 않는다. 필요해 보이면 고치지 말고 PR 본문에 적는다.
7. 임계값·속도·힘·거리 같은 수치를 코드에 박지 않는다. ROS 파라미터(`contact_scan_bringup/config/*.yaml`)로 둔다. BRD의 수치는 "설계 출발값"이지 실측값이 아니다.

## 작업 방식
- 시작: `gh issue view <번호>`로 이슈를 읽고, 이슈가 가리키는 docs만 읽은 뒤 계획부터 제시한다.
- 브랜치: `t<이슈ID>-<짧은설명>` (예: `t13-execute-motion`). main 직접 푸시 금지.
- PR: 이슈 1개 = PR 1개. 변경 파일이 15개를 넘으면 쪼갠다. 본문에 `Closes #번호`.
- 단위: ROS 내부 m·rad·N, 웹 표시 mm (`docs/contracts/units-frames.md`). 변환은 경계(robot_manager, mqtt_bridge)에서만 한다.

## 어떤 작업에 어떤 문서를 읽나
| 작업 | 문서 |
|---|---|
| msg/srv/action, 토픽 이름 | `docs/contracts/ros-interfaces.md` |
| MQTT 토픽, JSON, 명령 ID | `docs/contracts/mqtt-schema.md` |
| 좌표계, TCP, 홈, 단위 | `docs/contracts/units-frames.md` |
| 노드 책임, 데이터 흐름 | `docs/architecture.md` |
| 요구사항 번호(4.x.x), TR, KPI | `docs/BRD.md` 해당 절만 |
| 두산 API 실제 동작 여부 | `docs/env/api-check-log.md` |
| 왜 이렇게 결정했나 | `docs/decisions/` |
