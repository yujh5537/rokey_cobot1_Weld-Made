"""산출물 05 인터페이스 정의서의 그림 drawio 를 만든다 → 05-interfaces.drawio

쪽 2 개 (05-interfaces.md 1 · 7.5 절의 그림):
  1. 명령 한 번의 흐름 — 접수 ≠ 완료 (시작 → 완료, 작업 중지). 시퀀스 그림
  2. 정지 경로 3 가지 — 요청 · 접수 · 완료 확인
근거: docs/contracts/ros-interfaces.md 1장 · 7.1 · mqtt-schema.md 3장 · 코드(origin/main 2335057)
실행: python3 docs/deliverables/drawio_05.py
"""
import pathlib

from drawio_lib import CAT, Page, write_mxfile

HERE = pathlib.Path(__file__).resolve().parent

LIFE = [  # 이름, 부제, 채움, 테두리
    ('브라우저', 'React + Three.js', '#E3E7EC', '#A9B3BE'),
    ('FastAPI', ':8000', '#F1DCEB', '#C79BBD'),
    ('MQTT 브로커', 'Mosquitto :1883', '#DCE2E9', '#94A0AE'),
    ('mqtt_bridge', 'ROS 2 ↔ MQTT', '#D3DCF5', '#22357F'),
    ('scan_manager', '상태기계', '#D3DCF5', '#22357F'),
    ('robot_manager', '모션 · 드라이버 창구', '#D3DCF5', '#22357F'),
    ('contact_detector', '접촉 판정', '#D3DCF5', '#22357F'),
]


