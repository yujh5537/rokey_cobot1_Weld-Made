"""산출물 06 ROS2 노드 구조도 drawio 를 만든다 → 06-node-graph.drawio

쪽 3 개:
  1. 노드 구조도 v1.2 (상세)      — docs/design/contact-scan-node-diagram-v1.1.drawio 형식. phase 2 는 "phase 2 (용접)" 레이어
  2. 노드 구조도 v1.2 (1차만)     — 1 쪽에서 phase 2 레이어를 뺀 것 (png 내보내기용)
  3. 노드 구조도 (간략) v1.3      — docs/design/contact-scan-node-overview-v1.2.drawio 형식 (발표용)

선 하나 = 06-node-graph.md 연결 표에서 "같은 두 노드 · 같은 방향 · 같은 종류 · 같은 갈래" 인 행을 모은 것. 라벨 끝 [..] 이 행 번호다.
근거: docs/contracts/ros-interfaces.md(v0.1.22) · mqtt-schema.md · docs/phase2/weld-*.md(v0.2.0) · ws_cobot1/src (origin/main 2335057)
실행: python3 docs/deliverables/drawio_06.py
"""
import pathlib

from drawio_lib import CAT, P2, P2_FILL, Page, edge_style, write_mxfile, zone

HERE = pathlib.Path(__file__).resolve().parent
L2 = 'p2'   # phase 2 레이어 id

NODE = ('rounded=1;whiteSpace=wrap;html=1;fillColor=#D3DCF5;strokeColor=#22357F;strokeWidth=3;fontSize=12;'
        'fontColor=#12294D;align=left;verticalAlign=top;spacingLeft=10;spacingTop=6;spacingRight=8;')
NODE_P2 = NODE.replace('fillColor=#D3DCF5;strokeColor=#22357F', f'fillColor={P2_FILL};strokeColor={P2}')
EXT = ('rounded=1;whiteSpace=wrap;html=1;fillColor=#E9EDF1;strokeColor=#8A96A3;strokeWidth=1.5;dashed=1;fontSize=12;'
       'fontColor=#333F4E;align=left;verticalAlign=top;spacingLeft=10;spacingTop=6;spacingRight=8;')
MOD = ('rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#5566B5;strokeWidth=1;fontSize=11;'
       'fontColor=#22357F;align=left;verticalAlign=top;spacingLeft=8;spacingTop=4;')
NOTE = ('rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFDF6;strokeColor=#C2A57C;strokeWidth=1.4;dashed=1;'
        'dashPattern=6 4;fontSize=11;fontColor=#4A3620;align=left;verticalAlign=top;spacingLeft=10;spacingTop=6;'
        'spacingRight=8;')
LBL = ('edgeLabel;html=1;align=center;verticalAlign=middle;resizable=0;points=[];whiteSpace=nowrap;fontSize=10;'
       'fontColor=#16202B;labelBackgroundColor=#FFFFFF;labelBorderColor=#16202B;spacing=2;')
LBL_P2 = LBL.replace('labelBorderColor=#16202B', f'labelBorderColor={P2}').replace('fontColor=#16202B', 'fontColor=#7A3B06')


def P(name, *lines, param=None):
    s = f'<b style="font-size:15px">{name}</b>'
    for ln in lines:
        s += '<br/>' + ln
    if param:
        s += f'<br/><font color="#5A6B80">param: {param}</font>'
    return s


def lab(name, kind, ids, meaning):
    return f'<b>{name} · {kind}</b> [{ids}]<br/>{meaning}'


