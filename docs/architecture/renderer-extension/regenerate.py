"""Rebuild a relocated ZIP with pinned official/extended Archify checkouts.
Old completed receipts are archived OUTSIDE the delivery directory. Never delete locks.
"""
from pathlib import Path
import argparse,subprocess,json,tempfile,shutil,hashlib,sys
p=argparse.ArgumentParser();p.add_argument('--official',required=True);p.add_argument('--extended',required=True);p.add_argument('--project',required=True);a=p.parse_args()
root=Path(__file__).resolve().parent.parent
repos={k:Path(getattr(a,k)).resolve() for k in ['official','extended','project']}
for k,r in repos.items():
    expected='8933b739ee43294605e57dca07625bad2f9e8ca4' if k=='project' else 'bb6f126f1748a4079df1d263302466eb4333e3b0'
    assert subprocess.check_output(['git','-C',str(r),'rev-parse','HEAD'],text=True).strip()==expected,k
# These states require owner-aware recovery, not automatic deletion.
from package_delivery import excluded
states=[str(f) for f in root.rglob('*') if f.is_file() and (f.name.endswith(('.delivery-lock.json','.delivery-pending.json')) or f.name=='.archify-delivery-lock.json')]
if states:raise SystemExit('Execution state present; stop and inspect ownership: '+str(states))
names=['01_system','02_ros2','03_erd','04_flow']
assets=[root/'data'/(n+'.json') for n in names]+[root/(n+ext) for n in names for ext in ['.html','.svg','.png']]+[root/'Weld-Made-preview.html',root/'index.html']
def hashes():return {str(f.relative_to(root)):hashlib.sha256(f.read_bytes()).hexdigest() for f in assets}
before=hashes();archive=Path(tempfile.mkdtemp(prefix='archify-prior-receipts-',dir=root.parent))
for n in names:
    for suffix in ['.delivery.json','.browser-check.json','.finalize.json','.finalize-summary.json','.finalize-result.json']:
        f=root/(n+suffix)
        if f.exists():shutil.move(str(f),str(archive/f.name))
    visual=root/'evidence'/('visual-'+n)
    if visual.exists():shutil.move(str(visual),str(archive/visual.name))
    oldvisual=root/'evidence'/(n+'.visual-result.json')
    if oldvisual.exists():shutil.move(str(oldvisual),str(archive/oldvisual.name))
results=[]
recoveries=[]
finished=[]
def recover_own_completed_states():
    # This function only handles states created AFTER our initial empty-state
    # check, by child commands we already waited for. Never recover foreign locks.
    paths=[f for f in root.iterdir() if f.is_file() and (f.name.endswith(('.delivery-lock.json','.delivery-pending.json')) or f.name=='.archify-delivery-lock.json')]
    owners={}
    for name in finished:
        receipt=json.loads((root/(name+'.delivery.json')).read_text())
        assert receipt['artifact']['sha256']==hashlib.sha256((root/(name+'.html')).read_bytes()).hexdigest()
        assert receipt['specification']['sha256']==hashlib.sha256((root/'data'/(name+'.json')).read_bytes()).hexdigest()
        assert receipt['input']==str(root/'data'/(name+'.json')) and receipt['output']==str(root/(name+'.html'))
        owners[receipt['receiptId']]=name
    for state in paths:
        record=json.loads(state.read_text())
        assert record['receiptId'] in owners,('Foreign or incomplete delivery state; inspect manually',state)
    if paths:
        folder=archive/('completed-state-'+str(len(recoveries)));folder.mkdir()
        for state in paths:shutil.move(str(state),str(folder/state.name))
        recoveries.append({'files':[f.name for f in paths],'reason':'Our CLI children terminated; current receipt/candidate/artifact SHA and ownership paths verified; execution state archived outside package.'})
