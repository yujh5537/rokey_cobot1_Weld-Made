# API 호출 확인 로그 [E19] (T04, 담당 학민)

BRD는 "매뉴얼 설명 / 소스 확인 / 실제 PC 호출 확인 / 실기 성능 검증"을 구분한다. 이 표는 세 번째(실제 PC 호출 확인)만 기록한다. 성공했다는 것은 호출이 된다는 뜻이지 접촉 검출 성능이 검증됐다는 뜻이 아니다.

환경: <PC 이름> / 패키지 버전·커밋: <ws_dsr의 git rev> / DRCF·DART 버전: <>

| API / 서비스 | 호출 경로 (Python 래퍼 / service / drl_script_run) | Virtual | Real | 날짜 | 비고·로그 |
|---|---|---|---|---|---|
| get_tool_force | | 미확인 | 미확인 | | |
| get_current_posx | | 미확인 | 미확인 | | |
| amovel | | 미확인 | 미확인 | | |
| motion/move_stop (DR_QSTOP) | | 미확인 | 미확인 | | |
| task_compliance_ctrl / release_compliance_ctrl | | 미확인 | 미확인 | | Virtual에서 힘 제어가 정상 동작하지 않을 수 있음 [E10] |
| set_desired_force (DR_FC_MOD_REL) / release_force | | 미확인 | 미확인 | | **mod 의미는 헤더에서 확인**(`dsr_msgs2/srv/detail/set_desired_force__struct.h`): ABS(0)=절대값, REL(1)=**호출 시점 상태 기준 상대값**. 실기에서 ① SLIDE 시작 직후 `|F − F0|` 1회, ② `DR_FC_MOD_ABS` 가 실제로 동작하는지 확인한다 (#73) |
| check_position_condition | | 미확인 | 미확인 | | |
| drl_script_run (set_external_force_reset 경유) | | 미확인 | 미확인 | | |
| /onrobot/sendCommand (RG2 파지) | | 미확인 | 미확인 | | 실제 노드·네임스페이스 대조 필요 |
| 샘플 실제 수신 주기 | | 미측정 | 미측정 | | 설정상 50 Hz와 구분 (T08, T15) |
