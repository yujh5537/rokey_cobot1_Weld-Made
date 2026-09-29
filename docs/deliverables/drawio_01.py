"""산출물 01 시스템 아키텍처 drawio 를 만든다 → 01-system-architecture.drawio

형식은 docs/design/contact-scan-system-architecture-v1.6.drawio 를 따른다: PC 경계 3 구역(웹 PC · 메인 PC · 로봇 컨트롤러),
카드마다 왼쪽 입력 → 가운데 처리 로직 → 오른쪽 출력, 카드 사이 화살표 색 = 데이터 갈래.
쪽 2 개: 1. v1.7 (phase 2 포함 — "phase 2 (용접)" 레이어) · 2. v1.7 (1차만).
내용 근거: ws_cobot1/src · backend · frontend · docker (origin/main 2335057), docs/contracts v0.1.22, docs/phase2 v0.2.0,
          구현 PR #191 · #195~#197(머지 전). 카드 문장 끝의 절 번호는 BRD.
실행: python3 docs/deliverables/drawio_01.py
"""
import pathlib

from drawio_lib import CAT, P2, Page, char_w, plain, write_mxfile

HERE = pathlib.Path(__file__).resolve().parent
L2 = 'p2'
GAP_COLOR = CAT['gap']

# ── 카드 종류별 색 (v1.6 과 같은 값, phase 2 만 추가) ────────────────────────
KIND = {  # 머리띠 채움, 테두리, 글자, 열 머리 글자
    'human': ('#E3E7EC', '#A9B3BE', '#3A4550', '#3A4550'),
    'web': ('#F1DCEB', '#C79BBD', '#6E2E62', '#6E2E62'),
    'prov': ('#DCE2E9', '#94A0AE', '#333F4E', '#333F4E'),
    'ros': ('#D3DCF5', '#8C9CD2', '#22357F', '#22357F'),
    'robot': ('#CDE6E0', '#84B2A9', '#14564C', '#14564C'),
    'p2': ('#FAD9BB', P2, '#8A3D05', '#8A3D05'),
}
COLHEAD = {
    'human': ('입력 — 사람 · 수신', '처리 로직', '출력 — 요청 · 화면'),
    'web': ('입력 — REST 서버 · 구독', '처리 로직', '출력 — 발행 · 응답 · DB'),
    'prov': ('입력 — 받는 것', '처리', '출력 — 내보내는 것'),
    'ros': ('입력 — 구독 · 서비스/액션 서버', '처리 로직', '출력 — 발행 · 서비스/액션 호출'),
    'robot': ('입력', '처리', '출력'),
    'p2': ('입력 — 구독 · 서비스/액션 서버', '처리 로직', '출력 — 발행 · 서비스/액션 호출'),
}

CW = 1340                      # 카드 폭
IW, SW = 340, 420              # 입출력 상자 폭, 처리 상자 폭
COLX = [300, 1980, 3660]       # 열 왼쪽 x
ZX0, ZX1 = 60, 5300            # 구역 좌우
ROW_GAP = 240                  # 행 사이(가로 통로)
ITEM_GAP, STEP_GAP = 10, 22


def I(t, y='', u='', dash=False, p2=False):
    return dict(t=t, y=y, u=u, dash=dash, p2=p2)


def S(t, dia=False, p2=False, no=None, no_label='No', yes='Yes'):
    return dict(t=t, dia=dia, p2=p2, no=no, no_label=no_label, yes=yes)


