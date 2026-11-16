"""Score paired research policies against a locked cohort after the model run."""
import argparse
import collections
import hashlib
import json
import math
from pathlib import Path

from medcalc.source_fallback import execute
from score_live import wilson

ROOT = Path(__file__).resolve().parent


def records(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def index(rows, key):
    indexed = {row[key]: row for row in rows}
    if len(indexed) != len(rows):
        raise ValueError(f"Duplicate {key}")
    return indexed


def require_frozen_candidate():
    lock = json.loads((ROOT / "results/fallback/pre_inference_freeze.json").read_text())
    for name, expected in lock["hashes"].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Frozen file changed: {name}")


def evaluate(result, selected_calculator, reference):
    if not result.get("released"):
        return "unanswered"
    numerical_match = float(reference["lower"]) <= result["result"] <= float(reference["upper"])
    return "matching" if numerical_match and selected_calculator == reference["calculator_id"] else "nonmatching"


def exact_p(gains, losses):
    discordant = gains + losses
    return min(1, 2 * sum(math.comb(discordant, i) for i in range(min(gains, losses) + 1)) / 2**discordant)


def score_cohort(inputs_path, references_path, traces_path, output, reviewed):
    notes = index(records(inputs_path), "case_id")
    gold = index(records(references_path), "source_row")
    traces = index(records(traces_path), "case_id")
    if traces.keys() != notes.keys():
        raise ValueError("A complete set of unique paired traces is required")
    details = []
    for case, row in notes.items():
        trace = traces[case]
        reference = gold[row["source_row"]]
        field = trace.get("selected_calculator_id")
        proposal = trace.get("baseline_call")
        methods = {"baseline": trace.get("baseline_gates", {}).get("L2_unit_domain", {}),
                   "source_repair": trace.get("source_bound", {})}
        for name in ("note_only", "combined"):
            methods[name] = execute(row["question"], row["patient_note"], proposal, use_proposal=name == "combined")
        if reviewed:
            from medcalc.release_policy import execute_reviewed
            methods["reviewed"] = execute_reviewed(row["question"], row["patient_note"], proposal)
        outcomes = {name: evaluate(result, result.get("calculator_id", field), reference)
                    for name, result in methods.items()}
        details.append({"case_id": case, "group_id": row["group_id"], "calculator_id": reference["calculator_id"],
                        "outcomes": outcomes, "evaluated": {name: result for name, result in methods.items()
                                                           if name not in ("baseline", "source_repair")}})
    summary = {}
    for name in details[0]["outcomes"]:
        counts = collections.Counter(row["outcomes"][name] for row in details)
        released = counts["matching"] + counts["nonmatching"]
        pairs = collections.Counter((r["outcomes"]["baseline"], r["outcomes"][name]) for r in details)
        gains = sum(count for (a, b), count in pairs.items() if a != "matching" and b == "matching")
        losses = sum(count for (a, b), count in pairs.items() if a == "matching" and b != "matching")
        summary[name] = {"n": len(details), "matches": counts["matching"], "nonmatching_released": counts["nonmatching"],
                         "unanswered": counts["unanswered"], "released": released,
                         "all_case_agreement_wilson95": wilson(counts["matching"], len(details)),
                         "error_among_released_wilson95": wilson(counts["nonmatching"], released),
                         "gains_vs_baseline": gains, "losses_vs_baseline": losses, "paired_exact_p": exact_p(gains, losses),
                         "transitions_vs_baseline": {f"{a} to {b}": n for (a,b), n in sorted(pairs.items())}}
    output.mkdir(parents=True, exist_ok=True)
    (output / "cases.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in details))
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", required=True, type=Path)
    parser.add_argument("--references", required=True, type=Path)
    parser.add_argument("--traces", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--reviewed", action="store_true", help="Also evaluate the secondary release guard")
    args = parser.parse_args()
    require_frozen_candidate()
    results = score_cohort(args.inputs, args.references, args.traces, args.output, args.reviewed)
    print({method: (r["matches"], r["nonmatching_released"], r["unanswered"]) for method,r in results.items()})


if __name__ == "__main__":
    main()
