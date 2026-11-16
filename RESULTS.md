# MedCalc-Enforce v0.5 — BDCC Strengthening & Verification Report

All experiments below execute deterministically offline via `python3 run_bdcc_v05_suite.py` using only the Python standard library and SQLite WAL. Frozen v0.2/v0.3/v0.4 artifacts remain byte-identical for historical auditability.

## 1. Official 292-Trace Evaluation, Multiple-Testing Correction & Selective-Prediction AURC

- **Reference Entity Audit**: `expanded_registry.py` reconstructs **124/124 (100.0%)** official reference answers within benchmark bounds (resolving `official-283` platelet `mm^3` notation vs. 123/124 in v0.4).

| Model | Policy | Cases | Matched (%) | Unsafe Nonmatching (%) | Unanswered | AURC |
|---|---|---:|---:|---:|---:|---:|
| `qwen2.5_1.5b_q4km` | `baseline_unit_domain` | 124 | 98 (79.0%) | 16 (12.9%) | 10 | 0.0627 |
| `qwen2.5_1.5b_q4km` | `reviewed_v04` | 124 | 109 (87.9%) | 2 (1.6%) | 13 | — |
| `qwen2.5_1.5b_q4km` | `discourse_v05` | 124 | 110 (88.7%) | 2 (1.6%) | 12 | 0.0117 |
| `smollm2_1.7b_q4km` | `baseline_unit_domain` | 124 | 63 (50.8%) | 54 (43.5%) | 7 | 0.2586 |
| `smollm2_1.7b_q4km` | `reviewed_v04` | 124 | 106 (85.5%) | 2 (1.6%) | 16 | — |
| `smollm2_1.7b_q4km` | `discourse_v05` | 124 | 107 (86.3%) | 2 (1.6%) | 15 | 0.0166 |
| `qwen2.5_7b_q4km` | `baseline_unit_domain` | 44 | 38 (86.4%) | 3 (6.8%) | 3 | 0.0356 |
| `qwen2.5_7b_q4km` | `reviewed_v04` | 44 | 38 (86.4%) | 1 (2.3%) | 5 | — |
| `qwen2.5_7b_q4km` | `discourse_v05` | 44 | 40 (90.9%) | 1 (2.3%) | 3 | 0.0026 |

### Holm–Bonferroni and Benjamini–Hochberg Adjusted Paired Comparisons

| Comparison | Δ Agreement (95% Bootstrap CI) | Accuracy BH q | Unsafe Eliminated / Added | Safety BH q | Safety Holm p |
|---|---:|---:|---:|---:|---:|
| `qwen2.5_1.5b_q4km:baseline_vs_discourse_v05` | +9.7% (+3.2% to +16.1%) | 0.05098 | 15 / 1 | 0.0009338 | 0.003113 |
| `smollm2_1.7b_q4km:baseline_vs_discourse_v05` | +35.5% (+27.4% to +43.5%) | 9e-09 | 52 / 0 | 0 | 0 |
| `qwen2.5_7b_q4km:baseline_vs_discourse_v05` | +4.5% (-4.5% to +13.6%) | 0.9342 | 3 / 1 | 0.7031 | 1 |

## 2. Bounded Diagnostic Self-Repair (k = 1) vs. Ungrounded Critic Baseline

| Model | Cases | Ungrounded Critic Match / Unsafe | Strict Proposal (k=0) Match / Unsafe | Diagnostic Repair (k=1) Match / Unsafe | Repaired / Regressed |
|---|---:|---:|---:|---:|---:|
| `qwen2.5_1.5b_q4km` | 124 | 95 / 3 | 107 / 2 | 110 / 2 | 3 / 0 |
| `smollm2_1.7b_q4km` | 124 | 63 / 14 | 77 / 1 | 108 / 2 | 31 / 0 |
| `qwen2.5_7b_q4km` | 44 | 29 / 0 | 39 / 1 | 40 / 1 | 1 / 0 |

## 3. P = 3 Clinical Question Paraphrase & Cross-Sentence Discourse Robustness

