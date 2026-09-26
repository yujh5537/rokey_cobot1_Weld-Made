# WeldConfig.msg — 용접 설정 (phase 2). *_set=true 인 항목만 적용 (부분 갱신, ScanConfig 와 같은 규약)
# 값은 설계 출발값이며 실측으로 조정한다. 기본값은 weld_manager 파라미터(contact_scan_bringup/config/*.yaml)
float64 weld_speed_mps        # 용접선 위 TCP 속도
bool    weld_speed_set
float64 travel_speed_mps      # 선 사이 이동(안전 높이) 속도
bool    travel_speed_set
float64 standoff_m            # 팁이 이음선에서 툴 축 방향으로 물러나는 거리 (접촉하지 않는다)
bool    standoff_set
float64 weave_amplitude_m     # 위빙 진폭 (이음선 기준 ±). 0 이면 직선
bool    weave_amplitude_set
float64 weave_pitch_m         # 위빙 반주기 간격 (진행 방향). 0 이면 직선
bool    weave_pitch_set
float64 tilt_deg              # 툴 축이 연직에서 바깥으로 기우는 각. 두 면의 법선을 이등분하는 면 안에서 기운다
bool    tilt_set
