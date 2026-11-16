"""Offline audit of locked cohort membership, transcripts, paired outcomes and reported counts."""
import argparse
import collections
import hashlib
import json
import pathlib

from medcalc.live import (evaluate_gates, extraction_schema, extractor_messages, make_call,
                          parse_generation, planner_messages)
from medcalc.registry import SPECS
from official_study import INPUTS, LOCK, REFERENCES, RESULTS, digest, read_lines, validate_lock
from run_source_repair import apply_repair
from score_source_binding import agrees, outcome


def strip_timings(value):
    if isinstance(value, dict):
        return {k: strip_timings(v) for k,v in value.items() if k != 'gate_ms'}
    return value


def verify_request(entry, messages, cap, schema, model_id):
    generation=entry['generation']
    request=generation['request']
    signature=hashlib.sha256(json.dumps([messages,cap,schema],sort_keys=True).encode()).hexdigest()
    assert entry['signature']==signature
    assert request['messages']==messages and request['model']==model_id
    assert request['max_tokens']==cap and request['seed']==731 and request['temperature']==0
    assert request['response_format'].get('schema')==schema
    assert generation['text']==(generation['response']['choices'][0]['message'].get('content') or '')
    assert generation['finish_reason']==generation['response']['choices'][0]['finish_reason']
    return generation


def audit_model(model_id):
    lock=validate_lock()
    assert lock['reference_sha256']==digest(REFERENCES)
    inputs={r['case_id']:r for r in read_lines(INPUTS)}
    labels={r['case_id']:r for r in read_lines(REFERENCES)}
    assert set(inputs)==set(labels) and len(inputs)==lock['selected']
    assert len({r['group_id'] for r in inputs.values()})==len(inputs)
    assert len({' '.join(r['patient_note'].lower().split()) for r in inputs.values()})==len(inputs)
    folder=RESULTS/model_id
    expected_prompts=set()
    raw_requests=read_lines(folder/'requests.jsonl')
    requests={r['key']:r for r in raw_requests}
    assert len(requests)==len(raw_requests)
    records=read_lines(folder/'cases.jsonl')
    assert len(records)==len(inputs) and set(r['case_id'] for r in records)==set(inputs)
    transitions=collections.Counter()
    method_counts=collections.defaultdict(collections.Counter)
    reasons=collections.Counter()
    matched_tools=0
    for case in records:
        identifier=case['case_id']
        row=inputs[identifier]
        assert case['group_id']==row['group_id'] and case['source_row']==row['source_row']
        assert case['model_id']==model_id
        planner_key=identifier+'/planner'
        expected_prompts.add(planner_key)
        planner=verify_request(requests[planner_key],planner_messages(row['question']),48,None,model_id)
        try:
            cid=parse_generation(planner).get('calculator_id')
        except (ValueError, TypeError):
            cid=None
        assert case.get('selected_calculator_id')==cid
        matched_tools+=int(cid==labels[identifier]['calculator_id'])
        if isinstance(cid, str) and cid in SPECS:
            extractor_key=identifier+'/baseline'
            expected_prompts.add(extractor_key)
            extraction=verify_request(requests[extractor_key],extractor_messages(row['question'],row['patient_note'],cid),
                                      768,extraction_schema(cid),model_id)
            try:
                proposal,quotes=make_call(cid,parse_generation(extraction))
            except (ValueError,TypeError,KeyError):
                assert 'baseline_call' not in case
            else:
                assert proposal==case['baseline_call'] and quotes==case['baseline_quotes']
                assert strip_timings(evaluate_gates(proposal,quotes,row['patient_note']))==strip_timings(case['baseline_gates'])
        rerun={k:case[k] for k in ('selected_calculator_id','baseline_call') if k in case}
        apply_repair(rerun,row['patient_note'])
        assert strip_timings(rerun['source_bound'])==strip_timings(case['source_bound'])
        if 'source_packet' in rerun:
            assert rerun['source_packet']==case['source_packet']
        for field in rerun['source_bound'].get('evidence',{}).values():
            assert row['patient_note'][field['start']:field['end']]==field['source']
        statuses={}
        for method in ('L1_schema_only','L2_unit_domain','L3_literal_span','source_bound'):
            decision=outcome(case,method)
            status='matched' if agrees(case,method,labels[identifier]) else ('nonmatching_released' if decision.get('released') else 'blocked_or_failed')
            method_counts[method][status]+=1
            statuses[method]=status
        transitions[statuses['L2_unit_domain']+' to '+statuses['source_bound']]+=1
        if not case['source_bound'].get('released'):
            reasons[case.get('baseline_error') or case['source_bound'].get('reason','unspecified')]+=1
    assert expected_prompts==set(requests)
    summary=json.loads((folder/'summary.json').read_text())
    for method,counts in method_counts.items():
        for status in ('matched','nonmatching_released','blocked_or_failed'):
            assert counts[status]==summary['methods'][method][status]
    finish_reasons=collections.Counter(r['generation']['finish_reason'] for r in raw_requests)
    out={'model':model_id,'locked_utc':lock['locked_utc'],'requests_verified':len(requests),
         'complete_unique_cases':len(records),'tool_selected_matches':matched_tools,
         'finish_reasons':dict(finish_reasons),'paired_transitions_L2_to_repair':dict(transitions),
         'source_repair_failure_reasons':dict(reasons),'all_logged_proposals_and_decisions_reproduced':True,
         'all_reported_outcome_counts_reproduced':True,'unique_source_keys_and_normalized_notes':len(inputs)}
    (folder/'audit.json').write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps(out,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model',default='all')
    args=parser.parse_args()
    for model in json.loads(LOCK.read_text())['planned_models']:
        if args.model in ('all',model['id']):
            audit_model(model['id'])
