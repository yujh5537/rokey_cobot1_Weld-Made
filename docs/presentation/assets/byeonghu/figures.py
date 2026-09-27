"""병후 파트 슬라이드 그림. 원본 = 이 파일 + scan-state-machine.dot.

    python3 figures.py && python3 build_slides.py      # matplotlib · python-pptx · graphviz · Noto Sans CJK KR 필요

수치의 출처는 그림 안 각주와 build_slides.py 의 노트에 있다. 설계 출발값 · 실측 · 계산값을 그림 안에서 구분한다.
"""
import math
import pathlib
import subprocess

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
plt.rcParams['font.family'] = 'Noto Sans CJK KR'
NAVY, BLUE, ORANGE, RED, GRAY, TEXT = '#22357F', '#3378C8', '#D2691E', '#C0392B', '#7F7F7F', '#262626'
LIGHT = '#F2F5FA'


def save(fig, name):
    out = HERE / name
    fig.savefig(out, dpi=250, facecolor='white', bbox_inches='tight', pad_inches=0.05)
    plt.close(fig)
    return out


def canvas(w, h):
    fig = plt.figure(figsize=(w, h))
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_xlim(0, w)
    ax.set_ylim(0, h)
    ax.axis('off')
    return fig, ax


def arrow(ax, p0, p1, color=GRAY, lw=1.6, style='-|>', ls='-', ms=12, conn='arc3,rad=0'):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle=style, mutation_scale=ms, color=color, linewidth=lw,
                                 linestyle=ls, shrinkA=0, shrinkB=0, connectionstyle=conn))


# ── 01-③ MVP 범위: 5 점 → 형상 → 웹 ─────────────────────────────────────
def iso(x, y, z, ox, oy, s):
    return ox + (x - y) * math.cos(math.radians(30)) * s, oy + ((x + y) * math.sin(math.radians(30)) + z) * s


def cube(ax, ox, oy, s, face='#DCE6F5', edge=NAVY, lw=1.4):
    P = {k: iso(*v, ox, oy, s) for k, v in {
        'a': (0, 0, 0), 'b': (1, 0, 0), 'c': (1, 1, 0), 'd': (0, 1, 0),
        'A': (0, 0, 1), 'B': (1, 0, 1), 'C': (1, 1, 1), 'D': (0, 1, 1)}.items()}
    for poly, shade in ((('a', 'b', 'B', 'A'), 0.92), (('a', 'd', 'D', 'A'), 0.82), (('A', 'B', 'C', 'D'), 1.0)):
        ax.add_patch(Polygon([P[k] for k in poly], closed=True, facecolor=face, edgecolor=edge, linewidth=lw,
                             alpha=shade))
    return P


