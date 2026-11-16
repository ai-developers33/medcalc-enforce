# Actual local open-weight pilot results

These are observed executions, not predicted results. This is a development feasibility pilot; it does not establish clinical safety, prevention of harm, novelty, or journal readiness.

200 recorded model/decoding/case workflow attempts; 384 completed local LLM requests retained in these traces. Each workflow has a planner and extractor role using the same weights. The same 50 source cases are reused across models/variants, so workflow count is not a count of independent patients. An interrupted, unscored request during an infrastructure fix may not be in this retained-call count.

Total measured workflow wall time: 25.49 minutes (excluding downloads and model loading). Paid API cost: $0. CPU-only inference; eight requested threads, no GPU. There was no fine-tuning.

## Main comparison

Numerical correctness requires correct tool selection and a result within the benchmark answer interval (usually +/-5%). Denominators below include every recorded case, including failures and abstentions.

| Model / decoding | Cases | Tool selected correctly | L1 correct / released | L2 correct / released | L3 correct / released |
|---|---:|---:|---:|---:|---:|
| qwen2.5_1.5b_q4km | 50 | 50 | 0 / 0 | 0 / 0 | 0 / 0 |
| qwen2.5_1.5b_q4km_schema | 50 | 50 | 33 / 49 | 42 / 48 | 18 / 20 |
| smollm2_1.7b_q4km | 50 | 27 | 0 / 0 | 0 / 0 | 0 / 0 |
| smollm2_1.7b_q4km_schema | 50 | 35 | 17 / 48 | 23 / 45 | 7 / 10 |

L1: schema plus a unit-unaware executor. L2: unit-aware calculator baseline with arithmetic-domain/applicability checks. L3: L2 plus literal quote/value checks. All three gates replay each same generated call; they are not separate LLM workflows. L2 is the stronger baseline.

The tool-schema variant was added after observing formatting failures in the initial JSON-object run. It changes decoder constraints only, without changing prompts, cases, labels or token limits. Both variants and all failures are retained. This is disclosed development iteration, not a preregistered confirmatory result.

## Detailed measurements

### qwen2.5_1.5b_q4km

Workflow attempts: 50; source groups: 50; retained completed LLM requests: 100; transport-failure cases: 0. Tokens: 68,568 prompt, 2,892 generated. Workflow time: 3.71 minutes total, 3.99 seconds median, 8.03 seconds p95.

All required inputs correct after unit normalization: 0/50. Individual required inputs correct: 0/125. The scorer uses gold only after inference; no reference quantity enters generation or gating.

| Gate | Correct released / all cases | Incorrect released | Blocked or failed | Correct at 0.1% tolerance | Accuracy among released |
|---|---:|---:|---:|---:|---:|
| L1_schema_only | 0/50 (0.0%) | 0 | 50 | 0 | undefined (no releases) |
| L2_unit_domain | 0/50 (0.0%) | 0 | 50 | 0 | undefined (no releases) |
| L3_literal_span | 0/50 (0.0%) | 0 | 50 | 0 | undefined (no releases) |

The literal-span gate additionally blocked 0 otherwise benchmark-correct L2 outputs and 0 otherwise benchmark-incorrect L2 outputs. Numerical agreement is a limited proxy: it is not clinical adjudication.

Recorded workflow errors: {"Rejected: ARGUMENT_SET:": 49, "ValueError: Generation did not finish: length": 1}.

Finish reasons: {"length": 1, "stop": 99}.

### qwen2.5_1.5b_q4km_schema

Workflow attempts: 50; source groups: 50; retained completed LLM requests: 100; transport-failure cases: 0. Tokens: 68,568 prompt, 5,998 generated. Workflow time: 5.18 minutes total, 5.43 seconds median, 12.55 seconds p95.

All required inputs correct after unit normalization: 42/50. Individual required inputs correct: 112/125. The scorer uses gold only after inference; no reference quantity enters generation or gating.

| Gate | Correct released / all cases | Incorrect released | Blocked or failed | Correct at 0.1% tolerance | Accuracy among released |
|---|---:|---:|---:|---:|---:|
| L1_schema_only | 33/50 (66.0%) | 16 | 1 | 32 | 67.3% |
| L2_unit_domain | 42/50 (84.0%) | 6 | 2 | 42 | 87.5% |
| L3_literal_span | 18/50 (36.0%) | 2 | 30 | 18 | 90.0% |

The literal-span gate additionally blocked 24 otherwise benchmark-correct L2 outputs and 4 otherwise benchmark-incorrect L2 outputs. Numerical agreement is a limited proxy: it is not clinical adjudication.

Recorded workflow errors: {"ValueError: Generation did not finish: length": 1}.

Finish reasons: {"length": 1, "stop": 99}.

### smollm2_1.7b_q4km

Workflow attempts: 50; source groups: 50; retained completed LLM requests: 84; transport-failure cases: 8. Tokens: 60,305 prompt, 8,887 generated. Workflow time: 9.37 minutes total, 5.96 seconds median, 34.27 seconds p95.

