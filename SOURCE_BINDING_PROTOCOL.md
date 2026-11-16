# Source-bound observation selection: v0.3 development and validation protocol

**Historical development alternative:** this ID-selection design achieved 23/50 on development and was not advanced to validation. The selected implementation and actual validation follow `SOURCE_REPAIR_PROTOCOL.md`; all negative development results are retained.

The old model generated values, units, and quotes independently. L3 then required
exact copied quotes but did not bind a number to its printed unit. The new
workflow parses explicit source quantities with offsets and note hashes, asks
the model to select observation IDs, and constructs values/units from those
IDs. The source packet is regenerated and compared at execution. Changing a
value/unit or the underlying note invalidates it. No reference answer or
benchmark entity is used for candidate generation, model prompts, or execution.

The parser was developed on the original 50 notes. It handles explicit units,
unit word aliases, count scales, blood-pressure pairs, shared units in lists,
and a lab value immediately followed by a reference interval with a printed unit.
These parsing conventions are explicit code, not independent clinical adjudication.

## Fixed comparisons

Use the same publisher Qwen2.5-1.5B Q4_K_M weights and pinned CPU runtime.
Temperature 0, seed 731, 8192-token context, 256 MiB saved prompt-cache limit.
The original planner prompt and its 48-token cap remain unchanged. Old extraction
uses the original prompt, schema, and 768-token cap. Observation-ID selection
uses a dynamically constrained schema with a NONE abstention option and a
256-token cap. There is no retry, best-of sampling, gold repair, or silent fallback.

- Development: 50 previously evaluated cases. Reuse their recorded planner and
  baseline traces, and make 50 new observation-selection calls. This is tuning
  evidence, not held-out performance.
- Validation: 50 previously unrun inference cases, five per calculator, selected
  deterministically from the remaining original training-derived 200-row pool.
  Exclude overlap with development by source article/case group and normalized
  note text; do not select on model performance or parser coverage. These cases
  were included in the earlier arithmetic audit, so this is a new inference
  validation split, not an untouched official benchmark test.
- Freeze code/prompt and case hashes before running validation. Run the original
  baseline and new workflow on every same validation case with a shared live
  planner decision. Alternate execution order. Report L2 unit-aware baseline,
  L3 old quote gate and the new complete source-bound workflow side by side.
- Measure correct-tool plus benchmark numerical agreement, nonmatching answers
  released, abstentions/failures, literal/source consistency, and actual calls.
  Never optimize safety by suppressing every output. Preserve every result.
- Keep primary references and tolerances unchanged, including known disputed
  annotations. Record source-supported reference discrepancies separately.

## Scope of the guarantee

Source binding verifies the observed number/unit pair and note version. It does
NOT establish correct variable assignment, selection of the right patient or
timepoint within a narrative, or correctness of the source itself. A wrong lab
or later measurement selected by the model can still pass. The patient-note
benchmark does not provide trusted EHR observation codes or transaction state.
Actual EHR integration, independent clinical review and concurrency evaluation
remain outside this experiment. Do not infer prevention of clinical harm.

All requests, outputs, source packets, selected IDs, arithmetic, and failure
reasons are retained. Request journaling permits resumption without repeating a
completed inference. The inference process does not load reference labels.
