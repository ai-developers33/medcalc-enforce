# Experiment protocol v0.1 — development stage

Prepared November 8, 2026 (America/Los_Angeles). Manuscript writing remains deferred.

## Research question and permitted claims

Does deterministic enforcement of calculator input evidence, patient/encounter context, temporal selection, units, formula preconditions, and execution-time dependencies reduce invalid result release in tool-using agent workflows, compared with explicit schema validation and strong semantic/evidence validators?

The current pilot can establish implementation behavior on declared controlled fixtures. It cannot establish the incidence of natural LLM errors, clinical harm, clinical deployment safety, or novelty. “Clinically unsafe” requires independently justified clinical or calculator-domain labels in the later evaluation. For now, report **contract-invalid calls**.

Keep the agreed title as a working title. The EHR and multi-agent wording must be supported by the final experiments. Any synthetic environment must be identified explicitly.

## Dataset decisions

| Resource | Pinned content / measured size | Intended role | Status and limits |
|---|---|---|---|
| MedCalc-Bench Verified | v1.0.8; commit `801592132bfd833f049b517a4e013e00a5fc40fa`; 10,538 train, 1,100 test, 55 one-shot examples; 55 calculator types | Primary numeric and extraction benchmark | Downloaded and audited. Pilot uses only 200 selected training rows across 10 tools. Official test is reserved for later performance evaluation. |
| MedCalc-Pro | commit `751a514644d22bc6f7066087205fbbb61b7b40f5`; 1,048 simple, 62 nested, 1,158 multi-tool cases; registry has 77 tools | Nested dependencies and multi-calculator evaluation; relevant method comparator | Downloaded for metadata/overlap audit. Substantial overlap exists; do not call it an independent external validation cohort. Repository reuse terms should be clarified before redistribution. |
| Controlled fault/encounter fixtures | v0.1 generator; 200 base annotations; 800 valid controls and 2,040 invalid variants | Mechanism checks, regression tests, event-order stress tests | Generated and run. Derived data, not a third independent clinical dataset. |
| Synthea FHIR records | Version and seed to be frozen before generation | Realistic synthetic patient, encounter, observation and update plumbing | Proposed next-stage integration source; not used in this pilot. It supplies synthetic records, not clinician-validated calculator outcomes. |
| MIMIC-IV-Note / eICU | No data obtained | Optional real-record validation if authorized access is available | Credentialed resources. Not prerequisites for the current offline pilot. No claim that they were evaluated. |

PMC-Patients is not selected as a separate validation set: it supplies source material to related benchmarks and consists of case-report summaries, not automatically longitudinal EHR trajectories.

## Leakage and independence controls

Measured in the pinned downloads:

- Verified train/test share 159 unique normalized note texts and 199 explicit PMC case identifiers. The test set contains 1,074 unique normalized note texts across 1,100 rows.
- MedCalc-Pro simple has 833 rows whose normalized note text matches Verified test, and 569 rows with a matching explicit PMC case identifier. These sets overlap; do not add these counts.
- MedCalc-Pro multi has 1,065 rows matching a Verified training note by normalized text, and 67 matching a test note.
- Nested cases have no exact-note or explicit-PMC-id overlap detected by these checks. This is not proof of independence: near duplicates, paraphrases and hidden source reuse remain untested.

These findings identify reuse of source cases, not proof that a particular published model result is contaminated. They matter if examples, prompts, rules or models are developed using overlapping notes.

For the full study, create one source-group map across all selected resources. Keep all descendants, perturbations and repeated runs of a source case in one partition. Never expose relevant-entity dictionaries, reference answers or explanations to the tested LLM. Audit near duplicates before declaring an external subset. Add article-level grouping sensitivity analyses where public article IDs can be recovered. Preserve original benchmark scores and separately report overlap-screened sensitivity subsets.

The pilot selection is fixed by seed 731 and source-row hashes, 20 eligible rows per calculator. Eligibility is set before reference-answer comparison: supported annotation form/units, no identified official-test overlap, and age >=18 for the adult CKD-EPI contract. All exclusions and their reasons are retained. No row was removed because its calculated answer failed. There are 200 rows but 199 unique source groups.

## Current implementation and fixtures

Calculators: CKD-EPI 2021 creatinine; mean arterial pressure; BMI; albumin-corrected calcium; QTc Bazett; FIB-4; Hillier corrected sodium; serum osmolality; anion gap without potassium; Mosteller body surface area.

