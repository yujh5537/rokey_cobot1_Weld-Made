"""병후 파트 슬라이드 19 장(표지 · 목차 · 01 · 02 · 03 · 04-① ④ ⑦ ⑧ ⑨ · 05)을 template.pptx 에서 만든다.

    python3 figures.py && python3 build_slides.py      # python-pptx · matplotlib · graphviz 필요

- 현지 build_slides.py 와 같은 방식: 템플릿 장의 틀(배경 · 머리 · 부제 막대 · 오른쪽 위 라벨)만 복사하고 내용은 새로 넣는다.
  섹션마다 그 섹션의 양식 장(01 = 3 장, 02 = 4 장, 03 = 5 장, 04 = 6 장, 05 = 10 장)의 틀을 쓴다. 글꼴 · 색은 바꾸지 않는다.
- 표지 · 목차는 템플릿 1 · 2 장을 그대로 둔다(병후 파일만 가진다). 표지 제목은 용접을 뺀 기본값이다.
  용접이 들어간 표지는 slides-byeonghu-cover-weld.pptx 로 따로 만든다(9/29 용접 성사 시 합치기에서 바꾼다).
- [뺄 수 있음] 블록은 도형 이름에 "[뺄 수 있음]" 을 넣었다(선택 창에서 찾아 지운다). 다른 장은 그 블록을 참조하지 않는다.
- 노트 = 발표 대사(3~5 문장) + 괄호 안에 세부 · 출처 · 합치기 메모. 팀원 입력이 필요한 칸은 "[받으면 채움: 이름]".
- 화면 원칙(병후 9/28): 시각자료와 키워드만. 본문 글자는 13 pt 이상, 세부 내용은 노트(발표자가 구두로)에 둔다.
"""
import copy
import pathlib

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.opc.constants import RELATIONSHIP_TARGET_MODE as RTM
from pptx.opc.package import _Relationship
from pptx.oxml.ns import qn
from pptx.oxml.xmlchemy import OxmlElement
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
NAVY, PALE_BLUE = RGBColor(0x22, 0x35, 0x7F), RGBColor(0xDC, 0xE6, 0xF5)
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
def style_run(run, size, bold, color):
    """맑은 고딕을 라틴 · 한글(ea) 둘 다에 지정한다(한글 글자가 테마 글꼴로 빠지지 않게)."""
    run.font.name = FONT
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    rPr = run._r.get_or_add_rPr()
    if rPr.find(qn('a:ea')) is None:
        ea = OxmlElement('a:ea')
        ea.set('typeface', FONT)
        rPr.find(qn('a:latin')).addnext(ea)


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
        style_run(run, opt.get('size', size), opt.get('bold', False), opt.get('color', color))
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


def chip(slide, x, y, w, h, head, sub=None, fill=LIGHT, edge=None, head_color=NAVY, sub_color=DARK, head_size=18,
         sub_size=13, name=None, align=PP_ALIGN.CENTER):
    """키워드 카드: 굵은 키워드 한 줄 + 짧은 보조 한 줄. 세부는 노트로."""
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    shape.adjustments[0] = 0.12
    if name:
        shape.name = name
    shape.shadow.inherit = False
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    if edge is None:
        shape.line.fill.background()
    else:
        shape.line.color.rgb = edge
        shape.line.width = Pt(1.75)
    tf = shape.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = tf.margin_right = Inches(0.12)
    tf.margin_top = tf.margin_bottom = Inches(0.05)
    items = [(head, head_size, head_color, True)] + ([(ln, sub_size, sub_color, False) for ln in sub.split('\n')]
                                                     if sub else [])
    for i, (text, size, color, bold) in enumerate(items):
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.alignment = align
        run = para.add_run()
        run.text = text
        style_run(run, size, bold, color)
        para.space_after = Pt(2)
    return shape


def picture(slide, path, x, y, w=None, h=None):
    return slide.shapes.add_picture(str(path), Inches(x), Inches(y), Inches(w) if w else None,
                                    Inches(h) if h else None)


def table(slide, x, y, w, col_w, rows, size=10.5, row_h=0.36, header_fill=BLUE, fills=None, colors=None, name=None,
          bold_first_col=True, header_text=WHITE, header_size=None):
    """셀 값은 문자열("\\n" 로 줄바꿈) 또는 [(글, 색), …] — 줄마다 색을 따로 준다(○ △ × 표시용)."""
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
            cell.margin_left = cell.margin_right = Inches(0.08)
            cell.margin_top = cell.margin_bottom = Inches(0.03)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.fill.solid()
            fill = header_fill if r == 0 else (fills or {}).get(r, LIGHT if r % 2 == 0 else WHITE)
            cell.fill.fore_color.rgb = fill
            tf = cell.text_frame
            tf.word_wrap = True
            base = header_text if r == 0 else (colors or {}).get((r, c), DARK)
            parts = [(p, base) for p in value.split('\n')] if isinstance(value, str) else value
            for k, (part, color) in enumerate(parts):
                para = tf.paragraphs[0] if k == 0 else tf.add_paragraph()
                run = para.add_run()
                run.text = part
                style_run(run, header_size if (r == 0 and header_size) else size, r == 0 or (bold_first_col and c == 0),
                          color)
    return shape