def fig_mvp_flow():
    fig, ax = canvas(7.4, 4.1)
    heads = [('① 만진다', '윗면 1 점 + 모서리 4 점'), ('② 계산한다', '편향 보정 → 직육면체 ·\n외곽 엣지 · 경로 후보 4'),
             ('③ 보여준다', '웹 3D 관제 · 로그 · 버튼')]
    xs = [0.15, 2.6, 5.05]
    for (h, sub), x in zip(heads, xs):
        ax.add_patch(FancyBboxPatch((x, 0.15), 2.2, 3.8, boxstyle='round,pad=0,rounding_size=0.1',
                                    facecolor=LIGHT, edgecolor='#C9D3E3', linewidth=1))
        ax.text(x + 1.1, 3.7, h, ha='center', va='center', fontsize=13, fontweight='bold', color=NAVY)
        ax.text(x + 1.1, 3.28, sub, ha='center', va='center', fontsize=9, color=TEXT, linespacing=1.3)
    for x0 in (2.38, 4.83):
        arrow(ax, (x0, 1.9), (x0 + 0.2, 1.9), color=NAVY, lw=2.2, ms=16)
    # ① 탐침 · 5 점
    P = cube(ax, 1.25, 0.55, 0.95)
    top = iso(0.5, 0.5, 1, 1.25, 0.55, 0.95)
    arrow(ax, (top[0], top[1] + 0.85), (top[0], top[1] + 0.06), color=RED, lw=2)
    ax.text(top[0] + 0.08, top[1] + 0.55, '하강', fontsize=8.5, color=RED)
    ax.add_patch(Circle(top, 0.05, color=RED, zorder=5))
    for (x, y), (dx, dy) in (((1, 0.5), (1, 0)), ((0, 0.5), (-1, 0)), ((0.5, 1), (0, 1)), ((0.5, 0), (0, -1))):
        p = iso(x, y, 1, 1.25, 0.55, 0.95)
        q = iso(x + dx * 0.32, y + dy * 0.32, 1, 1.25, 0.55, 0.95)
        s = iso(x - dx * 0.3, y - dy * 0.3, 1, 1.25, 0.55, 0.95)
        arrow(ax, s, q, color=BLUE, lw=1.6, ms=10)
        ax.add_patch(Circle(p, 0.045, color=BLUE, zorder=5))
    ax.text(1.25, 0.32, '빨강 = 윗면 · 파랑 = ±X · ±Y 밀기(EDGE)', ha='center', fontsize=7.8, color=GRAY)
    # ② 직육면체 · 경로 후보
    P = cube(ax, 3.7, 0.55, 0.95, face='#EEF2F9')
    for a, b in (('A', 'B'), ('B', 'C'), ('C', 'D'), ('D', 'A')):
        ax.plot([P[a][0], P[b][0]], [P[a][1], P[b][1]], color=ORANGE, linewidth=3.2, solid_capstyle='round')
    for a, b in (('b', 'c'), ('c', 'd'), ('c', 'C')):
        ax.plot([P[a][0], P[b][0]], [P[a][1], P[b][1]], color=NAVY, linewidth=1, linestyle=(0, (3, 2)))
    ax.text(3.7, 0.32, '주황 = 외곽 엣지 · 경로 후보 4', ha='center', fontsize=7.8, color=GRAY)
    # ③ 웹 화면 목업
    ax.add_patch(FancyBboxPatch((5.25, 0.55), 1.8, 2.35, boxstyle='round,pad=0,rounding_size=0.05',
                                facecolor='white', edgecolor=NAVY, linewidth=1.4))
    ax.add_patch(Rectangle((5.25, 2.68), 1.8, 0.22, facecolor=NAVY, edgecolor=NAVY))
    ax.text(5.33, 2.79, 'weld-made 관제', fontsize=7.5, color='white', va='center')
    cube(ax, 5.85, 1.45, 0.42, face='#EEF2F9', lw=1)
    for i, lab in enumerate(['시작', '중지', '안전복귀', '재시작']):
        ax.add_patch(FancyBboxPatch((5.33 + i * 0.43, 0.65), 0.39, 0.2, boxstyle='round,pad=0,rounding_size=0.03',
                                    facecolor=[BLUE, RED, GRAY, BLUE][i], edgecolor='none'))
        ax.text(5.525 + i * 0.43, 0.75, lab, fontsize=5.8, color='white', ha='center', va='center')
    for j in range(4):
        ax.plot([6.55, 6.98], [2.45 - j * 0.16] * 2, color='#B8C2D3', linewidth=2.2)
    ax.text(6.76, 2.58, '로그', fontsize=6.5, color=GRAY, ha='center')
    ax.text(6.15, 0.32, 'MQTT → FastAPI → WebSocket', ha='center', fontsize=7.8, color=GRAY)
    return save(fig, 'overview-mvp-flow.png')


