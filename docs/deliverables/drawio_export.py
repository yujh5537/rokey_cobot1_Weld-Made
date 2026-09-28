"""drawio 쪽(page)을 png 로 내보낸다 — headless Chrome + diagrams.net 뷰어(viewer-static.min.js).

drawio 데스크톱이 없는 PC 에서 쓰려고 만들었다. 인터넷이 필요하다(뷰어 스크립트를 받는다. 그림 데이터는 밖으로 보내지 않는다).
app.diagrams.net 에서 파일 → 내보내기 → PNG 로 내보내도 결과는 같다.

사용:
  python3 docs/deliverables/drawio_export.py 06-node-graph.drawio 1:06-node-graph.png 2:06-node-graph-no-phase2.png
  (쪽 번호:출력 파일, 쪽 번호는 1 부터. 경로는 이 파일이 있는 폴더 기준)
옵션: --scale 1.5 (기본, 글자를 또렷하게)
"""
import argparse
import html
import json
import pathlib
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

HERE = pathlib.Path(__file__).resolve().parent
VIEWER = 'https://viewer.diagrams.net/js/viewer-static.min.js'


def bbox(diagram):
    xs, ys = [], []
    gm = diagram.find('mxGraphModel')
    layers = {c.get('id') for c in gm.iter('mxCell') if c.get('parent') == '0'}
    for c in gm.iter('mxCell'):
        g = c.find('mxGeometry')
        if g is None:
            continue
        if c.get('vertex') == '1' and c.get('parent') in layers:
            x, y = float(g.get('x', 0)), float(g.get('y', 0))
            xs += [x, x + float(g.get('width', 0))]
            ys += [y, y + float(g.get('height', 0))]
        if c.get('edge') == '1':
            for pt in g.iter('mxPoint'):
                if pt.get('as') in ('offset',):
                    continue
                if pt.get('x') is not None:
                    xs.append(float(pt.get('x')))
                    ys.append(float(pt.get('y')))
    return min(xs), min(ys), max(xs), max(ys)


def export(src, page_no, out, scale):
    root = ET.parse(src).getroot()
    d = list(root.iter('diagram'))[page_no - 1]
    x0, y0, x1, y1 = bbox(d)
    w, h = int(x1 - x0 + 40), int(y1 - y0 + 40)
    one = ET.Element('mxfile')
    one.append(d)
    cfg = {'xml': ET.tostring(one, encoding='unicode'), 'toolbar': '', 'nav': False, 'resize': False, 'zoom': 1,
           'lightbox': False, 'border': 20}
    page = ('<!doctype html><html><head><meta charset="utf-8"><style>body{margin:0;background:#fff}</style></head><body>'
            f'<div class="mxgraph" style="max-width:none" data-mxgraph="{html.escape(json.dumps(cfg))}"></div>'
            f'<script src="{VIEWER}"></script></body></html>')
    chrome = shutil.which('google-chrome') or shutil.which('chromium') or shutil.which('chromium-browser')
    if not chrome:
        raise SystemExit('Chrome 이 없다. app.diagrams.net 에서 내보내라.')
    with tempfile.TemporaryDirectory() as td:
        hp = pathlib.Path(td) / 'page.html'
        hp.write_text(page, encoding='utf-8')
        subprocess.run([chrome, '--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
                        f'--force-device-scale-factor={scale}', f'--window-size={w},{h}',
                        '--virtual-time-budget=20000', f'--screenshot={out}', hp.as_uri()],
                       check=True, capture_output=True, timeout=180)
    print(f'{src.name} 쪽 {page_no} ({d.get("name")}) → {out.name}  {w}×{h} px × {scale}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('drawio')
    ap.add_argument('pages', nargs='+', help='쪽번호:출력.png')
    ap.add_argument('--scale', type=float, default=1.5)
    a = ap.parse_args()
    src = (HERE / a.drawio) if not pathlib.Path(a.drawio).is_absolute() else pathlib.Path(a.drawio)
    for spec in a.pages:
        no, name = spec.split(':', 1)
        out = pathlib.Path(name)
        out = out if out.is_absolute() else HERE / out
        export(src, int(no), out, a.scale)


if __name__ == '__main__':
    main()