def footnote(slide, text, y=7.05):
    text_box(slide, LEFT, y, WIDTH, 0.3, [(text, {'size': 9.5, 'color': GRAY})], name='출처 각주')


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
    rows = [['비용이 드는 곳', '핵심', '근거'],
            ['재티칭 · 비가동', '교체마다 교시 + 셀 정지', '가정'],
            ['교육', '조작 익히는 데 2~3 일', 'E16'],
            ['불량 · 재작업', '편차 → 경로 어긋남', '가정'],
            ['납기 지연', '담당자 없으면 교체 지연', 'E3']]
    table(s, LEFT, 2.5, 7.0, [2.1, 3.7, 1.2], rows, size=15, row_h=0.84, header_size=15)
    chip(s, 7.85, 2.5, 2.4, 1.75, '68.2 %', '뿌리산업 종사자\n40 대 이상', fill=LIGHT, head_color=BLUE, head_size=34,
         sub_size=13)
    chip(s, 10.43, 2.5, 2.4, 1.75, '89.3 %', '10 인 미만 업체\n인력 부족', fill=LIGHT, head_color=BLUE, head_size=34,
         sub_size=13)
    chip(s, 7.85, 4.45, 4.98, 2.2, '놓고 → 누르면 → 로봇이 찾는다', '교시 없이 · 센서 추가 없이', fill=PALE_BLUE, edge=BLUE,
         head_color=NAVY, head_size=21, sub_size=15, name='기획 의도')
    footnote(s, '출처: BRD v3.2.0 1.1 · 3.1 · 3.3(US-01). E2 · E3 · E13 · E16 = BRD 11 장 근거 자료, "가정" = BRD 1.6 의 팀 가정값(A2~A6)')
    notes(s, '주제의 출발점은 직접교시입니다. 협동로봇 용접은 작업자가 로봇 끝을 잡고 점을 하나씩 기록하는데, 품종이 바뀌면 이 일을 '
             '다시 해야 합니다. 왼쪽 표처럼 그 시간 동안 셀이 멈추고, 교육과 불량 · 납기에도 비용이 듭니다. 그런데 이 일을 맡을 사람이 '
             '부족합니다 — 뿌리산업 종사자의 68.2 % 가 40 대 이상이고, 10 인 미만 업체의 89.3 % 가 인력 부족을 호소합니다. 그래서 '
             '"부재를 놓고 시작만 누르면 로봇이 직접 만져서 좌표를 얻는다"를 목표로 잡았습니다.\n'
             '(세부: 가설은 "다품종 소량 중소 제조사에서 품종 교체 시 재티칭이 가장 큰 운영 비용"이다. 셋업을 15~30 분에 바꾼다는 '
             '업계 주장도 있어 1 회 티칭 시간은 사실로 단정하지 않고 가정값으로 둔다(E13). 업체당 평균 종사자 2.8 명(E3). 출처: BRD 1.1 · 3.1)')


def s_01_point(prs, templ):
    s = frame_slide(prs, templ, '01', '센서를 더하지 않고 로봇이 만져서 찾는다 — 그 과정을 실시간 3D 로 보여준다',
                    '* 01-② 특화 포인트')
    picture(s, HERE / 'compare-alternatives.png', LEFT, 2.45, w=8.3)
    chip(s, 8.95, 2.5, 3.88, 1.3, '무센서 탐침 = 촉각', '로봇 관절 토크로 추정한 외력', fill=PALE_BLUE, edge=BLUE)
    chip(s, 8.95, 3.95, 3.88, 1.3, '실시간 3D 관제', '단계 · 접촉점 · 형상을 바로', fill=PALE_BLUE, edge=BLUE)
    chip(s, 8.95, 5.4, 3.88, 1.3, '스캔 → 용접 모션', '[뺄 수 있음]', fill=OR_FILL, edge=ORANGE, head_color=ORANGE,
         sub_color=ORANGE, name='[뺄 수 있음] 01-② 용접')
    footnote(s, '출처: BRD v3.2.0 3.2(대안 비교 · 가격) · 1.5(기술적 가치), ADR 0001. 비전 가격은 E12. 목표가 1,000 만원은 가정 A7')
    notes(s, '비슷한 문제를 푸는 방법을 나란히 놓았습니다. 지금의 재티칭은 매번 사람이 필요하고, 와이어 터치센싱은 감지 기능이 있는 용접 '
             '전원과 통전되는 깨끗한 모서리가 필요하며, 레이저나 3D 비전은 비싸고 반사나 아크광에 약합니다. 저희는 센서를 더하지 '
             '않고 로봇 관절 토크로 추정한 외력을 촉각으로, 그리퍼는 탐침을 쥐는 손가락으로 씁니다. 그리고 그 과정을 웹 3D 화면에 '
             '실시간으로 보여줍니다. [뺄 수 있음 카드] 같은 결과로 모서리를 용접 자세로 따라가는 것까지 이어 봤습니다.\n'
             '(세부: 우리 약점은 탐색 시간과 단순 형상 · 규칙 배치(MVP)다. 와이어 터치센싱의 가격은 "저가 SW 옵션, 금액 미확인"(E5), '
             '비전은 1만~5만 달러 이상(E12). ○ △ × 는 BRD 3.2 표의 문장을 기호로 옮긴 것이다. '
             '[합치기 체크] 용접을 빼면 주황 카드 "[뺄 수 있음] 01-② 용접" 만 지운다)')


def s_01_concept(prs, templ):
    s = frame_slide(prs, templ, '01', 'MVP: 직육면체 하나를 다섯 번 만져 형상과 경로 후보를 만들고 웹에 보여준다',
                    '* 01-③ 구현 내용 · 컨셉 · 훈련 연관')
    picture(s, HERE / 'overview-mvp-flow.png', LEFT, 2.45, w=7.6)
    text_box(s, 8.35, 2.42, 4.48, 0.45, [('훈련 연관', {'bold': True, 'color': BLUE, 'size': 16})])
    tiles = [('ROS 2 노드 5 개', '토픽 · 서비스 · 액션 계약'), ('두산 DSR 서비스', 'robot_manager 한 곳에서 호출'),
             ('launch · 파라미터', 'sim ↔ 실기를 인자 하나로'), ('HMI', 'React 3D · MQTT · FastAPI')]
    for i, (head, sub) in enumerate(tiles):
        chip(s, 8.35, 2.95 + i * 1.0, 4.48, 0.88, head, sub, head_size=17, sub_size=13)
    footnote(s, '출처: BRD v3.2.0 2 장 포함 범위 · 1.4 절(탐색 절차) · docs/architecture.md · 산출물 01 시스템 아키텍처')
    notes(s, 'MVP 범위는 한 장으로 이렇습니다. 작업대에 놓인 직육면체를 로봇이 위에서 한 번, 네 방향 옆으로 한 번씩, 모두 다섯 번 '
             '만집니다. 이 다섯 점을 탐침 크기만큼 보정해서 직육면체와 윗면의 외곽 엣지, 즉 경로 후보 네 개를 만들고, 그 과정을 웹 '
             '3D 화면에 보여줍니다. 오른쪽은 수업에서 배운 것과의 연결입니다 — ROS 2 노드와 통신, 두산 DSR 서비스, launch 와 '
             '파라미터, 그리고 HMI 입니다.\n'
             '(세부: 노드 5 개 = scan_manager · robot_manager · contact_detector · safety_monitor · mqtt_bridge. 입력원 전환은 '
             'launch 인자 source:=sim | robot_force. 웹은 React + Three.js 3D · FastAPI · Spring Boot · PostgreSQL · Mosquitto. '
             '경로 후보는 용접 이음 판정이 아니다. 출처: BRD 2 장 · architecture.md)')


