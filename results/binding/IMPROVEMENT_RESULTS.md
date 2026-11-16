# Source-backed runtime repair: measured improvement, v0.3

Actual CPU inference using Qwen2.5-1.5B-Instruct Q4_K_M. No fine-tuning, paid API, new prompts, or additional model calls for the selected repair adapter. Each method receives the same generated calculator call. Numerical agreement below means correct calculator selection plus a result inside the original benchmark interval; it is not independently adjudicated clinical correctness.

## Additional validation cases

Fifty previously unrun inference cases, five per calculator, selected before inference. Their source articles and normalized texts do not overlap the original 50 development cases. These records are from the training-derived 200-row arithmetic-audit pool; this is not the official test split or an untouched clinical dataset. Code/input hashes were frozen before inference and still match. No changes were made from validation outcomes.

| Method | Matching / all cases | Nonmatching results released | Blocked or failed | Matching / released |
|---|---:|---:|---:|---:|
| Unit/domain baseline (L2) | 37/50 (74%) | 11 | 2 | 37/48 |
| Original literal-quote gate (L3) | 11/50 (22%) | 2 | 37 | 11/13 |
| Source-backed repair (v2) | 39/50 (78%) | 0 | 11 | 39/39 |

All cases remain in the denominator, including abstentions and generation failures. The original gold references and answer tolerance are unchanged. Relative to L2, five previously nonmatching answers become matching, six nonmatching answers are blocked, and three previously matching answers are blocked. The two original generation failures remain failures. The observed four-point accuracy gain is uncertain; the strongest observed change is fewer nonmatching releases at lower coverage.

## Original development cases

The parser and repair rules were developed using these cases, so this table measures development fit. It must not be presented as held-out performance. The earlier schema-only executor matched 33/50 (66%); the stronger unit/domain baseline is the principal comparison below.

| Method | Matching / all cases | Nonmatching results released | Blocked or failed | Matching / released |
|---|---:|---:|---:|---:|
| Unit/domain baseline (L2) | 42/50 (84%) | 6 | 2 | 42/48 |
| Original literal-quote gate (L3) | 18/50 (36%) | 2 | 30 | 18/20 |
| Source-backed repair (v2) | 48/50 (96%) | 1 | 1 | 48/49 |

## What changed

The original small model still selects a calculator and proposes its inputs. The new deterministic adapter parses measurements from the source note, associates explicitly named variables and ordered lists, and reconstructs executable arguments from source text. It checks canonical value support, repairs a unit when the native number has one supported interpretation, and repairs a value only when there is one distinct explicitly named source quantity. Unsupported or ambiguous proposals abstain. Source packets are regenerated and checked against the note hash and formula version before execution.

The parser handles blood-pressure pairs, scientific platelet counts, shared-unit laboratory lists, and feet/inches. It rejects truncated compound units such as interpreting kg/m² as body weight in kg. The original model proposal is retained alongside every repair and source offset.

## Development alternative retained

The first prototype asked the same model to select observation IDs directly. It matched 23/50, released 23 nonmatching results, and abstained on 4. Its 50 new model calls, code and full negative results remain in `development_v1/`. It was rejected before the validation split was run. The final adapter replays the original stronger extractor. Thus development involved adaptive selection, which is disclosed rather than treated as preregistered evidence.

## Paired validation comparison and uncertainty

- Versus Unit/domain baseline (L2): 5 gained matching answers and 3 lost; change +4 percentage points. Exploratory calculator-stratified bootstrap 95% interval: -6 to +14 points; paired exact McNemar p=0.72656.
- Versus Original literal-quote gate (L3): 28 gained matching answers and 0 lost; change +56 percentage points. Exploratory calculator-stratified bootstrap 95% interval: +44 to +68 points; paired exact McNemar p=7.4506e-09.

The repair's descriptive Wilson 95% agreement interval is 64.8%–87.2%. Agreement at the stricter 0.1% tolerance is 39/50. The split is small, balanced by calculator, and not a random clinical sample. These intervals and exploratory comparisons do not establish patient safety or population performance.

## Validation by calculator

| Calculator | Cases | Unit/domain matching | Literal gate matching | Repair matching | Repair released |
|---|---:|---:|---:|---:|---:|
| CKD-EPI 2021 creatinine | 5 | 4 | 0 | 3 | 3 |
| Mean arterial pressure | 5 | 4 | 2 | 4 | 4 |
| BMI | 5 | 4 | 0 | 5 | 5 |
| Albumin-corrected calcium | 5 | 3 | 0 | 4 | 4 |
| QTc Bazett | 5 | 5 | 3 | 5 | 5 |
| FIB-4 | 5 | 1 | 0 | 2 | 2 |
| Corrected sodium | 5 | 5 | 1 | 5 | 5 |
| Calculated serum osmolality | 5 | 4 | 2 | 3 | 3 |
| Anion gap without potassium | 5 | 3 | 1 | 4 | 4 |
| Body surface area | 5 | 4 | 2 | 4 | 4 |

