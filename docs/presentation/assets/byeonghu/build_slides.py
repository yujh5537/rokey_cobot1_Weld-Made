"""병후 파트 슬라이드 19 장(표지 · 목차 · 01 · 02 · 03 · 04-① ④ ⑦ ⑧ ⑨ · 05)을 template.pptx 에서 만든다.

    python3 figures.py && python3 build_slides.py      # python-pptx · matplotlib · graphviz 필요

- 현지 build_slides.py 와 같은 방식: 템플릿 장의 틀(배경 · 머리 · 부제 막대 · 오른쪽 위 라벨)만 복사하고 내용은 새로 넣는다.
  섹션마다 그 섹션의 양식 장(01 = 3 장, 02 = 4 장, 03 = 5 장, 04 = 6 장, 05 = 10 장)의 틀을 쓴다. 글꼴 · 색은 바꾸지 않는다.
- 표지 · 목차는 템플릿 1 · 2 장을 그대로 둔다(병후 파일만 가진다). 표지 제목은 용접을 뺀 기본값이다.
  용접이 들어간 표지는 slides-byeonghu-cover-weld.pptx 로 따로 만든다(9/29 용접 성사 시 합치기에서 바꾼다).
- [뺄 수 있음] 블록은 도형 이름에 "[뺄 수 있음]" 을 넣었다(선택 창에서 찾아 지운다). 다른 장은 그 블록을 참조하지 않는다.
- 노트 = 발표 대사(3~5 문장) + 괄호 안에 출처 · 합치기 메모. 팀원 입력이 필요한 칸은 "[받으면 채움: 이름]".
"""
import copy
import pathlib

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.opc.constants import RELATIONSHIP_TARGET_MODE as RTM
from pptx.opc.package import _Relationship
from pptx.util import Inches, Pt

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[3]
TEMPLATE = ROOT / 'docs' / 'presentation' / 'template.pptx'
OUT = ROOT / 'docs' / 'presentation' / 'slides-byeonghu.pptx'
OUT_COVER_WELD = ROOT / 'docs' / 'presentation' / 'slides-byeonghu-cover-weld.pptx'
DELIV = ROOT / 'docs' / 'deliverables'
FONT = '맑은 고딕'
TITLE_NO_WELD = '접촉 탐색으로 용접선 후보를 찾는 협동로봇 시스템'
BLUE, RED, GRAY, DARK, LIGHT = (RGBColor(0x33, 0x78, 0xC8), RGBColor(0xC0, 0x39, 0x2B), RGBColor(0x7F, 0x7F, 0x7F),
                                RGBColor(0x26, 0x26, 0x26), RGBColor(0xF2, 0xF5, 0xFA))
ORANGE, OR_FILL, WHITE = RGBColor(0xD2, 0x69, 0x1E), RGBColor(0xFF, 0xF1, 0xE0), RGBColor(0xFF, 0xFF, 0xFF)
LEFT, WIDTH = 0.5, 12.33

# 섹션별 틀: 템플릿 장 번호(0 부터) · 남길 도형 · 부제 그룹 · 내용 시작 y
FRAMES = {
    '01': (2, {'그래픽 16', '사각형: 둥근 한쪽 모서리 17', '그룹 19', '그림 25', '그룹 27', 'TextBox 30', 'TextBox 31'},
           '그룹 27', 2.45),
    '02': (3, {'그래픽 190', '사각형: 둥근 한쪽 모서리 38', '그룹 2', '그림 34', '그룹 4', 'TextBox 1', 'TextBox 3'},
           '그룹 4', 2.45),
    '03': (4, {'그래픽 118', '사각형: 둥근 한쪽 모서리 38', '그룹 2', '그림 34', '그룹 7', 'TextBox 1', 'TextBox 3'},
           '그룹 7', 2.45),
    '04': (5, {'그래픽 98', '사각형: 둥근 한쪽 모서리 38', '그룹 2', 'TextBox 1', 'TextBox 3', '그룹 13', 'TextBox 15',
               '그림 34'}, '그룹 13', 2.45),
    '05': (9, {'그래픽 60', '사각형: 둥근 한쪽 모서리 38', '그룹 2', '그림 34', '그룹 4', 'TextBox 1', 'TextBox 3'},
           '그룹 4', 2.7),
}
LABEL_SRC = (5, 'TextBox 15')   # 오른쪽 위 라벨("* 04-③ …")은 04 틀에만 있다 → 다른 틀에 복사한다


# ── 틀 · 도형 도우미 ───────────────────────────────────────────────────
def set_text_keep_format(tf, text):
    first = tf.paragraphs[0]
    run = first.runs[0] if first.runs else first.add_run()
    run.text = text
    for extra in first.runs[1:]:
        extra._r.getparent().remove(extra._r)
    for para in tf.paragraphs[1:]:
        para._p.getparent().remove(para._p)


def frame_slide(prs, templ, section, title, label):
    idx, keep, sub_group, _ = FRAMES[section]
    src = templ[idx]
    new = prs.slides.add_slide(src.slide_layout)
    for rId, rel in src.part.rels.items():
        if rel.reltype.endswith('/slideLayout') or rel.reltype.endswith('/notesSlide'):
            continue
        new.part.rels._rels[rId] = _Relationship(new.part.partname.baseURI, rId, rel.reltype, RTM.INTERNAL,
                                                 rel.target_part)
    for shape in src.shapes:
        if shape.name in keep:
            new.shapes._spTree.insert_element_before(copy.deepcopy(shape._element), 'p:extLst')
    if 'TextBox 15' not in keep:
        lab = next(s for s in templ[LABEL_SRC[0]].shapes if s.name == LABEL_SRC[1])
        new.shapes._spTree.insert_element_before(copy.deepcopy(lab._element), 'p:extLst')
    for shape in new.shapes:
        if shape.name == sub_group:
            box = max((s for s in shape.shapes if s.has_text_frame), key=lambda s: len(s.text_frame.text))
            set_text_keep_format(box.text_frame, title)
        elif shape.name == 'TextBox 15':
            set_text_keep_format(shape.text_frame, label)
    return new


def text_box(slide, x, y, w, h, lines, size=12, color=DARK, anchor=MSO_ANCHOR.TOP, fill=None, line=None,
             align=PP_ALIGN.LEFT, name=None):
    """lines: 문자열 또는 (문자열, {size, color, bold, after}) 목록."""
    shape = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    if name:
        shape.name = name
    if fill is not None:
        shape.fill.solid()
        shape.fill.fore_color.rgb = fill
    if line is not None:
        shape.line.color.rgb = line
        shape.line.width = Pt(1.25)
    tf = shape.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Inches(0.1)
    tf.margin_top = tf.margin_bottom = Inches(0.06)
    for i, item in enumerate(lines):
        text, opt = (item, {}) if isinstance(item, str) else item
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.alignment = opt.get('align', align)
        run = para.add_run()
        run.text = text
        run.font.name = FONT
        run.font.size = Pt(opt.get('size', size))
        run.font.bold = opt.get('bold', False)
        run.font.color.rgb = opt.get('color', color)
        para.space_after = Pt(opt.get('after', 4))
    return shape


def bullets(slide, x, y, w, h, items, size=12.5, head=None, name=None, fill=LIGHT):
    lines = [(head, {'bold': True, 'color': BLUE, 'size': size + 1.5})] if head else []
    for it in items:
        if isinstance(it, tuple):
            lines.append(it)
        else:
            lines.append((f'· {it}', {'size': size, 'after': 7}))
    return text_box(slide, x, y, w, h, lines, size=size, fill=fill, name=name)


