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
| `qwen2.5_7b_q4km` | `baseline_unit_domain` | 124 | 108 (87.1%) | 11 (8.9%) | 5 | 0.0610 |
| `qwen2.5_7b_q4km` | `reviewed_v04` | 124 | 112 (90.3%) | 1 (0.8%) | 11 | — |
| `qwen2.5_7b_q4km` | `discourse_v05` | 124 | 114 (91.9%) | 1 (0.8%) | 9 | 0.0006 |
| `phi3.5_mini_q4km` | `baseline_unit_domain` | 124 | 102 (82.3%) | 16 (12.9%) | 6 | 0.0797 |
| `phi3.5_mini_q4km` | `reviewed_v04` | 124 | 110 (88.7%) | 3 (2.4%) | 11 | — |
| `phi3.5_mini_q4km` | `discourse_v05` | 124 | 110 (88.7%) | 4 (3.2%) | 10 | 0.0304 |
| `llama3.1_8b_q4km` | `baseline_unit_domain` | 124 | 106 (85.5%) | 10 (8.1%) | 8 | 0.0232 |
| `llama3.1_8b_q4km` | `reviewed_v04` | 124 | 111 (89.5%) | 2 (1.6%) | 11 | — |
| `llama3.1_8b_q4km` | `discourse_v05` | 124 | 113 (91.1%) | 2 (1.6%) | 9 | 0.0106 |

### Holm–Bonferroni and Benjamini–Hochberg Adjusted Paired Comparisons

| Comparison | Δ Agreement (95% Bootstrap CI) | Accuracy BH q | Unsafe Eliminated / Added | Safety BH q | Safety Holm p |
|---|---:|---:|---:|---:|---:|
| `qwen2.5_1.5b_q4km:baseline_vs_discourse_v05` | +9.7% (+3.2% to +16.1%) | 0.08496 | 15 / 1 | 0.001112 | 0.005371 |
| `smollm2_1.7b_q4km:baseline_vs_discourse_v05` | +35.5% (+27.4% to +43.5%) | 1.5e-08 | 52 / 0 | 0 | 0 |
| `qwen2.5_7b_q4km:baseline_vs_discourse_v05` | +4.8% (-0.8% to +10.5%) | 0.3589 | 11 / 1 | 0.008656 | 0.03809 |
| `phi3.5_mini_q4km:baseline_vs_discourse_v05` | +6.5% (+1.6% to +11.3%) | 0.2063 | 13 / 1 | 0.003433 | 0.01465 |
| `llama3.1_8b_q4km:baseline_vs_discourse_v05` | +5.6% (+0.0% to +11.3%) | 0.2839 | 9 / 1 | 0.02407 | 0.08594 |

## 2. Bounded Diagnostic Self-Repair (k = 1) vs. Ungrounded Critic Baseline

| Model | Cases | Ungrounded Critic Match / Unsafe | Strict Proposal (k=0) Match / Unsafe | Diagnostic Repair (k=1) Match / Unsafe | Repaired / Regressed |
|---|---:|---:|---:|---:|---:|
| `qwen2.5_1.5b_q4km` | 124 | 95 / 3 | 107 / 2 | 110 / 2 | 3 / 0 |
| `smollm2_1.7b_q4km` | 124 | 63 / 14 | 77 / 1 | 108 / 2 | 31 / 0 |
| `qwen2.5_7b_q4km` | 124 | 85 / 2 | 113 / 1 | 114 / 1 | 1 / 0 |
| `phi3.5_mini_q4km` | 124 | 102 / 7 | 109 / 4 | 110 / 4 | 1 / 0 |
| `llama3.1_8b_q4km` | 124 | 106 / 2 | 113 / 2 | 113 / 2 | 0 / 0 |

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

- **Peak Throughput**: **2,881.8 checks/sec** | **Worst p95 at 100k Notes**: **45.438 ms** | **Audit Storage**: **309.94 MB / 10^6 events**.

| Ledger Notes | Workers | Operations | Throughput (checks/s) | p50 (ms) | p95 (ms) | p99 (ms) |
|---:|---:|---:|---:|---:|---:|---:|
| 1,000 | 1 | 800 | 2,881.8 | 0.357 | 0.419 | 0.465 |
| 1,000 | 4 | 800 | 2,133.9 | 1.297 | 5.048 | 7.513 |
| 1,000 | 8 | 800 | 1,892.4 | 3.228 | 9.475 | 15.452 |
| 1,000 | 16 | 800 | 1,906.9 | 6.776 | 16.388 | 20.140 |
| 10,000 | 1 | 800 | 2,764.9 | 0.363 | 0.467 | 0.564 |
| 10,000 | 4 | 800 | 2,166.5 | 0.950 | 6.008 | 10.047 |
| 10,000 | 8 | 800 | 1,942.0 | 3.248 | 9.129 | 13.747 |
| 10,000 | 16 | 800 | 1,822.8 | 6.787 | 16.871 | 24.184 |
| 50,000 | 1 | 800 | 2,520.9 | 0.384 | 0.588 | 0.718 |
| 50,000 | 4 | 800 | 2,145.0 | 0.932 | 5.854 | 11.084 |
| 50,000 | 8 | 800 | 1,796.1 | 2.852 | 12.652 | 27.753 |
| 50,000 | 16 | 800 | 1,585.3 | 0.650 | 39.488 | 68.136 |
| 100,000 | 1 | 800 | 1,691.8 | 0.595 | 0.733 | 0.921 |
| 100,000 | 4 | 800 | 1,678.8 | 0.636 | 8.596 | 12.328 |
| 100,000 | 8 | 800 | 1,682.8 | 0.618 | 23.091 | 38.237 |
| 100,000 | 16 | 800 | 1,427.7 | 0.795 | 45.438 | 65.963 |
| 100,000 | 32 | 800 | 1,852.0 | 11.118 | 28.969 | 39.944 |

## 8. Live 5-Model Inference on 48 Cross-Sentence Clinical Distractor Traps (240 Live Workflows)

| Model | Traps | `unit_domain` False Releases (%) | `reviewed_v04` False Releases | `discourse_v05` False Releases (%) | Holm-Adjusted p | BH q |
|---|---:|---:|---:|---:|---:|---:|
| `qwen2.5_1.5b_q4km` | 48 | 48 (100.0%) | 48 | 0 (0.0%) | 0 | 0 |
| `smollm2_1.7b_q4km` | 48 | 48 (100.0%) | 48 | 0 (0.0%) | 0 | 0 |
| `qwen2.5_7b_q4km` | 48 | 25 (52.1%) | 48 | 0 (0.0%) | 5.96e-08 | 5.96e-08 |
| `phi3.5_mini_q4km` | 48 | 48 (100.0%) | 48 | 0 (0.0%) | 0 | 0 |
| `llama3.1_8b_q4km` | 48 | 48 (100.0%) | 48 | 0 (0.0%) | 0 | 0 |
