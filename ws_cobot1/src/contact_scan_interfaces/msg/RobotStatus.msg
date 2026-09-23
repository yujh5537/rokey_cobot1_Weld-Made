builtin_interfaces/Time stamp
bool connected              # dsr_controller2 서비스 응답 가능
bool moving                 # 정지 완료 = connected && !moving
bool error
uint16 error_code           # ReasonCode, 0 = 없음
bool compliance_active      # 순응 제어(task_compliance_ctrl) 켜짐
bool force_ctrl_active      # 힘 제어(set_desired_force) 켜짐
uint32 motion_id            # 실행 중인 goal. 없으면 0
uint8 operation             # RobotSample.OP_* 와 같은 값

# SLIDE 의 누름 목표. 서로 다른 세 값을 섞지 않으려고 따로 싣는다 (v0.1.17)
string slide_mode                 # 'force' = 순응 · 힘 제어(REL), 'step' = 위치 제어 스텝. 그 밖은 ''
float64 slide_force_setpoint_n    # force 모드 설정 증분 힘(DR_FC_MOD_REL). step 모드 · 모름이면 NaN
float64 slide_force_baseline_n    # 이번 SLIDE 를 시작한 시점의 기준 Fz. 모르면 NaN
float64 slide_force_estimate_n    # 추정 최종 누름 = 기준 + 설정. **추정값이며 실측이 아니다.** 모르면 NaN
float64 step_press_lo_n           # step 모드 목표 누름 ΔFz 하한. force 모드 · 모름이면 NaN
float64 step_press_hi_n           # step 모드 목표 누름 ΔFz 상한. force 모드 · 모름이면 NaN

string detail
