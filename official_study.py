"""Prepare a source-disjoint official-test sample, run pinned local models, and score it."""
import argparse
import collections
import concurrent.futures
import contextlib
import csv
import hashlib
import json
import os
import pathlib
import re
import subprocess
import threading
import time
import urllib.error
import urllib.request

from medcalc.live import (evaluate_gates, extraction_schema, extractor_messages, generate,
                          make_call, parse_generation, planner_messages)
from medcalc.registry import SPECS
from run_source_repair import apply_repair, code_hashes
from score_source_binding import agrees, outcome, paired
from score_live import wilson

ROOT = pathlib.Path(__file__).resolve().parent
DATA = ROOT / 'data'
LOCK = DATA / 'official_lock.json'
INPUTS = DATA / 'official_locked_inputs.jsonl'
REFERENCES = DATA / 'official_reference.jsonl'
RESULTS = ROOT / 'results/official'
TARGET_PER_CALCULATOR = 5
SELECTION_SEED = 'medcalc-official-731-v1'


def read_lines(path):
    return [json.loads(s) for s in path.read_text().splitlines()] if path.exists() else []


def write_new_or_identical(path, data):
    if path.exists() and path.read_bytes() != data:
        raise ValueError(f'Existing file differs: {path}. Use a new study folder for another cohort.')
    if not path.exists():
        path.write_bytes(data)


def digest(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def utc():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def source_keys(row):
    note_id = row['Note ID'].strip().lower()
    pmc = re.search(r'pmc-\d+', note_id)
    if pmc:
        source = pmc.group()
    elif note_id.startswith('usmle-'):
        source = note_id
    else:
        source = '/'.join((row['Calculator ID'], row['Note Type'].lower(), note_id))
    normalized = ' '.join(row['Patient Note'].lower().split())
    return source, hashlib.sha256(normalized.encode()).hexdigest()


def to_jsonl(rows):
    return ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows).encode()


def prepare(raw):
    manifest = json.loads((DATA / 'download_manifest.json').read_text())
    corpora = {}
    hashes = {}
    for entry in manifest:
        if entry['dataset'] != 'verified':
            continue
        path = raw / pathlib.Path(entry['local_path']).relative_to('data/raw')
        hashes[entry['file']] = digest(path)
        if hashes[entry['file']] != entry['sha256']:
            raise ValueError(f'Wrong source bytes: {path}')
        with path.open(encoding='utf-8', newline='') as file:
            corpora[entry['file']] = list(csv.DictReader(file))
    known = corpora['train_data.csv'] + corpora['one_shot_data.csv']
    used_sources = {source_keys(row)[0] for row in known}
    used_text = {source_keys(row)[1] for row in known}
    pools = collections.defaultdict(list)
    for row in corpora['test_data.csv']:
        calculator = row['Calculator ID']
        if calculator not in SPECS:
            continue
        group, note_hash = source_keys(row)
        if group in used_sources or note_hash in used_text:
            continue
        rank = hashlib.sha256(f"{SELECTION_SEED}|{calculator}|{row['Row Number']}".encode()).hexdigest()
        pools[calculator].append((rank, group, note_hash, row))
    selected = []
    for calculator in sorted(SPECS, key=int):
        count = 0
        for _, group, note_hash, row in sorted(pools[calculator]):
            if group in used_sources or note_hash in used_text:
                continue
            selected.append((row, group))
            used_sources.add(group)
            used_text.add(note_hash)
            count += 1
            if count == TARGET_PER_CALCULATOR:
                break
    inputs, references = [], []
    for row, group in selected:
        key = row['Row Number']
        inputs.append(dict(case_id='official-' + key, source_row=key, group_id=group,
                           note_id=row['Note ID'], note_type=row['Note Type'],
                           patient_note=row['Patient Note'], question=row['Question']))
        references.append(dict(case_id='official-' + key, source_row=key, calculator_id=row['Calculator ID'],
                               ground_truth=row['Ground Truth Answer'], lower=row['Lower Limit'], upper=row['Upper Limit']))
    write_new_or_identical(INPUTS, to_jsonl(inputs))
    write_new_or_identical(REFERENCES, to_jsonl(references))
    record = dict(dataset_hashes=hashes, selected=len(selected),
                  candidate_rows_by_calculator={k: len(pools[k]) for k in SPECS},
                  selected_by_calculator=dict(collections.Counter(row['calculator_id'] for row in references)),
                  planned_models=json.loads((DATA/'open_models_manifest.json').read_text())['models'],
                  code_hashes=code_hashes(), runner_sha256=digest(pathlib.Path(__file__)),
                  input_sha256=digest(INPUTS), reference_sha256=digest(REFERENCES),
                  selection_seed=SELECTION_SEED, maximum_each=TARGET_PER_CALCULATOR,
                  selection='Official test only. Exclude all train and one-shot source keys and normalized notes. Source key is PMC article, USMLE identifier or calculator/type-scoped note ID. Then globally deduplicate selected sources and text. No filtering by answer, extracted entities, note length, model behavior or parser coverage.',
                  primary_outcomes='For each model separately report matching, nonmatching released and blocked counts across every selected case. Compare all policies on the same model call. No replacements, prompt tuning or selective retries.')
    if LOCK.exists():
        old = json.loads(LOCK.read_text())
        old.pop('locked_utc')
        if old != record:
            raise ValueError('Existing lock differs from regenerated study')
    else:
        record['locked_utc'] = utc()
        LOCK.write_text(json.dumps(record, indent=2) + '\n')
    print('Locked', len(selected), 'official cases:', record['selected_by_calculator'], flush=True)


