"""Pointwise action ablations, paired comparisons and conditional release quotas for the official cohorts."""
import argparse
import json
import math
from pathlib import Path

from analyze_repair_ablations import BASELINE, FULL, METHODS, compact, paired, quota_result, read_rows, replay, score, summarize
from medcalc.release_policy import execute_reviewed
from medcalc.source_fallback import execute
from official_study import digest
from run_source_repair import code_hashes
from score_execution_policies import evaluate, index, require_frozen_candidate
from score_live import wilson

ROOT = Path(__file__).resolve().parent
COHORTS = {
    "first": ("data/official_lock.json", "data/official_locked_inputs.jsonl", "data/official_reference.jsonl", "results/official"),
    "extension": ("data/official_extension/lock.json", "data/official_extension/inputs.jsonl", "data/official_extension/references.jsonl", "results/official_extension"),
}
MODELS = ("qwen2.5_1.5b_q4km", "smollm2_1.7b_q4km")
EXTRA_METHODS = ("note_only", "combined", "reviewed")


def require_locked_inputs():
    require_frozen_candidate()
    for name, expected in json.loads((ROOT / "results/code_review/secondary_freeze.json").read_text())["hashes"].items():
        if digest(ROOT / name) != expected:
            raise ValueError(f"Reviewed policy differs from recorded freeze: {name}")
    for cohort, (lock_path, inputs_path, refs_path, _) in COHORTS.items():
        lock = json.loads((ROOT / lock_path).read_text())
        if lock["input_sha256"] != digest(ROOT / inputs_path) or lock["reference_sha256"] != digest(ROOT / refs_path):
            raise ValueError(f"Official input or reference checksum mismatch for {cohort}")
        if lock["code_hashes"] != code_hashes():
            raise ValueError(f"Frozen methods changed for {cohort}")


def replay_all(inputs, references, traces):
    notes = index(inputs, "case_id")
    gold = index(references, "source_row")
    trace_by_id = index(traces, "case_id")
    if len(inputs) != len(gold) or set(gold) != {r["source_row"] for r in inputs}:
        raise ValueError("Reference keys do not match input cases")
    records = sorted(replay(inputs, traces), key=lambda r: int(r["source_row"]))
    for row in records:
        x = notes[row["case_id"]]
        raw = trace_by_id[row["case_id"]]
        ref = gold[row["source_row"]]
        score(row, ref)
        if ref.get("case_id", row["case_id"]) != row["case_id"]:
            raise ValueError("Reference case ID differs")
        proposal = raw.get("baseline_call", raw.get("call"))
        outputs = {
            "note_only": execute(x["question"], x["patient_note"], proposal, use_proposal=False),
            "combined": execute(x["question"], x["patient_note"], proposal),
            "reviewed": execute_reviewed(x["question"], x["patient_note"], proposal),
        }
        for method, out in outputs.items():
            selected = out.get("calculator_id", row["selected_calculator_id"])
            status = evaluate(out, selected, ref)
            row["methods"][method] = dict(compact(out), matched=status == "matching",
                                          route=out.get("route"), calculator_id=selected)
    return records


def compare_at_same_coverage(records, comparator, candidate):
    def quota_comparison(rows):
        quota = min(sum(row["methods"][m]["released"] for row in rows) for m in (comparator, candidate))
        return {
            "quota": quota,
            "uniform_comparator": quota_result(rows, comparator, quota, False),
            "quote_ranked_comparator": quota_result(rows, comparator, quota, True),
            "uniform_candidate": quota_result(rows, candidate, quota, False),
        }

    result = quota_comparison(records)
    groups = {}
    for row in records:
        groups.setdefault(str(row["selected_calculator_id"]), []).append(row)
    strata = {cid: quota_comparison(rows) for cid, rows in groups.items()}
    result["matched_model_selected_tool_mix"] = {
        "quota": sum(s["quota"] for s in strata.values()),
        "expected_matches": {method: round(math.fsum(s[method]["expected_matches"] for s in strata.values()), 12)
                             for method in ("uniform_comparator", "quote_ranked_comparator", "uniform_candidate")},
        "by_tool": strata,
    }
    common = [r for r in records if r["methods"][comparator]["released"] and r["methods"][candidate]["released"]]
    result["shared_answered_cases"] = {
        "n": len(common), "comparator_matches": sum(r["methods"][comparator]["matched"] for r in common),
        "candidate_matches": sum(r["methods"][candidate]["matched"] for r in common),
    }
    return result


