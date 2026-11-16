# Computational reference audit

The locked official sample contains 44 cases from nine calculators. For each case, the audit takes the annotated quantities and calculates the expected result two ways. The first uses the frozen registry. The second uses 42-digit Decimal arithmetic, explicitly enumerated conversion factors for the encountered units, and independently implemented equations. Both implementations use the same documented mathematical specifications and benchmark field-name mapping. The checker verifies that the reference answer lies within its published interval and compares both reconstructions to that answer. It loads the selected source notes, references, and upstream entity/explanation excerpt. It has no dependency on model traces or predictions.

All 44 reconstructions from each implementation fell within the official scoring interval, and all 44 Decimal reconstructions fell within 0.1% of the published answer. The largest relative discrepancy was 0.00180%. The Decimal and registry calculations agreed on all 44 cases at a relative tolerance of 1e-11. The raw results retain all floating-point and decimal values.

Two targeted annotation checks illustrate the difference between arithmetic correctness and textual support.

* All four osmolality explanations use the BUN value again in the displayed glucose numerator. For example, in official-434 the displayed substitution uses 29 divided by 18. The glucose annotation is 86. Substituting 86 gives the published numerical answer of 293.13492 after rounding. The other three affected IDs are official-426, official-427 and official-440. Their numerical gold answers also match the annotated glucose calculation. Using the rationale as a supervised label or evaluation oracle would propagate a misleading expression.
* Four of five mean arterial pressure cases print mmHg with the annotated pressure pair. In official-63 the note reports a labeled blood pressure of 150/92 with no printed unit after it. The annotation assigns mmHg. A validator requiring the source to print the unit can legitimately abstain even though the annotation permits an answer.

These checks cover the displayed osmolality substitution and the explicit BP unit. Other note-level mismatches, incorrect variables, wrong timepoints, and conflicting patient identities require separate adjudication. No clinician reviewed these labels as part of this audit. Reference answers, scoring intervals, dates, and evaluated tool behavior retain their original definitions.

To reproduce the run using the bundled gold excerpt:

```bash
python3 results/reference_audit/audit.py
```

To rebuild the entity/explanation excerpt from the official CSV, supply the download path:

```bash
python3 results/reference_audit/audit.py --official-csv data/raw/test_data.csv
```

The program checks the official CSV digest against the frozen selection manifest before rebuilding the excerpt. The excerpt is an attributed selection from MedCalc-Bench Verified v1.0.8, commit 801592132bfd833f049b517a4e013e00a5fc40fa. The upstream CC-BY-SA 4.0 terms and attribution in SOURCE_NOTES.md apply to these selected records.

## All 124 official cases

The extension adds 80 cases from the remaining locked official sources. The independent Decimal converter covers 303 fields across the combined 124 cases. All reconstructed answers are within 0.1% of the numerical reference. The frozen registry independently reconstructs 123 of 124 rows from the literal unit strings in the annotated entities. On official-283 it rejects the benchmark notation `mm^3` in platelet counts. The upstream explanation specifies count/mm³. A cubic millimeter is a microliter, so the independent converter maps 342000 count/mm³ to 342 in 10^9/L. This is an input-unit alias limitation of the frozen registry. The reference quantities for this case remain available in the field audit. Benchmark labels and case selection were preserved.

Across both cohorts, 15 of 16 pressure pairs had an explicit mmHg unit immediately after the pair. The four osmolality explanation discrepancies all come from the initial cohort. Both targeted checks retain their stated scope.

`canonical_reference_all.jsonl` contains one keyed case for each model-independent evaluation, including original annotated quantities, reference field names/units, numeric or categorical canonical values, and per-case flags. All 124 have scorable reference fields. This file is evaluation-only. `combined_summary.json` reports separate cohort and combined denominators. The 80-row upstream excerpt is in `extension_reference_material.jsonl`; the source attribution and license above also cover it.

```bash
python3 results/reference_audit/audit_combined.py
```

Pass `--official-csv data/raw/test_data.csv` to rebuild both excerpts using the verified upstream file. The main audit and the original 44-case replay are runnable separately.
