"""Audit frozen inputs, paired replay, request integrity, and preservation of v0.2."""
import argparse, collections, hashlib, json, pathlib, re, statistics, zipfile
from medcalc.live import planner_messages, extractor_messages, extraction_schema, parse_generation, make_call, evaluate_gates
from run_source_repair import code_hashes, apply_repair
from medcalc.source_repair import make_source_packet
ROOT=pathlib.Path(__file__).resolve().parent

def rows(path):return [json.loads(s) for s in path.read_text().splitlines()]
def normalized(note):return hashlib.sha256(' '.join(note.split()).lower().encode()).hexdigest()
def article(group):
    m=re.match(r'(pmc-\d+)',group)
    return m.group(1) if m else group

def without_timing(obj):
    if isinstance(obj,dict):return {k:without_timing(v) for k,v in obj.items() if k!='gate_ms'}
    if isinstance(obj,list):return [without_timing(x) for x in obj]
    return obj

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--previous-archive',type=pathlib.Path);args=parser.parse_args()
    frozen=json.loads((ROOT/'data/binding_freeze.json').read_text())
    assert frozen['code_hashes']==code_hashes()
    val_path=ROOT/'data/binding_validation_inputs.jsonl'
    assert hashlib.sha256(val_path.read_bytes()).hexdigest()==frozen['input_sha256']
    inputs=rows(val_path);dev=rows(ROOT/'data/live_inputs.jsonl')
    inp={x['case_id']:x for x in inputs}
    assert len(inputs)==len(inp)==50
    for key in ['case_id','source_row','group_id']:
        assert not ({x[key] for x in inputs}&{x[key] for x in dev})
    for fn in [lambda x:article(x['group_id']),lambda x:normalized(x['patient_note'])]:
        assert not ({fn(x) for x in inputs}&{fn(x) for x in dev})
        assert len({fn(x) for x in inputs})==50
    allowed={'case_id','source_row','group_id','note_id','note_type','patient_note','question'}
    assert all(set(x)==allowed for x in inputs)
    labels={x['source_row']:x for x in rows(ROOT/'data/pilot_rows.jsonl')}
    counts=collections.Counter(labels[x['source_row']]['calculator_id'] for x in inputs)
    assert len(counts)==10 and set(counts.values())=={5}
    folder=ROOT/'results/binding/validation_repair_v2'
    cases=rows(folder/'cases.jsonl');requests=rows(folder/'requests.jsonl')
    assert len(cases)==len({r['case_id'] for r in cases})==50
    assert {r['case_id'] for r in cases}==set(inp)
    rq={r['key']:r for r in requests}
    assert len(rq)==len(requests)
    checked=0
    for r in cases:
        x=inp[r['case_id']]
        for role,messages,cap,schema in [
            ('planner',planner_messages(x['question']),48,None),
            ('baseline',extractor_messages(x['question'],x['patient_note'],r['selected_calculator_id']),768,extraction_schema(r['selected_calculator_id']))]:
            entry=rq[r['case_id']+'/'+role];g=entry['generation'];request=g['request']
            assert request['messages']==messages
            assert request['max_tokens']==cap and request['seed']==731 and request['temperature']==0
            assert request['response_format'].get('schema')==schema
            assert entry['signature']==hashlib.sha256(json.dumps([messages,cap,schema],sort_keys=True).encode()).hexdigest()
            assert g==r['planner' if role=='planner' else 'baseline_response']
            checked+=1
        if 'baseline_call' in r:
            call,quotes=make_call(r['selected_calculator_id'],parse_generation(r['baseline_response']))
            assert call==r['baseline_call'] and quotes==r['baseline_quotes']
            assert without_timing(evaluate_gates(call,quotes,x['patient_note']))==without_timing(r['baseline_gates'])
            assert make_source_packet(r['selected_calculator_id'],x['patient_note'])==r['source_packet']
        copied=dict(r);apply_repair(copied,x['patient_note'])
        assert without_timing(copied['source_bound'])==without_timing(r['source_bound'])
        for evidence in r['source_bound'].get('evidence',{}).values():
            assert x['patient_note'][evidence['start']:evidence['end']]==evidence['source']
    assert checked==len(requests)==100
    preserved=[]
    if args.previous_archive:
        with zipfile.ZipFile(args.previous_archive) as z:
            names=z.namelist()
            targets=['data/pilot_rows.jsonl','data/live_inputs.jsonl','results/live/qwen2.5_1.5b_q4km_schema.jsonl','medcalc/live.py','medcalc/registry.py','medcalc/enforcement.py']
            for path in targets:
                name=next(n for n in names if n.endswith('/'+path) or n==path)
                assert z.read(name)==(ROOT/path).read_bytes(),path
                preserved.append(path)
    tokens=collections.Counter()
    for entry in requests:
        tokens.update({k:v for k,v in entry['generation']['response'].get('usage',{}).items() if isinstance(v,(int,float))})
    repair_ms=[r['source_bound']['gate_ms'] for r in cases if 'gate_ms' in r['source_bound']]
    out={'frozen_code_and_input_hashes_match':True,'validation_cases':50,'development_article_and_text_overlap':0,
        'unique_validation_articles':50,'unique_validation_texts':50,'input_only_fields':sorted(allowed),
        'validation_counts_per_calculator':dict(counts),'completed_requests_checked':checked,'duplicate_request_keys':0,
        'raw_generation_to_call_replay_matches':True,'all_baseline_gate_replays_match':True,'all_source_repair_replays_match':True,
        'released_source_spans_match':True,'preserved_v0_2_files_byte_identical':preserved,
        'token_usage':dict(tokens),'finish_reasons':dict(collections.Counter(r['generation']['finish_reason'] for r in requests)),
        'repair_gate_ms':{'n_released_with_timings':len(repair_ms),'median':statistics.median(repair_ms),'max':max(repair_ms),
            'scope':'Successful repair only, excludes initial packet construction; descriptive shared-CPU timings, not an end-to-end latency benchmark.'}}
    (folder/'audit.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
if __name__=='__main__':main()
