# TCP pose + 외력 통합 샘플. 각 취득 시각을 별도 보존한다 (BRD 4.1.6).
# operation: robot_manager 가 지금 실행 중인 ExecuteMotion goal 의 종류. ExecuteMotion.action 의 OP_* 와 같은 값.
uint8 OP_NONE=0
uint8 OP_MOVE_TO=1
uint8 OP_DESCEND=2
uint8 OP_SLIDE=3
uint8 OP_HOME=4

uint64 sample_id                    # robot_manager 발급, 발행마다 +1
string frame_id                     # pose · wrench 의 기준 프레임 ('base_link' 가칭)
geometry_msgs/Pose pose             # TCP pose. m, quaternion
builtin_interfaces/Time pose_stamp  # get_current_posx 응답을 받은 시각
geometry_msgs/Wrench wrench         # 외력 추정. N, N·m. get_tool_force(ref=DR_BASE)
builtin_interfaces/Time force_stamp # get_tool_force 응답을 받은 시각
bool valid                          # 두 값 모두 정상 취득이면 true
uint32 motion_id                    # 실행 중인 goal 의 motion_id. 없으면 0
uint8 operation                     # 실행 중인 goal 의 종류. 없으면 OP_NONE