def sequence_page():
    p = Page('명령 한 번의 흐름 — 접수 ≠ 완료', 2400, 2100, pid='command-flow')
    p.text(40, 20, 2300, 44, '명령 한 번의 흐름 — 접수(cmd/ack) ≠ 완료(scan/command_result)', size=28, color='#12294D', bold=True)
    p.text(40, 66, 2300, 50, '근거: docs/contracts/mqtt-schema.md 3장 · ros-interfaces.md 1장 · 7.1 · 코드 origin/main 2335057 (2026-09-28) · '
           '화살표 색 = 갈래(01 · 06 과 같다) · 점선 = 응답 · 회색 쪽지 = 그 노드 안에서 하는 일', size=14, color='#4A5666')
    x0, dx = 150, 320
    xs = [x0 + i * dx for i in range(len(LIFE))]
    top, bottom = 140, 2060
    lifelines = []
    for (name, sub, fill, stroke), x in zip(LIFE, xs):
        p.v(x - 120, top, 240, 64, f'<b style="font-size:17px">{name}</b><br/><font style="font-size:12px">{sub}</font>',
            f'rounded=1;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};strokeWidth=2;fontColor=#12294D;'
            'align=center;verticalAlign=middle;')
        lifelines.append(p.free_edge(x, top + 64, x, bottom, 'endArrow=none;html=1;strokeColor=#9AA3AD;strokeWidth=1.5;'
                                     'dashed=1;dashPattern=6 5;'))

    y = [top + 110]

    def msg(a, b, text, cat, dashed=False, dy=58):
        xa, xb = xs[a], xs[b]
        st = (f'endArrow=blockThin;endFill=1;endSize=9;html=1;strokeColor={CAT[cat]};strokeWidth=2.4;fontSize=13;'
              f'fontColor=#16202B;labelBackgroundColor=#FFFFFF;verticalAlign=bottom;')
        if dashed:
            st += 'dashed=1;dashPattern=8 5;'
        cid = p.free_edge(xa, y[0], xb, y[0], st)
        for c in p.cells:
            if c['id'] == cid:
                c['value'] = text
        y[0] += dy

    def note(i, text, w=300, h=46, dy=62, color='#F4F6F8'):
        p.v(xs[i] - w / 2, y[0] - 18, w, h, text, f'rounded=1;whiteSpace=wrap;html=1;fillColor={color};strokeColor=#C2CBD5;'
            'fontSize=12;fontColor=#33465C;align=center;verticalAlign=middle;')
        y[0] += dy

    def band(text, color):
        p.v(20, y[0] - 20, 2330, 36, f'<b>{text}</b>', f'rounded=0;whiteSpace=wrap;html=1;fillColor={color};strokeColor=none;'
            'fontSize=15;fontColor=#12294D;align=left;verticalAlign=middle;spacingLeft=12;opacity=90;')
        y[0] += 50

    band('작업 시작 → 완료 (1.1 ~ 1.4 절)', '#E8EDFA')
    msg(0, 1, '① 버튼 "시작" → POST /commands/scan/start', 'cmd')
    note(1, 'request_id(UUID v4) · timestamp_ms · schema_version "0.1" 을 붙인다', w=330)
    msg(1, 2, '② cmd/scan/start (QoS 1 · retain=false)', 'cmd')
    msg(1, 0, '③ REST 응답 {status: PUBLISHED} · WS command/status', 'show', dashed=True)
    msg(2, 3, '④ cmd/scan/start', 'cmd')
    note(3, '공통 검사: 형식 → 중복(최근 100) → 만료(5 s). 실패면 cmd/ack 거절(101 · 106)', w=330, h=52)
    msg(3, 4, '⑤ /scan/run goal (Action)', 'cmd')
    msg(4, 3, '⑥ goal 수락 (늘 받는다 — 거절 사유는 Result 로)', 'cmd', dashed=True)
    msg(3, 2, '⑦ cmd/ack {accepted: true} = <b>접수</b>', 'show', dashed=True)
    msg(2, 1, '⑧ cmd/ack', 'show', dashed=True)
    msg(1, 0, '⑨ WS command/status ACCEPTED', 'show', dashed=True)
    note(4, '관문 100 · 108 · 102 · 601 · 103 · 104 → scan_id 발급 → progress.json', w=330, h=52)
    msg(4, 5, '⑩ /robot/execute_motion MOVE_TO → (tare) → DESCEND', 'motion')
    msg(5, 6, '⑪ /robot/sample 50 Hz (operation · motion_id)', 'state')
    msg(6, 5, '⑫ /contact/event CONTACT (판정 좌표)', 'contact')
    msg(6, 4, '⑫ 같은 이벤트 → z_top 기록', 'contact')
    msg(5, 4, '⑬ Result {정지 pose, reason, event_id}', 'motion', dashed=True)
    note(4, 'SLIDE × 4 (실기 스텝 모드: EDGE 는 robot_manager 가 낸다) → GEOMETRY', w=330, h=52)
    msg(4, 3, '⑭ /scan/state · /scan/result (1 회) · /scan/log', 'show')
    msg(3, 2, '⑮ scan/state (retain) · scan/result · scan/log (mm · null)', 'show')
    msg(2, 1, '⑯ → WS 방송 · scan/result 는 DB upsert', 'show')
    note(4, 'HOMING(올림 → OP_HOME) → DONE', w=300, h=40, dy=56)
    msg(4, 3, '⑰ RunScan Result {success, reason_code}', 'cmd', dashed=True)
    msg(3, 2, '⑱ scan/command_result {success: true} = <b>완료</b>', 'show', dashed=True)
    msg(2, 1, '⑲ scan/command_result', 'show', dashed=True)
    msg(1, 0, '⑳ WS command/status SUCCEEDED', 'show', dashed=True, dy=80)

    band('작업 중지 — 정지 경로 ① (1.5 절)', '#FBEDEC')
    msg(0, 1, '① 버튼 "중지" → POST /commands/scan/stop', 'cmd')
    msg(1, 2, '② cmd/scan/stop', 'cmd')
    msg(2, 3, '③ cmd/scan/stop', 'cmd')
    note(3, '만료 검사 제외 (늦게 와도 거절하지 않는다)', w=300, h=40, dy=56)
    msg(3, 4, "④ /scan/stop (Service · requester='mqtt_bridge')", 'cmd')
    msg(4, 3, '⑤ accepted = 접수 ≠ 정지 완료', 'cmd', dashed=True)
    msg(3, 2, '⑥ cmd/ack {accepted: true}', 'show', dashed=True)
    msg(4, 5, '⑦ /robot/stop + goal cancel (응답을 기다리지 않는다)', 'safety')
    note(5, 'move_stop → finally 순응 · 힘 제어 해제', w=300, h=40, dy=56)
    msg(5, 4, '⑧ /robot/status connected && !moving (요청 뒤 stamp)', 'state')
    note(4, 'STOPPED (5 s 안에 확인 못 하면 407 → ERROR) · 자동 홈 · 재시작 없음', w=330, h=52)
    msg(4, 3, '⑨ /scan/state phase=STOPPED', 'show')
    msg(3, 2, '⑩ scan/command_result {success: true, reason: STOP_REQUESTED} = <b>완료</b>', 'show', dashed=True)
    for c in p.cells:            # 생명선을 마지막 메시지 아래까지
        if c['id'] in lifelines:
            c['tp'] = (c['tp'][0], y[0] + 10)
    p.height = y[0] + 40
    return p


