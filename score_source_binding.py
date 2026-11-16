"""Evaluation only: references never enter source_binding or its model runner."""
import argparse, collections, json, math, pathlib, random
from score_live import wilson
ROOT=pathlib.Path(__file__).resolve().parent
METHODS=['L2_unit_domain','L3_literal_span','source_bound']

def outcome(r,method):
    return r.get('source_bound',{}) if method=='source_bound' else r.get('baseline_gates',{}).get(method,{})

def agrees(r,method,g,strict=False):
    o=outcome(r,method)
    if not o.get('released') or r.get('selected_calculator_id')!=g['calculator_id']:return False
    return math.isclose(o['result'],float(g['ground_truth']),rel_tol=.001,abs_tol=1e-6) if strict else float(g['lower'])<=o['result']<=float(g['upper'])

def paired(records,labels,a,b):
    changes=[(agrees(r,a,labels[r['source_row']]),agrees(r,b,labels[r['source_row']])) for r in records]
    gain=sum(not x and y for x,y in changes);loss=sum(x and not y for x,y in changes);discordant=gain+loss
    exact=min(1.,2*sum(math.comb(discordant,k) for k in range(min(gain,loss)+1))/2**discordant) if discordant else 1.
    by_tool=collections.defaultdict(list)
    for r,(x,y) in zip(records,changes):by_tool[labels[r['source_row']]['calculator_id']].append(int(y)-int(x))
    rng=random.Random(731);samples=[]
    for _ in range(2000):
        draws=[rng.choice(v) for v in by_tool.values() for _ in v]
        samples.append(sum(draws)/len(draws))
    samples.sort()
    return {'from':a,'to':b,'gained_matching_answers':gain,'lost_matching_answers':loss,
            'agreement_delta':(gain-loss)/len(records),'stratified_bootstrap95':[samples[49],samples[1949]],
            'paired_exact_mcnemar_p':exact,'scope':'Exploratory; bootstrap stratified by calculator, not clinical population inference.'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--phase',choices=['development','validation'],required=True);ap.add_argument('--tag',default='v1');args=ap.parse_args()
    folder=ROOT/'results/binding'/(args.phase+'_'+args.tag)
    records=[json.loads(s) for s in (folder/'cases.jsonl').read_text().splitlines()]
    if not records:return
    labels={r['source_row']:r for r in map(json.loads,(ROOT/'data/pilot_rows.jsonl').read_text().splitlines())}
    requests=[json.loads(s) for s in (folder/'requests.jsonl').read_text().splitlines()]
    n=len(records);summary={'phase':args.phase,'cases':n,'unique_groups':len({r['group_id'] for r in records}),
           'new_llm_calls':len(requests),'new_calls_by_role':dict(collections.Counter(r['key'].split('/')[-1] for r in requests)),
           'selected_correct_tool':sum(r.get('selected_calculator_id')==labels[r['source_row']]['calculator_id'] for r in records),
           'wall_seconds':sum(r['wall_seconds'] for r in records),'methods':{},'comparisons':[],'paid_api_cost_usd':0}
    details=[]
    for method in METHODS:
        released=sum(bool(outcome(r,method).get('released')) for r in records)
        good=sum(agrees(r,method,labels[r['source_row']]) for r in records)
        strict=sum(agrees(r,method,labels[r['source_row']],True) for r in records)
        by_tool={}
        for cid in sorted({labels[r['source_row']]['calculator_id'] for r in records},key=int):
            rr=[r for r in records if labels[r['source_row']]['calculator_id']==cid]
            by_tool[cid]={'n':len(rr),'matched':sum(agrees(r,method,labels[r['source_row']]) for r in rr),
                          'released':sum(bool(outcome(r,method).get('released')) for r in rr)}
        summary['methods'][method]={'matched':good,'strict_0_1pct_matched':strict,'nonmatching_released':released-good,
            'blocked_or_failed':n-released,'released':released,'agreement':good/n,'agreement_wilson95':wilson(good,n),
            'matching_fraction_of_released':good/released if released else None,'by_calculator':by_tool,
            'block_reasons':dict(collections.Counter(outcome(r,method).get('reason',r.get('baseline_error',r.get('workflow_error','no output')))
                                  for r in records if not outcome(r,method).get('released')))}
    summary['comparisons']=[paired(records,labels,x,'source_bound') for x in ['L2_unit_domain','L3_literal_span']]
    for r in records:
        g=labels[r['source_row']]
        details.append({'case_id':r['case_id'],'source_row':r['source_row'],'expected_calculator':g['calculator_id'],
            'benchmark_answer':g['ground_truth'],'methods':{m:{'matched':agrees(r,m,g),**outcome(r,m)} for m in METHODS}})
    (folder/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    (folder/'scored_cases.json').write_text(json.dumps(details,indent=2)+'\n')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
