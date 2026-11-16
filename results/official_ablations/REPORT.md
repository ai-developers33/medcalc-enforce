# Official test action ablations and paired release comparisons

Each model received the same 124 official cases. The first locked cohort contributed 44 cases and the extension added the remaining 80 eligible source groups. Pooling the two disjoint cohorts within each model weights every case equally. Counts across both models represent 248 model–case attempts from 124 sources. No interval or significance test treats the 248 attempts as independent. All denominators include unanswered cases.

The source verifier accepts canonical source matches. Unit and named-value ablations permit the indicated forms of repair and abstain when another frozen action was required. These are action restrictions. No alternative candidate search is performed after a disabled decision. The combined candidate also permits deterministic resolution from uniquely named measurements. The reviewed policy adds textual scope constraints and is a secondary comparison. All action ablations, quotas and paired tests in this report are exploratory.

## qwen2.5_1.5b_q4km

### First (44 cases)

| Policy | Match | Nonmatching released | Unanswered | Coverage |
|---|---:|---:|---:|---:|
| unit_domain | 33 | 7 | 4 | 90.9% |
| literal_quote | 8 | 1 | 35 | 20.5% |
| source_verify_only | 29 | 1 | 14 | 68.2% |
| source_verify_and_unit | 33 | 1 | 10 | 77.3% |
| source_verify_and_named_value | 31 | 3 | 10 | 77.3% |
| source_repair | 35 | 3 | 6 | 86.4% |
| note_only | 28 | 2 | 14 | 68.2% |
| combined | 36 | 3 | 5 | 88.6% |
| reviewed | 36 | 2 | 6 | 86.4% |

| Candidate vs unit/domain baseline | Gain / loss in matches | Paired change, points (exploratory 95% interval) | Shared answered cases, baseline / candidate matches |
|---|---:|---:|---:|
| source_repair | 6 / 4 | +4.5 (-6.8 to +15.9) | 37 cases, 31 / 34 matches |
| note_only | 7 / 12 | -11.4 (-27.3 to +4.5) | 28 cases, 23 / 26 matches |
| combined | 7 / 4 | +6.8 (-6.8 to +20.5) | 37 cases, 31 / 34 matches |
| reviewed | 7 / 4 | +6.8 (-6.8 to +20.5) | 36 cases, 30 / 34 matches |

| Compared at equal quotas | Released per method | Expected matches, uniform baseline | Expected matches, quote-ranked baseline | Expected matches, candidate |
|---|---:|---:|---:|---:|
| source_repair | 38 | 31.35 | 31.27 | 35.00 |
| note_only | 30 | 24.75 | 24.36 | 28.00 |
| combined | 39 | 32.17 | 32.14 | 36.00 |
| reviewed | 38 | 31.35 | 31.27 | 36.00 |

### Extension (80 cases)

| Policy | Match | Nonmatching released | Unanswered | Coverage |
|---|---:|---:|---:|---:|
| unit_domain | 65 | 9 | 6 | 92.5% |
| literal_quote | 25 | 1 | 54 | 32.5% |
| source_verify_only | 62 | 0 | 18 | 77.5% |
| source_verify_and_unit | 68 | 0 | 12 | 85.0% |
| source_verify_and_named_value | 64 | 0 | 16 | 80.0% |
| source_repair | 71 | 0 | 9 | 88.8% |
| note_only | 65 | 0 | 15 | 81.2% |
| combined | 73 | 0 | 7 | 91.2% |
| reviewed | 73 | 0 | 7 | 91.2% |

| Candidate vs unit/domain baseline | Gain / loss in matches | Paired change, points (exploratory 95% interval) | Shared answered cases, baseline / candidate matches |
|---|---:|---:|---:|
| source_repair | 9 / 3 | +7.5 (+0.0 to +13.8) | 70 cases, 62 / 70 matches |
| note_only | 10 / 10 | +0.0 (-10.0 to +10.0) | 62 cases, 55 / 62 matches |
| combined | 11 / 3 | +10.0 (+2.5 to +17.5) | 70 cases, 62 / 70 matches |
| reviewed | 11 / 3 | +10.0 (+2.5 to +17.5) | 70 cases, 62 / 70 matches |

