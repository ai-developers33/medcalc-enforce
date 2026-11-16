"""Measure local policy overhead on recorded proposals. No model inference is timed."""
import argparse
import hashlib
import json
import platform
import random
import statistics
import tempfile
import time
from pathlib import Path

from medcalc.checked_store import execute_and_publish
from medcalc.commit_store import Encounter, connect, initialize, put_note
from medcalc.release_policy import execute_reviewed
from medcalc.registry import calculate
from medcalc.enforcement import POLICIES, validate
from score_execution_policies import ROOT, records


def measured(label, operation, samples):
    start = time.perf_counter_ns()
    try:
        value = operation()
    except (ValueError, KeyError, ArithmeticError, TypeError):
        value = None
    elapsed = (time.perf_counter_ns() - start) / 1e6
    samples[label].append(elapsed)
    return value


def unit_domain(call):
    if call is None:
        return None
    values = validate(call, {}, {}, POLICIES[2])
    return calculate(call["calculator_id"], values)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("Positive repeat count required")
    inputs = records(ROOT / "data/binding_validation_inputs.jsonl")
    proposals = {r["case_id"]: r.get("baseline_call") for r in records(
        ROOT / "results/binding/validation_repair_v2/cases.jsonl")}
    samples = {"unit_domain": [], "checked_calculator": [], "checked_and_published": []}
    valid_outcomes = {k: 0 for k in samples}
    rng = random.Random(731)
    with tempfile.TemporaryDirectory() as folder, connect(Path(folder)/"timing.sqlite") as db:
        initialize(db)
        rows = []
        for r in inputs:
            scope = Encounter("synthetic-profile-"+r["case_id"], "single-encounter")
            digest = hashlib.sha256(r["patient_note"].encode()).hexdigest()
            rows.append((r,scope,put_note(db,scope,r["patient_note"]),digest))
        for _ in range(args.repeats):
            rng.shuffle(rows)
            for row, scope, revision, digest in rows:
                note, question = row["patient_note"], row["question"]
                proposal = proposals[row["case_id"]]
                operations = {
                    "unit_domain": lambda: unit_domain(proposal),
                    "checked_calculator": lambda: execute_reviewed(question, note, proposal).get("result"),
                    "checked_and_published": lambda: execute_and_publish(db,scope,revision,digest,question,proposal).result,
                }
                order = list(operations)
                rng.shuffle(order)
                for name in order:
                    valid_outcomes[name] += int(measured(name, operations[name], samples) is not None)
    if valid_outcomes["checked_calculator"] != valid_outcomes["checked_and_published"]:
        raise AssertionError("Stable-store check and publication disagree on total releases")
    out = {"scope":"Historical 50 cases; calls reused, no simulated updates in timing experiment. Includes abstentions and missing calls. Local CPU under concurrent inference load; SQLite durable writes on this host filesystem. Descriptive latency only.", "cases":len(inputs),
           "repetitions":args.repeats,"python":platform.python_version(),"timing_ms":{}}
    for method, durations in samples.items():
        ordered = sorted(durations)
        out["timing_ms"][method] = {"observations":len(durations),"numeric_results":valid_outcomes[method],
                                    "median":statistics.median(durations),"p95":ordered[(95*len(ordered)+99)//100-1],
                                    "max":max(durations)}
    destination = ROOT / "results/runtime_latency"
    destination.mkdir(exist_ok=True)
    (destination/"summary.json").write_text(json.dumps(out,indent=2)+"\n")
    print(json.dumps(out["timing_ms"],indent=2))


if __name__ == "__main__":
    main()
