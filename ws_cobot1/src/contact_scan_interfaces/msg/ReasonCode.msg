# ReasonCode.msg — 상수 전용. reason · error · reason_code · code 필드는 모두 이 표를 쓴다.
# 출처: docs/contracts/ros-interfaces.md 6.1절. v0.1 이후 번호는 추가만 하고 바꾸지 않는다.

# 0
uint16 OK=0                     # 정상 / 사유 없음

# 1xx 요청 거절
uint16 BUSY=100                 # 동작 중
uint16 INVALID_REQUEST=101      # 필드 누락 · 형식 오류 · 만료
uint16 INVALID_VALUE=102        # 범위 밖 설정값
uint16 SAFETY_LATCHED=103       # 안전 래치 중
uint16 ROBOT_DISCONNECTED=104   # 드라이버 미연결
uint16 NO_RESUMABLE_SCAN=105    # 재개할 기록 없음
uint16 DUPLICATE_REQUEST=106    # request_id 중복
uint16 NOT_SUPPORTED=107        # 미구현 절차
uint16 PARAM_SET_FAILED=108     # 다른 노드 파라미터 갱신 실패

# 2xx 동작 종료
uint16 STOP_REQUESTED=200       # 작업 중지 요청
uint16 CANCELED=201             # Action 취소
uint16 MAX_DISTANCE=202         # 최대 이동 거리 안 미접촉 · 미소실
uint16 TIMEOUT=203              # 제한 시간 초과
uint16 ROBOT_ERROR=204          # 드라이버 · 로봇 오류
uint16 DROP_LIMIT=205           # 하강량 제한 도달

# 3xx 접촉 · 툴
uint16 NO_CONTACT=300           # DESCEND 미접촉
uint16 NO_EDGE=301              # SLIDE 미소실
uint16 TOOL_REG_SUSPECT=302     # 무접촉 외력 허용치 초과
uint16 TARE_FAILED=303          # 기준값 설정 실패 (아래 세분 코드에 해당하지 않는 경우)
uint16 ROBOT_MOVING=304         # 정지 조건 미충족
uint16 TARE_UNSTABLE=305        # 구간 중 외력이 불안정
uint16 TARE_TIMEOUT=306         # 제한 시간 안에 샘플 수 미달
uint16 NO_SAMPLE=307            # /robot/sample 이 들어오지 않음

# 4xx 안전
uint16 OVER_FORCE=400           # 과대 외력
uint16 OVER_SPEED=401           # 속도 한계
uint16 OUT_OF_WORKSPACE=402     # 작업영역 · 하강 한계
uint16 SAMPLE_STALE=403         # 샘플 최신성 위반
uint16 ROBOT_STATUS_LOST=404    # 로봇 상태 미수신
uint16 HB_EXPIRED=405           # 웹 heartbeat 만료
uint16 CONDITION_ACTIVE=406     # 래치 해제 요청 시 조건이 아직 참
uint16 STOP_UNCONFIRMED=407     # 정지를 요청했지만 완료(connected && !moving)를 확인하지 못함

# 5xx 형상
uint16 INVALID_SHAPE=500        # 폭 0 이하 · 높이 음수
uint16 INSUFFICIENT_POINTS=501  # 5점 미확보
