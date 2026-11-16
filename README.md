# MedCalc-Enforce v0.6 — MDPI *Big Data and Cognitive Computing* Replication Package

**Author:** Ravi Shanker Thadishetti (ORCID: `0009-0000-7088-0531`) · **License:** MIT · **API Cost:** `$0.00` (100% Open-Weight GGUF + Python Standard Library)

This repository contains the complete source code, 860 live open-weight LLM execution traces (`Qwen2.5-1.5B`, `SmolLM2-1.7B`, `Phi-3.5-mini-3.8B`, `Qwen2.5-7B`, and `Meta-Llama-3.1-8B`), zero-tuning out-of-vocabulary (`OOV`) discourse transfer benchmarks (`N = 64`), SQLite WAL concurrency and 100k-note scalability suites, 75 automated regression tests, and the Google Colab T4 GPU notebook reproducing all tables and figures in the manuscript.

## 1. Instant Offline Verification & Metric Reproduction (< 60 Seconds, CPU Only, Standard Library Only)

No GPU, network access, or third-party pip packages are required to verify all checksums, replay all 860 stored LLM traces, run all 75 unit tests, and regenerate every statistical table in the manuscript:

~~~sh
python3 verify_release.py
python3 run_bdcc_v05_suite.py
python3 run_reviewer_fixes_v06.py
~~~

- `results/v0_5_bdcc/summary.json` — Complete 5-model official evaluation (`620` runs), `240` live cross-sentence distractor runs, bounded $k=1$ diagnostic repair, $P=3$ clinical paraphrases (`372` queries), 3 falsification controls, 16-calculator discrete/chained suite, 324 SQLite WAL concurrency trials, and 17-cell scalability matrix.
- `results/v0_5_bdcc/reviewer_fixes_v06.json` — Provenance-tier attribution (`Tier 1.0`, `Tier 0.85`, `Tier 0.70` vs. pure regex `note_only_v05`), zero-tuning OOV clinical discourse transfer (`data/oov_discourse_transfer_64.jsonl`), complete `11/620` residual error root-cause taxonomy, and 10,000-resample patient-case-clustered paired bootstrap statistics.

## 2. Live End-to-End GPU Reproduction on Free-Tier Google Colab (NVIDIA T4, $0 API Spend)

1. Open `MedCalc_Enforce_v0_6_Colab_Live_Reproduction.ipynb` (included in this repository) in Google Colab and select **Runtime -> Change runtime type -> T4 GPU**.
2. Upload or clone this repository into `/content/` and run all cells sequentially.
3. The notebook verifies SHA-256 digests for all five `Q4_K_M` GGUF models from Hugging Face against `llama.cpp` (`llama-server`, `temperature=0`, `seed=731`, with `--no-jinja` grammar isolation on `Phi-3.5-mini`), executes live tool planning and argument extraction across the locked official (`N = 124`) and adversarial (`N = 48`) cohorts, and runs `verify_release.py`.

---

# MedCalc-Enforce research experiments, v0.5 (BDCC Strengthened Package)

[BDCC v0.5 strengthened results](results/v0_5_bdcc/BDCC_STRENGTHENED_RESULTS.md) · [Official v0.4/v0.5 summary](RESULTS.md) · [Locked study protocol](OFFICIAL_PROTOCOL.md) · [Source attribution](SOURCE_NOTES.md)

Version 0.5 resolves all cross-version reproducibility, cross-sentence discourse, commit-freshness, and unit-coverage limitations identified in the v0.4 engineering review while keeping every v0.2/v0.3/v0.4 frozen file byte-identical for historical auditability:

