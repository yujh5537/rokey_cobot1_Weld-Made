# WeldResult.msg — 용접 결과 (phase 2). 작업 종료 시 1회 (실패 · 중단 포함). 미측정값은 NaN + *_valid=false
string weld_id
string scan_id
builtin_interfaces/Time stamp
bool success                   # 8 선(start_line 부터) 전부 DONE
uint16 reason_code             # ReasonCode. 성공 = 0
string detail
string frame_id                # seam · stop_pose 의 프레임 ('workpiece_fixture')
geometry_msgs/Vector3 base_to_fixture   # 이 결과가 쓴 작업대 원점의 Base 좌표 (m). 웹이 Base 샘플과 겹쳐 그릴 때 쓴다
uint8 start_line
uint8 end_line
WeldLine[8] lines
WeldConfig config              # 적용 설정 스냅샷 (전부 *_set=true)
builtin_interfaces/Time started_at
builtin_interfaces/Time finished_at