# ═════════════════════════════════════════════════════════════════════════
# 카드 내용
# ═════════════════════════════════════════════════════════════════════════
CARDS = [
    # ── 웹 PC 1 행 ────────────────────────────────────────────────────────
    dict(key='REACT', row=0, col=0, kind='human',
         title='React + Three.js — 관제 화면',
         sub='브라우저 (사람이 보는 자리) · React 19 · Three.js 0.186 · Vite 개발 서버 :5173 (Docker 밖, npm run dev) · '
             '버튼 5 개 · 설정 등록 버튼 없음(TR-05) · 4.4',
         ins=[I('사용자 조작', '버튼 시작 · 중지 · 안전복귀 · 재시작 · 안전 해제', '안전 해제는 래치가 아닌 것이 확인되면 꺼진다(safety/status 미수신이면 켜짐) · 마우스 3D 회전 · 확대'),
              I('WS /ws', '{topic, payload} — scan/state · scan/result · scan/log · robot/sample · robot/joints · '
                'contact/event · safety/status · command/status', 'FastAPI 가 MQTT 원본을 중계 · 끊기면 "연결 안 됨"(다시 붙지 않음)'),
              I('3D 모델 · 환경변수', 'M0609 DAE · RG2 STL(GitHub raw) · VITE_BASE_TO_FIXTURE_MM', '작업대 원점이 없으면 결과 3D 를 숨긴다')],
         steps=[S('<b>①</b> 화면 6 구역 — 제어 버튼 · 현재 상태 · 외곽 엣지 · 경로 후보 표 · 명령 상태 이력 · 3D · 시간순 로그'),
                S('<b>②</b> 단계 표시 — scan/state 의 phase(한글) · 방향 · n/4 · scan_id. 새 작업이면 이전 결과만 지운다'),
                S('<b>③</b> 3D 로봇 — robot/joints(rad)로 M0609 관절, TCP 빨간 점 · 궤적(최근 1000 점) · 접촉점 노란 점'),
                S('<b>④</b> 결과 — 꼭짓점 8 개로 반투명 부재, edges 회색 · path_candidates 초록, base_to_fixture 만큼 옮김'),
                S('<b>⑤</b> 단위 — mm 소수 둘째 자리 · ROS (x, y, z) → Three (x, z, −y)'),
                S('<b>⑥</b> 버튼 → POST /commands/… {payload}(재시작은 scan_id) → command/status 로 접수 · 완료 · 실패 이력')],
         outs=[I('POST /commands/scan/{start, stop, home, resume} · /commands/safety/reset', 'JSON {payload, scan_id?}',
                 'FastAPI 로만 · Spring 은 부르지 않는다'),
               I('화면', '상태 · 경로 후보 표 · 3D · 로그 · 명령 이력', '사람이 보고 버튼을 누른다')],
         lin=[(0, 5), (1, 1), (2, 2)], lout=[(5, 0), (0, 1)]),

    dict(key='FAPI', row=0, col=1, kind='web',
         title='FastAPI — 명령 · 실시간 중계 · 측정 DB 쓰기',
         sub='웹 PC · Python 3.12 · FastAPI + uvicorn :8000 · Docker(weld_made_fastapi) · paho-mqtt · psycopg · '
             '로봇 모션은 직접 제어하지 않음 · 4.3.4 · 4.4.2',
         ins=[I('REST 명령', 'POST /commands/scan/{start, stop, home, resume, set_config} · /commands/safety/reset',
                '본문 {session_id?, payload, scan_id?}'),
              I('MQTT 구독 (QoS 1)', 'robot/# · scan/# · contact/# · safety/# · cmd/ack · hb/ros · conn/ros', '다시 연결되면 다시 구독'),
              I('WS /ws 접속', '브라우저', '받은 글은 읽고 버린다')],
         steps=[S('<b>①</b> REST 명령 → request_id(UUID v4) · timestamp_ms · schema_version "0.1" 을 붙여 cmd/… 발행 '
                  '(QoS 1 · retain=false)'),
                S('<b>②</b> 발행 결과 PUBLISHED / PUBLISH_ERROR → 메모리 명령 표 → WS command/status 방송 → REST 응답'),
                S('<b>③</b> MQTT 수신 → JSON 파싱 → {topic, payload} 그대로 모든 WS 클라이언트에 방송'),
                S('<b>④</b> cmd/ack → ACCEPTED · REJECTED (set_config · safety/reset 은 바로 SUCCEEDED) · '
                  'scan/command_result → SUCCEEDED · FAILED'),
                S('<b>⑤</b> DB 쓰기 — scan/result → scan_jobs · measurements · scan_configs(한 트랜잭션 upsert) · '
                  'contact/event → contact_events'),
                S('<b>⑥</b> 아직 없음 — hb/web · conn/web 발행, cmd/ack 대기 제한, 최신 상태 캐시, 명령 상태 영속화',)],
         outs=[I('MQTT 발행 cmd/scan/* · cmd/safety/reset', 'QoS 1 · retain=false · schema_version · request_id · '
                 'timestamp_ms · payload', '공통 필드는 docs/contracts/mqtt-schema.md 4 장'),
               I('WS /ws', '원본 토픽 + 가상 토픽 command/status', '브라우저로 방송'),
               I('DB upsert', 'scan_jobs · measurements · scan_configs · contact_events', 'psycopg · 메시지마다 연결 · 실패는 로그만'),
               I('REST 응답', '{status, topic, request_id, mqtt_rc, message}', '접수 ≠ 완료')],
         lin=[(0, 0), (1, 2), (2, 2)], lout=[(0, 0), (2, 1), (4, 2), (1, 3)]),

    dict(key='MQTT', row=0, col=2, kind='prov',
         title='MQTT Broker (Mosquitto) — 설치 · 설정 사용',
         sub='웹 PC · eclipse-mosquitto:2 · :1883 · Docker(weld_made_mosquitto) · 두 PC 사이 단일 중계 · 판단하지 않는다',
         ins=[I('FastAPI 발행', 'cmd/scan/* · cmd/safety/reset', '웹 명령'),
              I('mqtt_bridge 발행', 'robot/* · scan/* · contact/event · safety/status · cmd/ack · scan/command_result · '
                'hb/ros · conn/ros', '메인 PC 에서 · robot/status · scan/state · safety/status · conn/ros 는 retain')],
         steps=[S('<b>①</b> 리스너 TCP 1883 하나 · WebSocket · TLS 없음'),
                S('<b>②</b> allow_anonymous true — 인증 · ACL 없음(실습망 전제)'),
                S('<b>③</b> persistence — retain · QoS 1 대기 메시지를 볼륨(mosquitto_data)에 보관'),
                S('<b>④</b> retain 토픽을 새 구독자에게 넘긴다 · LWT 는 클라이언트가 등록(mqtt_bridge → conn/ros)')],
         outs=[I('→ FastAPI', '구독 필터 7 개', ''),
               I('→ mqtt_bridge', 'cmd/scan/+ · cmd/safety/reset · hb/web · conn/web', 'hb/web · conn/web 은 보내는 쪽이 아직 없다')],
         lin=[(0, 0), (1, 3)], lout=[(3, 0), (3, 1)]),

    # ── 웹 PC 2 행 ────────────────────────────────────────────────────────
    dict(key='SPRING', row=1, col=0, kind='web',
         title='Spring Boot — 업무 · 측정 이력',
         sub='웹 PC · Java 21 · Spring Boot 3.5 · :8080 · Docker(weld_made_spring) · JPA · 화면(React)과는 아직 연결 없음 · 4.3.4',
         ins=[I('REST 이력', 'GET /api/history/scans · /api/history/scans/{scanId}', '측정 이력 목록 · 상세'),
              I('REST 업무', 'GET · POST · PUT /api/workpieces · /api/work-orders · /by-workpiece/{id}', '대상물 · 작업 등록 · 수정'),
              I('REST 연결', 'GET · POST /api/work-orders/{id}/scans/{scanId}', '작업 ↔ 스캔 연결')],
         steps=[S('<b>①</b> 이력 — scan_jobs 최신순, 상세는 scan_jobs + measurements + scan_configs (없으면 404)'),
                S('<b>②</b> 대상물 · 작업 등록 — 필수값 없으면 400 · 중복 409 · 작업 초기 상태 READY'),
                S('<b>③</b> 연결 — 작업 · 스캔이 없으면 404, 이미 연결된 스캔이면 409'),
                S('<b>④</b> ddl-auto=none — 스키마는 init SQL · 응답은 camelCase JSON · contact_events 는 읽지 않는다')],
         outs=[I('REST JSON 응답', '201 · 400 · 404 · 409', '호출하는 화면은 아직 없다'),
               I('DB (JPA)', '쓰기 workpieces · work_orders · work_order_scans / 읽기 scan_jobs · measurements · scan_configs', '')],
         lin=[(0, 0), (1, 1), (2, 2)], lout=[(0, 0), (1, 1)]),

    dict(key='PG', row=1, col=1, kind='prov',
         title='PostgreSQL 16 — 결과 · 이력 저장소 (설치 · 설정 사용)',
         sub='웹 PC · postgres:16 · :5432 · Docker(weld_made_postgres) · DB contact_scan · 원격 조회용 — 재시작 원본은 메인 PC result_store',
         ins=[I('FastAPI upsert', 'scan_jobs · measurements · scan_configs · contact_events', 'scan/result · contact/event 받을 때'),
              I('Spring JPA', '업무 3 테이블 쓰기 · 측정 3 테이블 읽기', '')],
         steps=[S('<b>①</b> init 스크립트 001(측정) · 002(업무) — 빈 볼륨일 때만 실행'),
                S('<b>②</b> healthcheck pg_isready — FastAPI · Spring 은 healthy 뒤 기동'),
                S('<b>③</b> 테이블 7 — 측정 scan_jobs · measurements · scan_configs · contact_events + 업무 workpieces · '
                  'work_orders · work_order_scans'),
                S('<b>④</b> 미측정값은 NULL + *_valid — 0 으로 넣지 않는다(TR-10)')],
         outs=[I('조회 결과', 'SELECT → Spring 이력 API', '')],
         lin=[(0, 2), (1, 2)], lout=[(2, 0)]),

    # ── 메인 PC 1 행 ──────────────────────────────────────────────────────
    dict(key='SAF', row=2, col=0, kind='ros',
         title='safety_monitor — 소프트웨어 이상 감시',
         sub='메인 PC · rclpy (Jazzy) · 단일 스레드 · 순수 모듈 safety_core · 웹을 거치지 않고 로컬 정지 요청 · '
             '하드웨어 안전 대체 아님 · 4.5.3 · 4.5.4',
         ins=[I('/robot/sample', 'RobotSample (SENSOR) · pose · wrench · valid · operation', 'sub · 과대 외력 · 하강 제한 · 샘플 끊김'),
              I('/robot/status', 'RobotStatus (STATE) · connected · moving', 'sub · 정지 완료 확인 · 상태 끊김'),
              I('/safety/reset', 'ResetSafety (Service 서버)', '래치 해제 요청 · 조건이 사라졌을 때만'),
              I('SetParameters (P03)', 'over_force_n · drop_limit_m', 'scan_manager 가 SetConfig 를 전파'),
              I('/scan/state · /web/heartbeat (계약만)', 'ScanState · WebHeartbeat', '구독하지 않는다 — heartbeat 만료 405 · '
                '속도 401 · 작업영역 402 감시 없음', dash=True)],
         steps=[S('<b>①</b> 샘플 · 상태 수신 시각 기록 · 기동 뒤 3 s 는 끊김 감시 유예'),
                S('<b>②</b> 이상 조건 하나라도 참인가? — 과대 외력 |F| &gt; 30 N · 하강(SLIDE 첫 z 기준) &gt; 5 + 5 mm · '
                  '샘플 끊김 &gt; 500 ms · 상태 끊김 &gt; 500 ms', dia=True, no=0, no_label='No · 다음 샘플'),
                S('<b>③</b> Yes → 래치(첫 원인 유지) · /robot/stop 비동기 요청 (reason 400 · 205 · 403 · 404) — 웹 경유 없음'),
                S('<b>④</b> 정지 확인 — connected · !moving. 0.6 s 안에 못 하면 2 s 마다 다시 요청 · "물리 비상정지 필요할 수 있음"'),
                S('<b>⑤</b> /safety/status — 바뀌면 즉시 + 1 s 주기 · level OK · WARN · STOP'),
                S('<b>⑥</b> /safety/reset — 참인 조건이 남아 있으면 CONDITION_ACTIVE(406) 거절, 없으면 래치 해제(로봇은 안 움직임)')],
         outs=[I('/safety/status', 'SafetyStatus (STATE) · level · reason_code · stop_required · stop_confirmed · latched',
                 'pub → scan_manager · mqtt_bridge · (phase 2) weld_manager'),
               I('/robot/stop', 'StopRobot {requester=safety_monitor, reason}', 'Service 클라이언트 · 정지 경로 ③'),
               I('/safety/reset 응답', 'success · reason_code 0 · 406', '')],
         lin=[(0, 1), (1, 3), (2, 5), (3, 1)], lout=[(4, 0), (2, 1), (5, 2)]),

    dict(key='SM', row=2, col=1, kind='ros',
         title='scan_manager — 스캔 순서 상태기계 · 중지 · 안전복귀 · 재시작 · 형상 계산',
         sub='메인 PC · rclpy (Jazzy) · MultiThreadedExecutor · geometry_estimator · result_store 모듈 포함 · '
             '4.2 · 4.3 · 4.4.7 ~ 4.4.9',
         ins=[I('/scan/run · /scan/home · /scan/resume', 'RunScan · ReturnHome · Resume (Action 서버)',
                'goal 은 늘 받고 거절 사유는 Result(1xx) · cancel 은 거절'),
              I('/scan/stop', 'StopScan (Service 서버)', 'accepted = 접수 ≠ 정지 완료'),
              I('/scan/set_config', 'SetConfig (Service 서버) · *_set 인 값만', '휴지 phase 에서만'),
              I('/robot/status', 'RobotStatus (STATE) · connected · moving', '시작 조건 · 정지 완료 확인'),
              I('/robot/sample', 'RobotSample (SENSOR) · 마지막 유효 pose', 'v0.1.21 · 안전복귀 · 재시작의 올림 목표 · 측정에는 안 씀'),
              I('/contact/event', 'ContactEvent (EVENT) · event_id · motion_id · pose', '판정 좌표 = 측정값'),
              I('/safety/status', 'SafetyStatus (STATE) · latched · reason_code', '시작 · 재시작 관문 · 손상 의심 판정'),
              I('/weld/state', 'WeldState (STATE) · phase', '용접 중이면 START · RESUME 거절 601 (P5 #204, main)', p2=True)],
         steps=[S('<b>①</b> 시작 관문 — BUSY 100 → 쌍 108 → 값 102 → <font color="#C0600A">용접 중 601</font> → 안전 103 → '
                  '로봇 104 → scan_id 발급 → progress.json 기록 뒤 첫 모션'),
                S('<b>②</b> 준비 — MOVE_TO 기준점 → 정지 확인 → /contact/tare (F₀)'),
                S('<b>③</b> TOP_SEARCH — DESCEND → CONTACT 짝 이벤트의 판정 z = 윗면 z_top (없으면 300 · 203)'),
                S('<b>④</b> EDGE_SEARCH — +X → −X → +Y → −Y: 올림 → 원점 x · y → 첫 접촉 z + 1 mm 저속 → SLIDE → EDGE 짝 '
                  '(재하강 없음) · 실기는 스텝 모드'),
                S('<b>⑤</b> 모서리 4 점 모두 확보했는가?', dia=True, no=3, no_label='No · 다음 방향'),
                S('<b>⑥</b> GEOMETRY — 편향 보정 d = √(2rδ − δ²) → 윗면 사각형 · 경로 후보 4 · 직육면체(꼭짓점 8 · 모서리 12) → '
                  'result.json → /scan/result 1 회'),
                S('<b>⑦</b> 마무리 — 정지 좌표 z + lift → OP_HOME → DONE (여기서 실패해도 측정은 유효)'),
                S('<b>⑧</b> 작업 중지 — /robot/stop + goal cancel → connected · !moving 확인(5 s) → STOPPED, 못 하면 407 → '
                  'ERROR · 자동 홈 · 재시작 없음'),
                S('<b>⑨</b> 안전복귀 — 손상 의심(400 · 205 · 402) · 위치 모름이면 107 → 수직 올림 → 도착 확인 → OP_HOME'),
                S('<b>⑩</b> 재시작 — STOPPED 또는 ERROR(403 · 404 · 407 만, /safety/reset 뒤) → 지금 자리 올림 → tare → '
                  '남은 방향만 · 확정값 유지'),
                S('<b>⑪</b> SetConfig — 휴지일 때만 → 자기 값 6 + 전파 P03 → P02 → P01 → 되읽기(어긋나면 108)')],
         outs=[I('/scan/state', 'ScanState (STATE) · phase · direction · progress n/4 · motion_id', '바뀌면 즉시 + 1 s 주기'),
               I('/scan/result', 'ScanResult (STATE) · z_top · x/y± · W/L/H · vertices 8 · edges 12 · path_candidates 4 · *_valid',
                 '작업 끝에 1 회 · 실패 · 중단도 NaN + valid=false'),
               I('/scan/log', 'ScanLog (LOG) · level · code · message · pose', '시간순'),
               I('/robot/execute_motion', 'ExecuteMotion (Action 클라이언트) · operation · target · speed · max_distance · timeout',
                 '한 번에 하나 · Result = 정지 pose + 사유'),
               I('/robot/stop', 'StopRobot {requester=scan_manager}', '정지 경로 ① · 응답을 기다리지 않는다'),
               I('/contact/tare', 'TareForce (Service 클라이언트)', '무접촉 · 정지 상태의 F₀'),
               I('*/set_parameters', 'rcl_interfaces SetParameters · P01 · P02 · P03', 'SetConfig 전파 · 두 겹 감시 같은 값'),
               I('result_store (로컬 원본)', '&lt;result_dir&gt;/&lt;scan_id&gt;/progress.json · result.json',
                 'tmp → fsync → replace · 재시작의 원본(웹 DB 와 구분) · 4.4.7')],
         lin=[(0, 0), (1, 7), (2, 10), (3, 0), (4, 8), (5, 2), (6, 0), (7, 0)],
         lout=[(0, 0), (5, 1), (6, 2), (1, 3), (7, 4), (1, 5), (10, 6), (5, 7)]),

    dict(key='MB', row=2, col=2, kind='ros',
         title='mqtt_bridge — ROS 2 ↔ MQTT 변환',
         sub='메인 PC · rclpy (Jazzy) · paho-mqtt · 토픽 이름표는 코드에 고정 · 단위 변환은 여기서만(m ↔ mm) · 4.4.2 · 4.6 · 4.7',
         ins=[I('MQTT cmd/scan/+ · cmd/safety/reset', 'QoS 1 · {schema_version, request_id, timestamp_ms, payload}', '웹 명령'),
              I('MQTT hb/web · conn/web', '형식 검사만', '웹이 아직 보내지 않는다'),
              I('ROS 구독 8', '/robot/sample · /robot/status · /scan/state · /scan/result · /scan/log · /contact/event · '
                '/safety/status · /dsr01/joint_states', 'QoS 는 contact_scan_qos 와 같은 정의')],
         steps=[S('<b>①</b> 명령 공통 검사 — 형식 → schema "0.1" → UUID v4 → 중복(최근 100) → 만료 5 s (stop 은 제외) · '
                  '실패면 cmd/ack 101 · 106'),
                S('<b>②</b> 호출 — start · home · resume → Action goal / stop · set_config · reset → Service (mm → m) · 서버 없으면 107'),
                S('<b>③</b> 접수 → cmd/ack — goal 수락 · 서비스 응답 그대로 · set_config 는 applied(mm)'),
                S('<b>④</b> 완료 → scan/command_result — Action Result · stop 은 /scan/state 가 STOPPED · ERROR 가 될 때'),
                S('<b>⑤</b> ROS → JSON — m → mm · NaN → null · enum 이름(모르면 UNKNOWN_&lt;n&gt;, v0.1.22) · published_at_ms'),
                S('<b>⑥</b> 솎기 — robot/sample 10 Hz · robot/joints · gripper_joints 20 Hz · scan/result 중복 방지'),
                S('<b>⑦</b> 생존 — hb/ros 1 Hz · conn/ros retain + LWT · hb/web 을 받았을 때만 /web/heartbeat')],
         outs=[I('MQTT robot/* · scan/* · contact/event · safety/status', 'QoS 0 · 1 · retain(status · state)', '표시 · DB 쓰기의 원천'),
               I('MQTT cmd/ack · scan/command_result', '접수 ≠ 완료', 'start 의 거절(103 등)은 ack 뒤 command_result 로 온다'),
               I('MQTT hb/ros · conn/ros', '1 Hz · retain + LWT', ''),
               I('Action 클라이언트', '/scan/run · /scan/home · /scan/resume', ''),
               I('Service 클라이언트', '/scan/stop · /scan/set_config · /safety/reset', ''),
               I('/web/heartbeat', 'WebHeartbeat (HEARTBEAT)', '받는 노드 없음 — 계약만', dash=True)],
         lin=[(0, 0), (1, 6), (2, 4)], lout=[(4, 0), (3, 1), (6, 2), (1, 3), (1, 4), (6, 5)]),

    # ── 메인 PC 2 행 ──────────────────────────────────────────────────────
    dict(key='CD', row=3, col=0, kind='ros',
         title='contact_detector — 접촉 · 접촉 소실 · 과대 외력 판정',
         sub='메인 PC · rclpy (Jazzy) · 순수 모듈 detector_core · 입력원 robot_force | sim · 로봇을 움직이지 않음 · 4.1 · TR-01',
         ins=[I('/robot/sample', 'RobotSample (SENSOR) · pose · wrench · valid · motion_id · operation', '판정 입력 전부'),
              I('/scan/state', 'ScanState (STATE) · scan_id', '이벤트 태깅'),
              I('/contact/tare', 'TareForce (Service 서버) · duration_s', 'F₀ · 툴 등록 점검'),
              I('SetParameters (P02)', 'contact_threshold_n · edge_drop_m · debounce_n · over_force_n', '')],
         steps=[S('<b>①</b> 최신성 — 100 ms 넘게 묵은 샘플은 버림 · motion_id 가 바뀌면 연속 횟수 초기화'),
                S('<b>②</b> OVER_FORCE — 모든 operation, 원시 |F| &gt; 30 N 이면 확정 (초과 구간마다 1 회)'),
                S('<b>③</b> operation 은? DESCEND → ④ · SLIDE → ⑤ · 그 밖 → OVER_FORCE 만', dia=True, yes='DESCEND'),
                S('<b>④</b> CONTACT — 이동 기준 F₀(최근 1.0 ~ 0.3 s 평균) 대비 |F − F₀| &gt; 3 N 이 3 회 연속 (출발 5.5 s 안은 6 N)'),
                S('<b>⑤</b> EDGE — 누름 확인(z 멈춤 + x · y 이동) 뒤 z 가 추세선보다 0.5 mm 넘게 3 회 연속 낮음 · '
                  '<b>실기 스텝 모드의 EDGE 는 robot_manager 가 낸다</b>'),
                S('<b>⑥</b> 이벤트 — 판정 샘플의 pose · motion_id 를 복사, 확정 시각 detect_stamp → /contact/event 1 회'),
                S('<b>⑦</b> tare — 구간 평균 F₀ · RMS &gt; 1 N 305 · |F₀| &gt; 6 N 302(툴 등록 의심) · 샘플 부족 306')],
         outs=[I('/contact/event', 'ContactEvent (EVENT) · type CONTACT · EDGE · OVER_FORCE · pose · motion_id · z_drop',
                 'pub → robot_manager · scan_manager · mqtt_bridge'),
               I('/contact/tare 응답', 'success · offset(F₀) · error · std_norm_n', '')],
         lin=[(0, 0), (1, 5), (2, 6), (3, 3)], lout=[(5, 0), (6, 1)]),

    dict(key='RM', row=3, col=1, kind='ros',
         title='robot_manager — 모션 · 힘/순응 제어 · 상태 수집 (제공 드라이버 래퍼)',
         sub='메인 PC · rclpy (Jazzy) · 두산 dsr01 · m0609 · <b>드라이버를 부르는 유일한 노드</b> · 단위(mm · deg ↔ m · quaternion) · '
             '4.1.6 · 4.2 · 4.5',
         ins=[I('/robot/execute_motion', 'ExecuteMotion (Action 서버) · operation · target · direction · speed · max_distance',
                '한 번에 하나 · cancel 허용'),
              I('/robot/stop', 'StopRobot (Service 서버) · requester · reason', '접수만 · 정지 완료는 /robot/status 로'),
              I('/contact/event', 'ContactEvent (EVENT) · type · motion_id', 'CONTACT · EDGE 는 motion_id 대조 뒤 정지, '
                'OVER_FORCE 는 바로 · 스텝 모드에서는 EDGE 무시'),
              I('SetParameters (P01)', 'slide_target_force_n · drop_limit_m', '다음 goal 부터'),
              I('/robot/execute_path', 'ExecutePath (Action 서버) · waypoints · speed · path_tolerance_m',
                'phase 2 · PR #191 머지 전 · ExecuteMotion 과 goal 자리 공유', p2=True),
              I('두산 서비스 응답', 'posx · tool_force · robot_state', '')],
         steps=[S('<b>①</b> 50 Hz 샘플 — posx → tool_force → (5 회마다) robot_state 를 한 줄로 차례 호출 · '
                  'm · quaternion 변환 · 실패는 NaN + valid=false'),
                S('<b>②</b> 상태 10 Hz — moving(0.3 s 창 0.2 mm) · connected · 실행 중 motion_id · operation'),
                S('<b>③</b> goal 을 받을 수 있는가? 실행 중 · 미연결 · 남은 정지 요청(OP_HOME 은 예외, #115) · 값 오류면 REJECT', dia=True,
                  yes='Yes · 수락'),
                S('<b>④</b> 이동(ASYNC) — MOVE_TO move_line ABS · DESCEND · SLIDE move_line REL · HOME move_joint home_joint_deg'),
                S('<b>⑤</b> SLIDE — <b>step(실기)</b>: 0.5 mm 긁고 멈춰 힘 읽기 → 3 ~ 7 N 유지 → 소실 → 0.1 mm 다듬기 → '
                  'EDGE 발행 / force(sim): 순응 + −z 목표 힘'),
                S('<b>⑥</b> 감시 20 ms — 취소 · 정지 요청 · 이벤트 · 하강 &gt; 5 mm(205) · 시간 초과 · 미연결 → move_stop'),
                S('<b>⑦</b> finally — release_force → release_compliance_ctrl (실패면 compliance_released=false) → Result'),
                S('<b>⑧</b> ExecutePath — 경유점마다 move_line → 멈춤 → 허용 오차 확인 · 출발점 · 경유점 z &lt; path_min_z_m 이면 604',
                  p2=True)],
         outs=[I('/robot/sample', 'RobotSample (SENSOR) · pose · wrench · valid · motion_id · operation',
                 '50 Hz 설정 · 실기 약 43 Hz'),
               I('/robot/status', 'RobotStatus (STATE) · connected · moving · compliance_active · slide_mode', '10 Hz + 바뀔 때'),
               I('/contact/event', 'ContactEvent · 스텝 모드 EDGE (source=robot_step)', 'v0.1.15'),
               I('ExecuteMotion Result', 'pose(정지 좌표) · reason · reason_code · event_id · compliance_released', ''),
               I('두산 서비스 10', 'move_line · move_joint · move_stop · task_compliance_ctrl · set_desired_force · '
                 'release_force · release_compliance_ctrl · get_current_posx · get_tool_force · get_robot_state',
                 'CallQueue 로 한 줄 · RG2 호출은 코드에 없다')],
         lin=[(0, 2), (1, 5), (2, 5), (3, 4), (4, 7), (5, 0)], lout=[(0, 0), (1, 1), (4, 2), (6, 3), (3, 4)]),

    dict(key='DRV', row=3, col=2, kind='prov',
         title='제공 드라이버 (외부) — doosan-robot2 · OnRobot RG2',
         sub='메인 PC · dsr_bringup2 · dsr_hardware2 · dsr_msgs2 · 실행명 dsr_controller2 · 네임스페이스 dsr01 · '
             '설치 · 설정 사용 · 수정하지 않음',
         ins=[I('dsr_msgs2 서비스', '/dsr01/dsr_controller2/{motion, force, aux_control, system}/…', 'robot_manager 만 호출'),
              I('RG2 명령 (계약만)', '/onrobot/sendCommand', '탐침을 쥔 채 운용 · 코드에서 부르지 않는다', dash=True)],
         steps=[S('<b>①</b> dsr_controller2 — DRCF TCP/IP 로 컨트롤러와 명령 · 상태를 주고받는다'),
                S('<b>②</b> joint_state_broadcaster → /dsr01/joint_states (표시 전용)'),
                S('<b>③</b> mode:=virtual 에뮬레이터 — 힘 제어 미동작 가능 · Virtual 종단 시험용')],
         outs=[I('서비스 응답', 'posx · 외력 추정 · 로봇 상태', '→ robot_manager'),
               I('/dsr01/joint_states', 'sensor_msgs/JointState (SENSOR)', '→ mqtt_bridge → robot/joints'),
               I('DRCF TCP/IP', '모션 · 순응 · 힘 제어 명령', '→ M0609 컨트롤러')],
         lin=[(0, 0), (1, 0)], lout=[(0, 0), (1, 1), (0, 2)]),

    # ── 메인 PC 3 행 (phase 2) ────────────────────────────────────────────
    dict(key='WM', row=4, col=1, kind='p2', p2=True,
         title='weld_manager [phase 2] — 스캔 결과로 모서리 8 개 용접 모션',
         sub='메인 PC · rclpy · 계약 docs/phase2 v0.2.0 · 구현 PR #195 → #196 → #197 머지 전 · Virtual 8 선 완주 246 s(sim 박스) · '
             '실기 9/29 · 접촉 · 힘 제어 없음',
         ins=[I('/weld/run · /weld/home', 'RunWeld · ReturnHome (Action 서버) · scan_id("" = 최신) · start_line · end_line', ''),
              I('/weld/stop', 'StopWeld (Service 서버)', '휴지면 accepted=false · OK'),
              I('/scan/state', 'ScanState (STATE) · phase', '스캔 중 600 · 없거나 5 s 넘으면 101'),
              I('/robot/status · /robot/sample · /safety/status', 'RobotStatus · RobotSample · SafetyStatus',
                '연결 104 · 정지 확인 · 시작 위치 · 툴 점검 302 · 실패 뒤 팁 z · 래치 103'),
              I('result.json (파일)', 'scan_manager result_store 가 쓴 것', '모서리 12 · z_top · base_to_fixture')],
         steps=[S('<b>①</b> 시작 관문 — BUSY 100 → 파라미터 102 → /scan/state 101 → 스캔 중 600 → 래치 103 → 연결 104'),
                S('<b>②</b> result.json 읽기 — 없음 · 무효 602 · 선 범위 603'),
                S('<b>③</b> 8 선 계획 — 모서리 edges[0..3, 8..11] · 45° 툴 자세 · 스탠드오프 3 mm · 위빙 2 mm / 4 mm 지그재그 경유점'),
                S('<b>④</b> 경로가 안전한가? z ≥ 지지면 + 5 mm · xy 부재 ±100 mm · 세로선 툴 외형 — 아니면 604', dia=True),
                S('<b>⑤</b> 선마다 — 접근(z_safe) → ExecutePath [p0 … pN, 후퇴점] → 후퇴 · 204 로 끝나면 안전 높이 위에서는 '
                  'FAILED 로 적고 계속(D33), 아래면 복구 뒤 ERROR'),
                S('<b>⑥</b> 남은 선이 있는가?', dia=True, no=4, no_label='Yes · 다음 선', yes='No'),
                S('<b>⑦</b> 끝 — /weld/result · 파일 → HOMING(z_safe → OP_HOME) → DONE · /weld/stop 은 정지 확인 → STOPPED')],
         outs=[I('/weld/state · /weld/result · /weld/log', 'WeldState · WeldResult · ScanLog', '→ scan_manager(601) · mqtt_bridge(계약만)'),
               I('/robot/execute_path', 'ExecutePath (Action 클라이언트) · waypoints · speed · path_tolerance_m', ''),
               I('/robot/execute_motion', 'ExecuteMotion · OP_MOVE_TO · OP_HOME', '접근 · 후퇴 · 복구 · 홈'),
               I('/robot/stop', "StopRobot {requester='weld_manager'}", ''),
               I('결과 파일', '&lt;result_dir&gt;/&lt;scan_id&gt;/weld/&lt;weld_id&gt;.json', '')],
         lin=[(0, 0), (1, 6), (2, 0), (3, 0), (4, 1)], lout=[(6, 0), (4, 1), (4, 2), (6, 3), (6, 4)]),

    # ── 로봇 컨트롤러 ─────────────────────────────────────────────────────
    dict(key='CTRL', row=5, col=2, kind='robot',
         title='M0609 컨트롤러 (DRCF) + 하드웨어 — 팔 · RG2 · 무센서 탐침 팁 · 작업대',
         sub='로봇 컨트롤러 · 안전 기능(비상정지 · 보호 정지 · 충돌 감지 · 협동 속도)은 여기가 담당 · 소프트웨어는 이 설정을 바꾸지 않는다 (4.5 ※)',
         ins=[I('DRCF TCP/IP', '모션 · 순응 · 힘 제어 명령', 'dsr_controller2 에서'),
              I('티치펜던트 · 사람', '비상정지 · 툴 · TCP 등록', '세션 시작 점검 (docs/env/apply_tool_tcp.py)')],
         steps=[S('<b>①</b> 모션 실행 — 직선 · 관절 이동 · 순응 · 힘 제어'),
                S('<b>②</b> 외력 추정 · 위치 · 상태를 돌려준다'),
                S('<b>③</b> 하드웨어 안전 — 충돌 감지 · 보호 정지 · 비상정지. 화면의 중지는 안전 등급 기능이 아니다'),
                S('<b>④</b> RG2 가 무센서 탐침(인공눈물 용기)을 쥔 채 운용 · 부재는 작업대 원점에 축 평행 배치')],
         outs=[I('상태 · 위치 · 외력 추정', '', '→ dsr_controller2')],
         lin=[(0, 0), (1, 2)], lout=[(1, 0)]),
]

