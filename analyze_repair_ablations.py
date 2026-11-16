"""Offline paired replay and equal-coverage diagnostics on archived model calls."""
import argparse
from collections import Counter, defaultdict
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import random
from statistics import quantiles

from medcalc.enforcement import Rejected
from medcalc.live import check_spans
from medcalc.source_repair import make_source_packet, repair_call
from run_source_repair import code_hashes
from score_live import wilson

ROOT = Path(__file__).resolve().parent
DEFAULT_INPUTS = "data/live_inputs.jsonl"
BASELINE = "unit_domain"
FULL = "source_repair"
EXACT = "canonical_source_match"
UNIT = "source_unit_repair"
NAMED = "unique_named_source_repair"
# IDs match the frozen v2 audit trail. A disabled action makes the case abstain.
ACTIONS = {
    "source_verify_only": {EXACT},
    "source_verify_and_unit": {EXACT, UNIT},
    "source_verify_and_named_value": {EXACT, NAMED},
    FULL: {EXACT, UNIT, NAMED},
}
METHODS = (BASELINE, "literal_quote", *ACTIONS)
COHORTS = [
    ("qwen_development", "results/live/qwen2.5_1.5b_q4km_schema.jsonl", DEFAULT_INPUTS),
    ("qwen_validation", "results/binding/validation_repair_v2/cases.jsonl", "data/binding_validation_inputs.jsonl"),
    ("smollm2_development", "results/live/smollm2_1.7b_q4km_schema.jsonl", DEFAULT_INPUTS),
]


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def compact(outcome):
    if outcome.get("released"):
        return {"released": True, "result": outcome["result"]}
    return {"released": False, "reason": outcome.get("reason", "no_executable_call")}


def ablations(call, note):
    if call is None:
        return {method: compact({}) for method in ACTIONS}, {}
    try:
        packet = make_source_packet(call["calculator_id"], note)
        full = repair_call(call, packet, note)
    except (Rejected, ValueError, TypeError, KeyError) as error:
        return {method: {"released": False, "reason": str(error)} for method in ACTIONS}, {}
    field_actions = {name: audit["action"] for name, audit in full["evidence"].items()}
    required_actions = set(field_actions.values())
    if not required_actions <= ACTIONS[FULL]:
        raise ValueError(f"Unrecognized frozen action {required_actions - ACTIONS[FULL]}")
    outputs = {}
    for method, allowed in ACTIONS.items():
        disabled = sorted(required_actions - allowed)
        outputs[method] = ({"released": False, "reason": "disabled action " + ", ".join(disabled)}
                           if disabled else compact(full))
    return outputs, field_actions


def supported_quote_fraction(call, quotes, note):
    """Evidence-only score. The literal v0.2 verifier judges one proposed field at a time."""
    if not call:
        return Fraction(0)
    supported = 0
    for field, arg in call["arguments"].items():
        try:
            check_spans({"arguments": {field: arg}}, {field: quotes[field]}, note)
        except (Rejected, KeyError, TypeError, ValueError):
            continue
        supported += 1
    return Fraction(supported, len(call["arguments"]))


def score(case, label):
    if case["source_row"] != label["source_row"]:
        raise ValueError("Scoring join mismatch")
    for method in METHODS:
        out = case["methods"][method]
        out["matched"] = bool(out["released"] and case["selected_calculator_id"] == label["calculator_id"]
                              and float(label["lower"]) <= out["result"] <= float(label["upper"]))
    case["reference_calculator_id"] = label["calculator_id"]