def diagnostics(records):
    result = summarize(records)
    for method in EXTRA_METHODS:
        matched = sum(r["methods"][method]["matched"] for r in records)
        released = sum(r["methods"][method]["released"] for r in records)
        n = len(records)
        result["methods"][method] = {
            "released": released, "matched": matched, "nonmatching": released - matched, "no_answer": n - released,
            "agreement": matched / n, "coverage": released / n, "agreement_wilson95": wilson(matched, n),
            "conditional_agreement_wilson95": wilson(matched, released),
        }
    pairs = [(BASELINE, "note_only"), (BASELINE, "combined"), (BASELINE, "reviewed"),
             ("note_only", "combined"), (FULL, "combined"), ("combined", "reviewed")]
    result["extra_paired"] = {f"{a}_vs_{b}": paired(records, a, b) for a,b in pairs}
    result["extra_equal_coverage"] = {f"{BASELINE}_vs_{b}": compare_at_same_coverage(records, BASELINE, b)
                                      for b in EXTRA_METHODS}
    return result


def self_check():
    # Independent of all official inference. Known outcomes come from v0.3.
    inputs = read_rows(ROOT / "data/binding_validation_inputs.jsonl")
    refs = index(read_rows(ROOT / "data/pilot_rows.jsonl"), "source_row")
    traces = read_rows(ROOT / "results/binding/validation_repair_v2/cases.jsonl")
    records = replay_all(inputs, [refs[r["source_row"]] for r in inputs], traces)
    summary = diagnostics(records)
    if summary["methods"][BASELINE]["matched"] != 37 or summary["methods"][FULL]["matched"] != 39:
        raise ValueError("Prior complete-cohort replay drifted")
    for method in METHODS + EXTRA_METHODS:
        m = summary["methods"][method]
        assert m["matched"] + m["nonmatching"] + m["no_answer"] == len(records)
    for name, quota in summary["extra_equal_coverage"].items():
        for m in ("uniform_comparator", "quote_ranked_comparator", "uniform_candidate"):
            assert quota[m]["released"] == quota["quota"], name
    print("50-case offline regression passed for all policies, paired scores and equal-coverage quotas.")


def cross_model_counts(per_model):
    # Both models see the same source group. Descriptive totals only.
    return {method: {metric: sum(per_model[model]["pooled"]["methods"][method][metric] for model in MODELS)
                     for metric in ("matched", "nonmatching", "no_answer", "released")}
            for method in METHODS + EXTRA_METHODS}


