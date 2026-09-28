"""drawio(mxGraph XML) 를 코드로 쓰는 작은 도구. 산출물 01 · 05 · 06 의 drawio 를 만드는 스크립트가 같이 쓴다.

색 · 선 모양은 docs/design 의 옛 그림(시스템 아키텍처 v1.6 · 노드 구성도 v1.1 · 노드 구조도 간략 v1.2)과 같은 값을 쓴다.
drawio 파일이 원본이다. 이 스크립트는 처음 만들 때와 크게 고칠 때만 쓰고, 작은 수정은 app.diagrams.net 에서 해도 된다.
"""
import html
import re
import xml.etree.ElementTree as ET

# ── 갈래 색 (v1.6 범례와 같은 값) ────────────────────────────────────────
CAT = {
    'cmd': '#5F7FD8',      # 명령
    'show': '#4FA79B',     # 표시 데이터
    'state': '#DB8368',    # 로봇 상태
    'contact': '#C99A1E',  # 접촉 이벤트
    'motion': '#A78BE4',   # 모션
    'safety': '#D9736C',   # 안전
    'store': '#C2A57C',    # 저장
    'biz': '#8894A4',      # 업무 관리
    'ext': '#8A96A3',      # 외부(제공 · 설치 사용)
    'gap': '#9AA3AD',      # 계약에만 있고 구현 안 됨
}
P2 = '#E07B24'             # phase 2(용접) 표시색
P2_FILL = '#FDF0E4'
P2_HEAD = '#FAD9BB'

ZONE = {  # (채움, 테두리) — 웹 PC · 메인 PC · 로봇 컨트롤러
    'web': ('#FAEFF7', '#A05195'),
    'main': ('#EFF1FB', '#5566B5'),
    'robot': ('#EEF7F5', '#2E8B7A'),
}


def plain(value):
    """html 값 → 글자만 (길이 추정용)."""
    s = re.sub(r'<br\s*/?>', '\n', value or '')
    s = re.sub(r'<[^>]+>', '', s)
    return html.unescape(s)


def char_w(ch):
    o = ord(ch)
    if 0xAC00 <= o <= 0xD7A3 or 0x3000 <= o <= 0x9FFF or 0x2460 <= o <= 0x24FF:
        return 1.0
    if ch == ' ':
        return 0.3
    if ch in '·—→←↑↓↔≈±×○△◇≠≤≥':
        return 0.85
    if ch.isupper() or ch.isdigit():
        return 0.64
    return 0.55