1. **Cross-Python Deterministic Release Verification (`verify_release.py`, `analyze_official_ablations.py`)**: Replaces platform-dependent float `sum()` with `round(math.fsum(...), 12)` across calculator strata so `verify_release.py` produces identical SHA-256 digests on Python 3.10 through 3.14.
2. **Unified Stateful Discourse & Delta-Quantity Guard (`medcalc.discourse_guard`, `unified_calculator.py` / `medcalc-enforce`)**: Tracks forward-framing paragraph/section headers (`Family history:`, `belong to his brother`, `Discharge measurements are listed below`) across sentence boundaries, blocks relative weight-loss/gain deltas (`lost 6 kg of weight` in `official-749`), supports requested output-unit conversion (`s` vs `ms` on Bazett QTc), and resolves `mm^3` platelet counts (`official-283`, reaching **124/124 = 100.0%** official reference reconstruction). Passes **8/8** smoke checks and **4/4** extended CLI stress checks (`--require-all`), blocks **48/48** cross-sentence traps, and improves official benchmark matches across all three evaluated models (`110/124` on Qwen2.5-1.5B, `107/124` on SmolLM2-1.7B, and `40/44` on Qwen2.5-7B).
3. **Field-Projected Semantic Snapshot Revalidation & Tamper-Evident Audit Chain (`medcalc.semantic_commit`)**: Eliminates **24/24** benign false withholdings caused by irrelevant note addenda or edit-and-restore cycles under SQLite WAL concurrency (`0/108` stale or unsafe publications, `0/108` benign false withholdings) and records every stage/publish/withhold event in an append-only SHA-256 hash-chained `audit_log`.
4. **Expanded 16-Calculator Registry & Chained Provenance (`medcalc.expanded_registry`)**: Adds six discrete/hybrid clinical calculators (`CHA2DS2-VASc`, `CURB-65`, `Wells DVT`, `GCS`, `MELD-Na`, `Cockcroft-Gault`) with `120/120` valid and `120/120` fault-interception accuracy plus `72/72` verified two-stage nested calculator chains.
5. **Complete Offline BDCC Statistical & Scalability Suite (`run_bdcc_v05_suite.py`)**: Computes 10,000-resample calculator-stratified paired bootstrap CIs, Holm–Bonferroni and Benjamini–Hochberg FDR `q`-values, Selective-Prediction Risk–Coverage (`AURC`) curves, bounded diagnostic self-repair (`k = 0, 1`), `P = 3` clinical question paraphrases (`N = 372`), three formal falsification controls, and a 17-cell scalability matrix up to **100,000 stored encounter notes and 32 concurrent workers**.

## Quickstart (v0.5)

~~~sh
python3 verify_release.py
python3 run_bdcc_v05_suite.py
echo '{"question":"What was the patient's admission BMI?","note":"Discharge measurements are listed below. Height 180 cm. Weight 90 kg."}' | python3 unified_calculator.py
~~~

---

# MedCalc-Enforce research experiments, v0.4

[Official results and limitations](RESULTS.md) · [Locked study protocol](OFFICIAL_PROTOCOL.md) · [Source attribution](SOURCE_NOTES.md)

The package evaluates whether calculator arguments proposed by open-weight models are supported by clinical benchmark notes. The new official study covers 124 source-distinct records, nine calculator families, two models on all records and one larger model on the initial 44 records. Each numerical answer is scored against the original benchmark interval. The archive contains model transcripts, references, per-case decisions, software, and the installable runtime.

## Run the research tool

Python 3.12 is the recorded runtime. The wheel uses only the standard library. From the unpacked project directory:

~~~sh
python3 -m pip install --no-index --no-deps dist/medcalc_enforce_research-0.4.0-py3-none-any.whl
echo '{"question":"What is the mean arterial pressure?","note":"Blood pressure 120/75 mmHg."}' | medcalc-check
~~~

The command returns 90.0 with both source offsets. A request can also contain a generated calculator call under the key `call`. An unsupported request or conflicting measurement returns a decision with `released: false`. Questions in the official study follow a small set of recurring calculator templates. Subject, measurement status, and clinical timeline extraction from unrestricted prose remain imperfect.

## Reproduce the results

~~~sh
python3 verify_release.py
~~~

This offline command verifies packaged checksums, runs the regression suite in a temporary copy, reconstructs logged requests and calculator decisions, and recomputes the paired analyses. It consumes the stored model generations and requires no model download. For the original inference commands and complete source-disjoint selection procedure, see [OFFICIAL_PROTOCOL.md](OFFICIAL_PROTOCOL.md). The additional 7B model, on the initial cohort only, uses `python3 official_larger_model.py fetch` and `python3 official_larger_model.py infer` after downloading the study runtime. Tokens, compute, inference failures and abstentions are part of the evidence.

## Entry points and their intended use

| Entry point | Behavior evaluated |
|---|---|
| `medcalc-check` | Combines deterministic question routing, model proposal checking, a fallback using explicitly named fields, and local context checks. |
| `medcalc-experiment` | Runs the combined candidate before the secondary context checks. `--note-only` measures the effect of computing from named source fields alone. |
| `medcalc.checked_store.execute_and_publish` | Binds a calculation to a caller-supplied encounter and note revision. Checks revision and digest atomically at local publication. |
| `medcalc.temporal_guard` | Supports time-bound decisions in the explicit section grammar tested in the synthetic challenge. |

The transaction experiment exercised the prior source-repair execution path in local SQLite. Two additional integration tests exercise the reviewed execution path with transactional publication. All numerical benchmark runs used offline notes. None of these paths have been independently clinically validated.