def s_01_value(prs, templ):
    s = frame_slide(prs, templ, '01', '품종 교체 1 회의 사람 시간을 1 시간에서 0.1 시간으로 — 수치는 BRD 가정이다',
                    '* 01-⑤ 활용방안 · 기대효과')
    picture(s, HERE / 'value-compare.png', LEFT, 2.45, w=WIDTH)
    footnote(s, '출처: BRD v3.2.0 1.6(가정 A2 · A3 · A4 · 시나리오) · 1.3 · 2 장. 로봇 탐색 7.3 분 = 9/23 실기 438 s(#180, KPI 120 s 미달). '
                '치수 = 캘리퍼 대비(#180)')
    notes(s, '기대효과를 지금의 직접교시와 나란히 놓았습니다. 품종을 바꿀 때 사람이 쓰는 시간이 한 시간 안팎에서 배치와 시작 · 확인 '
             '0.1 시간으로 줄고, 하루 두 번 교체하는 현장이면 1 년에 500 시간이 50 시간이 됩니다. 정확도는 교시하는 사람의 숙련도가 '
             '아니라 목표 ±3 mm 로 관리되고, 9/23 실기에서 그 안에 들어왔습니다. 다만 이 숫자들은 BRD 의 가정이고, 지금 MVP 는 '
             '원리를 보여 주는 단계라 이 절감을 바로 만들지는 않습니다.\n'
             '(세부: 기본 시나리오 = 교체 일 2 회 · 250 일 · 1 회 티칭 1.0 h · 사람 개입 0.1 h · 인건비 35,000 원 → 연 절감 1,775 만원, '
             '도입비 1,000 만원(가정) 회수 약 7.2 개월. 보수적 시나리오(일 1 회 · 0.5 h)는 회수 약 6.7 년이라 목표 고객이 아니다 → '
             '목표 고객 = 교체 하루 2 회 이상 또는 1 회 티칭 1 시간 안팎인 임가공 · 제관 업체. 로봇 탐색 7.3 분은 스텝 모드 실측이며 '
             'KPI 2 분은 미달(현지 04-⑥). MVP 이후: 비스듬한 배치 · 곡면 · ±1 mm · 마커로 경로 따라 긋기. 출처: BRD 1.5 · 1.6 · 2 장)')


# ── 02 팀 ──────────────────────────────────────────────────────────────
TEAM = [
    ('박병후', '팀장 · 스캔 흐름 · 계약', NAVY,
     ['scan_manager', 'result_store', 'contact_scan_interfaces'],
     '스캔 순서 상태기계\n중지 · 안전복귀 · 재시작\n결과 기록 · 설정 전파', '01 · 05 · 06 · BRD'),
    ('김학민', '로봇 제어 · 좌표 기준', RGBColor(0x2E, 0x8B, 0x7A),
     ['robot_manager'],
     '모션 · 힘/순응 제어\n샘플 발행\nTCP · 홈 · 작업대 원점', '04 · 08 · 09'),
    ('남현지', '판정 · 안전 · 통합', RGBColor(0xB8, 0x86, 0x0B),
     ['contact_detector', 'safety_monitor', 'geometry_estimator', 'bringup'],
     '접촉 · 모서리 판정\n두 겹 안전 감시\n형상 계산 · 통합 빌드', '02 (메인 PC) · 03'),
    ('정의석', '관제 화면 · 연동', RGBColor(0xA0, 0x51, 0x95),
     ['mqtt_bridge', 'FastAPI · Spring', 'React 3D'],
     'ROS ↔ MQTT\n3D 관제 · 명령\n저장 · 조회', '02 (웹 PC) · 07'),
]


def s_02_team(prs, templ):
    s = frame_slide(prs, templ, '02', '네 명이 노드를 나눠 맡고, 계약 문서로 경계를 정했다', '* 02 팀 구성 및 역할')
    w, gap = 2.94, 0.19
    for i, (name, role, col, pkgs, work, deliv) in enumerate(TEAM):
        x = LEFT + i * (w + gap)
        chip(s, x, 2.45, w, 0.95, name, role, fill=col, head_color=WHITE, sub_color=WHITE, head_size=21, sub_size=13)
        text_box(s, x, 3.48, w, 1.25, [(p, {'bold': True, 'size': 14, 'color': col, 'after': 1,
                                             'align': PP_ALIGN.CENTER}) for p in pkgs], fill=LIGHT)
        text_box(s, x, 4.8, w, 1.2, [(ln, {'size': 13, 'after': 1, 'align': PP_ALIGN.CENTER})
                                     for ln in work.split('\n')])
        text_box(s, x, 5.95, w, 0.35, [(f'산출물 {deliv}', {'size': 13, 'color': GRAY, 'align': PP_ALIGN.CENTER})])
    chip(s, LEFT, 6.4, WIDTH, 0.55, '멘토 이일주 — 주제 선정 피드백 · 질의응답 · 중간 점검', None, fill=LIGHT, head_size=15)
    footnote(s, '출처: ws_cobot1/src/README.md 담당 표 · docs/deliverables/README.md 2 · 3 절 · docs/presentation/outline-v1.md')
    notes(s, '팀은 네 명이고, ROS 노드를 나눠 맡았습니다. 저는 스캔 전체 순서를 쥐는 scan_manager 를 맡아 윗면 · 모서리 탐색 순서와 '
             '중지 · 안전복귀 · 재시작, 결과 기록을 만들었고, 노드 사이의 약속인 인터페이스 패키지와 계약 문서를 맡았습니다. 학민은 '
             '로봇을 움직이는 robot_manager 와 좌표 기준을, 현지는 접촉 판정과 안전 감시와 통합을, 의석은 관제 화면과 브리지를 '
             '맡았습니다. 네 명이 동시에 개발하려고 노드 사이의 이름과 형식을 계약 문서로 먼저 정했습니다.\n'
             '(팀원 확인 전: 역할 · 하는 일 문구는 담당 표로 채웠다. 받으면 채움: 학민 · 현지 · 의석의 담당 한 줄. '
             '산출물 번호: 01 아키텍처 · 02 네트워크 · 03 순서도 · 04 하드웨어 · 05 인터페이스 · 06 노드 구조도 · 07 HMI · 08 예외 · '
             '09 안전, 그 밖에 소스 zip(현지) · Readme · 영상(의석 · 현지) · 발표자료(병후))')