- **372 Paraphrased Clinical Queries (124 Official Notes × 3 Non-Templated Wording Variants)**: `v0.4` matched **187/372 (50.3%)** with **41** unit/mismatch errors (due to rigid regex templates and ms-only QTc output), whereas `v0.5` matched **316/372 (84.9%)** with only **7** nonmatching outputs.
- **48 Adversarial Cross-Sentence Subject/Timepoint Traps**: `v0.4` falsely released **40/48 (83.3%)**, whereas `v0.5` stateful paragraph discourse tracking released **0/48 (0.0%)**.
- **124 Distractor-Prepended Official Notes (Paragraph Reset Check)**: `v0.5` preserved **110/124 (88.7%)** matching answers when a multi-sentence family-history block preceded the patient encounter.

## 4. Three Formal Falsification Controls

- **Control A (Note–Proposal Permutation across 117 same-calculator pairs)**: `unit_domain` falsely accepted **114/117 (97.4%)** wrong-patient calls, whereas exact canonical source matching accepted **0/117 (0.0%)**.
- **Control B (Corrupted Molar-Mass Table across 45 analyte cases)**: True molecular weights matched **45/45** vs. **3/45** under corrupted masses.
- **Control C (Discourse Polarity Inversion across 24 paired scenarios)**: Valid admission/patient notes released **24/24**; inverted brother/discharge headers released **0/24**.

## 5. Expanded 16-Calculator Suite & Nested Multi-Tool Provenance

| Calculator | Valid Released / Tested | Invalid Faults Intercepted / Tested |
|---|---:|---:|
| `61_CHA2DS2_VASc` | 20/20 | 20/20 |
| `62_CURB65` | 20/20 | 20/20 |
| `63_Wells_DVT` | 20/20 | 20/20 |
| `64_GCS` | 20/20 | 20/20 |
| `65_MELD_Na` | 20/20 | 20/20 |
| `66_Cockcroft_Gault` | 20/20 | 20/20 |

- **Nested Multi-Calculator Chained Provenance (BSA + eGFR → Absolute Dosing GFR)**: **36/36** valid chains verified; **36/36** cross-snapshot tampered chains intercepted.

## 6. Three-Policy SQLite WAL Concurrency & SHA-256 Audit Chain (324 Trials)

| Commit Policy | Trials | Published | Unsafe / Outdated Published | Benign False Withholds | Revalidated Saves |
|---|---:|---:|---:|---:|---:|
| `read_then_write` | 108 | 96 | 24 | 0 | 0 |
| `strict_revision_lock` | 108 | 48 | 0 | 24 | 0 |
| `semantic_field_commit_v05` | 108 | 72 | 0 | 0 | 24 |

- **Cryptographic Audit Integrity**: **108/108** SQLite WAL databases (**204** hash-chained events) passed full SHA-256 tamper-evident chain reconstruction.

## 7. BDCC Scalability & Multi-Worker Contention Matrix (Up to 100,000 Notes & 32 Workers)

- **Peak Throughput**: **4,258.8 checks/sec** | **Worst p95 at 100k Notes**: **20.028 ms** | **Audit Storage**: **309.94 MB / 10^6 events**.

| Ledger Notes | Workers | Operations | Throughput (checks/s) | p50 (ms) | p95 (ms) | p99 (ms) |
|---:|---:|---:|---:|---:|---:|---:|
| 1,000 | 1 | 800 | 4,258.8 | 0.240 | 0.279 | 0.325 |
| 1,000 | 4 | 800 | 3,796.4 | 0.267 | 4.388 | 6.681 |
| 1,000 | 8 | 800 | 3,404.3 | 1.217 | 7.237 | 9.953 |
| 1,000 | 16 | 800 | 3,007.1 | 3.914 | 10.812 | 15.573 |
| 10,000 | 1 | 800 | 4,215.2 | 0.241 | 0.280 | 0.347 |
| 10,000 | 4 | 800 | 3,335.8 | 1.019 | 2.649 | 3.780 |
| 10,000 | 8 | 800 | 3,104.0 | 1.968 | 5.985 | 8.344 |
| 10,000 | 16 | 800 | 2,948.7 | 3.992 | 11.534 | 16.083 |
| 50,000 | 1 | 800 | 4,163.3 | 0.246 | 0.282 | 0.356 |
| 50,000 | 4 | 800 | 3,293.7 | 1.090 | 2.345 | 3.053 |
| 50,000 | 8 | 800 | 3,120.9 | 2.111 | 6.102 | 7.965 |
| 50,000 | 16 | 800 | 2,967.4 | 4.214 | 11.582 | 14.807 |
| 100,000 | 1 | 800 | 4,092.8 | 0.250 | 0.286 | 0.336 |
| 100,000 | 4 | 800 | 3,298.6 | 1.097 | 2.451 | 3.301 |
| 100,000 | 8 | 800 | 3,139.3 | 2.007 | 6.148 | 8.322 |
| 100,000 | 16 | 800 | 2,972.0 | 4.318 | 10.655 | 14.289 |
| 100,000 | 32 | 800 | 2,864.1 | 6.989 | 20.028 | 26.406 |