def detail_page(with_p2):
    p = Page('노드 구조도 v1.2 (상세)' if with_p2 else '노드 구조도 v1.2 (1차만)', 3200, 3080,
             pid='node-detail' if with_p2 else 'node-detail-no-p2')
    if with_p2:
        p.layer(L2, 'phase 2 (용접) — 끄면 1차만')
    lay2 = L2 if with_p2 else None

    # ── 제목 · 범례 ───────────────────────────────────────────────────────
    p.text(100, 30, 1850, 40, '접촉 스캔 시스템 — ROS 2 노드 구조도 v1.2' + (' (phase 2 용접 포함)' if with_p2 else ' (1차 스캔)'),
           size=26, color='#12294D', bold=True)
    p.text(100, 78, 1850, 130,
           '기준: <b>docs/contracts v0.1.22 · docs/phase2 v0.2.0 — 이 그림과 다르면 계약이 우선</b> · 코드 대조 origin/main '
           '<b>2335057</b>(2026-09-28) · 출발 그림 docs/design/contact-scan-node-diagram-v1.1.drawio(40 선) · 짝 문서 '
           '06-node-graph.md(연결 표) · 05-interfaces.md(필드 · QoS)<br/>'
           '라벨 = <b>이름 · 종류</b> [연결 표 번호] + 뜻 한 줄. 같은 두 노드 · 같은 방향 · 같은 종류 · 같은 갈래의 행은 선 하나로 '
           '모았다. 네임스페이스 없음 · 실행 파일명 = 노드명 · 노드별 패키지(ws_cobot1/src)<br/>'
           '<b>회색 점선 = 계약에는 있고 main 코드에는 없는 연결</b>(L10 · L26 · X06' + (' · phase 2 브리지 선' if with_p2 else '') + '). '
           + ('<font color="#C0600A"><b>주황 = phase 2(용접)</b> — 레이어 "phase 2 (용접)" 를 끄면 1차만 남는다. '
              'weld_manager · /robot/execute_path 는 구현 PR(#191 · #195~#197) 머지 전, scan_manager 의 601 거절(P5 #204)은 main</font>'
              if with_p2 else 'phase 2(용접)를 뺀 판. 포함 판은 같은 파일 1 쪽.'),
           size=12, color='#4A5668', valign='top')
    p.v(1980, 20, 1120, 210, '', 'rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#B8C0CC;strokeWidth=1;')
    p.text(1995, 25, 200, 22, '<b>범례</b>', size=13, color='#12294D')
    legend_lines = [('T', 'show', False, None, 'Topic (T) · 실선 화살표'),
                    ('S', 'show', False, None, 'Service (S) · 요청/응답 (○ 클라이언트 → ▶ 서버)'),
                    ('A', 'show', False, None, 'Action (A) · 굵은 양방향 (목표/피드백/결과/취소)'),
                    ('T', 'show', True, None, '점선 = 검토안(MVP 밖) · 파일'),
                    ('T', 'gap', True, CAT['gap'], '회색 점선 = 계약 · 미구현'),
                    ('X', 'ext', False, None, '외부(제공 · 설치 사용) · 이름과 방향만')]
    for i, (k, cat, dash, col, txt) in enumerate(legend_lines):
        y = 62 + i * 27
        st = edge_style(cat, k, dash, color=col or '#4A5668').replace('edgeStyle=orthogonalEdgeStyle;', '')
        p.free_edge(2000, y, 2120, y, st)
        p.text(2132, y - 12, 420, 24, txt, size=11)
    chips = [('cmd', '명령'), ('show', '표시 데이터'), ('state', '로봇 상태'), ('contact', '접촉 이벤트'),
             ('motion', '모션'), ('safety', '안전'), ('store', '저장 · 파일')]
    for i, (cat, txt) in enumerate(chips):
        cx, cy = 2570 + (i % 2) * 250, 56 + (i // 2) * 30
        p.v(cx, cy, 34, 14, '', f'rounded=1;fillColor={CAT[cat]};strokeColor={CAT[cat]};')
        p.text(cx + 44, cy - 5, 190, 24, txt, size=11)
    p.v(2570, 180, 60, 30, '', 'rounded=1;fillColor=#D3DCF5;strokeColor=#22357F;strokeWidth=3;')
    p.text(2636, 183, 130, 24, '자체 ROS 2 노드', size=11)
    p.v(2770, 180, 50, 30, '', 'rounded=1;fillColor=#E9EDF1;strokeColor=#8A96A3;strokeWidth=1.5;dashed=1;')
    p.text(2826, 183, 100, 24, '외부 구성요소', size=11)
    if with_p2:
        p.v(2930, 180, 50, 30, '', f'rounded=1;fillColor={P2_FILL};strokeColor={P2};strokeWidth=3;', layer=L2)
        p.text(2986, 183, 110, 24, 'phase 2', size=11, color='#C0600A', layer=L2)

    # ── 구역 ──────────────────────────────────────────────────────────────
    zone(p, 100, 250, 3050, 250, 'web', '웹 PC · Ubuntu 24.04 · Docker(Mosquitto · PostgreSQL 16 · FastAPI · Spring Boot) + '
         'React·Three.js(Docker 밖) — ROS 2 아님 · 이 그림에서는 이름과 방향만')
    zone(p, 60, 560, 3090, 2180, 'main', '메인 PC (= 제어 PC) · Ubuntu 24.04 / ROS 2 Jazzy · 자체 노드 5 개'
         + (' + weld_manager(phase 2)' if with_p2 else '') + ' + 제공 드라이버 · contact_scan_interfaces 정의 패키지(노드 아님)')
    zone(p, 100, 2800, 3050, 240, 'robot', '로봇 컨트롤러 · Doosan M0609 (DRCF) · RG2 · 무센서 탐침 팁(인공눈물 용기) — '
         '하드웨어 안전(비상정지 · 충돌 감지) 담당')

    # ── 노드 ──────────────────────────────────────────────────────────────
    WEB = p.v(200, 320, 1000, 150, P(
        '[외부] 웹 스택 — FastAPI · Spring Boot · PostgreSQL · React+Three.js',
        '브라우저 버튼 5 개(시작 · 중지 · 안전복귀 · 재시작 · 안전 해제) → FastAPI REST /commands/* → MQTT 발행 · '
        'MQTT → WebSocket /ws 표시(mm) · 측정 DB 쓰기는 FastAPI · Spring 은 업무 · 이력 API(화면과 아직 연결 없음) · '
        '<b>hb/web · conn/web 은 보내지 않는다</b>(계약만)'), EXT, cid='WEB')
    BRK = p.v(1650, 320, 1100, 150, P(
        '[외부] MQTT Broker (Mosquitto 2) · :1883',
        '두 PC 사이 단일 중계 · 판단하지 않음 · 익명 접속 · persistence(retain · QoS 1 대기 메시지) · '
        'retain = robot/status · scan/state · safety/status · conn/ros · JSON 스키마는 docs/contracts/mqtt-schema.md'), EXT, cid='BRK')

    MB = p.v(200, 640, 2700, 190, P(
        'mqtt_bridge',
        'ROS 2 ↔ MQTT 변환 · cmd/scan/+ · cmd/safety/reset 수신 → 공통 필드 검사(schema_version · request_id 중복 · '
        '만료, <b>cmd/scan/stop 은 만료 검사 제외</b>) → cmd/ack(접수) → Action/Service 호출 → scan/command_result(완료) · '
        '접수 ≠ 완료',
        'ROS Topic → MQTT JSON: m → mm · NaN → null · enum 은 이름(표에 없으면 "UNKNOWN_&lt;n&gt;", v0.1.22) · '
        '/robot/sample 10 Hz 로 솎음 · hb/web 을 받았을 때만 /web/heartbeat · hb/ros(1 Hz) · conn/ros(LWT) · '
        '/dsr01/joint_states → robot/joints · robot/gripper_joints(표시 전용, 20 Hz) · 토픽 이름표는 코드에 고정 · '
        'set_config · safety/reset 은 cmd/ack 가 곧 결과',
        param='broker_host · broker_port · topic_prefix · dedup_cache_size · cmd_expiry_s · sample_publish_hz · '
              'joint_publish_hz · joint_state_topic · heartbeat_hz · keepalive_s'), NODE, cid='MB')

    SM = p.v(200, 1330, 950, 440, P(
        'scan_manager',
        '스캔 순서 상태기계 — 시작 조건 → tare → DESCEND(윗면) → 방향 4 개(+x · −x · +y · −y) → 형상 계산 → 홈 복귀(마무리) → '
        '완료 · <b>작업 중지(STOPPED) · 안전복귀 · 재시작은 서로 독립</b> · 실패해도 자동 홈 없음',
        'scan_id · motion_id 발급 · 측정값 = /contact/event 의 판정 좌표 · /robot/sample 은 마지막 유효 pose 만(v0.1.21: 안전복귀 '
        '올림 목표 · 재시작 위치 확인) · 오류 뒤 재시작 허용 403 · 404 · 407(/safety/reset 후) · SetConfig 수락 → 세 노드에 '
        '표준 SetParameters 로 전파'
        + (' · <font color="#C0600A">용접 중(/weld/state)이면 START · RESUME 거절 601(P5 #204)</font>' if with_p2 else ''),
        param='descend_speed_mps · slide_speed_mps · move_speed_mps · recontact_speed_mps · max_descend_m · '
              'max_slide_m · motion_timeout_s · lift_height_m · recontact_margin_m · search_origin_pose · '
              'base_to_fixture · support_z_m · tip_radius_m · detect_latency_s · edge_round_radius_m · '
              'edge_bias_offset_m · result_dir · result_frame_id · motion_frame_id · direction_order · '
              '*_timeout_s · pose_max_age_s' + (' · weld_state_timeout_s' if with_p2 else '')), NODE, cid='SM')
    p.v(230, 1650, 440, 100, '<b>geometry_estimator</b> (계산 모듈 · 노드 아님)<br/>편향 보정 d = √(2rδ − δ²) · 윗면 '
        '사각형 · 외곽 엣지 · 경로 후보 4 · 지지면 투영 직육면체(꼭짓점 8 · 모서리 12)', MOD, cid='GE')
    RS = p.v(700, 1650, 420, 100, '<b>result_store</b> (로컬 원본 · 노드 아님)<br/>result_dir/&lt;scan_id&gt;/progress.json · '
             'result.json — 재시작의 원본(웹 DB 와 구분)', MOD, cid='RS')

    SAF = p.v(1350, 1330, 700, 280, P(
        'safety_monitor',
        '소프트웨어 이상 감시 → /robot/stop <b>즉시 로컬 요청(웹 경유 없음)</b> · 래치 · /safety/status',
        '구현된 감시 4 가지: 과대 외력 400(원시 |F|) · 하강 제한 205(SLIDE 첫 샘플 z 기준, 제한 + 여유 5 mm) · '
        '샘플 끊김 403 · 상태 끊김 404 · 정지 확인 0.6 s, 못 하면 2 s 마다 다시 요청 · 하드웨어 안전 대체 아님',
        '<font color="#6B7785">계약에만 있음: /scan/state 구독 · 웹 heartbeat 만료 405 · 속도 401 · 작업영역 402</font>',
        param='over_force_n · drop_limit_m · drop_limit_margin_m · confirm_n · startup_grace_s · sample_stale_ms · '
              'robot_status_timeout_ms · stop_confirm_timeout_s · stop_retry_period_s · status_publish_period_s · '
              'check_period_s'), NODE, cid='SAF')

    CD = p.v(200, 2130, 750, 260, P(
        'contact_detector',
        '접촉(CONTACT) · 접촉 소실(EDGE) · 과대 외력(OVER_FORCE) 판정 · tare(기준값 F₀) · 디바운스 · 이동 기준 · z 추세선 · 판정 모드는 '
        '샘플의 operation(DESCEND → CONTACT, 연속 SLIDE → EDGE, 모든 operation → OVER_FORCE) · 입력원 robot_force | sim · '
        '<b>스텝 모드 SLIDE(실기 기본)의 EDGE 는 robot_manager 가 낸다</b>',
        param='source · contact_threshold_n · edge_drop_m · debounce_n · over_force_n · over_force_debounce_n · '
              'edge_arm_* · edge_trend_* · edge_force_* · stale_age_ms · tare_* · descend_ref_* · '
              'descend_hold_threshold_n'), NODE, cid='CD')

    RM = p.v(1300, 2130, 1550, 280, P(
        'robot_manager',
        '모션 · 힘/순응 제어 · 상태 수집 — <b>두산 드라이버를 부르는 유일한 노드</b>(RG2 호출은 코드에 없음) · 단위(mm · deg ↔ m · rad) 변환 · '
        'sample_id 발급 · 샘플 · 상태에 실행 중 goal 의 motion_id · operation 기록 · /contact/event 대조 뒤 자체 정지 · '
        '하강량 제한 1 차 · 순응 · 힘 제어 해제는 finally',
        'SLIDE 두 방식: slide_mode = step(실기 기본 — 조금씩 긁고 멈춰 힘을 읽어 모서리를 찾고 EDGE 를 직접 발행) | '
        'force(sim 기본 — 순응 · 힘 제어로 연속 밀기) · 두산 서비스 10 개를 한 줄로 차례로 부른다'
        + (' · <font color="#C0600A">/robot/execute_path(경유점 직선 이동, P1 #191 머지 전)</font>' if with_p2 else ''),
        param='home_joint_deg · home_speed_deg_s · drop_limit_m · slide_target_force_n · compliance_stiffness · '
              'arrival_* · motion_timeout_s · move_restart_max · release_force_time_s · frame_id · dsr_namespace · '
              'sample_rate_hz · status_rate_hz · service_timeout_s · slide_mode · step_*'), NODE, cid='RM')

    DSR = p.v(1300, 2520, 750, 150, P(
        '[외부] 두산 드라이버 doosan-robot2',
        'dsr_controller2 · 네임스페이스 dsr01 · 모델 m0609 · dsr_msgs2 서비스 · joint_state_broadcaster → '
        '/dsr01/joint_states · mode:=virtual 에뮬레이터는 힘 제어 미동작 가능'), EXT, cid='DSR')
    RG2 = p.v(2200, 2520, 650, 150, P(
        '[외부] OnRobot RG2 드라이버',
        'onrobot_driver · 계약상 탐침 파지 명령 창구 · 실기는 탐침을 쥔 채 운용하고 코드에서 부르지 않는다'), EXT, cid='RG2')
    CTRL = p.v(1300, 2870, 1550, 130, P(
        '[외부] M0609 컨트롤러 (DRCF) + RG2 · 무센서 탐침 팁 · 작업대',
        '비상정지 · 충돌 감지 · 협동 속도 제한은 여기가 담당. 소프트웨어는 이 설정을 바꾸지 않는다'), EXT, cid='CTRL')

    p.v(200, 2450, 1000, 270,
        '<b>정지 경로 3 가지 — 그림에서 따라가기</b><br/>'
        '① 웹 작업 중지: 브로커 → mqtt_bridge → <b>/scan/stop</b>(S) → scan_manager → <b>/robot/stop</b>(S) + ExecuteMotion '
        'cancel → robot_manager. 정지 <b>완료</b>는 /robot/status(connected · !moving)로 확인, 못 하면 STOP_UNCONFIRMED(407)<br/>'
        '② 접촉 판정: contact_detector → <b>/contact/event</b> → robot_manager 가 motion_id 를 대조해 스스로 멈춤. '
        'OVER_FORCE 는 대조 없이 우선 정지<br/>'
        '③ 안전 이상: robot_manager → /robot/sample · /robot/status → safety_monitor → <b>/robot/stop</b>(S, 웹 경유 없음) → '
        '래치 → 해제는 <b>/safety/reset</b>(조건이 사라졌을 때만)<br/>'
        '과대 외력 · 하강량 제한은 ② · ③ 두 겹(같은 값: SetConfig 가 P01 · P03 로 함께 전파). accepted = 접수일 뿐이다.',
        NOTE)

    # ── 선 ────────────────────────────────────────────────────────────────
    def E(src, tgt, cat, kind, sside, spos, tside, tpos, via, text, at, w=240, dashed=False, color=None, layer='1',
          lh=None):
        ls = LBL_P2 if layer == L2 else LBL
        return p.e(src, tgt, edge_style(cat, kind, dashed, color=color), sside, spos, tside, tpos, via=via,
                   label=text, label_at=at, label_w=w, label_style=ls, layer=layer, label_h=lh)

    T1, T2 = 960, 1170   # MB ↔ 2 행 사이 라벨 높이 두 단
    # mqtt_bridge ↔ scan_manager
    E(MB, SM, 'cmd', 'A', 'B', 260, 'T', 260, [], lab('/scan/run · /scan/home · /scan/resume', 'A', 'L01 · L02 · L03',
      '작업 시작 · 안전복귀 · 재시작(별도 Action)'), (260, T1), w=250)
    E(MB, SM, 'cmd', 'S', 'B', 440, 'T', 440, [], lab('/scan/stop · /scan/set_config', 'S', 'L04 · L05',
      '작업 중지(접수 ≠ 정지 완료) · 설정 등록(동작 중 거절)'), (440, T2), w=250)
    E(MB, SM, 'cmd', 'A', 'B', 620, 'T', 620, [], lab('/scan/calibrate', 'A', 'C01', '검토안(MVP 밖) · 구현 없음'),
      (620, T1), w=200, dashed=True)
    E(SM, MB, 'show', 'T', 'T', 800, 'B', 800, [], lab('/scan/state · /scan/result · /scan/log', 'T', 'L06 · L07 · L08',
      '단계 · 진행 n/4 · 형상 결과(무효값 NaN + *_valid) · 로그'), (800, T2), w=250)
    E(SM, MB, 'show', 'T', 'T', 1000, 'B', 1000, [], lab('/calibration/result', 'T', 'C02', '검토안(MVP 밖)'),
      (1000, T1), w=190, dashed=True)
    # mqtt_bridge ↔ safety_monitor
    E(SAF, MB, 'safety', 'T', 'T', 1420, 'B', 1420, [], lab('/safety/status', 'T', 'L25', '표시 · 래치 여부'), (1420, T1),
      w=190)
    E(MB, SAF, 'safety', 'T', 'B', 1650, 'T', 1650, [], lab('/web/heartbeat', 'T', 'L26',
      '<font color="#6B7785">계약만 — 웹이 hb/web 을 안 보내고 safety_monitor 도 구독하지 않음</font>'), (1650, T2),
      w=240, dashed=True, color=CAT['gap'])
    E(MB, SAF, 'safety', 'S', 'B', 1900, 'T', 1900, [], lab('/safety/reset', 'S', 'L27',
      '안전 래치 해제 · 조건 해소 때만 · 로봇은 안 움직임'), (1900, T1), w=220)
    # 브로커 ↔ mqtt_bridge · 웹 ↔ 브로커
    E(BRK, MB, 'ext', 'X', 'B', 1750, 'T', 1750, [], lab('MQTT cmd/scan/+ · cmd/safety/reset · hb/web · conn/web',
      '외부', 'X01', '웹 명령 · (heartbeat · 연결: 웹이 아직 안 보냄)'), (1750, 528), w=250)
    E(MB, BRK, 'ext', 'X', 'T', 2050, 'B', 2050, [], lab('MQTT robot/* · scan/* · contact/event · safety/status · '
      'cmd/ack · scan/command_result · hb/ros · conn/ros', '외부', 'X02', '표시 · 접수 · 완료'), (2050, 528), w=300)
    E(WEB, BRK, 'store', 'XX', 'R', 395, 'L', 395, [], lab('MQTT 발행 · 구독', '외부', 'X03',
      'FastAPI = 명령 발행 · 표시 구독 · DB 쓰기'), (1425, 395), w=250)

    # scan_manager ↔ contact_detector (세로)
    E(SM, CD, 'show', 'T', 'B', 280, 'T', 280, [], lab('/scan/state', 'T', 'L09', 'scan_id 태깅'), (280, 1860), w=170)
    E(SM, CD, 'motion', 'S', 'B', 450, 'T', 450, [], lab('/contact/tare', 'S', 'L12', '외력 기준값 F₀(무접촉 · 정지)'),
      (450, 2040), w=200)
    E(SM, CD, 'cmd', 'S', 'B', 620, 'T', 620, [], lab('/contact_detector/set_parameters', 'S', 'P02',
      'SetConfig 전파(임계값 · 디바운스 · 과대 외력)'), (620, 1860), w=240)
    E(CD, SM, 'contact', 'T', 'T', 800, 'B', 800, [], lab('/contact/event', 'T', 'L20', '판정 좌표 = 측정값(정지 좌표와 구분)'),
      (800, 2040), w=200)
    # contact_detector → mqtt_bridge (왼쪽 길)
    E(CD, MB, 'contact', 'T', 'L', 2200, 'L', 790, [(130, 2200), (130, 790)],
      lab('/contact/event', 'T', 'L21', '표시(즉시)'), (130, 1300), w=110)

    # scan_manager ↔ robot_manager (Z 모양, 안쪽부터)
    xs = [900, 950, 1000, 1050, 1100]
    ys = [2060, 2005, 1950, 1895, 1840]
    xe = [1600, 1650, 1700, 1750, 1800]
    lx = 1450
    E(SM, RM, 'motion', 'A', 'B', xs[4], 'T', xe[4], [(xs[4], ys[4]), (xe[4], ys[4])],
      lab('/robot/execute_motion', 'A', 'L11', 'MOVE_TO · DESCEND · SLIDE · HOME · Result = 정지 pose + 사유'), (lx, ys[4]),
      w=290, lh=36)
    E(SM, RM, 'safety', 'S', 'B', xs[3], 'T', xe[3], [(xs[3], ys[3]), (xe[3], ys[3])],
      lab('/robot/stop', 'S', 'L22', '작업 중지 · 실패 때 정지(정지 경로 ①)'), (lx, ys[3]), w=290, lh=36)
    E(SM, RM, 'cmd', 'S', 'B', xs[2], 'T', xe[2], [(xs[2], ys[2]), (xe[2], ys[2])],
      lab('/robot_manager/set_parameters', 'S', 'P01', 'slide_target_force_n · drop_limit_m 전파'), (lx, ys[2]), w=290, lh=36)
    E(RM, SM, 'state', 'T', 'T', xe[1], 'B', xs[1], [(xe[1], ys[1]), (xs[1], ys[1])],
      lab('/robot/status · /robot/sample', 'T', 'L16 · L30', '시작 조건 · 정지 완료 / 마지막 유효 pose(v0.1.21)'), (lx, ys[1]),
      w=290, lh=36)
    E(RM, SM, 'contact', 'T', 'T', xe[0], 'B', xs[0], [(xe[0], ys[0]), (xs[0], ys[0])],
      lab('/contact/event', 'T', 'L28', '스텝 모드 SLIDE 의 EDGE(v0.1.15)'), (lx, ys[0]), w=290, lh=36)

    # contact_detector ↔ robot_manager (가로)
    E(CD, RM, 'contact', 'T', 'R', 2240, 'L', 2240, [], lab('/contact/event', 'T', 'L19', 'motion_id 대조 뒤 자체 정지(경로 ②)'),
      (1125, 2240), w=300, lh=36)
    E(RM, CD, 'state', 'T', 'L', 2330, 'R', 2330, [], lab('/robot/sample', 'T', 'L13',
      'TCP · 힘 + motion_id · operation(50 Hz 설정, 실기 약 43 Hz)'), (1125, 2330), w=300, lh=36)

    # scan_manager ↔ safety_monitor (가로)
    E(SM, SAF, 'safety', 'T', 'R', 1380, 'L', 1380, [], lab('/scan/state', 'T', 'L10',
      '<font color="#6B7785">계약만 · 구독 없음</font>'), (1250, 1380), w=190, dashed=True, color=CAT['gap'])
    E(SM, SAF, 'cmd', 'S', 'R', 1450, 'L', 1450, [], lab('/safety_monitor/set_parameters', 'S', 'P03',
      'over_force_n · drop_limit_m(두 겹 같은 값)'), (1250, 1450), w=190)
    E(SAF, SM, 'safety', 'T', 'L', 1530, 'R', 1530, [], lab('/safety/status', 'T', 'L24', '래치면 시작 · 재시작 거절'),
      (1250, 1530), w=190)

    # safety_monitor ↔ robot_manager (세로)
    E(RM, SAF, 'state', 'T', 'T', 1900, 'B', 1900, [], lab('/robot/sample · /robot/status', 'T', 'L14 · L17',
      '값 · 최신성 · 하강 제한 2 차 · 연결 · 정지 확인'), (1900, 1880), w=200)
    E(SAF, RM, 'safety', 'S', 'B', 2000, 'T', 2000, [], lab('/robot/stop', 'S', 'L23', '안전 이상 정지(경로 ③) · 웹 경유 없음'),
      (2000, 2045), w=190)

    # robot_manager · 두산 드라이버 → mqtt_bridge (오른쪽 길)
    E(RM, MB, 'state', 'T', 'R', 2180, 'R', 800, [(2920, 2180), (2920, 800)],
      lab('/robot/sample · /robot/status', 'T', 'L15 · L18', '표시(샘플은 다운샘플)'), (2920, 1880), w=110)
    E(RM, MB, 'contact', 'T', 'R', 2230, 'R', 760, [(3010, 2230), (3010, 760)],
      lab('/contact/event', 'T', 'L29', '스텝 EDGE 표시'), (3010, 2040), w=100)
    E(DSR, MB, 'state', 'T', 'B', 1900, 'R', 720, [(1900, 2720), (3100, 2720), (3100, 720)],
      lab('/dsr01/joint_states', 'T', 'P04', 'sensor_msgs/JointState · 표시 전용 → robot/joints'), (2980, 2720), w=260)

    # 외부 드라이버 · 컨트롤러
    E(RM, DSR, 'motion', 'XX', 'B', 1450, 'T', 1450, [], lab('dsr_msgs2 서비스', '외부', 'X04', '이동 · 순응/힘 · 정지 · 조회'),
      (1450, 2465), w=200)
    E(DSR, RM, 'state', 'X', 'T', 1700, 'B', 1700, [], lab('조회 응답', '외부', 'X05', 'TCP · 외력 · 상태'), (1700, 2465), w=150)
    E(RM, RG2, 'motion', 'X', 'B', 2400, 'T', 2400, [], lab('RG2 명령', '외부', 'X06',
      '<font color="#6B7785">계약만 · 코드 호출 없음</font>'), (2400, 2465), w=170, dashed=True, color=CAT['gap'])
    E(DSR, CTRL, 'ext', 'XX', 'B', 1600, 'T', 1600, [], lab('DRCF TCP/IP', '외부', 'X07', '모션 · 힘 제어 / 상태 · 외력 추정'),
      (1600, 2770), w=230)
    E(RG2, CTRL, 'ext', 'XX', 'B', 2500, 'T', 2500, [], lab('RG2 명령 · 상태', '외부', 'X08', '파지 / 폭'), (2500, 2770), w=160)

    # ── phase 2 ──────────────────────────────────────────────────────────
    if with_p2:
        WM = p.v(2250, 1330, 600, 330, P(
            '<font color="#C0600A">weld_manager [phase 2]</font>',
            '스캔 결과(result.json)의 모서리 8 개를 45° 자세 · 스탠드오프 · 위빙 경유점으로 따라가는 용접 순서 · '
            '선마다 접근 → 경로 → 후퇴 · 중지 · 안전복귀 · 스캔 중(/scan/state)이면 시작 거절 600',
            '<font color="#C0600A">구현 PR #195 → #196 → #197 머지 전 · Virtual 8 선 완주(sim 박스) · 실기 9/29</font>',
            param='weld_speed_mps · standoff_m · weave_* · tilt_deg · approach_m · travel_clearance_m · tool_profile_* · '
                  'path_tolerance_m · path_point_dwell_s · continue_on_line_failure · top_line_offset_dir · …'),
            NODE_P2, cid='WM', layer=L2)
        p.v(2270, 1580, 560, 62, '<b>결과 파일</b> (weld_record · 노드 아님) [W18]<br/>result_dir/&lt;scan_id&gt;/weld/&lt;weld_id&gt;.json',
            MOD.replace('strokeColor=#5566B5', f'strokeColor={P2}'), layer=L2)
        G = '<font color="#6B7785">계약만 · 브리지 구현 없음</font>'
        E(MB, WM, 'cmd', 'A', 'B', 2310, 'T', 2310, [], lab('/weld/run · /weld/home', 'A', 'W01 · W02',
          '용접 시작 · 안전복귀<br/>' + G), (2310, T1), w=200, layer=L2, dashed=True, color=CAT['gap'])
        E(MB, WM, 'cmd', 'S', 'B', 2500, 'T', 2500, [], lab('/weld/stop', 'S', 'W03', '용접 중지<br/>' + G), (2500, T2), w=170,
          layer=L2, dashed=True, color=CAT['gap'])
        E(WM, MB, 'show', 'T', 'T', 2700, 'B', 2700, [], lab('/weld/state · /weld/result · /weld/log', 'T', 'W04 · W05 · W06',
          '단계 · 선 번호 · 결과 · 로그<br/>' + G), (2700, T1), w=220, layer=L2, dashed=True, color=CAT['gap'])
        E(BRK, MB, 'ext', 'X', 'B', 2350, 'T', 2350, [], lab('MQTT cmd/weld/+', '외부', 'W16', G), (2350, 528), w=180,
          layer=L2, dashed=True, color=CAT['gap'])
        E(MB, BRK, 'ext', 'X', 'T', 2600, 'B', 2600, [], lab('MQTT weld/*', '외부', 'W17', G), (2600, 528), w=170,
          layer=L2, dashed=True, color=CAT['gap'])
        E(SAF, WM, 'safety', 'T', 'R', 1400, 'L', 1400, [], lab('/safety/status', 'T', 'W10', '래치면 시작 거절'),
          (2150, 1400), w=170, layer=L2)
        E(SM, WM, 'show', 'T', 'R', 1660, 'L', 1450, [(2150, 1660), (2150, 1450)],
          lab('/scan/state', 'T', 'W08', '스캔 중이면 용접 시작 거절 600 · 없거나 5 s 넘으면 101'), (1480, 1660), w=250, layer=L2)
        E(WM, SM, 'show', 'T', 'L', 1500, 'R', 1700, [(2180, 1500), (2180, 1700)],
          lab('/weld/state', 'T', 'W07', '용접 중이면 스캔 START · RESUME 거절(601, #204 main)'), (1760, 1700), w=260,
          layer=L2)
        E(RS, WM, 'store', 'F', 'R', 1730, 'L', 1550, [(2210, 1730), (2210, 1550)],
          lab('result.json 읽기', '파일', 'W15', 'scan_manager(result_store)가 쓴 스캔 결과 · "" = 최신 · ROS 아님'), (1480, 1730), w=250,
          layer=L2)
        E(RM, WM, 'state', 'T', 'T', 2320, 'B', 2320, [], lab('/robot/status · /robot/sample', 'T', 'W09 · W11',
          '연결 · 정지 완료 / 시작 위치 · 툴 점검 · 실패 뒤 팁 z'), (2320, 1790), w=200, layer=L2)
        E(WM, RM, 'motion', 'A', 'B', 2500, 'T', 2500, [], lab('/robot/execute_path · /robot/execute_motion', 'A',
          'W12 · W13', '경유점 경로(위빙) / 접근 · 후퇴 · 복구 · 홈'), (2500, 1960), w=220, layer=L2)
        E(WM, RM, 'safety', 'S', 'B', 2700, 'T', 2700, [], lab('/robot/stop', 'S', 'W14', "requester='weld_manager'"),
          (2700, 1790), w=180, layer=L2)
    return p


# ── 간략 (발표용, docs/design/contact-scan-node-overview-v1.2 형식) ─────────
OV_NODE = ('rounded=1;arcSize=30;whiteSpace=wrap;html=1;fillColor=#EAF4FC;strokeColor=#C4DCF0;strokeWidth=2;'
           'fontColor=#1B5CA6;align=center;verticalAlign=middle;fontSize=14;')
OV_EXT = ('rounded=1;arcSize=30;whiteSpace=wrap;html=1;fillColor=#F4F8FC;strokeColor=#B9C9D8;strokeWidth=2;'
          'fontColor=#1B5CA6;align=center;verticalAlign=middle;dashed=1;dashPattern=8 6;fontSize=14;')
OV_P2 = OV_NODE.replace('fillColor=#EAF4FC;strokeColor=#C4DCF0', f'fillColor={P2_FILL};strokeColor={P2}').replace(
    'fontColor=#1B5CA6', 'fontColor=#A34C08')
OV_EDGE = ('edgeStyle=orthogonalEdgeStyle;rounded=1;arcSize=10;html=1;strokeColor=#B9CCDD;strokeWidth=2.5;'
           'endArrow=open;endFill=0;endSize=8;')
OV_LBL = ('rounded=1;arcSize=50;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#B9CCDD;strokeWidth=1.5;'
          'fontSize=13;fontColor=#2C5F9C;align=center;verticalAlign=middle;')


def overview_page():
    p = Page('노드 구조도 (간략) v1.3', 2200, 1180, pid='node-overview')
    p.layer(L2, 'phase 2 (용접) — 끄면 1차만')
    p.text(40, 30, 1200, 40, '접촉 스캔 시스템 — 노드 구조도 (간략) v1.3', size=26, color='#1B5CA6', bold=True)
    p.text(40, 72, 2100, 30, '실선 상자 = 자체 ROS 2 노드 5 개 · 점선 상자 = 외부(제공 드라이버 · 웹) · 화살표 = 데이터 · 명령 방향 · '
           '<font color="#C0600A">주황 = phase 2 용접(레이어로 끄고 켬)</font> · 상세는 같은 파일 1 쪽 · 계약 v0.1.22 (2026-09-28)',
           size=14, color='#6B8199')
    n = {}
    n['WEB'] = p.v(860, 110, 400, 90, '<b style="font-size:18px">웹 관제</b><br/>React · FastAPI · MQTT 브로커', OV_EXT)
    n['MB'] = p.v(860, 280, 400, 90, '<b style="font-size:18px">mqtt_bridge</b><br/>ROS 2 ↔ MQTT 변환 · 상태 중계', OV_NODE)
    n['SM'] = p.v(860, 500, 400, 100, '<b style="font-size:18px">scan_manager</b><br/>스캔 순서 · 중지 · 안전복귀 · 재시작 · '
                  '형상 계산 · 원본 보관', OV_NODE)
    n['SAF'] = p.v(1560, 500, 400, 100, '<b style="font-size:18px">safety_monitor</b><br/>이상 감시 · 로컬 정지 · 래치', OV_NODE)
    n['RM'] = p.v(360, 500, 360, 100, '<b style="font-size:18px">robot_manager</b><br/>M0609 명령 · 스텝 모서리 탐색 · 상태 보고',
                  OV_NODE)
    n['CD'] = p.v(860, 780, 400, 100, '<b style="font-size:18px">contact_detector</b><br/>접촉과 엣지 판정', OV_NODE)
    n['DSR'] = p.v(40, 420, 260, 90, '<b style="font-size:18px">dsr_controller2</b><br/>두산 ROS 2 드라이버', OV_EXT)
    n['RG2'] = p.v(40, 590, 260, 90, '<b style="font-size:18px">onrobot_driver</b><br/>탐침 파지 (코드 호출 없음)', OV_EXT)
    n['WM'] = p.v(1560, 780, 400, 100, '<b style="font-size:18px">weld_manager</b><br/>모서리 8 개 용접 모션(위빙)', OV_P2,
                  layer=L2)

    def OE(a, b, sx, sy, tx, ty, via=(), label=None, lx=0, ly=0, lw=150, layer='1', dashed=False):
        st = OV_EDGE + f'exitX={sx};exitY={sy};exitDx=0;exitDy=0;entryX={tx};entryY={ty};entryDx=0;entryDy=0;'
        if dashed:
            st += 'dashed=1;dashPattern=8 6;'
        if layer == L2:
            st = st.replace('strokeColor=#B9CCDD', f'strokeColor={P2}')
        cid = p._id('e')
        p.cells.append(dict(id=cid, value='', style=st, edge='1', parent=layer, source=n[a], target=n[b],
                            geo=dict(relative='1'), points=list(via)))
        if label:
            ls = OV_LBL if layer != L2 else OV_LBL.replace('strokeColor=#B9CCDD', f'strokeColor={P2}').replace(
                'fontColor=#2C5F9C', 'fontColor=#A34C08')
            p.v(lx, ly, lw, 36, label, ls, layer=layer)

    OE('WEB', 'MB', 0.45, 1, 0.45, 0, label='MQTT 명령', lx=903, ly=222, lw=114)
    OE('MB', 'WEB', 0.55, 0, 0.55, 1, label='MQTT 상태 · 결과', lx=1105, ly=222, lw=170)
    OE('MB', 'SM', 0.25, 1, 0.25, 0, label='시작 · 중지 · 안전복귀 · 재시작 · 설정', lx=760, ly=410, lw=300)
    OE('SM', 'MB', 0.75, 0, 0.75, 1, label='상태 · 결과 · 로그', lx=1090, ly=440, lw=170)
    OE('MB', 'SAF', 1, 0.5, 0.5, 0, via=[(1760, 325)], label='안전 해제', lx=1700, ly=392, lw=120)
    OE('SM', 'RM', 0, 0.25, 1, 0.25, label='동작 · 정지 · 설정 전파', lx=727, ly=468, lw=126)
    OE('RM', 'SM', 1, 0.75, 0, 0.75, label='로봇 상태 · 위치', lx=740, ly=556, lw=112)
    OE('SM', 'SAF', 1, 0.25, 0, 0.25, label='설정 전파', lx=1350, ly=468, lw=140)
    OE('SAF', 'SM', 0, 0.75, 1, 0.75, label='안전 상태', lx=1364, ly=556, lw=112)
    OE('SM', 'CD', 0.375, 1, 0.35, 0, label='tare · 설정 전파', lx=860, ly=650, lw=170)
    OE('CD', 'SM', 0.65, 0, 0.625, 1, label='접촉 · 엣지 이벤트', lx=1080, ly=700, lw=170)
    OE('RM', 'CD', 0.8, 1, 0, 0.3, via=[(648, 810)], label='TCP · 외력 · 실행 중 동작', lx=610, ly=792, lw=210)
    OE('CD', 'RM', 0, 0.7, 0.6, 1, via=[(576, 850)], label='접촉 · 과대 외력 → 정지', lx=560, ly=842, lw=200)
    OE('RM', 'SAF', 0.15, 1, 0.25, 1, via=[(414, 990), (1660, 990)], label='TCP · 외력 · 로봇 상태', lx=905, ly=972, lw=220)
    OE('SAF', 'RM', 0.5, 1, 0.4, 1, via=[(1760, 1040), (504, 1040)], label='안전 정지 (웹 경유 없음)', lx=1248, ly=1022,
       lw=203)
    OE('RM', 'DSR', 0, 0.25, 1, 0.5, via=[(330, 525), (330, 465)])
    OE('RM', 'RG2', 0, 0.75, 1, 0.5, via=[(330, 575), (330, 635)], dashed=True)
    OE('MB', 'WM', 1, 0.75, 1, 0.5, via=[(2020, 348), (2020, 830)], label='용접 명령 · 상태', lx=1950, ly=640, lw=150,
       layer=L2)
    OE('WM', 'RM', 0.25, 1, 0.9, 1, via=[(1660, 940), (684, 940)], label='경유점 경로 · 정지', lx=1300, ly=922, lw=170,
       layer=L2)
    OE('WM', 'SM', 0, 0.5, 1, 0.9, via=[(1400, 830), (1400, 590)], label='스캔 ↔ 용접 배타', lx=1330, ly=690, lw=150,
       layer=L2)
    return p


def main():
    pages = [detail_page(True), detail_page(False), overview_page()]
    out = HERE / '06-node-graph.drawio'
    write_mxfile(out, pages)
    print(out)


if __name__ == '__main__':
    main()