Gate structure: explicit schema; analyte-aware unit normalization; narrow arithmetic domains and coupled identities; formula applicability; evidence existence/variable/value binding; patient/encounter/time/formula context; revalidation against state available immediately before execution. All configurations execute a copied value mapping, so a weak mutable-payload implementation is not used to manufacture an advantage.

The query explicitly selects the latest eligible observation at its fixed `as_of` time within one encounter. This is a **fixture policy**, not a universal rule for clinical measurements. Actual calculator-specific temporal windows and cross-encounter use require reviewed contracts. Unrelated new observations and observations after a historical query time must not force rejection.

Four valid cases per base: canonical units, equivalent alternate units, legitimate historical query with later observations, and unrelated update. Ten invalid cases per base: fabricated value; relabeled unit without conversion; missing evidence; wrong patient; wrong encounter; stale evidence; late-arriving relevant observation; required formula-version change; unsupported unit; negative source measurement. CKD-EPI adds a pediatric applicability case; MAP adds an inverted pressure pair. All fixtures serialize as strict JSON and pass the shape-only baseline; their invalidity is semantic under the declared contracts.

The source ledger is oracle-backed: input quantities come from benchmark annotations. IDs/times/events are synthetic. Lexical extraction from notes and independently adjudicated clinical labels are absent. The fault author and validator author are not independent. Sequential replay injects exactly specified event schedules; it does not demonstrate race freedom in deployed concurrent software.

## Comparative conditions

| Condition | Definition | Current status |
|---|---|---|
| B0 | Unchecked canonical-argument Python arithmetic; runtime errors logged separately | Run |
| B1 | Explicit shape/type/finite-number validation | Run |
| B2 | Schema + unit normalization + mathematical domain + declared applicability | Run |
| B3 | B2 + evidence and context validation before the injected update | Run |
| B4 | B3 + revalidation against the post-update state before execution | Run |
| Ablations | B4 without argument normalization, domain, applicability, provenance, or context | Run; no-commit condition is B3 |
| Existing runtime enforcement | Reproduce/adapt AgentSpec with comparable policies and expose adaptation choices | Planned, not replaced by B1/B2 |
| Medical agent method | Run the released MedCalc-Pro pipeline and audit-related ablation where compatible | Planned |
| LLM critic | Same model/budget with a structured review step | Planned |

B3 already uses the same static semantic predicates as B4. Its deliberate limitation is that validation precedes a changing state. The no-normalization ablation removes argument conversion for arithmetic; provenance still needs unit-aware comparison. This is not an ablation of every use of unit information, and the predicates are not claimed to be fully independent. A rigorous full study must also compare a strong execution-time revalidation baseline and, where feasible, a transactional/pinned-snapshot reference design. If an existing method matches the benefit, report that result and revise the claimed contribution.

## Experiment sequence

1. **Arithmetic and data audit — completed pilot.** Confirm source hashes, exclusions, units and benchmark tolerances. Independently implement formulas and compare with supplied gold results. Supplement with external reference vectors. Do not confuse oracle-input arithmetic accuracy with end-to-end LLM accuracy.
2. **Controlled contract replay — completed pilot.** Run all configurations on paired valid/invalid variants. Retain every attempted call, rejection reason, runtime error and returned value. Measure gate-only latency separately from total task latency.
3. **Evidence annotation and independent challenge set — next.** Annotate actual source spans, analyte, unit, subject, encounter and measurement time. Use a clinical/domain reviewer for applicability and safety labels and an independent author for adversarial cases. Log ambiguous/unresolvable examples separately; never turn missing data into a guessed default. Include valid extreme measurements, ambiguous dates and legitimate historical calculations. Current evidence metadata is not a substitute for this work.
4. **Genuine LLM workflows — next.** Begin with a fixed development subset to measure actual error rates and token cost. Choose at least two materially different model families and freeze exact versions. Compare a single-agent and a three-role pipeline (extraction, selection/planning, execution) with and without enforcement under matched retry/tool budgets. A pipeline is not “multi-agent” merely because one function calls another. Run 3 independent repetitions where affordable and publish decoding settings and raw outputs. No model weights or paid API have been configured yet.
5. **Bounded repair — next.** Compare structured diagnostic errors with generic retry messages, at budgets k=0,1,2,3. Both conditions receive equal opportunities. A correction must be grounded in accessible evidence; irrecoverably missing inputs require abstention. No ground-truth value may be included in feedback. Measure unsafe-to-safe repair, regressions of initially correct calls, abstention accuracy, tokens and latency.
6. **Held-out evaluation and workflow validation — later.** Freeze contracts, code, prompts and analysis before official test execution. Evaluate overlapping benchmark families transparently; add an overlap-screened nested/multi-tool subset. Integrate synthetic FHIR records and then, if available, authorized real-record validation. Test repeated state changes, simultaneous conflicting updates, retries and result consumption. Define and implement the atomicity requirement rather than claiming it from this sequential simulator.

