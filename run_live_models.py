"""Run two isolated LLM roles locally; labels are used only by a separate scorer."""
import argparse
import hashlib
import json
import pathlib
import subprocess
import time
import urllib.request

from medcalc.live import (generate, planner_messages, extractor_messages,
                          parse_generation, make_call, evaluate_gates, extraction_schema)
from medcalc.registry import SPECS

ROOT = pathlib.Path(__file__).resolve().parent

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cache', type=pathlib.Path, default=ROOT.parent/'open_model_cache')
    ap.add_argument('--limit', type=int, default=50)
    ap.add_argument('--model', default='all')
    ap.add_argument('--mode', choices=['object', 'schema'], default='object')
    ap.add_argument('--cache-ram', type=int, default=256)
    args = ap.parse_args()
    manifest = json.loads((ROOT/'data/open_models_manifest.json').read_text())
    inputs_path = ROOT/'data/live_inputs.jsonl'
    inputs = [json.loads(s) for s in inputs_path.read_text().splitlines()][:args.limit]
    dest = ROOT/'results/live'; dest.mkdir(parents=True, exist_ok=True)
    runtime = args.cache/'runtime'/('llama-'+manifest['runtime']['release'])/'llama-server'
    base = 'http://127.0.0.1:18731'
    for model in manifest['models']:
        if args.model != 'all' and model['id'] != args.model:
            continue
        run_id = model['id'] + ('_schema' if args.mode == 'schema' else '')
        path = dest/(run_id+'.jsonl')
        done = {json.loads(s)['case_id'] for s in path.read_text().splitlines()} if path.exists() else set()
        if all(x['case_id'] in done for x in inputs):
            continue
        weights = args.cache/model['filename']
        if hashlib.file_digest(weights.open('rb'), 'sha256').hexdigest() != model['sha256']:
            raise ValueError('Model hash does not match pinned manifest')
        cmd = [str(runtime), '-m', str(weights), '-c', '8192', '-np', '1',
               '-t', '8', '-tb', '8', '-b', '512', '-ub', '512', '-ngl', '0',
               '--cache-ram', str(args.cache_ram),
               '--host', '127.0.0.1', '--port', '18731', '--no-context-shift']
        log_path = dest/(run_id+'_server.log')
        with log_path.open('a') as log:
            server = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
            try:
                ready = False
                for _ in range(120):
                    if server.poll() is not None:
                        raise RuntimeError('Model server exited; see ' + str(log_path))
                    try:
                        with urllib.request.urlopen(base+'/health', timeout=2) as r:
                            ready = json.load(r).get('status') == 'ok'
                        if ready:
                            break
                    except Exception:
                        pass
                    time.sleep(0.5)
                if not ready:
                    raise RuntimeError('Model loading timeout')
                with urllib.request.urlopen(base+'/props', timeout=10) as r:
                    props = json.load(r)
                run_info = {'model': model, 'command': cmd, 'mode': args.mode,
                            'cache_ram_mib': args.cache_ram,
                            'existing_cases_at_resume': sorted(done),
                            'runtime_version': subprocess.run([str(runtime), '--version'],
                              capture_output=True, text=True).stderr.strip(),
                            'input_sha256': hashlib.sha256(inputs_path.read_bytes()).hexdigest(),
                            'properties': props, 'planned_cases': len(inputs),
                            'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                            'schema_constrained_decoding': args.mode,
                            'paid_api_calls': 0, 'repairs': 0}
                (dest/(run_id+'_run.json')).write_text(json.dumps(run_info, indent=2)+'\n')
                for item in inputs:
                    if item['case_id'] in done:
                        continue
                    record = {'case_id': item['case_id'], 'group_id': item['group_id'],
                              'source_row': item['source_row'], 'model_id': model['id'],
                              'cache_ram_mib': args.cache_ram, 'decoding_mode': args.mode}
                    started = time.perf_counter()
                    try:
                        record['planner'] = generate(base, model['id'],
                            planner_messages(item['question']), 48)
                        selection = parse_generation(record['planner'])
                        cid = selection.get('calculator_id')
                        record['selected_calculator_id'] = cid
                        if not isinstance(cid, str) or cid not in SPECS:
                            raise ValueError('Unknown or missing selected calculator')
                        record['extractor'] = generate(base, model['id'],
                            extractor_messages(item['question'], item['patient_note'], cid), 768,
                            schema=extraction_schema(cid) if args.mode == 'schema' else None)
                        extracted = parse_generation(record['extractor'])
                        call, quotes = make_call(cid, extracted)
                        record['call'] = call
                        record['quotes'] = quotes
                        record['gates'] = evaluate_gates(call, quotes, item['patient_note'])
                    except Exception as e:
                        record['workflow_error'] = type(e).__name__ + ': ' + str(e)
                    record['wall_seconds'] = time.perf_counter()-started
                    with path.open('a') as f:
                        f.write(json.dumps(record, ensure_ascii=False)+'\n')
                        f.flush()
                    done.add(item['case_id'])
                    print(json.dumps({'model': model['id'], 'done': len(done),
                        'case': item['case_id'], 'seconds': round(record['wall_seconds'], 2),
                        'error': record.get('workflow_error'),
                        'released': {k:v['released'] for k,v in record.get('gates',{}).items()}}), flush=True)
            finally:
                server.terminate()
                try:
                    server.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    server.kill(); server.wait()

if __name__ == '__main__':
    main()
