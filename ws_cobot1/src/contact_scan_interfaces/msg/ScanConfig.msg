# *_set=true 인 항목만 적용 (부분 갱신). 값은 설계 출발값이며 실측으로 조정한다.
# 접촉 판정 → contact_detector (over_force_n 은 safety_monitor 에도)
float64 contact_threshold_n
bool    contact_threshold_set
float64 edge_drop_m
bool    edge_drop_set
uint8   debounce_n
bool    debounce_set
float64 over_force_n
bool    over_force_set
# 모션 → scan_manager 가 ExecuteMotion goal 에 실음
float64 descend_speed_mps
bool    descend_speed_set
float64 slide_speed_mps
bool    slide_speed_set
float64 max_descend_m
bool    max_descend_set
float64 max_slide_m
bool    max_slide_set
float64 motion_timeout_s
bool    motion_timeout_set
float64 lift_height_m
bool    lift_height_set
# 힘/순응 → robot_manager (drop_limit_m 은 safety_monitor 에도)
float64 target_force_n     # robot_manager 파라미터 slide_target_force_n 으로 전파 (P01). 숫자는 그대로 전달된다
                           #   기준은 DR_FC_MOD_REL: set_desired_force 호출 시점의 힘에 더해지는 값이다.
                           #   tare 대비 절대 누름 힘이 아니다. SLIDE 는 DESCEND 가 접촉으로 끝난 직후에 오므로
                           #   실제 누름 = 접촉력 + 이 값. REL 유지 여부는 실기 뒤에 정한다 (#73)
bool    target_force_set
float64 drop_limit_m
bool    drop_limit_set
