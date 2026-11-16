"""Secondary audit of reference argument agreement conditional on model and policy releases."""
import argparse
import ast
import collections
import csv
import json
import math
from pathlib import Path

from medcalc.registry import SPECS, canonical_value, map_entities
from official_study import DATA, RESULTS, digest, read_lines
from score_source_binding import agrees, outcome


def same(a,b):
    if isinstance(a,str) or isinstance(b,str):
        return a==b
    return math.isclose(a,b,rel_tol=1e-6,abs_tol=1e-8)


def reference_fields(row):
    fields=map_entities(ast.literal_eval(row['Relevant Entities']))
    if set(fields) != set(SPECS[row['Calculator ID']]['params']):
        raise ValueError('unexpected required fields')
    return {f:canonical_value(f,q['value'],q['unit']) for f,q in fields.items()}


def evaluate(records, refs, raw_rows):
    output={}
    for policy in ('L2_unit_domain','source_bound'):
        counts=collections.Counter(); examples=[];unavailable=[]
        for record in records:
            identifier=record['source_row']; annot=raw_rows[identifier]
            released=outcome(record,policy)
            if not released.get('released'):
                continue
            counts['released']+=1
            try:
                expected=reference_fields(annot)
            except (KeyError,TypeError,ValueError,SyntaxError) as e:
                unavailable.append({'case_id':record['case_id'],'detail':str(e)})
                continue
            counts['annotation_comparable_released']+=1
            values=released['canonical_inputs']
            right_tool=record.get('selected_calculator_id')==annot['Calculator ID']
            misses=[field for field,val in expected.items() if not (right_tool and field in values and same(values[field],val))]
            counts['expected_fields_in_comparable_releases']+=len(expected)
            counts['matching_fields_in_comparable_releases']+=len(expected)-len(misses)
            counts['all_fields_match']+=int(not misses)
            if misses and agrees(record,policy,refs[identifier]):
                counts['numeric_match_with_argument_discrepancy']+=1
                examples.append(dict(case_id=record['case_id'],mismatched_fields=misses))
        output[policy]={'counts':dict(counts),'matching_answers_with_argument_discrepancies':examples,
                        'unavailable_reference_fields':unavailable}
    return output


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw',type=Path,default=DATA/'raw')
    parser.add_argument('--cohort',choices=['initial','extension'],default='initial')
    parser.add_argument('--model',default='all')
    args=parser.parse_args(); raw=args.raw/'test_data.csv'
    lock=json.loads((DATA/'official_lock.json').read_text())
    if digest(raw)!=lock['dataset_hashes']['test_data.csv']:
        raise ValueError('Incorrect official CSV checksum')
    with raw.open(encoding='utf-8',newline='') as f:
        raw_rows={r['Row Number']:r for r in csv.DictReader(f)}
    extension=args.cohort=='extension'
    label_path=DATA/'official_extension'/'references.jsonl' if extension else DATA/'official_reference.jsonl'
    refs={r['source_row']:r for r in read_lines(label_path)}
    result_path=RESULTS.parent/'official_extension' if extension else RESULTS
    for model in lock['planned_models']:
        if args.model not in ('all',model['id']):
            continue
        folder=result_path/model['id']; records=read_lines(folder/'cases.jsonl')
        if len(records)!=len(refs) or set(r['source_row'] for r in records)!=set(refs):
            raise ValueError('Missing outcomes')
        result=evaluate(records,refs,raw_rows)
        report={'model':model['id'],'cases':len(refs),'cohort':args.cohort,'methods':result,
                'scope':'Secondary descriptive audit after the primary outcome lock. Evaluation of annotated fields uses the original registry and strict canonical tolerance. Non-comparable field annotations are explicitly counted. Source annotation quality is not independently adjudicated.'}
        (folder/'argument_audit.json').write_text(json.dumps(report,indent=2)+'\n')
        print(model['id'],args.cohort, {k:v['counts'] for k,v in result.items()})

if __name__=='__main__':
    main()
