"""병후 파트 슬라이드 그림 (원본 = 이 파일).

    python3 figures.py && python3 build_slides.py      # matplotlib · python-pptx · Noto Sans CJK KR 필요

원칙(병후 9/28 피드백): 화면에는 시각자료와 키워드만. 그림 안에도 작은 글씨를 두지 않는다 — 그림은 슬라이드에 넣을 크기(인치)로
그리고, 그 크기에서 글자가 12 pt 아래로 내려가지 않게 한다. 세부 설명 · 출처는 슬라이드 노트와 각주에 둔다.
수치는 출처가 있는 것만 쓰고 실측 · 설계 출발값 · 계산값 · 가정을 그림 안에서 구분한다.
"""
import math
import pathlib
import struct

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, ConnectionPatch, FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
plt.rcParams['font.family'] = 'Noto Sans CJK KR'
NAVY, BLUE, ORANGE, RED, GRAY, TEXT = '#22357F', '#3378C8', '#D2691E', '#C0392B', '#7F7F7F', '#262626'
GREEN, AMBER = '#2E8B57', '#B8860B'
LIGHT, PALE_BLUE, PALE_RED, PALE_OR, PALE_GREEN = '#F2F5FA', '#DCE6F5', '#FDE2E0', '#FFF1E0', '#E3F3E8'
MIN_PT = 12


def save(fig, name, dpi=250):
    out = HERE / name
    fig.savefig(out, dpi=dpi, facecolor='white')
    plt.close(fig)
    return out


def canvas(w, h):
    fig = plt.figure(figsize=(w, h))
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_xlim(0, w)
    ax.set_ylim(0, h)
    ax.axis('off')
    return fig, ax


def rbox(ax, x, y, w, h, face=LIGHT, edge='#C9D3E3', lw=1.2, r=0.1, ls='-', z=1):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f'round,pad=0,rounding_size={r}', facecolor=face,
                                edgecolor=edge, linewidth=lw, linestyle=ls, zorder=z))


def arrow(ax, p0, p1, color=GRAY, lw=2.0, style='-|>', ls='-', ms=16, conn='arc3,rad=0', z=3):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle=style, mutation_scale=ms, color=color, linewidth=lw,
                                 linestyle=ls, shrinkA=0, shrinkB=0, connectionstyle=conn, zorder=z))


def t(ax, x, y, s, size=MIN_PT, color=TEXT, bold=False, ha='center', va='center', z=5, **kw):
    assert size >= MIN_PT - 0.01, f'{s!r}: {size} pt < {MIN_PT}'
    ax.text(x, y, s, fontsize=size, color=color, fontweight='bold' if bold else 'normal', ha=ha, va=va, zorder=z,
            linespacing=1.25, **kw)


def mark(ax, x, y, kind, r=0.2):
    """○ 유리 · △ 조건부 · × 불리 — 색 원 안의 기호."""
    color = {'good': GREEN, 'mid': AMBER, 'bad': RED}[kind]
    sym = {'good': '○', 'mid': '△', 'bad': '×'}[kind]
    ax.add_patch(Circle((x, y), r, facecolor=color, edgecolor='none', zorder=4))
    t(ax, x, y - 0.01, sym, size=15, color='white', bold=True)


# ── 01-② 대안 비교 (기호 매트릭스) ─────────────────────────────────────
# 근거: BRD 3.2 표(티칭 · 추가 HW · 약점 · 비용), 1.5(기술적 가치). ○ △ ✕ 는 그 문장을 기호로 옮긴 것
def fig_compare():
    W, H = 8.3, 4.45
    fig, ax = canvas(W, H)
    cols = ['티칭', '추가 장비', '표면 · 환경', '비용']
    rows = [
        ('재티칭 (현행)', [('bad', '매번'), ('good', '없음'), ('good', '무관'), ('mid', '인건비 반복')]),
        ('와이어 터치센싱', [('mid', '기준 경로'), ('mid', '감지 전원'), ('bad', '깨끗한 모서리'), ('good', '저가 옵션')]),
        ('레이저 · 3D 비전', [('mid', '제품 따라'), ('bad', '센서 · 보정'), ('bad', '반사 · 아크광'), ('bad', '1~5 만 $')]),
        ('접촉 탐색 (우리)', [('good', '불필요'), ('good', '탐침 팁만'), ('good', '무관'), ('good', '목표 1천만원')]),
    ]
    x0, cw, top, rh = 2.25, 1.47, 3.75, 0.8
    for j, c in enumerate(cols):
        t(ax, x0 + cw * (j + 0.5), top + 0.42, c, size=14, bold=True, color=NAVY)
    for i, (name, cells) in enumerate(rows):
        y = top - rh * (i + 0.5)
        ours = i == 3
        rbox(ax, 0.05, y - rh / 2 + 0.05, W - 0.1, rh - 0.1, face=PALE_BLUE if ours else (LIGHT if i % 2 else 'white'),
             edge=BLUE if ours else '#E1E6EF', lw=2 if ours else 1)
        t(ax, 0.2, y, name, size=14, bold=True, color=BLUE if ours else TEXT, ha='left')
        for j, (kind, kw) in enumerate(cells):
            cx = x0 + cw * (j + 0.5)
            mark(ax, cx - 0.47, y, kind, r=0.19)
            t(ax, cx - 0.2, y, kw, size=12, ha='left', color=TEXT)
    t(ax, W / 2, 0.22, '○ 유리   △ 조건부   × 불리   —  BRD 3.2 · 1.5 를 기호로 옮김', size=12, color=GRAY)
    return save(fig, 'compare-alternatives.png', dpi=250)


