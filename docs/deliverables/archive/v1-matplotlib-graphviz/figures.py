"""산출물 01 · 06 그림을 만든다 (원본 = 이 파일 + 06-node-graph.dot).

    python3 docs/deliverables/archive/v1-matplotlib-graphviz/figures.py          # matplotlib · graphviz(dot) · Noto Sans CJK KR 필요

- 01-system-architecture.png            : 두 PC · 로봇 컨트롤러 · 노드 · 데이터 흐름 (phase 2 포함, 주황 점선)
- 01-system-architecture-no-phase2.png  : 같은 그림에서 phase 2 만 뺀 판 (9/29 에 용접을 빼면 슬라이드 그림만 바꾼다)
- 06-node-graph.png / -no-phase2.png    : 06-node-graph.dot 에서 dot 으로. "// P2" 가 붙은 줄이 phase 2 다
그림 안의 노드 · 토픽 · 서비스 · 액션 이름은 docs/contracts/ros-interfaces.md · docs/phase2/weld-ros-interfaces.md 와 같다.
"""
import pathlib
import re
import struct
import subprocess

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
FONT = 'Noto Sans CJK KR'
plt.rcParams['font.family'] = FONT

NAVY, NODE_FILL, GRAY, RED = '#22357F', '#FFFFFF', '#8A96A3', '#B00020'
P2, P2_FILL, P2_TEXT = '#D2691E', '#FFF1E0', '#8B3A00'
TEXT = '#1F2937'


def cluster(ax, x0, y0, x1, y1, label, edge, fill, dashed=False):
    ax.add_patch(FancyBboxPatch((x0, y0), x1 - x0, y1 - y0, boxstyle='round,pad=0,rounding_size=0.12',
                                linewidth=1.6, edgecolor=edge, facecolor=fill, linestyle='--' if dashed else '-'))
    ax.text(x0 + 0.12, y1 - 0.08, label, ha='left', va='top', fontsize=10.5, color=edge, fontweight='bold')


def box(ax, x0, y0, x1, y1, title, lines=(), edge=NAVY, fill=NODE_FILL, color=TEXT, dashed=False, lw=1.8,
        size=9.3, title_size=11.5):
    ax.add_patch(FancyBboxPatch((x0, y0), x1 - x0, y1 - y0, boxstyle='round,pad=0,rounding_size=0.08',
                                linewidth=lw, edgecolor=edge, facecolor=fill, linestyle='--' if dashed else '-'))
    cx = (x0 + x1) / 2
    n = len(lines)
    step = 0.21
    top = (y0 + y1) / 2 + (n * step) / 2
    ax.text(cx, top, title, ha='center', va='center', fontsize=title_size, fontweight='bold', color=color)
    for i, line in enumerate(lines):
        ax.text(cx, top - step * (i + 1) - 0.03, line, ha='center', va='center', fontsize=size, color=color)


def arrow(ax, p0, p1, label=None, color='#4B5563', both=False, lw=1.4, dashed=False, conn='arc3,rad=0',
          lpos=None, lsize=8.6, lcolor=None, ha='center', label_bg=True):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle='<|-|>' if both else '-|>', mutation_scale=11, color=color,
                                 linewidth=lw, linestyle=(0, (4, 3)) if dashed else '-', connectionstyle=conn,
                                 shrinkA=0, shrinkB=0))
    if label:
        x, y = lpos if lpos else ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2)
        bbox = dict(boxstyle='round,pad=0.12', facecolor='white', edgecolor='none', alpha=0.9) if label_bg else None
        ax.text(x, y, label, ha=ha, va='center', fontsize=lsize, color=lcolor or color, bbox=bbox, linespacing=1.25)


def poly(ax, pts, color='#4B5563', lw=1.4, dashed=False, both=False):
    """꺾은선. 마지막 구간에 화살촉(both 면 첫 구간에도)."""
    ls = (0, (4, 3)) if dashed else '-'
    for a, b in zip(pts[1:-2], pts[2:-1]):
        ax.plot([a[0], b[0]], [a[1], b[1]], color=color, linewidth=lw, linestyle=ls, solid_capstyle='butt')
    ax.add_patch(FancyArrowPatch(pts[-2], pts[-1], arrowstyle='-|>', mutation_scale=11, color=color, linewidth=lw,
                                 linestyle=ls, shrinkA=0, shrinkB=0))
    ax.add_patch(FancyArrowPatch(pts[1], pts[0], arrowstyle='-|>' if both else '-', mutation_scale=11, color=color,
                                 linewidth=lw, linestyle=ls, shrinkA=0, shrinkB=0))