# ── 03 절차 도식 ───────────────────────────────────────────────────────
def fig_procedure():
    fig, ax = canvas(12.3, 2.75)
    ax.set_ylim(-0.05, 2.75)
    steps = [('BRD', 'v3.2.0 · 9/18\n요구 · KPI'), ('계약', 'docs/contracts v0.1\n9/18 동결'),
             ('모듈 병렬', '노드별 패키지\n담당 4 명'), ('sim', '가상 접촉 입력원\nsource:=sim'),
             ('에뮬레이터', '두산 Virtual Mode\n모션 · DSR 호출'), ('실기', 'M0609 + RG2\n힘 · 접촉 · 치수'),
             ('시험 보고', 'docs/test-reports\nTR · daily')]
    w, gap, y0, h = 1.62, 0.13, 1.0, 1.15
    colors = ['#8FA7D6', '#6F8CCB', '#5577BD', '#3F66AF', '#2E579F', '#22357F', '#1B2A63']
    for i, ((head, sub), c) in enumerate(zip(steps, colors)):
        x = 0.1 + i * (w + gap)
        pts = [(x, y0), (x + w - 0.18, y0), (x + w, y0 + h / 2), (x + w - 0.18, y0 + h), (x, y0 + h)]
        if i:
            pts.append((x + 0.18, y0 + h / 2))
        ax.add_patch(Polygon(pts, closed=True, facecolor=c, edgecolor='white', linewidth=1.5))
        ax.text(x + w / 2 + 0.03, y0 + h * 0.68, head, ha='center', va='center', fontsize=12.5, fontweight='bold',
                color='white')
        ax.text(x + w / 2 + 0.03, y0 + h * 0.3, sub, ha='center', va='center', fontsize=7.8, color='white',
                linespacing=1.25)
    # 되먹임: 실기 실측 → 계약 개정
    x_real = 0.1 + 5 * (w + gap) + w / 2
    x_contract = 0.1 + 1 * (w + gap) + w / 2
    arrow(ax, (x_real, y0), (x_contract, y0), color=ORANGE, lw=1.8, conn='arc3,rad=-0.12', ms=14)
    ax.text((x_real + x_contract) / 2, 0.2, '실측 → 파라미터(yaml) · 계약 개정(PR + CHANGELOG, v0.1 → v0.1.20)',
            ha='center', va='center', fontsize=9, color=ORANGE, fontweight='bold')
    ax.text(0.1, 2.52, '단계마다 확인하고 다음으로 — sim · 에뮬레이터에서 먼저, 실기는 마지막',
            fontsize=10, color=NAVY, fontweight='bold')
    return save(fig, 'method-procedure.png')


# ── 04-④ 1/2 상태기계 (dot) ─────────────────────────────────────────────
def fig_state_machine():
    src = HERE / 'scan-state-machine.dot'
    out = HERE / 'scan-state-machine.png'
    subprocess.run(['dot', '-Tpng', '-Gdpi=220', str(src), '-o', str(out)], check=True)
    return out


# ── 04-④ 2/2 5 점 → 편향 보정 → 직육면체 ─────────────────────────────────
# 출처: 9/23 실기 scan 20260923-183211-3702 의 result.json (docs/phase2/fixtures, PR #186) · #180 학민 코멘트(9/23)
RAW = {'POS_X': 462.21853637695315, 'NEG_X': 376.6019287109375, 'POS_Y': -117.126708984375, 'NEG_Y': -200.32232666015626}
CORR = {'POS_X': 1.3418279573560522, 'NEG_X': 1.2723855163138625, 'POS_Y': 1.2793940417820965,
        'NEG_Y': 1.2722189548564152}
SHAPE = dict(x_pos=40.621708419597106, x_neg=-42.38068577274862, y_pos=38.26889697384292, y_neg=-42.375107705299835,
             z_top=82.75947241210939, support_z=2.0, width=83.00239419234573, length=80.64400467914276,
             height=80.75947241210939)
BASE_X = RAW['POS_X'] - CORR['POS_X'] - SHAPE['x_pos']        # 작업대 원점의 Base x (계산값)
BASE_Y = RAW['POS_Y'] - CORR['POS_Y'] - SHAPE['y_pos']