# ── 03 절차 · 방법 ─────────────────────────────────────────────────────
def s_03_schedule(prs, templ):
    s = frame_slide(prs, templ, '03', '계약을 먼저 동결하고, 모듈 → 통합 → 실기를 엿새 안에 끝냈다 (9/18 ~ 9/23)',
                    '* 03 수행 절차 · 일정')
    rows = [['단계', '기간', '한 일', '결과물'],
            ['기획', '9/14 ~ 9/17', '주제 · 요구사항 · 설계 초안', 'BRD · 설계 문서'],
            ['계약 동결', '9/18', '토픽 · 서비스 · MQTT · 좌표 규칙', '계약 v0.1'],
            ['모듈 개발', '9/19 ~ 9/20', '노드별 병렬 구현 · sim', '노드 5 + 웹'],
            ['통합 · 실기', '9/21 ~ 9/23', 'sim → 에뮬레이터 → 실기', '실기 종단 3 회 연속'],
            ['[뺄 수 있음] phase 2', '9/24 ~ 9/29', '스캔 결과로 용접 모션', 'docs/phase2'],
            ['발표', '9/30', '결과 보고 · 평가', '발표 · 영상 · 소스']]
    table(s, LEFT, 2.5, WIDTH, [2.6, 1.9, 4.4, 3.43], rows, size=15, row_h=0.62, header_size=15, fills={5: OR_FILL},
          colors={(5, 0): ORANGE, (5, 1): ORANGE, (5, 2): ORANGE, (5, 3): ORANGE})
    footnote(s, '출처: outline-v1.md · conventions.md(9/21 기능 동결) · PR #179(튜닝) · 9/23 시연 영상(팀원 4 명 입회). '
                '주황 행은 [뺄 수 있음] — 행만 지운다')
    notes(s, '일정은 여섯 단계였습니다. 나흘 동안 요구사항과 설계를 정리하고, 9/18 에 노드 사이의 약속을 계약 문서로 동결했습니다. '
             '그 뒤 이틀 동안 각자 모듈을 만들고, 9/21 부터 사흘 동안 통합과 실기를 해서 9/23 에 실기에서 웹까지 이어지는 종단 '
             '실행을 세 번 연속 성공했습니다. [뺄 수 있음 행] 연휴에는 그 결과로 용접 모션을 이어 붙였습니다. 발표는 오늘입니다.\n'
             '(세부: 9/21 저녁 기능 동결 뒤에는 버그 수정만 머지했다. 3 회 연속 = 9/23 실기 시연에서 1 회 약 7 분 종단을 팀원 4 명 '
             '입회 하에 세 번 연속 성공, 동영상 촬영(슬랙 채널). 그 전 파라미터 튜닝은 PR #179. '
             '[합치기 체크] 용접을 빼면 주황 행만 지운다)')


def s_03_procedure(prs, templ):
    s = frame_slide(prs, templ, '03', '요구 → 계약 → 병렬 개발 → sim → 에뮬레이터 → 실기 → 시험 보고 순서로 검증했다',
                    '* 03 수행 절차 · 도식')
    picture(s, HERE / 'method-procedure.png', LEFT, 2.5, w=WIDTH)
    chips = [('계약 = 코드보다 우선', '바뀌면 문서 · 패키지를 함께'), ('source:=sim', '인자 하나로 로봇 없이'),
             ('실측 → yaml', '실기 PC 에만 남은 값은 없는 값')]
    for i, (head, sub) in enumerate(chips):
        chip(s, LEFT + i * 4.18, 5.35, 3.97, 1.3, head, sub, fill=PALE_BLUE, edge=BLUE, head_size=19, sub_size=14)
    footnote(s, '출처: docs/conventions.md · docs/contracts/CHANGELOG.md(v0.1.1 ~ v0.1.20, 9/18~9/23 의 19 항목) · '
                'contact_scan_interfaces test_contract_sync. 9/23 main 머지 기준')
    notes(s, '진행 순서는 이 그림과 같습니다. 요구사항에서 계약을 만들고, 계약을 기준으로 네 명이 병렬로 개발했습니다. 검증은 로봇 '
             '없이 가상 접촉을 만드는 sim, 두산 에뮬레이터, 그리고 실기 순서로 올라갔고, 결과는 시험 보고서로 남겼습니다. 실기에서 '
             '잰 값은 파라미터 파일과 계약 개정으로만 되돌렸는데, 9/18 에 동결한 계약을 9/23 실기까지 열아홉 번 고쳐 main 에 넣었습니다.\n'
             '(세부: 계약이 코드보다 우선이라 이름 · 필드 · 단위가 바뀌면 계약 문서 · 인터페이스 패키지 · 변경 이력을 한 PR 에서 '
             '같이 고치고, 둘이 어긋나면 동기화 시험이 CI 에서 실패한다. 입력원은 launch 인자 source:=sim | robot_force 하나로 바꾼다. '
             'CHANGELOG 는 v0.1.1 ~ v0.1.20 의 19 항목(v0.1.17 은 번호만 비어 있다). v0.1.21 도 9/23 날짜로 적혔지만 main 머지는 9/27 이라 세지 않았다)')


