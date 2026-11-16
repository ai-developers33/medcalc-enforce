"""Replay MedCalc-Pro's upstream first-pass validator and scoring components.

Usage: python results/code_review/compare_published_component.py --upstream CHECKOUT --model MODEL_DIR
Only the exact upstream source and calculator config hashes listed in the manifest are accepted.
"""
import argparse
import hashlib
import importlib.util
import json
import math
import sys
import types
from collections import Counter
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
sys.path.insert(0, str(PROJECT))
from medcalc.release_policy import execute_reviewed

# Chosen by comparing published calculator definitions and variable names.
SCALES = {
    "3": "ckd_epi_equations_for_glomerular_filtration_rate",
    "5": "mean_arterial_pressure_map",
    "6": "body_mass_index_bmi",
    "7": "calcium_correction_for_hypoalbuminemia",
    "19": "fibrosis_4_fib_4_index_for_liver_fibrosis",
    "26": "sodium_correction_for_hyperglycemia",
    "30": "serum_osmolality",
    "39": "anion_gap",
    "60": "body_surface_area_calculator",
}
FIELDS = {
    "albumin": "Albumin", "calcium": "Calcium", "sbp": "Systolic Blood Pressure",
    "dbp": "Diastolic Blood Pressure", "ast": "Aspartate aminotransferase",
    "alt": "Alanine aminotransferase", "platelets": "Platelet count",
    "sodium": "Sodium", "glucose": "Glucose", "bun": "Blood Urea Nitrogen (BUN)",
    "chloride": "Chloride", "bicarbonate": "Bicarbonate",
}


class ModelUnavailable:
    def __init__(self, model_id):
        self.attempts = 0

    def generate(self, prompt):
        self.attempts += 1
        raise RuntimeError("Fresh model inference would be required")


def upstream_agent(source):
    digests = json.loads((HERE / "upstream_hashes.json").read_text())["sha256"]
    for name, expected in digests.items():
        if hashlib.sha256((source / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Upstream component changed: {name}")
    # The author's validator uses its own code and its own schemas. Only model
    # construction, logging of model traces and prompt-container construction
    # are disconnected. Any attempted LLM conversion is counted and withheld.
    stubs = {key: types.ModuleType(key) for key in ("core", "core.Config", "core.Models", "core.Prompts", "core.VerboseLog")}
    stubs["core.Config"].args = types.SimpleNamespace(llm_model="unavailable", ablate_hardcheck=False)
    stubs["core.Models"].LLMs = ModelUnavailable
    class Prompts:
        unit_conversion_prompt = "Offline component replay"
    stubs["core.Prompts"].Prompts = Prompts
    stubs["core"].VerboseLog = stubs["core.VerboseLog"]
    spec = importlib.util.spec_from_file_location("published_medcalc_pro", source / "core/Execution.py")
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
        agent = module.ExecutionAgent()
    return agent


def published_component(trace, source, agent):
    selected = trace.get("selected_calculator_id")
    if selected not in SCALES or "baseline_call" not in trace:
        return None, "missing_call_or_unmapped_selection"
    scale = SCALES[selected]
    folder = source / "toolconfig" / scale
    tool = {"id": scale, "entry_point": "calculate_" + scale, "paths": {k: str(folder / path)
            for k, path in [("config", "config.json"), ("score", "score.py")]}}
    raw = {FIELDS.get(field, field): {"value": value["value"], "unit": value["unit"],
           "evidence": trace["baseline_quotes"][field]} for field, value in trace["baseline_call"]["arguments"].items()}
    before = agent.llm.attempts
    valid, _, flat, _, _ = agent._validate_parameters(tool, raw)
    if agent.llm.attempts != before:
        return None, "requires_new_unit_conversion_generation"
    if not valid:
        return None, "validator_withheld"
    try:
        result = agent._execute_score_code(tool, flat)["score_raw"]
    except (ArithmeticError, TypeError, ValueError, KeyError) as exc:
        return None, "upstream_exception_" + type(exc).__name__
    if isinstance(result, bool) or not isinstance(result, (float, int)) or not math.isfinite(result):
        return None, "no_numeric_score"
    return result, "returned"


def read_cases(path):
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    by_id = {row["case_id"]: row for row in rows}
    assert len(rows) == len(by_id)
    return by_id


def outcome(value, selected, ref):
    if value is None:
        return "unanswered"
    return "matches" if selected == ref["calculator_id"] and float(ref["lower"]) <= value <= float(ref["upper"]) else "disagrees"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--upstream", type=Path, required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--cases-file", type=Path)
    p.add_argument("--panel", choices=["primary", "extension"], default="primary")
    args = p.parse_args()
    agent = upstream_agent(args.upstream)
    if args.panel == "primary":
        inputs = read_cases(PROJECT / "data/official_locked_inputs.jsonl")
        refs = read_cases(PROJECT / "data/official_reference.jsonl")
    else:
        inputs = read_cases(PROJECT / "data/official_extension/inputs.jsonl")
        refs = read_cases(PROJECT / "data/official_extension/references.jsonl")
    path = args.cases_file or PROJECT / "results/official" / args.model / "cases.jsonl"
    traces = read_cases(path)
    if traces.keys() != refs.keys() or refs.keys() != inputs.keys():
        raise ValueError("Scoring requires the complete locked panel")
    records, counts = [], {name: Counter() for name in ("published_first_pass", "unit_domain", "reviewed")}
    for cid, ref in refs.items():
        if ref["calculator_id"] not in SCALES:
            continue
        t, x = traces[cid], inputs[cid]
        new_score, reason = published_component(t, args.upstream, agent)
        reviewed = execute_reviewed(x["question"], x["patient_note"], t.get("baseline_call"))
        level_two = t.get("baseline_gates", {}).get("L2_unit_domain", {})
        row = {"case_id": cid, "expected_tool": ref["calculator_id"], "selected": t.get("selected_calculator_id"),
               "first_pass_status": reason, "first_pass_score": new_score}
        for name, value, selected in (("published_first_pass", new_score,t.get("selected_calculator_id")),
                                     ("unit_domain",level_two.get("result"),t.get("selected_calculator_id")),
                                     ("reviewed",reviewed.get("result"),reviewed.get("calculator_id"))):
            row[name] = outcome(value, selected, ref)
            counts[name][row[name]] += 1
        records.append(row)
    summary = {"upstream_commit": "751a514644d22bc6f7066087205fbbb61b7b40f5", "model": args.model,
               "official_panel_cases": len(refs), "formula_matched_subset": len(records),
               "mapped_calculators": SCALES, "status": dict(Counter(r["first_pass_status"] for r in records)),
               "outcomes": {name: dict(values) for name, values in counts.items()}, "cases": records}
    common = [r for r in records if r["published_first_pass"] != "unanswered" and r["reviewed"] != "unanswered"]
    summary["panel"] = args.panel
    summary["both_returned"] = {"cases": len(common), **{name: sum(r[name]=="matches" for r in common) for name in ("published_first_pass", "reviewed")}}
    (HERE / f"published_component_{args.panel}_{args.model}.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({k:v for k,v in summary.items() if k not in ("mapped_calculators","cases")}, indent=2))


if __name__ == "__main__":
    main()
