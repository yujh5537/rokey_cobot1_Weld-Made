# WeldLine.msg — 용접선 1개의 계획과 결과 (phase 2)
uint8 STATUS_NOT_ATTEMPTED=0   # 아직 안 함
uint8 STATUS_DONE=1            # 끝까지 지나감
uint8 STATUS_FAILED=2          # 실패 (reason_code)
uint8 STATUS_STOPPED=3         # 중지로 중단
uint8 STATUS_SKIPPED=4         # start_line 앞이라 건너뜀
uint8 index                    # 0~7 (weld-motion.md 의 표)
Segment seam                   # 이음선 = 부재 모서리 (작업대 좌표, m). 세로선은 bottom_margin 만큼 짧다
uint8 status
uint16 reason_code             # ReasonCode. 성공 = 0
string detail
geometry_msgs/Pose stop_pose   # FAILED · STOPPED 일 때 멈춘 자리 (frame_id 는 WeldResult.frame_id)
bool stop_pose_valid
builtin_interfaces/Time started_at
builtin_interfaces/Time finished_at