# ── 카드 사이 선: (보내는 카드, 출력 번호, 받는 카드, 입력 번호, 갈래, 라벨, 점선 · 계약만, phase 2) ────────
LINKS = [
    ('REACT', 0, 'FAPI', 0, 'cmd', '명령 · REST', 0, 0),
    ('FAPI', 1, 'REACT', 1, 'show', 'WebSocket', 0, 0),
    ('FAPI', 0, 'MQTT', 0, 'cmd', 'cmd/* QoS 1', 0, 0),
    ('MQTT', 0, 'FAPI', 1, 'show', '구독 7 필터', 0, 0),
    ('FAPI', 2, 'PG', 0, 'store', 'upsert', 0, 0),
    ('SPRING', 1, 'PG', 1, 'store', 'JPA', 0, 0),
    ('PG', 0, 'SPRING', 0, 'biz', 'SELECT', 0, 0),
    ('MQTT', 1, 'MB', 0, 'cmd', '명령 · MQTT', 0, 0),
    ('MB', 0, 'MQTT', 1, 'show', '표시 · MQTT', 0, 0),
    ('MB', 1, 'MQTT', 1, 'show', '', 0, 0),
    ('MB', 2, 'MQTT', 1, 'show', '', 0, 0),
    ('MB', 3, 'SM', 0, 'cmd', 'Action', 0, 0),
    ('MB', 4, 'SM', 1, 'cmd', 'Service', 0, 0),
    ('MB', 4, 'SM', 2, 'cmd', '', 0, 0),
    ('MB', 4, 'SAF', 2, 'safety', '/safety/reset', 0, 0),
    ('MB', 5, 'SAF', 4, 'safety', '계약만', 1, 0),
    ('SM', 0, 'MB', 2, 'show', '표시', 0, 0),
    ('SM', 1, 'MB', 2, 'show', '', 0, 0),
    ('SM', 2, 'MB', 2, 'show', '', 0, 0),
    ('SM', 0, 'CD', 1, 'show', 'scan_id', 0, 0),
    ('SM', 0, 'SAF', 4, 'show', '계약만', 1, 0),
    ('SM', 3, 'RM', 0, 'motion', 'ExecuteMotion Action', 0, 0),
    ('SM', 4, 'RM', 1, 'safety', '정지 경로 ①', 0, 0),
    ('SM', 5, 'CD', 2, 'motion', 'tare', 0, 0),
    ('SM', 6, 'SAF', 3, 'cmd', 'P03', 0, 0),
    ('SM', 6, 'CD', 3, 'cmd', 'P02', 0, 0),
    ('SM', 6, 'RM', 3, 'cmd', 'P01', 0, 0),
    ('RM', 0, 'CD', 0, 'state', 'RobotSample', 0, 0),
    ('RM', 0, 'SAF', 0, 'state', '', 0, 0),
    ('RM', 0, 'SM', 4, 'state', '', 0, 0),
    ('RM', 0, 'MB', 2, 'state', '', 0, 0),
    ('RM', 1, 'SAF', 1, 'state', 'RobotStatus', 0, 0),
    ('RM', 1, 'SM', 3, 'state', '', 0, 0),
    ('RM', 1, 'MB', 2, 'state', '', 0, 0),
    ('RM', 2, 'SM', 5, 'contact', '스텝 EDGE', 0, 0),
    ('RM', 2, 'MB', 2, 'contact', '', 0, 0),
    ('CD', 0, 'RM', 2, 'contact', 'ContactEvent', 0, 0),
    ('CD', 0, 'SM', 5, 'contact', '', 0, 0),
    ('CD', 0, 'MB', 2, 'contact', '', 0, 0),
    ('SAF', 0, 'SM', 6, 'safety', 'SafetyStatus', 0, 0),
    ('SAF', 0, 'MB', 2, 'safety', '', 0, 0),
    ('SAF', 1, 'RM', 1, 'safety', '정지 경로 ③ · 웹 경유 없음', 0, 0),
    ('RM', 4, 'DRV', 0, 'motion', 'dsr_msgs2', 0, 0),
    ('DRV', 0, 'RM', 5, 'state', '응답', 0, 0),
    ('DRV', 1, 'MB', 2, 'state', 'joint_states', 0, 0),
    ('DRV', 2, 'CTRL', 0, 'motion', 'DRCF TCP/IP', 0, 0),
    ('CTRL', 0, 'DRV', 0, 'state', '상태 · 외력', 0, 0),
    # phase 2
    ('WM', 0, 'SM', 7, 'show', '/weld/state → 601', 0, 1),
    ('WM', 0, 'MB', 2, 'show', '계약만 · 브리지 없음', 1, 1),
    ('SM', 0, 'WM', 2, 'show', '/scan/state → 600', 0, 1),
    ('SM', 7, 'WM', 4, 'store', 'result.json', 1, 1),
    ('WM', 1, 'RM', 4, 'motion', 'ExecutePath', 0, 1),
    ('WM', 2, 'RM', 0, 'motion', '', 0, 1),
    ('WM', 3, 'RM', 1, 'safety', '', 0, 1),
    ('RM', 1, 'WM', 3, 'state', '', 0, 1),
    ('RM', 0, 'WM', 3, 'state', '', 0, 1),
    ('SAF', 0, 'WM', 3, 'safety', '', 0, 1),
    ('MB', 3, 'WM', 0, 'cmd', '계약만 · 브리지 없음', 1, 1),
    ('MB', 4, 'WM', 1, 'cmd', '', 1, 1),
]