# ── 01-③ MVP 범위: 만진다 → 계산한다 → 보여준다 ────────────────────────
def iso(x, y, z, ox, oy, s):
    return ox + (x - y) * math.cos(math.radians(30)) * s, oy + ((x + y) * math.sin(math.radians(30)) + z) * s


def cube(ax, ox, oy, s, face=PALE_BLUE, edge=NAVY, lw=1.6):
    P = {k: iso(*v, ox, oy, s) for k, v in {
        'a': (0, 0, 0), 'b': (1, 0, 0), 'c': (1, 1, 0), 'd': (0, 1, 0),
        'A': (0, 0, 1), 'B': (1, 0, 1), 'C': (1, 1, 1), 'D': (0, 1, 1)}.items()}
    for poly, shade in ((('a', 'b', 'B', 'A'), 0.92), (('a', 'd', 'D', 'A'), 0.82), (('A', 'B', 'C', 'D'), 1.0)):
        ax.add_patch(Polygon([P[k] for k in poly], closed=True, facecolor=face, edgecolor=edge, linewidth=lw,
                             alpha=shade, zorder=2))
    return P


def fig_mvp_flow():
    W, H = 7.6, 4.45
    fig, ax = canvas(W, H)
    heads = [('① 만진다', '윗면 1 + 모서리 4'), ('② 계산한다', '보정 → 직육면체'), ('③ 보여준다', '웹: 3D · 버튼 · 로그')]
    xs = [0.05, 2.6, 5.15]
    for (h, sub), x in zip(heads, xs):
        rbox(ax, x, 0.05, 2.4, 4.35)
        t(ax, x + 1.2, 3.98, h, size=18, bold=True, color=NAVY)
        t(ax, x + 1.2, 3.5, sub, size=13)
    for x0 in (2.46, 5.01):
        arrow(ax, (x0, 1.9), (x0 + 0.13, 1.9), color=NAVY, lw=3, ms=20)
    # ① 탐침 · 5 점
    ox, oy, s = 1.25, 0.45, 1.0
    top = iso(0.5, 0.5, 1, ox, oy, s)
    cube(ax, ox, oy, s)
    arrow(ax, (top[0], top[1] + 0.95), (top[0], top[1] + 0.08), color=RED, lw=3, ms=18)
    ax.add_patch(Circle(top, 0.07, color=RED, zorder=6))
    for (x, y), (dx, dy) in (((1, 0.5), (1, 0)), ((0, 0.5), (-1, 0)), ((0.5, 1), (0, 1)), ((0.5, 0), (0, -1))):
        p = iso(x, y, 1, ox, oy, s)
        q = iso(x + dx * 0.34, y + dy * 0.34, 1, ox, oy, s)
        s0 = iso(x - dx * 0.3, y - dy * 0.3, 1, ox, oy, s)
        arrow(ax, s0, q, color=BLUE, lw=2.4, ms=14)
        ax.add_patch(Circle(p, 0.065, color=BLUE, zorder=6))
    # ② 직육면체 · 경로 후보
    P = cube(ax, 3.8, 0.45, 1.0, face='#EEF2F9')
    for a, b in (('A', 'B'), ('B', 'C'), ('C', 'D'), ('D', 'A')):
        ax.plot([P[a][0], P[b][0]], [P[a][1], P[b][1]], color=ORANGE, linewidth=4.5, solid_capstyle='round', zorder=4)
    for a, b in (('b', 'c'), ('c', 'd'), ('c', 'C')):
        ax.plot([P[a][0], P[b][0]], [P[a][1], P[b][1]], color=NAVY, linewidth=1.2, linestyle=(0, (3, 2)), zorder=3)
    t(ax, 3.8, 3.05, '주황 = 경로 후보 4', size=12, color=ORANGE, bold=True)
    # ③ 웹 화면 목업(글자 없는 그림)
    rbox(ax, 5.35, 0.45, 2.0, 2.6, face='white', edge=NAVY, lw=1.8, r=0.06)
    ax.add_patch(Rectangle((5.35, 2.8), 2.0, 0.25, facecolor=NAVY, edgecolor=NAVY, zorder=2))
    cube(ax, 6.0, 1.3, 0.5, face='#EEF2F9', lw=1.3)
    for i, col in enumerate([BLUE, RED, GRAY, BLUE]):
        rbox(ax, 5.45 + i * 0.47, 0.58, 0.4, 0.28, face=col, edge=col, r=0.04, z=3)
    for j in range(4):
        ax.plot([6.85, 7.25], [2.55 - j * 0.2] * 2, color='#B8C2D3', linewidth=3, zorder=3)
    return save(fig, 'overview-mvp-flow.png', dpi=250)