---

# MedCalc-Enforce v0.4 experiment results

Two open-weight models executed the planner and extraction tasks on all 124 eligible distinct official test cases. A third, larger model ran on the same first 44 cases. That makes 292 model-case attempts on 124 underlying sources. An outcome matches when it uses the requested calculator and falls within the original answer interval. Every abstention, workflow failure and nonmatching release remains in the denominator. The original development figures from v0.3 are recorded separately in the historical report.

## All evaluated cases by model

| Model | Method | All cases | Within benchmark interval | Nonmatching release | No answer |
|---|---|---:|---:|---:|---:|
| Qwen2.5-1.5B | Unit and domain checks | 124 | 98 (79.0%) | 16 | 10 |
| Qwen2.5-1.5B | Original source repair | 124 | 106 (85.5%) | 3 | 15 |
| Qwen2.5-1.5B | Named measurements, without a model | 124 | 93 (75.0%) | 2 | 29 |
| Qwen2.5-1.5B | Combined candidate | 124 | 109 (87.9%) | 3 | 12 |
| Qwen2.5-1.5B | Combined candidate plus local context checks | 124 | 109 (87.9%) | 2 | 13 |
| SmolLM2-1.7B | Unit and domain checks | 124 | 63 (50.8%) | 54 | 7 |
| SmolLM2-1.7B | Original source repair | 124 | 76 (61.3%) | 5 | 43 |
| SmolLM2-1.7B | Named measurements, without a model | 124 | 93 (75.0%) | 2 | 29 |
| SmolLM2-1.7B | Combined candidate | 124 | 106 (85.5%) | 3 | 15 |
| SmolLM2-1.7B | Combined candidate plus local context checks | 124 | 106 (85.5%) | 2 | 16 |
| Qwen2.5-7B | Unit and domain checks | 44 | 38 (86.4%) | 3 | 3 |
| Qwen2.5-7B | Original source repair | 44 | 37 (84.1%) | 2 | 5 |
| Qwen2.5-7B | Named measurements, without a model | 44 | 28 (63.6%) | 2 | 14 |
| Qwen2.5-7B | Combined candidate | 44 | 38 (86.4%) | 2 | 4 |
| Qwen2.5-7B | Combined candidate plus local context checks | 44 | 38 (86.4%) | 1 | 5 |

The first official cohort was capped at five examples per calculator. The extension included all 80 remaining eligible distinct sources. It was locked before the first model’s official summary was scored. The larger model comparison was added separately. Its cohort was limited to the first 44. All models use the same underlying formulas. The global note-only row is deterministic and repeats across models evaluated on the same cases.

The combined candidate was frozen before official scoring. The additional context checks were developed from synthetic CLI review examples and locked while the first model was running, before the reviewer examined official results. Treat this reviewed row as a secondary analysis. Neither published benchmark answers nor scores enter runtime decisions.

## Paired comparisons and input agreement

| Model | Context-checked candidate gained / lost matches vs baseline | Paired exact p | All released inputs agree with annotations | Answer matches despite a discrepant input |
|---|---:|---:|---:|---:|
| Qwen2.5-1.5B | 18 / 7 | 0.04329 | 109/111 | 0 |
| SmolLM2-1.7B | 50 / 7 | 4.237e-09 | 105/108 | 1 |
| Qwen2.5-7B | 4 / 4 | 1 | 38/39 | 0 |

