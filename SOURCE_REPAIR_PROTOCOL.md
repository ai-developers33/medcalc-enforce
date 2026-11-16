# v0.3: frozen source-backed repair validation

The first ID-selection prototype (development_v1) made 50 new Qwen calls but
matched only 23/50 answers. All its negative results and code are retained.
It is not the selected implementation.

The selected repair_v2 retains the ORIGINAL planner and extractor. There are
no additional model calls or prompt changes. A deterministic adapter parses
source quantities, associates explicitly named variables and ordered lists,
and constructs source-bound execution arguments:

1. Prefer a canonical quantity that matches the proposal in the source.
2. Otherwise, repair the unit only when a unique source quantity has the same
   native number for that variable.
3. Otherwise, repair the value only when there is exactly one semantically
   distinct, explicitly named source quantity for that variable.
4. Abstain on ambiguity or absence of support. Reparse/check the source packet
   and note hash before execution; check formula version and arithmetic domain.

A source match is evidence of consistency, not a guarantee of the correct
clinical patient, variable or timepoint. A later measurement selected by the
model can still pass. Source-parser errors and faulty benchmark annotations
remain possible. No clinical harm prevention is measured.

Development uses the original 50 cases and saved model calls. Parsing and repair
were tuned there, so its improvement is NOT a held-out estimate. The code,
prompts and validation-case hashes are frozen BEFORE new validation inference.
Validation selects the next five eligible rows per calculator from the earlier
200-row training-derived pool, excluding original development text, case and
article overlap and duplicate validation sources. Selection does not inspect
parser coverage or output accuracy. These 50 rows were in the earlier arithmetic
audit; they are previously unrun inference cases, not the official test split.
No validation outcomes are used for further tuning in this version.

Every validation case gets one common live planner and extractor execution,
using the same Qwen2.5-1.5B Q4_K_M weights, original prompts, seed 731 and token
caps. Compare L2, L3 and repair_v2 on the identical generated call. Retain all
cases, failures, abstentions and original gold references. Report correct-tool
plus benchmark-tolerance agreement, nonmatching outputs, coverage, paired
changes and exploratory uncertainty. No gold reference enters execution.

There are no best-of samples, additional LLM repairs, or selective reruns.
Journal completed requests before scoring or case completion. A software fix
after the freeze requires a new version and a new validation split. Clinical
review, real EHR integration and concurrent state-update experiments remain
required before strong paper claims.