# ── 01-⑤ 기대효과: 직접교시 vs 접촉 탐색 ──────────────────────────────
# 근거: BRD 1.6(A3 · A4 · 시나리오) · 9 장(추가 센서 0 원) · 1.3(숙련도) · 2 장(사람 개입) · 9/23 실측(#180 · TR)
def fig_value():
    W, H = 12.3, 4.5
    fig, ax = canvas(W, H)
    rbox(ax, 2.35, 3.88, 4.35, 0.58, face='#EDEDED', edge='#EDEDED')
    rbox(ax, 7.75, 3.88, 4.5, 0.58, face=BLUE, edge=BLUE)
    t(ax, 4.52, 4.17, '지금: 직접교시', size=17, bold=True, color=TEXT)
    t(ax, 10.0, 4.17, '우리: 접촉 탐색', size=17, bold=True, color='white')
    rows = [
        ('교체 1 회\n사람 시간', '약 1 h', '가정 A3 (0.5~2 h)', '0.1 h', '가정 A4 + 로봇 탐색 7.3 분(실측)'),
        ('연간\n교시 시간', '500 h', '교체 하루 2 회 × 250 일', '50 h', '같은 가정 · 계산값'),
        ('정확도', '숙련도에\n좌우', 'BRD 1.3', '±3 mm 안', '+1.50 / −0.36 / +0.26 mm\n9/23 실기 1 회'),
        ('자동화', '점마다\n손으로', '끌어서 기록', '버튼 1 번', '놓고 · 시작 · 확인'),
    ]
    rh = 0.82
    for i, (label, a_big, a_sub, b_big, b_sub) in enumerate(rows):
        y = 3.4 - rh * i
        if i % 2 == 0:
            ax.add_patch(Rectangle((0.05, y - rh / 2), W - 0.1, rh, facecolor=LIGHT, edgecolor='none', zorder=0))
        t(ax, 1.15, y, label, size=15, bold=True, color=NAVY)
        t(ax, 3.35, y, a_big, size=19, bold=True, color=GRAY)
        t(ax, 5.55, y, a_sub, size=12, color=GRAY)
        arrow(ax, (6.75, y), (7.6, y), color=BLUE, lw=3, ms=20)
        t(ax, 8.75, y, b_big, size=22, bold=True, color=BLUE)
        t(ax, 10.95, y, b_sub, size=12, color=TEXT)
    t(ax, W / 2, 0.2, '경제성(BRD 1.6 기본 시나리오, 가정): 연 절감 1,775 만원 · 회수 약 7 개월   |   MVP 는 원리 실증 — 이 절감을 바로 만들지 않는다',
      size=12, color=RED)
    return save(fig, 'value-compare.png', dpi=200)


# ── 03 절차 도식 ───────────────────────────────────────────────────────
def fig_procedure():
    W, H = 12.3, 2.55
    fig, ax = canvas(W, H)
    steps = [('BRD', '요구 · KPI'), ('계약', '9/18 동결'), ('병렬 개발', '담당 4 명'), ('sim', '가상 접촉'),
             ('에뮬레이터', 'Virtual'), ('실기', 'M0609'), ('시험 보고', 'TR · daily')]
    w, gap, y0, h = 1.62, 0.13, 0.95, 1.5
    colors = ['#8FA7D6', '#6F8CCB', '#5577BD', '#3F66AF', '#2E579F', '#22357F', '#1B2A63']
    for i, ((head, sub), c) in enumerate(zip(steps, colors)):
        x = 0.1 + i * (w + gap)
        pts = [(x, y0), (x + w - 0.2, y0), (x + w, y0 + h / 2), (x + w - 0.2, y0 + h), (x, y0 + h)]
        if i:
            pts.append((x + 0.2, y0 + h / 2))
        ax.add_patch(Polygon(pts, closed=True, facecolor=c, edgecolor='white', linewidth=2, zorder=2))
        t(ax, x + w / 2 + 0.05, y0 + h * 0.64, head, size=16, bold=True, color='white')
        t(ax, x + w / 2 + 0.05, y0 + h * 0.3, sub, size=12, color='white')
    x_real = 0.1 + 5 * (w + gap) + w / 2
    x_contract = 0.1 + 1 * (w + gap) + w / 2
    arrow(ax, (x_real, y0), (x_contract, y0), color=ORANGE, lw=2.4, conn='arc3,rad=-0.1', ms=18)
    t(ax, (x_real + x_contract) / 2, 0.14, '실측 → yaml · 계약 개정 (9/18 → 9/23, 19 회)', size=14, color=ORANGE, bold=True)
    return save(fig, 'method-procedure.png', dpi=200)


