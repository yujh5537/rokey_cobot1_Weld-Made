"""Generate manifest only after complete assets; reopen ZIP and decode extracted PNGs."""
from pathlib import Path
import json,hashlib,zipfile,tempfile,os,sys,shutil
from png_integrity import inspect_png

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def excluded(path):
    """Execution state is never a delivery artifact; completed receipts remain."""
    return (any(x.startswith('.') or x=='__pycache__' for x in path.parts)
            or path.name.endswith(('.delivery-lock.json','.delivery-pending.json'))
            or path.name=='specification.snapshot.json')

def pack(root,out):
    for p in root.rglob('*.png'):inspect_png(p.read_bytes())
    for n in ['01_system','02_ros2','03_erd','04_flow']:
        result=json.loads((root/(n+'.finalize-result.json')).read_text())
        assert all(result['gates'][g]=='pass'for g in ['validate','deliver','check']),n
        browser=json.loads((root/(n+'.browser-check.json')).read_text())
        assert browser['artifact']['sha256']==sha(root/(n+'.html'))
        assert browser['status']in ['pass','skipped'],n
        visual=json.loads((root/'evidence'/(n+'.visual-result.json')).read_text())
        assert visual['status']in ['pass','skipped'],n
    paths=sorted(p for p in root.rglob('*')if p.is_file()and p.name!='MANIFEST.json'and not excluded(p.relative_to(root)))
    manifest={'schemaVersion':1,'projectCommit':'8933b739ee43294605e57dca07625bad2f9e8ca4','archifyCommit':'bb6f126f1748a4079df1d263302466eb4333e3b0','generatedAt':'2026-10-05','files':[{'path':p.relative_to(root).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)}for p in paths]}
    (root/'MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    fd,tmp=tempfile.mkstemp(prefix='.'+out.name+'-',dir=out.parent)
    try:
        with os.fdopen(fd,'w+b')as f:
            with zipfile.ZipFile(f,'w',zipfile.ZIP_DEFLATED)as z:
                for p in paths+[root/'MANIFEST.json']:z.write(p,p.relative_to(root).as_posix())
            f.flush();os.fsync(f.fileno())
        os.replace(tmp,out)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
    return manifest

def verify_extracted(out,destination):
    destination.mkdir(parents=True,exist_ok=False)
    with zipfile.ZipFile(out)as z:
        assert z.testzip()is None
        assert not any(excluded(Path(n)) for n in z.namelist()), 'Transient execution state in delivery ZIP'
        for n in z.namelist():
            assert not Path(n).is_absolute()and '..'not in Path(n).parts
        z.extractall(destination)
    manifest=json.loads((destination/'MANIFEST.json').read_text())
    assert not any(excluded(Path(rec['path'])) for rec in manifest['files'])
    assert {rec['path'] for rec in manifest['files']} == {p.relative_to(destination).as_posix() for p in destination.rglob('*') if p.is_file() and p.name != 'MANIFEST.json'}
    for rec in manifest['files']:
        p=destination/rec['path'];assert p.stat().st_size==rec['bytes'];assert sha(p)==rec['sha256']
    for p in destination.rglob('*.png'):inspect_png(p.read_bytes())
    png=[];audit={x['diagram']:x for x in json.loads((destination/'evidence/svg-png-audit.json').read_text())}
    for n in ['01_system','02_ros2','03_erd','04_flow']:
        rec=inspect_png((destination/(n+'.png')).read_bytes());assert rec['sha256']==audit[n]['png_sha256']
        png.append({'diagram':n,**rec})
        receipt=json.loads((destination/(n+'.delivery.json')).read_text())
        assert receipt['artifact']['sha256']==sha(destination/(n+'.html'))
        assert receipt['specification']['sha256']==sha(destination/'data'/(n+'.json'))
    return {'transientStateFiles':0,'zipCRC':'pass','manifestFilesVerified':len(manifest['files']),'pngs':png,'receiptSha':'pass','method':'Completed ZIP physically extracted to separate directory; SHA/size/PNG CRC/IEND/full Pillow pixels including bottom decoded again.'}

if __name__=='__main__':
    root=Path(__file__).resolve().parent.parent
    out=Path(sys.argv[1]).resolve()if len(sys.argv)>1 else root.parent/'Weld-Made-architectures-png-repaired.zip'
    pack(root,out)
    first=Path(tempfile.mkdtemp(prefix='png-zip-review-',dir=root.parent));first.rmdir()
    report=verify_extracted(out,first)
    (root/'evidence/zip-roundtrip-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    # Include the new record and manifest, then verify the FINAL ZIP again.
    pack(root,out)
    final=Path(tempfile.mkdtemp(prefix='png-final-extracted-',dir=root.parent));final.rmdir()
    final_report=verify_extracted(out,final)
    print(json.dumps({'zip':str(out),'zipBytes':out.stat().st_size,'zipSha256':sha(out),'finalExtraction':str(final),'result':final_report},ensure_ascii=False,indent=2))
