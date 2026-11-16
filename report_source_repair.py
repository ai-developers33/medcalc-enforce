"""Build the improvement report from retained, paired experiment results."""
import collections,json,pathlib
from medcalc.registry import SPECS
ROOT=pathlib.Path(__file__).resolve().parent
LABEL={'L2_unit_domain':'Unit/domain baseline (L2)','L3_literal_span':'Original literal-quote gate (L3)','source_bound':'Source-backed repair (v2)'}

def table(s):
    lines=['| Method | Matching / all cases | Nonmatching results released | Blocked or failed | Matching / released |','|---|---:|---:|---:|---:|']
    for key,label in LABEL.items():
        m=s['methods'][key]
        lines.append(f"| {label} | {m['matched']}/{s['cases']} ({100*m['agreement']:.0f}%) | {m['nonmatching_released']} | {m['blocked_or_failed']} | {m['matched']}/{m['released']} |")
    return '\n'.join(lines)

def main():
    base=ROOT/'results/binding'
    dev=json.loads((base/'development_repair_v2/summary.json').read_text())
    val=json.loads((base/'validation_repair_v2/summary.json').read_text())
    failed=json.loads((base/'development_v1/summary.json').read_text())
    audit=json.loads((base/'validation_repair_v2/audit.json').read_text())
    cases=json.loads((base/'validation_repair_v2/scored_cases.json').read_text())
    assert dev['cases']==val['cases']==50
    out=['# Source-backed runtime repair: measured improvement, v0.3','',
    'Actual CPU inference using Qwen2.5-1.5B-Instruct Q4_K_M. No fine-tuning, paid API, new prompts, or additional model calls for the selected repair adapter. Each method receives the same generated calculator call. Numerical agreement below means correct calculator selection plus a result inside the original benchmark interval; it is not independently adjudicated clinical correctness.','',
    '## Additional validation cases','',
    'Fifty previously unrun inference cases, five per calculator, selected before inference. Their source articles and normalized texts do not overlap the original 50 development cases. These records are from the training-derived 200-row arithmetic-audit pool; this is not the official test split or an untouched clinical dataset. Code/input hashes were frozen before inference and still match. No changes were made from validation outcomes.','',table(val),'',
    'All cases remain in the denominator, including abstentions and generation failures. The original gold references and answer tolerance are unchanged. Relative to L2, five previously nonmatching answers become matching, six nonmatching answers are blocked, and three previously matching answers are blocked. The two original generation failures remain failures. The observed four-point accuracy gain is uncertain; the strongest observed change is fewer nonmatching releases at lower coverage.','',
    '## Original development cases','',
    'The parser and repair rules were developed using these cases, so this table measures development fit. It must not be presented as held-out performance. The earlier schema-only executor matched 33/50 (66%); the stronger unit/domain baseline is the principal comparison below.','',table(dev),'',
    '## What changed','',
    'The original small model still selects a calculator and proposes its inputs. The new deterministic adapter parses measurements from the source note, associates explicitly named variables and ordered lists, and reconstructs executable arguments from source text. It checks canonical value support, repairs a unit when the native number has one supported interpretation, and repairs a value only when there is one distinct explicitly named source quantity. Unsupported or ambiguous proposals abstain. Source packets are regenerated and checked against the note hash and formula version before execution.','',
    'The parser handles blood-pressure pairs, scientific platelet counts, shared-unit laboratory lists, and feet/inches. It rejects truncated compound units such as interpreting kg/m² as body weight in kg. The original model proposal is retained alongside every repair and source offset.','',
    '## Development alternative retained','',
    f"The first prototype asked the same model to select observation IDs directly. It matched {failed['methods']['source_bound']['matched']}/50, released {failed['methods']['source_bound']['nonmatching_released']} nonmatching results, and abstained on {failed['methods']['source_bound']['blocked_or_failed']}. Its 50 new model calls, code and full negative results remain in `development_v1/`. It was rejected before the validation split was run. The final adapter replays the original stronger extractor. Thus development involved adaptive selection, which is disclosed rather than treated as preregistered evidence.",'',
    '## Paired validation comparison and uncertainty','']
    for comparison in val['comparisons']:
        a=LABEL[comparison['from']];low,high=comparison['stratified_bootstrap95']
        out.append(f"- Versus {a}: {comparison['gained_matching_answers']} gained matching answers and {comparison['lost_matching_answers']} lost; change {100*comparison['agreement_delta']:+.0f} percentage points. Exploratory calculator-stratified bootstrap 95% interval: {100*low:+.0f} to {100*high:+.0f} points; paired exact McNemar p={comparison['paired_exact_mcnemar_p']:.5g}.")
    m=val['methods']['source_bound'];lo,hi=m['agreement_wilson95']
    out.extend(['',f"The repair's descriptive Wilson 95% agreement interval is {100*lo:.1f}%–{100*hi:.1f}%. Agreement at the stricter 0.1% tolerance is {m['strict_0_1pct_matched']}/50. The split is small, balanced by calculator, and not a random clinical sample. These intervals and exploratory comparisons do not establish patient safety or population performance.",'',
    '## Validation by calculator','',
    '| Calculator | Cases | Unit/domain matching | Literal gate matching | Repair matching | Repair released |','|---|---:|---:|---:|---:|---:|'])
    for cid in sorted(m['by_calculator'],key=int):
        t=m['by_calculator'][cid]
        out.append(f"| {SPECS[cid]['name']} | {t['n']} | {val['methods']['L2_unit_domain']['by_calculator'][cid]['matched']} | {val['methods']['L3_literal_span']['by_calculator'][cid]['matched']} | {t['matched']} | {t['released']} |")
    out.extend(['','## Remaining validation failures','','| Case | Calculator | Final outcome |','|---|---|---|'])
    for r in cases:
        result=r['methods']['source_bound']
        if not result['matched']:
            reason='Released a nonmatching numerical result' if result.get('released') else result.get('reason','No output')
            out.append(f"| {r['case_id']} | {SPECS[r['expected_calculator']]['name']} | {reason} |")
    if all(r['methods']['source_bound']['matched'] for r in cases):out.append('| None in this sample | — | — |')
    actions=collections.Counter(e['action'] for r in cases for e in r['methods']['source_bound'].get('evidence',{}).values())
    out.extend(['','## Cost, execution and integrity','',
    f"Validation made {val['new_llm_calls']} completed local calls: 50 planner and 50 extractor requests. All three gates reuse each common call. New request count in this improvement cycle is {val['new_llm_calls']+failed['new_llm_calls']} including the failed development alternative. Original development replay uses no new model calls. Paid API cost is $0; local compute is still required. The validation workflows took {val['wall_seconds']/60:.2f} minutes in total, excluding model loading/downloads; this shared-CPU timing is descriptive.",'',
    f"Successful-repair field actions: {dict(actions)}. These counts cover released cases only and do not count independent patient outcomes.",'',
    'The audit reconstructs all validation prompts from allowed note/question inputs, checks request signatures and deterministic decoding settings, reconstructs model calls, replays all gates, verifies every released evidence substring, checks all 50 cases are retained, and confirms no duplicate request keys. Original development notes, gold labels, model trace, prompt builder, formula registry and baseline enforcement are byte-identical to v0.2. See `validation_repair_v2/audit.json`.','',
    'Thirty-five software tests passed, including ambiguous measurements, mutated source packets, stale formula versions, non-finite/boolean inputs, unit labels, compound units, ordered lists, and a regression that explicitly demonstrates the remaining timepoint limitation.','',
    '## Limits and next experiments','',
    '- A source-supported measurement can still be the wrong timepoint, subject, or clinical variable. This adapter does not establish trusted EHR provenance or admission-time semantics; the test suite includes an example where a later matching measurement passes.',
    '- Pattern-based source parsing can fail or attach a label incorrectly. Reconstructing a packet only establishes consistency with this parser and source, not truth of the source or medical appropriateness.',
    '- The original development case train-4318 retains its known platelet-label discrepancy; primary scores are not corrected or filtered. Reference-quality flags from v0.2 remain available. No systematic clinician adjudication has been performed on either split.',
    '- One small quantized model, ten calculators, and 50 new cases are insufficient for a general performance claim. Public benchmark contamination during model pretraining is unknown.',
    '- The next study should freeze the selected implementation, broaden model/calculator coverage, independently verify evidence/temporal labels, evaluate the official test split, and test conflicting observations and state updates. No real EHR integration or commit-time concurrency enforcement was added here.',
    '- These experiments measure computational agreement and abstention, not clinical harm, prevented fatalities, or journal acceptance.','',
    '## Reproduce','',
    '```bash','python3 -m unittest discover -s tests -v',
    'python3 run_source_repair.py --phase development',
    'python3 score_source_binding.py --phase development --tag repair_v2',
    'python3 score_source_binding.py --phase validation --tag repair_v2',
    'python3 audit_source_repair.py --previous-archive ../MedCalc_Enforce_Experiments_v0_2.zip',
    'python3 report_source_repair.py','```','',
    'Rescoring and repair replay require no model download. For fresh validation inference, first run `fetch_open_models.py`, preserve the bundled recorded output directory elsewhere, then run `python3 run_source_repair.py --phase validation`. The runner checks the frozen code/input hashes and skips completed cases; to record a separate repeat without overwriting the original, use `--tag repair_v2_repeat` and score that tag separately. Repeated inference is not a new independent validation set. If the v0.2 archive is unavailable, omit `--previous-archive`; all other integrity checks remain available.',''])
    (base/'IMPROVEMENT_RESULTS.md').write_text('\n'.join(out))
    print('Wrote results/binding/IMPROVEMENT_RESULTS.md')
if __name__=='__main__':main()