# ── 04-① 슬라이드용 아키텍처(단순판) ──────────────────────────────────
def node(ax, x, y, w, h, name, desc, edge=NAVY, face='white', color=TEXT, ls='-', name_size=15):
    rbox(ax, x, y, w, h, face=face, edge=edge, lw=2, r=0.08, ls=ls, z=2)
    t(ax, x + w / 2, y + h * 0.64, name, size=name_size, bold=True, color=color)
    t(ax, x + w / 2, y + h * 0.28, desc, size=12, color=color)


def fig_arch(phase2):
    W, H = 12.3, 4.5
    fig, ax = canvas(W, H)
    # 웹 PC
    rbox(ax, 0.05, 0.05, 2.9, 4.35, face='#FAEFF7', edge='#A05195', lw=1.6)
    t(ax, 1.5, 4.12, '웹 PC · 브라우저', size=14, bold=True, color='#A05195')
    node(ax, 0.25, 2.75, 2.5, 1.0, '관제 화면', 'React · 3D · 버튼')
    node(ax, 0.25, 1.45, 2.5, 1.0, '웹 서버', 'FastAPI · DB · Spring')
    node(ax, 0.25, 0.2, 2.5, 1.0, 'MQTT 브로커', 'Mosquitto')
    arrow(ax, (1.5, 2.75), (1.5, 2.45), color=GRAY, style='<|-|>', ms=14)
    arrow(ax, (1.5, 1.45), (1.5, 1.2), color=GRAY, style='<|-|>', ms=14)
    # 메인 PC
    rbox(ax, 3.3, 0.05, 6.65, 4.35, face='#EFF1FB', edge='#5566B5', lw=1.6)
    t(ax, 6.62, 4.12, '메인 PC · ROS 2', size=14, bold=True, color='#5566B5')
    rbox(ax, 3.45, 0.2, 1.3, 3.55, face='white', edge=NAVY, lw=2, r=0.08, z=2)
    t(ax, 4.1, 2.25, 'mqtt_\nbridge', size=15, bold=True)
    t(ax, 4.1, 1.35, 'ROS ↔\nMQTT', size=12)
    node(ax, 5.1, 2.75, 2.05, 1.0, 'scan_manager', '순서 · 중지 · 재시작', face=PALE_BLUE)
    node(ax, 5.1, 1.45, 2.05, 1.0, 'safety_monitor', '감시 · 정지', name_size=14)
    node(ax, 7.6, 2.75, 2.2, 1.0, 'contact_detector', '접촉 · 모서리 판정', name_size=14)
    node(ax, 7.6, 1.45, 2.2, 1.0, 'robot_manager', '모션 · 로봇 호출')
    if phase2:
        node(ax, 7.6, 0.2, 2.2, 1.0, 'weld_manager', 'phase 2 · 진행 중', edge=ORANGE, face=PALE_OR, color='#8B3A00',
             ls='--', name_size=14)
    arrow(ax, (2.75, 0.7), (3.45, 0.7), color=NAVY, style='<|-|>', lw=3, ms=18)
    t(ax, 3.1, 1.0, 'MQTT', size=12, color=NAVY, bold=True)
    arrow(ax, (4.75, 3.25), (5.1, 3.25), color=GRAY, style='<|-|>', ms=14)
    arrow(ax, (4.75, 1.95), (5.1, 1.95), color=GRAY, style='<|-|>', ms=14)
    arrow(ax, (7.15, 3.25), (7.6, 3.25), color=GRAY, style='<|-|>', ms=14)
    arrow(ax, (7.15, 2.9), (7.6, 2.3), color=GRAY, style='<|-|>', ms=14)
    arrow(ax, (8.7, 2.45), (8.7, 2.75), color=GRAY, style='<|-|>', ms=14)
    arrow(ax, (7.15, 1.75), (7.6, 1.75), color=RED, lw=3.4, ms=20)
    t(ax, 7.37, 1.45, '정지', size=12, color=RED, bold=True)
    if phase2:
        arrow(ax, (8.7, 1.2), (8.7, 1.45), color=ORANGE, style='<|-|>', ls='--', ms=14)
        arrow(ax, (4.75, 0.7), (7.6, 0.7), color=ORANGE, style='<|-|>', ls='--', ms=14)
    # 로봇
    rbox(ax, 10.3, 0.05, 1.95, 4.35, face='#EEF7F5', edge='#2E8B7A', lw=1.6)
    t(ax, 11.27, 4.12, '로봇', size=14, bold=True, color='#2E8B7A')
    node(ax, 10.45, 1.2, 1.65, 2.3, 'M0609', 'RG2 + 탐침', edge='#2E8B7A')
    arrow(ax, (9.8, 1.95), (10.45, 1.95), color='#2E8B7A', style='<|-|>', lw=3, ms=18)
    t(ax, 10.12, 2.22, 'DRCF', size=12, color='#2E8B7A', bold=True)
    return save(fig, 'arch-simple.png' if phase2 else 'arch-simple-no-phase2.png', dpi=200)


