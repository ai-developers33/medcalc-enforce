"""Audit locked benchmark annotations independently of model outputs.

Run from any directory. The bundled 44-row reference excerpt is sufficient.
Pass --official-csv to rebuild that excerpt from the pinned upstream test CSV.
"""
import argparse
import ast
import csv
import hashlib
import json
import math
import re
import sys
from collections import Counter
from decimal import Decimal, localcontext
from pathlib import Path

DEST = Path(__file__).resolve().parent
ROOT = DEST.parents[1]
sys.path.insert(0, str(ROOT))
from medcalc.registry import SPECS, calculate, canonical_value, map_entities

D = Decimal
PRECISION = 42

# Independent factors for units present in the locked gold excerpt; decimal
# conversion constants implement the published project conventions.
UNIT_FACTORS = {
    "age": {"years": "1"}, "creatinine": {"umol/l": ".011312", "mg/dl": "1"},
    "height": {"cm": ".01", "m": "1"}, "weight": {"kg": "1"},
    "sbp": {"mmhg": "1"}, "dbp": {"mmhg": "1"},
    "albumin": {"g/dl": "1", "g/l": ".1"}, "calcium": {"mg/dl": "1", "mmol/l": "4.008"},
    "qt": {"msec": "1"}, "heart_rate": {"beatsperminute": "1"},
    "sodium": {"meq/l": "1", "mmol/l": "1"}, "platelets": {"ul": ".001", "mm^3": ".001"},
    "alt": {"u/l": "1"}, "ast": {"u/l": "1"},
    "glucose": {"mg/dl": "1", "mmol/l": "18.016"}, "bun": {"mg/dl": "1"},
}


def hash_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def write_rows(path, sequence):
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in sequence))


def decimal_inputs(quantities):
    values = {}
    for field, item in quantities.items():
        if field == "sex":
            if item["unit"] != "category" or item["value"] not in ("Female", "Male"):
                raise ValueError("unknown sex coefficient")
            values[field] = item["value"]
        else:
            unit = item["unit"].lower().replace(" ", "").replace("µ", "u").replace("μ", "u")
            values[field] = D(str(item["value"])) * D(UNIT_FACTORS[field][unit])
    return values


def decimal_result(cid, quantities):
    x = decimal_inputs(quantities)
    if cid == "3":
        female = x["sex"] == "Female"
        ratio = x["creatinine"] / D(".7" if female else ".9")
        exponent = D("-.241" if female else "-.302") if ratio < 1 else D("-1.2")
        return D(142) * ratio ** exponent * D(".9938") ** x["age"] * (D("1.012") if female else D(1))
    if cid == "5":
        return x["dbp"] + (x["sbp"] - x["dbp"]) / 3
    if cid == "6":
        return x["weight"] / x["height"] ** 2
    if cid == "7":
        return x["calcium"] + D(".8") * (4 - x["albumin"])
    if cid == "11":
        return x["qt"] * (x["heart_rate"] / 60).sqrt()
    if cid == "19":
        return (x["age"] * x["ast"]) / (x["platelets"] * x["alt"].sqrt())
    if cid == "26":
        return x["sodium"] + D("2.4") * ((x["glucose"] - 100) / 100)
    if cid == "30":
        return 2 * x["sodium"] + x["bun"] / D("2.8") + x["glucose"] / 18
    if cid == "60":
        return (x["height"] * x["weight"] / 36).sqrt()
    raise ValueError("unimplemented independent equation")


def rebuild(path, lock, reference, output=None):
    if hash_file(path) != lock["dataset_hashes"]["test_data.csv"]:
        raise ValueError("Official CSV hash mismatch")
    with path.open(encoding="utf-8", newline="") as file:
        raw = {row["Row Number"]: row for row in csv.DictReader(file)}
    material = []
    for gold in reference:
        source = raw[gold["source_row"]]
        for k, column in (("calculator_id", "Calculator ID"), ("ground_truth", "Ground Truth Answer"),
                          ("lower", "Lower Limit"), ("upper", "Upper Limit")):
            if gold[k] != source[column]:
                raise ValueError(f"Label mismatch for {gold['case_id']}, {column}")
        material.append({"case_id": gold["case_id"], "entities": ast.literal_eval(source["Relevant Entities"]),
                         "upstream_explanation": source["Ground Truth Explanation"]})
    write_rows(output or DEST / "reference_material.jsonl", material)


def bp_unit_check(note, sbp, dbp):
    pair = rf"(?<!\d){sbp:g}\s*/\s*{dbp:g}(?!\d)"
    for match in re.finditer(pair, note):
        units = re.match(r"\s*mm\s*Hg\b", note[match.end():], re.I)
        if units:
            return {"status": "explicit_mmHg_after_reference_pair", "span": [match.start(), match.end()+units.end()]}
    match = re.search(pair, note)
    if match:
        return {"status": "numeric_pair_present_unit_not_printed_after_pair", "span": list(match.span())}
    return {"status": "no_literal_pair"}