def picture(slide, path, x, y, w=None, h=None):
    return slide.shapes.add_picture(str(path), Inches(x), Inches(y), Inches(w) if w else None,
                                    Inches(h) if h else None)


def table(slide, x, y, w, col_w, rows, size=10.5, row_h=0.36, header_fill=BLUE, fills=None, colors=None, name=None,
          bold_first_col=True, header_text=WHITE):
    shape = slide.shapes.add_table(len(rows), len(rows[0]), Inches(x), Inches(y), Inches(w), Inches(row_h * len(rows)))
    if name:
        shape.name = name
    tbl = shape.table
    for i, cw in enumerate(col_w):
        tbl.columns[i].width = Inches(cw)
    for r, row in enumerate(rows):
        tbl.rows[r].height = Inches(row_h)
        for c, value in enumerate(row):
            cell = tbl.cell(r, c)
            cell.margin_left = cell.margin_right = Inches(0.06)
            cell.margin_top = cell.margin_bottom = Inches(0.03)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.fill.solid()
            fill = header_fill if r == 0 else (fills or {}).get(r, LIGHT if r % 2 == 0 else WHITE)
            cell.fill.fore_color.rgb = fill
            tf = cell.text_frame
            tf.word_wrap = True
            for k, part in enumerate(value.split('\n')):
                para = tf.paragraphs[0] if k == 0 else tf.add_paragraph()
                run = para.add_run()
                run.text = part
                run.font.name = FONT
                run.font.size = Pt(size)
                run.font.bold = r == 0 or (bold_first_col and c == 0)
                run.font.color.rgb = header_text if r == 0 else (colors or {}).get((r, c), DARK)
    return shape


def footnote(slide, text, y=7.05):
    text_box(slide, LEFT, y, WIDTH, 0.3, [(text, {'size': 9, 'color': GRAY})], name='출처 각주')


def notes(slide, text):
    slide.notes_slide.notes_text_frame.text = text


# ── 표지 · 목차 ────────────────────────────────────────────────────────
def cover_title_box(slide):
    group = next(s for s in slide.shapes if s.name == '그룹 2')
    return next(s for s in group.shapes if s.name == 'TextBox 9')


COVER_NOTE = ('안녕하십니까, weld-made 팀장 박병후입니다. 저희는 로봇이 카메라나 추가 센서 없이 부재를 직접 만져서 형상을 알아내고, '
              '그 결과로 용접선 후보를 만드는 협동로봇 시스템을 만들었습니다. 장비는 두산 M0609 와 RG2 그리퍼, 그리고 그리퍼가 쥔 '
              '탐침 하나입니다. 개요와 진행 방식은 제가 먼저 말씀드리고, 모듈별 내용은 담당자가 이어서 설명하겠습니다.\n'
              '[합치기 체크] 제목에 "용접"이 들어가는 곳이다. 기본 표지는 용접을 뺀 제목("{no_weld}"). 9/29 에 용접이 성사되면 '
              'slides-byeonghu-cover-weld.pptx 의 표지(원래 제목 "접촉 탐색으로 용접선을 찾아 용접하는 협동로봇 시스템")로 바꾼다.')


def cover_and_toc(prs):
    cover, toc = prs.slides[0], prs.slides[1]
    set_text_keep_format(cover_title_box(cover).text_frame, TITLE_NO_WELD)
    notes(cover, COVER_NOTE.format(no_weld=TITLE_NO_WELD))
    notes(toc, '순서는 양식대로 다섯 부분입니다. 01 에서 왜 이 주제를 골랐는지, 02 와 03 에서 팀과 진행 방식을 말씀드리고, '
               '04 에서 실제로 만든 것과 실기 결과를, 05 에서 자체 평가를 말씀드립니다. 04 는 모듈 담당자가 차례로 발표합니다.')


# ── 01 개요 ────────────────────────────────────────────────────────────
def s_01_background(prs, templ):
    s = frame_slide(prs, templ, '01', '직접교시는 품종이 바뀔 때마다 다시 해야 한다 — 다품종 소량일수록 부담이 크다',
                    '* 01-① 주제 · 배경 · 기획 의도')
    rows = [['고객이 지금 비용을 내는 곳', '내용', '성격'],
            ['재티칭 인건비 · 비가동', '품종 교체마다 교시 담당자의 시간이 들고, 그동안 셀이 멈춘다', '가정 A2 · A3 · A5'],
            ['교육비', '비숙련자가 용접 협동로봇 조작을 익히는 데 2~3 일', '근거 E16'],
            ['불량 · 재작업', '치수 · 지그 편차가 있으면 교시 경로와 실제 이음이 어긋난다', '가정 A6'],
            ['납기 지연', '교시 담당자가 없으면 교체가 밀린다(업체당 평균 2.8 명)', '근거 E3']]
    table(s, LEFT, 2.5, 7.3, [1.95, 4.05, 1.3], rows, size=10.5, row_h=0.72)
    bullets(s, 8.05, 2.5, 4.78, 4.15, [
        '문제 · 배경: 협동로봇 용접은 끝단을 잡고 점을 기록하는 직접교시에 의존하고, 품종이 바뀌면 다시 한다. 뿌리산업 종사자 68.2 % 가 40 대 이상, 10 인 미만 업체 89.3 % 가 인력 부족(E2 · E3)',
        '가설: 다품종 소량 중소 제조사에서 "품종 교체 시 재티칭"이 가장 큰 운영 비용이다. 단, 셋업을 15~30 분에 바꾼다는 주장도 있어 티칭 시간은 가정값으로 둔다(E13)',
        '기획 의도: 부재를 놓고 시작만 누르면 로봇이 만져서 좌표를 얻는다 — 교시 없이, 센서 추가 없이',
    ], head='왜 이 주제인가', size=12)
    footnote(s, '출처: BRD v3.2.0 1.1 · 3.1 · 3.3(US-01). E2 · E3 · E13 · E16 은 BRD 11 장 근거 자료, A2~A6 은 BRD 1.6 의 팀 가정값')
    notes(s, '주제의 출발점은 직접교시입니다. 협동로봇 용접은 작업자가 로봇 끝을 잡고 점을 하나씩 기록하는 방식이라, 품종이 '
             '바뀌면 이 일을 다시 해야 합니다. 품종이 자주 바뀌는 중소 현장일수록 이 시간이 쌓이고, 그 일을 맡을 숙련 인력도 '
             '부족합니다. 그래서 "부재를 놓고 시작만 누르면 로봇이 직접 만져서 좌표를 얻는다"를 목표로 잡았습니다. 다만 티칭 '
             '시간 자체는 현장마다 달라서, 사실이 아니라 가정으로 두었습니다.\n(출처: BRD 1.1 · 3.1)')


