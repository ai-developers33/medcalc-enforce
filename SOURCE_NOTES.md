# Sources, attribution and formula notes

## Dataset provenance

MedCalc-Bench / MedCalc-Bench Verified, by the original NCBI/NLM benchmark authors and Verified maintainer Nikhil Khandekar:

- https://github.com/ncbi-nlp/MedCalc-Bench
- https://github.com/nikhilk7153/MedCalc-Bench-Verified
- https://huggingface.co/datasets/nsk7153/MedCalc-Bench-Verified
- Version used: v1.0.8; immutable commit `801592132bfd833f049b517a4e013e00a5fc40fa`.

The upstream repository and dataset card identify CC-BY-SA 4.0. The included development quantity annotations and derived fixtures are adaptations of that dataset under the same license: https://creativecommons.org/licenses/by-sa/4.0/ . Changes: deterministic training-row selection; parameter-name mapping; independent arithmetic; generated observation IDs/patient IDs/encounter IDs/times; synthetic faulty calls and event schedules. Source row identifiers and formula reference values are retained. In v0.2, 50 original development notes and questions are included in `data/live_inputs.jsonl` and repeated in model request logs under this same attribution/license. Generated outputs and annotations derived from these records are also supplied under CC-BY-SA 4.0. In v0.3, 50 additional selected training notes/questions are included in `data/binding_validation_inputs.jsonl` and model logs under the same attribution/license. Source-parsed quantities, offsets, and repair annotations are additional adaptations; all source row IDs remain attached. The full source datasets are not bundled.

MedCalc-Pro, Siran Zhao, Ruihui Hou, Ziyue Huai, Chennuo Zhang and Tong Ruan:

- https://aclanthology.org/2026.findings-emnlp.1512/
- https://github.com/easymoney7774/MedCalc-Pro
- Inspected commit `751a514644d22bc6f7066087205fbbb61b7b40f5`.

Its downloaded raw files are used only for the overlap audit and are excluded from the archive. No explicit data/code license was established from the reviewed root listing/README. Confirm reuse/redistribution terms before bundling this resource or publishing adaptations.

File-level SHA-256 hashes and immutable download URLs are in `data/download_manifest.json`.

## Formula and applicability sources

The ten equation definitions were inspected in the pinned Verified repository's `calculator_implementations` files. `medcalc/registry.py` implements the equations independently; no third-party Python code is executed.

CKD-EPI 2021 equation and adult applicability were also checked against:

- NIDDK: https://www.niddk.nih.gov/research-funding/research-programs/kidney-clinical-research-epidemiology/laboratory/glomerular-filtration-rate-equations/adults
- National Kidney Foundation, implementation verification Table S1: https://www.kidney.org/recommendations-implementing-ckd-epi-2021-race-free-egfr-calculation-guidelines-clinical

The eight rounded NKF eGFR test values are used in `tests/test_contracts.py`. The benchmark derives creatinine mass/molar conversion from molecular mass 113.12; the conventional clinical conversion of 88.4 micromol/L per mg/dL is rounded slightly differently. This prototype follows the benchmark convention and does not treat exact floating-point identity as clinical equivalence.

Corrected sodium uses the Hillier coefficient 2.4 per 100 mg/dL glucose increment, not the alternative 1.6 convention. BSA uses Mosteller. QTc uses Bazett; the benchmark rounds the intermediate RR interval, while the independent function retains precision. CKD-EPI is the 2021 creatinine equation with its specified coefficients. These choices must be pinned and reviewed for later studies.

Only explicitly listed units are supported. The prototype intentionally does not guess malformed units or composite age annotations. Negative/zero primitive quantities and inverted simultaneous pressure pairs are development contract violations; these rules are not an exhaustive clinical plausibility model. No healthy reference-range threshold is used.

## Relevant existing work

- AgentSpec: Customizable Runtime Enforcement for Safe and Reliable LLM Agents: https://arxiv.org/abs/2503.18666
- MedCalc-Pro: https://aclanthology.org/2026.findings-emnlp.1512/
- Synthea (synthetic records; not evaluated here): https://github.com/synthetichealth/synthea
- MIMIC-IV-Note (credentialed; not accessed): https://physionet.org/content/mimic-iv-note/2.2/
- eICU (credentialed; not accessed): https://physionet.org/content/eicu-crd/2.0/

Runtime predicates, validation, unit checks and evidence audits are not presumed novel. A formal contribution and fair comparisons remain necessary.

## Open-weight model sources and execution runtime

- Qwen publisher: https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF
- HuggingFaceTB publisher: https://huggingface.co/HuggingFaceTB/SmolLM2-1.7B-Instruct-GGUF
- Both model cards identify Apache-2.0. Publisher-provided Q4_K_M weights were
  downloaded directly, pinned to the immutable revisions and SHA-256 hashes in
  `data/open_models_manifest.json`. No fine-tuning was performed. Quantized model
  weights are not included in this archive.
- llama.cpp release b12211: https://github.com/ggml-org/llama.cpp/releases/tag/b12211
  (MIT-licensed upstream runtime; binary not redistributed in this bundle).
- Pinned server documentation:
  https://github.com/ggml-org/llama.cpp/blob/b12211/tools/server/README.md
- JSON-object and JSON-schema output constraints are server-side decoding
  features. They enforce output structure; they do not establish clinical facts.
- The two models are small CPU-feasible exploratory baselines, not a claim that
  they represent the strongest or newest free models available.

## v0.4 derived research records

The 44 initial official cases and the 80 additional eligible cases, source notes, case-level traces, prompts echoing those notes, and benchmark derivative annotations have the Verified dataset attribution and CC BY-SA 4.0 terms documented above. Fresh official model calls were generated with locally downloaded publisher weights. Qwen2.5-7B-Instruct Q4_K_M uses two verified publisher shards, identified in `data/official_larger_model_lock.json`. Model binaries and third-party raw corpora are excluded from the archive. The filtered study covers nine calculator types. Any external method or benchmark analysis has its own stated scope and source attribution.