def osmolality_text_check(explanation, expected_glucose):
    # Read operands only from the spelled-out numerical substitution.
    match = re.search(r"2\s*\*\s*([\d.]+)\s*\+\s*\(([\d.]+)\s*/\s*2\.8\)\s*\+\s*\(([\d.]+)\s*/\s*18\)\s*=\s*([\d.]+)", explanation)
    if not match:
        return {"status": "equation_text_not_recognized"}
    sodium, bun, glucose, printed = map(D, match.groups())
    shown_result = 2*sodium + bun/D("2.8") + glucose/18
    return {"status": "third_operand_disagrees_with_glucose_annotation" if glucose != expected_glucose else "third_operand_matches",
            "displayed_third_operand": str(glucose), "annotated_glucose": str(expected_glucose),
            "displayed_expression_evaluates_to": str(shown_result), "displayed_final_number": str(printed)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--official-csv", type=Path)
    args = parser.parse_args()
    data = ROOT / "data"
    lock = json.loads((data / "official_lock.json").read_text())
    references = data / "official_reference.jsonl"
    inputs = data / "official_locked_inputs.jsonl"
    if hash_file(references) != lock["reference_sha256"] or hash_file(inputs) != lock["input_sha256"]:
        raise ValueError("Artifact differs from the locked case selection")
    ref_rows = rows(references)
    if args.official_csv:
        rebuild(args.official_csv, lock, ref_rows)
    material_path = DEST / "reference_material.jsonl"
    material = {r["case_id"]: r for r in rows(material_path)}
    notes = {r["case_id"]: r["patient_note"] for r in rows(inputs)}
    if set(material) != set(notes) or set(notes) != {g["case_id"] for g in ref_rows}:
        raise ValueError("Inconsistent selected case identifiers")

    details = []
    with localcontext() as ctx:
        ctx.prec = PRECISION
        for g in ref_rows:
            key, cid = g["case_id"], g["calculator_id"]
            quantities = map_entities(material[key]["entities"])
            if set(quantities) != set(SPECS[cid]["params"]):
                raise ValueError(f"Missing or unexpected field in {key}")
            decimal = decimal_result(cid, quantities)
            canonical = {field: canonical_value(field, **item) for field, item in quantities.items()}
            registered = calculate(cid, canonical)
            lo, answer, hi = map(D, (g["lower"], g["ground_truth"], g["upper"]))
            if not lo <= answer <= hi or not all(v.is_finite() for v in (lo, answer, hi)):
                raise ValueError(f"Invalid primary scoring interval for {key}")
            details.append({
                "case_id": key, "calculator_id": cid, "decimal_reconstruction": str(decimal),
                "registry_reconstruction": registered, "ground_truth": g["ground_truth"],
                "decimal_within_interval": lo <= decimal <= hi, "registry_within_interval": float(lo) <= registered <= float(hi),
                "decimal_within_0_1_percent": abs(decimal-answer) <= abs(answer)*D(".001"),
                "implementations_agree_at_1e_11_relative": math.isclose(float(decimal), registered, rel_tol=1e-11, abs_tol=1e-12),
                "relative_difference_from_gold": float(abs(decimal-answer)/abs(answer)) if answer else None,
            })
            if cid == "5":
                details[-1]["bp_unit_check"] = bp_unit_check(notes[key], canonical["sbp"], canonical["dbp"])
            if cid == "30":
                details[-1]["osmolality_explanation_check"] = osmolality_text_check(material[key]["upstream_explanation"], D(str(canonical["glucose"])))
    write_rows(DEST / "cases.jsonl", details)
    summary = {
        "selected_cases": len(details),
        "selected_calculators": len({r["calculator_id"] for r in details}),
        "decimal_within_interval": sum(r["decimal_within_interval"] for r in details),
        "registry_within_interval": sum(r["registry_within_interval"] for r in details),
        "decimal_within_0_1_percent": sum(r["decimal_within_0_1_percent"] for r in details),
        "arithmetic_implementations_agree": sum(r["implementations_agree_at_1e_11_relative"] for r in details),
        "largest_relative_difference_from_gold": max(r["relative_difference_from_gold"] for r in details),
        "bp_source_unit_status": dict(Counter(r["bp_unit_check"]["status"] for r in details if "bp_unit_check" in r)),
        "osmolality_explanation_status": dict(Counter(r["osmolality_explanation_check"]["status"] for r in details if "osmolality_explanation_check" in r)),
        "locked_reference_sha256": hash_file(references), "upstream_excerpt_sha256": hash_file(material_path),
        "decimal_precision": PRECISION,
    }
    (DEST / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