All required inputs correct after unit normalization: 0/50. Individual required inputs correct: 0/125. The scorer uses gold only after inference; no reference quantity enters generation or gating.

| Gate | Correct released / all cases | Incorrect released | Blocked or failed | Correct at 0.1% tolerance | Accuracy among released |
|---|---:|---:|---:|---:|---:|
| L1_schema_only | 0/50 (0.0%) | 0 | 50 | 0 | undefined (no releases) |
| L2_unit_domain | 0/50 (0.0%) | 0 | 50 | 0 | undefined (no releases) |
| L3_literal_span | 0/50 (0.0%) | 0 | 50 | 0 | undefined (no releases) |

The literal-span gate additionally blocked 0 otherwise benchmark-correct L2 outputs and 0 otherwise benchmark-incorrect L2 outputs. Numerical agreement is a limited proxy: it is not clinical adjudication.

Recorded workflow errors: {"Rejected: ARGUMENT_SET:": 35, "RemoteDisconnected: Remote end closed connection without response": 1, "URLError: <urlopen error [Errno 111] Connection refused>": 7, "ValueError: Duplicate key: field": 1, "ValueError: Duplicate key: unit": 1, "ValueError: Generation did not finish: length": 5}.

Finish reasons: {"length": 5, "stop": 79}.

### smollm2_1.7b_q4km_schema

Workflow attempts: 50; source groups: 50; retained completed LLM requests: 100; transport-failure cases: 0. Tokens: 71,844 prompt, 7,128 generated. Workflow time: 7.23 minutes total, 7.93 seconds median, 15.45 seconds p95.

All required inputs correct after unit normalization: 22/50. Individual required inputs correct: 69/125. The scorer uses gold only after inference; no reference quantity enters generation or gating.

| Gate | Correct released / all cases | Incorrect released | Blocked or failed | Correct at 0.1% tolerance | Accuracy among released |
|---|---:|---:|---:|---:|---:|
| L1_schema_only | 17/50 (34.0%) | 31 | 2 | 16 | 35.4% |
| L2_unit_domain | 23/50 (46.0%) | 22 | 5 | 22 | 51.1% |
| L3_literal_span | 7/50 (14.0%) | 3 | 40 | 7 | 70.0% |

The literal-span gate additionally blocked 16 otherwise benchmark-correct L2 outputs and 19 otherwise benchmark-incorrect L2 outputs. Numerical agreement is a limited proxy: it is not clinical adjudication.

Recorded workflow errors: {"ValueError: Generation did not finish: length": 2}.

Finish reasons: {"length": 2, "stop": 98}.

## Interpretation and limits

- The simple JSON-object condition tests a weak interface for these small models; it must not be presented as a best-effort comparison to modern structured tool calling.
- JSON schema can make a call structurally valid while leaving values, units, variables and timepoints wrong. Numerical disagreement here is not a measured clinical-harm event.
- L3 only checks that quoted text occurs verbatim and contains the asserted literal value. It does not prove correct variable/value pairing, correct units, correct admission timepoint, or trusted patient/encounter provenance. It can reject correct outputs when quote formatting is imperfect.
- An abstain-on-everything gate would release no errors but deliver no useful calculations. Coverage and correct released answers must always accompany error rates.
- The original SmolLM JSON-object server exited unexpectedly; eight affected cases remain in its denominator. These are infrastructure failures, not evidence of model reasoning failure. The prompt-cache limit was subsequently reduced from its 8192 MiB default to 256 MiB; completed schema cases were retained across the pause. See diagnostics/cache_limit_amendment.json for the exact split. Timing is descriptive on shared compute and is not a controlled speed comparison.
- No live EHR state changes were tested. This pilot does not evaluate the proposed commit-time freshness contribution. The earlier controlled ledger study remains a separate experiment.
- Fifty development cases, five per calculator, are too few for clinical or general model conclusions. Model exposure to public benchmark text during pretraining is unknown. The official test split has not been used for model evaluation.
- A source-supported platelet annotation discrepancy was found in train-4318. Primary scores retain the original label and all cases. See reference_quality_flags.json and ERROR_ANALYSIS.md; benchmark agreement must not be presented as independently adjudicated clinical correctness.
- Larger models, robust extraction, separate tuning/held-out source groups, trusted EHR evidence, bounded repair, temporal/concurrency stress tests and fair competing-method comparisons remain before manuscript claims are justified.
- Wilson intervals in summary.json are descriptive per-case binomial intervals; they do not establish performance on a sampled clinical population.

## Audit and reproduction

See `summary.json`, `scored_cases.json`, each raw JSONL trace, server logs and `*_run.json`. All prompts, responses, selected tools, gate decisions, token usage and finish reasons are retained. `data/open_models_manifest.json` pins model revisions and hashes. `data/live_inputs.jsonl` contains only the allowed note/question input view; gold annotations are read solely by `score_live.py`.

Recompute metrics without running models: `python score_live.py` then `python report_live.py`. Full CPU inference instructions are in README.md. Source attribution and licensing are in SOURCE_NOTES.md.