# ── 04-④ 1/2 스캔 흐름 + 관제자 명령 ───────────────────────────────────
# 근거: scan_manager README(시퀀스 · 전이표 · 재시작 · 안전복귀) · 계약 7.1 · 7.3 · 7.4 · 7.5 · 9 장(v0.1.21)
def fig_scan_flow():
    W, H = 12.3, 4.45
    fig, ax = canvas(W, H)
    t(ax, 0.1, 4.28, '정상 흐름', size=14, bold=True, color=NAVY, ha='left')
    steps = [('준비', '기준점 · 영점'), ('윗면', '내려서 닿기'), ('모서리 × 4', '밀어서 떨어짐'), ('형상', '5 점 → 직육면체'),
             ('복귀', '들어 올림 → 홈'), ('완료', '')]
    x, w, gap, y0, h = 0.1, 1.83, 0.24, 2.95, 1.0
    for i, (head, sub) in enumerate(steps):
        done = i == 5
        rbox(ax, x, y0, w, h, face=PALE_GREEN if done else PALE_BLUE, edge=GREEN if done else NAVY, lw=2, r=0.1, z=2)
        t(ax, x + w / 2, y0 + h * (0.62 if sub else 0.5), head, size=17, bold=True, color=GREEN if done else NAVY)
        if sub:
            t(ax, x + w / 2, y0 + h * 0.26, sub, size=12)
        if i < 5:
            arrow(ax, (x + w + 0.02, y0 + h / 2), (x + w + gap - 0.02, y0 + h / 2), color=NAVY, lw=2.6, ms=16)
        if i == 2:
            ax.add_patch(FancyArrowPatch((x + w * 0.25, y0 + h), (x + w * 0.75, y0 + h), arrowstyle='-|>',
                                         mutation_scale=14, color=BLUE, linewidth=2, connectionstyle='arc3,rad=-0.9',
                                         zorder=3))
            t(ax, x + w / 2 + 1.0, y0 + h + 0.3, '방향 전환: 올림 → 원점 → 다시 닿기', size=12, color=BLUE, ha='left')
        x += w + gap
    ax.plot([0.1, W - 0.1], [2.78, 2.78], color='#C9D3E3', linewidth=1.5)
    t(ax, 0.1, 2.55, '관제자 명령 — 서로 부르지 않는다', size=14, bold=True, color=NAVY, ha='left')
    lanes = [
        ('중지', AMBER, '#FFF5CC', '멈춤 확인 → 멈춘 자리 · 측정값 기록'),
        ('재시작', BLUE, PALE_BLUE, '확정값 유지 → 멈춘 단계부터  (오류 뒤는 403 · 404 · 407 만)'),
        ('안전복귀', GRAY, '#EDEDED', '위치 확인 → 수직 올림 → 도착 확인 → 홈'),
        ('실패', RED, PALE_RED, '그 자리에서 멈춤 · 원인 · 위치 기록 · 자동 복귀 없음'),
    ]
    for i, (name, col, face, desc) in enumerate(lanes):
        y = 2.1 - i * 0.5
        rbox(ax, 0.1, y - 0.21, 1.5, 0.42, face=col, edge=col, r=0.1, z=2)
        t(ax, 0.85, y, name, size=14, bold=True, color='white')
        rbox(ax, 1.75, y - 0.21, W - 1.85, 0.42, face=face, edge=face, r=0.1, z=1)
        t(ax, 1.95, y, desc, size=13, ha='left')
    return save(fig, 'scan-flow.png', dpi=200)


# ── 04-④ 2/2 5 점 → 편향 보정 → 직육면체 (+ 탐침 확대) ───────────────────
# 출처: 9/23 실기 scan 20260923-183211-3702 의 result.json (docs/phase2/fixtures, #186) · #180 학민 코멘트(9/23)
RAW = {'POS_X': 462.21853637695315, 'NEG_X': 376.6019287109375, 'POS_Y': -117.126708984375, 'NEG_Y': -200.32232666015626}
CORR = {'POS_X': 1.3418279573560522, 'NEG_X': 1.2723855163138625, 'POS_Y': 1.2793940417820965,
        'NEG_Y': 1.2722189548564152}
SHAPE = dict(x_pos=40.621708419597106, x_neg=-42.38068577274862, y_pos=38.26889697384292, y_neg=-42.375107705299835,
             z_top=82.75947241210939, support_z=2.0, width=83.00239419234573, length=80.64400467914276,
             height=80.75947241210939)


