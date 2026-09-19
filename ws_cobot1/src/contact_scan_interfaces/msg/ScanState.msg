uint8 PHASE_IDLE=0          # 대기
uint8 PHASE_PREPARING=1     # 시작 조건 점검 · tare
uint8 PHASE_TOP_SEARCH=2    # 윗면 탐색
uint8 PHASE_EDGE_SEARCH=3   # 모서리 탐색 n/4 (밀기 + 방향 전환 이동)
uint8 PHASE_GEOMETRY=4      # 형상 생성
uint8 PHASE_DONE=5          # 완료
uint8 PHASE_ERROR=6         # 오류 (실패 · 안전 이상)
uint8 PHASE_STOPPING=7      # 중지 요청 접수 · 정지 완료 대기
uint8 PHASE_STOPPED=8       # 중단됨
uint8 PHASE_HOMING=9        # 홈 복귀 진행 (안전복귀 · 스캔 마무리 공용)
uint8 PHASE_RESUMING=10     # 재시작 진행
uint8 DIR_NONE=0
uint8 DIR_POS_X=1
uint8 DIR_NEG_X=2
uint8 DIR_POS_Y=3
uint8 DIR_NEG_Y=4

builtin_interfaces/Time stamp
string scan_id              # IDLE 이면 ""
uint8 phase
uint8 direction             # 모서리 탐색 중에만 유효
uint8 progress              # 확보한 모서리 수 n (0~4)
uint8 progress_total        # 4
uint32 motion_id            # 진행 중 ExecuteMotion goal. 없으면 0
