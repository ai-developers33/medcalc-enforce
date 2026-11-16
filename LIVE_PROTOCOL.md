# Open-weight development pilot, protocol v0.2

This protocol was fixed before model inference. It is a feasibility pilot, not a
confirmatory experiment or evidence of prevention of clinical harm.

- 50 development questions: the first five rows per calculator in the existing
  seeded 200-row development selection, covering 10 calculators and 50 source
  groups. The selected training notes exclude previously detected exact-text and
  explicit case-ID overlap with the official test set. No selection by results.
- Models: publisher-provided Qwen2.5-1.5B-Instruct Q4_K_M and
  SmolLM2-1.7B-Instruct Q4_K_M. Both Apache-2.0; immutable revisions and SHA256
  digests are in `data/open_models_manifest.json`. CPU only, one model at a time.
- Each workflow uses two isolated roles with the same model weights. A planner
  sees the question and tool catalog; an extractor sees the question, selected
  tool schema, and complete note. Questions generally name the calculator, so
  selection is an easy routing task, not autonomous diagnostic reasoning.
- Generation is greedy, seed 731, JSON-object grammar, 48-token planner cap and
  768-token extractor cap, 8192-token context, no context shifting. Truncated
  output is a failure. The server rejects oversized prompts. Notes are not cut.
- Native source units are requested. No gold entities, reference answer, answer
  interval, or ground-truth explanation enters prompts or validation. The live
  runner reads only the allowlisted `live_inputs.jsonl` input view. Evaluation is
  a separate script and cannot feed corrected values back to the model.
- No repair, retry-on-bad-output, prompt tuning, or fine-tuning in this pilot.
  Model calls failing transport or syntax are retained. Resume skips all recorded
  cases, including failures; failures are not silently rerun.
- Three gates are replayed on the SAME generated calls: L1 schema alone, L2
  schema plus declared units/domain/applicability, L3 L2 plus exact literal span
  and value-in-span checks. These are three evaluations, not three independent
  LLM workflow runs. L1 intentionally demonstrates a unit-unaware executor;
  L2 is the stronger, more realistic comparator.
- L3 is a limited text-support check, not the earlier B3/B4 trusted-ledger gate.
  It cannot establish variable-value attachment, source-unit attachment,
  correct time selection, patient identity, or clinical applicability beyond
  registered rules. It can reject correct values with unsupported quote formats.
- No EHR updates are simulated during these natural-error runs. Therefore no
  claim about commit-time revalidation is made from this pilot. The controlled
  fault-injection study remains separate in `results/PILOT_RESULTS.md`.

## Outcomes (all actual counts, no target results)

Selection accuracy; complete/schema-valid call rate; numeric agreement within
the benchmark supplied interval (usually +/-5%) and a stricter 0.1% relative
tolerance; correct released results / all cases; incorrect released results /
all cases; blocked or failed / all cases; correctness conditional on release;
literal-span gate rejection of otherwise benchmark-correct outputs; prompt and
completion tokens; total inference wall time; descriptive gate latency.

Correctness requires the correct selected calculator AND a numeric answer in
the reference interval. Lack of numerical agreement is not a clinical-harm
label. Zero released errors is not useful by itself if every call is blocked.
The scorer reports both coverage and correctness. Each model is evaluated on
the same source groups. This small development sample is not a held-out result.

## Reproducibility and next-stage requirements

Raw requests, raw responses, finish reasons, usage, server logs, model/runtime
digests, derived calls, and each gate's result are retained. All failures remain.
Do not pool these results with injected-fault trials. Public benchmark exposure
in model pretraining cannot be excluded. Larger recent models, independent EHR
evidence, bounded repair, matched competing methods, concurrency/freshness tests,
and a frozen, group-disjoint held-out evaluation remain necessary for the paper.

## Development amendment: tool-schema-constrained decoding

After the first Qwen JSON-object runs showed repeated literal `field` placeholder
keys, a second decoding variant was added for BOTH models on the same 50 cases.
This amendment was made after observing development-format failures; it is not
a preregistered confirmatory comparison. The original failures are preserved.
Prompts, seed, token caps, cases, scoring and gates are unchanged. Only extractor
decoding receives the selected tool's full JSON schema: required field names,
numeric values, sex enum, strings for units/quotes, and explicit null entries
for unavailable inputs. No reference values or reference answers are in that
schema. This models a stronger structured-output baseline. Schema validity does
not establish that an extracted value, unit, or timepoint is medically correct.
Run it with `python run_live_models.py --mode schema`. Results use `_schema`
suffixes; both variants and all failures are reported, without pooling them.

## Infrastructure amendment: cap the runtime cache

The original JSON-object SmolLM run lost its server at case 43 after substantial
latency increases; all eight affected transport-failure cases remain in that
run. The runtime's default saved prompt-cache allowance was 8192 MiB on a host
with roughly 10 GB total RAM. Memory pressure is a plausible explanation, not
a confirmed kernel diagnosis. The subsequent schema run was paused to cap this
cache at 256 MiB, preserving all completed schema cases and their raw outputs.
The remaining schema cases resumed with unchanged model weights/prompts/decoding.
The exact retained case IDs and initial configuration are in `results/live/diagnostics`.
An in-flight request at interruption may be unrecorded and is outside scored
workflow/request counts. No output was discarded because of its accuracy.
Reported timings are descriptive shared-host measurements, not a controlled
speed comparison between models or variants. New reproductions use the 256 MiB
cap throughout; original logs retain the first-run failures.