def fig_geometry():
    W, H = 8.2, 4.45
    fig = plt.figure(figsize=(W, H))
    # (a) 윗면 — 보정 전(○) → 보정 뒤(●) · 경로 후보(주황)
    ax = fig.add_axes((0.0, 0.02, 0.43, 0.86))
    ax.set_aspect('equal')
    ax.axis('off')
    x0, x1, y0, y1 = SHAPE['x_neg'], SHAPE['x_pos'], SHAPE['y_neg'], SHAPE['y_pos']
    ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, facecolor='#EEF2F9', edgecolor='none'))
    ax.plot([x0, x1, x1, x0, x0], [y0, y0, y1, y1, y0], color=ORANGE, linewidth=4, solid_capstyle='round')
    k = 4.0            # 보정량을 잘 보이게 4 배로 벌려 그린다(그림 안 표기)
    pts = {'POS_X': ((x1, 0), (1, 0)), 'NEG_X': ((x0, 0), (-1, 0)), 'POS_Y': ((0, y1), (0, 1)), 'NEG_Y': ((0, y0), (0, -1))}
    for key, ((cx, cy), (dx, dy)) in pts.items():
        rx, ry = cx + dx * CORR[key] * k, cy + dy * CORR[key] * k
        ax.plot(rx, ry, 'o', markersize=13, markerfacecolor='white', markeredgecolor=BLUE, markeredgewidth=2.4)
        ax.annotate('', xy=(cx, cy), xytext=(rx, ry), arrowprops=dict(arrowstyle='-|>', color=BLUE, lw=2))
        ax.plot(cx, cy, 'o', markersize=11, color=BLUE)
    ax.plot(0, 0, 'o', markersize=13, color=RED)
    ax.text(0, -12, f'{SHAPE["width"]:.1f} × {SHAPE["length"]:.1f}\n높이 {SHAPE["height"]:.1f} mm', ha='center',
            va='top', fontsize=14, color=NAVY, fontweight='bold', linespacing=1.3)
    ax.text(0, 8, '윗면 1 점', ha='center', fontsize=12, color=RED)
    ax.set_xlim(-60, 60)
    ax.set_ylim(-58, 58)
    fig.text(0.215, 0.955, '위에서 본 윗면 (9/23 실기)', ha='center', va='top', fontsize=13, color=TEXT, fontweight='bold')
    fig.text(0.215, 0.03, '○ 판정 좌표 → ● 보정 뒤 (간격 4 배 확대)', ha='center', fontsize=12, color=BLUE)

    # (b) 옆에서 본 탐침 + 확대
    bx = fig.add_axes((0.45, 0.0, 0.55, 1.0))
    bx.set_xlim(0, 4.5)
    bx.set_ylim(0, 4.45)
    bx.axis('off')
    fig.text(0.725, 0.955, '판정 순간의 탐침 — 왜 보정하나', ha='center', va='top', fontsize=13, color=TEXT, fontweight='bold')
    # 부재와 탐침(개략)
    bx.add_patch(Rectangle((0.1, 0.45), 1.1, 1.3, facecolor=PALE_BLUE, edgecolor=NAVY, linewidth=1.8))
    tip = (1.32, 1.83)
    bx.add_patch(Rectangle((tip[0] - 0.035, tip[1] + 0.06), 0.07, 1.35, facecolor='#B0B7C3', edgecolor='#6B7280'))
    bx.add_patch(Rectangle((tip[0] - 0.24, tip[1] + 1.25), 0.16, 0.55, facecolor='#6B7280', edgecolor='#374151'))
    bx.add_patch(Rectangle((tip[0] + 0.08, tip[1] + 1.25), 0.16, 0.55, facecolor='#6B7280', edgecolor='#374151'))
    bx.add_patch(Circle(tip, 0.075, facecolor='white', edgecolor=RED, linewidth=2))
    arrow(bx, (0.35, 3.55), (1.0, 3.55), color=BLUE, lw=2.4, ms=14)
    bx.text(0.67, 3.72, '밀기', ha='center', fontsize=12, color=BLUE)
    bx.text(0.33, 3.12, 'RG2 +\n탐침', ha='center', fontsize=12, color='#374151', linespacing=1.2)
    bx.add_patch(Circle(tip, 0.22, facecolor='none', edgecolor=GRAY, linewidth=1.5, linestyle='--'))
    # 확대 원 — 부재는 원 안에서만 보이게 자른다
    zc, zr = (3.2, 2.05), 1.2
    zoom = Circle(zc, zr, facecolor='white', edgecolor=GRAY, linewidth=1.8, zorder=1)
    bx.add_patch(zoom)
    for ang in (70, -50):
        a = math.radians(ang)
        bx.plot([tip[0] + 0.22 * math.cos(a), zc[0] - zr * math.cos(a)],
                [tip[1] + 0.22 * math.sin(a), zc[1] + zr * math.sin(a)], color=GRAY, linewidth=1.2, linestyle='--')
    s = 0.34                   # 확대 배율(그림 단위 / mm)
    r, dl = 2.0, 0.5
    d = math.sqrt(2 * r * dl - dl * dl)
    corner = (zc[0] - 0.3, zc[1] - 0.45)
    block = Rectangle((corner[0] - 2.0, corner[1] - 2.0), 2.0, 2.0, facecolor=PALE_BLUE, edgecolor=NAVY, linewidth=2,
                      zorder=2)
    bx.add_patch(block)
    block.set_clip_path(zoom)
    cen = (corner[0] + d * s, corner[1] + (r - dl) * s)
    bx.add_patch(Circle(cen, r * s, facecolor='none', edgecolor=RED, linewidth=2.6, zorder=3))
    bx.plot(*cen, 'o', color=RED, markersize=6, zorder=4)
    ride = corner[1] + r * s                         # 윗면에 얹혀 있을 때의 중심 높이
    bx.plot([corner[0] - 0.45, cen[0] + 0.05], [ride, ride], color=GRAY, linewidth=1.4, linestyle='--', zorder=3)
    bx.plot([cen[0] - 0.1] * 2, [ride, cen[1]], color=NAVY, linewidth=2.4, zorder=4)
    bx.text(cen[0] - 0.2, (ride + cen[1]) / 2 + 0.02, 'δ', fontsize=16, color=NAVY, ha='right', va='center',
            fontweight='bold', zorder=5)
    bx.plot([corner[0], cen[0]], [corner[1] - 0.12] * 2, color=NAVY, linewidth=2.2, zorder=4)
    bx.text((corner[0] + cen[0]) / 2, corner[1] - 0.32, 'd', fontsize=16, color=NAVY, ha='center',
            fontweight='bold', zorder=5)
    bx.plot([cen[0], cen[0] + r * s * 0.8], [cen[1], cen[1] + r * s * 0.6], color=RED, linewidth=1.8, zorder=4)
    bx.text(cen[0] + r * s * 0.45, cen[1] + r * s * 0.55, 'r', fontsize=15, color=RED, fontweight='bold', zorder=5)
    bx.text(zc[0], 0.55, 'd = √(2rδ − δ²)', ha='center', fontsize=15, color=NAVY, fontweight='bold')
    bx.text(zc[0] - 0.15, 0.2, '팁 중심은 d 만큼 바깥 → 되돌린다', ha='center', fontsize=12, color=TEXT)
    return save(fig, 'scan-geometry-bias.png', dpi=250)