Do not keep rerunning or modifying the held-out protocol until results look favorable. Log all deviations, regressions, null findings and model failures. Readiness means credible evidence, not a predetermined positive result.

## Metric calculations

Let U be contract-invalid calls and V be valid controls. TP is an invalid call rejected **before execution**; FP is a valid call rejected; FN is an invalid call not rejected before execution; TN is a valid call not rejected. Runtime arithmetic exceptions are logged separately and are not credited as semantic interception.

- Interception recall = TP / |U|.
- Precision = TP / (TP + FP), undefined when nothing is rejected.
- F1 = 2 TP / (2 TP + FP + FN).
- Invalid execution-attempt rate = FN / |U|.
- Invalid result-release rate = invalid calls returning a value / |U|. A runtime exception may lower this rate without performing pre-execution validation.
- Valid false-rejection rate = FP / |V|.
- Valid answer coverage = valid cases returning an answer / |V|.
- Numeric accuracy over valid cases = correct returned answers / |V|, with abstentions counted as not correct. Also report accuracy conditional on answer coverage, so blanket abstention cannot appear successful.
- Benchmark arithmetic agreement uses the dataset's stored lower/upper limits. A stricter 0.1% relative comparison is also reported. The natural-task evaluator must use the appropriate tolerance for each tool, with exact matching for discrete outputs; numerical tolerance is not a safety margin.
- Repair success at k = initially invalid cases that become valid and numerically correct within k attempts / initially invalid, repairable cases. Report irreparable cases and their abstention separately. No repair rate is available from the current pilot.
- End-to-end correctness = tasks with appropriate tool selection, grounded inputs, correct calculation and justified final response / all tasks. Not measured here.
- Runtime overhead = paired guarded execution latency minus matched baseline latency; report gate-only and total pipeline p50/p95/p99, hardware, warmups, repetitions, tokens and actual cost separately.

Example from the measured development run: B3 rejected 1,640/2,040 invalid calls = 80.39%; B4 rejected 2,040/2,040 = 100%. Both rejected 0/800 valid controls. These are deliberate controlled faults, not independent observed clinical events. The 800 controls are four variants of 200 source annotations, not 800 independent patients.

Use paired, source-group bootstrap intervals for configuration differences; keep all variants/repetitions from a source together. The pilot uses 2,000 resamples over 199 source groups. Its intervals describe this constructed corpus and cannot be interpreted as clinical-risk confidence bounds. In the full study, preregister the primary comparison and correction for multiple secondary comparisons. Report effect sizes and uncertainty, not just p-values.

For planning independent held-out benign examples, zero failures among n independent cases has a one-sided exact 95% upper error bound of 1 - 0.05^(1/n). Approximately 299 independent cases with zero failures would support an upper bound near 1%. This calculation does not apply to the 800 correlated pilot controls. A separate pilot-informed sample-size calculation is needed for the primary paired model comparison.

## Go/no-go before manuscript drafting

The following are proposed engineering targets, not observed full-study results or journal acceptance criteria:

- Every implemented formula and unit rule has traceable sources and independent review; ambiguous labels are adjudicated.
- Source overlap, preprocessing, exclusions, model versions and costs are documented; confirmed held-out evaluations exist.
- Full-method invalid release is lower than the strongest comparable baseline with a source-group confidence interval supporting the prespecified effect; no claim of novelty from extra validators alone.
- Valid-call false rejection is acceptably low (proposed target <=2%, with uncertainty reported), and coverage/correctness are not sacrificed to blanket abstention.
- Generalization is demonstrated across model families and workflow settings, including independent adversarial cases and valid difficult controls.
- Evidence extraction and bounded repair are tested; failures caused by wrong but plausible source data are reported.
- Execution consistency is tested with the actual concurrency/transaction mechanism, not only deterministic replay.
- The full record, including null results and regressions, is preserved. If these requirements fail, improve the method on development data and revise the claim before writing.

The present pilot passes basic implementation checks but is **not ready for paper-level performance claims**.