def replay(inputs, traces):
    by_case = {x["case_id"]: x for x in inputs}
    if len(by_case) != len(inputs) or len(traces) != len(inputs) or {r["case_id"] for r in traces} != set(by_case):
        raise ValueError("Trace and input IDs do not form a one-to-one complete match")
    records = []
    for row in traces:
        x = by_case[row["case_id"]]
        if row["source_row"] != x["source_row"] or row["group_id"] != x["group_id"]:
            raise ValueError(f"Input mismatch on {row['case_id']}")
        call = row.get("baseline_call", row.get("call"))
        quotes = row.get("baseline_quotes", row.get("quotes", {}))
        gates = row.get("baseline_gates", row.get("gates", {}))
        repair, actions = ablations(call, x["patient_note"])
        known = row.get("source_bound")
        if known is not None:
            if bool(known.get("released")) != repair[FULL]["released"] or known.get("result") != repair[FULL].get("result"):
                raise ValueError(f"Frozen replay diverged on {row['case_id']}")
        records.append({
            "case_id": row["case_id"], "source_row": row["source_row"], "group_id": row["group_id"],
            "selected_calculator_id": row.get("selected_calculator_id"),
            "quote_fraction": str(supported_quote_fraction(call, quotes, x["patient_note"])),
            "source_actions": actions,
            "methods": {
                BASELINE: compact(gates.get("L2_unit_domain", {})),
                "literal_quote": compact(gates.get("L3_literal_span", {})),
                **repair,
            },
        })
    return records


def paired(records, before, after):
    by_calculator = defaultdict(list)
    transitions = Counter()
    for r in records:
        a, b = (r["methods"][m] for m in (before, after))
        by_calculator[r["reference_calculator_id"]].append(int(b["matched"]) - int(a["matched"]))
        statuses = tuple("match" if v["matched"] else ("nonmatch" if v["released"] else "no_answer") for v in (a, b))
        transitions[" to ".join(statuses)] += 1
    deltas = [d for group in by_calculator.values() for d in group]
    gains, losses = deltas.count(1), deltas.count(-1)
    discordant = gains + losses
    exact = min(1.0, 2 * sum(math.comb(discordant, k) for k in range(min(gains, losses) + 1)) / 2**discordant)
    rng = random.Random(731)
    draws = [sum(sum(rng.choices(group, k=len(group))) for group in by_calculator.values()) / len(records)
             for _ in range(5000)]
    cuts = quantiles(draws, n=40, method="inclusive")
    return {"gained": gains, "lost": losses, "delta_fraction": (gains - losses) / len(records),
            "calculator_stratified_bootstrap95": [cuts[0], cuts[-1]], "paired_exact_mcnemar_p": exact,
            "transitions": dict(sorted(transitions.items()))}


def hypergeometric_interval(population, matches, count):
    """Conditional central 95% random-selection interval, not a population CI."""
    low = max(0, count - (population - matches))
    high = min(count, matches)
    denominator = math.comb(population, count)
    cumulative = 0
    bounds = []
    for matched in range(low, high + 1):
        cumulative += math.comb(matches, matched) * math.comb(population - matches, count - matched)
        for target in (Fraction(1, 40), Fraction(39, 40))[len(bounds):]:
            if cumulative < target * denominator:
                break
            bounds.append(matched)
    return bounds


def quota_result(records, method, quota, rank_by_quote):
    """Integrate tie-breaking exactly at a quota. Rank uses no benchmark labels."""
    groups = defaultdict(list)
    for row in records:
        out = row["methods"][method]
        if out["released"]:
            rank = Fraction(row["quote_fraction"]) if rank_by_quote else Fraction(0)
            groups[rank].append(out["matched"])
    if quota > sum(map(len, groups.values())):
        raise ValueError("Quota exceeds available outputs")
    remaining = quota
    fixed = 0
    for rank in sorted(groups, reverse=True):
        members = groups[rank]
        if remaining >= len(members):
            remaining -= len(members)
            fixed += sum(members)
            continue
        matches = sum(members)
        expectation = fixed + remaining * matches / len(members)
        interval = [fixed + v for v in hypergeometric_interval(len(members), matches, remaining)]
        return {"released": quota, "expected_matches": round(expectation, 12), "expected_nonmatching": round(quota - expectation, 12),
                "conditional_95_match_counts": interval, "tied_candidates_at_cutoff": len(members),
                "places_at_cutoff": remaining}
    return {"released": quota, "expected_matches": fixed, "expected_nonmatching": quota - fixed,
            "conditional_95_match_counts": [fixed, fixed], "tied_candidates_at_cutoff": 0, "places_at_cutoff": 0}