# ── 04-⑧ #136 — 증상 → 원인 → 조치 → 결과 ────────────────────────────
def fig_problem():
    W, H = 12.3, 3.55
    fig, ax = canvas(W, H)
    cards = [('증상', RED, PALE_RED), ('원인', AMBER, '#FFF5CC'), ('조치 · PR #136', BLUE, PALE_BLUE),
             ('결과 (sim)', GREEN, PALE_GREEN)]
    cw, gap = 2.83, 0.28
    for i, (head, col, face) in enumerate(cards):
        x = 0.05 + i * (cw + gap)
        rbox(ax, x, 0.05, cw, 3.45, face=face, edge=col, lw=2, r=0.12)
        rbox(ax, x, 2.95, cw, 0.55, face=col, edge=col, r=0.12, z=2)
        t(ax, x + cw / 2, 3.22, head, size=16, bold=True, color='white')
        if i < 3:
            arrow(ax, (x + cw + 0.03, 1.7), (x + cw + gap - 0.03, 1.7), color=GRAY, lw=3, ms=20)
    # 1 증상
    x = 0.05
    t(ax, x + cw / 2, 2.2, '1 시간+', size=34, bold=True, color=RED)
    t(ax, x + cw / 2, 1.35, '감시자 종료를\n아무도 몰랐다', size=14)
    t(ax, x + cw / 2, 0.45, '하강 5 · 밀기 2 무감시', size=12, color=RED)
    # 2 원인
    x += cw + gap
    rbox(ax, x + 0.45, 1.75, 1.95, 0.7, face='white', edge=AMBER, lw=1.6, r=0.08, z=3)
    t(ax, x + cw / 2, 2.1, 'latched = false', size=15, bold=True, color=TEXT)
    t(ax, x + cw / 2, 1.35, '죽기 전 마지막 값을\n계속 믿었다', size=14)
    t(ax, x + cw / 2, 0.45, '값만 보고 나이는 안 봄', size=12, color='#8B6508')
    # 3 조치
    x += cw + gap
    t(ax, x + cw / 2, 2.2, '나이 = 지금 − stamp', size=17, bold=True, color=BLUE)
    t(ax, x + cw / 2, 1.35, '한도를 넘으면\nSTART · RESUME 거절', size=14)
    t(ax, x + cw / 2, 0.45, '안전복귀는 막지 않음', size=12, color=BLUE)
    # 4 결과
    x += cw + gap
    t(ax, x + cw / 2, 2.2, '5.5 s > 5.0 s', size=24, bold=True, color=GREEN)
    t(ax, x + cw / 2, 1.35, '→ START 거절 103\n누르기 전 경고', size=14)
    t(ax, x + cw / 2, 0.45, '시험 1124 · 실패 0', size=12, color=GREEN)
    return save(fig, 'problem-before-after.png', dpi=200)


