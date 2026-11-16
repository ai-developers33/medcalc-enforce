# Official MedCalc-Bench Verified evaluation

This study evaluates the archived source-repair software with two pinned local open-weight models on previously unrun records from the official test split. The official benchmark has 1,100 total questions and 200 questions for the ten implemented calculators. Ground-truth answers and intervals are available only to the selection export and retrospective scorer. Neither the inference workflow nor the source-repair policy reads a reference file.

## Cohorts and selection

The first cohort targeted up to five entries per supported calculator. A deterministic SHA-256 ordering within each calculator used the calculator ID, official row number and a fixed seed. Rows sharing a source key or exact normalized note with any of the 10,538 training rows or 55 one-shot examples were excluded. Source keys use the article for PMC, the item identifier for USMLE, and the calculator, note type and note ID for other records. Deduplication applies across the selected cohort. The ordinal ordering of calculators resolves a source appearing more than once across calculators. These checks establish separation under these specific identifiers and text rules. Undetected near-duplicates, templates, and prior model exposure to public records remain possible.

This yielded 44 cases across nine calculators. All 20 official anion-gap rows failed the inclusion rules. Four eligible osmolality records were available. The subsequent extension selected every remaining eligible distinct source and text, yielding another 80 cases. Its lock was written during first-cohort inference, before the first model finished or scores had been inspected. The original sample and extension have disjoint source keys, normalized texts and row IDs. Together the two sets include 124 sources, with 104 extracted and 20 template notes. The partial cohort and complete eligible-sample results can be reported separately. Each model receives the same cases, so the two models provide repeated evaluations of 124 unique sources.

The source-of-truth byte hashes, exact IDs and inclusion counts are in `data/official_lock.json` and `data/official_extension/lock.json`. The curated inputs and logs contain extracts from MedCalc-Bench Verified v1.0.8 under CC BY-SA 4.0. See `SOURCE_NOTES.md` for authors, upstream URLs and ownership. Changes consist of selecting and deduplicating official records, creating input-only and scoring-only views, recording model calls and attaching derived runtime decisions.

## Locked inference and outcomes

The common Qwen2.5-1.5B or SmolLM2-1.7B planner and extractor use the original prompts, greedy decoding, seed 731, the 48 and 768 generation caps, and 8,192 tokens of context per slot. The CPU server used three concurrent slots on the initial cohort and four slots for the Qwen extension. The four-slot SmolLM2 extension server disconnected after four completed cases. That run resumed with two slots, preserving all completed cases and requests. Eleven requests had been journaled at the interruption. Unreturned in-flight requests may have been reissued. See `results/official_extension/smollm2_1.7b_q4km/infrastructure_resume.json`. Threads, release, archived binary and model checksums, prompt/response payloads and startup metadata are retained. Each case receives one planner request. A known selected tool triggers one extractor request. A malformed or truncated model output is counted as a failed attempt. Recoverable disconnected runs can resume from the request journal. A case enters the output table only after its full pipeline completes. Both baseline and repair consume the same parsed model call.

Primary outcomes are benchmark-matching answers returned, nonmatching answers returned, and cases without a returned answer. A match requires the correct selected calculator and numerical output inside the original official answer interval. The unit/domain policy is the primary paired comparison. Matching and nonmatching outputs are scored across all cases and among returned answers. `summary.json` also reports exploratory Wilson intervals and paired case-level changes. Timings across concurrent throughput runs are descriptive. The source-repair policy checks text-supported numerical input consistency. Patient identity, variable interpretation and clinical timing are independent issues.

## Commands

Python 3.12 or later and the Python standard library suffice for retrospective verification. Complete frozen inputs and logs are included for that workflow. Running new inference also requires the pinned CPU runtime and model weights fetched by `fetch_open_models.py`. Published shots and training/test datasets are needed only to reproduce original cohort selection through `fetch_data.py`. To reproduce selection from an existing source folder, pass `--raw` to `prepare`.

```bash
python3 official_study.py score
python3 audit_official_study.py
python3 official_extension.py score
python3 official_extension.py audit
```

To reproduce dataset selection, run `python3 official_study.py prepare` followed by `python3 official_extension.py prepare`. For a distinct inference replicate, unpack a new copy in a different directory and move its existing `results/official` and `results/official_extension` elsewhere. After acquiring the pinned models, use `python3 official_study.py infer --slots 3 --threads 8` and `python3 official_extension.py infer --model qwen2.5_1.5b_q4km --slots 4 --threads 8`, then `python3 official_extension.py infer --model smollm2_1.7b_q4km --slots 2 --threads 8`. If the weight cache is in a different directory, supply `--cache`. Stored request signatures protect resumed cases. Numeric outcomes may vary across CPUs and inference backends even with matching generation settings. Output-specific reruns of failed or incorrect cases are outside the study protocol.

A secondary argument audit (`score_official_inputs.py --cohort initial|extension --raw PATH`) compares each released call's canonical inputs with mapped official Relevant Entities. It records unparseable references and calls whose output falls within tolerance despite an argument discrepancy. This post-lock diagnostic is distinct from the numerical primary endpoint. Check `argument_audit.json` beside the corresponding model summary.