def summarize(records):
    metrics = {}
    for method in METHODS:
        released = sum(r["methods"][method]["released"] for r in records)
        matched = sum(r["methods"][method]["matched"] for r in records)
        metrics[method] = {"released": released, "matched": matched, "nonmatching": released - matched,
                           "no_answer": len(records) - released, "agreement": matched / len(records),
                           "coverage": released / len(records), "agreement_wilson95": wilson(matched, len(records)),
                           "conditional_agreement_wilson95": wilson(matched, released)}
    quota = min(metrics[BASELINE]["released"], metrics[FULL]["released"])
    by_selected_tool = defaultdict(list)
    for row in records:
        by_selected_tool[row["selected_calculator_id"]].append(row)
    # A model-selected tool is available before scoring. Matching its quotas
    # controls for differences in the mix of answered calculators.
    matched_tool_mix = {}
    for tool, rows in by_selected_tool.items():
        count = min(sum(row["methods"][m]["released"] for row in rows) for m in (BASELINE, FULL))
        matched_tool_mix[str(tool)] = {
            "quota": count, "uniform_unit_domain": quota_result(rows, BASELINE, count, False),
            "quote_ranked_unit_domain": quota_result(rows, BASELINE, count, True),
            "uniform_source_repair": quota_result(rows, FULL, count, False),
        }
    common = [r for r in records if all(r["methods"][m]["released"] for m in (BASELINE, FULL))]
    common_results = {
        "same_returned_case_count": len(common),
        "baseline_matches": sum(r["methods"][BASELINE]["matched"] for r in common),
        "full_repair_matches": sum(r["methods"][FULL]["matched"] for r in common),
    }
    mix_totals = {m: round(math.fsum(v[m]["expected_matches"] for v in matched_tool_mix.values()), 12)
                  for m in ("uniform_unit_domain", "quote_ranked_unit_domain", "uniform_source_repair")}
    return {
        "same_returned_cases": common_results,
        "matched_selected_tool_mix": {
            "quota": sum(v["quota"] for v in matched_tool_mix.values()),
            "expected_matches": mix_totals, "by_tool": matched_tool_mix,
        },
        "cases": len(records), "unique_source_groups": len({r["group_id"] for r in records}), "methods": metrics,
        "paired_to_full": {method: paired(records, method, FULL) for method in METHODS if method != FULL},
        "matched_coverage": {"quota": quota, "coverage": quota / len(records),
                             "uniform_unit_domain": quota_result(records, BASELINE, quota, False),
                             "quote_ranked_unit_domain": quota_result(records, BASELINE, quota, True),
                             "uniform_source_repair": quota_result(records, FULL, quota, False)},
    }


