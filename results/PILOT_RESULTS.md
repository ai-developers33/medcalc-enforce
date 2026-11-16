# Development pilot results — not manuscript evidence

The results below are the original measured software development checks; no LLM inference or real EHR deployment was performed in this controlled experiment. The separate v0.2 local LLM pilot is reported in `live/LIVE_RESULTS.md`.

Base annotations: 200 from the official training split; source groups: 199; controlled cases: 2840.

| Configuration | Invalid calls rejected before execution | Invalid result release | Valid false rejection | Valid numeric accuracy |
|---|---:|---:|---:|---:|
| B0_unchecked_python | 0/2040 (0.0%) | 98.0% | 0.0% | 75.0% |
| B1_schema | 0/2040 (0.0%) | 98.0% | 0.0% | 75.0% |
| B2_static_semantics | 461/2040 (22.6%) | 77.4% | 0.0% | 100.0% |
| B3_evidence_at_validation | 1640/2040 (80.4%) | 19.6% | 0.0% | 100.0% |
| B4_commit_revalidation | 2040/2040 (100.0%) | 0.0% | 0.0% | 100.0% |
| A_no_argument_normalization | 2040/2040 (100.0%) | 0.0% | 0.0% | 75.0% |
| A_no_domain | 1840/2040 (90.2%) | 7.8% | 0.0% | 100.0% |
| A_no_applicability | 2020/2040 (99.0%) | 1.0% | 0.0% | 100.0% |
| A_no_provenance | 1460/2040 (71.6%) | 28.4% | 0.0% | 100.0% |
| A_no_context | 1041/2040 (51.0%) | 49.0% | 0.0% | 100.0% |

## Arithmetic reconstruction

200/200 results satisfy the dataset's recorded answer interval. This uses supplied reference input annotations, so it is not LLM accuracy.

## Limitations

- Controlled development transformations; not naturally occurring LLM failures.
- Oracle-backed structured evidence generated from benchmark annotations; no clinical-note extraction evaluated.
- Patient, encounter, timestamps, and update events are simulated; no real longitudinal EHR outcomes.
- Ten equation calculators only; no claim to cover all 55 tools or all clinically unsafe behaviors.
- Sequential event replay; no production transaction isolation or distributed concurrency guarantee.
- Clinical labels and provenance annotations have not been independently adjudicated.
- No live multi-agent repair, upstream AgentSpec comparison, or MedCalc-Pro inference has run.
- Perfect rejection on hand-constructed covered faults cannot establish novelty or clinical safety.

Inspect `metrics_by_fault.csv`, `trial_results.jsonl`, and `formula_checks.json` for failures. Timing includes gates only and excludes model/network latency. The paired bootstrap groups all variants from the same source case.

Stable semantic-result digest: `148cdc51a40a8389eea41a34e1f02b331cedf2f8974e2527b965c00f100d0e32`
