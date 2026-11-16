# Independent command-line review

The review exercised the frozen v0.4 research_calculator.py entry point directly, using eight deliberately constructed examples. All materials for this review are synthetic. The reviewer inspected implementation before constructing the challenge, and did not inspect the official test inputs or results. These diagnostic examples establish individual failure modes. Their frequency in patient records remains unknown.

| Source text or requested computation | Expected behavior | Observed behavior |
|---|---|---|
| A single patient height and weight | Compute BMI | Returned 27.78 |
| Equivalent measurements with different units | Compute the same BMI | Returned 27.78 |
| Weight absent | Abstain | Abstained |
| Two conflicting weights, no requested time | Abstain | Abstained |
| Only the father's weight was recorded | Abstain | Used the father's weight and returned 27.78 |
| Only a target weight was recorded | Abstain | Used the target as the observed weight and returned 27.78 |
| Admission BMI requested, only discharge values available | Abstain | Used discharge values and returned 27.78 |
| BMI percentile requested, only raw BMI is implemented | Abstain | Returned raw BMI 27.78 |

All eight requests produced byte-identical replies when invoked a second time. Every released measurement had an exact source substring, and every released result carried the digest of its input note. The erroneous releases satisfied those checks. Matching a substring establishes textual presence. The missing facts in these cases are who supplied the measurement, whether it was observed, when it was observed, and which output statistic the question requested.

The default CLI with no proposed call took the named-measurements fallback. These findings apply to that route. The optional section-based temporal experiment and SQLite publication experiment evaluate separate entry points and do not change the outcomes above.

The frozen study policies remain inspectable. A future revision could require structured patient/encounter and measured-status evidence, and explicitly bind requested time and output type before allowing a fallback calculation. The four named cases are suitable acceptance tests for that revision. The ambiguous weights case also demonstrates why resolving only a single surviving quantity is insufficient.

Run `python3 results/code_review/replay.py` from the project directory to print the per-case outcomes. Add `--require-all` to require all expected behaviors, including abstentions. The stricter option currently exits with status 1 for the four observed failures. Neither command uses network access or any benchmark labels.

## Secondary contextual guard

The separately frozen checked_calculator.py command adds a conservative check of the text near each selected evidence span. It recognizes explicit kinship, target or hypothetical measurements, and incompatible measurement times. It also rejects explicit requests for ranks, percentiles and changes that the registry does not calculate. The underlying calculation receives the same question, note and optional proposal. The final check runs on every numerical release from either calculation route.

The revised implementation met the expected behavior for all eight original smoke examples, including withholding all four previously released unsupported numbers. These eight examples informed the revision. They are development checks.

Four additional stress cases were run after the secondary freeze. The two controls returned the expected number. The other two still released unsupported values when an earlier sentence established that all following measurements belonged to the brother or to the discharge encounter. The local cue check loses context across sentence boundaries. These outcomes are retained in extended_observations.json. The optional structured temporal guard covers explicit sections under a different policy, and the generic CLI does not supply authenticated encounter/subject provenance.

The two versions share no added model calls. Code hashes, time of freeze and evaluation status are in secondary_freeze.json. Use `--entry checked_calculator.py` to verify the secondary policy and `--cases results/code_review/extended_cases.json` to replay the remaining limitations.