def write_report(path, report):
    lines = [
        "# Paired action ablations and equal-coverage comparisons",
        "",
        "Offline replay reuses the archived schema-constrained tool calls. Qwen validation uses 50 cases from separate articles within the training-derived study pool. Both models' development results use the same original 50 cases that informed development. SmolLM2 is a second set of model-generated calls on those cases. There are 100 distinct case IDs across all three cohorts. No new model inference or clinical outcome assessment took place in this analysis.",
        "",
        "The four source policies use the frozen source parser and original formula code. The verification-only alternative accepts proposals already matching canonical source quantities. The unit alternative additionally accepts a native-number match needing unit repair. The named-value alternative instead permits replacement by a unique explicitly named source quantity. A disabled required action makes the case abstain. These variants isolate which frozen decisions depend on each action. They do not search for new lower-priority evidence after disabling a decision.",
        "",
        "Numerical matches require the correct calculator and its benchmark result interval. All cases contribute to the agreement denominator. Development and validation counts are reported separately.",
    ]
    for key, cohort in report["cohorts"].items():
        lines += ["", "## " + key.replace("_", " ").title().replace("Smollm2", "SmolLM2"), "",
                  "| Method | Matches / cases | Nonmatching released | No answer | Coverage |",
                  "|---|---:|---:|---:|---:|"]
        for method, m in cohort["methods"].items():
            lines.append(f"| {method} | {m['matched']}/{cohort['cases']} | {m['nonmatching']} | {m['no_answer']} | {m['coverage']:.0%} |")
        contrast = cohort["paired_to_full"][BASELINE]
        low, high = contrast["calculator_stratified_bootstrap95"]
        lines += ["", f"Full repair gained {contrast['gained']} matches and lost {contrast['lost']} compared with unit/domain checks. The change was {contrast['delta_fraction']:+.1%} of all cases (exploratory stratified bootstrap interval {low:+.1%} to {high:+.1%}, paired exact McNemar p = {contrast['paired_exact_mcnemar_p']:.4g}).",
                  "", "| Matched-coverage policy | Released | Expected matches | Expected nonmatches | Random-selection 95% match-count interval |",
                  "|---|---:|---:|---:|---:|"]
        for name, m in cohort["matched_coverage"].items():
            if isinstance(m, dict):
                interval = m["conditional_95_match_counts"]
                lines.append(f"| {name} | {m['released']} | {m['expected_matches']:.2f} | {m['expected_nonmatching']:.2f} | {interval[0]} to {interval[1]} |")
        mix = cohort["matched_selected_tool_mix"]
        results = mix["expected_matches"]
        common = cohort["same_returned_cases"]
        lines += ["", f"Matching release quotas separately within each model-selected calculator gives a total quota of {mix['quota']}. Expected matches are {results['uniform_unit_domain']:.2f} for uniform baseline selection, {results['quote_ranked_unit_domain']:.2f} for quote-ranked baseline selection and {results['uniform_source_repair']:.2f} for source repair.",
                  "", f"Both policies answered the same {common['same_returned_case_count']} cases in their overlap. On those identical cases the unit/domain baseline matched {common['baseline_matches']} references and source repair matched {common['full_repair_matches']}. This conditional subset isolates differences in the returned values; it is not a coverage estimate."]
    lines += ["", "## Interpretation", "",
              "Matched coverage uses the smaller observed release count as a quota for both policies. Uniform selection gives the expected count when withholding answers at random. An evidence-based comparator ranks the baseline's eligible calls by the fraction of individual field quotes that pass the existing literal verifier. Rank and tie handling use only proposed fields and source text. Random tie-breaking is integrated exactly using the hypergeometric distribution. Fractional counts are expectations, not individual observed answers. A central interval can have identical endpoints even when rare alternative counts are possible.",
              "",
              "These quotas are retrospective. A deployment would need a threshold calibrated on separate data. A model-confidence selector or a different evidence ranker could outperform either comparator. The hypergeometric intervals describe tie/random-selection variation conditional on the fixed cases. The paired bootstrap resamples cases inside each reference-calculator stratum. Neither interval establishes performance in a clinical population. The comparisons are exploratory and are unadjusted for multiple testing.",
              "",
              "Run `python3 analyze_repair_ablations.py` from the project root. The JSON summary includes paired gains, losses, transitions, descriptive intervals and exact input hashes for every cohort. Case-level JSONL records the score, source actions and outcomes for each replay.",
              ""]
    path.write_text("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "results/paired_ablations")
    args = parser.parse_args()
    freeze = json.loads((ROOT / "data/binding_freeze.json").read_text())
    if freeze["code_hashes"] != code_hashes():
        raise ValueError("Evaluated source or prompt code differs from the frozen version")
    args.output.mkdir(parents=True, exist_ok=True)
    label_path = ROOT / "data/pilot_rows.jsonl"
    labels = {r["source_row"]: r for r in read_rows(label_path)}
    report = {"new_model_calls": 0, "distinct_case_ids": None, "code_hashes": code_hashes(),
              "label_sha256": hashlib.sha256(label_path.read_bytes()).hexdigest(), "cohorts": {}}
    distinct = set()
    for name, trace_name, input_name in COHORTS:
        traces_path, inputs_path = ROOT / trace_name, ROOT / input_name
        records = replay(read_rows(inputs_path), read_rows(traces_path))
        for case in records:
            score(case, labels[case["source_row"]])
        distinct.update(r["case_id"] for r in records)
        cohort = summarize(records)
        cohort["trace_sha256"] = hashlib.sha256(traces_path.read_bytes()).hexdigest()
        cohort["input_sha256"] = hashlib.sha256(inputs_path.read_bytes()).hexdigest()
        report["cohorts"][name] = cohort
        with (args.output / (name + "_cases.jsonl")).open("w") as output:
            for row in records:
                output.write(json.dumps(row, sort_keys=True) + "\n")
    report["distinct_case_ids"] = len(distinct)
    (args.output / "summary.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    write_report(args.output / "REPORT.md", report)


if __name__ == "__main__":
    main()
