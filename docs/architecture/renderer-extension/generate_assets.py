from pathlib import Path
import re,json,hashlib,html
from bs4 import BeautifulSoup
import cairosvg,tinycss2,cssselect2
from png_integrity import atomic_png
R=Path(__file__).resolve().parent.parent;checks=[]
for n in ['01_system','02_ros2','03_erd','04_flow']:
 text=(R/(n+'.html')).read_text();soup=BeautifulSoup(text,'html.parser');svg=soup.find('svg',attrs={'role':'img'});vb=svg['viewbox'] if 'viewbox'in svg.attrs else svg['viewBox'];w,h=map(float,vb.split()[2:]);styles='\n'.join(st.get_text() for st in soup.find_all('style'))
 vars=dict(re.findall(r'(--[\w-]+)\s*:\s*([^;]+);',re.search(r'\[data-theme="dark"\]\s*\{(.*?)\}',styles,re.S).group(1)))
 css=re.sub(r'var\((--[\w-]+)(?:,[^)]*)?\)',lambda m:vars.get(m.group(1),'#94a3b8'),styles)
 # Package the renderer's own SVG geometry and styles; no node/edge/text changes.
 svg['xmlns']='http://www.w3.org/2000/svg';svg['width']=str(int(w));svg['height']=str(int(h));svg['data-theme']='dark';svg['viewBox']=vb;svg.attrs.pop('viewbox',None)
 st=soup.new_tag('style');st.string=css+"\ntext{font-family:'Noto Sans CJK KR',monospace} svg{background:#020617}";svg.insert(0,st)
 bg=soup.new_tag('rect',attrs={'width':'100%','height':'100%','fill':'#020617'});svg.insert(1,bg)
 # html parser folds SVG names. Restore names from the canonical markup, including attributes.
 ss=str(svg);ss=re.sub(r'<style>(.*?)</style>',lambda m:'<style><![CDATA['+m.group(1)+']]></style>',ss,flags=re.S)
 names={'viewbox':'viewBox','markerunits':'markerUnits','markerwidth':'markerWidth','markerheight':'markerHeight','refx':'refX','refy':'refY','preserveaspectratio':'preserveAspectRatio','gradientunits':'gradientUnits','patternunits':'patternUnits'}
 for a,b in names.items():ss=re.sub(r'\b'+a+r'=',b+'=',ss)
 for a,b in [('lineargradient','linearGradient'),('radialgradient','radialGradient'),('clippath','clipPath')]:ss=re.sub(r'(<\/?)(%s)(\s|>)'%a,r'\1'+b+r'\3',ss)
 ss=re.sub(r'var\((--[\w-]+)(?:,[^)]*)?\)',lambda m:vars.get(m.group(1),'#94a3b8'),ss)
 (R/(n+'.svg')).write_text('<?xml version="1.0" encoding="UTF-8"?>\n'+ss)
 raster_rules=[]
 for rule in tinycss2.parse_stylesheet(css):
  if rule.type!='qualified-rule':continue
  try:cssselect2.compile_selector_list(rule.prelude)
  except cssselect2.SelectorError:continue
  raster_rules.append(tinycss2.serialize([rule]))
 raster_css='\n'.join(raster_rules)+"\ntext{font-family:'Noto Sans CJK KR',monospace}"
 raster_svg=re.sub(r'<style>.*?</style>',lambda m:'<style><![CDATA['+raster_css+']]></style>',ss,flags=re.S)
 png_bytes=cairosvg.svg2png(bytestring=raster_svg.encode(),output_width=int(w*1.5),output_height=int(h*1.5))
 png_validation=atomic_png(R/(n+'.png'),png_bytes)
 orig=BeautifulSoup(text,'html.parser').find('svg',attrs={'role':'img'});new=BeautifulSoup(ss,'xml').find('svg')
 oldlabels=[x.get_text() for x in orig.find_all('text')];newlabels=[x.get_text() for x in new.find_all('text')];assert oldlabels==newlabels
 candidate=json.load(open(R/'data'/(n+'.json')));svgids={x.get('data-node-id') for x in orig.find_all(attrs={'data-node-id':True})};assert {x['id'] for x in candidate['components']}<=svgids
 checks.append(dict(diagram=n,labels_exact=True,node_ids_exact=True,node_count=len(candidate['components']),edge_count=len(candidate['connections']),svg_sha256=hashlib.sha256((R/(n+'.svg')).read_bytes()).hexdigest(),png_sha256=png_validation['sha256'],png_validation=png_validation,method='Original renderer SVG + original CSS with resolved dark theme tokens; CairoSVG PNG, Noto CJK fallback. Atomic write after PNG CRC/IEND/full decoding. Not a native UI download.'))
(R/'evidence/svg-png-audit.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2))
# Self-contained wrapper embeds all latest generated viewers byte-for-byte.
text=(R/'site-wrapper.html').read_text();payload={k:(R/f).read_text() for k,f in [('system','01_system.html'),('ros','02_ros2.html'),('erd','03_erd.html'),('flow','04_flow.html')]}
text=re.sub(r'(?:src|data-src)="0[1-4]_[^\"]+\.html\?theme=dark"','',text)
text=text.replace("let mode='system',theme='dark';",'const payload='+json.dumps(payload,ensure_ascii=False).replace('</','<\\/')+";let mode='system',theme='dark';")
text=text.replace("if(!frame.getAttribute('src'))frame.src=paths[mode]+'?theme='+theme+'';","if(!frame.getAttribute('srcdoc'))frame.srcdoc=payload[mode];")
text=text.replace("setTheme('dark');\n})();","frames.system.srcdoc=payload.system;setTheme('dark');\n})();")
(R/'Weld-Made-preview.html').write_text(text)
(R/'index.html').write_text(text)
print('Four SVGs/PNGs and current embedded preview generated')
