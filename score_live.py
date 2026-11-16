"""Offline scorer; never imported by the model runner or deterministic gate."""
import collections
import hashlib
import json
import math
import pathlib
import statistics

from medcalc.registry import canonical_value

ROOT = pathlib.Path(__file__).resolve().parent
GATES = ['L1_schema_only', 'L2_unit_domain', 'L3_literal_span']

def wilson(k, n):
    if not n:
        return None
    z = 1.959963984540054
    p = k/n
    d = 1+z*z/n
    a = (p+z*z/(2*n))/d
    b = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [max(0, a-b), min(1, a+b)]

def percentile(values, p):
    if not values:
        return None
    x = sorted(values)
    at = (len(x)-1)*p
    lo, hi = math.floor(at), math.ceil(at)
    return x[lo] + (at-lo)*(x[hi]-x[lo])

def correct(r, outcome, gold, strict=False):
    if not outcome.get('released') or r.get('selected_calculator_id') != gold['calculator_id']:
        return False
    v = outcome['result']
    return (math.isclose(v, float(gold['ground_truth']), rel_tol=.001, abs_tol=1e-6)
            if strict else float(gold['lower']) <= v <= float(gold['upper']))

def score(records, labels):
    n = len(records)
    counts = {'cases': n, 'source_groups': len({r['group_id'] for r in records}),
              'selected_correct_tool': 0, 'llm_calls': 0,
              'transport_failure_cases': 0,
              'prompt_tokens': 0, 'completion_tokens': 0,
              'extraction_fields_correct': 0, 'extraction_fields_expected': 0,
              'all_required_fields_correct': 0, 'workflow_errors': collections.Counter(),
              'finish_reasons': collections.Counter(), 'gates': {}}
    for r in records:
        g = labels[r['source_row']]
        cid_ok = r.get('selected_calculator_id') == g['calculator_id']
        counts['selected_correct_tool'] += cid_ok
        if r.get('workflow_error'):
            counts['workflow_errors'][r['workflow_error']] += 1
            counts['transport_failure_cases'] += r['workflow_error'].startswith(
                ('URLError:', 'HTTPError:', 'RemoteDisconnected:', 'TimeoutError:', 'ConnectionError:'))
        for role in ['planner', 'extractor']:
            if role not in r:
                continue
            counts['llm_calls'] += 1
            counts['finish_reasons'][r[role]['finish_reason']] += 1
            usage = r[role]['response'].get('usage', {})
            counts['prompt_tokens'] += usage.get('prompt_tokens', 0)
            counts['completion_tokens'] += usage.get('completion_tokens', 0)
        matched = 0
        for field, target in g['quantities'].items():
            counts['extraction_fields_expected'] += 1
            try:
                entry = r['call']['arguments'][field]
                a = canonical_value(field, entry['value'], entry['unit'])
                b = canonical_value(field, target['value'], target['unit'])
                ok = cid_ok and (a == b if isinstance(a, str) else math.isclose(a, b, rel_tol=1e-6, abs_tol=1e-8))
            except (KeyError, TypeError, ValueError):
                ok = False
            matched += ok
        counts['extraction_fields_correct'] += matched
        counts['all_required_fields_correct'] += matched == len(g['quantities'])
    counts['wall_seconds'] = sum(r['wall_seconds'] for r in records)
    counts['workflow_seconds_median'] = statistics.median(r['wall_seconds'] for r in records) if n else None
    counts['workflow_seconds_p95'] = percentile([r['wall_seconds'] for r in records], .95)
    for name in GATES:
        release = good = strict_good = execution_errors = 0
        reason = collections.Counter()
        latencies = []
        for r in records:
            o = r.get('gates', {}).get(name, {})
            release += bool(o.get('released'))
            good += correct(r, o, labels[r['source_row']])
            strict_good += correct(r, o, labels[r['source_row']], strict=True)
            execution_errors += o.get('stage') == 'executor'
            if not o.get('released'):
                reason[o.get('reason', r.get('workflow_error', 'No call'))] += 1
            if 'gate_ms' in o:
                latencies.append(o['gate_ms'])
        counts['gates'][name] = {'released': release, 'correct_released': good,
            'strict_0_1pct_correct_released': strict_good, 'incorrect_released': release-good,
            'blocked_or_failed': n-release, 'execution_errors': execution_errors,
            'end_to_end_accuracy': good/n if n else None,
            'end_to_end_accuracy_wilson95': wilson(good, n),
            'incorrect_release_rate': (release-good)/n if n else None,
            'coverage': release/n if n else None,
            'accuracy_among_released': good/release if release else None,
            'reasons': reason, 'gate_ms_p50': percentile(latencies, .5),
            'gate_ms_p95': percentile(latencies, .95)}
    counts['literal_gate_blocked_otherwise_numerically_correct'] = sum(
        correct(r, r.get('gates', {}).get('L2_unit_domain', {}), labels[r['source_row']])
        and not r.get('gates', {}).get('L3_literal_span', {}).get('released', False)
        for r in records)
    counts['literal_gate_blocked_otherwise_numerically_incorrect'] = sum(
        r.get('gates', {}).get('L2_unit_domain', {}).get('released', False)
        and not correct(r, r['gates']['L2_unit_domain'], labels[r['source_row']])
        and not r['gates']['L3_literal_span'].get('released', False) for r in records)
    return counts

def main():
    labels = {r['source_row']: r for r in map(json.loads, (ROOT/'data/pilot_rows.jsonl').read_text().splitlines())}
    dest = ROOT/'results/live'
    summary = {'status': 'development pilot; not held-out clinical validation',
               'models': {}, 'paid_api_cost_usd': 0, 'scored_files': {}}
    details = []
    for path in sorted(dest.glob('*.jsonl')):
        records = [json.loads(s) for s in path.read_text().splitlines()]
        if not records:
            continue
        if len({r['case_id'] for r in records}) != len(records):
            raise ValueError('Duplicate case in '+path.name)
        summary['models'][path.stem] = score(records, labels)
        summary['scored_files'][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        for r in records:
            g = labels[r['source_row']]
            detail = {k:r.get(k) for k in ['case_id','model_id','selected_calculator_id','workflow_error']}
            detail.update({'expected_calculator_id':g['calculator_id'], 'reference':g['ground_truth'],
                           'lower':g['lower'], 'upper':g['upper'], 'gates':{}})
            for name in GATES:
                o = r.get('gates',{}).get(name,{})
                detail['gates'][name] = dict(o, correct_within_interval=correct(r,o,g),
                                             correct_within_0_1pct=correct(r,o,g,True))
            details.append(detail)
    (dest/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    (dest/'scored_cases.json').write_text(json.dumps(details,indent=2)+'\n')
    print(json.dumps(summary,indent=2))

if __name__ == '__main__':
    main()
