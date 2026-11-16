# Paired action ablations and equal-coverage comparisons

Offline replay reuses the archived schema-constrained tool calls. Qwen validation uses 50 cases from separate articles within the training-derived study pool. Both models' development results use the same original 50 cases that informed development. SmolLM2 is a second set of model-generated calls on those cases. There are 100 distinct case IDs across all three cohorts. No new model inference or clinical outcome assessment took place in this analysis.

The four source policies use the frozen source parser and original formula code. The verification-only alternative accepts proposals already matching canonical source quantities. The unit alternative additionally accepts a native-number match needing unit repair. The named-value alternative instead permits replacement by a unique explicitly named source quantity. A disabled required action makes the case abstain. These variants isolate which frozen decisions depend on each action. They do not search for new lower-priority evidence after disabling a decision.

Numerical matches require the correct calculator and its benchmark result interval. All cases contribute to the agreement denominator. Development and validation counts are reported separately.

## Qwen Development

| Method | Matches / cases | Nonmatching released | No answer | Coverage |
|---|---:|---:|---:|---:|
| unit_domain | 42/50 | 6 | 2 | 96% |
| literal_quote | 18/50 | 2 | 30 | 40% |
| source_verify_only | 42/50 | 1 | 7 | 86% |
| source_verify_and_unit | 46/50 | 1 | 3 | 94% |
| source_verify_and_named_value | 43/50 | 1 | 6 | 88% |
| source_repair | 48/50 | 1 | 1 | 98% |

Full repair gained 6 matches and lost 0 compared with unit/domain checks. The change was +12.0% of all cases (exploratory stratified bootstrap interval +6.0% to +20.0%, paired exact McNemar p = 0.03125).

| Matched-coverage policy | Released | Expected matches | Expected nonmatches | Random-selection 95% match-count interval |
|---|---:|---:|---:|---:|
| uniform_unit_domain | 48 | 42.00 | 6.00 | 42 to 42 |
| quote_ranked_unit_domain | 48 | 42.00 | 6.00 | 42 to 42 |
| uniform_source_repair | 48 | 47.02 | 0.98 | 47 to 47 |

Matching release quotas separately within each model-selected calculator gives a total quota of 48. Expected matches are 42.00 for uniform baseline selection, 42.00 for quote-ranked baseline selection and 47.00 for source repair.

Both policies answered the same 48 cases in their overlap. On those identical cases the unit/domain baseline matched 42 references and source repair matched 47. This conditional subset isolates differences in the returned values; it is not a coverage estimate.

## Qwen Validation

| Method | Matches / cases | Nonmatching released | No answer | Coverage |
|---|---:|---:|---:|---:|
| unit_domain | 37/50 | 11 | 2 | 96% |
| literal_quote | 11/50 | 2 | 37 | 26% |
| source_verify_only | 34/50 | 0 | 16 | 68% |
| source_verify_and_unit | 38/50 | 0 | 12 | 76% |
| source_verify_and_named_value | 35/50 | 0 | 15 | 70% |
| source_repair | 39/50 | 0 | 11 | 78% |

Full repair gained 5 matches and lost 3 compared with unit/domain checks. The change was +4.0% of all cases (exploratory stratified bootstrap interval -6.0% to +14.0%, paired exact McNemar p = 0.7266).

| Matched-coverage policy | Released | Expected matches | Expected nonmatches | Random-selection 95% match-count interval |
|---|---:|---:|---:|---:|
| uniform_unit_domain | 39 | 30.06 | 8.94 | 28 to 32 |
| quote_ranked_unit_domain | 39 | 29.17 | 9.83 | 28 to 31 |
| uniform_source_repair | 39 | 39.00 | 0.00 | 39 to 39 |

Matching release quotas separately within each model-selected calculator gives a total quota of 39. Expected matches are 31.80 for uniform baseline selection, 31.33 for quote-ranked baseline selection and 39.00 for source repair.

Both policies answered the same 39 cases in their overlap. On those identical cases the unit/domain baseline matched 34 references and source repair matched 39. This conditional subset isolates differences in the returned values; it is not a coverage estimate.

## SmolLM2 Development

| Method | Matches / cases | Nonmatching released | No answer | Coverage |
|---|---:|---:|---:|---:|
| unit_domain | 23/50 | 22 | 5 | 90% |
| literal_quote | 7/50 | 3 | 40 | 20% |
| source_verify_only | 22/50 | 4 | 24 | 52% |
| source_verify_and_unit | 26/50 | 4 | 20 | 60% |
| source_verify_and_named_value | 28/50 | 5 | 17 | 66% |
| source_repair | 32/50 | 5 | 13 | 74% |

Full repair gained 9 matches and lost 0 compared with unit/domain checks. The change was +18.0% of all cases (exploratory stratified bootstrap interval +10.0% to +26.0%, paired exact McNemar p = 0.003906).

| Matched-coverage policy | Released | Expected matches | Expected nonmatches | Random-selection 95% match-count interval |
|---|---:|---:|---:|---:|
| uniform_unit_domain | 37 | 18.91 | 18.09 | 16 to 21 |
| quote_ranked_unit_domain | 37 | 18.73 | 18.27 | 16 to 21 |
| uniform_source_repair | 37 | 32.00 | 5.00 | 32 to 32 |

Matching release quotas separately within each model-selected calculator gives a total quota of 37. Expected matches are 21.89 for uniform baseline selection, 22.00 for quote-ranked baseline selection and 32.00 for source repair.

Both policies answered the same 36 cases in their overlap. On those identical cases the unit/domain baseline matched 23 references and source repair matched 31. This conditional subset isolates differences in the returned values; it is not a coverage estimate.

## Interpretation

Matched coverage uses the smaller observed release count as a quota for both policies. Uniform selection gives the expected count when withholding answers at random. An evidence-based comparator ranks the baseline's eligible calls by the fraction of individual field quotes that pass the existing literal verifier. Rank and tie handling use only proposed fields and source text. Random tie-breaking is integrated exactly using the hypergeometric distribution. Fractional counts are expectations, not individual observed answers. A central interval can have identical endpoints even when rare alternative counts are possible.

These quotas are retrospective. A deployment would need a threshold calibrated on separate data. A model-confidence selector or a different evidence ranker could outperform either comparator. The hypergeometric intervals describe tie/random-selection variation conditional on the fixed cases. The paired bootstrap resamples cases inside each reference-calculator stratum. Neither interval establishes performance in a clinical population. The comparisons are exploratory and are unadjusted for multiple testing.

Run `python3 analyze_repair_ablations.py` from the project root. The JSON summary includes paired gains, losses, transitions, descriptive intervals and exact input hashes for every cohort. Case-level JSONL records the score, source actions and outcomes for each replay.
