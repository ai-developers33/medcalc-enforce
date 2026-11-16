"""Render a concise, evidence-backed report from the measured trace summary."""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent

def main():
    dest=ROOT/'results/live'
    summary=json.loads((dest/'summary.json').read_text())
    total_cases=sum(x['cases'] for x in summary['models'].values())
    total_calls=sum(x['llm_calls'] for x in summary['models'].values())
    total_seconds=sum(x['wall_seconds'] for x in summary['models'].values())
    lines=['# Actual local open-weight pilot results', '',
       'These are observed executions, not predicted results. This is a development feasibility pilot; it does not establish clinical safety, prevention of harm, novelty, or journal readiness.', '',
       f'{total_cases} recorded model/decoding/case workflow attempts; {total_calls} completed local LLM requests retained in these traces. Each workflow has a planner and extractor role using the same weights. The same 50 source cases are reused across models/variants, so workflow count is not a count of independent patients. An interrupted, unscored request during an infrastructure fix may not be in this retained-call count.', '',
       f'Total measured workflow wall time: {total_seconds/60:.2f} minutes (excluding downloads and model loading). Paid API cost: $0. CPU-only inference; eight requested threads, no GPU. There was no fine-tuning.', '',
       '## Main comparison', '',
       'Numerical correctness requires correct tool selection and a result within the benchmark answer interval (usually +/-5%). Denominators below include every recorded case, including failures and abstentions.', '',
       '| Model / decoding | Cases | Tool selected correctly | L1 correct / released | L2 correct / released | L3 correct / released |',
       '|---|---:|---:|---:|---:|---:|']
    for name,x in summary['models'].items():
        cells=[f"{x['gates'][g]['correct_released']} / {x['gates'][g]['released']}" for g in ['L1_schema_only','L2_unit_domain','L3_literal_span']]
        lines.append(f"| {name} | {x['cases']} | {x['selected_correct_tool']} | "+' | '.join(cells)+' |')
    lines += ['', 'L1: schema plus a unit-unaware executor. L2: unit-aware calculator baseline with arithmetic-domain/applicability checks. L3: L2 plus literal quote/value checks. All three gates replay each same generated call; they are not separate LLM workflows. L2 is the stronger baseline.', '',
       'The tool-schema variant was added after observing formatting failures in the initial JSON-object run. It changes decoder constraints only, without changing prompts, cases, labels or token limits. Both variants and all failures are retained. This is disclosed development iteration, not a preregistered confirmatory result.', '',
       '## Detailed measurements', '']
    for name,x in summary['models'].items():
        lines += [f'### {name}', '',
            f"Workflow attempts: {x['cases']}; source groups: {x['source_groups']}; retained completed LLM requests: {x['llm_calls']}; transport-failure cases: {x['transport_failure_cases']}. Tokens: {x['prompt_tokens']:,} prompt, {x['completion_tokens']:,} generated. Workflow time: {x['wall_seconds']/60:.2f} minutes total, {x['workflow_seconds_median']:.2f} seconds median, {x['workflow_seconds_p95']:.2f} seconds p95.", '',
            f"All required inputs correct after unit normalization: {x['all_required_fields_correct']}/{x['cases']}. Individual required inputs correct: {x['extraction_fields_correct']}/{x['extraction_fields_expected']}. The scorer uses gold only after inference; no reference quantity enters generation or gating.", '',
            '| Gate | Correct released / all cases | Incorrect released | Blocked or failed | Correct at 0.1% tolerance | Accuracy among released |',
            '|---|---:|---:|---:|---:|---:|']
        for name_gate,g in x['gates'].items():
            precision='undefined (no releases)' if g['accuracy_among_released'] is None else f"{100*g['accuracy_among_released']:.1f}%"
            lines.append(f"| {name_gate} | {g['correct_released']}/{x['cases']} ({100*g['end_to_end_accuracy']:.1f}%) | {g['incorrect_released']} | {g['blocked_or_failed']} | {g['strict_0_1pct_correct_released']} | {precision} |")
        lines += ['', f"The literal-span gate additionally blocked {x['literal_gate_blocked_otherwise_numerically_correct']} otherwise benchmark-correct L2 outputs and {x['literal_gate_blocked_otherwise_numerically_incorrect']} otherwise benchmark-incorrect L2 outputs. Numerical agreement is a limited proxy: it is not clinical adjudication.", '',
            'Recorded workflow errors: '+json.dumps(x['workflow_errors'],sort_keys=True)+'.', '',
            'Finish reasons: '+json.dumps(x['finish_reasons'],sort_keys=True)+'.', '']
    lines += ['## Interpretation and limits', '',
        '- The simple JSON-object condition tests a weak interface for these small models; it must not be presented as a best-effort comparison to modern structured tool calling.',
        '- JSON schema can make a call structurally valid while leaving values, units, variables and timepoints wrong. Numerical disagreement here is not a measured clinical-harm event.',
        '- L3 only checks that quoted text occurs verbatim and contains the asserted literal value. It does not prove correct variable/value pairing, correct units, correct admission timepoint, or trusted patient/encounter provenance. It can reject correct outputs when quote formatting is imperfect.',
        '- An abstain-on-everything gate would release no errors but deliver no useful calculations. Coverage and correct released answers must always accompany error rates.',
        '- The original SmolLM JSON-object server exited unexpectedly; eight affected cases remain in its denominator. These are infrastructure failures, not evidence of model reasoning failure. The prompt-cache limit was subsequently reduced from its 8192 MiB default to 256 MiB; completed schema cases were retained across the pause. See diagnostics/cache_limit_amendment.json for the exact split. Timing is descriptive on shared compute and is not a controlled speed comparison.',
        '- No live EHR state changes were tested. This pilot does not evaluate the proposed commit-time freshness contribution. The earlier controlled ledger study remains a separate experiment.',
        '- Fifty development cases, five per calculator, are too few for clinical or general model conclusions. Model exposure to public benchmark text during pretraining is unknown. The official test split has not been used for model evaluation.',
        '- A source-supported platelet annotation discrepancy was found in train-4318. Primary scores retain the original label and all cases. See reference_quality_flags.json and ERROR_ANALYSIS.md; benchmark agreement must not be presented as independently adjudicated clinical correctness.',
        '- Larger models, robust extraction, separate tuning/held-out source groups, trusted EHR evidence, bounded repair, temporal/concurrency stress tests and fair competing-method comparisons remain before manuscript claims are justified.',
        '- Wilson intervals in summary.json are descriptive per-case binomial intervals; they do not establish performance on a sampled clinical population.', '',
        '## Audit and reproduction', '',
        'See `summary.json`, `scored_cases.json`, each raw JSONL trace, server logs and `*_run.json`. All prompts, responses, selected tools, gate decisions, token usage and finish reasons are retained. `data/open_models_manifest.json` pins model revisions and hashes. `data/live_inputs.jsonl` contains only the allowed note/question input view; gold annotations are read solely by `score_live.py`.', '',
        'Recompute metrics without running models: `python score_live.py` then `python report_live.py`. Full CPU inference instructions are in README.md. Source attribution and licensing are in SOURCE_NOTES.md.']
    (dest/'LIVE_RESULTS.md').write_text('\n'.join(lines)+'\n')
    print('Wrote results/live/LIVE_RESULTS.md')

if __name__ == '__main__': main()