for n in names:
    repo=repos['official' if n in names[:2] else 'extended']
    command=['node',str(repo/'archify/bin/archify.mjs'),'finalize','architecture',str(root/'data'/(n+'.json')),str(root/(n+'.html')),'--repo-root',str(repos['project']),'--quality',('standard' if n in names[:2] else 'showcase'),'--json']
    attempts=[]
    for attempt in range(3):
        recover_own_completed_states()
        # Evidence is path/receipt-owned; do not reuse an earlier attempt's sidecars.
        for suffix in ['.browser-check.json','.finalize.json','.finalize-summary.json','.finalize-result.json']:
            old=root/(n+suffix)
            if old.exists():shutil.move(str(old),str(archive/(str(attempt)+'-'+old.name)))
        run=subprocess.run(command,text=True,capture_output=True)
        (root/'evidence'/(n+'.regenerate-stderr.txt')).write_text(run.stderr)
        try:result=json.loads(run.stdout)
        except Exception:raise RuntimeError(run.stdout+run.stderr)
        (root/(n+'.finalize-result.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2))
        attempts.append({'exitCode':run.returncode,'status':result['status'],'gates':result.get('gates',{}),'diagnostics':result.get('diagnostics',[])})
        if result.get('gates',{}).get('deliver')=='pass' and n not in finished:finished.append(n)
        valid_status = result['status']=='pass' or (result['status']=='skipped' and all(d['code']=='viewer/chrome-unavailable' for d in result.get('diagnostics',[])))
        if all(result.get('gates',{}).get(g)=='pass' for g in ['validate','deliver','check']) and valid_status:break
        provenance_block = result.get('gates',{}).get('deliver')=='pass' and all(d['code'] in ['delivery/provenance-locked','delivery/provenance-failed'] for d in result.get('diagnostics',[]))
        ended_prior_lock = bool(result.get('diagnostics')) and all(d['code']=='delivery/lock-stale' for d in result['diagnostics'])
        assert provenance_block or ended_prior_lock,result
        # A stale-lock retry is allowed only when recover_own_completed_states
        # verifies it belongs to an earlier child we waited for, with current hashes.
        recover_own_completed_states()
    assert all(result.get('gates',{}).get(g)=='pass' for g in ['validate','deliver','check']),result
    assert result['status']=='pass' or (result['status']=='skipped' and all(d['code']=='viewer/chrome-unavailable' for d in result.get('diagnostics',[]))),result
    results.append({'diagram':n,'command':command,'exitCode':run.returncode,'status':result['status'],'gates':result['gates'],'diagnostics':result.get('diagnostics',[]),'attempts':attempts})
recover_own_completed_states()
# Run visual evidence after all deliveries to keep directory ownership serial.
for n in names:
    repo=repos['official' if n in names[:2] else 'extended']
    visualCommand=['node',str(repo/'archify/bin/archify.mjs'),'visual-check',str(root/(n+'.html')),'--out-dir',str(root/'evidence'/('visual-'+n)),'--json']
    recover_own_completed_states()
    for visualAttempt in range(2):
        visualRun=subprocess.run(visualCommand,text=True,capture_output=True)
        visualResult=json.loads(visualRun.stdout)
        (root/'evidence'/(n+'.visual-result.json')).write_text(json.dumps(visualResult,ensure_ascii=False,indent=2))
        if visualResult['status'] in ['pass','skipped']:break
        assert all(d['code'] in ['delivery/provenance-locked','delivery/provenance-failed'] for d in visualResult.get('diagnostics',[])),visualResult
        recover_own_completed_states()
        directory=root/'evidence'/('visual-'+n)
        if directory.exists():shutil.move(str(directory),str(archive/('visual-recovery-'+n+'-'+str(visualAttempt))))
    assert visualResult['status'] in ['pass','skipped'],visualResult
recover_own_completed_states()
run=subprocess.run([sys.executable,str(root/'renderer-extension/generate_assets.py')],text=True,capture_output=True)
assert run.returncode==0,run.stderr
report={'method':'Actual finalize commands in newly extracted directory, followed by actual SVG/PNG/embedded regeneration','commands':results,'completedOwnStateRecoveries':recoveries,'priorCompletedReceiptsArchivedOutsidePackage':str(archive),'assetHashesBefore':before,'assetHashesAfter':hashes(),'allPreservedAssetsByteIdentical':before==hashes(),'browserFunctions':'Not retested by this packaging-only procedure; chrome-unavailable is skipped, not pass'}
(root/'evidence/relocated-regeneration.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
assert report['allPreservedAssetsByteIdentical'],report
print(json.dumps(report,ensure_ascii=False,indent=2))
