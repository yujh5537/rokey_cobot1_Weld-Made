uint8 LEVEL_OK=0
uint8 LEVEL_WARN=1
uint8 LEVEL_STOP=2

builtin_interfaces/Time stamp
uint8 level
uint16 reason_code          # ReasonCode 4xx. OK = 0
bool stop_required          # 이 상태에서 /robot/stop 을 요청했음
bool stop_confirmed         # 요청한 정지가 /robot/status 로 확인됨
bool latched                # true 면 scan_manager 는 시작·재시작을 거절
uint32 motion_id            # 이상 판정 시점의 RobotSample.motion_id. 없으면 0
geometry_msgs/Point position  # 이상 판정 시점의 TCP 위치 (RobotSample.frame_id 기준)
bool position_valid
string detail               # 예: "force 32.1 N > 30 N"