## Evidence directories

- `results/final_evaluation/` contains per-model decisions, cumulative metrics, matched-field checks, and the separate narrative-note analysis.
- `results/official_ablations/` contains comparisons at equal release counts, same-case comparisons and individual repair ablations.
- `results/code_review/` contains the secondary freeze, reviewed synthetic failures and comparisons to published methods.
- `results/commit_publication/` and `results/temporal_challenge/` contain controlled engineering experiments.
- `results/reference_audit/` and `results/template_audit/` document arithmetic reconstruction and overlap across train, one-shot and official test sets.
- `results/binding/` records all earlier versions including the failed observation-ID selector. The older protocol below describes their historical context.

---

## Historical v0.3 package notes

Development pilot for the agreed BDCC working title:

**When Syntactically Valid Tool Calls Are Clinically Unsafe: Deterministic Runtime Enforcement for Clinical Calculator Calls in Multi-Agent EHR Systems**

This package contains controlled validator experiments and an actual local open-weight LLM development pilot. It is not a manuscript or a clinically validated calculator service. The controlled fault-injection results and natural model-output results are separate experiments.

## Start here

- `results/binding/IMPROVEMENT_RESULTS.md`: latest improvement, paired results, tradeoffs and uncertainty.
- `SOURCE_REPAIR_PROTOCOL.md`: selected source-backed repair and frozen validation design.
- `data/binding_freeze.json`: code/input hashes recorded before new validation inference.
- `results/binding/validation_repair_v2/`: all 50 new cases, 100 raw requests, scores and integrity audit.
- `results/binding/development_repair_v2/`: original 50-case development replay.
- `results/binding/development_v1/`: retained unsuccessful observation-ID prototype.

The selected v0.3 adapter matches **39/50 (78%)** new validation answers versus
**37/50 (74%)** for the unit-aware baseline. Nonmatching released answers fall
from **11 to 0**, while blocked/failed cases increase from **2 to 11**. The
adapter gains five matching answers and blocks three previously matching ones.
The small accuracy gain is uncertain in this sample. On the original tuning
cases it matches 48/50 (96%); that is development fit, not held-out performance.
All numbers preserve original labels, tolerances and failed cases. No paid API
or extra model call is used by the selected adapter.

Earlier v0.2 results remain available:

- `results/live/LIVE_RESULTS.md`: actual open-weight inference results and limitations.
- `LIVE_PROTOCOL.md`: live pilot design and transparently documented decoding amendment.
- `results/live/summary.json` and `scored_cases.json`: calculated live metrics and case-level results.
- `results/live/ERROR_ANALYSIS.md`: a concrete unit-label failure, quote-gate tradeoffs, and a source-checked reference annotation discrepancy.
- `results/live/*q4km*.jsonl`: complete model requests, responses, generated calls, and replayed gate outcomes for both decoding variants.
- `EXPERIMENT_PROTOCOL.md`: datasets, hypotheses, full experiment design, metric formulas, and readiness criteria.
- `results/PILOT_RESULTS.md`: measured offline results and their limits.
- `results/dataset_audit.json`: verified sizes, overlap counts, and development exclusions.
- `results/pilot_summary.json`: counts, metrics, grouped bootstrap, and measured gate latency.
- `results/metrics_by_fault.csv`: every configuration broken down by fault category.
- `results/trial_results.jsonl`: all 28,400 configuration/case records.
- `results/fixtures.jsonl`: the 2,840 controlled inputs, including simulated ledger state before and after updates.
- `data/pilot_rows.jsonl`: the 200 development annotations needed to reproduce the pilot offline.
- `SOURCE_NOTES.md`: exact source commits, attribution, formula versions, and limitations.

## Reproduce the offline pilot

Python 3.10 or newer; standard library only. No model credentials, GPU, package installation, or external service is needed for this command.

```bash
python run_pilot.py
python -m unittest discover -s tests -v
```

Existing result files are replaced by the new run. Copy `results/` first if you want to preserve the recorded timing sample. Semantic outcomes should reproduce; hardware timings will vary.

To repeat the complete data audit and development selection, first download the pinned public files (approximately 69 MB in total), then run:

```bash
python fetch_data.py
python prepare_data.py
python run_pilot.py
```

`fetch_data.py` checks SHA-256 hashes and never downloads or executes third-party code. Raw full datasets are excluded from this archive. Derived pilot annotations and the 100 development/validation input notes are included with dataset attribution. The audit can be reproduced with the pinned downloads.

## Reproduce local model inference

