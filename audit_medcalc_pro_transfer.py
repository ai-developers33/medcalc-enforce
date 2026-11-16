"""Pre-execution eligibility audit of the pinned MedCalc-Pro Simple split.

Outputs contain aggregates, row hashes, and overlap flags. They contain no
clinical source text, benchmark questions, ground truth, or model generations.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path

from medcalc.source_fallback import select_calculator
from official_study import source_keys


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "results/external_transfer"
POLICY = {
    "3": ("CKD-EPI GFR (2021)", "CKD-EPI 2021 creatinine-only, normalized to 1.73 m²"),
    "5": ("Mean Arterial Pressure", "(SBP + 2 DBP)/3, mmHg"),
    "6": ("Body Mass Index", "weight in kg divided by squared height in m"),
    "7": ("Calcium Correction", "total calcium in mg/dL, albumin in g/dL, coefficient 0.8 and reference albumin 4"),
    "11": ("QTc (Bazett)", "Bazett correction, frozen output ms; these benchmark queries explicitly request seconds"),
    "19": ("FIB-4", "age times AST divided by platelets times square root of ALT"),
    "26": ("Sodium Correction", "Hillier 2.4 coefficient, mEq/L"),
    "30": ("Serum Osmolality", "2 Na + BUN/2.8 + glucose/18 after unit normalization"),
    "39": ("Anion Gap", "sodium minus chloride and bicarbonate, potassium excluded"),
    "60": ("BSA", "Mosteller square-root formula, m²"),
}


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def file_hash(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle,"sha256").hexdigest()


def by_csv(paths):
    sources, texts = set(), set()
    for path in paths:
        with path.open(encoding="utf-8",newline="") as file:
            for row in csv.DictReader(file):
                source, text = source_keys(row)
                sources.add(source)
                texts.add(text)
    return sources, texts


def checked_study_inputs():
    paths = [
        (ROOT/"data/official_locked_inputs.jsonl", ROOT/"data/official_lock.json"),
        (ROOT/"data/official_extension/inputs.jsonl", ROOT/"data/official_extension/lock.json"),
    ]
    sources, texts = set(), set()
    for inputs, lock in paths:
        if file_hash(inputs) != json.loads(lock.read_text())["input_sha256"]:
            raise ValueError("Study cohort changed")
        for line in inputs.read_text().splitlines():
            row = json.loads(line)
            sources.add(row["group_id"])
            texts.add(sha(" ".join(row["patient_note"].lower().split())))
    return sources, texts


def summarize(rows):
    flags = ["matched_tool_metadata","query_resolved_to_listed_calculator","explicit_admission_request",
             "formula_unit_mismatch","full_official_test_shared_source","full_official_test_shared_text",
             "training_one_shot_overlap","locked_official_cohort_overlap","eligible"]
    return {"rows":len(rows), **{key:sum(row[key] for row in rows) for key in flags}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw",type=Path,default=ROOT/"data/raw")
    args = parser.parse_args()
    manifest = json.loads((ROOT/"data/download_manifest.json").read_text())
    study_lock = json.loads((ROOT/"data/official_lock.json").read_text())
    source = args.raw/"medcalc_pro/simple.json"
    source_hash = file_hash(source)
    expected = next(row["sha256"] for row in manifest if row["dataset"]=="medcalc_pro" and row["file"]=="simple.json")
    if source_hash != expected:
        raise ValueError("Unexpected external source version")
    files = [args.raw/"verified/train_data.csv",args.raw/"verified/one_shot_data.csv",args.raw/"test_data.csv"]
    for path in files:
        if study_lock["dataset_hashes"][path.name] != file_hash(path):
            raise ValueError("Unexpected Verified source version")
    train_ids,train_text = by_csv(files[:2])
    test_ids,test_text = by_csv(files[2:])
    official_ids,official_text = checked_study_inputs()
    raw_rows = json.loads(source.read_text())
    records = []
    for row in raw_rows:
        cid = str(row["medrac_calculator_id"])
        if cid not in POLICY:
            continue
        query = row["doctor_query"]
        source_id, note_hash = source_keys({"Note ID":row["id"], "Calculator ID":cid,
            "Note Type":row["meta"]["note_type"], "Patient Note":row["patient_case"]})
        train_hit = source_id in train_ids or note_hash in train_text
        prior_hit = source_id in official_ids or note_hash in official_text
        metadata_match = row["meta"]["medrac_tool_name"] == POLICY[cid][0]
        unit_mismatch = cid == "11" and "seconds" in query.casefold()
        try:
            resolved = select_calculator(query) == cid
        except ValueError:
            resolved = False
        records.append({
            "row_key_sha256": sha(f"{cid}|{row['medrac_row']}|{row['id']}"),
            "calculator_id":cid, "source_key_sha256":sha(source_id),
            "normalized_note_sha256":note_hash, "matched_tool_metadata":metadata_match,
            "query_resolved_to_listed_calculator":resolved,
            "explicit_admission_request":"first admitted" in query.casefold(),
            "formula_unit_mismatch":unit_mismatch,
            "full_official_test_shared_source":source_id in test_ids,
            "full_official_test_shared_text":note_hash in test_text,
            "training_one_shot_overlap":train_hit, "locked_official_cohort_overlap":prior_hit,
            "eligible":metadata_match and not unit_mismatch and not train_hit and not prior_hit,
        })
    totals = summarize(records)
    summary = {
        "pinned_external_sha256":source_hash,"total_rows":len(raw_rows),
        "mapped_calculator_ids":list(POLICY),"mapping_and_formula_policy":POLICY,
        "outside_supported_calculator_ids":len(raw_rows)-len(records),
        "mapped_rows":totals,"by_calculator":{c:summarize([r for r in records if r["calculator_id"]==c]) for c in POLICY},
        "performance_scored_cases":0,"model_calls":0,
        "eligibility_policy":"Map IDs and metadata tool names, require compatible output units, exclude rows matching a source key or normalized note in train/one-shot or either locked official cohort. Query intent resolution is descriptive and does not filter cases.",
        "design":"Eligibility-only audit; the frozen ten calculator specifications are shown, formula choice within generic prompts can be ambiguous, and source independence is evaluated before proposing numerical scoring.",
    }
    if totals["eligible"]:
        raise ValueError("Positive eligibility requires a separate prespecified scoring run")
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    (OUT/"exclusion_flags.jsonl").write_text("".join(json.dumps(r)+"\n" for r in records))
    print(json.dumps(totals,indent=2))


if __name__ == "__main__":
    main()
