"""Audit both locked official input cohorts against pinned benchmark source text."""

import argparse
from collections import Counter, defaultdict
import csv
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re

from official_study import digest, source_keys


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "results" / "template_audit"
NUMERIC = re.compile(r"[+\-−]?\d+(?:[,\u202f]\d{3})*(?:\.\d+)?(?:[Ee][+\-]?\d+)?")
TOKENS = re.compile(r"⟨n⟩|[^\W\d_]+|\d+", re.UNICODE)
THRESHOLDS = (0.70, 0.80, 0.90)


def normalized(text):
    return " ".join(text.lower().split())


def masked(text):
    return NUMERIC.sub("⟨n⟩", normalized(text))


def fingerprint(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def shingles(text):
    words = TOKENS.findall(masked(text))
    return {tuple(words[i:i+5]) for i in range(len(words)-4)}


@dataclass(frozen=True)
class Entry:
    row: str
    cid: str
    note_type: str
    note_id: str
    source: str
    note: str
    question: str


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as file:
        return [
            Entry(row["Row Number"], row["Calculator ID"], row["Note Type"],
                  row["Note ID"], source_keys(row)[0], row["Patient Note"], row["Question"])
            for row in csv.DictReader(file)
        ]


def keys(entry):
    return {
        "source_id": entry.source,
        "exact_note": normalized(entry.note),
        "masked_note": masked(entry.note),
        "exact_question": normalized(entry.question),
        "masked_question": masked(entry.question),
    }


def make_queries(first, second, test_rows):
    result = []
    heldout = set()
    for cohort, inputs, lock in [("first", *first), ("extension", *second)]:
        if digest(inputs) != lock["input_sha256"]:
            raise ValueError("Cohort input digest does not match lock")
        cohort_rows = [json.loads(line) for line in inputs.read_text().splitlines()]
        if len(cohort_rows) != lock["selected"]:
            raise ValueError("Unexpected cohort size")
        for row in cohort_rows:
            entry = test_rows[row["source_row"]]
            if (entry.note, entry.question, entry.source, entry.note_type, entry.note_id) != (
                row["patient_note"], row["question"], row["group_id"], row["note_type"], row["note_id"]
            ):
                raise ValueError("Cohort text/metadata differs from pinned raw official test")
            if row["case_id"] in heldout:
                raise ValueError("Repeated case across cohorts")
            heldout.add(row["case_id"])
            result.append((cohort,row["case_id"],entry))
    return result


def index_matches(train, queries):
    index = {name: defaultdict(list) for name in keys(queries[0][2])}
    for i, entry in enumerate(train):
        for name, val in keys(entry).items():
            index[name][val].append(i)
    # Restrict postings to queried shingles. All train/one-shot rows compete.
    query_shingles = [shingles(entry.note) for _, _, entry in queries]
    queried = set().union(*query_shingles)
    postings = defaultdict(list)
    sizes = []
    for i, entry in enumerate(train):
        grams = shingles(entry.note)
        sizes.append(len(grams))
        for gram in grams & queried:
            postings[gram].append(i)
    results = []
    for q, (_, _, entry) in enumerate(queries):
        matches = {k: index[k].get(v, []) for k, v in keys(entry).items()}
        grams = query_shingles[q]
        shared = Counter(i for gram in grams for i in postings[gram])
        scores = {
            i: count / (len(grams) + sizes[i] - count) for i, count in shared.items()
        }
        ordered = sorted(scores, key=lambda i: (-scores[i], int(train[i].row)))
        best = ordered[0] if ordered else None
        near = {}
        for cutoff in THRESHOLDS:
            near[f"{cutoff:.2f}"] = sum(scores[i] >= cutoff for i in ordered)
        results.append({
            "match_counts": {k: len(v) for k, v in matches.items()},
            "first_matching_rows": {k: [train[i].row for i in v[:3]] for k, v in matches.items()},
            "masked_note_5gram_count": len(grams),
            "similarity_available": bool(grams),
            "high_similarity_row_counts": near,
            "nearest": None if best is None else {
                "row": train[best].row, "calculator_id": train[best].cid,
                "note_type": train[best].note_type, "note_id": train[best].note_id,
                "distinct_shingles": sizes[best], "shared_shingles": shared[best],
                "jaccard": scores[best],
            },
        })
    return results


def group_rows(records, fields):
    groups = defaultdict(list)
    for record in records:
        groups[tuple(record[f] for f in fields)].append(record)
    output = []
    for key, group in sorted(groups.items()):
        count = Counter({k: 0 for k in group[0]["flags"]})
        for row in group:
            count.update({k: int(v) for k, v in row["flags"].items()})
        output.append({**dict(zip(fields,key)), "cases": len(group), **dict(count)})
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=ROOT / "data" / "raw")
    args = parser.parse_args()
    paths = {"test_data.csv": args.raw/"test_data.csv",
             "train_data.csv": args.raw/"verified/train_data.csv",
             "one_shot_data.csv": args.raw/"verified/one_shot_data.csv"}
    lock = json.loads((ROOT/"data/official_lock.json").read_text())
    extension = json.loads((ROOT/"data/official_extension/lock.json").read_text())
    raw_hashes = {name: digest(p) for name,p in paths.items()}
    if raw_hashes != lock["dataset_hashes"] or raw_hashes != extension["dataset_hashes"]:
        raise ValueError("Source digests do not match both study locks")
    queries = make_queries(
        (ROOT/"data/official_locked_inputs.jsonl",lock),
        (ROOT/"data/official_extension/inputs.jsonl",extension),
        {entry.row: entry for entry in read_csv(paths["test_data.csv"])},
    )
    rows = []
    for cohort, case_id, entry in queries:
        rows.append({
            "cohort": cohort, "case_id": case_id, "calculator_id": entry.cid,
            "note_type": entry.note_type, "source_key": entry.source,
            "normalized_note_sha256": fingerprint(normalized(entry.note)),
            "masked_note_sha256": fingerprint(masked(entry.note)),
            "masked_question_sha256": fingerprint(masked(entry.question)),
            "matches": {},
        })
    sizes = {}
    for split in ["train_data.csv","one_shot_data.csv"]:
        reference = read_csv(paths[split])
        sizes[split] = len(reference)
        for record,evidence in zip(rows,index_matches(reference,queries)):
            record["matches"][split] = evidence
    for record in rows:
        evidence = record["matches"].values()
        flags = {k: any(e["match_counts"][k] > 0 for e in evidence)
                 for k in ["source_id","exact_note","masked_note","exact_question","masked_question"]}
        for cutoff in THRESHOLDS:
            flags[f"masked_5gram_jaccard_at_least_{cutoff:.2f}"] = any(
                e["high_similarity_row_counts"][f"{cutoff:.2f}"] > 0 for e in evidence)
        record["flags"] = flags
    summary = {
        "source_sha256": raw_hashes, "train_and_one_shot_rows": sizes,
        "cohort_sha256": {"first": lock["input_sha256"], "extension": extension["input_sha256"]},
        "all_cases": group_rows(rows,[])[0], "by_cohort": group_rows(rows,["cohort"]),
        "distinct_masked_questions": len({row["masked_question_sha256"] for row in rows}),
        "distinct_matching_masked_notes": len({row["masked_note_sha256"] for row in rows if row["flags"]["masked_note"]}),
        "by_note_type": group_rows(rows,["note_type"]),
        "by_calculator": group_rows(rows,["calculator_id"]),
        "by_cohort_calculator_note_type": group_rows(rows,["cohort","calculator_id","note_type"]),
        "per_reference_split": {
            split: {
                match: sum(row["matches"][split]["match_counts"][match]>0 for row in rows)
                for match in ["source_id","exact_note","masked_note","exact_question","masked_question"]
            } for split in sizes
        },
    }
    OUT.mkdir(exist_ok=True, parents=True)
    (OUT/"case_flags.jsonl").write_text("".join(json.dumps(row,ensure_ascii=False)+"\n" for row in rows))
    template_groups = defaultdict(list)
    for row in rows:
        if row["flags"]["masked_note"]:
            template_groups[row["masked_note_sha256"]].append(row["case_id"])
    (OUT/"matched_template_groups.json").write_text(json.dumps(template_groups,indent=2)+"\n")
    (OUT/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    print(json.dumps({k:summary[k] for k in ["all_cases","by_cohort","by_note_type","per_reference_split"]},indent=2))


if __name__ == "__main__":
    main()
