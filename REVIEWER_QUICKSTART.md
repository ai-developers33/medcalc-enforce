# Reviewing MedCalc-Enforce v0.6.0

The release contains 124 official cases and 48 distractor cases evaluated with five models, for 620 official and 240 distractor workflows. The 64-case out-of-vocabulary transfer suite is a separate evaluation. The published software and data are archived at [Zenodo](https://doi.org/10.5281/zenodo.24293301).

## Run all checks locally

Use Python 3.12 and a CPU. From a terminal, clone the repository and run the reviewer script. The checkout contains all inputs for an offline run.

```sh
git clone https://github.com/ai-developers33/medcalc-enforce.git
cd medcalc-enforce
python3 reproduce_all.py
```

To test the published ZIP itself, run `python3 reproduce_all.py --download-release-zip`. This downloads the [v0.6.0 release ZIP](https://github.com/ai-developers33/medcalc-enforce/releases/download/v0.6.0/MedCalc_Enforce_Experiments_v0_6.3.zip) and checks its SHA-256 before extraction. Both commands run in a temporary directory and finish with `All four MedCalc-Enforce v0.6.0 reproduction checks passed.` on success.

| Check | Expected result |
|---|---|
| Release verification | 294 file checksums pass. The test runner reports `Ran 75 tests` and `OK`. The archived verifier's closing line still says 70. |
| Experiment 8 | All five model summaries and the published 240-workflow table match the replay from the saved calls. |
| Reviewer analyses | The regenerated 64-case transfer dataset and the reviewer-results JSON both match the release byte-for-byte. |
| Experiments 1–7 | Experiments 1–6 match the published results, including the 620 official workflows and 324 SQLite WAL trials. The scalability benchmark runs the published workloads and records new timings. |

## Run the notebook in Colab

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ai-developers33/medcalc-enforce/blob/main/MedCalc_Enforce_v0_6_Colab_Live_Reproduction.ipynb)

1. Click **Open in Colab**, then **Runtime → Run all**. Cell 2 downloads the GitHub release ZIP and verifies its SHA-256 and 294 file checksums. The default run scores the 620 official and 240 distractor workflows from the archived traces on a CPU.
2. To run fresh inference, select **Runtime → Change runtime type → T4 GPU**, set **`FORCE_FRESH_GPU_INFERENCE = True`** in cell 2, and choose **Runtime → Run all**. With the checkpoint field empty, the notebook runs all 48 distractor cases on each of the five models using the recorded `llama.cpp` build `b12428`. It reuses the 620 archived official workflows. Fresh model outputs and timings can vary.
3. Cell 4 scores all 860 workflows, shows the Experiment 8 table and verifies the regenerated ZIP. The saved Tesla T4 output streams document the original run from the 248-file baseline through its 290-file intermediate package. The published v0.6.0 release includes the later reviewer analyses.

## Regenerate the official-cohort and reviewer analyses

To keep the generated reports for inspection, use a separate directory. The following commands extract the tagged inputs and omit the four output files that the scripts will create.

```sh
run_dir=$(mktemp -d)
git archive v0.6.0 | tar --exclude='results/v0_5_bdcc' --exclude='data/oov_discourse_transfer_64.jsonl' -xf - -C "$run_dir"
(
  cd "$run_dir" &&
  python3 -B run_bdcc_v05_suite.py &&
  python3 -B run_reviewer_fixes_v06.py
)
```

| Command | Where to look in the run directory |
|---|---|
| `run_bdcc_v05_suite.py` | `results/v0_5_bdcc/summary.json` and `BDCC_STRENGTHENED_RESULTS.md` in the same directory. These cover Experiments 1–7, including the 620 official workflows. Latency and throughput depend on the machine. |
| `run_reviewer_fixes_v06.py` | `data/oov_discourse_transfer_64.jsonl` and `results/v0_5_bdcc/reviewer_fixes_v06.json`. Compare their SHA-256 digests with the corresponding entries in the release's `SHA256SUMS.txt`. |

For the Experiment 8 table by itself, run `python3 replay_experiment8.py --check` from the clone. It checks the rounded probabilities and all other summary fields against the published JSON and Markdown.