Linux x86-64 and Python 3.12+, approximately 2.2 GB download/cache space for weights
and the CPU runtime, plus working memory for one quantized model at a time. The
recorded run used about 10 GB total system RAM and eight inference threads;
no GPU or paid API was used. No API key is required. The downloaded runtime is
a pinned prebuilt llama.cpp release; its archive and model digests are verified.

```bash
python fetch_open_models.py
python run_live_models.py --mode object
python run_live_models.py --mode schema
python score_live.py
python report_live.py
```

Run commands sequentially. Existing logged cases are skipped, including failures.
To perform a new measured run, archive/rename `results/live/` first. The bundled
raw traces can be rescored immediately without downloading models or executing
inference: use only the last two commands. Model outputs can vary with runtime,
quantization, hardware and decoding despite a fixed seed. Server logs and hashes
make the recorded run inspectable. Inference is limited to localhost.

## What has run

1. Full metadata/overlap audit of MedCalc-Bench Verified train/test and MedCalc-Pro simple/nested/multi files.
2. Deterministic selection of 20 training annotations for each of ten equation calculators, excluding known source overlap with the Verified test split.
3. Independent arithmetic reconstruction against those 200 reference answers.
4. Controlled replay: five baselines/configurations plus five ablations, 2,840 cases each.
5. Source-group bootstrap for paired invalid-result-release differences.
6. Warm gate-only latency measurement and eleven software checks, including eight external NKF reference vectors in one parameterized check.
7. Two local open-weight models with planner/extractor roles, JSON-object and tool-schema decoding variants, and three gate replays per generated call. See the live report for the exact counts, numerical agreement, failures and measured compute.
8. Seventeen software checks, including strict JSON handling, input separation, unit conversion, the literal gate's limitations, and scoring denominators.
9. A 50-call development observation-ID prototype (unsuccessful; retained), followed by deterministic source-backed repair of original model proposals.
10. Frozen validation on 50 additional source-disjoint cases: 100 new local Qwen requests, three paired gate evaluations, 35 software tests in total, and a byte-level preservation/replay audit.

## What has not run

- Independent clinician-verified evidence-span annotation.
- Bounded LLM self-repair, larger-model validation, or prompt/model optimization on a separate tuning set.
- The official 1,100-case test set as a performance evaluation.
- MedCalc-Pro inference, AgentSpec reproduction, or an LLM critic comparison.
- Synthea/FHIR integration or credentialed real EHR experiments.
- Independent clinical adjudication, deployment testing, or patient outcome evaluation.

## Trust boundary

The simulated ledger is constructed from supplied benchmark annotations. Evidence identifiers, patient/encounter identities, and timestamps are generated fixture metadata, not recovered EHR provenance. The verifier checks consistency against this trusted ledger. It cannot establish that the ledger itself is correct; an explicit regression test demonstrates that a coherently corrupted ledger can pass.

The current formula policy is a research specification. Successful execution means the implemented predicates passed. It does not establish clinical appropriateness, absence of all harms, or novelty. The sequential update simulation does not provide production concurrency control.

The live experiment does not construct a supposedly trusted ledger from model
output. Its original L3 check verifies only literal quote/value consistency
against the original note. The v0.3 adapter reconstructs arguments from a
pattern-based source parser and checks their support. Neither establishes
correct clinical variable or timepoint selection, independently trusted patient
identity, or source truth. A later measurement can still pass.
There are no real EHR updates in this live pilot, so it provides no new evidence
for commit-time enforcement. Neither pilot supports a mortality claim.

## Reproduce the selected v0.3 repair

Rescore and audit the bundled validation without model downloads:

```bash
python3 run_source_repair.py --phase development
python3 score_source_binding.py --phase development --tag repair_v2
python3 score_source_binding.py --phase validation --tag repair_v2
python3 audit_source_repair.py
python3 report_source_repair.py
```

To also verify byte-identical preservation of the previous package, supply
`--previous-archive /path/to/MedCalc_Enforce_Experiments_v0_2.zip` to the audit.
To record a separate inference repeat after `fetch_open_models.py`, run
`python3 run_source_repair.py --phase validation --tag repair_v2_repeat` and
score that tag. Keep the original recorded directory for inspection. Repeated
runs on the same cases are not additional independent validation evidence.
The runner enforces the frozen code/input hashes; modified implementations
require a new study version and a new validation split.

`SOURCE_BINDING_PROTOCOL.md` and `run_source_binding.py` document the rejected
ID-selection alternative. They are retained for transparency; the selected
entry point is `run_source_repair.py`.