## Remaining validation failures

| Case | Calculator | Final outcome |
|---|---|---|
| train-442 | CKD-EPI 2021 creatinine | Rejected: AMBIGUOUS_OR_UNSUPPORTED_SOURCE:creatinine |
| train-456 | CKD-EPI 2021 creatinine | ValueError: BASELINE_EXTRACTION_FAILED |
| train-1453 | Mean arterial pressure | Rejected: AMBIGUOUS_OR_UNSUPPORTED_SOURCE:sbp |
| train-2571 | Albumin-corrected calcium | Rejected: AMBIGUOUS_OR_UNSUPPORTED_SOURCE:albumin |
| train-4315 | FIB-4 | Rejected: AMBIGUOUS_OR_UNSUPPORTED_SOURCE:platelets |
| train-4309 | FIB-4 | Rejected: AMBIGUOUS_OR_UNSUPPORTED_SOURCE:ast |
| train-4329 | FIB-4 | Rejected: AMBIGUOUS_OR_UNSUPPORTED_SOURCE:platelets |
| train-5714 | Calculated serum osmolality | Rejected: AMBIGUOUS_OR_UNSUPPORTED_SOURCE:sodium |
| train-5730 | Calculated serum osmolality | Rejected: AMBIGUOUS_OR_UNSUPPORTED_SOURCE:bun |
| train-6196 | Anion gap without potassium | Rejected: AMBIGUOUS_OR_UNSUPPORTED_SOURCE:bicarbonate |
| train-7486 | Body surface area | ValueError: BASELINE_EXTRACTION_FAILED |

## Cost, execution and integrity

Validation made 100 completed local calls: 50 planner and 50 extractor requests. All three gates reuse each common call. New request count in this improvement cycle is 150 including the failed development alternative. Original development replay uses no new model calls. Paid API cost is $0; local compute is still required. The validation workflows took 6.42 minutes in total, excluding model loading/downloads; this shared-CPU timing is descriptive.

Successful-repair field actions: {'canonical_source_match': 86, 'unique_named_source_repair': 2, 'source_unit_repair': 4}. These counts cover released cases only and do not count independent patient outcomes.

The audit reconstructs all validation prompts from allowed note/question inputs, checks request signatures and deterministic decoding settings, reconstructs model calls, replays all gates, verifies every released evidence substring, checks all 50 cases are retained, and confirms no duplicate request keys. Original development notes, gold labels, model trace, prompt builder, formula registry and baseline enforcement are byte-identical to v0.2. See `validation_repair_v2/audit.json`.

Thirty-five software tests passed, including ambiguous measurements, mutated source packets, stale formula versions, non-finite/boolean inputs, unit labels, compound units, ordered lists, and a regression that explicitly demonstrates the remaining timepoint limitation.

## Limits and next experiments

- A source-supported measurement can still be the wrong timepoint, subject, or clinical variable. This adapter does not establish trusted EHR provenance or admission-time semantics; the test suite includes an example where a later matching measurement passes.
- Pattern-based source parsing can fail or attach a label incorrectly. Reconstructing a packet only establishes consistency with this parser and source, not truth of the source or medical appropriateness.
- The original development case train-4318 retains its known platelet-label discrepancy; primary scores are not corrected or filtered. Reference-quality flags from v0.2 remain available. No systematic clinician adjudication has been performed on either split.
- One small quantized model, ten calculators, and 50 new cases are insufficient for a general performance claim. Public benchmark contamination during model pretraining is unknown.
- The next study should freeze the selected implementation, broaden model/calculator coverage, independently verify evidence/temporal labels, evaluate the official test split, and test conflicting observations and state updates. No real EHR integration or commit-time concurrency enforcement was added here.
- These experiments measure computational agreement and abstention, not clinical harm, prevented fatalities, or journal acceptance.

## Reproduce

```bash
python3 -m unittest discover -s tests -v
python3 run_source_repair.py --phase development
python3 score_source_binding.py --phase development --tag repair_v2
python3 score_source_binding.py --phase validation --tag repair_v2
python3 audit_source_repair.py --previous-archive ../MedCalc_Enforce_Experiments_v0_2.zip
python3 report_source_repair.py
```

Rescoring and repair replay require no model download. For fresh validation inference, first run `fetch_open_models.py`, preserve the bundled recorded output directory elsewhere, then run `python3 run_source_repair.py --phase validation`. The runner checks the frozen code/input hashes and skips completed cases; to record a separate repeat without overwriting the original, use `--tag repair_v2_repeat` and score that tag separately. Repeated inference is not a new independent validation set. If the v0.2 archive is unavailable, omit `--previous-archive`; all other integrity checks remain available.
