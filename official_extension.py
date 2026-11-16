"""Lock all remaining eligible official sources as a separate, optional second cohort."""
import argparse
import collections
import csv
import hashlib
import json
import pathlib

import audit_official_study as audit
import official_study as study

FOLDER = study.DATA / 'official_extension'
FIRST_LOCK = study.LOCK
FIRST_INPUTS = study.INPUTS


def prepare(raw):
    first = study.validate_lock()
    with (raw/'test_data.csv').open(encoding='utf-8',newline='') as file:
        test = list(csv.DictReader(file))
    for name,expected in first['dataset_hashes'].items():
        file = raw/name if name=='test_data.csv' else raw/'verified'/name
        if study.digest(file) != expected:
            raise ValueError('Wrong pinned data version')
    excluded_sources, excluded_texts = set(), set()
    for file in ('train_data.csv','one_shot_data.csv'):
        with (raw/'verified'/file).open(encoding='utf-8',newline='') as stream:
            for row in csv.DictReader(stream):
                source,text=study.source_keys(row)
                excluded_sources.add(source)
                excluded_texts.add(text)
    for row in study.read_lines(FIRST_INPUTS):
        excluded_sources.add(row['group_id'])
        excluded_texts.add(hashlib.sha256(' '.join(row['patient_note'].lower().split()).encode()).hexdigest())
    inputs,references = [],[]
    for cid in sorted(study.SPECS,key=int):
        pool = [r for r in test if r['Calculator ID']==cid]
        pool.sort(key=lambda r: hashlib.sha256(f"{study.SELECTION_SEED}|{cid}|{r['Row Number']}".encode()).hexdigest())
        for row in pool:
            group,note_hash=study.source_keys(row)
            if group in excluded_sources or note_hash in excluded_texts:
                continue
            excluded_sources.add(group)
            excluded_texts.add(note_hash)
            key=row['Row Number']
            inputs.append(dict(case_id='official-'+key,source_row=key,group_id=group,note_id=row['Note ID'],
                               note_type=row['Note Type'],patient_note=row['Patient Note'],question=row['Question']))
            references.append(dict(case_id='official-'+key,source_row=key,calculator_id=cid,
                                   ground_truth=row['Ground Truth Answer'],lower=row['Lower Limit'],upper=row['Upper Limit']))
    FOLDER.mkdir(exist_ok=True)
    study.write_new_or_identical(FOLDER/'inputs.jsonl',study.to_jsonl(inputs))
    study.write_new_or_identical(FOLDER/'references.jsonl',study.to_jsonl(references))
    record = dict(dataset_hashes=first['dataset_hashes'],first_cohort_lock_sha256=study.digest(FIRST_LOCK),
                  input_sha256=study.digest(FOLDER/'inputs.jsonl'),reference_sha256=study.digest(FOLDER/'references.jsonl'),
                  code_hashes=study.code_hashes(),runner_sha256=study.digest(pathlib.Path(study.__file__)),
                  extension_script_sha256=study.digest(pathlib.Path(__file__)),
                  planned_models=first['planned_models'],selected=len(inputs),
                  selected_by_calculator=dict(collections.Counter(r['calculator_id'] for r in references)),
                  selection='All remaining official-test rows for the ten supported calculators under original source/text exclusions, deduplicated globally by source key and normalized note. Excludes all 44 first-cohort sources and normalized notes. No model or outcomes used to determine membership.',
                  primary_outcomes=first['primary_outcomes'])
    lock_path=FOLDER/'lock.json'
    if lock_path.exists():
        previous=json.loads(lock_path.read_text());previous.pop('locked_utc')
        if previous != record:
            raise ValueError('Existing extension differs')
    else:
        record['locked_utc']=study.utc()
        lock_path.write_text(json.dumps(record,indent=2)+'\n')
    print('Extension locked',len(inputs),'cases',record['selected_by_calculator'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','infer','score','audit'])
    parser.add_argument('--raw',type=pathlib.Path,default=study.DATA/'raw')
    parser.add_argument('--cache',type=pathlib.Path,default=study.ROOT.parent/'open_model_cache')
    parser.add_argument('--model',default='all',choices=['all','qwen2.5_1.5b_q4km','smollm2_1.7b_q4km'])
    parser.add_argument('--slots',type=int,default=3)
    parser.add_argument('--threads',type=int,default=8)
    parser.add_argument('--port',type=int,default=18736)
    args=parser.parse_args()
    if args.action=='prepare':
        prepare(args.raw)
        return
    metadata=json.loads((FOLDER/'lock.json').read_text())
    if metadata['first_cohort_lock_sha256']!=study.digest(FIRST_LOCK) or metadata['extension_script_sha256']!=study.digest(pathlib.Path(__file__)):
        raise ValueError('Extension lock mismatch')
    # Reuse the identical frozen engine in this separate CLI process with distinct files.
    study.LOCK=audit.LOCK=FOLDER/'lock.json'
    study.INPUTS=audit.INPUTS=FOLDER/'inputs.jsonl'
    study.REFERENCES=audit.REFERENCES=FOLDER/'references.jsonl'
    study.RESULTS=audit.RESULTS=study.ROOT/'results/official_extension'
    for model in study.validate_lock()['planned_models']:
        if args.model not in ('all',model['id']):
            continue
        if args.action=='infer':
            study.run_model(model,args.cache.resolve(),args.threads,args.slots,args.port)
        elif args.action=='score':
            study.score(model)
        else:
            audit.audit_model(model['id'])

if __name__=='__main__':
    main()
