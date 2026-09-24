"""현지 파트 발표 그림을 만든다 (04-③ · 04-⑥ · 04-⑧). 수치는 모두 아래 주석의 출처에서 옮겼다.

    python3 figures.py        # matplotlib 필요. graphviz(dot) 로 .dot 두 개도 png 로 만든다

출처
- 검출 하중: docs/test-reports/TR-01_20260923.md(PR #181) 2 절 — 2026-09-23 학민 실기, 하강 2 mm/s, 큐브 윗면 1 점
- 탐색 시간: docs/phase1/detection-safety-geometry.md 4 장 — scan 20260923-183211-3702, #180
- 기동 래치: PR #99 본문 — 2026-09-21 아침 Virtual + sim 재현
"""
import pathlib
import subprocess

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
BLUE, RED, GRAY, ORANGE = '#3378C8', '#C0392B', '#7F7F7F', '#E08E0B'
for f in font_manager.findSystemFonts():
    if 'NanumGothic.ttf' in f:
        font_manager.fontManager.addfont(f)
plt.rcParams.update({'font.family': 'NanumGothic', 'axes.unicode_minus': False, 'font.size': 13})


def detect_load():
    a = [3.99, 4.79, 4.42, 4.69, 5.15, 3.24, 4.80, 5.29, 3.64, 4.94]   # 임계 3.0 N, 10 회
    c = [3.12, 2.87, 2.70, 2.93, 2.91, 2.36, 2.41]                     # 임계 2.0 N, 실접촉 7 회
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6), sharey=True, gridspec_kw={'width_ratios': [10, 7]})
    # 평균은 보고서 값을 그대로 쓴다(4.495 를 반올림하면 4.50 이 되어 보고서 4.49 와 어긋난다)
    for ax, vals, name, mean_txt in ((axes[0], a, '판정 임계 3.0 N (10 회)', '4.49'),
                                     (axes[1], c, '판정 임계 2.0 N (실접촉 7 회)', '2.76')):
        colors = [RED if v > 5.0 else BLUE for v in vals]
        ax.bar(range(1, len(vals) + 1), vals, color=colors, width=0.65)
        ax.axhline(5.0, color=RED, ls='--', lw=1.5)
        ax.axhline(3.0, color=ORANGE, ls=':', lw=1.5)
        over = sum(v > 5.0 for v in vals)
        ax.set_title(f'{name}\n평균 {mean_txt} N · 5 N 초과 {over}/{len(vals)}', fontsize=14)
        ax.set_xticks(range(1, len(vals) + 1))
        ax.set_xlabel('회차')
        for i, v in enumerate(vals, 1):
            ax.text(i, v + 0.08, f'{v:.2f}', ha='center', fontsize=10)
        ax.spines[['top', 'right']].set_visible(False)
    axes[0].set_ylabel('접촉 확정 순간 외력 증분 ΔF [N]')
    axes[0].set_ylim(0, 6.2)
    axes[1].text(7.45, 5.0, 'KPI 5 N', color=RED, fontsize=11, va='center')
    axes[1].text(7.45, 3.0, '도전 3 N', color=ORANGE, fontsize=11, va='center')
    axes[1].set_xlim(0.4, 8.6)
    fig.suptitle('접촉 검출 하중 — 2026-09-23 실기(측정 학민), 하강 2 mm/s, 큐브 윗면 한 점 반복', fontsize=13, y=0.995)
    fig.tight_layout()
    fig.savefig(HERE / 'kpi-detect-load.png', dpi=160)
    plt.close(fig)


def scan_time():
    parts = [('스텝 긁기 (모서리 4 방향)', 331, BLUE), ('재접근 내림', 100, '#8FB3E0'), ('나머지 (계산값)', 7, GRAY)]
    fig, ax = plt.subplots(figsize=(12, 2.6))
    left = 0
    for name, sec, color in parts:
        ax.barh(0, sec, left=left, color=color, height=0.5)
        if sec > 40:
            ax.text(left + sec / 2, 0, f'{name}\n{sec} s', ha='center', va='center', color='white', fontsize=12)
        left += sec
    ax.text(left + 4, 0, '← 나머지 7 s', va='center', fontsize=11, color=GRAY)
    ax.axvline(120, color=RED, ls='--', lw=2)
    ax.text(124, -0.36, 'KPI 120 s', color=RED, fontsize=12, va='center')
    ax.set_xlim(0, 500)
    ax.set_ylim(-0.45, 0.35)
    ax.set_yticks([])
    ax.set_xlabel('시작 버튼 → 형상 생성 종료 [s]')
    ax.set_title('전체 탐색 시간 438 s — 2026-09-23 실기 통합 스캔 20260923-183211-3702 (스텝 모드)', fontsize=13)
    ax.spines[['top', 'right', 'left']].set_visible(False)
    fig.tight_layout()
    fig.savefig(HERE / 'kpi-scan-time.png', dpi=160)
    plt.close(fig)


def startup_latch():
    fig, axes = plt.subplots(2, 1, figsize=(12, 4.4), sharex=True)
    for ax, title, grace in ((axes[0], '고치기 전: 기동 중 샘플 공백 508 ms > 한계 500 ms → 로봇이 서 있는데 래치(403)', False),
                             (axes[1], '고친 뒤: 기동 후 3 s 는 최신성만 유예 → level 0 · latched false (과대 외력 · 하강 제한은 즉시)', True)):
        ax.set_xlim(0, 5)
        ax.set_ylim(0, 1)
        ax.axis('off')
        ax.set_title(title, fontsize=13, loc='left', color=RED if not grace else BLUE)
        ax.plot([0, 5], [0.45, 0.45], color='#444444', lw=1)
        for x in (0.0, 0.5, 1.0):
            ax.plot([x], [0.45], marker='|', color='#444444', markersize=14)
        ax.add_patch(plt.Rectangle((1.2, 0.3), 0.508, 0.3, color=ORANGE, alpha=0.7))
        ax.text(1.2 + 0.254, 0.72, '샘플 공백 508 ms', ha='center', fontsize=11)
        ax.text(0.0, 0.08, '노드 5 개 동시 기동', fontsize=11)
        if grace:
            ax.add_patch(plt.Rectangle((0, 0.26), 3.0, 0.38, fill=False, ec=BLUE, lw=2, ls='--'))
            ax.text(3.0, 0.72, 'startup_grace_s 3.0 s', color=BLUE, fontsize=11, ha='right')
            ax.text(3.6, 0.08, 'START 는 이 뒤에 온다', fontsize=11, color=GRAY)
        else:
            ax.annotate('SAMPLE_STALE → /robot/stop + 래치', xy=(1.71, 0.45), xytext=(2.4, 0.1),
                        fontsize=11, color=RED, arrowprops=dict(arrowstyle='->', color=RED))
    axes[1].text(0, -0.25, '시간 [s] — 개념도(공백의 시작 시각은 기록이 없어 임의 위치). 수치는 PR #99 로그', fontsize=10,
                 color=GRAY, transform=axes[1].transData)
    fig.tight_layout()
    fig.savefig(HERE / 'problem-startup-latch.png', dpi=160)
    plt.close(fig)


def dots():
    for name in ('detect-dataflow', 'safety-recovery'):
        subprocess.run(['dot', '-Tpng', '-Gdpi=160', f'{name}.dot', '-o', f'{name}.png'], cwd=HERE, check=True)


if __name__ == '__main__':
    detect_load()
    scan_time()
    startup_latch()
    dots()
