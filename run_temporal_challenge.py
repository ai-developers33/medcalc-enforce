"""Run the controlled timepoint challenge, independently of gold-free execution."""

import collections
import hashlib
import json
import math
from pathlib import Path

from medcalc.enforcement import Rejected
from medcalc.registry import SPECS
from medcalc.source_repair import make_source_packet, repair_call
from medcalc.temporal_guard import execute_at_timepoint, target_lines


ROOT = Path(__file__).resolve().parent
FIXTURES = ROOT / "data" / "temporal_challenge.json"
OUTPUT = ROOT / "results" / "temporal_challenge"


def matches(actual, expected):
    if isinstance(expected, str):
        return actual == expected
    return math.isclose(actual, expected, rel_tol=1e-6, abs_tol=1e-8)


def score(output, case):
    expected = case["expected"]
    if not output["released"]:
        return "appropriate_abstention" if expected is None else "answerable_blocked"
    if expected is None:
        return "unsupported_release"
    values = output["canonical_inputs"]
    correct_inputs = values.keys() == expected["inputs"].keys() and all(
        matches(values[key], value) for key, value in expected["inputs"].items()
    )
    if correct_inputs and matches(output["result"], expected["answer"]):
        return "matching_release"
    return "nonmatching_release"


def run_case(case):
    cid = case["calculator"]
    call = {
        "calculator_id": cid, "formula_version": SPECS[cid]["version"],
        "arguments": {key: {"value": pair[0], "unit": pair[1], "evidence_id": "proposal"}
                      for key, pair in case["proposal"].items()},
    }
    note = case["note"]
    expected_digest = hashlib.sha256(note.encode("utf-8")).hexdigest()
    record = {"id": case["id"], "group": case["group"], "answerable": case["expected"] is not None}
    for method in ["frozen_source_repair", "explicit_timepoint_guard"]:
        try:
            if method == "frozen_source_repair":
                decision = repair_call(call, make_source_packet(cid, note), note)
            else:
                decision = execute_at_timepoint(call, note, phase=case["phase"], expected_note_sha256=expected_digest)
        except Rejected as error:
            decision = {"released": False, "reason": str(error)}
        record[method] = {"score": score(decision, case), "decision": decision}
    return record


def main():
    cases = json.loads(FIXTURES.read_text())
    assert len(cases) == len({case["id"] for case in cases})
    results = [run_case(case) for case in cases]
    summary = {
        "source": "Constructed sectioned-note fixtures and negative/control probes",
        "fixture_sha256": hashlib.sha256(FIXTURES.read_bytes()).hexdigest(),
        "cases": len(cases), "distinct_notes": len({case["note"] for case in cases}),
        "calculators": sorted({case["calculator"] for case in cases}),
        "answerable": sum(r["answerable"] for r in results),
        "methods": {}, "llm_calls": 0,
        "scope": "The author of the guard wrote the explicit fixture oracles; these related scenarios test a contract, not clinical accuracy or independent adjudication.",
    }
    for method in ["frozen_source_repair", "explicit_timepoint_guard"]:
        summary["methods"][method] = dict(collections.Counter(r[method]["score"] for r in results))
    input_path = ROOT / "data" / "binding_validation_inputs.jsonl"
    notes = [json.loads(line) for line in input_path.read_text().splitlines()]
    requests = [r for r in notes if "first admitted" in r["question"].casefold()]
    present = 0
    for row in requests:
        try:
            target_lines(row["patient_note"], "admission")
            present += 1
        except Rejected:
            pass
    summary["previous_validation_input_compatibility"] = {
        "all_notes": len(notes), "explicit_first_admitted_requests": len(requests),
        "unique_supported_admission_section_among_requested": present,
        "scope": "Input-format applicability only, before executing any calculator. Remaining questions do not expressly request the first admission.",
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for name, obj in [("cases.json", results), ("summary.json", summary)]:
        (OUTPUT / name).write_text(json.dumps(obj, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