def text_lines(text, width_px, font_px):
    n = 0
    for para in text.split('\n'):
        w = sum(char_w(c) for c in para) * font_px
        n += max(1, int(w // max(1.0, width_px)) + (1 if w % max(1.0, width_px) > 0 else 0))
    return n


def wrap_html(value, width_px, font_px):
    """html 값의 각 줄(<br/> 로 나뉜)을 width_px 안에 들도록 ' · ' 나 빈칸에서 끊어 <br/> 을 넣는다."""
    out = []
    for line in re.split(r'<br\s*/?>', value):
        if sum(char_w(c) for c in plain(line)) * font_px <= width_px:
            out.append(line)
            continue
        # 태그 안은 끊지 않는다: 태그를 자리표시로 바꿔 두고 끊은 뒤 되돌린다
        tags = []

        def keep(m):
            tags.append(m.group(0))
            return f'\x00{len(tags) - 1}\x00'
        t = re.sub(r'<[^>]+>', keep, line)
        words = re.split(r'(?<= )', t)
        cur, lines = '', []
        for w in words:
            cand = cur + w
            if cur and sum(char_w(c) for c in plain(re.sub(r'\x00\d+\x00', '', cand))) * font_px > width_px:
                lines.append(cur.rstrip())
                cur = w
            else:
                cur = cand
        lines.append(cur.rstrip())
        restore = lambda x: re.sub(r'\x00(\d+)\x00', lambda m: tags[int(m.group(1))], x)
        # 여는 태그가 줄을 넘어가면 줄마다 닫고 다시 연다(<b> · <font> 만)
        fixed, open_tags = [], []
        for ln in lines:
            ln = ''.join(open_tags) + restore(ln)
            stack = []
            for m in re.finditer(r'<(/?)(b|font)(\s[^>]*)?>', ln):
                if m.group(1):
                    if stack:
                        stack.pop()
                else:
                    stack.append(m.group(0))
            fixed.append(ln + ''.join(f'</{re.match(r"<(\w+)", t2).group(1)}>' for t2 in reversed(stack)))
            open_tags = stack
        out.append('<br/>'.join(fixed))
    return '<br/>'.join(out)


def fit_h(value, width_px, font_px, pad=14, line=1.28, min_h=0):
    """글이 들어갈 상자 높이(px) 추정. 글씨 크기가 섞인 경우 큰 쪽 기준."""
    return max(min_h, int(text_lines(plain(value), width_px - 18, font_px) * font_px * line + pad))


class Page:
    def __init__(self, name, width, height, pid=None):
        self.name = name
        self.id = pid or re.sub(r'\W+', '-', name)
        self.width, self.height = width, height
        self.cells = []          # (tag, attrs, geometry dict, points, extra children)
        self.layers = [('1', '1차 (스캔)')]
        self.n = 0
        self.geo = {}            # id → (x, y, w, h) 절대 좌표

    def _id(self, prefix='c'):
        self.n += 1
        return f'{prefix}{self.n}'

    def layer(self, lid, name):
        self.layers.append((lid, name))
        return lid

    def v(self, x, y, w, h, value='', style='', cid=None, layer='1'):
        cid = cid or self._id()
        self.cells.append(dict(id=cid, value=value, style=style, vertex='1', parent=layer,
                               geo=dict(x=x, y=y, width=w, height=h)))
        self.geo[cid] = (x, y, w, h)
        return cid

    def text(self, x, y, w, h, value, size=13, color='#33465C', bold=False, align='left', layer='1', cid=None,
             valign='middle', wrap=True):
        st = (f'text;html=1;align={align};verticalAlign={valign};fontSize={size};fontColor={color};'
              + ('fontStyle=1;' if bold else '') + ('whiteSpace=wrap;' if wrap else ''))
        return self.v(x, y, w, h, value, st, cid=cid, layer=layer)

    def port(self, cid, side, pos):
        """상자 cid 의 한 변(side: L R T B) 위 절대 좌표 pos(세로 변은 y, 가로 변은 x) → (점, exit/entry 비율)."""
        x, y, w, h = self.geo[cid]
        if side in 'LR':
            fy = (pos - y) / h
            px = x if side == 'L' else x + w
            return (px, pos), (0.0 if side == 'L' else 1.0, round(fy, 4))
        fx = (pos - x) / w
        py = y if side == 'T' else y + h
        return (pos, py), (round(fx, 4), 0.0 if side == 'T' else 1.0)

    def e(self, src, tgt, style, sside, spos, tside, tpos, via=(), label=None, label_at=None, label_w=220,
          label_style=None, layer='1', cid=None, label_h=None, label_font=10):
        """선 하나. via = 꺾이는 점(절대 좌표). label_at = 라벨 가운데를 둘 선 위의 점(절대 좌표)."""
        cid = cid or self._id('e')
        p0, (ex, ey) = self.port(src, sside, spos)
        p1, (nx, ny) = self.port(tgt, tside, tpos)
        st = (style + f'exitX={ex};exitY={ey};exitDx=0;exitDy=0;entryX={nx};entryY={ny};entryDx=0;entryDy=0;')
        self.cells.append(dict(id=cid, value='', style=st, edge='1', parent=layer, source=src, target=tgt,
                               geo=dict(relative='1'), points=list(via)))
        if label:
            pts = [p0, *via, p1]
            rel = rel_along(pts, label_at) if label_at else 0.0
            ls = label_style or ('edgeLabel;html=1;align=center;verticalAlign=middle;resizable=0;points=[];whiteSpace=nowrap;'
                                 f'fontSize={label_font};fontColor=#16202B;labelBackgroundColor=#FFFFFF;'
                                 'labelBorderColor=#16202B;spacing=2;')
            # 폭을 주면 drawio 가 라벨을 기준점 오른쪽으로 민다. 폭 없이(기본 라벨처럼) 두고 줄바꿈은 직접 넣는다.
            self.cells.append(dict(id=cid + 'l', value=wrap_html(label, label_w, label_font), style=ls, vertex='1',
                                   connectable='0', parent=cid, geo=dict(x=round(rel, 4), relative='1'),
                                   offset=(0, 0)))
        return cid

    def free_edge(self, x0, y0, x1, y1, style, layer='1'):
        cid = self._id('e')
        self.cells.append(dict(id=cid, value='', style=style, edge='1', parent=layer,
                               geo=dict(width=50, height=50, relative='1'), sp=(x0, y0), tp=(x1, y1)))
        return cid

    def xml(self):
        d = ET.Element('diagram', id=self.id, name=self.name)
        gm = ET.SubElement(d, 'mxGraphModel', dx='0', dy='0', grid='1', gridSize='10', guides='1', tooltips='1',
                           connect='1', arrows='1', fold='1', page='1', pageScale='1', pageWidth=str(self.width),
                           pageHeight=str(self.height), math='0', shadow='0')
        root = ET.SubElement(gm, 'root')
        ET.SubElement(root, 'mxCell', id='0')
        for lid, lname in self.layers:
            a = dict(id=lid, parent='0')
            if lid != '1':
                a['value'] = lname
            ET.SubElement(root, 'mxCell', a)
        for c in self.cells:
            a = {k: c[k] for k in ('id', 'value', 'style', 'vertex', 'edge', 'connectable', 'parent', 'source',
                                   'target') if k in c}
            el = ET.SubElement(root, 'mxCell', a)
            g = {k: str(v) for k, v in c['geo'].items()}
            g['as'] = 'geometry'
            ge = ET.SubElement(el, 'mxGeometry', g)
            if c.get('points'):
                arr = ET.SubElement(ge, 'Array', {'as': 'points'})
                for px, py in c['points']:
                    ET.SubElement(arr, 'mxPoint', x=str(px), y=str(py))
            if 'sp' in c:
                ET.SubElement(ge, 'mxPoint', x=str(c['sp'][0]), y=str(c['sp'][1]), **{'as': 'sourcePoint'})
                ET.SubElement(ge, 'mxPoint', x=str(c['tp'][0]), y=str(c['tp'][1]), **{'as': 'targetPoint'})
            if 'offset' in c:
                ET.SubElement(ge, 'mxPoint', x=str(c['offset'][0]), y=str(c['offset'][1]), **{'as': 'offset'})
        return d


def rel_along(pts, at):
    """꺾은선 pts 위에서 점 at 에 가장 가까운 곳의 위치 → drawio 라벨 x(−1 = 시작, +1 = 끝)."""
    segs, total = [], 0.0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        L = abs(x1 - x0) + abs(y1 - y0)
        segs.append((x0, y0, x1, y1, total, L))
        total += L
    best, bd = 0.0, 1e18
    ax, ay = at
    for x0, y0, x1, y1, s0, L in segs:
        if L == 0:
            continue
        t = ((ax - x0) * (x1 - x0) + (ay - y0) * (y1 - y0)) / (L * L) if (x0 == x1 or y0 == y1) else 0.5
        t = min(1.0, max(0.0, t))
        px, py = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
        dd = (px - ax) ** 2 + (py - ay) ** 2
        if dd < bd:
            bd, best = dd, s0 + L * t
    return 2 * best / total - 1 if total else 0.0


def write_mxfile(path, pages, agent='contact-scan-deliverables'):
    mf = ET.Element('mxfile', host='app.diagrams.net', agent=agent, version='24.7.8')
    for p in pages:
        mf.append(p.xml())
    ET.indent(mf, space='  ')
    path.write_text(ET.tostring(mf, encoding='unicode') + '\n', encoding='utf-8')


# ── 자주 쓰는 모양 ────────────────────────────────────────────────────────
def zone(p, x, y, w, h, kind, title, stroke_w=3, head_h=40, font=15, layer='1'):
    fill, stroke = ZONE[kind]
    p.v(x, y, w, h, '', f'rounded=1;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};strokeWidth={stroke_w};'
        + ('arcSize=2;' if h > 800 else ''), layer=layer)
    p.v(x, y, w, head_h, title, f'rounded=1;whiteSpace=wrap;html=1;fillColor={stroke};strokeColor={stroke};fontSize={font};'
        'fontStyle=1;fontColor=#FFFFFF;align=center;verticalAlign=middle;', layer=layer)


def edge_style(cat, kind, dashed=False, color=None):
    """kind: T(Topic) · S(Service) · A(Action) · X(외부 한 방향) · XX(외부 양방향) · F(파일)."""
    c = color or CAT[cat]
    base = f'edgeStyle=orthogonalEdgeStyle;rounded=1;arcSize=8;html=1;jumpStyle=arc;jumpSize=8;strokeColor={c};'
    if kind == 'A':
        s = base + 'strokeWidth=4.5;endArrow=block;endFill=1;startArrow=block;startFill=1;'
    elif kind == 'S':
        s = base + 'strokeWidth=2.2;endArrow=block;endFill=1;startArrow=oval;startFill=0;startSize=6;'
    elif kind == 'XX':
        s = base + 'strokeWidth=2;endArrow=blockThin;endFill=1;startArrow=blockThin;startFill=1;'
    elif kind in ('X', 'F'):
        s = base + 'strokeWidth=2;endArrow=blockThin;endFill=1;startArrow=none;'
    else:
        s = base + 'strokeWidth=2.2;endArrow=blockThin;endFill=1;startArrow=none;'
    if dashed or kind == 'F':
        s += 'dashed=1;dashPattern=6 4;'
    return s
