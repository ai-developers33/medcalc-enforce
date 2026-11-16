"""Rebuild the v0.6.0 distractor table from the five archived model traces."""

import argparse
import json
import sys
from pathlib import Path

from medcalc.discourse_guard import execute_v05
from medcalc.release_policy import execute_reviewed
from run_bdcc_v05_suite import benjamini_hochberg, holm_bonferroni
from score_execution_policies import exact_p, index, records
from score_live import wilson


ROOT = Path(__file__).resolve().parent
MODELS = (
    "qwen2.5_1.5b_q4km",
    "smollm2_1.7b_q4km",
    "qwen2.5_7b_q4km",
    "phi3.5_mini_q4km",
    "llama3.1_8b_q4km",
)
SECTION = "experiment_8_live_5model_distractor_traps_240"


def score_model(model, inputs):
    path = ROOT / "results" / "distractor_traps" / model / "cases.jsonl"
    traces = index(records(path), "case_id")
    if traces.keys() != inputs.keys():
        raise ValueError(f"{model}: trace case IDs differ from the 48 locked inputs")

    n = len(inputs)
    baseline_count = reviewed_count = discourse_count = 0
    prevented = introduced = 0
    for case_id, case in inputs.items():
        trace = traces[case_id]
        if trace["model_id"] != model:
            raise ValueError(f"{case_id}: unexpected model in {path}")
        proposal = trace.get("baseline_call")
        # A workflow with no recorded proposal contributed a baseline abstention.
        baseline = False if proposal is None else trace["baseline_gates"]["L2_unit_domain"]["released"]
        args = case["question"], case["patient_note"], proposal
        reviewed = execute_reviewed(*args)["released"]
        discourse = execute_v05(*args)["released"]
        baseline_count += baseline
        reviewed_count += reviewed
        discourse_count += discourse
        prevented += baseline and not discourse
        introduced += discourse and not baseline

    p = exact_p(prevented, introduced)
    metrics = {
        "n_traps": n,
        "unit_domain_false_releases": baseline_count,
        "unit_domain_false_release_rate": round(baseline_count / n, 6),
        "unit_domain_wilson95": [round(x, 6) for x in wilson(baseline_count, n)],
        "reviewed_v04_false_releases": reviewed_count,
        "discourse_v05_false_releases": discourse_count,
        "discourse_v05_false_release_rate": round(discourse_count / n, 6),
        "discourse_v05_wilson95": [round(x, 6) for x in wilson(discourse_count, n)],
        "unsafe_traps_eliminated_vs_unit_domain": prevented,
        "mcnemar_exact_p": round(p, 14),
    }
    return metrics, p


def replay():
    inputs = index(records(ROOT / "data/distractor_traps_48.jsonl"), "case_id")
    if len(inputs) != 48:
        raise ValueError(f"Expected 48 distinct input cases, found {len(inputs)}")
    summaries, p_values = {}, {}
    for model in MODELS:
        summaries[model], p_values[model] = score_model(model, inputs)
    # Multiple-testing corrections use the unrounded paired p-values.
    holm = holm_bonferroni(p_values)
    bh = benjamini_hochberg(p_values)
    for model, row in summaries.items():
        row["holm_p"] = holm[model]
        row["bh_q"] = bh[model]
    return summaries


def table(summaries):
    lines = [
        "| Model | Traps | `unit_domain` False Releases (%) | `reviewed_v04` False Releases | "
        "`discourse_v05` False Releases (%) | Holm-Adjusted p | BH q |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for model, row in summaries.items():
        lines.append(
            f"| `{model}` | {row['n_traps']} | {row['unit_domain_false_releases']} "
            f"({row['unit_domain_false_release_rate']:.1%}) | {row['reviewed_v04_false_releases']} | "
            f"{row['discourse_v05_false_releases']} ({row['discourse_v05_false_release_rate']:.1%}) | "
            f"{row['holm_p']:.4g} | {row['bh_q']:.4g} |"
        )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="also compare all Experiment 8 metrics and the table with the release",
    )
    args = parser.parse_args()
    rows = replay()
    markdown = table(rows)
    if args.check:
        directory = ROOT / "results/v0_5_bdcc"
        published = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
        if published.get(SECTION) != rows:
            raise SystemExit("Experiment 8 metrics differ from, or are missing in, summary.json")
        report = (directory / "BDCC_STRENGTHENED_RESULTS.md").read_text(encoding="utf-8")
        section = report.partition("\n## 8. ")[2].partition("\n## ")[0]
        archived_table = "\n".join(line for line in section.splitlines() if line.startswith("|"))
        if archived_table != markdown:
            raise SystemExit("Experiment 8 table differs from the published report")
        print("Verified all five model summaries and the published 240-workflow table.", file=sys.stderr)
    print(markdown)


if __name__ == "__main__":
    main()