def write_report(summary, path):
    s = ["# Official test action ablations and paired release comparisons", "",
         "Each model received the same 124 official cases. The first locked cohort contributed 44 cases and the extension added the remaining 80 eligible source groups. Pooling the two disjoint cohorts within each model weights every case equally. Counts across both models represent 248 model–case attempts from 124 sources. No interval or significance test treats the 248 attempts as independent. All denominators include unanswered cases.", "",
         "The source verifier accepts canonical source matches. Unit and named-value ablations permit the indicated forms of repair and abstain when another frozen action was required. These are action restrictions. No alternative candidate search is performed after a disabled decision. The combined candidate also permits deterministic resolution from uniquely named measurements. The reviewed policy adds textual scope constraints and is a secondary comparison. All action ablations, quotas and paired tests in this report are exploratory.", ""]
    for model, views in summary["models"].items():
        s += ["## " + model, ""]
        for view in ("first", "extension", "pooled"):
            result = views[view]
            s += [f"### {view.title()} ({result['cases']} cases)", "",
                  "| Policy | Match | Nonmatching released | Unanswered | Coverage |",
                  "|---|---:|---:|---:|---:|"]
            for name,m in result["methods"].items():
                s.append(f"| {name} | {m['matched']} | {m['nonmatching']} | {m['no_answer']} | {m['coverage']:.1%} |")
            s += ["", "| Candidate vs unit/domain baseline | Gain / loss in matches | Paired change, points (exploratory 95% interval) | Shared answered cases, baseline / candidate matches |",
                  "|---|---:|---:|---:|"]
            for candidate in (FULL,) + EXTRA_METHODS:
                if candidate == FULL:
                    contrast = result["paired_to_full"][BASELINE]
                    common = result["same_returned_cases"]
                    shared = [common["same_returned_case_count"], common["baseline_matches"], common["full_repair_matches"]]
                else:
                    key = f"{BASELINE}_vs_{candidate}"
                    contrast = result["extra_paired"][key]
                    common = result["extra_equal_coverage"][key]["shared_answered_cases"]
                    shared = [common["n"], common["comparator_matches"], common["candidate_matches"]]
                low, high = contrast["calculator_stratified_bootstrap95"]
                s.append(f"| {candidate} | {contrast['gained']} / {contrast['lost']} | {100*contrast['delta_fraction']:+.1f} ({100*low:+.1f} to {100*high:+.1f}) | {shared[0]} cases, {shared[1]} / {shared[2]} matches |")
            s += ["", "| Compared at equal quotas | Released per method | Expected matches, uniform baseline | Expected matches, quote-ranked baseline | Expected matches, candidate |",
                  "|---|---:|---:|---:|---:|"]
            quota = result["matched_coverage"]
            s.append(f"| {FULL} | {quota['quota']} | {quota['uniform_unit_domain']['expected_matches']:.2f} | {quota['quote_ranked_unit_domain']['expected_matches']:.2f} | {quota['uniform_source_repair']['expected_matches']:.2f} |")
            for candidate in EXTRA_METHODS:
                q = result["extra_equal_coverage"][f"{BASELINE}_vs_{candidate}"]
                s.append(f"| {candidate} | {q['quota']} | {q['uniform_comparator']['expected_matches']:.2f} | {q['quote_ranked_comparator']['expected_matches']:.2f} | {q['uniform_candidate']['expected_matches']:.2f} |")
            s.append("")
    s.extend(["## Interpretation", "", "Each equal-coverage comparison uses the smaller of the paired release counts. Uniform thinning integrates random selection exactly. Quote ranking sorts the baseline answers by the fraction of proposed fields with exact supporting quotes and integrates ties exactly at the cutoff. The quota uses the two observed coverage counts and is retrospective. Fractional values are conditional expectations. Missing results and abstentions remain in the denominator for paired whole-cohort comparisons. JSON also reports direct shared-case comparisons, per-selected-calculator quotas, hypergeometric selection intervals, and exploratory calculator-stratified case-bootstrap intervals. Alternative confidence rankers and prospectively calibrated thresholds may yield different results.", "",
               "Recompute from the four completed model traces with `python3 analyze_official_ablations.py`. The input/output digests identify each locked cohort and each source trace. The self-check uses an earlier complete 50-case cohort with known reference counts.", ""])
    path.write_text("\n".join(s))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "results/official_ablations")
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        self_check()
        return
    require_locked_inputs()
    results = {"models": {}, "input_sha256": {}, "trace_sha256": {}, "new_llm_calls_for_replay": 0}
    case_artifacts = {}
    for model in MODELS:
        views, union = {}, []
        for cohort, (lock, inputs, refs, traces) in COHORTS.items():
            ids = json.loads((ROOT / lock).read_text())
            path = ROOT / traces / model / "cases.jsonl"
            archived = read_rows(path)
            if len(archived) != ids["selected"] or not all(r.get("model_id") == model for r in archived):
                raise ValueError(f"Missing or wrong-model rows for {model} {cohort}")
            records = replay_all(read_rows(ROOT / inputs), read_rows(ROOT / refs), archived)
            views[cohort] = diagnostics(records)
            results["trace_sha256"][f"{model}/{cohort}"] = digest(path)
            results["input_sha256"][cohort] = {p:digest(ROOT / p) for p in (lock,inputs,refs)}
            union.extend(dict(r, cohort=cohort) for r in records)
        if len(union) != 124 or len({r["group_id"] for r in union}) != 124 or len({r["case_id"] for r in union}) != 124:
            raise ValueError("Pooled cohort must comprise 124 distinct cases and source groups")
        views["pooled"] = diagnostics(union)
        results["models"][model] = views
        case_artifacts[model] = union
    if {r["case_id"] for r in case_artifacts[MODELS[0]]} != {r["case_id"] for r in case_artifacts[MODELS[1]]}:
        raise ValueError("Models were evaluated on different case IDs")
    results["cross_model_descriptive_only"] = {"unique_sources": 124, "model_case_attempts": 248,
                                              "methods": cross_model_counts(results["models"])}
    args.output.mkdir(parents=True, exist_ok=True)
    for model, records in case_artifacts.items():
        (args.output / (model + "_cases.jsonl")).write_text("".join(json.dumps(r,sort_keys=True)+"\n" for r in records))
    (args.output / "summary.json").write_text(json.dumps(results, indent=2)+"\n")
    write_report(results, args.output / "REPORT.md")
    print("Wrote official ablations and equal-coverage analysis:", args.output)


if __name__ == "__main__":
    main()