def fig_geometry():
    fig = plt.figure(figsize=(7.6, 4.3))
    ax = fig.add_axes((0.02, 0.06, 0.55, 0.86))
    ax.set_aspect('equal')
    x0, x1, y0, y1 = SHAPE['x_neg'], SHAPE['x_pos'], SHAPE['y_neg'], SHAPE['y_pos']
    ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, facecolor='#EEF2F9', edgecolor='none'))
    ax.plot([x0, x1, x1, x0, x0], [y0, y0, y1, y1, y0], color=ORANGE, linewidth=3, solid_capstyle='round')
    raw_f = {'POS_X': (RAW['POS_X'] - BASE_X, 0), 'NEG_X': (RAW['NEG_X'] - BASE_X, 0),
             'POS_Y': (0, RAW['POS_Y'] - BASE_Y), 'NEG_Y': (0, RAW['NEG_Y'] - BASE_Y)}
    corr_f = {'POS_X': (x1, 0), 'NEG_X': (x0, 0), 'POS_Y': (0, y1), 'NEG_Y': (0, y0)}
    for k in RAW:
        (rx, ry), (cx, cy) = raw_f[k], corr_f[k]
        ax.plot(rx, ry, 'o', markersize=7, markerfacecolor='white', markeredgecolor=BLUE, markeredgewidth=1.6)
        ax.plot(cx, cy, 'o', markersize=5.5, color=BLUE)
    ax.plot(0, 0, marker='x', color=GRAY, markersize=6)
    ax.plot(0, 0, 'o', markersize=8, markerfacecolor='none', markeredgecolor=RED, markeredgewidth=1.6)
    ax.text(3, 4, '윗면 1 점\n(하강 CONTACT)', fontsize=7.5, color=RED)
    ax.annotate('판정 좌표 (보정 전)', xy=raw_f['POS_X'], xytext=(24, -30), fontsize=7.5, color=BLUE,
                arrowprops=dict(arrowstyle='-', color=BLUE, lw=0.8))
    ax.annotate('보정 뒤 모서리', xy=corr_f['POS_Y'], xytext=(-38, 20), fontsize=7.5, color=BLUE,
                arrowprops=dict(arrowstyle='-', color=BLUE, lw=0.8))
    ax.text(0, -10, f'폭 {SHAPE["width"]:.2f}\n길이 {SHAPE["length"]:.2f}\n높이 {SHAPE["height"]:.2f} mm',
            ha='center', va='top', fontsize=9, color=NAVY, fontweight='bold', linespacing=1.3)
    ax.set_xlim(-58, 58)
    ax.set_ylim(-58, 55)
    ax.set_xticks([-40, 0, 40])
    ax.set_yticks([-40, 0, 40])
    ax.tick_params(labelsize=7, colors=GRAY)
    for sp in ax.spines.values():
        sp.set_color('#C9D3E3')
    ax.set_title('윗면 (작업대 좌표, mm) — 9/23 실기 1 회', fontsize=9.5, color=TEXT)
    ax.text(-56, -56, '주황 = 외곽 엣지 · 경로 후보 4   ○ 보정 전 → ● 보정 뒤 (1.27~1.34 mm 안쪽)', fontsize=7.2,
            color=ORANGE)

    # 오른쪽: 모서리 단면 — 팁 구가 모서리를 넘어 δ 내려앉은 순간
    bx = fig.add_axes((0.6, 0.12, 0.39, 0.75))
    bx.set_aspect('equal')
    bx.axis('off')
    r, dl = 2.0, 0.5
    d = math.sqrt(2 * r * dl - dl * dl)
    bx.add_patch(Rectangle((-5, -4), 5, 4, facecolor='#DCE6F5', edgecolor=NAVY, linewidth=1.4))
    bx.add_patch(Circle((d, r - dl), r, facecolor='none', edgecolor=RED, linewidth=1.6))
    bx.add_patch(Circle((-3.2, r), r, facecolor='none', edgecolor=RED, linewidth=1, linestyle=(0, (3, 2))))
    bx.plot([d], [r - dl], 'o', color=RED, markersize=3)
    arrow(bx, (-3.2, r + 2.4), (-0.6, r + 2.4), color=BLUE, lw=1.4, ms=9)
    bx.text(-1.9, r + 2.75, '밀기 (+X)', fontsize=7.5, color=BLUE, ha='center')
    bx.plot([0, d], [-0.35, -0.35], color=NAVY, linewidth=1)
    bx.text(d / 2, -0.95, 'd', fontsize=10, color=NAVY, ha='center', fontstyle='italic')
    bx.plot([d + r + 0.3, d + r + 0.3], [r, r - dl], color=NAVY, linewidth=1)
    bx.text(d + r + 0.5, r - dl / 2, 'δ', fontsize=10, color=NAVY, va='center')
    bx.plot([-3.2, -3.2 + r], [r, r], color=RED, linewidth=0.8)
    bx.text(-2.2, r + 0.2, 'r', fontsize=9, color=RED, ha='center', fontstyle='italic')
    bx.plot([-5, 0], [0, 0], color=NAVY, linewidth=1.4)
    bx.text(-2.5, -2.2, '부재', fontsize=9, color=NAVY, ha='center')
    bx.text(-1.4, -4.9, 'd = √(2rδ − δ²) (+ v·t)', fontsize=9.5, color=NAVY, ha='center')
    bx.text(-1.4, -5.9, 'r 2 mm · δ 0.46~0.52 mm (실측)\n→ 보정 1.27~1.34 mm (계산값)', fontsize=7.8,
            color=TEXT, ha='center', va='top', linespacing=1.3)
    bx.set_xlim(-5.5, 5.2)
    bx.set_ylim(-7.3, 5.2)
    bx.set_title('모서리 단면 — 판정 순간의 팁', fontsize=9.5, color=TEXT)
    return save(fig, 'scan-geometry-bias.png')