def s_01_point(prs, templ):
    s = frame_slide(prs, templ, '01', '센서를 더하지 않고 로봇이 만져서 찾는다 — 그 과정을 실시간 3D 로 보여준다',
                    '* 01-② 특화 포인트')
    rows = [['대안', '티칭', '추가 장비 · 통합', '약점'],
            ['재티칭 (현행)', '매번', '없음', '인력 의존, 교시 중 비가동'],
            ['와이어 터치센싱', '기준 경로 필요', '감지 기능이 있는 용접 전원 · 와이어 커터', '통전되는 깨끗한 모서리 필요, 경로를 오프셋할 뿐'],
            ['레이저 · 3D 비전', '제품에 따라 불필요', '센서 · 핸드아이 캘리브레이션\n1만~5만 달러 이상(E12)', '반사 표면 · 아크광 · 스패터 · 연기에 약함'],
            ['본 시스템', '불필요', '없음 (무센서 탐침 팁)', '탐색 시간, 단순 형상 · 규칙 배치 (MVP)']]
    table(s, LEFT, 2.5, 7.55, [1.55, 1.35, 2.4, 2.25], rows, size=10, row_h=0.66,
          fills={4: RGBColor(0xE3, 0xEC, 0xF8)}, colors={(4, 0): BLUE, (4, 1): BLUE, (4, 2): BLUE})
    bullets(s, 8.3, 2.5, 4.53, 3.0, [
        '무센서 탐침 접촉 탐색: RG2 는 탐침을 쥐는 손가락, 로봇 관절 토크로 추정한 외력이 촉각이 된다',
        '실시간 3D 관제: 탐색 단계 · 접촉점 · 형상을 웹에 바로 그리고, 중지 · 안전복귀 · 재시작은 서로 독립된 버튼',
    ], head='무엇이 다른가')
    text_box(s, 8.3, 5.6, 4.53, 1.05, [
        ('[뺄 수 있음]', {'size': 9, 'color': ORANGE, 'bold': True, 'after': 2}),
        ('· 스캔 결과로 용접까지: 같은 결과로 모서리를 용접 자세로 따라간다', {'size': 12.5})],
        fill=OR_FILL, name='[뺄 수 있음] 01-② 용접 불릿')
    footnote(s, '출처: BRD v3.2.0 3.2 · 1.5, ADR 0001(접촉 판정은 로봇 내장 힘 감지). 비전 가격은 E12, 원화 환산은 가정 A9')
    notes(s, '비슷한 문제를 푸는 방법은 세 가지가 있습니다. 와이어 터치센싱은 용접 전원에 감지 기능이 있어야 하고, 레이저나 '
             '3D 비전은 비싸고 반사나 아크광에 약합니다. 저희는 센서를 더하지 않고, 이미 로봇에 있는 관절 토크 기반 외력 추정을 '
             '촉각으로 쓰고 그리퍼는 탐침을 쥐는 손가락으로 씁니다. 그리고 로봇이 지금 무엇을 찾고 있는지를 웹 3D 화면에 실시간으로 '
             '보여줍니다. [뺄 수 있음 불릿] 이 결과로 모서리를 용접 자세로 따라가는 것까지 이어 봤습니다.\n'
             '(출처: BRD 3.2 · ADR 0001. [합치기 체크] 용접을 빼면 주황 상자 "[뺄 수 있음] 01-② 용접 불릿" 만 지운다)')


def s_01_concept(prs, templ):
    s = frame_slide(prs, templ, '01', 'MVP: 직육면체 하나를 다섯 번 만져 형상과 경로 후보를 만들고 웹에 보여준다',
                    '* 01-③ 구현 내용 · 컨셉 · 훈련 연관')
    picture(s, HERE / 'overview-mvp-flow.png', LEFT, 2.5, w=7.3)
    rows = [['훈련 내용', '이 프로젝트에서'],
            ['ROS 2 노드 · 통신', '자체 노드 5 개, 토픽 · 서비스 · 액션과 QoS 를 계약 문서로 먼저 정의'],
            ['두산 DSR 서비스', '이동 · 순응/힘 제어 · 외력 조회를 robot_manager 한 곳에서만 호출'],
            ['launch · 파라미터', 'bringup 하나로 5 노드. source:=sim | robot_force 로 입력원 전환, 수치는 yaml'],
            ['HMI · 연동', 'React + Three.js 3D, MQTT · FastAPI · Spring Boot · PostgreSQL']]
    table(s, 8.0, 2.5, 4.83, [1.45, 3.38], rows, size=10, row_h=0.8)
    footnote(s, '출처: BRD v3.2.0 2 장 포함 범위 · 1.4 절(탐색 절차) · docs/architecture.md · 산출물 01 시스템 아키텍처')
    notes(s, 'MVP 범위는 한 장으로 이렇습니다. 작업대에 놓인 직육면체를 로봇이 위에서 한 번, 네 방향 옆으로 한 번씩, 모두 다섯 번 '
             '만집니다. 이 다섯 점을 탐침 크기만큼 보정해서 직육면체와 윗면의 외곽 엣지, 즉 경로 후보 네 개를 만들고, 그 과정을 웹 '
             '3D 화면에 보여줍니다. 오른쪽은 수업에서 배운 것과의 연결입니다 — ROS 2 노드와 통신, 두산 DSR 서비스, launch 와 '
             '파라미터, 그리고 HMI 입니다.\n(출처: BRD 2 장 · architecture.md)')


def s_01_value(prs, templ):
    s = frame_slide(prs, templ, '01', '품종 교체가 잦은 현장에서 티칭 시간을 줄인다 — 수치는 모두 가정이다',
                    '* 01-⑤ 활용방안 · 기대효과')
    rows = [['BRD 1.6 시나리오 (가정)', '보수적', '기본', '낙관적'],
            ['품종 교체 횟수 (A2)', '일 1 회', '일 2 회', '일 4 회'],
            ['1 회 재티칭 시간 (A3)', '0.5 h', '1.0 h', '2.0 h'],
            ['연간 절감액 (계산)', '250 만원', '1,775 만원', '9,050 만원'],
            ['투자 회수 (도입비 1,000 만원 가정)', '약 6.7 년', '약 7.2 개월', '약 1.3 개월'],
            ['판정', '도입 부적합', '적합', '적합']]
    table(s, LEFT, 2.5, 7.3, [2.8, 1.5, 1.5, 1.5], rows, size=10.5, row_h=0.55,
          colors={(5, 1): RED, (5, 2): BLUE, (5, 3): BLUE})
    text_box(s, LEFT, 5.95, 7.3, 0.7, [
        ('주의: 이 수치는 최종 비전(임의 배치 · 다양한 형상) 기준이다. 직육면체 · 규칙 배치의 MVP 는 그 자체로 이 절감액을 '
         '실현하지 못하는 원리 실증 단계다.', {'size': 10.5, 'color': RED})])
    bullets(s, 8.05, 2.5, 4.78, 4.15, [
        '가치: 설비 추가 없이 기존 협동로봇 + 탐침 팁. 와이어 터치센싱을 못 쓰는 현장(감지 기능 없는 용접기, 도장 · 스케일 표면)부터',
        '목표 고객: 품종 교체가 하루 2 회 이상이거나 1 회 티칭이 1 시간 안팎인 임가공 · 제관 업체',
        'MVP 이후: 비스듬한 배치 · 곡면, 오차 ±3 → ±1 mm, 마커로 경로 따라 긋기 → 최종: 임의 배치 · 실용접',
    ], head='활용 방안')
    footnote(s, '출처: BRD v3.2.0 1.5 · 1.6(A1~A9 은 팀 가정. A3 보수값만 근거 E13) · 3.2 가격 포지셔닝 · 2 장 MVP 구분')
    notes(s, '기대효과는 BRD 의 경제성 계산을 그대로 옮겼고, 표의 입력은 모두 저희가 둔 가정입니다. 품종 교체가 하루 두 번, 한 번 '
             '티칭에 한 시간이면 도입비 1,000 만원을 7 개월쯤에 회수한다는 계산이 나오지만, 하루 한 번에 30 분이면 7 년 가까이 '
             '걸려 맞지 않습니다. 그래서 목표 고객을 품종 교체가 잦은 임가공 · 제관 업체로 좁혔습니다. 그리고 이 숫자는 최종 비전 '
             '기준이라, 지금 MVP 가 이 절감을 바로 만든다고는 말씀드리지 않겠습니다.\n(출처: BRD 1.5 · 1.6 · 2 장)')


