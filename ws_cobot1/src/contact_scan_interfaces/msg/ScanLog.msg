uint8 LEVEL_INFO=0
uint8 LEVEL_WARN=1
uint8 LEVEL_ERROR=2

builtin_interfaces/Time stamp
string scan_id
uint8 level
uint8 phase                 # ScanState.PHASE_*
uint8 direction             # ScanState.DIR_*
uint32 motion_id
uint16 code                 # ReasonCode, 0 = 정보
string message
string frame_id
geometry_msgs/Pose pose     # 관련 좌표 (판정 좌표인지 정지 좌표인지 message 에 명시)
bool pose_valid