| Compared at equal quotas | Released per method | Expected matches, uniform baseline | Expected matches, quote-ranked baseline | Expected matches, candidate |
|---|---:|---:|---:|---:|
| source_repair | 71 | 62.36 | 62.35 | 71.00 |
| note_only | 65 | 57.09 | 57.06 | 65.00 |
| combined | 73 | 64.12 | 64.12 | 73.00 |
| reviewed | 73 | 64.12 | 64.12 | 73.00 |

### Pooled (124 cases)

| Policy | Match | Nonmatching released | Unanswered | Coverage |
|---|---:|---:|---:|---:|
| unit_domain | 98 | 16 | 10 | 91.9% |
| literal_quote | 33 | 2 | 89 | 28.2% |
| source_verify_only | 91 | 1 | 32 | 74.2% |
| source_verify_and_unit | 101 | 1 | 22 | 82.3% |
| source_verify_and_named_value | 95 | 3 | 26 | 79.0% |
| source_repair | 106 | 3 | 15 | 87.9% |
| note_only | 93 | 2 | 29 | 76.6% |
| combined | 109 | 3 | 12 | 90.3% |
| reviewed | 109 | 2 | 13 | 89.5% |

| Candidate vs unit/domain baseline | Gain / loss in matches | Paired change, points (exploratory 95% interval) | Shared answered cases, baseline / candidate matches |
|---|---:|---:|---:|
| source_repair | 15 / 7 | +6.5 (+0.0 to +12.1) | 107 cases, 93 / 104 matches |
| note_only | 17 / 22 | -4.0 (-12.1 to +4.0) | 90 cases, 78 / 88 matches |
| combined | 18 / 7 | +8.9 (+1.6 to +15.3) | 107 cases, 93 / 104 matches |
| reviewed | 18 / 7 | +8.9 (+1.6 to +15.3) | 106 cases, 92 / 104 matches |

| Compared at equal quotas | Released per method | Expected matches, uniform baseline | Expected matches, quote-ranked baseline | Expected matches, candidate |
|---|---:|---:|---:|---:|
| source_repair | 109 | 93.70 | 93.62 | 106.00 |
| note_only | 95 | 81.67 | 81.38 | 93.00 |
| combined | 112 | 96.28 | 96.25 | 109.00 |
| reviewed | 111 | 95.42 | 95.38 | 109.00 |

## smollm2_1.7b_q4km

### First (44 cases)

| Policy | Match | Nonmatching released | Unanswered | Coverage |
|---|---:|---:|---:|---:|
| unit_domain | 22 | 20 | 2 | 95.5% |
| literal_quote | 7 | 2 | 35 | 20.5% |
| source_verify_only | 18 | 0 | 26 | 40.9% |
| source_verify_and_unit | 21 | 0 | 23 | 47.7% |
| source_verify_and_named_value | 21 | 2 | 21 | 52.3% |
| source_repair | 24 | 3 | 17 | 61.4% |
| note_only | 28 | 2 | 14 | 68.2% |
| combined | 34 | 2 | 8 | 81.8% |
| reviewed | 34 | 1 | 9 | 79.5% |

| Candidate vs unit/domain baseline | Gain / loss in matches | Paired change, points (exploratory 95% interval) | Shared answered cases, baseline / candidate matches |
|---|---:|---:|---:|
| source_repair | 6 / 4 | +4.5 (-9.1 to +18.2) | 26 cases, 19 / 23 matches |
| note_only | 15 / 9 | +13.6 (-2.3 to +29.5) | 29 cases, 14 / 27 matches |
| combined | 16 / 4 | +27.3 (+11.4 to +43.2) | 35 cases, 19 / 33 matches |
| reviewed | 16 / 4 | +27.3 (+11.4 to +43.2) | 34 cases, 18 / 33 matches |

| Compared at equal quotas | Released per method | Expected matches, uniform baseline | Expected matches, quote-ranked baseline | Expected matches, candidate |
|---|---:|---:|---:|---:|
| source_repair | 27 | 14.14 | 14.50 | 24.00 |
| note_only | 30 | 15.71 | 16.00 | 28.00 |
| combined | 36 | 18.86 | 19.00 | 34.00 |
| reviewed | 35 | 18.33 | 18.50 | 34.00 |

### Extension (80 cases)