# ── 02 팀 ──────────────────────────────────────────────────────────────
def s_02_team(prs, templ):
    s = frame_slide(prs, templ, '02', '네 명이 노드를 나눠 맡고, 계약 문서로 경계를 정했다', '* 02 팀 구성 및 역할')
    rows = [['이름', '역할', '담당 패키지 · 모듈', '담당 산출물'],
            ['박병후', '팀장 · 전체 구성 · 계약', 'scan_manager(result_store) · contact_scan_interfaces', '01 아키텍처 · 05 인터페이스 · 06 노드 구조도 · BRD · 발표자료'],
            ['김학민', '로봇 제어 · 좌표 기준', 'robot_manager · 좌표 · TCP · 홈', '04 하드웨어 · 08 예외 · 오류 · 09 위험 · 안전'],
            ['남현지', '접촉 판정 · 안전 감시 · 통합', 'contact_detector · safety_monitor · geometry_estimator · bringup', '03 동작 순서도 · 02 네트워크(메인 PC) · 소스 zip · 영상'],
            ['정의석', '관제 화면 · 연동', 'mqtt_bridge · FastAPI · Spring Boot · React(3D 관제)', '02 네트워크(웹 PC) · 07 HMI · Readme · 영상']]
    table(s, LEFT, 2.5, WIDTH, [1.2, 2.6, 4.4, 4.13], rows, size=11, row_h=0.62)
    text_box(s, LEFT, 5.75, WIDTH, 0.85, [
        ('멘토 이일주 — 주제 선정 피드백 · 프로젝트 질의응답 · 중간 점검', {'bold': True, 'color': BLUE, 'size': 13}),
        ('역할 · 담당 한 줄은 팀원 확인 전이다(담당 표 기준)', {'size': 10, 'color': GRAY})], fill=LIGHT)
    footnote(s, '출처: ws_cobot1/src/README.md 담당 표 · docs/deliverables/README.md 2 · 3 절 · docs/presentation/outline-v1.md')
    notes(s, '팀은 네 명이고, ROS 노드를 하나씩 나눠 맡았습니다. 저는 스캔 순서를 조정하는 scan_manager 와 인터페이스 패키지, 계약 '
             '문서를 맡았고, 학민은 로봇 제어와 좌표 기준, 현지는 접촉 판정과 안전 감시, 의석은 관제 화면과 연동을 맡았습니다. '
             '네 명이 동시에 개발하기 위해 노드 사이의 이름과 형식을 계약 문서로 먼저 정했습니다. 멘토님께는 주제 선정과 중간 '
             '점검에서 피드백을 받았습니다.\n'
             '(팀원 확인 전: "역할" 열과 "담당 한 줄"은 담당 표로 채웠다. 받으면 채움: 학민 · 현지 · 의석의 담당 한 줄)')


# ── 03 절차 · 방법 ─────────────────────────────────────────────────────
def s_03_schedule(prs, templ):
    s = frame_slide(prs, templ, '03', '계약을 먼저 얼리고, 모듈 → 통합 → 실기를 엿새 안에 끝냈다 (9/18 ~ 9/23)',
                    '* 03 수행 절차 · 일정')
    rows = [['단계', '기간', '한 일', '결과물'],
            ['기획', '9/14 ~ 9/17', '주제 선정 · 요구사항 · 아키텍처 · 인터페이스 초안', 'BRD · 설계 문서(docs/design)'],
            ['계약 동결', '9/18', '토픽 · 서비스 · 액션 · MQTT · 좌표 규칙 합의', 'docs/contracts v0.1'],
            ['모듈 개발', '9/19 ~ 9/20', '노드별 병렬 구현 · 단위시험 · sim', '패키지 5 개 + 웹'],
            ['통합 · 실기', '9/21 ~ 9/23', 'sim → 에뮬레이터 → 실기, 9/21 저녁 기능 동결', '실기 종단 성공(9/23) · 시험 보고'],
            ['[뺄 수 있음] phase 2', '9/24 ~ 9/29', '스캔 결과로 용접 모션: 계약 → 구현 → 9/29 실기', 'docs/phase2'],
            ['발표', '9/30', '결과 보고 · 평가', '발표자료 · 영상 · 소스 · Readme']]
    table(s, LEFT, 2.5, WIDTH, [1.9, 1.5, 5.2, 3.73], rows, size=11.5, row_h=0.58, fills={5: OR_FILL},
          colors={(5, 0): ORANGE, (5, 1): ORANGE, (5, 2): ORANGE, (5, 3): ORANGE})
    footnote(s, '출처: docs/presentation/outline-v1.md · docs/conventions.md(기능 동결) · docs/test-reports/daily · PR #179(9/23 실기 종단). '
                '주황 행은 [뺄 수 있음] — 표에서 행만 지운다')
    notes(s, '일정은 여섯 단계였습니다. 나흘 동안 요구사항과 설계를 정리하고, 9/18 에 노드 사이의 약속을 계약 문서로 얼렸습니다. '
             '그 뒤 이틀 동안 각자 모듈을 만들고, 9/21 부터 사흘 동안 통합과 실기를 해서 9/23 에 실기에서 웹까지 이어지는 종단 '
             '실행에 성공했습니다. [뺄 수 있음 행] 연휴에는 그 결과로 용접 모션을 이어 붙였습니다. 발표는 오늘입니다.\n'
             '([합치기 체크] 용접을 빼면 주황 행만 지운다)')


def s_03_procedure(prs, templ):
    s = frame_slide(prs, templ, '03', '요구 → 계약 → 병렬 개발 → sim → 에뮬레이터 → 실기 → 시험 보고 순서로 검증했다',
                    '* 03 수행 절차 · 도식')
    picture(s, HERE / 'method-procedure.png', LEFT, 2.45, w=WIDTH)
    bullets(s, LEFT, 5.35, WIDTH, 1.6, [
        '계약이 코드보다 우선: 이름 · 필드 · 단위가 바뀌면 계약 문서 · 인터페이스 패키지 · 변경 이력을 한 번에 고친다. 둘이 어긋나면 동기화 시험이 CI 에서 실패한다',
        '입력원 전환: launch 인자 하나(source:=sim | robot_force)로 로봇 없이 전체 흐름을 돌린다',
        '실측은 설계 출발값을 바꾼다: 실기에서 잰 값은 yaml 과 계약 개정으로만 들어간다 — 실기 PC 에만 남은 값은 없는 값',
    ], size=11.5)
    footnote(s, '출처: docs/conventions.md · docs/contracts/CHANGELOG.md(v0.1 → v0.1.20, 9/18~9/23) · contact_scan_interfaces test_contract_sync')
    notes(s, '진행 순서는 이 그림과 같습니다. 요구사항에서 계약을 만들고, 계약을 기준으로 네 명이 병렬로 개발했습니다. 검증은 로봇 '
             '없이 가상 접촉을 만드는 sim, 두산 에뮬레이터, 그리고 실기 순서로 올라갔고, 결과는 시험 보고서로 남겼습니다. 실기에서 '
             '잰 값은 파라미터 파일과 계약 개정으로만 되돌렸는데, 9/18 에 얼린 계약을 9/23 까지 열아홉 번 고쳤습니다.\n'
             '(출처: CHANGELOG — v0.1.1 ~ v0.1.20 의 19 항목. v0.1.17 은 번호만 비어 있다)')


