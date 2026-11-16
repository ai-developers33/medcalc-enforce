"""Run the offline development pilot. No model/API, no manuscript generation."""

import csv
import hashlib
import json
import math
import platform
import random
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path
from medcalc.enforcement import POLICIES, Rejected, enforce
from medcalc.fixtures import make_cases
from medcalc.metrics import summarize, percentile, paired_cluster_delta
from medcalc.registry import SPECS, calculate, canonical_value

ROOT = Path(__file__).resolve().parent

def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+"\n")

def numeric_match(answer, reference):
    return math.isfinite(answer) and math.isclose(answer,reference,rel_tol=.05,abs_tol=1e-9)

def execute(case, policy):
    start = time.perf_counter_ns()
    code = None
    try:
        values = enforce(case["call"],case["context"],case["before"],case["after"],policy)
        status = "validated"
    except Rejected as e:
        status, code = "rejected", e.code
    except (ValueError, TypeError, KeyError, ZeroDivisionError, OverflowError) as e:
        status, code = "rejected", "VALIDATION_EXCEPTION:"+type(e).__name__
    gate_ns = time.perf_counter_ns()-start
    answer = None
    if status == "validated":
        try:
            answer = calculate(case["calculator_id"], values)
            if isinstance(answer, complex) or not math.isfinite(answer): raise ValueError("nonfinite output")
            status = "returned"
        except (ValueError, TypeError, KeyError, ZeroDivisionError, OverflowError) as e:
            status, code = "runtime_error", type(e).__name__
            answer = None
    return {"case_id":case["case_id"],"base_id":case["base_id"],"group_id":case["group_id"],
            "calculator_id":case["calculator_id"],"kind":case["kind"],"valid":case["valid"],
            "policy":policy.name,"status":status,"code":code,"answer":answer,
            "numeric_correct":bool(status == "returned" and numeric_match(answer,case["numeric_reference"])),
            "gate_ns":gate_ns}

