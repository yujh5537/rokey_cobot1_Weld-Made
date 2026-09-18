string session_id
uint32 seq
builtin_interfaces/Time stamp           # 웹 발신 시각 (웹 PC 시계)
builtin_interfaces/Time received_stamp  # mqtt_bridge 수신 시각 (ROS 시계). 만료 판정은 이 값 기준