ROW_ZONE = ['web', 'web', 'main', 'main', 'main', 'robot']


# ═════════════════════════════════════════════════════════════════════════
def item_value(it):
    s = f'<b>{it["t"]}</b>'
    if it['y']:
        s += f'<br/><font style="font-size:13px;" color="#0B5FA5">{it["y"]}</font>'
    if it['u']:
        s += f'<br/><font style="font-size:12px;" color="#8A97A6">{it["u"]}</font>'
    return s


def lines_for(text, width, font):
    w = sum(char_w(c) for c in plain(text)) * font
    return max(1, -(-int(w) // int(width)))


def item_h(it):
    w = IW - 24
    n = lines_for(it['t'], w, 14.5) * 14 * 1.22 + (lines_for(it['y'], w, 13.5) * 13 * 1.22 if it['y'] else 0) \
        + (lines_for(it['u'], w, 12.5) * 12 * 1.22 if it['u'] else 0)
    return max(56, int(n + 18))


def step_h(st):
    w = SW - 20 if not st['dia'] else SW * 0.62
    n = lines_for(st['t'], w, 14.5) * 14 * 1.24
    return max(56 if not st['dia'] else 96, int(n + (20 if not st['dia'] else 44)))


def build(with_p2):
    p = Page('시스템 아키텍처 v1.7' + (' (phase 2 포함)' if with_p2 else ' (1차만)'), 5360, 6000,
             pid='arch' if with_p2 else 'arch-no-p2')
    if with_p2:
        p.layer(L2, 'phase 2 (용접) — 끄면 1차만')
    cards = [c for c in CARDS if with_p2 or not c.get('p2')]

    def keep(x):
        return with_p2 or not x.get('p2')

    # ── 카드 높이 ────────────────────────────────────────────────────────
    geom = {}
    for c in cards:
        ins = [it for it in c['ins'] if keep(it)]
        outs = [it for it in c['outs'] if keep(it)]
        steps = [st for st in c['steps'] if keep(st)]
        hi = sum(item_h(i) for i in ins) + ITEM_GAP * (len(ins) - 1)
        ho = sum(item_h(i) for i in outs) + ITEM_GAP * (len(outs) - 1)
        hs = sum(step_h(s) for s in steps) + STEP_GAP * (len(steps) - 1)
        geom[c['key']] = dict(h=68 + 26 + 24 + max(hi, ho, hs) + 30, ins=ins, outs=outs, steps=steps)

    # ── 행 위치 · 구역 · 가로 통로 ─────────────────────────────────────────
    row_y, row_h, gaps, zones = {}, {}, [], {}
    y, prev, last_bottom = 470, None, None
    for r, z in enumerate(ROW_ZONE):
        rh = max([geom[c['key']]['h'] for c in cards if c['row'] == r] + [0])
        if r == 4:   # phase 2 행: 설명 쪽지도 들어간다
            rh = max(rh, 560)
        if r == 5:
            rh = max(rh, 520)
        if z != prev:
            if prev is None:
                ztop = y
            else:
                zones[prev][1] = last_bottom + 70
                gaps.append((last_bottom + 16, last_bottom + 150))      # 구역 사이 통로
                ztop = last_bottom + 170
            zones[z] = [ztop, None]
            y = ztop + 100
        elif last_bottom is not None:
            gaps.append((last_bottom + 16, y - 16))                      # 같은 구역 행 사이 통로
        row_y[r], row_h[r] = y, rh
        last_bottom = y + rh
        y = last_bottom + ROW_GAP
        prev = z
    zones[prev][1] = last_bottom + 70
    gaps.append((last_bottom + 16, last_bottom + 60))
    p.height = last_bottom + 120

    # ── 제목 · 범례 ───────────────────────────────────────────────────────
    p.text(60, 40, 4800, 52, '접촉 탐색으로 용접선 후보를 찾는 협동로봇 시스템 — 시스템 아키텍처 v1.7'
           + (' (phase 2 용접 포함)' if with_p2 else ' (1차 스캔)'), size=34, color='#12294D', bold=True)
    p.text(60, 100, 5200, 30, '기준 <b>docs/contracts v0.1.22 · docs/phase2 v0.2.0</b> (이 그림과 다르면 계약이 우선) · 코드 대조 origin/main '
           '<b>2335057</b> (2026-09-28) · 출발 그림 docs/design/contact-scan-system-architecture-v1.6.drawio · Ubuntu 24.04 + ROS 2 '
           'Jazzy · 자체 ROS 2 노드 5 개' + (' + weld_manager(phase 2)' if with_p2 else '') + ' + 웹 5 개 + 제공 드라이버 · '
           '각 카드는 입력 → 처리 로직 → 출력 · 선 하나하나의 이름 · 타입은 06 노드 구조도', size=15, color='#4A5666')
    p.text(60, 136, 5200, 30, '<b>1차 절차</b>  부재를 작업대 원점에 축 평행 배치 → [시작] → 무접촉 기준값(tare) → 수직 하강 → 윗면 z → '
           '+x / −x / +y / −y 모서리 4 점(실기: 스텝 모드) → 편향 보정 → 윗면 사각형 · 외곽 엣지 · 경로 후보 4 개 → 직육면체 → 결과 발행 · '
           '3D · 저장 → 홈 복귀(정상 완료일 때만)'
           + ('   <font color="#C0600A"><b>phase 2</b> 스캔 결과 → 모서리 8 선 45° · 위빙 경유점 용접 모션</font>' if with_p2 else ''),
           size=15, color='#4A5666')
    p.v(60, 190, 2250, 250, '', 'rounded=0;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#B7C1CC;strokeWidth=1.5;')
    p.text(74, 198, 1400, 22, '화살표 색 = 데이터 갈래 (선 하나가 갈래 하나) · 굵은 선 = 카드 사이 · 가는 회색 = 카드 안 · '
           '점선 = 계약에만 있음 · 파일', size=14, color='#12294D', bold=True)
    legend = [('cmd', '명령 — 시작 · 중지 · 안전복귀 · 재시작 · 설정 · 안전 해제 (브라우저 → FastAPI → MQTT → bridge → 노드)'),
              ('show', '표시 데이터 — 단계 · 결과 · 로그 · 접수/완료 (노드 → bridge → MQTT → FastAPI → 화면)'),
              ('state', '로봇 상태 — /robot/sample(TCP · 힘 + 실행 중 motion_id · operation) · /robot/status · 관절'),
              ('contact', '접촉 이벤트 — CONTACT · EDGE · OVER_FORCE (contact_detector, 스텝 EDGE 는 robot_manager)'),
              ('motion', '모션 — ExecuteMotion · ExecutePath Action · tare · 두산 서비스 · DRCF'),
              ('safety', '안전 — 로컬 정지 요청 · 안전 상태 · 래치 해제 (웹 경유 없음)'),
              ('store', '저장 — PostgreSQL(FastAPI 측정 쓰기 · Spring 업무) · result.json 파일'),
              ('biz', '업무 관리 — REST 조회 (Spring)')]
    for i, (cat, txt) in enumerate(legend):
        cx, cy = 74 + (i // 4) * 1110, 236 + (i % 4) * 44
        p.free_edge(cx, cy, cx + 56, cy, f'endArrow=blockThin;endFill=1;endSize=8;html=1;strokeColor={CAT[cat]};strokeWidth=2.6;')
        p.text(cx + 66, cy - 11, 1030, 22, txt, size=13)
    p.v(2350, 190, 1600, 250, '', 'rounded=1;arcSize=3;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#B7C1CC;strokeWidth=1.5;')
    p.text(2366, 198, 900, 22, '두꺼운 테두리 = 그 노드가 도는 컴퓨터', size=14, color='#12294D', bold=True)
    zl = [('web', '웹 PC — Ubuntu 24.04 · Docker(Mosquitto · PostgreSQL 16 · FastAPI · Spring Boot) + React·Three.js(Docker 밖)'),
          ('main', '메인 PC (= 제어 PC) — Ubuntu 24.04 · ROS 2 Jazzy · 자체 노드 5 개' + (' + weld_manager' if with_p2 else '')
           + ' · 제공 드라이버 · contact_scan_interfaces'),
          ('robot', '로봇 컨트롤러 — M0609 (DRCF) · RG2 · 무센서 탐침 팁 · 작업대')]
    for i, (z, txt) in enumerate(zl):
        f, s = {'web': ('#FAEFF7', '#A05195'), 'main': ('#EFF1FB', '#5566B5'), 'robot': ('#EEF7F5', '#2E8B7A')}[z]
        p.v(2366, 236 + i * 40, 64, 26, '', f'rounded=1;arcSize=8;whiteSpace=wrap;html=1;fillColor={f};strokeColor={s};strokeWidth=5;')
        p.text(2444, 238 + i * 40, 1480, 22, txt, size=13)
    p.text(2364, 360, 1560, 22, '<b>읽는 법</b>   왼쪽 입력 → 가운데 처리 → 오른쪽 출력 · Topic = sub/pub · Service = 요청/응답 · '
           'Action = 목표/피드백/결과/취소 · 점선 항목 = 계약에만 있음', size=12)
    p.text(2364, 384, 1560, 44, '살구 마름모 = 판단 · 회색 머리띠 = 제공 · 설치 사용 · 테두리 옅은 머리띠(React) = 사람이 보는 자리 · '
           '점선 상자 = 설명 쪽지' + (' · <font color="#C0600A"><b>주황 = phase 2(용접)</b> — 레이어 "phase 2 (용접)" 를 끄면 1차만'
                                   '</font>' if with_p2 else ''), size=12)
    if with_p2:
        p.v(3990, 190, 1290, 250, '<b style="font-size:16px">phase 2 (용접) 구현 상태 — 2026-09-28</b><br/>'
            '계약 v0.2.0 은 main(#184 · #198 · #199). <b>main 에 있는 구현</b>: scan_manager 의 601 거절(P5 #204) · '
            '브리지 이름표 WELD_PATH(#200).<br/><b>머지 전</b>: robot_manager /robot/execute_path(#191) · weld_manager(#195 → #196 → '
            '#197).<br/><b>PR 없음</b>: mqtt_bridge cmd/weld · weld/* 중계(P4) · 웹 용접 화면(P3).<br/>9/23 측정: 45° 자세 16 중 12 도달 '
            '(L1 · L5 불가). 실기 용접은 9/29.',
            f'rounded=1;whiteSpace=wrap;html=1;fillColor=#FDF0E4;strokeColor={P2};strokeWidth=1.6;dashed=1;dashPattern=6 4;'
            'fontSize=13;fontColor=#5A2A04;align=left;verticalAlign=top;spacingLeft=12;spacingTop=8;spacingRight=10;', layer=L2)

    # ── 구역 ──────────────────────────────────────────────────────────────
    ztitle = {'web': '웹 PC · Docker 4 서비스(Mosquitto :1883 · PostgreSQL :5432 · FastAPI :8000 · Spring Boot :8080) + React·Three.js :5173',
              'main': '메인 PC (= 제어 PC) · Ubuntu 24.04 / ROS 2 Jazzy · 자체 노드 5 개' + (' + weld_manager' if with_p2 else '')
                      + ' + 제공 드라이버 · 네임스페이스 없음',
              'robot': '로봇 컨트롤러 (Doosan M0609 · DRCF) · RG2 · 무센서 탐침 팁 · 작업대 — 하드웨어 안전 담당'}
    for z, (y0, y1) in zones.items():
        f, s = {'web': ('#FAEFF7', '#A05195'), 'main': ('#EFF1FB', '#5566B5'), 'robot': ('#EEF7F5', '#2E8B7A')}[z]
        p.v(ZX0, y0, ZX1 - ZX0, y1 - y0, '', f'rounded=1;whiteSpace=wrap;html=1;fillColor={f};strokeColor={s};strokeWidth=7;arcSize=2;')
        p.v(ZX0 + 26, y0 + 20, 1900, 44, ztitle[z], f'rounded=1;whiteSpace=wrap;html=1;fillColor={s};strokeColor={s};strokeWidth=1;'
            'fontSize=17;fontStyle=1;fontColor=#FFFFFF;align=center;verticalAlign=middle;arcSize=8;')

    # ── 카드 ──────────────────────────────────────────────────────────────
    ports = {}   # (card, 'in'|'out', idx) → (cell id, y 가운데)
    for c in cards:
        g = geom[c['key']]
        x, y = COLX[c['col']], row_y[c['row']]
        hf, bd, fc, hc = KIND[c['kind']]
        lay = L2 if c.get('p2') else '1'
        p.v(x, y, CW, g['h'], '', f'rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor={bd};strokeWidth=1.8;arcSize=3;',
            layer=lay)
        p.v(x, y, CW, 68, f'{c["title"]}<br/><font style="font-size:13px;" color="{fc}">{c["sub"]}</font>',
            f'rounded=1;whiteSpace=wrap;html=1;fillColor={hf};strokeColor={hf};fontColor={fc};fontSize=20;fontStyle=1;'
            'align=left;verticalAlign=middle;spacingLeft=14;arcSize=5;', layer=lay)
        heads = COLHEAD[c['kind']]
        for k, (hx, hw) in enumerate([(x, IW), (x + 460, SW), (x + CW - IW, IW)]):
            p.v(hx, y + 78, hw, 26, heads[k], f'rounded=0;whiteSpace=wrap;html=1;fillColor=#F4F6F8;strokeColor=none;'
                f'fontColor={hc};fontSize=13;fontStyle=1;align=center;verticalAlign=middle;', layer=lay)
        body_top = y + 118
        p.v(x + 452, body_top - 8, SW + 16, g['h'] - 118 - 14, '', 'rounded=0;whiteSpace=wrap;html=1;fillColor=#FBFCFD;'
            'strokeColor=#E4E9EE;dashed=1;dashPattern=4 4;', layer=lay)

        def item_style(it):
            st = ('rounded=1;whiteSpace=wrap;html=1;fillColor=#F4F6F8;strokeColor=#C2CBD5;fontSize=14;fontColor=#16202B;'
                  'align=left;verticalAlign=middle;spacingLeft=8;spacingRight=6;strokeWidth=1.2;arcSize=4;')
            if it.get('dash'):
                st += 'dashed=1;dashPattern=6 4;fillColor=#FBFBFB;fontColor=#6B7785;'
            if it.get('p2'):
                st += f'strokeColor={P2};fillColor=#FDF0E4;'
            return st

        cy = body_top
        in_ids = []
        for k, it in enumerate(c['ins']):
            if not keep(it):
                in_ids.append(None)
                continue
            h = item_h(it)
            cid = p.v(x, cy, IW, h, item_value(it), item_style(it), layer=L2 if (it['p2'] or c.get('p2')) else '1')
            ports[(c['key'], 'in', k)] = (cid, cy + h / 2)
            in_ids.append(cid)
            cy += h + ITEM_GAP
        cy = body_top
        out_ids = []
        for k, it in enumerate(c['outs']):
            if not keep(it):
                out_ids.append(None)
                continue
            h = item_h(it)
            cid = p.v(x + CW - IW, cy, IW, h, item_value(it), item_style(it), layer=L2 if (it['p2'] or c.get('p2')) else '1')
            ports[(c['key'], 'out', k)] = (cid, cy + h / 2)
            out_ids.append(cid)
            cy += h + ITEM_GAP
        cy = body_top
        step_ids = []
        prev = None
        for k, st in enumerate(c['steps']):
            if not keep(st):
                step_ids.append(None)
                continue
            h = step_h(st)
            sl = L2 if (st['p2'] or c.get('p2')) else '1'
            if st['dia']:
                cid = p.v(x + 460, cy, SW, h, st['t'], 'rhombus;whiteSpace=wrap;html=1;fillColor=#F7E3CD;strokeColor=#CBA97C;'
                          'strokeWidth=1.3;fontSize=14;fontColor=#4A3620;align=center;verticalAlign=middle;spacingLeft=40;'
                          'spacingRight=40;', layer=sl)
            else:
                cid = p.v(x + 460, cy, SW, h, st['t'], 'rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#C2CBD5;'
                          'strokeWidth=1.2;fontSize=14;fontColor=#16202B;align=left;verticalAlign=middle;spacingLeft=9;'
                          'spacingRight=7;arcSize=4;' + (f'strokeColor={P2};' if st['p2'] else ''), layer=sl)
            if prev is not None:
                p.cells.append(dict(id=p._id('g'), value=c['steps'][prev[1]].get('yes', 'Yes') if c['steps'][prev[1]]['dia'] else '', style=(
                    'edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#B0BAC6;strokeWidth=1.8;endArrow=blockThin;'
                    'endFill=1;endSize=6;fontSize=12;fontColor=#7A8798;labelBackgroundColor=#FFFFFF;exitX=0.5;exitY=1;'
                    'exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0;'), edge='1', parent=sl,
                    source=prev[0], target=cid, geo=dict(relative='1')))
            prev = (cid, k)
            step_ids.append(cid)
            cy += h + STEP_GAP
        for k, st in enumerate(c['steps']):
            if st.get('no') is not None and step_ids[k] and step_ids[st['no']]:
                sl = L2 if (st['p2'] or c.get('p2')) else '1'
                sx0, sy0, sw0, sh0 = p.geo[step_ids[k]]
                tx0, ty0, tw0, th0 = p.geo[step_ids[st['no']]]
                xr = sx0 + sw0 + 18
                p.cells.append(dict(id=p._id('g'), value=st.get('no_label', 'No'), style=(
                    'edgeStyle=orthogonalEdgeStyle;rounded=1;arcSize=8;html=1;strokeColor=#B0BAC6;strokeWidth=1.6;'
                    'endArrow=blockThin;endFill=1;endSize=6;fontSize=12;fontColor=#7A8798;labelBackgroundColor=#FFFFFF;'
                    'exitX=1;exitY=0.5;exitDx=0;exitDy=0;entryX=1;entryY=0.5;entryDx=0;entryDy=0;'), edge='1', parent=sl,
                    source=step_ids[k], target=step_ids[st['no']], geo=dict(relative='1'),
                    points=[(xr, sy0 + sh0 / 2), (xr, ty0 + th0 / 2)]))
        grey = ('edgeStyle=orthogonalEdgeStyle;rounded=1;arcSize=8;html=1;strokeColor=#B0BAC6;strokeWidth=1.6;endArrow=blockThin;'
                'endFill=1;endSize=6;exitX=1;exitY=0.5;exitDx=0;exitDy=0;entryX=0;entryY=0.5;entryDx=0;entryDy=0;')
        for a, b in c['lin']:
            if a < len(in_ids) and b < len(step_ids) and in_ids[a] and step_ids[b]:
                lay_e = L2 if (c['ins'][a]['p2'] or c['steps'][b]['p2'] or c.get('p2')) else '1'
                p.cells.append(dict(id=p._id('g'), value='', style=grey + ('dashed=1;' if c['ins'][a]['dash'] else ''), edge='1',
                                    parent=lay_e, source=in_ids[a], target=step_ids[b], geo=dict(relative='1')))
        for a, b in c['lout']:
            if a < len(step_ids) and b < len(out_ids) and step_ids[a] and out_ids[b]:
                lay_e = L2 if (c['outs'][b]['p2'] or c['steps'][a]['p2'] or c.get('p2')) else '1'
                p.cells.append(dict(id=p._id('g'), value='', style=grey + ('dashed=1;' if c['outs'][b]['dash'] else ''), edge='1',
                                    parent=lay_e, source=step_ids[a], target=out_ids[b], geo=dict(relative='1')))

    # ── 설명 쪽지 ─────────────────────────────────────────────────────────
    NOTE = ('rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFDF6;strokeColor=#C2A57C;strokeWidth=1.4;dashed=1;dashPattern=6 4;'
            'fontSize=14;fontColor=#4A3620;align=left;verticalAlign=top;spacingLeft=12;spacingTop=10;spacingRight=10;arcSize=4;')
    p.v(COLX[2], row_y[1], CW, 560,
        '<b style="font-size:16px">MQTT · 명령 계약 — 설계 설명 (실행 노드 아님)</b><br/><br/>'
        '<b>명령</b> cmd/scan/start → /scan/run Action · cmd/scan/home → /scan/home Action · cmd/scan/resume → /scan/resume Action '
        '(scan_id 는 최상위 키) · cmd/scan/stop → /scan/stop Service · cmd/scan/set_config → /scan/set_config Service · '
        'cmd/safety/reset → /safety/reset Service(safety_monitor)<br/>'
        '<b>공통 필드</b> schema_version "0.1" · request_id(UUID v4) · timestamp_ms · payload · session_id 는 선택 · '
        '중복 → DUPLICATE_REQUEST(106) · 만료(5 s) → INVALID_REQUEST(101) · <b>cmd/scan/stop 은 만료 검사 제외</b> · 명령은 모두 retain=false<br/>'
        '<b>접수 ≠ 완료</b> cmd/ack = 접수 · 거절, scan/command_result = 완료. scan_manager 는 goal 을 늘 받으므로 start 의 거절(103 등)도 '
        'ack accepted=true 뒤 command_result 로 온다. set_config · safety/reset 은 ack 가 곧 결과<br/>'
        '<b>ROS → 웹</b> 길이 mm · 시각 epoch ms · enum 은 이름(모르면 UNKNOWN_&lt;n&gt;) · 무효값 null + *_valid 유지 · '
        'retain = robot/status · scan/state · safety/status · conn/ros<br/>'
        '<b>계약에만 있음</b> 웹의 hb/web(1 Hz) · conn/web(LWT) 발행, heartbeat 만료 감시(405)'
        + ('<br/><font color="#C0600A"><b>phase 2</b> cmd/weld/{start, stop, home} → /weld/run · /weld/stop · /weld/home, '
           'weld/state · weld/result · weld/log · weld/command_result — 계약만, 브리지 · 웹 구현 없음</font>' if with_p2 else ''),
        NOTE)
    p.v(COLX[0], row_y[4], CW, 560,
        '<b style="font-size:16px">contact_scan_interfaces — 공통 정의 패키지 (실행 노드 아님)</b><br/><br/>'
        '<b>msg</b> RobotSample · RobotStatus · ContactEvent · ScanState · ScanResult · ScanLog · SafetyStatus · WebHeartbeat · '
        '하위 ScanConfig · Segment · ReasonCode' + (' · <font color="#C0600A">WeldConfig · WeldState · WeldLine · WeldResult</font>' if with_p2 else '')
        + '<br/><b>srv</b> StopRobot · StopScan · TareForce · ResetSafety · SetConfig' + (' · <font color="#C0600A">StopWeld</font>' if with_p2 else '')
        + '<br/><b>action</b> RunScan · ReturnHome · Resume · ExecuteMotion' + (' · <font color="#C0600A">RunWeld · ExecutePath</font>' if with_p2 else '')
        + '<br/><b>QoS</b> contact_scan_qos 모듈 한 곳 — SENSOR · STATE · EVENT · LOG · HEARTBEAT (발행 · 구독 양쪽이 import)<br/>'
        '<b>ReasonCode</b> 1xx 요청 거절 · 2xx 동작 종료 · 3xx 접촉 · 툴 · 4xx 안전 · 5xx 형상' + (' · <font color="#C0600A">6xx 용접</font>' if with_p2 else '')
        + ' — 번호는 추가만<br/><b>규칙</b> ROS 안은 m · rad · N, 웹 표시는 mm(변환은 경계에서만) · 미측정값은 NaN + *_valid=false · '
        '좌표는 frame_id 로 기준을 밝힌다 · .msg 와 계약 문서가 어긋나면 test_contract_sync 가 CI 에서 실패<br/>'
        '<b>자세한 필드</b> 05 인터페이스 정의서', NOTE)
    p.v(COLX[0], row_y[5], 2 * CW + (COLX[1] - COLX[0] - CW), max(row_h[5], 520),
        '<b style="font-size:16px">v1.6 → v1.7 에서 바뀐 것 · 계약과 구현이 다른 곳 — 2026-09-28</b><br/><br/>'
        '① <b>웹 PC 를 실제 구성으로</b>: Docker 4 서비스 + React 는 Docker 밖 · FastAPI 경로 /commands/* · /ws · psycopg · Spring 은 '
        '/api/* (화면과 연결 없음) · DB 테이블 7 개 (v1.6 의 /api/scan/* · /ws/live · asyncpg · 테이블 이름은 옛 설계)<br/>'
        '② <b>스텝 모드 SLIDE</b>(실기 기본): robot_manager 가 긁고 멈춰 힘을 읽어 모서리를 찾고 EDGE 를 직접 발행(v0.1.15)<br/>'
        '③ <b>안전 감사 후속(v0.1.21)</b>: scan_manager 의 /robot/sample 구독 · 안전복귀 5 단계 · 오류 뒤 재시작 허용 403 · 404 · 407 · '
        '정지 확인 실패 STOP_UNCONFIRMED 407<br/>'
        '④ <b>표시 전용 관절</b>: /dsr01/joint_states → robot/joints · robot/gripper_joints (v0.1.19 · v0.1.20) · 이름표 밖 값은 UNKNOWN_&lt;n&gt; (v0.1.22)<br/>'
        '⑤ <b>계약에만 있고 코드에 없는 것</b>: 웹 hb/web · conn/web 발행 · safety_monitor 의 /scan/state · /web/heartbeat 구독 · '
        'heartbeat 만료 405 · 속도 401 · 작업영역 402 감시 · robot_manager 의 RG2 호출 · 시작 전 툴 · TCP 확인 · 화면의 설정 등록 버튼(TR-05) · '
        'RobotStatus.error 필드(늘 false)<br/>'
        '⑥ <b>v1.6 에서 지운 것</b>: contact_detector 의 이동평균 필터(코드 없음 — 디바운스 · 이동 기준 · 추세선) · /scan/calibrate 검토안 카드 · '
        'React ↔ Spring 연결<br/>'
        '⑦ <b>실측</b>: 9/23 실기 종단 3 회 연속 성공(1 회 약 7 분, 팀원 입회 · 영상) · 탐색 438 s(KPI 120 s 미달) · 검출 하중 평균 4.49 N · '
        '같은 점 10 회 산포 0.040 mm'
        + ('<br/>⑧ <font color="#C0600A"><b>phase 2</b>: weld_manager · /robot/execute_path · 스캔 ↔ 용접 배타(600 · 601) · result.json 파일 '
           '연결 (계약 v0.2.0)</font>' if with_p2 else ''), NOTE)

    # ── 카드 사이 선 (통로 배선) ─────────────────────────────────────────
    route_links(p, cards, ports, row_y, row_h, gaps, with_p2)
    return p


def route_links(p, cards, ports, row_y, row_h, gaps, with_p2):
    card = {c['key']: c for c in cards}
    # 세로 통로: 열 사이 틈. 0 = 맨 왼쪽 여백, 1 = 0|1 사이, 2 = 1|2 사이, 3 = 맨 오른쪽 여백
    gut = {0: (ZX0 + 30, COLX[0] - 10), 1: (COLX[0] + CW + 10, COLX[1] - 10), 2: (COLX[1] + CW + 10, COLX[2] - 10),
           3: (COLX[2] + CW + 10, ZX1 - 30)}
    src_lane, tgt_lane = {}, {}
    src_used = {g: 0 for g in gut}
    tgt_used = {g: 0 for g in gut}
    STEP = 11

    def lane_src(g, key):
        if key not in src_lane:
            src_lane[key] = gut[g][0] + 12 + src_used[g] * STEP
            src_used[g] += 1
        return src_lane[key]

    def lane_tgt(g, key):
        if key not in tgt_lane:
            tgt_lane[key] = gut[g][1] - 12 - tgt_used[g] * STEP
            tgt_used[g] += 1
        return tgt_lane[key]

    chan = {}
    chan_used = {i: 0 for i in range(len(gaps))}

    def channel(gi, key):
        if (gi, key) not in chan:
            y0, y1 = gaps[gi]
            chan[(gi, key)] = y0 + 8 + chan_used[gi] * 13
            chan_used[gi] += 1
            if chan[(gi, key)] > y1:
                print('통로 넘침', gi, key)
        return chan[(gi, key)]

    mids = [(g0 + g1) / 2 for g0, g1 in gaps]

    def gap_between(r_src, r_tgt):
        lo, hi = min(r_src, r_tgt), max(r_src, r_tgt)
        below_lo = [i for i, m in enumerate(mids) if m > row_y[lo] + row_h[lo]]
        if lo == hi:
            return below_lo[0]
        between = [i for i in below_lo if mids[i] < row_y[hi]]
        return between[-1] if r_tgt > r_src else between[0]

    labeled = set()
    for (a, ai, b, bi, cat, text, dash, is_p2) in LINKS:
        if is_p2 and not with_p2:
            continue
        if a not in card or b not in card or (a, 'out', ai) not in ports or (b, 'in', bi) not in ports:
            continue
        sid, sy = ports[(a, 'out', ai)]
        tid, ty = ports[(b, 'in', bi)]
        ca, cb = card[a], card[b]
        gs, gt = ca['col'] + 1, cb['col']      # 보내는 카드 오른쪽 통로 · 받는 카드 왼쪽 통로
        if gs == gt:                           # 바로 오른쪽 열: 받는 쪽 세로 차선 하나로
            xt = lane_tgt(gt, (b, bi))
            via = [(xt, sy), (xt, ty)] if abs(sy - ty) > 1 else []
            at = (xt, (sy + ty) / 2) if via else ((COLX[ca['col']] + CW + COLX[cb['col']]) / 2, sy)
        else:
            xs = lane_src(gs, (a, ai))
            xt = lane_tgt(gt, (b, bi))
            gi = gap_between(ca['row'], cb['row'])
            yc = channel(gi, (a, ai))
            via = [(xs, sy), (xs, yc), (xt, yc), (xt, ty)]
            at = (xs + (160 if xt > xs else -160), yc) if abs(xt - xs) > 400 else (xs, (sy + yc) / 2)
        color = GAP_COLOR if dash and cat != 'store' else CAT[cat]
        st = (f'edgeStyle=orthogonalEdgeStyle;rounded=1;arcSize=10;html=1;jumpStyle=arc;jumpSize=7;strokeColor={color};'
              f'strokeWidth=2.4;endArrow=blockThin;endFill=1;endSize=8;')
        if dash:
            st += 'dashed=1;dashPattern=8 5;'
        lbl = None
        if text and (a, ai, text) not in labeled:
            labeled.add((a, ai, text))
            lbl = f'<b><font color="{color}">{text}</font></b>'
        lay = L2 if (is_p2 or ca.get('p2') or cb.get('p2')) else '1'
        ls = ('edgeLabel;html=1;align=center;verticalAlign=middle;resizable=0;points=[];whiteSpace=nowrap;fontSize=12;'
              'labelBackgroundColor=#FFFFFF;spacing=2;')
        p.e(sid, tid, st, 'R', sy, 'L', ty, via=via, label=lbl, label_at=at, label_w=400, label_style=ls, layer=lay,
            label_font=12)


def main():
    out = HERE / '01-system-architecture.drawio'
    write_mxfile(out, [build(True), build(False)])
    print(out)


if __name__ == '__main__':
    main()