P values are exploratory and unadjusted for multiple methods and endpoints. Conditional field agreement is assessed against the benchmark entities with numeric relative tolerance 1e-5. Exact agreement on the reference quantity is more demanding than the benchmark answer interval. Confidence intervals, case IDs, calculator breakdowns and transition counts are included in each model report.

## Initial cohort for an equal comparison of model sizes

| Model | Method | All cases | Within benchmark interval | Nonmatching release | No answer |
|---|---|---:|---:|---:|---:|
| Qwen2.5-1.5B | Unit and domain checks | 44 | 33 (75.0%) | 7 | 4 |
| Qwen2.5-1.5B | Original source repair | 44 | 35 (79.5%) | 3 | 6 |
| Qwen2.5-1.5B | Named measurements, without a model | 44 | 28 (63.6%) | 2 | 14 |
| Qwen2.5-1.5B | Combined candidate | 44 | 36 (81.8%) | 3 | 5 |
| Qwen2.5-1.5B | Combined candidate plus local context checks | 44 | 36 (81.8%) | 2 | 6 |
| SmolLM2-1.7B | Unit and domain checks | 44 | 22 (50.0%) | 20 | 2 |
| SmolLM2-1.7B | Original source repair | 44 | 24 (54.5%) | 3 | 17 |
| SmolLM2-1.7B | Named measurements, without a model | 44 | 28 (63.6%) | 2 | 14 |
| SmolLM2-1.7B | Combined candidate | 44 | 34 (77.3%) | 2 | 8 |
| SmolLM2-1.7B | Combined candidate plus local context checks | 44 | 34 (77.3%) | 1 | 9 |
| Qwen2.5-7B | Unit and domain checks | 44 | 38 (86.4%) | 3 | 3 |
| Qwen2.5-7B | Original source repair | 44 | 37 (84.1%) | 2 | 5 |
| Qwen2.5-7B | Named measurements, without a model | 44 | 28 (63.6%) | 2 | 14 |
| Qwen2.5-7B | Combined candidate | 44 | 38 (86.4%) | 2 | 4 |
| Qwen2.5-7B | Combined candidate plus local context checks | 44 | 38 (86.4%) | 1 | 5 |

## Notes with extracted clinical narrative

All 124 questions repeat normalized question templates in the benchmark training data. Twenty QTc notes also match a training-note template after replacing numbers. None of the remaining 104 extracted notes reached 0.70 Jaccard similarity using number-masked token five-grams against the pinned training and one-shot notes. Exact normalized-note and source-key overlap is zero under the declared rule. This sensitivity analysis changes the mix of calculators because it removes the QTc family. It does not test generalization to novel requests or model pretraining exposure.

| Model | Method | All cases | Within benchmark interval | Nonmatching release | No answer |
|---|---|---:|---:|---:|---:|
| Qwen2.5-1.5B | Unit and domain checks | 104 | 78 (75.0%) | 16 | 10 |
| Qwen2.5-1.5B | Original source repair | 104 | 86 (82.7%) | 3 | 15 |
| Qwen2.5-1.5B | Named measurements, without a model | 104 | 73 (70.2%) | 2 | 29 |
| Qwen2.5-1.5B | Combined candidate | 104 | 89 (85.6%) | 3 | 12 |
| Qwen2.5-1.5B | Combined candidate plus local context checks | 104 | 89 (85.6%) | 2 | 13 |
| SmolLM2-1.7B | Unit and domain checks | 104 | 63 (60.6%) | 34 | 7 |
| SmolLM2-1.7B | Original source repair | 104 | 76 (73.1%) | 5 | 23 |
| SmolLM2-1.7B | Named measurements, without a model | 104 | 73 (70.2%) | 2 | 29 |
| SmolLM2-1.7B | Combined candidate | 104 | 86 (82.7%) | 3 | 15 |
| SmolLM2-1.7B | Combined candidate plus local context checks | 104 | 86 (82.7%) | 2 | 16 |
| Qwen2.5-7B | Unit and domain checks | 39 | 33 (84.6%) | 3 | 3 |
| Qwen2.5-7B | Original source repair | 39 | 32 (82.1%) | 2 | 5 |
| Qwen2.5-7B | Named measurements, without a model | 39 | 23 (59.0%) | 2 | 14 |
| Qwen2.5-7B | Combined candidate | 39 | 33 (84.6%) | 2 | 4 |
| Qwen2.5-7B | Combined candidate plus local context checks | 39 | 33 (84.6%) | 1 | 5 |

