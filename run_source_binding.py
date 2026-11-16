"""Paired source-binding experiment. The inference process never reads labels."""
import argparse, hashlib, json, pathlib, subprocess, time, urllib.request
from medcalc.live import generate, planner_messages, extractor_messages, extraction_schema, parse_generation, make_call, evaluate_gates
from medcalc.registry import SPECS
from medcalc.source_binding import packet_for, selection_schema, selection_messages, execute_selection

ROOT=pathlib.Path(__file__).resolve().parent
CODE_FILES=['medcalc/source_binding.py','medcalc/live.py','medcalc/registry.py','medcalc/enforcement.py','run_source_binding.py']
def code_hashes():return {f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in CODE_FILES}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--phase',choices=['development','validation'],required=True);ap.add_argument('--tag',default='v1');args=ap.parse_args()
    input_file=ROOT/'data'/('live_inputs.jsonl' if args.phase=='development' else 'binding_validation_inputs.jsonl')
    cases=[json.loads(x) for x in input_file.read_text().splitlines()]
    if args.phase=='validation':
        frozen=json.loads((ROOT/'data/binding_freeze.json').read_text())
        assert frozen['code_hashes']==code_hashes(),'Code changed since freeze'
        assert frozen['input_sha256']==hashlib.sha256(input_file.read_bytes()).hexdigest(),'Validation cases changed'
    dest=ROOT/'results/binding'/(args.phase+'_'+args.tag);dest.mkdir(parents=True,exist_ok=True)
    records=dest/'cases.jsonl';journal=dest/'requests.jsonl'
    done={r['case_id'] for r in map(json.loads,records.read_text().splitlines())} if records.exists() else set()
    requests={r['key']:r for r in map(json.loads,journal.read_text().splitlines())} if journal.exists() else {}
    old_file=ROOT/'results/live/qwen2.5_1.5b_q4km_schema.jsonl'
    old={r['case_id']:r for r in map(json.loads,old_file.read_text().splitlines())} if args.phase=='development' else {}
    manifest=json.loads((ROOT/'data/open_models_manifest.json').read_text());model=manifest['models'][0]
    cache=ROOT.parent/'open_model_cache';weights=cache/model['filename']
    with weights.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==model['sha256']
    binary=cache/'runtime'/('llama-'+manifest['runtime']['release'])/'llama-server'
    command=[str(binary),'-m',str(weights),'-c','8192','-np','1','-t','8','-tb','8','-b','512','-ub','512','-ngl','0','--cache-ram','256','--host','127.0.0.1','--port','18732','--no-context-shift']
    base='http://127.0.0.1:18732'
    with (dest/'server.log').open('a') as log:
        server=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
        try:
            ready=False
            for _ in range(120):
                if server.poll() is not None:raise RuntimeError('Local model server exited')
                try:
                    with urllib.request.urlopen(base+'/health',timeout=2) as r:ready=json.load(r).get('status')=='ok'
                    if ready:break
                except Exception:pass
                time.sleep(.5)
            if not ready:raise RuntimeError('Server not ready')
            with urllib.request.urlopen(base+'/props',timeout=10) as r:props=json.load(r)
            assert props['model_path']==str(weights)
            info={'phase':args.phase,'model':model,'command':command,'properties':props,'code_hashes':code_hashes(),
                  'input_sha256':hashlib.sha256(input_file.read_bytes()).hexdigest(),'planned_cases':len(cases),
                  'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'paid_api_calls':0,
                  'old_trace_sha256':hashlib.sha256(old_file.read_bytes()).hexdigest() if old else None}
            info_path=dest/'run.json'
            if info_path.exists():assert json.loads(info_path.read_text())['code_hashes']==info['code_hashes'],'Use a new tag for changed code'
            else:info_path.write_text(json.dumps(info,indent=2)+'\n')
            def request(case_id,role,messages,cap,schema=None):
                key=case_id+'/'+role
                signature=hashlib.sha256(json.dumps([messages,cap,schema],sort_keys=True).encode()).hexdigest()
                if key in requests:
                    assert requests[key]['signature']==signature,'Request changed during resume'
                    return requests[key]['generation']
                generation=generate(base,model['id'],messages,cap,schema)
                entry={'key':key,'signature':signature,'generation':generation}
                with journal.open('a') as f:f.write(json.dumps(entry,ensure_ascii=False)+'\n')
                requests[key]=entry
                return generation
            for i,case in enumerate(cases):
                if case['case_id'] in done:continue
                start=time.perf_counter();r={k:case[k] for k in ['case_id','source_row','group_id']};r['model_id']=model['id']
                try:
                    if old:
                        previous=old[case['case_id']]
                        cid=previous['selected_calculator_id'];r['planner_reference']=case['case_id']
                        r['baseline_gates']=previous.get('gates',{})
                        r['baseline_error']=previous.get('workflow_error')
                    else:
                        plan=request(case['case_id'],'planner',planner_messages(case['question']),48)
                        r['planner']=plan;cid=parse_generation(plan).get('calculator_id')
                    r['selected_calculator_id']=cid
                    if cid not in SPECS:raise ValueError('Unknown calculator')
                    packet=packet_for(cid,case['patient_note']);r['source_packet']=packet
                    order=['source'] if old else (['baseline','source'] if i%2==0 else ['source','baseline'])
                    r['execution_order']=order
                    for mode in order:
                        if mode=='baseline':
                            try:
                                response=request(case['case_id'],'baseline',extractor_messages(case['question'],case['patient_note'],cid),768,extraction_schema(cid))
                                r['baseline_response']=response
                                call,quotes=make_call(cid,parse_generation(response))
                                r['baseline_call']=call;r['baseline_quotes']=quotes
                                r['baseline_gates']=evaluate_gates(call,quotes,case['patient_note'])
                            except Exception as e:r['baseline_error']=type(e).__name__+': '+str(e)
                        else:
                            try:
                                response=request(case['case_id'],'source',selection_messages(case['question'],case['patient_note'],packet),256,selection_schema(packet))
                                r['source_response']=response;selection=parse_generation(response)
                                r['selection']=selection
                                r['source_bound']=execute_selection(selection,packet,case['patient_note'])
                            except Exception as e:r['source_bound']={'released':False,'reason':type(e).__name__+': '+str(e)}
                except Exception as e:r['workflow_error']=type(e).__name__+': '+str(e)
                r['wall_seconds']=time.perf_counter()-start
                with records.open('a') as f:f.write(json.dumps(r,ensure_ascii=False)+'\n')
                done.add(case['case_id'])
                print(json.dumps({'phase':args.phase,'done':len(done),'case':case['case_id'],'source_released':r.get('source_bound',{}).get('released'),
                    'source_error':r.get('source_bound',{}).get('reason'),'seconds':round(r['wall_seconds'],2)}),flush=True)
        finally:
            server.terminate()
            try:server.wait(timeout=20)
            except subprocess.TimeoutExpired:server.kill();server.wait()

if __name__=='__main__':main()
