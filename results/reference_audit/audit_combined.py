"""Rebuild an output-blind arithmetic audit for both frozen official cohorts."""
import argparse
import json
import math
from collections import Counter
from decimal import localcontext
from pathlib import Path

from audit import (
    D, DEST, ROOT, PRECISION, bp_unit_check, calculate, canonical_value, decimal_inputs,
    decimal_result, hash_file, map_entities, osmolality_text_check, rebuild, rows, write_rows,
)
from medcalc.registry import CANONICAL, SPECS


def process(cohort, paths, csv_path):
    lock_path, inputs_path, references_path, material_path = paths
    lock = json.loads(lock_path.read_text())
    if hash_file(inputs_path) != lock["input_sha256"] or hash_file(references_path) != lock["reference_sha256"]:
        raise ValueError(f"Locked records changed for {cohort}")
    gold = rows(references_path)
    if csv_path:
        rebuild(csv_path, lock, gold, output=material_path)
    material = {r["case_id"]: r for r in rows(material_path)}
    notes = {r["case_id"]: r["patient_note"] for r in rows(inputs_path)}
    if len(gold) != lock["selected"] or set(material) != set(notes) or set(notes) != {g["case_id"] for g in gold}:
        raise ValueError(f"Inconsistent {cohort} set")
    details = []
    for r in gold:
        cid, key = r["calculator_id"], r["case_id"]
        detail = {
            "case_id": key, "source_row": r["source_row"], "cohort": cohort, "calculator_id": cid,
            "ground_truth": r["ground_truth"], "lower": r["lower"], "upper": r["upper"],
            "required_fields": list(SPECS[cid]["params"]),
        }
        details.append(detail)
        gold_lo, answer, gold_hi = map(D, (r["lower"], r["ground_truth"], r["upper"]))
        if not gold_lo <= answer <= gold_hi:
            raise ValueError(f"Invalid scoring interval for {key}")
        try:
            quantities = map_entities(material[key]["entities"])
            if set(quantities) != set(SPECS[cid]["params"]):
                raise ValueError("incomplete gold arguments")
            norm = decimal_inputs(quantities)
            expected = decimal_result(cid, quantities)
            detail["canonical_inputs"] = {name: float(v) if isinstance(v,D) else v for name,v in norm.items()}
            detail["canonical_units"] = {name: CANONICAL[name] for name in norm}
            detail["annotated_quantities"] = quantities
            detail["reference_fields_scorable"] = True
            detail["decimal_reconstruction"] = str(expected)
            detail["decimal_within_interval"] = gold_lo <= expected <= gold_hi
            detail["relative_difference_from_gold"] = float(abs((expected-answer)/answer)) if answer else None
            detail["decimal_within_0_1_percent"] = abs(expected-answer) <= abs(answer)*D(".001")
        except (KeyError, TypeError, ValueError, ArithmeticError) as e:
            detail["reference_fields_scorable"] = False
            detail["reference_fields_reason"] = str(e)
            continue
        try:
            primitive = {name: canonical_value(name, **quantity) for name, quantity in quantities.items()}
            numeric = calculate(cid, primitive)
            detail["registry_reconstruction"] = numeric
            detail["registry_within_interval"] = float(gold_lo) <= numeric <= float(gold_hi)
            detail["implementations_agree_at_1e_11_relative"] = math.isclose(float(expected),numeric, rel_tol=1e-11,abs_tol=1e-12)
        except (KeyError, TypeError, ValueError, ArithmeticError) as e:
            detail["registry_unscorable"] = str(e)
        if cid == "5":
            detail["bp_unit_check"] = bp_unit_check(notes[key], float(norm["sbp"]), float(norm["dbp"]))
        if cid == "30":
            detail["osmolality_explanation_check"] = osmolality_text_check(material[key]["upstream_explanation"], norm["glucose"])
    return details


def summarize(details):
    return {
        "cases": len(details), "source_fields_scorable": sum(r["reference_fields_scorable"] for r in details),
        "field_units_covered": sum(len(r.get("canonical_units",{})) for r in details),
        "decimal_within_primary_interval": sum(bool(r.get("decimal_within_interval")) for r in details),
        "decimal_within_0_1_percent": sum(bool(r.get("decimal_within_0_1_percent")) for r in details),
        "registry_checks_applicable": sum("registry_reconstruction" in r for r in details),
        "registry_within_primary_interval": sum(bool(r.get("registry_within_interval")) for r in details),
        "registry_agrees_with_decimal": sum(bool(r.get("implementations_agree_at_1e_11_relative")) for r in details),
        "max_relative_difference_from_gold": max(r["relative_difference_from_gold"] for r in details if r.get("relative_difference_from_gold") is not None),
        "reference_arithmetic_unscorable": {r["case_id"]:r["reference_fields_reason"] for r in details if not r["reference_fields_scorable"]},
        "registry_unscorable": {r["case_id"]:r["registry_unscorable"] for r in details if "registry_unscorable" in r},
        "decimal_outside_interval": [r["case_id"] for r in details if r.get("decimal_within_interval") is False],
        "bp_unit_check_counts": dict(Counter(r["bp_unit_check"]["status"] for r in details if "bp_unit_check" in r)),
        "osmolality_explanation_counts": dict(Counter(r["osmolality_explanation_check"]["status"] for r in details if "osmolality_explanation_check" in r)),
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--official-csv", type=Path)
    args = p.parse_args()
    data = ROOT / "data"
    ext = data / "official_extension"
    if json.loads((ext / "lock.json").read_text())["first_cohort_lock_sha256"] != hash_file(data/"official_lock.json"):
        raise ValueError("First cohort selection differs from extension lock")
    cohorts = {
        "first": (data/"official_lock.json", data/"official_locked_inputs.jsonl", data/"official_reference.jsonl", DEST/"reference_material.jsonl"),
        "extension": (ext/"lock.json", ext/"inputs.jsonl", ext/"references.jsonl", DEST/"extension_reference_material.jsonl"),
    }
    with localcontext() as ctx:
        ctx.prec=PRECISION
        parsed = {name: process(name,paths,args.official_csv) for name,paths in cohorts.items()}
    cases=[r for batch in parsed.values() for r in batch]
    if len({r["case_id"] for r in cases})!=len(cases):
        raise ValueError("Duplicate across audited cohorts")
    out=DEST/"canonical_reference_all.jsonl"
    write_rows(out,cases)
    summary={"by_cohort":{name:summarize(details) for name,details in parsed.items()},
             "combined":summarize(cases), "canonical_reference_all_sha256":hash_file(out)}
    (DEST/"combined_summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    print(json.dumps(summary["combined"],indent=2))


if __name__=="__main__":
    main()