| Policy | Match | Nonmatching released | Unanswered | Coverage |
|---|---:|---:|---:|---:|
| unit_domain | 41 | 34 | 5 | 93.8% |
| literal_quote | 7 | 2 | 71 | 11.2% |
| source_verify_only | 37 | 2 | 41 | 48.8% |
| source_verify_and_unit | 44 | 2 | 34 | 57.5% |
| source_verify_and_named_value | 44 | 2 | 34 | 57.5% |
| source_repair | 52 | 2 | 26 | 67.5% |
| note_only | 65 | 0 | 15 | 81.2% |
| combined | 72 | 1 | 7 | 91.2% |
| reviewed | 72 | 1 | 7 | 91.2% |

| Candidate vs unit/domain baseline | Gain / loss in matches | Paired change, points (exploratory 95% interval) | Shared answered cases, baseline / candidate matches |
|---|---:|---:|---:|
| source_repair | 14 / 3 | +13.8 (+5.0 to +22.5) | 51 cases, 38 / 49 matches |
| note_only | 32 / 8 | +30.0 (+20.0 to +40.0) | 62 cases, 33 / 62 matches |
| combined | 34 / 3 | +38.8 (+30.0 to +47.5) | 69 cases, 38 / 68 matches |
| reviewed | 34 / 3 | +38.8 (+30.0 to +47.5) | 69 cases, 38 / 68 matches |

| Compared at equal quotas | Released per method | Expected matches, uniform baseline | Expected matches, quote-ranked baseline | Expected matches, candidate |
|---|---:|---:|---:|---:|
| source_repair | 54 | 29.52 | 29.95 | 52.00 |
| note_only | 65 | 35.53 | 35.74 | 65.00 |
| combined | 73 | 39.91 | 39.95 | 72.00 |
| reviewed | 73 | 39.91 | 39.95 | 72.00 |

### Pooled (124 cases)

| Policy | Match | Nonmatching released | Unanswered | Coverage |
|---|---:|---:|---:|---:|
| unit_domain | 63 | 54 | 7 | 94.4% |
| literal_quote | 14 | 4 | 106 | 14.5% |
| source_verify_only | 55 | 2 | 67 | 46.0% |
| source_verify_and_unit | 65 | 2 | 57 | 54.0% |
| source_verify_and_named_value | 65 | 4 | 55 | 55.6% |
| source_repair | 76 | 5 | 43 | 65.3% |
| note_only | 93 | 2 | 29 | 76.6% |
| combined | 106 | 3 | 15 | 87.9% |
| reviewed | 106 | 2 | 16 | 87.1% |

| Candidate vs unit/domain baseline | Gain / loss in matches | Paired change, points (exploratory 95% interval) | Shared answered cases, baseline / candidate matches |
|---|---:|---:|---:|
| source_repair | 20 / 7 | +10.5 (+3.2 to +17.7) | 77 cases, 57 / 72 matches |
| note_only | 47 / 17 | +24.2 (+15.3 to +33.1) | 91 cases, 47 / 89 matches |
| combined | 50 / 7 | +34.7 (+26.6 to +42.7) | 104 cases, 57 / 101 matches |
| reviewed | 50 / 7 | +34.7 (+26.6 to +42.7) | 103 cases, 56 / 101 matches |

| Compared at equal quotas | Released per method | Expected matches, uniform baseline | Expected matches, quote-ranked baseline | Expected matches, candidate |
|---|---:|---:|---:|---:|
| source_repair | 81 | 43.62 | 44.35 | 76.00 |
| note_only | 95 | 51.15 | 51.60 | 93.00 |
| combined | 109 | 58.69 | 58.86 | 106.00 |
| reviewed | 108 | 58.15 | 58.34 | 106.00 |

## Interpretation

Each equal-coverage comparison uses the smaller of the paired release counts. Uniform thinning integrates random selection exactly. Quote ranking sorts the baseline answers by the fraction of proposed fields with exact supporting quotes and integrates ties exactly at the cutoff. The quota uses the two observed coverage counts and is retrospective. Fractional values are conditional expectations. Missing results and abstentions remain in the denominator for paired whole-cohort comparisons. JSON also reports direct shared-case comparisons, per-selected-calculator quotas, hypergeometric selection intervals, and exploratory calculator-stratified case-bootstrap intervals. Alternative confidence rankers and prospectively calibrated thresholds may yield different results.

Recompute from the four completed model traces with `python3 analyze_official_ablations.py`. The input/output digests identify each locked cohort and each source trace. The self-check uses an earlier complete 50-case cohort with known reference counts.