# ── 04-⑧ #136 타임라인 ─────────────────────────────────────────────────
def fig_problem_timeline():
    fig, ax = canvas(12.3, 2.15)
    # 위: 9/21 실기
    ax.text(0.1, 1.9, '9/21 실기 (고치기 전)', fontsize=10, fontweight='bold', color=RED)
    t0, t1, xa, xb = 10.0, 13.0, 2.2, 12.0

    def tx(h, m, s=0):
        return xa + ((h + m / 60 + s / 3600) - t0) / (t1 - t0) * (xb - xa)
    ax.plot([xa, xb], [1.45, 1.45], color=GRAY, linewidth=1.2)
    for h in (10, 11, 12, 13):
        ax.plot([tx(h, 0)] * 2, [1.4, 1.5], color=GRAY, linewidth=1)
        ax.text(tx(h, 0), 1.3, f'{h}:00', fontsize=7.5, color=GRAY, ha='center')
    ax.add_patch(Rectangle((tx(11, 51, 45), 1.37), xb - tx(11, 51, 45), 0.16, facecolor='#F6D5D1', edgecolor='none'))
    for (h, m, s), lab in (((10, 34, 33), '감시자 종료 ① 10:34:33'), ((11, 51, 45), '감시자 종료 ② 11:51:45')):
        ax.plot(tx(h, m, s), 1.45, 'v', color=RED, markersize=9)
        ax.text(tx(h, m, s), 1.62, lab, fontsize=8, color=RED, ha='center')
    ax.text((tx(11, 51, 45) + xb) / 2, 1.08, '하강 5 · 밀기 2 가 2차 감시 없이 — START 는 계속 받음 · 1 시간 넘게 모름',
            fontsize=8, color=RED, ha='center', va='center')
    ax.text(0.1, 1.45, '#103 · #120', fontsize=7.5, color=GRAY, va='center')
    # 아래: sim 종단 (고친 뒤)
    ax.text(0.1, 0.78, 'sim 종단 (PR #136 뒤)', fontsize=10, fontweight='bold', color=BLUE)
    sa, sb, ya = 292.0, 299.0, 0.35

    def sx(t):
        return xa + (t - sa) / (sb - sa) * (xb - xa)
    ax.plot([xa, xb], [ya, ya], color=GRAY, linewidth=1.2)
    for t in range(292, 300):
        ax.plot([sx(t)] * 2, [ya - 0.05, ya + 0.05], color=GRAY, linewidth=1)
        ax.text(sx(t), ya - 0.22, f'{t} s', fontsize=7, color=GRAY, ha='center')
    last = 298.25 - 5.5
    ax.plot(sx(last), ya, 'o', color=GRAY, markersize=6)
    ax.text(sx(last), ya + 0.14, '마지막 stamp\n(≈292.75 s, 계산값)', fontsize=7.5, color=GRAY, ha='center',
            va='bottom')
    ax.add_patch(Rectangle((sx(last), ya - 0.03), sx(last + 5.0) - sx(last), 0.06, facecolor='#CFE0F5',
                           edgecolor='none'))
    ax.text((sx(last) + sx(last + 5.0)) / 2, ya + 0.1, '한도 safety_status_timeout_s 5.0 s (설계 출발값)',
            fontsize=7.5, color=BLUE, ha='center', va='bottom')
    ax.plot(sx(297.87), ya, 'D', color=ORANGE, markersize=6)
    ax.text(sx(297.87) - 0.1, ya + 0.14, '끊김 WARN\n297.87 s', fontsize=7.5, color=ORANGE, ha='right',
            va='bottom')
    ax.plot(sx(298.25), ya, 's', color=BLUE, markersize=7)
    ax.text(sx(298.25) + 0.08, ya + 0.14, 'START 거절 103\n298.25 s', fontsize=7.5, color=BLUE, ha='left',
            va='bottom')
    return save(fig, 'problem-status-age.png')


