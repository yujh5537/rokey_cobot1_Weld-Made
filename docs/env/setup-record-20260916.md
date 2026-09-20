# 협동1 프로젝트 환경설정 기록 (2026-09-16)

강사님 강의안 5개(환경설정1~5)를 순서대로 진행하고, 업그레이드와 재부팅 뒤 재검증까지 마친 기록입니다.

- PC: `<user>@<host>` (Ubuntu 24.04 메인 PC)
- 대상: Doosan M0609 + OnRobot RG2 그리퍼

---

## 1. 최종 상태 요약

| 항목 | 상태 |
|---|---|
| Ubuntu / ROS2 / Python | 24.04.4 LTS / jazzy / 3.12.3 (강의안 기준 일치, 변경 없음) |
| ROS_DOMAIN_ID | **30** (A-3 / C-3조) |
| ROS_DISCOVERY_SERVER | 해제됨 (TurtleBot4 설정 비활성화) |
| RMW_IMPLEMENTATION | rmw_fastrtps_cpp |
| Docker | 29.8.1, docker 그룹 가입 완료 (sudo 없이 사용) |
| 두산 에뮬레이터 | `doosanrobot/dsr_emulator:3.0.1` (1.83GB) |
| ws_dsr 빌드 | 35개 패키지, 실패 0건 |
| idc_ws 빌드 | 6개 패키지, 실패 0건 (업그레이드 후 재빌드) |
| Virtual 모드 | DRCF 연결, 컨트롤러 2개 active, RViz 정상, dance 정상 (에러 0건) |
| apt | full-upgrade 392개 완료 후 재부팅. 잔여 5개는 netplan/dnsmasq phasing으로 ROS와 무관 |
| venv | `~/venvs/rokey_venv`가 .bashrc에서 자동 활성화됨 (기존 유지) |

---

## 2. 강의안별 진행 내용

### 강의안 1: 수업 환경 구성 (Ubuntu)
시스템 정보, ROS2 버전, Python 버전을 확인했습니다. 모두 기준과 일치해서 재설치하지 않았습니다.

### 강의안 2: 디렉토리 구조
강사님 구조를 그대로 따라 아래와 같이 생성했습니다.

```
~/ws_cobot_pjt
├── DartPlatform      # Dart Simulator
├── backend/app       # FastAPI / Flask
├── docker
├── docs              # 스크립트, 문서 (setup_sudo.sh, upgrade_apt.sh)
├── frontend
├── ws_cobot1         # ROS2 프로젝트 워크스페이스
│   ├── doc
│   └── src           # ※ 아직 비어 있음
└── ws_dsr            # RG2 그리퍼 연동 로봇 실행환경
    └── src           # cobot_rg2 클론
```

### 강의안 3: RG2 그리퍼 포함 Simulator 설치
1. 클론: `git clone https://github.com/ahnisinc/cobot_rg2.git src`
   - 구성: `doosan-robot2`, `onrobot-ros2`, `rg2` (m0609_rg2_bringup), `rokey`
2. 의존성: rosdep으로 13개 설치 (moveit 계열, ros2_control 계열)
3. 에뮬레이터: Docker Engine(공식 저장소) 설치 후 `install_emulator.sh`로 이미지 pull
4. 빌드: 강의안대로 `--symlink-install` 없이 `colcon build`
   - 경고는 deprecated/unused 수준이며, 빌드 로그의 "error" 문자열은 boost 헤더 경로라 무시해도 됩니다.
   - PYTHONPATH용 경로 `install/dsr_common2/lib/dsr_common2/imp/`가 생성된 것 확인 (DSR_ROBOT2.py 등)

### 강의안 4: .bashrc 구성
**추가한 블록 (파일 맨 끝):**

```bash
# 협동1 프로젝트 (Doosan M0609 + RG2 그리퍼)
export ROS_DOMAIN_ID=30
export PYTHONPATH=$PYTHONPATH:$HOME/ws_cobot_pjt/ws_dsr/install/dsr_common2/lib/dsr_common2/imp

alias sod='source ~/ws_cobot_pjt/ws_dsr/install/setup.bash'
alias sodvir='ros2 launch m0609_rg2_bringup bringup.launch.py mode:=virtual host:=127.0.0.1 port:=12345 model:=m0609'
alias sodreal='ros2 launch m0609_rg2_bringup bringup.launch.py mode:=real host:=192.168.1.100 port:=12345 model:=m0609'

tb4-on() {   # TurtleBot4 환경 임시 복귀 (해당 터미널에서만)
  source /etc/turtlebot4_discovery/setup.bash
  ros2 daemon stop >/dev/null 2>&1
  echo "[tb4-on] TurtleBot4 모드 ..."
}
```

**비활성화한 기존 설정:** 모두 `#[TB4-off 2026-09-16] ` 접두사로 주석 처리했습니다.
- `source /etc/turtlebot4_discovery/setup.bash`: 이 파일이 DOMAIN_ID=2와 디스커버리 서버 192.168.109.105:11811을 강제로 지정해서 두산 로봇 통신을 방해하기 때문입니다.
- alias `sd`, `ed`, `vd`, `ssh-robot`, `robot-*`
- 함수 `undock`, `dock`, `loc`, `nav`, `rv`

