# Reviewing MedCalc-Enforce v0.6.0

The release contains 124 official cases and 48 distractor cases evaluated with five models, for 620 official and 240 distractor workflows. The 64-case out-of-vocabulary transfer suite is a separate evaluation. The published software and data are archived at [Zenodo](https://doi.org/10.5281/zenodo.24293301).

## Verify the release and reproduce Experiment 8

Use Python 3.12. From a terminal with Git installed, run the following commands. After the clone, both Python commands work offline on a CPU with the standard library.

```sh
git clone https://github.com/ai-developers33/medcalc-enforce.git
cd medcalc-enforce
python3 -B verify_release.py
python3 -B replay_experiment8.py --check
```

1. The release verifier should print `Verified 294 checksums.` and the test runner should report `Ran 75 tests` followed by `OK`. The verifier's closing message still quotes the older count of 70.
2. The Experiment 8 replay joins each model's saved calls to the 48 locked distractor inputs by case ID. It reads the recorded unit/domain decisions, reruns the reviewed and discourse-aware policies, and prints the five-row table. The `--check` option compares every Experiment 8 summary field and the rendered table with the archived results. The published reporting precision rounds some adjusted probabilities to zero.
3. If you downloaded the v0.6.0 ZIP from GitHub or Zenodo, open the directory containing `verify_release.py`. To run the second command there, save this supplemental script beside the verifier. [Experiment 8 replay script](replay_experiment8.py)

## Regenerate the official-cohort and reviewer analyses

From the Git clone, use a separate directory for the generated reports. The following shell commands extract the tagged inputs and omit the four output files that the scripts will create.

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
| `run_bdcc_v05_suite.py` | `results/v0_5_bdcc/summary.json` and `BDCC_STRENGTHENED_RESULTS.md` in the same directory. These cover Experiments 1–7, including the 620 official workflows. Latency and throughput depend on the machine. Use the separate command above for Experiment 8. |
| `run_reviewer_fixes_v06.py` | `data/oov_discourse_transfer_64.jsonl` and `results/v0_5_bdcc/reviewer_fixes_v06.json`. Compare their SHA-256 digests with the corresponding entries in the release's `SHA256SUMS.txt`. |

## Repeat the historical GPU run in Colab

Open the notebook from the top. Its last code cell contains the five-model distractor scoring procedure. Google Drive controls viewing access. [Open the authors' Colab notebook](https://colab.research.google.com/drive/17q_lYUUniM5AlJTR7IR_pQkxGTLcpR6J)

1. Obtain the original **`MedCalc_Enforce_Experiments_v0_5.zip`** baseline from the authors. The notebook expects a `medcalc_enforce_pilot/` directory inside the ZIP. The public v0.6.0 release asset contains the completed study and cannot serve as that historical baseline.
2. Start a fresh Colab session. Choose **Runtime → Change runtime type → T4 GPU**, then **Runtime → Run all**. At the upload prompt in the second code cell, select the v0.5 ZIP. The recorded baseline passed 248 checksum checks.
3. The remaining cells reuse completed official traces, generate the additional model runs, and score the 240 distractor workflows. The notebook downloads a compatible CUDA build of `llama.cpp`. Its saved run used build `b12428`; a new session can select a different build.
4. The notebook's saved output reports **290 checksums** for its intermediate ZIP. The final GitHub and Zenodo release includes the subsequent reviewer analysis and verifies **294 files**. Use the released archive for the exact version cited in the paper.