def s_03_method(prs, templ):
    s = frame_slide(prs, templ, '03', '작게 나눠 리뷰받고, 수치는 파라미터로 두고, 결과는 보고서로 남겼다',
                    '* 03 수행 방법  [뺄 수 있음]')
    chip(s, LEFT, 2.45, WIDTH, 0.72, '[뺄 수 있음]  발표 시간이 모자라면 이 장을 통째로 뺀다', None, fill=ORANGE,
         head_color=WHITE, head_size=22, name='[뺄 수 있음] 03 방법 배너')
    tiles = [('작업 1 = PR 1', '작게 나눠 리뷰'), ('코드 오너 승인', '계약 · 공용 파일'), ('3 단계 검증', 'sim → Virtual → 실기'),
             ('수치 = 파라미터', '코드에 박지 않는다'), ('실측 분리', '출발값 · 실측 · 계산'), ('시험 보고', '실패 · 미달도 기록')]
    w, h = 3.97, 1.55
    for i, (head, sub) in enumerate(tiles):
        x = LEFT + (i % 3) * (w + 0.21)
        y = 3.35 + (i // 3) * (h + 0.15)
        chip(s, x, y, w, h, head, sub, head_size=21, sub_size=15)
    footnote(s, '출처: docs/conventions.md · docs/test-reports/README.md · docs/contracts/units-frames.md')
    notes(s, '[이 장은 뺄 수 있음 — 15 분 발표면 ⑨ 다음으로 뺀다] 개발 규칙은 여섯 가지였습니다. 작업 하나를 PR 하나로 작게 나눴고, '
             '계약처럼 모두가 쓰는 파일은 코드 오너의 승인을 받아야 들어가게 했습니다. 속도나 힘 같은 숫자는 코드에 박지 않고 설정 '
             '파일에 두었고, 설계에서 잡은 값과 실제로 잰 값을 문서에서 섞지 않았습니다. 결과는 실패와 미달까지 보고서로 남겼습니다.\n'
             '(세부: 변경 파일 15 개를 넘으면 쪼갠다 · main 직접 푸시 금지 · 다른 사람 패키지는 소유자 리뷰 · yaml 은 sim · real 분리 · '
             '미측정은 0 이 아니라 NaN · null · 시험 번호(TR)별 보고서 + 저녁 통합 기록(daily). 도구 이름 · 이슈 · PR 개수는 넣지 않았다)')


# ── 04 수행 경과 ────────────────────────────────────────────────────────
def s_04_arch(prs, templ):
    s = frame_slide(prs, templ, '04', '두 PC 와 로봇 — 접촉 판정과 정지는 메인 PC 안에서 끝난다', '* 04-① 시스템 아키텍처')
    pic = picture(s, HERE / 'arch-simple.png', LEFT, 2.45, w=WIDTH)
    pic.name = '[뺄 수 있음] 04-① 그림(용접 포함) — 빼면 arch-simple-no-phase2.png'
    footnote(s, '출처: 산출물 01 시스템 아키텍처 v1.7(상세 그림) · 06 ROS2 노드 구조도 v1.2(선 하나하나) · docs/contracts/ros-interfaces.md 2 장')
    notes(s, '전체 구성입니다. 왼쪽 웹 PC 에는 관제 화면과 웹 서버, MQTT 브로커가 있고, 가운데 메인 PC 에서 ROS 2 노드 다섯 개가 '
             '돕니다. 스캔 순서는 scan_manager 가, 접촉 판정은 contact_detector 가, 로봇 호출은 robot_manager 한 곳이 맡고, 로봇 '
             '컨트롤러와는 robot_manager 만 명령을 주고받습니다. 핵심은 빨간 화살표입니다 — 안전 감시와 정지는 웹을 거치지 않고 메인 '
             'PC 안에서 끝나서, 웹이 끊겨도 로봇은 멈출 수 있습니다. 주황 점선은 연휴에 더한 용접 부분으로, 구현은 아직 진행 중입니다.\n'
             '(세부: 웹 PC 는 Docker 4 서비스 — Mosquitto :1883 · PostgreSQL :5432 · FastAPI :8000 · Spring Boot :8080, React 는 '
             'Docker 밖. 토픽 · 서비스 · 액션 이름은 산출물 06. 화면 버튼은 5 개이고 설정 등록 버튼은 아직 없다. safety_monitor 의 웹 '
             'heartbeat 감시는 계약에만 있고 미구현이다. [합치기 체크] 용접을 빼면 그림을 assets/byeonghu/arch-simple-no-phase2.png 로 '
             '바꾸고 마지막 문장을 뺀다)')


def s_04_sequence(prs, templ):
    s = frame_slide(prs, templ, '04', '스캔 순서는 상태기계 하나가 쥐고, 중지 · 재시작 · 안전복귀는 서로 부르지 않는다',
                    '* 04-④ 탐색 시퀀스 · 형상 (1/2)')
    picture(s, HERE / 'scan-flow.png', LEFT, 2.45, w=WIDTH)
    footnote(s, '출처: ws_cobot1/src/scan_manager/README.md(시퀀스 · 전이표 · 재시작 · 안전복귀) · docs/contracts/ros-interfaces.md 7.1 · 7.3 · 7.5 · 9 장(v0.1.21)')
    notes(s, '제가 맡은 scan_manager 입니다. 위 줄이 정상 흐름입니다 — 준비, 윗면에 내려서 닿기, 네 방향으로 밀어서 모서리 찾기, 형상 '
             '계산, 들어 올려 홈 복귀. 모서리를 바꿀 때는 들어 올리고 원점 위로 가서 다시 닿은 뒤 밉니다. 아래 줄은 관제자 명령입니다. '
             '중지는 멈추고 기록만 남기고, 재시작은 확정된 값은 두고 멈춘 단계부터 잇고, 안전복귀는 위치를 확인하고 수직으로 올린 뒤 '
             '홈으로 갑니다. 셋은 서로를 부르지 않고, 실패하면 그 자리에서 멈출 뿐 자동으로 홈에 가지 않습니다.\n'
             '(세부: 상태 이름 = PREPARING → TOP_SEARCH → EDGE_SEARCH ×4 → GEOMETRY → HOMING → DONE, 중지 = STOPPING → STOPPED, '
             '실패 = ERROR. 재시작은 기록(progress.json)만 보고 잇는다 — 중지한 뒤 프로세스를 다시 띄워도 같은 자리에서(sim 시험, 실기 미실시). '
             '스캔 도중 프로세스가 죽으면 멈춘 자리를 몰라 잇지 않는다(NO_RESUMABLE_SCAN). 오류 뒤 재시작은 v0.1.21 부터 SAMPLE_STALE 403 · ROBOT_STATUS_LOST 404 · STOP_UNCONFIRMED 407 만, '
             '/safety/reset 뒤에 받는다. 안전복귀는 손상 의심(400 · 205 · 402)이나 위치 불명이면 멈추고 사람이 조그한다. 출처: README · 계약)')


def s_04_geometry(prs, templ):
    s = frame_slide(prs, templ, '04', '판정 좌표는 모서리를 지난 뒤에 찍힌다 — 팁 기하만큼 되돌려 직육면체를 만든다',
                    '* 04-④ 탐색 시퀀스 · 형상 (2/2)')
    picture(s, HERE / 'scan-geometry-bias.png', LEFT, 2.45, w=8.2)
    rows = [['9/23 실기', '값', '구분'],
            ['하강량 δ', '0.46~0.52 mm', '실측'],
            ['보정량 d', '1.27~1.34 mm', '계산'],
            ['크기', '83.0 × 80.6\n× 80.8 mm', '실측'],
            ['캘리퍼 대비', '+1.50 / −0.36\n/ +0.26 mm', '±3 mm 안'],
            ['10 회 반복', '미실시', 'KPI']]
    table(s, 8.9, 2.5, 3.93, [1.4, 1.63, 0.9], rows, size=13, row_h=0.72, header_size=13,
          colors={(4, 2): BLUE, (5, 1): RED, (5, 2): RED})
    footnote(s, '출처: 9/23 실기 scan 20260923-183211-3702 result.json(docs/phase2/fixtures) · 캘리퍼 대비는 #180 학민 코멘트(9/23) · '
                '식은 geometry_estimator README')
    notes(s, '두 번째 장은 다섯 점으로 형상을 만드는 방법입니다. 오른쪽 그림처럼 탐침이 모서리를 넘어가 팁이 살짝 내려앉는 순간을 '
             '"모서리"로 판정하기 때문에, 그때 팁 중심은 실제 모서리보다 d 만큼 바깥에 있습니다. 그래서 팁 반지름과 내려앉은 깊이로 '
             '그 거리를 계산해 되돌립니다 — 9/23 실기에서는 방향마다 1.3 mm 안팎이었습니다. 보정한 결과는 캘리퍼 대비 폭 +1.50, '
             '길이 −0.36, 높이 +0.26 mm 로 목표 ±3 mm 안이었습니다. 다만 한 번 잰 값이고, 10 회 반복성은 아직 재지 않았습니다.\n'
             '(세부: 보정 입력 = 팁 반지름 r 2 mm · 판정 지연 t 0 · 모서리 둥글림 R 0(설정값). 정확한 크기 83.00 × 80.64 × 80.76 mm. '
             '왼쪽 그림은 보정 전 · 뒤 간격을 4 배로 벌려 그렸다. 보정된 윗면 사각형의 네 변이 경로 후보이고 용접 이음을 판정한 것은 '
             '아니다. 출처: result.json 3702 의 bias_corrections · #180)')


def s_04_eval(prs, templ):
    s = frame_slide(prs, templ, '04', '평가 다섯 항목마다 증거를 붙였다 — 미달 · 미실시도 같은 표에 둔다',
                    '* 04-⑦ 평가 항목 대응표')
    G, R, A = RGBColor(0x2E, 0x8B, 0x57), RED, RGBColor(0xB8, 0x86, 0x0B)
    rows = [['평가 항목', '우리가 한 것   (○ 됨 · △ 일부 · × 미달)', '증거'],
            ['완전성', [('○ 교시 없이 5 점 → 형상 → 웹 3D, 실기 종단', G), ('× 탐색 438 s(KPI 120 s) · 설정 버튼 없음', R)],
             '04-⑥ · PR #179'],
            ['정확성', [('○ 치수 ±3 mm 안 (1 회)', G), ('× 검출 하중 2/10 이 5 N 초과', R)], '04-⑥ · TR-01'],
            ['안정성', [('○ 실기 종단 3 회 연속 · 두 겹 감시 · 래치', G), ('× 관제 반영 지연 최대 312 ms', R)], '영상 · 04-③ · TR-05'],
            ['입출력', [('○ 계약 한 벌 · 미측정 = NaN / null', G), ('○ 저장 → 조회 일치 (sim)', G)], '산출물 05 · TR-10'],
            ['지속성', [('○ 중지 · 복귀 · 재시작 독립', G), ('△ 재시작은 sim · 시험만, 실기 미실시', A)], '04-④ · 04-⑧']]
    table(s, LEFT, 2.42, WIDTH, [1.75, 7.8, 2.78], rows, size=14, row_h=0.69, header_size=14)
    table(s, LEFT, 6.6, WIDTH, [1.75, 7.8, 2.78],
          [['[뺄 수 있음] 용접', '○ 실기 8 선 중 6 선 완주 (9/29) · Virtual 8 / 8   △ 띄움 거리 치우침', '04-⑨ · 9/29 기록']],
          size=13, row_h=0.4, header_fill=OR_FILL, header_text=ORANGE, name='[뺄 수 있음] 04-⑦ 용접 행')
    footnote(s, '출처: TR-01(9/23) · TR-05 · TR-10(9/22 sim) · #180 · 9/23 시연 영상(3 회 연속 · 팀원 입회). '
                '438 s = #180 학민 실측(본문 합계 435 s)')
    notes(s, '평가 기준 다섯 항목에 저희가 한 것과 증거를 붙였습니다. 동그라미는 된 것, 가위표는 목표에 못 미친 것입니다. 기능은 교시 '
             '없이 형상까지 나오고, 9/23 실기에서는 약 7 분짜리 종단을 세 번 연속 성공했습니다. 치수도 목표 안이지만, 탐색 시간은 438 초로 목표의 3.6 배이고 설정 등록 버튼은 아직 화면에 없습니다. '
             '검출 하중은 평균만 보면 통과지만 열 번 중 두 번이 5 N 을 넘어 미달로 적었고, 관제 반영 지연도 최대 312 ms 로 '
             '미달입니다. 재시작은 sim 과 시험으로만 확인했습니다. 9/29 같은 배치에서 스캔을 다시 했을 때는 세 번 모두 한 방향에서 '
             '실패해 원인을 찾고 있습니다.\n'
             '(세부: 검출 하중 평균 4.49 N · 2/10 초과(5.15 · 5.29 N), 중지 반응 706 · 600 ms 는 sim 측정(TR-05), 반영 지연 312 ms '
             'FAIL, 저장 · 조회 일치는 TR-10 sim. 3 회 연속 = 9/23 실기 시연, 팀원 4 명 입회 · 동영상 촬영(GitHub 에는 기록 없음, 튜닝은 PR #179). 438 s 는 '
             '#180 학민 코멘트의 실측(이슈 본문 구간 합계는 435 s). [합치기 체크] 용접을 빼면 주황 표 "[뺄 수 있음] '
             '04-⑦ 용접 행"만 지운다)')


def s_04_problem(prs, templ):
    s = frame_slide(prs, templ, '04', '감시자가 죽은 걸 아무도 몰랐다 → 상태의 "나이"로 스캔 시작을 막았다',
                    '* 04-⑧ 문제와 해결 (병후)')
    picture(s, HERE / 'problem-before-after.png', LEFT, 2.45, w=WIDTH)
    chip(s, LEFT, 6.1, 6.05, 0.82, '교훈: 값과 함께 나이를 본다', None, fill=PALE_BLUE, edge=BLUE, head_size=19)
    chip(s, LEFT + 6.28, 6.1, 6.05, 0.82, '남은 것: 실기 미확인 · 진행 중 스캔은 계속', None, fill=LIGHT, head_color=RED,
         head_size=16)
    footnote(s, '출처: PR #136 · #103 · #120 · realrobot-session_20260921 · safety-audit-review_20260922 D-1 · docs/phase1/scan_manager.md 5.1')
    notes(s, '제가 고친 문제 하나입니다. 9/21 실기에서 안전 감시 노드가 두 번 죽었는데, 두 번째 뒤로 하강 다섯 번과 밀기 두 번이 '
             '2차 감시 없이 돌았고 한 시간 넘게 아무도 몰랐습니다. 원인은 scan_manager 가 죽기 직전에 받은 "래치 없음"이라는 마지막 '
             '값을 계속 믿은 것입니다. 그래서 상태 메시지의 시각으로 나이를 재서, 한도보다 오래됐으면 시작과 재시작을 거절하게 '
             '했습니다. sim 에서 감시자를 죽이면 5.5 초가 한도 5 초를 넘어 거절되고, 누르기 전에 경고가 먼저 뜹니다. 다만 실기에서 '
             '다시 확인하지 못했고, 이미 돌고 있는 스캔은 멈추지 않는다는 한계가 남아 있습니다.\n'
             '(세부: 종료 시각 10:34:33 · 11:51:45(#103). "한 번도 못 받음"만 거절하고 "받다가 끊김"은 통과시키던 것이 원인. 조치 PR #136 '
             '(9/21 머지): /safety/status 끊김 → SAFETY_LATCHED 103, /robot/status 끊김 → ROBOT_DISCONNECTED 104, 한도 '
             'safety_status_timeout_s 5.0 · robot_status_timeout_s 2.0(설계 출발값), 안전복귀는 막지 않음, 끊김 · 회복을 /scan/log 에 '
             '한 번씩. 결과: 거절 298.25 s 보다 WARN 297.87 s 가 먼저, 시험 1101 → 1124 · 실패 0(5 회 실행). 9/22 안전 감사는 '
             '"부분 해결". 현지 04-③ 2 장 "감시자도 죽는다"(#117, 죽은 원인)와 짝 — 현지는 "죽었다", 병후는 "몰랐다")')


def s_04_weld1(prs, templ):
    s = frame_slide(prs, templ, '04', '스캔 결과만으로 모서리 8 선을 용접 자세로 따라간다 — 닿지 않고 띄워서',
                    '* 04-⑨ phase 2 용접 (1/2)  [뺄 수 있음]')
    picture(s, HERE / 'weld-pose-weave.png', LEFT, 2.5, w=7.6)
    tiles = [('계약 먼저', 'v0.2.0 · 1차 계약은 그대로'), ('45° · 3 mm 띄움', '힘 · 순응 제어 없음'),
             ('지그재그 경유점', '위빙 = 점마다 멈추며'), ('실패 선만 FAILED', '나머지는 계속')]
    for i, (head, sub) in enumerate(tiles):
        chip(s, 8.3, 2.5 + i * 1.06, 4.53, 0.94, head, sub, fill=OR_FILL, edge=ORANGE, head_color=ORANGE, head_size=18,
             sub_size=13)
    footnote(s, '출처: docs/phase2/README.md(D1 · D2 · D19 · D22 · D33) · weld-motion.md 1~4 · 6 절 · weld-ros-interfaces.md. '
                '3 mm · 45° · 진폭 2 mm · 반주기 4 mm 는 설계 출발값')
    notes(s, '연휴에는 스캔 결과를 그대로 받아 용접 모션으로 이어 봤습니다. 직육면체의 모서리 여덟 개를 윗면 네 변, 세로 네 모서리 '
             '순서로 따라가는데, 토치처럼 두 면 사이를 이등분하는 방향으로 45 도 기울이고 3 mm 띄워서 닿지 않게 갑니다. 용접처럼 '
             '좌우로 흔드는 위빙은 지그재그 경유점을 만들어 지나가게 했습니다. 여기서도 인터페이스 계약을 먼저 정하고 병렬로 '
             '구현했습니다.\n'
             '(세부: 계약 v0.2.0 = 9/23 초안 · 9/26 머지 — 노드 weld_manager · 타입 7 개 · 사유 코드 600~604. 두산 move_periodic 은 '
             '제자리 주기 운동이라 직선 이동과 겹치지 않아 쓰지 않았다(D19). 스탠드오프는 팁 구 표면 ↔ 이음선 최단거리(D22). '
             '한 선이 z_safe 위에서 204 로 실패하면 그 선만 FAILED 로 두고 계속(D33). 점선 L1 · L5 = 45° 도달 불가(9/23 M1). '
             '[뺄 수 있음] 9/29 에 용접이 성사되지 않으면 04-⑨ 두 장을 통째로 뺀다. 다른 장은 이 장을 참조하지 않는다)')


def s_04_weld2(prs, templ):
    s = frame_slide(prs, templ, '04', '9/29 실기: 8 선 중 6 선 완주 — 닿지 않는 두 선은 계획대로 건너뛰었다',
                    '* 04-⑨ phase 2 용접 (2/2)  [뺄 수 있음]')
    rows = [['확인', '환경 · 날짜', '결과'],
            ['45° 자세 도달', '실기 · 9/23', '12 / 16   (L1 · L5 불가)'],
            ['8 선 종단', 'Virtual · 9/25', '8 / 8 완주 · 246 s'],
            ['실패 선 처리', 'Virtual · 9/25', 'FAILED 기록 → 마무리 ○'],
            ['윗면 L0 → L0~L3', '실기 · 9/29', '3 / 4 ○   (L1 은 FAILED 뒤 계속)'],
            ['8 선 중 완주', '실기 · 9/29', '6 / 8 ○ · 144 s   (L1 · L5 건너뜀)'],
            ['도착 · 무접촉', '실기 · 9/29', '경유점 3 mm 안 · 무접촉 · 안전 0 건'],
            ['3 mm 띄움 (눈 관찰)', '실기 · 9/29', '△ 선마다 0~8 mm (한쪽 치우침)']]
    amber = RGBColor(0xB8, 0x86, 0x0B)
    table(s, LEFT, 2.5, WIDTH, [3.7, 2.8, 5.83], rows, size=16, row_h=0.55, header_size=16,
          colors={(7, 2): amber})
    footnote(s, '출처: test-reports/realrobot-session_20260929.md(9/29 실기, 입력은 9/23 실기 스캔) · '
                'phase2/measurements-20260923.md(M1) · p2-weld-virtual_20260925.md(가상 박스 100×60×40 mm)')
    notes(s, '용접 쪽 결과입니다. 9/23 실기에서 기울인 자세의 도달성을 먼저 쟀는데, 16 자세 중 12 개에 닿았고 L1 · L5 두 선은 로봇 팔 '
             '길이가 모자라 닿지 않았습니다. 그래서 한 선이 실패해도 그 선만 실패로 남기고 다음 선으로 가게 만들었습니다. 에뮬레이터에서는 '
             '여덟 선을 모두 끝까지 돌았습니다. 9/29 실기에서는 여덟 선 중 여섯 선을 끝까지 따라갔고, 닿지 않는 두 선은 계획대로 '
             '실패로 기록한 뒤 다음 선으로 넘어갔습니다. 한 바퀴에 2 분 24 초, 닿거나 멈춘 일은 없었습니다. 다만 3 mm 띄운 거리가 '
             '선마다 0 에서 8 mm 로 달라 보여, 한쪽으로 3~4 mm 치우친 것을 다음 과제로 남겼습니다.\n'
             '(세부: M1 도달 자세 위치 오차 최대 0.14 mm, 45° 도달 한계는 플랜지 거리 689~761 mm 사이, L1 · L5 는 761 · 762 mm. 세로 '
             '아래 4 자세는 계약 z 104.13 이 아니라 121.25 mm 에서 확인했다(계약 z 는 9/29). Virtual 은 sim 가상 박스 100 × 60 × 40 mm '
             '입력이고 L7 강제 실패 시험에서 FAILED 기록 → 마무리 복귀 → DONE(success=false). 9/29 순서: 실기 스캔 1 회 → Virtual 종단 '
             '→ 윗면 L0(기울임 0 → 45°) → L0~L3 → 조건부로 세로선 · 위빙. '
             '9/29 실기(명령 현지 · 입회 학민): 기준점 점검 −0.016 mm 통과. 접근 · 후퇴점 도달성(D34)에서 L6 접근점이 도달 불가'
             '(알람 1206) → 윗면선 오프셋을 수직으로 · z_safe 32.5 mm · L6 · L7 툴 roll 180 으로 바꿔 L6 을 살렸다(#210). 툴 치수 '
             'M2 13 / 12 / 12 mm. 입력은 9/23 실기 스캔 — 9/29 실기 스캔은 3 회 모두 한 방향(NEG_Y)에서 실패했고, 잡힌 세 변이 9/23 '
             '과 1 mm 안이라 배치가 같음을 확인했다. 점마다 멈추는 비용 0.5 s. 위빙 L3 · L7 도 완주. 경유점 도착은 robot_manager 가 '
             '점마다 3 mm 안을 확인. 띄움 거리 0~8 mm 는 눈 관찰(현지 · 학민)이고 실측이 아니다. 한 번은 웹의 스캔 중지 버튼이 눌려 '
             '용접이 멈췄고(D25, 요청하지 않은 정지 = ERROR) 안전복귀로 정상 복귀. 구현 PR #191 · #195~#197 은 9/29 머지)')


# ── 05 자체 평가 ────────────────────────────────────────────────────────
def s_05_team(prs, templ):
    s = frame_slide(prs, templ, '05', '형상 정확도는 목표 안, 탐색 시간과 반복 검증은 목표 밖 — 팀의 자체 평가',
                    '* 05 자체 평가 — 팀')
    rows = [['이름', '완성도 /10', '이유'],
            ['박병후', '8 / 10', '먼저 계약을 확정하고 작업별로 꼼꼼하게 검증한 덕분에 최종 integration 때 시행착오가 적었다. 하지만 이해도가 뒷받침되지 못하고 꼼꼼한 검증 절차로 각 작업의 진행이 지연되었다.'],
            ['김학민', '[받으면]', '[받으면 채움: 학민]'],
            ['남현지', '[받으면]', '[받으면 채움: 현지]'],
            ['정의석', '[받으면]', '[받으면 채움: 의석]']]
    table(s, LEFT, 2.7, 6.0, [1.2, 0.95, 3.85], rows, size=10.5, row_h=0.5,
          colors={(r, c): ORANGE for r in range(2, 5) for c in (1, 2)})
    text_box(s, LEFT, 5.95, 6.0, 0.6, [('평균 [받으면 채움] / 10', {'bold': True, 'size': 13, 'color': ORANGE})])
    bullets(s, 6.7, 2.7, 6.13, 4.2, [
        ('잘한 점', {'bold': True, 'color': BLUE, 'size': 12.5, 'after': 2}),
        ('· 계약을 먼저 동결해 네 명이 병렬로 만들었고, 9/23 실기에서 웹 → ROS → 웹이 이어졌다', {'size': 11}),
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
             '(병후 8 / 10 — 이유: 먼저 계약을 확정하고 작업별로 꼼꼼하게 검증한 덕분에 최종 integration 때 시행착오가 적었다. 하지만 이해도가 뒷받침되지 못하고 꼼꼼한 검증 절차로 각 작업의 진행이 지연되었다. 받으면 채움: 학민 · 현지 · 의석의 점수와 이유, 평균. 잘한 점 · 아쉬운 점 · 개선점 문장은 '
             '사실 기반 초안이라 팀 확인 필요)')


def s_05_personal(prs, templ):
    s = frame_slide(prs, templ, '05', '각자 한 줄 소감과, 운영 · 협업 · 개선 사례 하나씩', '* 05 자체 평가 — 개인')
    rows = [['이름', '한 줄 (느낀 점 · 성과)', '운영', '협업', '개선'],
            ['박병후', '계약을 먼저 고정하니 넷이 따로 만들어도 한 흐름으로 이어졌다. 대신 실측이 바꾼 값을 계약에 되돌리는 일이 끝까지 남았다',
             '계약 동결(9/18) 뒤 변경은 PR + 변경 이력으로만 — v0.1 → v0.1.20',
             'MQTT 계약을 의석과 한 장으로 합의(9/18) — 목업 발행기와 브리지 시험이 같은 예시를 쓴다',
             '감시자 끊김이면 시작 거절(04-⑧, PR #136)'],
            ['김학민', '[받으면 채움: 학민]', '[받으면 채움]', '[받으면 채움]', '[받으면 채움]'],
            ['남현지', '[받으면 채움: 현지]', '[받으면 채움]', '[받으면 채움]', '[받으면 채움]'],
            ['정의석', '[받으면 채움: 의석]', '[받으면 채움]', '[받으면 채움]', '[받으면 채움]']]
    colors = {(r, c): ORANGE for r in range(2, 5) for c in range(1, 5)}
    table(s, LEFT, 2.7, WIDTH, [1.1, 3.9, 2.45, 2.6, 2.28], rows, size=10, row_h=0.8, colors=colors)
    footnote(s, '출처: docs/contracts/CHANGELOG.md · docs/contracts/mqtt-schema.md 상태 줄(T01 1 차 회의 병후 · 의석) · PR #136. '
                '병후 행은 병후 확인(9/28), 나머지는 받으면 채움', y=7.1)
    notes(s, '마지막으로 개인 평가입니다. 저는 계약을 먼저 정해 두니 네 명이 따로 만들어도 한 흐름으로 이어진다는 것을 배웠고, 대신 '
             '실기에서 잰 값이 계약을 계속 바꿔서 그것을 되돌리는 일이 끝까지 남았습니다. 운영에서는 계약 변경을 PR 과 변경 이력으로만 '
             '받았고, 협업에서는 의석과 MQTT 계약을 한 장으로 합의했으며, 개선 사례는 앞에서 말씀드린 감시자 끊김 문제입니다. '
             '팀원들의 한 줄은 각자 말씀드리겠습니다 — [받으면 채움].\n'
             '(병후 행은 병후 확인(9/28). 받으면 채움: 학민 · 현지 · 의석의 한 줄 + 운영 · 협업 · 개선 사례 1 개씩)')


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
