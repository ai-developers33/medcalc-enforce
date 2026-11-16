# Text overlap in the two locked official cohorts

We tested all 44 first-cohort cases and all 80 extension cases against 10,538 training rows and 55 one-shot rows in the same pinned Verified benchmark release. Its three CSV digests and both official input hashes matched the study locks. The audit uses only the source identifier, note, question, calculator identity and dataset metadata. It reads no model results, answer limits or numerical reference answers. No flags change membership or the primary evaluation.

| Flag found in train or one-shot | First (44) | Extension (80) | Combined (124) |
|---|---:|---:|---:|
| Matching source key | 0 | 0 | 0 |
| Matching normalized complete note | 0 | 0 | 0 |
| Matching complete note with numbers masked | 5 | 15 | 20 |
| Matching normalized question | 44 | 80 | 124 |
| Number-masked note Jaccard ≥ 0.70 on five-token shingles | 5 | 15 | 20 |

All 20 masked note matches belong to the QTc/Bazett calculator and to the benchmark’s Template note type. All 20 collapse to one masked complete note and match training rows. None match a complete masked one-shot note. The other 104 cases have the Extracted note type. Across the 124 cases the masked question text has nine distinct patterns. All 124 question texts match training and one-shot questions even before number masking. Reuse of benchmark task questions limits conclusions about new question phrasing or independent tool selection. It does not establish that a model saw a case during pretraining.

A subgroup evaluation of the 104 Extracted cases would exclude the calculator represented by all 20 Template cases. Performance differences between those subgroups cannot isolate a template effect from a calculator effect. Pooling the cohorts would also mix the prespecified capped first sample and its later extension. The primary cohort and extension keep their original identities in all audit outputs.

**Method.** Exact note and question comparisons use lowercasing and whitespace collapse, as in the original source split. Complete masked matches additionally replace signed digit strings, decimal components, grouped digits and scientific notation with the same token, including any digits in printed units. This conservative screen can match records that used different measurements or units. For an extra near-duplication screen, tokenize the masked text into words and mask tokens, discard punctuation, form sets of distinct contiguous five-token shingles, and compute exact set Jaccard against every reference note. The union threshold flags at 0.70, 0.80 and 0.90 identify the same 20 cases. No case has an empty shingle set. These thresholds are descriptive and cannot detect all paraphrases, indirect reuse, undisclosed source identity, or pretraining contamination. Source keys follow the original split and use article IDs where available and scoped note identifiers elsewhere.

`case_flags.jsonl` records each case ID, group key, calculator, note type, SHA-256 hashes for the complete and masked notes, flags, matching reference row counts and example row numbers in each split, and the best near neighbor with its intersection size. Matching row examples use CSV ordering. Nearest similarities break ties by the reference row number. `summary.json` includes counts by cohort, calculator, note type, their intersection, and reference split. The original pinned corpora and reference row identifiers allow source inspection without including another copy of the raw texts.

To reproduce from the package root, run `python3 audit_template_overlap.py --raw data/raw` after fetching the sources with `python3 fetch_data.py`.