def s_03_method(prs, templ):
    s = frame_slide(prs, templ, '03', '작게 나눠 리뷰받고, 수치는 파라미터로 두고, 결과는 보고서로 남겼다',
                    '* 03 수행 방법  [뺄 수 있음]')
    rows = [['방법', '어떻게'],
            ['작업 1 개 = PR 1 개', '한 작업은 한 브랜치 · 한 PR. 변경 파일이 15 개를 넘으면 쪼갠다. main 에 직접 올리지 않는다'],
            ['리뷰', '계약 · 인터페이스 · 공용 파일은 코드 오너 승인 뒤 머지. 다른 사람 패키지는 소유자에게 리뷰 요청'],
            ['3 단계 검증', 'sim → 두산 에뮬레이터(Virtual Mode) → 실기. 앞 단계에서 되는 것만 다음 단계로'],
            ['파라미터', '임계 · 속도 · 힘 · 거리는 코드에 박지 않고 yaml 에(sim · real 분리)'],
            ['실측 분리', '설계 출발값 · 실측값 · 계산값을 문서에서 구분. 미측정은 0 이 아니라 NaN · null'],
            ['시험 보고', '시험 번호(TR)별 보고서 + 저녁 통합 기록(daily). 실패 · 미달도 그대로 적는다']]
    table(s, LEFT, 2.5, WIDTH, [2.4, 9.93], rows, size=12, row_h=0.6)
    footnote(s, '출처: docs/conventions.md · docs/test-reports/README.md · docs/contracts/units-frames.md(단위) · 이 장은 [뺄 수 있음]')
    notes(s, '개발 규칙은 여섯 가지였습니다. 작업 하나를 PR 하나로 작게 나눴고, 계약처럼 모두가 쓰는 파일은 코드 오너의 승인을 '
             '받아야 들어가게 했습니다. 속도나 힘 같은 숫자는 코드에 박지 않고 설정 파일에 두었고, 설계에서 잡은 값과 실제로 잰 '
             '값을 문서에서 섞지 않았습니다. 결과는 실패와 미달까지 보고서로 남겼습니다.\n'
             '(이 장은 [뺄 수 있음] — 15 분 발표면 ⑨ 다음으로 뺀다. 도구 이름 · 이슈 · PR 개수는 넣지 않았다)')


# ── 04 수행 경과 ────────────────────────────────────────────────────────
def s_04_arch(prs, templ):
    s = frame_slide(prs, templ, '04', '두 PC 와 로봇 컨트롤러 — 접촉 판정과 정지는 메인 PC 안에서 끝난다',
                    '* 04-① 시스템 아키텍처')
    picture(s, DELIV / '01-system-architecture.png', 1.05, 2.42, w=10.25)
    footnote(s, '출처: 산출물 01 시스템 아키텍처 v1.7 · 06 ROS2 노드 구조도 v1.2(선 하나하나) · docs/contracts/ros-interfaces.md 2 장 · '
                'docker/docker-compose.yml', y=7.1)
    notes(s, '전체 구성입니다. 왼쪽 웹 PC 에는 브로커 · FastAPI · DB · Spring 이 Docker 로 돌고, 화면은 React 입니다. 가운데 메인 '
             'PC 에서 ROS 2 노드 다섯 개가 돌고, 로봇에 명령을 내리는 것은 robot_manager 하나뿐이고, 두산 드라이버를 거쳐 오른쪽 로봇 컨트롤러로 갑니다. 핵심은 '
             '빨간 선입니다 — 접촉 판정과 안전 정지는 웹을 거치지 않고 메인 PC 안에서 끝나서, 웹이 끊겨도 로봇은 멈출 수 있습니다. '
             '주황 점선은 연휴에 더한 용접 부분으로, 구현은 아직 진행 중입니다.\n'
             '([합치기 체크] 용접을 빼면 그림을 docs/deliverables/01-system-architecture-no-phase2.png 로 바꾸고 마지막 문장을 뺀다)')


def s_04_sequence(prs, templ):
    s = frame_slide(prs, templ, '04', '스캔 순서는 상태기계 하나가 쥔다 — 중지 · 안전복귀 · 재시작은 서로 부르지 않는다',
                    '* 04-④ 탐색 시퀀스 · 형상 (1/2)')
    picture(s, HERE / 'scan-state-machine.png', LEFT, 2.42, w=WIDTH)
    bullets(s, LEFT, 6.1, WIDTH, 0.95, [
        '방향 전환(2 번째부터): 올림 → 기준 원점 x · y 로 이동 → 첫 접촉 높이 + 여유까지 저속 내림 → 밀기. 윗면을 다시 재지 않는다',
        '작업 기록을 디스크에 먼저 만들고 움직인다. 재시작은 그 기록만 보고 확정 안 된 방향부터 잇는다(sim · 시험으로 확인, 실기 미실시)',
    ], size=11, fill=None)
    footnote(s, '출처: ws_cobot1/src/scan_manager/README.md(전이표 · 시퀀스 · 재시작) · docs/contracts/ros-interfaces.md 7.1 · 7.3 · 7.4 · '
                'TR-05(9/22 sim, 재시작 명령 독립 PASS)', y=7.1)
    notes(s, '제가 맡은 scan_manager 입니다. 스캔은 상태기계 하나가 순서를 쥐고 있어서, 준비 · 윗면 하강 · 네 방향 밀기 · 형상 계산 · '
             '마무리 복귀 순서로만 진행합니다. 두 번째 방향부터는 올리고, 원점 위로 가서, 처음 닿았던 높이 근처까지 천천히 내린 뒤 '
             '밉니다. 중지는 멈추기만 하고, 홈으로 가는 안전복귀와 이어서 하는 재시작은 관제자가 따로 누릅니다. 실패해도 자동으로 '
             '홈에 가지 않습니다. 재시작은 디스크의 기록만 보고 이어서, 프로세스가 죽었다 다시 떠도 같은 자리에서 잇는 것을 sim 과 '
             '시험으로 확인했습니다 — 실기에서는 아직 못 해 봤습니다.\n(출처: scan_manager README · 계약 7 장)')


def s_04_geometry(prs, templ):
    s = frame_slide(prs, templ, '04', '판정 좌표는 모서리를 지난 뒤에 찍힌다 — 팁 기하만큼 되돌려 직육면체를 만든다',
                    '* 04-④ 탐색 시퀀스 · 형상 (2/2)')
    picture(s, HERE / 'scan-geometry-bias.png', LEFT, 2.45, w=7.5)
    rows = [['9/23 실기 1 회', '값', '구분'],
            ['하강량 δ (4 방향)', '0.46 ~ 0.52 mm', '실측'],
            ['방향별 보정량 d', '1.27 ~ 1.34 mm', '계산값'],
            ['폭 × 길이 × 높이', '83.00 × 80.64 ×\n80.76 mm', '실측 + 보정'],
            ['캘리퍼 대비 오차', '+1.50 / −0.36 /\n+0.26 mm', 'KPI ±3 mm 안'],
            ['10 회 반복성', '미실시', 'TR-02'],
            ['보정 입력', 'r 2 mm · t 0 · R 0', '설정값']]
    table(s, 8.2, 2.5, 4.63, [1.75, 1.73, 1.15], rows, size=10.5, row_h=0.6,
          colors={(4, 2): BLUE, (5, 1): RED, (5, 2): RED})
    footnote(s, '출처: 9/23 실기 scan 20260923-183211-3702 result.json(docs/phase2/fixtures, PR #186 머지 전) · 캘리퍼 대비는 #180 학민 코멘트(9/23) · '
                '식은 geometry_estimator README', y=7.1)
    notes(s, '두 번째 장은 다섯 점으로 형상을 만드는 방법입니다. 탐침이 모서리를 넘어가 팁이 살짝 내려앉는 순간에 "모서리"로 판정하기 '
             '때문에, 판정 좌표는 실제 모서리보다 바깥에 찍힙니다. 그래서 팁 반지름과 내려앉은 깊이로 그 거리를 계산해 되돌립니다 — '
             '9/23 실기에서는 방향마다 1.3 mm 안팎이었습니다. 보정한 결과는 캘리퍼 대비 폭 +1.50, 길이 −0.36, 높이 +0.26 mm 로 '
             '목표 ±3 mm 안이었습니다. 다만 한 번 잰 값이고, 10 회 반복성은 아직 재지 않았습니다. 보정된 윗면 사각형의 네 변이 경로 후보이고, 용접 이음을 판정한 것은 아닙니다.\n'
             '(출처: result.json 3702 · #180. 보정량은 result.json 의 bias_corrections 값)')


