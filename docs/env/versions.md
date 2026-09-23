# 실행 환경 버전

| 항목 | 값 | 확인 |
|---|---|---|
| 메인 PC OS / ROS / Python | Ubuntu 24.04 / Jazzy / 3.12 | 2026-09-16 현지 PC |
| ROS_DOMAIN_ID | 30 (조 내 분리 필요 시 31~39) | 노드 테스트는 31~39 중 **비어 있는 번호를 골라 락으로 점유한다**(`contact_scan_testing`, #126). 손으로 고르지 않는다. 30 은 조 공용(실기 · 팀원의 Virtual)이라 테스트가 쓰지 않는다 |
| RMW | rmw_fastrtps_cpp | |
| ws_dsr 소스 | github.com/ahnisinc/cobot_rg2 @ `4d5657f` (4d5657f36a160eedb533ab1c975cd8a30c3e53b2, 2026-08-15) | 2026-09-19 학민 PC. `doosan-robot2` · `rg2` · `onrobot-ros2`는 수정 없음. 개인 실험 패키지 `rokey`에 로컬 수정, `tactile_probe`는 미추적 (이 프로젝트가 쓰지 않는다) |
| 두산 에뮬레이터 | doosanrobot/dsr_emulator:3.0.1 (image `878b8557dfa2`) | 2026-09-19 학민 PC |
| DART / DRCF | Virtual 에뮬레이터: DRCF `GF03020000`, DRFL `GL013303`. **실기 컨트롤러: DRCF `GF02120100`, DRFL `GL013303`** (`sodreal` 로그, `mode : real`) | 2026-09-19 학민 PC, 브링업 로그 · 실기 2026-09-21 확인(로그 118개, 09-16~21) |
| 로봇 IP (real) | 192.168.1.100:12345 | |
| 웹 PC: Mosquitto / PostgreSQL / Python / Java / Node | TBD (의석) | |

ws_dsr 구축은 `setup-record-20260916.md`를 따른다. 팀원 4명의 ws_dsr 커밋 해시가 같은지 Day 1에 확인한다.