def validate_lock():
    lock = json.loads(LOCK.read_text())
    if lock['input_sha256'] != digest(INPUTS) or lock['code_hashes'] != code_hashes():
        raise ValueError('Original methods or input bytes differ from the lock')
    if lock['runner_sha256'] != digest(pathlib.Path(__file__)):
        raise ValueError('Official runner differs from the locked version')
    return lock


@contextlib.contextmanager
def local_server(cache, model, folder, port, threads, slots):
    runtime = json.loads((DATA/'open_models_manifest.json').read_text())['runtime']
    binary = cache / 'runtime' / ('llama-' + runtime['release']) / 'llama-server'
    weights = cache / model['filename']
    if digest(weights) != model['sha256']:
        raise ValueError('Incorrect model checksum')
    archive = cache / runtime['url'].split('/')[-1]
    if digest(archive) != runtime['sha256']:
        raise ValueError('Incorrect runtime archive checksum')
    base = f'http://127.0.0.1:{port}'
    command = list(map(str, [binary,'-m',weights,'-c',8192*slots,'-np',slots,'-t',threads,'-tb',threads,
                              '-b',512,'-ub',512,'-ngl',0,'--cache-ram',128,'--host','127.0.0.1','--port',port,'--no-context-shift']))
    with (folder/'server.log').open('a') as log:
        proc = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        try:
            for _ in range(120):
                if proc.poll() is not None:
                    raise RuntimeError('Server exited before responding')
                try:
                    with urllib.request.urlopen(base+'/health', timeout=2) as reply:
                        if json.load(reply).get('status') == 'ok':
                            break
                except (OSError, urllib.error.URLError):
                    time.sleep(.5)
            else:
                raise TimeoutError('Server startup timed out')
            with urllib.request.urlopen(base+'/props',timeout=10) as response:
                props = json.load(response)
            if props['model_path'] != str(weights):
                raise ValueError('Incorrect model on local server')
            meta = dict(started_utc=utc(), command=command, model=model, build=props.get('build_info'),
                        input_sha256=digest(INPUTS), threads=threads, slots=slots, model_context_per_slot=8192)
            with (folder/'invocations.jsonl').open('a') as f:
                f.write(json.dumps(meta)+'\n')
            yield base
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