def s_04_eval(prs, templ):
    s = frame_slide(prs, templ, '04', '평가 다섯 항목마다 증거를 붙였다 — 미달 · 미실시도 같은 표에 둔다',
                    '* 04-⑦ 평가 항목 대응표')
    rows = [['평가 항목', '우리가 한 것', '증거 (장 · 문서 · 시험 보고)'],
            ['기능 구현\n완전성', '교시 없이 5 점 → 직육면체 · 외곽 엣지 · 경로 후보 4 → 웹 3D. 버튼 5 개(시작 · 중지 · 안전복귀 · 재시작 · 안전 해제), 설정 등록은 화면 버튼 미구현. '
             '전체 탐색 438 s 로 KPI 120 s 미달',
             '04-⑥ · 04-⑩ · PR #179(9/23 실기 종단) · #180(탐색 시간)'],
            ['기능 구현\n정확성', '치수 캘리퍼 대비 +1.50 / −0.36 / +0.26 mm(±3 mm 안, 1 회). 검출 하중은 평균 4.49 N 이지만 10 회 중 2 회가 5 N 초과 → 미달',
             '04-④ · 04-⑥ · TR-01(9/23 실기) · #180'],
            ['동작 · 운용\n안정성', '9/23 실기 웹 → ROS → 웹 종단 성공(연속 회차 기록 없음). 정지는 메인 PC 안에서 두 겹 감시 · 래치. 관제 반영 지연 최대 312 ms → 미달',
             '04-③ · TR-05(9/22, 반영 지연 FAIL) · daily 0923 §7 정지 대응표'],
            ['입출력 데이터\n이해도', '계약 문서 한 벌(ROS · MQTT · 단위 · 좌표). 미측정은 0 이 아닌 NaN · null. 결과 원본 저장 → DB → 조회 일치',
             '04-① · 04-⑤ · 산출물 05 · 06 · TR-10(9/22 sim, 저장 · 조회 PASS)'],
            ['기능 동작\n지속성', '중지 · 안전복귀 · 재시작 독립, 재시작은 기록으로 잇는다. 감시자가 끊기면 시작 거절. 중지 반응 706 · 600 ms 는 sim 측정',
             '04-④ · 04-⑧ · TR-05(9/22 sim) · 산출물 08 · 09']]
    table(s, LEFT, 2.42, WIDTH, [1.45, 7.1, 3.78], rows, size=9.5, row_h=0.66,
          colors={(1, 1): DARK, (2, 1): DARK, (3, 1): DARK})
    table(s, LEFT, 6.58, WIDTH, [1.45, 7.1, 3.78],
          [['[뺄 수 있음]', '용접(phase 2) — 스캔 결과로 모서리 8 선. Virtual 8 선 DONE 246 s(가상 박스), 실기는 9/29', 'docs/phase2 · Virtual 기록(PR #197)']],
          size=10, row_h=0.42, header_fill=OR_FILL, header_text=ORANGE, name='[뺄 수 있음] 04-⑦ 용접 행')
    footnote(s, '출처: deliverables README 5 절 · TR-01(9/23) · TR-05(9/22, 설정 버튼 미구현) · TR-10(9/22) · #180 · PR #179. '
                '438 s = 액션 전체(마무리 복귀 포함)', y=7.1)
    notes(s, '평가 기준 다섯 항목에 저희가 한 것과 증거를 붙였습니다. 기능은 교시 없이 형상까지 나오고 치수는 목표 안이지만, 설정 등록은 '
             '화면 버튼이 아직 없고, 탐색 시간은 마무리 복귀까지 포함해 438 초로 목표의 3.6 배이며, 검출 하중은 평균만 보면 통과지만 열 번 중 두 번이 5 N 을 넘어 미달로 적었습니다. '
             '관제 반영 지연도 최대 312 ms 로 미달이고, 중지 반응 시간은 sim 에서만 쟀습니다. 실기에서 웹까지 이어지는 종단은 '
             '성공했지만 몇 번 연속인지는 기록이 없어 쓰지 않았습니다. 자세한 수치는 앞의 KPI 장에 있습니다.\n'
             '(주의: 달성처럼 읽히지 않게 outline 04-⑥ 의 "채울 때 주의"를 따랐다. [합치기 체크] 용접을 빼면 주황 표 "[뺄 수 있음] 04-⑦ 용접 행"만 지운다)')


def s_04_problem(prs, templ):
    s = frame_slide(prs, templ, '04', '감시자가 죽은 걸 아무도 몰랐다 → 상태의 "나이"로 스캔 시작을 막았다',
                    '* 04-⑧ 문제와 해결 (병후)')
    boxes = [
        ('증상', ['9/21 실기 safety_monitor 가 10:34 · 11:51 두 번 종료', '그 뒤 하강 5 · 밀기 2 가 2차 감시 없이',
                  'scan_manager 는 START 를 계속 받았다 — 1 시간 넘게 모름']),
        ('원인', ['"한 번도 못 받음"만 거절, "받다가 끊김"은 통과', '죽기 직전의 latched=false 가 계속 "안전 정상"으로 남음',
                  '값만 보고 값의 나이는 안 봤다']),
        ('조치 (PR #136)', ['START · RESUME 때 상태 토픽의 stamp 나이 검사', '끊기면 103 · 104 로 거절 + detail',
                          '한도는 파라미터(5.0 · 2.0 s), 안전복귀는 막지 않음']),
        ('결과 (sim 종단)', ['감시자 종료 → START 거절 103 "5.5 s 전, 한계 5.0 s"', '거절보다 먼저 끊김 WARN(297.87 < 298.25 s)',
                           '시험 1101 → 1124, 실패 0 (5 회 실행)']),
    ]
    w = (WIDTH - 0.3) / 4
    for i, (head, lines) in enumerate(boxes):
        text_box(s, LEFT + i * (w + 0.1), 2.45, w, 2.0,
                 [(f'{i + 1}. {head}', {'bold': True, 'size': 14, 'color': RED if i == 0 else BLUE})]
                 + [(f'· {t}', {'size': 10.5}) for t in lines], fill=LIGHT)
    picture(s, HERE / 'problem-status-age.png', LEFT, 4.55, w=WIDTH)
    text_box(s, LEFT, 6.72, WIDTH, 0.36, [
        ('남은 것: 실기 재확인 없음 · 진행 중인 스캔은 감시자가 죽어도 계속된다(안전 감사 "부분 해결")   교훈: 마지막 값은 살아 있다는 '
         '증거가 아니다 — 값과 함께 나이를 본다', {'size': 10.5, 'color': BLUE, 'bold': True})])
    footnote(s, '출처: PR #136 · #103 · #120 · realrobot-session_20260921 · safety-audit-review_20260922 D-1 · docs/phase1/scan_manager.md 5.1. '
                '마지막 stamp = 298.25 − 5.5 (계산)', y=7.1)
    notes(s, '제가 고친 문제 하나입니다. 9/21 실기에서 안전 감시 노드가 두 번 죽었는데, 두 번째 뒤로 하강 다섯 번과 밀기 두 번이 '
             '2차 감시 없이 돌았고 한 시간 넘게 아무도 몰랐습니다. 원인은 scan_manager 가 "한 번도 못 받은 상태"만 거절하고, 받다가 '
             '끊긴 상태는 마지막 값을 그대로 믿었던 것입니다. 그래서 상태 메시지의 시각으로 나이를 재서, 한도보다 오래됐으면 시작과 '
             '재시작을 거절하게 했습니다. sim 에서 감시자를 죽이면 거절되고, 누르기 전에 경고가 먼저 뜹니다. 다만 실기에서 다시 '
             '확인하지 못했고, 이미 돌고 있는 스캔은 멈추지 않는다는 한계가 남아 있습니다.\n'
             '(현지 04-③ 2 장 "감시자도 죽는다"(#117, 죽은 원인)와 짝 — 현지는 "죽었다", 병후는 "몰랐다". 출처: PR #136 본문 · 코멘트)')