def architecture(phase2):
    fig = plt.figure(figsize=(16, 7.1), dpi=150)
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 7.1)
    ax.axis('off')
    ax.text(0.15, 7.0, '시스템 아키텍처 v1.7 — 두 PC · 로봇 컨트롤러 · 노드 · 데이터 흐름', ha='left', va='top',
            fontsize=15, fontweight='bold', color=NAVY)
    legend = '(A) Action · (S) Service · 표시 없는 이름 = Topic · 빨강 = 안전 정지(웹 경유 없음) · 회색 점선 = 제공 드라이버'
    if phase2:
        legend += ' · 주황 점선 = phase 2 용접(구현 PR 진행 중)'
    ax.text(8.0, 0.1, legend, ha='center', va='center', fontsize=9, color='#4B5563')
    lab = dict(fontsize=8.2, color='#374151', va='center')

    # ── 브라우저 · 웹 PC ──────────────────────────────────────────────
    cluster(ax, 0.15, 5.35, 4.05, 6.65, '브라우저 (관제자)', '#6B7280', '#F4F4F4')
    box(ax, 0.35, 5.45, 3.85, 6.35, 'React + Three.js 관제 화면',
        ['Vite 5173 · Docker 밖 (npm run dev)', '3D 형상 · 접촉점 · 로그 · 버튼 5'])
    cluster(ax, 0.15, 0.3, 4.05, 4.95, '웹 PC — docker compose 4 서비스', '#A05195', '#FAEFF7')
    box(ax, 0.35, 3.7, 3.85, 4.55, 'FastAPI :8000', ['REST /commands/* · WS /ws · DB 쓰기'])
    box(ax, 1.45, 2.45, 3.85, 3.25, 'Mosquitto :1883', ['MQTT 브로커 · 중계만'])
    box(ax, 0.35, 0.5, 1.85, 1.6, 'PostgreSQL', [':5432', '측정 · 설정 · 이벤트'], size=8.6, title_size=10.5)
    box(ax, 2.15, 0.5, 3.85, 1.6, 'Spring Boot', [':8080 /api/*', '작업 · 대상물 · 이력'], size=8.6, title_size=10.5)
    arrow(ax, (3.35, 5.45), (3.35, 4.55), None, both=True)
    ax.text(3.27, 5.13, 'REST 명령 · WS 실시간', ha='right', **lab)
    arrow(ax, (2.65, 3.7), (2.65, 3.25), None, both=True)
    ax.text(2.73, 3.48, 'MQTT', ha='left', **lab)
    arrow(ax, (0.9, 3.7), (0.9, 1.6), None)
    ax.text(0.97, 2.6, '측정 ·\n설정\n쓰기', ha='left', **lab)
    arrow(ax, (2.15, 1.05), (1.85, 1.05), None, both=True)
    ax.text(2.0, 1.27, '조회', ha='center', **lab)

    # ── 메인 PC ───────────────────────────────────────────────────────
    main_label = '메인 PC — Ubuntu 24.04 · ROS 2 Jazzy · 자체 노드 5'
    if phase2:
        main_label += ' + weld_manager (phase 2)'
    cluster(ax, 4.45, 0.3, 13.4, 6.65, main_label, '#5566B5', '#EFF1FB')
    box(ax, 4.65, 2.25, 5.95, 4.55, 'mqtt_bridge', ['ROS 2 ↔ MQTT', 'm → mm', 'NaN → null', '명령 중복 ·', '만료 검사'],
        size=8.8, title_size=10.2)
    arrow(ax, (3.85, 2.85), (4.65, 2.85), None, both=True, lw=2.4, color=NAVY)
    ax.text(4.25, 3.05, 'MQTT', fontsize=8.4, color=NAVY, ha='center', va='center')

    cluster(ax, 6.75, 3.75, 9.35, 6.3, 'scan_manager (노드)', NAVY, '#D3DCF5')
    box(ax, 6.9, 4.95, 9.2, 5.98, 'scan_manager', ['스캔 순서 상태기계', '중지 · 안전복귀 · 재시작', '설정 전파 (SetConfig)'],
        size=8.8, title_size=11)
    box(ax, 6.9, 3.88, 7.98, 4.8, 'geometry_', ['estimator', '5 점 → 형상'], lw=1, size=8.4, title_size=9.2)
    box(ax, 8.12, 3.88, 9.2, 4.8, 'result_store', ['progress.json', 'result.json'], lw=1, size=8.4, title_size=9.2)
    box(ax, 7.1, 2.3, 9.2, 3.3, 'safety_monitor', ['과대 외력 · 하강 제한 2차', '샘플 최신성', '→ 정지 요청 · 래치'],
        size=8.6, title_size=11)
    box(ax, 11.15, 5.0, 13.25, 6.05, 'contact_detector', ['CONTACT · EDGE ·', 'OVER_FORCE 판정 · tare'],
        size=8.8, title_size=11)
    box(ax, 11.15, 2.55, 13.25, 4.0, 'robot_manager', ['모션 · 힘/순응 제어와 해제', 'TCP · 힘 샘플 발행', '드라이버 호출 단일 창구'],
        size=8.8, title_size=11)
    box(ax, 11.1, 1.2, 12.2, 2.0, '두산 드라이버', ['dsr_controller2'], edge=GRAY, fill='#E9EDF1', dashed=True,
        lw=1.2, size=7.4, title_size=8.4)
    box(ax, 12.28, 1.2, 13.3, 2.0, 'RG2 드라이버', ['onrobot_driver'], edge=GRAY, fill='#E9EDF1', dashed=True, lw=1.2,
        size=7.4, title_size=8.4)

    # mqtt_bridge ↔ scan_manager
    poly(ax, [(5.95, 4.35), (6.62, 4.35), (6.62, 5.45), (6.9, 5.45)], both=True)
    ax.text(4.6, 5.55, '/scan/run (A)\n/scan/home (A)\n/scan/resume (A)\n/scan/stop (S)\n/scan/set_config (S)\n'
            '↑ /scan/state\n   · result · log', ha='left', linespacing=1.22, **lab)
    # scan_manager ↔ contact_detector
    arrow(ax, (9.2, 5.75), (11.15, 5.75), None)
    ax.text(10.18, 5.9, '/contact/tare (S)', ha='center', **lab)
    arrow(ax, (11.15, 5.2), (9.2, 5.2), None)
    ax.text(10.18, 5.05, '/contact/event', ha='center', **lab)
    # scan_manager ↔ robot_manager
    arrow(ax, (9.35, 4.35), (11.15, 3.8), None)
    ax.text(10.25, 4.55, '/robot/execute_motion (A)\n/robot/stop (S)', ha='center', linespacing=1.2,
            bbox=dict(boxstyle='round,pad=0.06', facecolor='#EFF1FB', edgecolor='none'), **lab)
    arrow(ax, (11.15, 3.4), (9.35, 3.9), None)
    ax.text(10.35, 3.45, '/robot/status · sample', ha='center', **lab)
    # contact_detector ↔ robot_manager
    arrow(ax, (11.55, 5.0), (11.55, 4.0), None)
    ax.text(11.62, 4.72, '/contact/event', ha='left', **lab)
    arrow(ax, (12.85, 4.0), (12.85, 5.0), None)
    ax.text(12.78, 4.3, '/robot/sample', ha='right', **lab)
    # safety_monitor
    arrow(ax, (11.15, 3.0), (9.2, 3.0), None)
    ax.text(10.18, 3.12, '/robot/sample · status', ha='center', **lab)
    arrow(ax, (9.2, 2.55), (11.15, 2.7), None, color=RED, lw=2)
    ax.text(10.18, 2.43, '/robot/stop (S)', ha='center', fontsize=8.2, color=RED, va='center', fontweight='bold')
    arrow(ax, (8.15, 3.3), (8.15, 3.75), None)
    ax.text(8.22, 3.52, '/safety/status', ha='left', **lab)
    arrow(ax, (5.95, 2.75), (7.1, 2.75), None)
    ax.text(6.0, 3.12, '/safety/reset (S)\n(heartbeat 감시 미구현)', ha='left', fontsize=7.8, color='#374151', va='center',
            linespacing=1.2)
    # 표시 데이터 → mqtt_bridge
    poly(ax, [(11.3, 2.55), (11.3, 2.1), (5.95, 2.1)], color='#6B7280', lw=1.1)
    ax.text(8.6, 2.1, '표시: /robot/sample · status · /contact/event · /safety/status → mqtt_bridge', fontsize=7.8,
            color='#4B5563', ha='center', va='center',
            bbox=dict(boxstyle='round,pad=0.05', facecolor='#EFF1FB', edgecolor='none'))
    # 드라이버 · 로봇 컨트롤러
    arrow(ax, (11.65, 2.55), (11.65, 2.0), None, both=True)
    ax.text(11.72, 2.3, 'dsr_msgs2', ha='left', fontsize=7.8, color='#374151', va='center')
    arrow(ax, (12.75, 2.55), (12.75, 2.0), None)
    ax.text(12.82, 2.3, '탐침 파지', ha='left', fontsize=7.8, color='#374151', va='center')
    cluster(ax, 13.65, 0.3, 15.85, 3.1, '로봇 컨트롤러', '#2E8B7A', '#EEF7F5')
    box(ax, 13.8, 0.5, 15.7, 2.6, 'M0609 (DRCF)', ['+ RG2 · 무센서 탐침 팁', '하드웨어 안전:', '비상정지 · 충돌 감지'],
        edge='#2E8B7A', size=8.8)
    poly(ax, [(11.65, 1.2), (11.65, 0.7), (13.8, 0.7)], color='#2E8B7A', lw=2.2, both=True)
    ax.text(12.9, 0.55, 'DRCF TCP/IP', ha='center', fontsize=7.8, color='#2E8B7A', va='center')
    arrow(ax, (13.25, 1.6), (13.8, 1.6), None, both=True, lw=1.2, color='#2E8B7A')

    # ── phase 2 ───────────────────────────────────────────────────────
    if phase2:
        box(ax, 6.9, 0.5, 9.2, 1.85, 'weld_manager  [phase 2]',
            ['8 선 용접 모션 상태기계', '45° 자세 · 위빙 경유점', '입력 result.json · 스캔과 배타', '구현 PR 진행 중 (머지 전)'],
            edge=P2, fill=P2_FILL, color=P2_TEXT, dashed=True, size=8.4, title_size=9.6)
        poly(ax, [(5.3, 2.25), (5.3, 1.6), (6.9, 1.6)], color=P2, dashed=True, both=True)
        ax.text(4.6, 1.05, '/weld/run (A)\n/weld/home (A) · /weld/stop (S)\n↑ /weld/state · result · log',
                fontsize=7.8, color=P2_TEXT, ha='left', va='center', linespacing=1.25)
        arrow(ax, (9.2, 1.25), (11.25, 2.55), None, color=P2, dashed=True)
        ax.text(10.2, 1.45, '/robot/execute_path (A)\n/robot/execute_motion (A)\n/robot/stop (S)', fontsize=7.8,
                color=P2_TEXT, ha='center', va='center', linespacing=1.2,
                bbox=dict(boxstyle='round,pad=0.05', facecolor='#EFF1FB', edgecolor='none'))
        ax.text(2.65, 2.27, '+ cmd/weld/* · weld/#', fontsize=8, color=P2_TEXT, ha='center', va='center')

    out = HERE / ('01-system-architecture.png' if phase2 else '01-system-architecture-no-phase2.png')
    fig.savefig(out, dpi=150, facecolor='white', bbox_inches='tight', pad_inches=0.08)
    plt.close(fig)
    return out


def png_size(path):
    with open(path, 'rb') as fh:
        return struct.unpack('>II', fh.read(24)[16:24])


def node_graph():
    src = HERE / '06-node-graph.dot'
    text = src.read_text(encoding='utf-8')
    no_p2 = '\n'.join(line for line in text.splitlines() if '// P2' not in line)
    no_p2 = re.sub(r' \+ weld_manager \(phase 2[^)]*\)', '', no_p2)
    (HERE / '06-node-graph-no-phase2.dot').write_text(no_p2 + '\n', encoding='utf-8')
    outs = []
    for name in ('06-node-graph', '06-node-graph-no-phase2'):
        out = HERE / f'{name}.png'
        subprocess.run(['dot', '-Tpng', '-Gdpi=110', str(HERE / f'{name}.dot'), '-o', str(out)], check=True)
        outs.append(out)
    return outs


def main():
    outs = [architecture(True), architecture(False)]
    if (HERE / '06-node-graph.dot').exists():
        outs += node_graph()
    for out in outs:
        w, h = png_size(out)
        print(f'{out.name}: {w} x {h}' + ('' if w >= 1600 else '  ← 가로 1600 px 미만'))


if __name__ == '__main__':
    main()