def main():
    path = ROOT / "data/pilot_rows.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    cases = [c for row in rows for c in make_cases(row)]
    result_dir = ROOT / "results"
    result_dir.mkdir(exist_ok=True)
    # Calculator reconstruction is evaluated independently of gate acceptance.
    formula_records=[]
    for row in rows:
        values={k:canonical_value(k,**v) for k,v in row["quantities"].items()}
        result=calculate(row["calculator_id"],values)
        gt=float(row["ground_truth"])
        lo,hi=sorted([float(row["lower"]),float(row["upper"])])
        formula_records.append({"source_row":row["source_row"],"calculator_id":row["calculator_id"],
                                "computed":result,"reference":gt,"benchmark_match":lo-1e-9 <= result <= hi+1e-9,
                                "match_at_0_1_percent":math.isclose(result,gt,rel_tol=.001,abs_tol=1e-9)})
    formula_summary={cid:{"name":SPECS[cid]["name"],"n":sum(r["calculator_id"]==cid for r in formula_records),
                         "benchmark_matches":sum(r["benchmark_match"] for r in formula_records if r["calculator_id"]==cid),
                         "strict_0_1_percent_matches":sum(r["match_at_0_1_percent"] for r in formula_records if r["calculator_id"]==cid)}
                     for cid in SPECS}
    write_json(result_dir/"formula_checks.json",formula_records)
    records=[]
    for c in cases:
        policies=list(POLICIES)
        random.Random(c["case_id"]).shuffle(policies)
        records.extend(execute(c,p) for p in policies)
    # Each fault label is checked to be syntactically serializable strict JSON.
    with (result_dir/"fixtures.jsonl").open("w") as f:
        for c in cases: f.write(json.dumps(c,allow_nan=False)+"\n")
    with (result_dir/"trial_results.jsonl").open("w") as f:
        for r in records: f.write(json.dumps(r,allow_nan=False)+"\n")
    per_policy={p.name:[r for r in records if r["policy"]==p.name] for p in POLICIES}
    summary={k:summarize(v) for k,v in per_policy.items()}
    stratified=[]
    for policy,rr in per_policy.items():
        for kind in sorted({r["kind"] for r in rr}):
            stratified.append({"policy":policy,"kind":kind,**summarize([r for r in rr if r["kind"]==kind])})
    fields=list(stratified[0])
    with (result_dir/"metrics_by_fault.csv").open("w",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(stratified)
    # Isolated warm microbenchmark: canonical valid calls only, 20 repeats.
    clean=[c for c in cases if c["kind"]=="valid_canonical"]
    timings={p.name:[] for p in POLICIES}
    for p in POLICIES:
        for c in clean[:20]: execute(c,p)
    for rep in range(20):
        policies=list(POLICIES);random.Random(731+rep).shuffle(policies)
        for p in policies:
            for c in clean:timings[p.name].append(execute(c,p)["gate_ns"]/1e6)
    latency={name:{"samples":len(v),"mean_ms":statistics.mean(v),"p50_ms":percentile(v,.5),
                   "p95_ms":percentile(v,.95),"p99_ms":percentile(v,.99)} for name,v in timings.items()}
    full=per_policy["B4_commit_revalidation"]
    deltas={name:paired_cluster_delta(full,rr) for name,rr in per_policy.items() if name.startswith("B") and name!="B4_commit_revalidation"}
    stable=[{k:v for k,v in r.items() if k!="gate_ns"} for r in records]
    digest=hashlib.sha256(json.dumps(stable,sort_keys=True,allow_nan=False).encode()).hexdigest()
    output={"stage":"development-only oracle-backed offline simulation",
            "model_calls":0,"api_spend_usd":0,"seed":731,"base_rows":len(rows),
            "unique_source_groups":len({r["group_id"] for r in rows}),
            "cases":len(cases),"case_types":dict(Counter(c["kind"] for c in cases)),
            "policies":len(POLICIES),"evaluation_records":len(records),
            "strict_JSON_serialization_passed":True,"semantic_results_sha256":digest,
            "input_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
            "environment":{"python":platform.python_version(),"platform":platform.platform(),"processor":platform.processor()},
            "formula_checks":formula_summary,"metrics":summary,"gate_latency_ms":latency,
            "paired_cluster_comparisons":deltas,
            "limitations":["Controlled development transformations; not naturally occurring LLM failures.",
                           "Oracle-backed structured evidence generated from benchmark annotations; no clinical-note extraction evaluated.",
                           "Patient, encounter, timestamps, and update events are simulated; no real longitudinal EHR outcomes.",
                           "Ten equation calculators only; no claim to cover all 55 tools or all clinically unsafe behaviors.",
                           "Sequential event replay; no production transaction isolation or distributed concurrency guarantee.",
                           "Clinical labels and provenance annotations have not been independently adjudicated.",
                           "No live multi-agent repair, upstream AgentSpec comparison, or MedCalc-Pro inference has run.",
                           "Perfect rejection on hand-constructed covered faults cannot establish novelty or clinical safety."]}
    write_json(result_dir/"pilot_summary.json",output)
    lines=["# Development pilot results — not manuscript evidence", "", "The results below are measured software development checks. No LLM inference or real EHR deployment was performed.","",
           f"Base annotations: {len(rows)} from the official training split; source groups: {output['unique_source_groups']}; controlled cases: {len(cases)}.","",
           "| Configuration | Invalid calls rejected before execution | Invalid result release | Valid false rejection | Valid numeric accuracy |", "|---|---:|---:|---:|---:|"]
    for name,m in summary.items():
        lines.append(f"| {name} | {m['tp_preexecution_rejections']}/{m['invalid_cases']} ({m['interception_recall']:.1%}) | {m['invalid_result_release_rate']:.1%} | {m['valid_false_rejection_rate']:.1%} | {m['valid_calculation_accuracy_all_cases']:.1%} |")
    lines += ["", "## Arithmetic reconstruction", "", f"{sum(r['benchmark_match'] for r in formula_records)}/{len(formula_records)} results satisfy the dataset's recorded answer interval. This uses supplied reference input annotations, so it is not LLM accuracy.", "", "## Limitations", ""]
    lines += ["- "+s for s in output["limitations"]]
    lines += ["", "Inspect `metrics_by_fault.csv`, `trial_results.jsonl`, and `formula_checks.json` for failures. Timing includes gates only and excludes model/network latency. The paired bootstrap groups all variants from the same source case.", "", f"Stable semantic-result digest: `{digest}`", ""]
    (result_dir/"PILOT_RESULTS.md").write_text("\n".join(lines))
    print(json.dumps({"base_rows":len(rows),"cases":len(cases),"formula_matches":sum(r["benchmark_match"] for r in formula_records),"metrics":summary,"latency_full":latency["B4_commit_revalidation"],"sha256":digest},indent=2))

if __name__ == "__main__":main()
