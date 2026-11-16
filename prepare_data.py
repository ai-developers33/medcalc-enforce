"""Audit pinned data and choose development rows, without selecting on accuracy."""

import ast
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from medcalc.registry import SPECS, map_entities, canonical_value

ROOT = Path(__file__).resolve().parent
SEED = 731

def text_key(text):
    return hashlib.sha256(" ".join(text.lower().split()).encode()).hexdigest()

def public_id(value):
    match = re.search(r"pmc-\d+-\d+", str(value), re.I)
    return match.group().lower() if match else None

def load_csv(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))

def main():
    raw = ROOT / "data/raw"
    train = load_csv(raw / "verified/train_data.csv")
    test = load_csv(raw / "test_data.csv")
    shots = load_csv(raw / "verified/one_shot_data.csv")
    test_text = {text_key(r["Patient Note"]) for r in test}
    test_public = {p for r in test if (p := public_id(r["Note ID"]))}
    train_text = {text_key(r["Patient Note"]) for r in train}
    train_public = {p for r in train if (p := public_id(r["Note ID"]))}
    audit = {"verified_version": "v1.0.8", "verified_commit": "801592132bfd833f049b517a4e013e00a5fc40fa",
             "train_rows": len(train), "test_rows": len(test), "one_shot_rows": len(shots),
             "test_calculators": len({r["Calculator ID"] for r in test}),
             "test_note_types": dict(Counter(r["Note Type"] for r in test)),
             "train_test_shared_exact_normalized_notes": len(train_text & test_text),
             "train_test_shared_public_case_ids": len(train_public & test_public),
             "test_unique_normalized_notes": len(test_text),
             "overlap_scope": "Exact normalized text and explicit PMC patient-case identifiers only; no near-duplicate or patient identity guarantee."}
    secondary = {}
    for split in ("simple", "nest", "multi"):
        path = raw / "medcalc_pro" / f"{split}.json"
        if path.exists():
            data = json.loads(path.read_text())
            text_hits = sum(text_key(r.get("patient_case", r.get("case", ""))) in test_text for r in data)
            id_hits = sum(public_id(r.get("id")) in test_public for r in data if public_id(r.get("id")))
            secondary[split] = {"rows": len(data), "exact_note_overlap_rows_with_verified_test": text_hits,
                                "public_case_id_overlap_rows_with_verified_test": id_hits,
                                "exact_note_overlap_rows_with_verified_train": sum(text_key(r.get("patient_case", "")) in train_text for r in data),
                                "public_case_id_overlap_rows_with_verified_train": sum(public_id(r.get("id")) in train_public for r in data if public_id(r.get("id")))}
    audit["medcalc_pro_commit"] = "751a514644d22bc6f7066087205fbbb61b7b40f5"
    audit["medcalc_pro"] = secondary
    # Eligibility is decided before looking at the reference answer.
    pools = defaultdict(list)
    exclusions = []
    for row in train:
        cid = row["Calculator ID"]
        if cid not in SPECS: continue
        reason = None
        group = text_key(row["Patient Note"])
        pid = public_id(row["Note ID"])
        if group in test_text or (pid and pid in test_public): reason = "shared_with_official_test"
        try:
            q = map_entities(ast.literal_eval(row["Relevant Entities"]))
            if set(q) != set(SPECS[cid]["params"]): raise ValueError("unexpected parameter set")
            canonical = {k: canonical_value(k, **v) for k, v in q.items()}
            if cid == "3" and canonical["age"] < 18: reason = reason or "outside_adult_CKD_contract"
        except (ValueError, TypeError, KeyError, SyntaxError) as e:
            reason = reason or f"unsupported_annotation:{e}"
        if reason:
            exclusions.append({"row": row["Row Number"], "calculator": cid, "reason": reason})
            continue
        record = {"source_row": row["Row Number"], "source_note_id": row["Note ID"],
                  "source_note_type": row["Note Type"], "note_hash": group,
                  "group_id": pid or group, "calculator_id": cid,
                  "quantities": q, "ground_truth": row["Ground Truth Answer"],
                  "lower": row["Lower Limit"], "upper": row["Upper Limit"]}
        pools[cid].append(record)
    selected = []
    for cid in sorted(SPECS, key=int):
        ordered = sorted(pools[cid], key=lambda r: hashlib.sha256(f'{SEED}|{cid}|{r["source_row"]}'.encode()).hexdigest())
        seen = set()
        for row in ordered:
            if row["group_id"] in seen: continue
            seen.add(row["group_id"])
            selected.append(row)
            if len(seen) == 20: break
        if len(seen) < 20: raise RuntimeError(f"insufficient eligible rows for {cid}")
    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "data/pilot_rows.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False)+"\n" for r in selected))
    audit["development_selection"] = {"seed": SEED, "rows": len(selected), "source": "official train only",
                                      "rows_per_calculator": dict(Counter(r["calculator_id"] for r in selected)),
                                      "unique_source_groups": len({r["group_id"] for r in selected}),
                                      "eligible_pool_sizes": {k:len(v) for k,v in pools.items()},
                                      "excluded_rows": len(exclusions), "exclusion_reasons": dict(Counter(x["reason"] for x in exclusions)),
                                      "selected_on_output_accuracy": False}
    (ROOT / "results/dataset_audit.json").write_text(json.dumps(audit, indent=2)+"\n")
    (ROOT / "results/development_exclusions.json").write_text(json.dumps(exclusions, indent=2)+"\n")
    print(json.dumps(audit, indent=2))

if __name__ == "__main__": main()