def s_04_weld1(prs, templ):
    s = frame_slide(prs, templ, '04', '스캔 결과만으로 모서리 8 선을 용접 자세로 따라간다 — 닿지 않고 띄워서',
                    '* 04-⑨ phase 2 용접 (1/2)  [뺄 수 있음]')
    picture(s, HERE / 'weld-pose-weave.png', LEFT, 2.5, w=7.5)
    bullets(s, 8.2, 2.5, 4.63, 4.3, [
        '계약 먼저(9/23 초안 · 9/26 머지, v0.2.0): 노드 weld_manager · 타입 7 개 · 사유 코드 600~604 를 더하고, 1차 계약은 고치지 않았다',
        '자세: 두 면 법선의 이등분면에서 45° 기울이고 3 mm 띄운다(팁 구 표면 ↔ 이음선). 힘 · 순응 제어는 켜지 않는다',
        '위빙: move_periodic 은 이동과 겹쳐 돌지 않아 지그재그 경유점으로 — robot_manager 가 점마다 멈추며 지난다. 한 선이 실패하면 그 선만 FAILED 로 남기고 계속',
    ], size=11.5, head='phase 2 (9/24 ~ 9/29)')
    footnote(s, '출처: docs/phase2/README.md(D1 · D2 · D19 · D22 · D33) · weld-motion.md 1~4 · 6 절 · weld-ros-interfaces.md. 3 mm · 45° · 진폭 · 반주기는 설계 출발값',
             y=7.1)
    notes(s, '연휴에는 스캔 결과를 그대로 받아 용접 모션으로 이어 봤습니다. 직육면체의 모서리 여덟 개를 윗면 네 변, 세로 네 모서리 '
             '순서로 따라가는데, 토치처럼 두 면 사이를 이등분하는 방향으로 45 도 기울이고 3 mm 띄워서 닿지 않게 갑니다. 용접처럼 '
             '좌우로 흔드는 위빙은 두산의 주기 운동 명령이 직선 이동과 겹쳐 돌지 않아서, 지그재그 경유점을 만들어 지나가게 했습니다. '
             '여기서도 인터페이스 계약을 먼저 정하고 병렬로 구현했습니다.\n'
             '([뺄 수 있음] 9/29 에 용접이 성사되지 않으면 04-⑨ 두 장을 통째로 뺀다. 다른 장은 이 장을 참조하지 않는다)')


def s_04_weld2(prs, templ):
    s = frame_slide(prs, templ, '04', '지금까지는 Virtual 과 자세 도달성까지 — 실기 결과는 9/29 에 채운다',
                    '* 04-⑨ phase 2 용접 (2/2)  [뺄 수 있음]')
    rows = [['확인', '환경 · 날짜', '결과', '출처'],
            ['45° 자세 도달성 (M1)', '실기 · 9/23', '16 자세 중 12 도달, L1 · L5 는 도달 불가(플랜지 761 · 762 mm). 위치 오차 최대 0.14 mm. 세로 아래 4 자세는 계약 z 보다 17 mm 위에서 확인(계약 z 는 9/29)', 'PR #186'],
            ['8 선 종단', 'Virtual · 9/25', '8 선 모두 DONE, 246 s (sim 가상 박스 100 × 60 × 40 mm)', 'PR #197'],
            ['선 실패 뒤 처리', 'Virtual · 9/25', 'L7 강제 실패 → FAILED 로 기록 → 마무리 복귀 → DONE(success=false)', 'PR #197'],
            ['윗면 1 단계 (L0 → L0~L3)', '실기 · 9/29', '[9/29 채움]', '—'],
            ['8 선 중 DONE', '실기 · 9/29', '[9/29 채움] (기대: 6 선, L1 · L5 는 FAILED)', '—'],
            ['도착 오차 · 무접촉', '실기 · 9/29', '[9/29 채움]', '—']]
    table(s, LEFT, 2.5, WIDTH, [2.6, 1.65, 6.93, 1.15], rows, size=10.5, row_h=0.52,
          fills={4: OR_FILL, 5: OR_FILL, 6: OR_FILL},
          colors={(4, 2): ORANGE, (5, 2): ORANGE, (6, 2): ORANGE})
    bullets(s, LEFT, 6.2, WIDTH, 0.8, [
        '9/29 순서: 실기 스캔 1 회 → Virtual 종단 → 윗면 L0(기울임 0 → 45°) → L0~L3 → 조건부로 세로선 · 위빙. 구현은 PR 진행 중(9/27 기준 main 에 없음)',
    ], size=11, fill=None)
    footnote(s, '출처: docs/phase2/measurements-20260923.md(PR #186, 머지 전) · docs/test-reports/p2-weld-virtual_20260925.md(PR #197, 머지 전) · '
                'docs/phase2/README.md 통합 순서(D27)', y=7.1)
    notes(s, '용접 쪽 결과입니다. 9/23 실기에서 기울인 자세의 도달성을 먼저 쟀는데, 16 자세 중 12 개에 닿았고 L1 · L5 두 선은 로봇 팔 '
             '길이가 모자라 닿지 않았습니다. 그래서 한 선이 실패해도 그 선만 실패로 남기고 다음 선으로 가게 만들었습니다. 에뮬레이터에서는 '
             '여덟 선을 모두 끝까지 돌았고, 실기 결과는 9/29 에 [여기에 채웁니다].\n'
             '(9/29 채움: 윗면 1 단계 성공 여부 · DONE 선 수 · 도착 오차 · 무접촉. 성사되지 않으면 04-⑨ 두 장을 통째로 뺀다)')


