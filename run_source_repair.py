"""Frozen paired test: same model calls, different deterministic execution gates."""
import argparse,hashlib,json,pathlib,subprocess,time,urllib.request
from medcalc.live import generate,planner_messages,extractor_messages,extraction_schema,parse_generation,make_call,evaluate_gates
from medcalc.registry import SPECS
from medcalc.source_repair import make_source_packet,repair_call
ROOT=pathlib.Path(__file__).resolve().parent
CODE_FILES=['medcalc/source_binding.py','medcalc/source_repair.py','medcalc/live.py','medcalc/registry.py','medcalc/enforcement.py','run_source_repair.py']
def code_hashes():return {f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in CODE_FILES}

def apply_repair(r,note):
    try:
        if 'baseline_call' not in r:raise ValueError('BASELINE_EXTRACTION_FAILED')
        p=make_source_packet(r['selected_calculator_id'],note);r['source_packet']=p
        start=time.perf_counter();r['source_bound']=repair_call(r['baseline_call'],p,note)
        r['source_bound']['gate_ms']=(time.perf_counter()-start)*1000
    except Exception as e:r['source_bound']={'released':False,'reason':type(e).__name__+': '+str(e)}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--phase',choices=['development','validation'],required=True);ap.add_argument('--tag',default='repair_v2');args=ap.parse_args()
    inputs_path=ROOT/'data'/('live_inputs.jsonl' if args.phase=='development' else 'binding_validation_inputs.jsonl')
    cases=[json.loads(x) for x in inputs_path.read_text().splitlines()]
    dest=ROOT/'results/binding'/(args.phase+'_'+args.tag);dest.mkdir(parents=True,exist_ok=True)
    path=dest/'cases.jsonl';journal=dest/'requests.jsonl'
    if args.phase=='development':
        old_file=ROOT/'results/live/qwen2.5_1.5b_q4km_schema.jsonl'
        old={r['case_id']:r for r in map(json.loads,old_file.read_text().splitlines())}
        info={'phase':'development','replay_only':True,'new_llm_calls':0,'code_hashes':code_hashes(),
              'input_sha256':hashlib.sha256(inputs_path.read_bytes()).hexdigest(),
              'old_trace_sha256':hashlib.sha256(old_file.read_bytes()).hexdigest()}
        records=[]
        for x in cases:
            o=old[x['case_id']];start=time.perf_counter()
            r={k:x[k] for k in ['case_id','source_row','group_id']}
            r.update(selected_calculator_id=o.get('selected_calculator_id'),baseline_gates=o.get('gates',{}),baseline_error=o.get('workflow_error'),planner_reference=x['case_id'])
            if 'call' in o:r['baseline_call']=o['call']
            apply_repair(r,x['patient_note']);r['wall_seconds']=time.perf_counter()-start;records.append(r)
        path.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in records));journal.write_text('')
        (dest/'run.json').write_text(json.dumps(info,indent=2)+'\n');print('Replayed',len(records),'development cases');return
    frozen=json.loads((ROOT/'data/binding_freeze.json').read_text())
    assert frozen['code_hashes']==code_hashes(),'Code changed after validation freeze'
    assert frozen['input_sha256']==hashlib.sha256(inputs_path.read_bytes()).hexdigest(),'Validation inputs changed'
    done={r['case_id'] for r in map(json.loads,path.read_text().splitlines())} if path.exists() else set()
    requests={r['key']:r for r in map(json.loads,journal.read_text().splitlines())} if journal.exists() else {}
    manifest=json.loads((ROOT/'data/open_models_manifest.json').read_text());model=manifest['models'][0]
    cache=ROOT.parent/'open_model_cache';weights=cache/model['filename'];binary=cache/'runtime'/('llama-'+manifest['runtime']['release'])/'llama-server'
    with weights.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==model['sha256']
    command=[str(binary),'-m',str(weights),'-c','8192','-np','1','-t','8','-tb','8','-b','512','-ub','512','-ngl','0','--cache-ram','256','--host','127.0.0.1','--port','18732','--no-context-shift']
    base='http://127.0.0.1:18732'
    with (dest/'server.log').open('a') as log:
        server=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
        try:
            ready=False
            for _ in range(120):
                if server.poll() is not None:raise RuntimeError('Server exited')
                try:
                    with urllib.request.urlopen(base+'/health',timeout=2) as r:ready=json.load(r).get('status')=='ok'
                    if ready:break
                except Exception:pass
                time.sleep(.5)
            if not ready:raise RuntimeError('Server timeout')
            with urllib.request.urlopen(base+'/props',timeout=10) as r:props=json.load(r)
            assert props['model_path']==str(weights)
            info={'phase':'validation','model':model,'command':command,'properties':props,'code_hashes':code_hashes(),
                  'input_sha256':frozen['input_sha256'],'planned_cases':len(cases),'paid_api_calls':0,
                  'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'method':'deterministic source repair of common generated call'}
            info_path=dest/'run.json'
            if info_path.exists():assert json.loads(info_path.read_text())['code_hashes']==info['code_hashes']
            else:info_path.write_text(json.dumps(info,indent=2)+'\n')
            def request(case_id,role,messages,cap,schema=None):
                key=case_id+'/'+role;signature=hashlib.sha256(json.dumps([messages,cap,schema],sort_keys=True).encode()).hexdigest()
                if key in requests:
                    assert requests[key]['signature']==signature;return requests[key]['generation']
                generation=generate(base,model['id'],messages,cap,schema)
                entry={'key':key,'signature':signature,'generation':generation}
                with journal.open('a') as f:f.write(json.dumps(entry,ensure_ascii=False)+'\n')
                requests[key]=entry;return generation
            for x in cases:
                if x['case_id'] in done:continue
                start=time.perf_counter();r={k:x[k] for k in ['case_id','source_row','group_id']};r['model_id']=model['id']
                try:
                    r['planner']=request(x['case_id'],'planner',planner_messages(x['question']),48)
                    cid=parse_generation(r['planner']).get('calculator_id');r['selected_calculator_id']=cid
                    if cid not in SPECS:raise ValueError('Unknown calculator')
                    r['baseline_response']=request(x['case_id'],'baseline',extractor_messages(x['question'],x['patient_note'],cid),768,extraction_schema(cid))
                    call,quotes=make_call(cid,parse_generation(r['baseline_response']))
                    r['baseline_call']=call;r['baseline_quotes']=quotes;r['baseline_gates']=evaluate_gates(call,quotes,x['patient_note'])
                except Exception as e:r['baseline_error']=type(e).__name__+': '+str(e)
                apply_repair(r,x['patient_note']);r['wall_seconds']=time.perf_counter()-start
                with path.open('a') as f:f.write(json.dumps(r,ensure_ascii=False)+'\n')
                done.add(x['case_id'])
                print(json.dumps({'done':len(done),'case':x['case_id'],'released':r['source_bound']['released'],'reason':r['source_bound'].get('reason'),'seconds':round(r['wall_seconds'],2)}),flush=True)
        finally:
            server.terminate()
            try:server.wait(timeout=20)
            except subprocess.TimeoutExpired:server.kill();server.wait()
if __name__=='__main__':main()