## What each code change contributes

The baseline executes the model-proposed quantities with unit conversion and arithmetic checks. The original repair rebinds those proposals to quantities in the note. The combined version uses question-based calculator selection and falls back to a complete set of unique, explicitly named measurements if the model call is missing or unsupported. The secondary guard additionally checks for explicit subject, measurement-status, time and output-statistic conflicts. A note-only comparator measures what the same templated questions and named fields allow without model inference.

All policies remain subject to source parsing errors and missing context. The engineering review documents cases that passed substring verification despite using a relative’s weight or a target weight. The local guard fixed the explicit examples and still failed two fresh probes in which another sentence supplied the subject or time. A locally supported value can still be a wrong-time or wrong-person value.

The equal-coverage analysis ranks baseline releases by the proportion of individually supported source quotes and integrates tie breaking. It also reports uniform thinning, per-calculator quotas, and answers released on identical cases. The comparisons are retrospective diagnostics. Detailed model-by-model results and uncertainty are in [the paired ablation report](results/official_ablations/REPORT.md).

## Temporal and commit-time experiments

In 19 authored temporal scenarios, the structured-section guard matched 10 of 12 answerable requests, withheld the other two, and abstained on all seven ambiguous or incomplete requests. The comparisons used four calculators and 17 distinct texts. The earlier narrative validation set contained zero compatible sectioned notes among 45 explicitly requesting first-admission measurements. The temporal guard is a separate structured-input policy with a narrower contract.

In 216 controlled two-connection SQLite trials, the read-then-write baseline published 36 superseded revisions in its 108 trials. Twelve of those had an outdated numerical value. The atomic publication check published zero superseded revisions in 108 trials. It withheld 24 otherwise numerically valid answers after an irrelevant addendum or an edit that restored the original value. These schedules test the local publication invariant and its coverage cost. They do not measure production incidence. The reference experiment used BMI. The integrated checked store also has regression coverage for an edit between staging and publication.

## Arithmetic and source integrity

A Decimal implementation reconstructed all 124 reference answers from 303 annotated fields within 0.1%. Four osmolality rationales repeat the BUN value in the displayed glucose term despite a matching reference answer. One annotated blood-pressure unit is absent directly after the pressure pair. The original registry rejects one unusual count-volume spelling. All labels were preserved; the separate offline field-level audit supports the reported input comparisons.

## Scope and remaining evidence

Nine calculator families survived the full training and one-shot source exclusion. Anion gap had no eligible independent official cases under these rules. The Q4_K_M weights and decoding configuration are pinned. Replicates on the same notes with multiple models remain paired measurements. Accuracy on these notes does not establish patient outcomes, clinical validation, hospital deployment or end-to-end correctness under distributed EHR updates.

A transfer audit considered MedCalc-Pro Simple. All 200 records spanning the supported families shared sources with the existing evaluation or development data. The audit therefore produced no independent external estimate. The published framework comparison is documented in [the methods comparison](results/code_review/RELATED_METHODS.md) with its actual execution scope.

The next substantive validation would be blinded review of variable identity, units, timepoint and appropriateness on independent notes with new question wording. Each reviewer should see the source and requested computation before seeing system output. The public score set can support retrospective error analysis; it has now been evaluated.


## Measured local execution time

| Method | Timed attempts | Median milliseconds | 95th percentile milliseconds |
|---|---:|---:|---:|
| unit_domain | 150 | 0.018 | 0.039 |
| checked_calculator | 150 | 3.954 | 18.039 |
| checked_and_published | 150 | 4.122 | 16.367 |

Fifty earlier cases were timed three times each in shuffled order. Timing includes abstentions, excludes model generation and was measured on a shared CPU. Publication includes local durable SQLite operations. Latencies describe this run only.

## Reproduce

Run `python3 verify_release.py` from the unpacked project to verify checksums and reproduce the main decisions and totals from retained model generations. See [the protocol](OFFICIAL_PROTOCOL.md) for fresh inference commands. [The per-case artifacts](results/final_evaluation/) retain nonmatching answer IDs, reasons for abstention, evidence spans, repaired values and per-model diagnostics.