# ── 05 자체 평가 ────────────────────────────────────────────────────────
def s_05_team(prs, templ):
    s = frame_slide(prs, templ, '05', '형상 정확도는 목표 안, 탐색 시간과 반복 검증은 목표 밖 — 팀의 자체 평가',
                    '* 05 자체 평가 — 팀')
    rows = [['완성도 (10 점)', '점수', '이유'],
            ['박병후', '[받으면 채움: 병후]', '[받으면 채움: 병후]'],
            ['김학민', '[받으면 채움: 학민]', '[받으면 채움: 학민]'],
            ['남현지', '[받으면 채움: 현지]', '[받으면 채움: 현지]'],
            ['정의석', '[받으면 채움: 의석]', '[받으면 채움: 의석]']]
    table(s, LEFT, 2.7, 6.0, [1.35, 1.75, 2.9], rows, size=10.5, row_h=0.62,
          colors={(r, c): ORANGE for r in range(1, 5) for c in (1, 2)})
    text_box(s, LEFT, 5.95, 6.0, 0.6, [('평균 [받으면 채움] / 10', {'bold': True, 'size': 13, 'color': ORANGE})])
    bullets(s, 6.7, 2.7, 6.13, 4.2, [
        ('잘한 점', {'bold': True, 'color': BLUE, 'size': 12.5, 'after': 2}),
        ('· 계약을 먼저 얼려 네 명이 병렬로 만들었고, 9/23 실기에서 웹 → ROS → 웹이 이어졌다', {'size': 11}),
        ('· 미달 · 미실시까지 수치와 보고서로 남겼다', {'size': 11, 'after': 8}),
        ('아쉬운 점', {'bold': True, 'color': RED, 'size': 12.5, 'after': 2}),
        ('· 탐색 438 s(KPI 120 s) · 검출 하중 2/10 초과 · 반영 지연 312 ms · 설정 등록 버튼 미구현', {'size': 11}),
        ('· 반복성 · 오검출 · 셋업 시간 KPI 와 재시작 실기 시험은 미실시', {'size': 11, 'after': 8}),
        ('개선점', {'bold': True, 'color': BLUE, 'size': 12.5, 'after': 2}),
        ('· 재접근 2 단 · 거친 스텝 1.0 mm 로 약 230 s(계산값 · 미실시)', {'size': 11}),
        ('· 10 회 반복 · 20 회 오검출 시험, 진행 중 스캔에도 감시자 끊김 적용', {'size': 11, 'after': 6}),
        ('(잘한 점 · 아쉬운 점 · 개선점은 초안 — 팀 확인 전)', {'size': 9, 'color': GRAY}),
    ])
    footnote(s, '출처: #180(탐색 시간 · 개선안 계산값) · TR-01_20260923 · TR-05_20260922 · PR #179 · integration-audit_20260921(TR-08 미착수) · '
                'safety-audit D-1')
    notes(s, '팀 자체 평가입니다. 완성도 점수는 각자 준 점수와 이유를 모았습니다 — [받으면 채움]. 잘한 점은 계약을 먼저 정해 네 명이 '
             '동시에 개발하고도 실기에서 끝까지 이어졌다는 것, 그리고 안 된 것까지 숫자로 남겼다는 것입니다. 아쉬운 점은 탐색 시간과 '
             '검출 하중, 반영 지연이 목표에 못 미쳤고, 반복성 같은 몇 가지 KPI 는 재지 못한 것입니다. 개선안은 탐색 시간을 230 초 '
             '정도로 줄이는 계산이 있지만 아직 해 보지 않았습니다.\n'
             '(받으면 채움: 병후 · 학민 · 현지 · 의석의 점수와 이유. 잘한 점 · 아쉬운 점 · 개선점 문장은 사실 기반 초안이라 팀 확인 필요)')


def s_05_personal(prs, templ):
    s = frame_slide(prs, templ, '05', '각자 한 줄 소감과, 운영 · 협업 · 개선 사례 하나씩', '* 05 자체 평가 — 개인')
    rows = [['이름', '한 줄 (느낀 점 · 성과)', '운영', '협업', '개선'],
            ['박병후\n(초안)', '계약을 먼저 고정하니 넷이 따로 만들어도 한 흐름으로 이어졌다. 대신 실측이 바꾼 값을 계약에 되돌리는 일이 끝까지 남았다',
             '계약 동결(9/18) 뒤 변경은 PR + 변경 이력으로만 — v0.1 → v0.1.20',
             'MQTT 계약을 의석과 한 장으로 합의(9/18) — 목업 발행기와 브리지 시험이 같은 예시를 쓴다',
             '감시자 끊김이면 시작 거절(04-⑧, PR #136)'],
            ['김학민', '[받으면 채움: 학민]', '[받으면 채움]', '[받으면 채움]', '[받으면 채움]'],
            ['남현지', '[받으면 채움: 현지]', '[받으면 채움]', '[받으면 채움]', '[받으면 채움]'],
            ['정의석', '[받으면 채움: 의석]', '[받으면 채움]', '[받으면 채움]', '[받으면 채움]']]
    colors = {(r, c): ORANGE for r in range(2, 5) for c in range(1, 5)}
    table(s, LEFT, 2.7, WIDTH, [1.1, 3.9, 2.45, 2.6, 2.28], rows, size=10, row_h=0.8, colors=colors)
    footnote(s, '출처: docs/contracts/CHANGELOG.md · docs/contracts/mqtt-schema.md 상태 줄(T01 1 차 회의 병후 · 의석) · PR #136. '
                '병후 행은 초안(병후 확인), 나머지는 받으면 채움', y=7.1)
    notes(s, '마지막으로 개인 평가입니다. 저는 계약을 먼저 정해 두니 네 명이 따로 만들어도 한 흐름으로 이어진다는 것을 배웠고, 대신 '
             '실기에서 잰 값이 계약을 계속 바꿔서 그것을 되돌리는 일이 끝까지 남았습니다. 운영에서는 계약 변경을 PR 과 변경 이력으로만 '
             '받았고, 협업에서는 의석과 MQTT 계약을 한 장으로 합의했으며, 개선 사례는 앞에서 말씀드린 감시자 끊김 문제입니다. '
             '팀원들의 한 줄은 각자 말씀드리겠습니다 — [받으면 채움].\n'
             '(병후 행은 사실 기반 초안 — 병후 확인. 받으면 채움: 학민 · 현지 · 의석의 한 줄 + 운영 · 협업 · 개선 사례 1 개씩)')


BUILDERS = [s_01_background, s_01_point, s_01_concept, s_01_value, s_02_team, s_03_schedule, s_03_procedure,
            s_03_method, s_04_arch, s_04_sequence, s_04_geometry, s_04_eval, s_04_problem, s_04_weld1, s_04_weld2,
            s_05_team, s_05_personal]


def drop_slides(prs, keep_n):
    ids = list(prs.slides._sldIdLst)
    for sld in ids[keep_n:]:
        prs.part.drop_rel(sld.rId)
        prs.slides._sldIdLst.remove(sld)


def build_main():
    prs = Presentation(str(TEMPLATE))
    templ = list(prs.slides)
    cover_and_toc(prs)
    n_templ = len(templ)
    for build in BUILDERS:
        build(prs, templ)
    ids = list(prs.slides._sldIdLst)
    for sld in ids[2:n_templ]:                 # 양식 안내 · 예시 장(3~10)만 지운다. 표지 · 목차는 남긴다
        prs.part.drop_rel(sld.rId)
        prs.slides._sldIdLst.remove(sld)
    prs.save(str(OUT))
    print('saved', OUT.relative_to(ROOT), len(prs.slides), 'slides')


def build_cover_weld():
    prs = Presentation(str(TEMPLATE))
    notes(prs.slides[0], COVER_NOTE.format(no_weld=TITLE_NO_WELD).replace(
        '안녕하십니까', '[용접 성사 시 표지] 안녕하십니까', 1))
    drop_slides(prs, 1)
    prs.save(str(OUT_COVER_WELD))
    print('saved', OUT_COVER_WELD.relative_to(ROOT), len(prs.slides), 'slide')


if __name__ == '__main__':
    build_main()
    build_cover_weld()