# ── 04-⑨ 용접 모션: 8 선 · 45° 자세 · 스탠드오프 · 위빙 ──────────────────
def fig_weld():
    fig = plt.figure(figsize=(7.6, 4.3))
    # (a) 8 선 — 사투상(뒤 모서리가 앞 모서리와 겹치지 않게)
    ax = fig.add_axes((0.0, 0.3, 0.36, 0.62))
    ax.set_aspect('equal')
    ax.axis('off')

    def ob(x, y, z):
        return x + 0.55 * y * math.cos(math.radians(35)), z + 0.55 * y * math.sin(math.radians(35))
    V = {'v0': (0, 0, 1), 'v1': (1, 0, 1), 'v2': (1, 1, 1), 'v3': (0, 1, 1),
         'v4': (0, 0, 0), 'v5': (1, 0, 0), 'v6': (1, 1, 0), 'v7': (0, 1, 0)}
    Q = {k: ob(*v) for k, v in V.items()}
    for face, alpha in ((('v4', 'v5', 'v1', 'v0'), 0.95), (('v5', 'v6', 'v2', 'v1'), 0.8), (('v0', 'v1', 'v2', 'v3'), 1.0)):
        ax.add_patch(Polygon([Q[k] for k in face], closed=True, facecolor='#EEF2F9', edgecolor=NAVY, linewidth=0.8,
                             alpha=alpha))
    for a, b in (('v4', 'v7'), ('v7', 'v6')):
        ax.plot([Q[a][0], Q[b][0]], [Q[a][1], Q[b][1]], color=NAVY, linewidth=0.6, linestyle=(0, (2, 2)))
    lines = [('v0', 'v1', 'L0'), ('v1', 'v2', 'L1'), ('v2', 'v3', 'L2'), ('v3', 'v0', 'L3'),
             ('v0', 'v4', 'L4'), ('v1', 'v5', 'L5'), ('v2', 'v6', 'L6'), ('v3', 'v7', 'L7')]
    for a, b, lab in lines:
        failed = lab in ('L1', 'L5')
        ax.plot([Q[a][0], Q[b][0]], [Q[a][1], Q[b][1]], color=GRAY if failed else ORANGE, linewidth=2.6,
                linestyle=(0, (2, 1.5)) if failed else '-')
        mx, my = (Q[a][0] + Q[b][0]) / 2, (Q[a][1] + Q[b][1]) / 2
        ax.text(mx, my, lab, fontsize=8, color=GRAY if failed else ORANGE, fontweight='bold', ha='center',
                va='center', bbox=dict(boxstyle='round,pad=0.08', facecolor='white', edgecolor='none'))
    ax.text(Q['v0'][0] - 0.05, Q['v0'][1] + 0.05, '(x−, y−)', fontsize=6.5, color=GRAY, ha='right')
    ax.set_xlim(-0.25, 1.65)
    ax.set_ylim(-0.12, 1.5)
    ax.set_title('8 선: 윗면 L0 → L3 → 세로 L4 → L7', fontsize=9, color=TEXT)
    fig.text(0.18, 0.2, '점선 L1 · L5 = 45° 도달 불가\n(9/23 실측 M1, 16 자세 중 12 도달)', fontsize=7.4, color=GRAY,
             ha='center', va='top', linespacing=1.3)
    # (b) 단면: 45° 이등분 자세 + 스탠드오프
    bx = fig.add_axes((0.38, 0.1, 0.28, 0.82))
    bx.set_aspect('equal')
    bx.axis('off')
    bx.add_patch(Rectangle((-6, -6), 6, 6, facecolor='#DCE6F5', edgecolor=NAVY, linewidth=1.3))
    th = math.radians(45)
    dvec = (-math.sin(th), -math.cos(th))          # 팁이 보는 방향 (아래 · 안쪽), 바깥은 +x
    s_off, r = 3.0, 2.0
    tcp = (-dvec[0] * s_off, -dvec[1] * s_off)       # 이음선(모서리 0,0)에서 −d 로 s′ (윗면선은 standoff 와 같다)
    cen = (tcp[0] - dvec[0] * r, tcp[1] - dvec[1] * r)
    bx.add_patch(Circle(cen, r, facecolor='none', edgecolor=RED, linewidth=1.5))
    ax_end = (cen[0] - dvec[0] * 9, cen[1] - dvec[1] * 9)
    bx.plot([cen[0], ax_end[0]], [cen[1], ax_end[1]], color=RED, linewidth=5, solid_capstyle='butt', alpha=0.35)
    bx.plot([0, ax_end[0] + 1.5], [0, ax_end[1] + 1.5], color=GRAY, linewidth=0.8, linestyle=(0, (3, 2)))
    bx.plot([0, 0], [0, 7.5], color=GRAY, linewidth=0.6, linestyle=(0, (1, 2)))
    bx.text(0.6, 7.2, '45°', fontsize=8.5, color=NAVY)
    bx.plot([0, tcp[0]], [0, tcp[1]], color=NAVY, linewidth=1.2)
    bx.text(tcp[0] / 2 + 0.4, tcp[1] / 2 - 0.6, '3 mm', fontsize=8, color=NAVY)
    bx.plot(0, 0, 'o', color=ORANGE, markersize=6)
    bx.text(-0.4, -0.9, '이음선\n(모서리)', fontsize=7.5, color=ORANGE, ha='right', va='top')
    bx.text(ax_end[0] + 0.4, ax_end[1] + 0.3, '탐침 축', fontsize=8, color=RED)
    bx.set_xlim(-6.5, 11)
    bx.set_ylim(-6.5, 12.5)
    bx.set_title('단면: 두 면 이등분 · 45° · 띄움', fontsize=9, color=TEXT)
    # (c) 위빙 지그재그 (위에서 본 선)
    cx = fig.add_axes((0.69, 0.18, 0.31, 0.72))
    cx.axis('off')
    L, pitch, amp = 24.0, 4.0, 2.0
    n = int(math.ceil(L / pitch))
    xs = [min(k * pitch, L) for k in range(n + 1)]
    ys = [0 if k in (0, n) else amp * (-1) ** k for k in range(n + 1)]
    cx.plot([0, L], [0, 0], color=ORANGE, linewidth=2.2)
    cx.plot(xs, ys, color=RED, linewidth=1.3, marker='o', markersize=3.5)
    cx.annotate('', xy=(pitch * 2, -amp - 1.2), xytext=(pitch, -amp - 1.2),
                arrowprops=dict(arrowstyle='<->', color=NAVY, lw=0.9))
    cx.text(pitch * 1.5, -amp - 2.4, '반주기 4 mm', fontsize=7.5, color=NAVY, ha='center')
    cx.annotate('', xy=(pitch * 3, amp + 0.1), xytext=(pitch * 3, 0),
                arrowprops=dict(arrowstyle='<->', color=NAVY, lw=0.9))
    cx.text(pitch * 3 + 0.5, amp + 0.6, '진폭 2 mm', fontsize=7.5, color=NAVY)
    cx.text(L / 2, 6.2, '위빙 = 지그재그 경유점\n(ExecutePath, 점마다 정지)', fontsize=8, color=TEXT, ha='center',
            va='center', linespacing=1.3)
    cx.text(L / 2, -7.0, '경유점 ≤ 100 / 선', fontsize=7.5, color=GRAY, ha='center')
    cx.set_xlim(-1, L + 1)
    cx.set_ylim(-8, 8)
    cx.set_title('위에서 본 한 선', fontsize=9, color=TEXT)
    fig.text(0.99, 0.01, '3 mm · 45° · 진폭 · 반주기 = 설계 출발값(weld-motion.md 6절)', fontsize=7, color=GRAY,
             ha='right')
    return save(fig, 'weld-pose-weave.png')


def main():
    outs = [fig_mvp_flow(), fig_procedure(), fig_state_machine(), fig_geometry(), fig_problem_timeline(), fig_weld()]
    for out in outs:
        import struct
        with open(out, 'rb') as fh:
            w, h = struct.unpack('>II', fh.read(24)[16:24])
        print(f'{out.name}: {w} x {h}' + ('' if w >= 1600 else '  ← 1600 px 미만'))


if __name__ == '__main__':
    main()