**유지한 설정:** venv 활성화, `/opt/ros/jazzy`, colcon-argcomplete, `turtlebot4_ws`와 `idc_ws` 오버레이 source, `cb`, `sis`, `sb`, `eb`, `vb`, `ros-restart`, `rosenv`, `hw-local`

**백업:** `~/.bashrc.bak.20260916_095656`

### 강의안 5: VirtualMode로 두산 로봇 동작
```bash
# 터미널 1
sod
sodvir

# 터미널 2
sod
ros2 run dsr_example dance
```
검증 결과: `Connected to DRCF`, `joint_state_broadcaster`와 `dsr_controller2` 모두 active, RViz(OpenGL 4.6) 정상, movej/movel/move_periodic 호출 정상.

> ⚠️ **Real 모드에서는 dance를 절대 실행하지 않기.** TCP 설정이 잘못되어 있으면 로봇이 바닥에 부딪힙니다.

---

## 3. 자주 쓰는 명령

```bash
sod                      # ws_dsr 환경 source
sodvir                   # Virtual 모드 브링업
sodreal                  # Real 모드 브링업 (192.168.1.100)
echo $ROS_DOMAIN_ID      # 30 확인

# 노드 / 컨트롤러 확인 (네임스페이스 /dsr01)
ros2 node list
ros2 control list_controllers -c /dsr01/controller_manager
ros2 topic echo /dsr01/joint_states --once

# 에뮬레이터 컨테이너
docker ps                         # dsr01_emulator 확인
docker rm -f dsr01_emulator       # 비정상 종료 후 남은 컨테이너 정리

# TurtleBot4 작업이 필요할 때 (해당 터미널에서만)
tb4-on
```

---

## 4. 트러블슈팅 기록

| 증상 | 원인 | 해결 |
|---|---|---|
| rosdep 설치 중 `404 Not Found` 대량 발생 | apt 인덱스가 오래되어 저장소에서 이미 삭제된 구버전 .deb를 요청함 (ROS 저장소는 구버전을 주기적으로 삭제) | `sudo apt-get update` 후 `rosdep update`, 그다음 `rosdep install` |
| 에뮬레이터 설치 스크립트 실패 | Docker 미설치 | Docker Engine 공식 저장소로 설치하고 docker 그룹에 추가 |
| docker 명령에 권한 오류 | 그룹 가입이 현재 세션에 반영되지 않음 | 재로그인/재부팅, 또는 해당 터미널에서 `newgrp docker` |
| 새 터미널에서도 DOMAIN_ID=2, 디스커버리 서버가 보임 | .bashrc 수정 전에 열어둔 터미널이 옛 환경을 가지고 있음 | 새 터미널을 열거나 재로그인 |
| `ros2 node list`가 비어 있는데 토픽은 수신됨 | ros2 daemon에 이전 도메인 상태가 남아 있음 | `ros2 daemon stop; ros2 daemon start` (또는 `ros-restart`) |
| `ros2 control list_controllers`가 서비스를 못 찾음 | 컨트롤러 매니저가 `/dsr01` 네임스페이스에 있음 | `-c /dsr01/controller_manager` 옵션 지정 |
| 일반 `apt upgrade`에서 ros2-controllers, linux-firmware가 보류됨 | 의존 패키지를 새로 설치해야 해서 kept back 처리됨 | `sudo apt-get full-upgrade` (제거 0개임을 시뮬레이션으로 확인) |
| 브링업 종료 후 프로세스/컨테이너가 남음 | launch 비정상 종료 | 남은 `ros2_control_node`, `*_state_publisher` 프로세스 종료 후 `docker rm -f dsr01_emulator` |

---

## 5. 만들어둔 파일

- `~/ws_cobot_pjt/docs/setup_sudo.sh`: apt update, rosdep, Docker 설치, 에뮬레이터 설치를 한 번에 실행 (조원 환경 구축에 재사용 가능)
- `~/ws_cobot_pjt/docs/upgrade_apt.sh`: apt update 후 full-upgrade
- `~/.bashrc.bak.20260916_095656`: 변경 전 .bashrc 백업

---

## 6. 되돌리기 / 다음 할 일

**TurtleBot4 설정 영구 복구**
```bash
sed -i 's/^#\[TB4-off 2026-09-16\] //' ~/.bashrc
# 이후 협동1 블록의 ROS_DOMAIN_ID=30 줄은 주석 처리 필요
```

**다음 할 일**
- [ ] `ws_cobot1/src`에 프로젝트 패키지 생성
- [ ] 조원들과 디렉토리 구조와 ROS_DOMAIN_ID 공유 (조 내 분리가 필요하면 31~39 사용)
- [ ] Real 모드 연결 전에 TCP 설정 확인
