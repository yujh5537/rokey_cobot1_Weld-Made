uint8 TYPE_CONTACT=0        # 접촉 발생 확정
uint8 TYPE_EDGE=1           # 접촉 소실 확정 = BRD 의 "엣지"
uint8 TYPE_OVER_FORCE=2     # 과대 외력

uint64 event_id             # contact_detector 발급, 발행마다 +1
string scan_id              # /scan/state 에서 받은 현재 scan_id. 없으면 ""
uint32 motion_id            # 판정에 쓴 RobotSample.motion_id 를 그대로 복사
uint64 sample_id            # 판정 샘플(= 조건이 처음 성립한 샘플)의 RobotSample.sample_id
uint8 type
string source               # 'robot_force' | 'sim' | 'robot_step' (robot_manager 스텝 모드 SLIDE 의 EDGE, v0.1.15)
string frame_id             # RobotSample 과 동일
geometry_msgs/Pose pose     # 판정 샘플의 TCP pose (≠ 확정 샘플, ≠ 정지 완료 좌표)
geometry_msgs/Wrench wrench # 판정 샘플의 외력
builtin_interfaces/Time pose_stamp     # 판정 샘플의 값
builtin_interfaces/Time force_stamp    # 판정 샘플의 값
builtin_interfaces/Time detect_stamp   # 판정을 확정한 시각 (확정 샘플. 연속 N 번째)
float64 force_delta_n       # 확정 샘플의 |F − F0|. OVER_FORCE 는 원시 |F|
float64 z_drop_m            # EDGE 판정 샘플의 실제 z 하강량. 그 외 type 은 NaN
bool z_drop_valid
uint8 debounce_count        # 판정을 확정한 연속 횟수