# ── 04-⑨ 용접 모션: 8 선 · 45° 자세 · 스탠드오프 · 위빙 ──────────────────
def fig_weld():
    fig = plt.figure(figsize=(7.6, 4.3))
    ax = fig.add_axes((0.0, 0.2, 0.36, 0.7))
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
        ax.plot([Q[a][0], Q[b][0]], [Q[a][1], Q[b][1]], color=GRAY if failed else ORANGE, linewidth=3,
                linestyle=(0, (2, 1.5)) if failed else '-')
        mx, my = (Q[a][0] + Q[b][0]) / 2, (Q[a][1] + Q[b][1]) / 2
        ax.text(mx, my, lab, fontsize=12, color=GRAY if failed else ORANGE, fontweight='bold', ha='center',
                va='center', bbox=dict(boxstyle='round,pad=0.08', facecolor='white', edgecolor='none'))
    ax.set_xlim(-0.2, 1.65)
    ax.set_ylim(-0.12, 1.5)
    fig.text(0.18, 0.95, '8 선: 윗면 → 세로', ha='center', va='top', fontsize=13, color=TEXT, fontweight='bold')
    fig.text(0.18, 0.13, '점선 = 45° 도달 불가', fontsize=12, color=GRAY, ha='center', va='top')
    # (b) 단면
    bx = fig.add_axes((0.37, 0.08, 0.3, 0.8))
    bx.set_aspect('equal')
    bx.axis('off')
    bx.add_patch(Rectangle((-6, -6), 6, 6, facecolor=PALE_BLUE, edgecolor=NAVY, linewidth=1.5))
    th = math.radians(45)
    dvec = (-math.sin(th), -math.cos(th))
    s_off, r = 3.0, 2.0
    tcp = (-dvec[0] * s_off, -dvec[1] * s_off)
    cen = (tcp[0] - dvec[0] * r, tcp[1] - dvec[1] * r)
    bx.add_patch(Circle(cen, r, facecolor='none', edgecolor=RED, linewidth=2))
    ax_end = (cen[0] - dvec[0] * 9, cen[1] - dvec[1] * 9)
    bx.plot([cen[0], ax_end[0]], [cen[1], ax_end[1]], color=RED, linewidth=6, solid_capstyle='butt', alpha=0.35)
    bx.plot([0, 0], [0, 7.5], color=GRAY, linewidth=0.8, linestyle=(0, (1, 2)))
    bx.text(0.7, 7.2, '45°', fontsize=14, color=NAVY, fontweight='bold')
    bx.plot([0, tcp[0]], [0, tcp[1]], color=NAVY, linewidth=1.8)
    bx.text(tcp[0] / 2 + 0.5, tcp[1] / 2 - 1.0, '3 mm', fontsize=13, color=NAVY, fontweight='bold')
    bx.plot(0, 0, 'o', color=ORANGE, markersize=8)
    bx.text(-0.4, -1.0, '모서리', fontsize=12, color=ORANGE, ha='right', va='top')
    bx.set_xlim(-6.5, 11)
    bx.set_ylim(-6.5, 12.5)
    fig.text(0.52, 0.95, '45° · 3 mm 띄움', ha='center', va='top', fontsize=13, color=TEXT, fontweight='bold')
    # (c) 위빙
    cx = fig.add_axes((0.69, 0.2, 0.31, 0.62))
    cx.axis('off')
    L, pitch, amp = 24.0, 4.0, 2.0
    n = int(math.ceil(L / pitch))
    xs = [min(k * pitch, L) for k in range(n + 1)]
    ys = [0 if k in (0, n) else amp * (-1) ** k for k in range(n + 1)]
    cx.plot([0, L], [0, 0], color=ORANGE, linewidth=3)
    cx.plot(xs, ys, color=RED, linewidth=1.8, marker='o', markersize=5)
    cx.text(L / 2, -5.2, '지그재그 경유점', fontsize=13, color=TEXT, ha='center', fontweight='bold')
    cx.set_xlim(-1, L + 1)
    cx.set_ylim(-7, 5)
    fig.text(0.845, 0.95, '위빙', ha='center', va='top', fontsize=13, color=TEXT, fontweight='bold')
    return save(fig, 'weld-pose-weave.png', dpi=250)


def main():
    outs = [fig_compare(), fig_mvp_flow(), fig_value(), fig_procedure(), fig_arch(True), fig_arch(False),
            fig_scan_flow(), fig_geometry(), fig_problem(), fig_weld()]
    for out in outs:
        with open(out, 'rb') as fh:
            w, h = struct.unpack('>II', fh.read(24)[16:24])
        print(f'{out.name}: {w} x {h}' + ('' if w >= 1600 else '  ← 1600 px 미만'))


if __name__ == '__main__':
    main()