def stop_paths_page():
    p = Page('정지 경로 3 가지', 2400, 1250, pid='stop-paths')
    p.text(40, 20, 2300, 44, '정지 경로 3 가지 — 요청 · 접수 · 완료 확인은 다르다', size=28, color='#12294D', bold=True)
    p.text(40, 66, 2300, 50, '근거: docs/contracts/ros-interfaces.md 7.1 · 7.2 · 7.5 (v0.1.21) · 코드 origin/main 2335057 · '
           '완료는 어느 경로든 /robot/status 의 connected && !moving 으로만 본다', size=14, color='#4A5666')
    BOX = ('rounded=1;arcSize=18;whiteSpace=wrap;html=1;fillColor=#EAF4FC;strokeColor=#C4DCF0;strokeWidth=2;fontColor=#1B5CA6;'
           'align=center;verticalAlign=middle;fontSize=14;')
    ROW = [
        ('① 웹 작업 중지', '#5F7FD8',
         [('관제자', '버튼 "중지"'), ('mqtt_bridge', 'cmd/scan/stop → /scan/stop<br/>(만료 검사 제외)'),
          ('scan_manager', '/robot/stop + goal cancel<br/>StopScan.accepted = 접수'), ('robot_manager', 'move_stop · 순응 해제'),
          ('완료 확인', 'scan_manager 가 connected · !moving<br/>→ STOPPED (못 하면 407)')]),
        ('② 접촉 · 엣지 · 과대 외력', '#C99A1E',
         [('contact_detector', 'CONTACT · EDGE · OVER_FORCE<br/>(스텝 EDGE 는 robot_manager)'), ('/contact/event', '판정 확정 즉시 1 회'),
          ('robot_manager', 'motion_id 대조 → 자체 정지<br/>OVER_FORCE 는 대조 없이'), ('ExecuteMotion Result', '정지 pose + 사유<br/>(접수 단계 없음)'),
          ('완료 확인', 'Result + /robot/status')]),
        ('③ 안전 이상', '#D9736C',
         [('safety_monitor', '400 · 205 · 403 · 404<br/>기동 3 s 유예'), ('래치', '첫 원인 유지<br/>해제는 /safety/reset 만'),
          ('/robot/stop', "requester='safety_monitor'<br/>웹 경유 없음"), ('robot_manager', 'move_stop · Result.reason_code = 사유'),
          ('완료 확인', 'SafetyStatus.stop_confirmed<br/>0.6 s 넘으면 2 s 마다 다시 요청')]),
    ]
    y = 150
    for title, color, steps in ROW:
        p.v(40, y, 2320, 250, '', f'rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor={color};strokeWidth=3;arcSize=4;')
        p.v(40, y, 2320, 44, f'<b>{title}</b>', f'rounded=1;whiteSpace=wrap;html=1;fillColor={color};strokeColor={color};'
            'fontSize=17;fontColor=#FFFFFF;align=left;verticalAlign=middle;spacingLeft=16;arcSize=8;')
        prev = None
        for k, (name, text) in enumerate(steps):
            bx = 80 + k * 455
            last = k == len(steps) - 1
            st = BOX if not last else BOX.replace('fillColor=#EAF4FC;strokeColor=#C4DCF0', 'fillColor=#EEF7F5;strokeColor=#2E8B7A')
            cid = p.v(bx, y + 70, 380, 150, f'<b style="font-size:17px">{name}</b><br/>{text}', st)
            if prev:
                p.cells.append(dict(id=p._id('e'), value='', style=(
                    f'edgeStyle=orthogonalEdgeStyle;html=1;strokeColor={color};strokeWidth=3;endArrow=blockThin;endFill=1;'
                    'endSize=10;exitX=1;exitY=0.5;exitDx=0;exitDy=0;entryX=0;entryY=0.5;entryDx=0;entryDy=0;'),
                    edge='1', parent='1', source=prev, target=cid, geo=dict(relative='1')))
            prev = cid
        y += 290
    p.v(40, y, 2320, 150,
        '<b>두 겹 감시</b> — 과대 외력(30 N)과 하강 제한(SLIDE 첫 z 기준 5 mm)은 ②(또는 robot_manager 1 차)와 ③(safety_monitor 2 차, 하강은 '
        '+ 여유 5 mm = 10 mm)이 따로 본다. 값은 SetConfig 가 P01 · P02 · P03 로 같이 전파한다.<br/>'
        '<b>정지 KPI 두 가지</b> — 물리 정지 1 s 이내(로봇 실측) · STOPPED 표시 3 s 이내(상태 전이). accepted 는 둘 다 아니다.<br/>'
        '<b>정지 뒤</b> — 홈 복귀 · 재시작을 자동으로 부르지 않는다. 안전복귀 · 재시작 · 안전 해제는 사람이 누르는 독립 명령이다.',
        'rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFDF6;strokeColor=#C2A57C;strokeWidth=1.4;dashed=1;dashPattern=6 4;'
        'fontSize=15;fontColor=#4A3620;align=left;verticalAlign=middle;spacingLeft=14;spacingRight=12;')
    p.height = y + 180
    return p


def main():
    out = HERE / '05-interfaces.drawio'
    write_mxfile(out, [sequence_page(), stop_paths_page()])
    print(out)


if __name__ == '__main__':
    main()
