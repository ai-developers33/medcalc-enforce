"""Replay the frozen proposed methods and summarize same-case outcomes across models."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path

from score_execution_policies import ROOT, exact_p, index, records, require_frozen_candidate, score_cohort
from score_live import wilson

DATA = ROOT / "data"
OUTPUT = ROOT / "results/final_evaluation"
SMALL = ("qwen2.5_1.5b_q4km", "smollm2_1.7b_q4km")
LARGE = "qwen2.5_7b_q4km"
PHASES = {
    "first": (DATA / "official_locked_inputs.jsonl", DATA / "official_reference.jsonl", ROOT / "results/official"),
    "extension": (DATA / "official_extension/inputs.jsonl", DATA / "official_extension/references.jsonl", ROOT / "results/official_extension"),
}


def field_match(observed, expected):
    if isinstance(expected, str):
        return observed == expected
    return isinstance(observed, (int, float)) and math.isclose(observed, expected, rel_tol=1e-5, abs_tol=1e-7)


def counts(group, method):
    return Counter(row["outcomes"][method] for row in group)


def analysis(group, gold, traces):
    result = {}
    for method in group[0]["outcomes"]:
        tally = counts(group, method)
        matches, mismatches = tally["matching"], tally["nonmatching"]
        released = matches + mismatches
        baseline = "baseline"
        gains = sum(r["outcomes"][baseline] != "matching" and r["outcomes"][method] == "matching" for r in group)
        losses = sum(r["outcomes"][baseline] == "matching" and r["outcomes"][method] != "matching" for r in group)
        field_tally = Counter()
        diagnostic_ids = defaultdict(list)
        for row in group:
            ref = gold[row["case_id"]]
            trace = traces[row["case_id"]]
            if method == "baseline":
                decision = trace.get("baseline_gates", {}).get("L2_unit_domain", {})
            elif method == "source_repair":
                decision = trace.get("source_bound", {})
            else:
                decision = row["evaluated"][method]
            if row["outcomes"][method] == "nonmatching":
                diagnostic_ids["disagreements"].append(row["case_id"])
            if not decision.get("released"):
                continue
            cid = decision.get("calculator_id", trace.get("selected_calculator_id"))
            correct_fields = sum(field_match(decision["canonical_inputs"].get(field), value)
                                 for field, value in ref["canonical_inputs"].items()) if cid == ref["calculator_id"] else 0
            all_fields = correct_fields == len(ref["canonical_inputs"])
            field_tally["all_annotated_inputs_matched"] += all_fields
            field_tally["individual_matches"] += correct_fields
            field_tally["required_fields_among_releases"] += len(ref["canonical_inputs"])
            if not all_fields and row["outcomes"][method] == "matching":
                diagnostic_ids["answer_in_tolerance_despite_field_disagreement"].append(row["case_id"])
        result[method] = {
            "cases": len(group), "matched": matches, "nonmatching": mismatches, "unanswered": len(group)-released,
            "coverage":released/len(group), "agreement":matches/len(group),
            "agreement_wilson95":wilson(matches,len(group)),
            "error_among_released_wilson95":wilson(mismatches,released),
            "paired_gains":gains, "paired_losses":losses, "paired_exact_p_unadjusted":exact_p(gains,losses),
            "by_calculator":{cid:dict(counts([r for r in group if r["calculator_id"] == cid], method))
                             for cid in sorted({r["calculator_id"] for r in group}, key=int)},
            "field_checks":dict(field_tally), "case_ids":dict(diagnostic_ids),
        }
    return result


def verify_lock(path):
    lock = json.loads(path.read_text())
    for file, expected in lock["hashes"].items():
        if hashlib.sha256((ROOT/file).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Hash mismatch in {file}")


def run(model, phases):
    gold = index(records(ROOT / "results/reference_audit/canonical_reference_all.jsonl"), "case_id")
    details, all_traces, outputs = [], [], {}
    for phase in phases:
        inputs, refs, folder = PHASES[phase]
        traces = folder / model / "cases.jsonl"
        destination = OUTPUT / model / phase
        score_cohort(inputs, refs, traces, destination, True)
        phase_rows = records(destination / "cases.jsonl")
        phase_traces = records(traces)
        details.extend(phase_rows)
        all_traces.extend(phase_traces)
        outputs[phase] = analysis(phase_rows, gold, index(phase_traces,"case_id"))
    if len({r["group_id"] for r in details}) != len(details):
        raise ValueError("Source overlap across cohorts")
    all_index = index(all_traces, "case_id")
    outputs["all"] = analysis(details, gold, all_index)
    overlap = index(records(ROOT / "results/template_audit/case_flags.jsonl"), "case_id")
    narrative = [r for r in details if overlap[r["case_id"]]["note_type"] == "Extracted"]
    if narrative:
        outputs["extracted_source_notes"] = analysis(narrative, gold, all_index)
    (OUTPUT / model / "report.json").write_text(json.dumps(outputs, indent=2) + "\n")
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=(*SMALL,LARGE), required=True)
    parser.add_argument("--first-only", action="store_true")
    args = parser.parse_args()
    require_frozen_candidate()
    verify_lock(ROOT/"results/code_review/secondary_freeze.json")
    phases = ["first"] if args.model == LARGE or args.first_only else ["first","extension"]
    report = run(args.model, phases)
    print({m:[v["matched"],v["nonmatching"],v["unanswered"]] for m,v in report["all"].items()})


if __name__ == "__main__":
    main()