def run_model(model, cache, threads, slots, port):
    validate_lock()
    inputs = read_lines(INPUTS)
    folder = RESULTS / model['id']
    folder.mkdir(parents=True, exist_ok=True)
    cases_path = folder/'cases.jsonl'
    requests_path = folder/'requests.jsonl'
    completed = {r['case_id'] for r in read_lines(cases_path)}
    pending = [r for r in inputs if r['case_id'] not in completed]
    if not pending:
        return
    requests = {r['key']:r for r in read_lines(requests_path)}
    write_lock = threading.Lock()
    with local_server(cache, model, folder, port, threads, slots) as base:
        def request(key, messages, cap, schema=None):
            signature = hashlib.sha256(json.dumps([messages,cap,schema],sort_keys=True).encode()).hexdigest()
            if key in requests:
                if signature != requests[key]['signature']:
                    raise ValueError('Stored request differs')
                return requests[key]['generation']
            result = generate(base, model['id'], messages, cap, schema)
            entry = dict(key=key, signature=signature, generation=result)
            with write_lock, requests_path.open('a') as stream:
                stream.write(json.dumps(entry,ensure_ascii=False)+'\n')
                stream.flush()
                os.fsync(stream.fileno())
            return result

        def infer(row):
            case = {k:row[k] for k in ('case_id','source_row','group_id')}
            case['model_id'] = model['id']
            started = time.monotonic()
            try:
                plan = request(row['case_id']+'/planner', planner_messages(row['question']), 48)
                cid = parse_generation(plan).get('calculator_id')
                case['selected_calculator_id'] = cid
                if cid not in SPECS:
                    raise ValueError('Unknown calculator')
                proposal = request(row['case_id']+'/baseline', extractor_messages(row['question'],row['patient_note'],cid),768,extraction_schema(cid))
                call, quotes = make_call(cid,parse_generation(proposal))
                case['baseline_call'] = call
                case['baseline_quotes'] = quotes
                case['baseline_gates'] = evaluate_gates(call,quotes,row['patient_note'])
            except (ValueError, TypeError, KeyError, urllib.error.HTTPError) as error:
                case['baseline_error'] = type(error).__name__ + ': ' + str(error)
            apply_repair(case,row['patient_note'])
            case['wall_seconds'] = time.monotonic()-started
            return case

        with concurrent.futures.ThreadPoolExecutor(max_workers=slots) as pool, cases_path.open('a') as output:
            for result in concurrent.futures.as_completed([pool.submit(infer, row) for row in pending]):
                case = result.result()
                output.write(json.dumps(case,ensure_ascii=False)+'\n')
                output.flush()
                os.fsync(output.fileno())
                completed.add(case['case_id'])
                print(model['id'], len(completed), '/', len(inputs), flush=True)


def score(model):
    lock = validate_lock()
    if digest(REFERENCES) != lock['reference_sha256']:
        raise ValueError('Reference table differs')
    by_id = {r['source_row']:r for r in read_lines(REFERENCES)}
    folder = RESULTS / model['id']
    rows = sorted(read_lines(folder/'cases.jsonl'),key=lambda r:int(r['source_row']))
    if len(rows) != len(by_id) or {r['source_row'] for r in rows} != set(by_id):
        raise ValueError('Incomplete or duplicate outcomes')
    stats = dict(cases=len(rows),independent_sources=len({r['group_id'] for r in rows}),
                 paid_api_calls=0,recorded_requests=len(read_lines(folder/'requests.jsonl')),methods={})
    correct = {k:[] for k in ('L1_schema_only','L2_unit_domain','L3_literal_span','source_bound')}
    for method in correct:
        released = sum(bool(outcome(r,method).get('released')) for r in rows)
        match = sum(agrees(r,method,by_id[r['source_row']]) for r in rows)
        wrong = released-match
        stats['methods'][method] = dict(matched=match,nonmatching_released=wrong,blocked_or_failed=len(rows)-released,
                                            released=released,agreement=match/len(rows),coverage=released/len(rows),
                                            disagreement_among_released=wrong/released if released else None,
                                            conditional_error_Wilson95=wilson(wrong,released) if released else None)
    stats['paired_vs_unit_domain'] = paired(rows,by_id,'L2_unit_domain','source_bound')
    (folder/'summary.json').write_text(json.dumps(stats,indent=2)+'\n')
    print(model['id'],json.dumps(stats,indent=2))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['prepare','infer','score'])
    p.add_argument('--raw',type=pathlib.Path,default=DATA/'raw')
    p.add_argument('--cache',type=pathlib.Path,default=ROOT.parent/'open_model_cache')
    p.add_argument('--model',choices=['all','qwen2.5_1.5b_q4km','smollm2_1.7b_q4km'],default='all')
    p.add_argument('--threads',type=int,default=8)
    p.add_argument('--slots',type=int,default=4)
    p.add_argument('--port',type=int,default=18735)
    args = p.parse_args()
    if args.action=='prepare':
        prepare(args.raw)
        return
    for model in validate_lock()['planned_models']:
        if args.model in ('all',model['id']):
            if args.action=='infer':
                run_model(model,args.cache.resolve(),args.threads,args.slots,args.port)
            else:
                score(model)

if __name__=='__main__':
    main()
