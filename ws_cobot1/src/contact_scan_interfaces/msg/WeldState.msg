# WeldState.msg — 용접 진행 상태 (phase 2). 변경 시 + 주기 발행 (STATE QoS)
uint8 PHASE_IDLE=0          # 대기
uint8 PHASE_PREPARING=1     # 시작 조건 점검 · 결과 읽기 · 경로 생성
uint8 PHASE_APPROACH=2      # 안전 높이 이동 · 접근점 하강
uint8 PHASE_WELDING=3       # 용접선 위 이동 (ExecutePath)
uint8 PHASE_RETREAT=4       # 후퇴 · 안전 높이 상승
uint8 PHASE_DONE=5          # 완료 (마무리 홈 복귀 포함)
uint8 PHASE_ERROR=6         # 오류 (실패 · 안전 이상)
uint8 PHASE_STOPPING=7      # 중지 요청 접수 · 정지 완료 대기
uint8 PHASE_STOPPED=8       # 중단됨
uint8 PHASE_HOMING=9        # 홈 복귀 진행 (안전복귀 · 마무리 공용)
uint8 LINE_NONE=255         # line_index 가 없을 때
builtin_interfaces/Time stamp
string weld_id              # IDLE 이면 ""
string scan_id              # 용접 대상 스캔 결과
uint8 phase
uint8 line_index            # 진행 중인 용접선 0~7. 없으면 LINE_NONE
uint8 line_total            # 8
uint8 lines_done            # 완료한 용접선 수
float32 line_progress       # 진행 중인 선 안의 진행률 0.0~1.0 (WELDING 에서만 유효, 그 밖은 0)
uint32 motion_id            # 진행 중 ExecuteMotion · ExecutePath goal. 없으면 0
