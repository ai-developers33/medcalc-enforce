"""Metric calculations with explicit denominators and source-group resampling."""

import math
import random
from collections import defaultdict

def ratio(numerator, denominator):
    return numerator / denominator if denominator else None

def summarize(records):
    invalid = [r for r in records if not r["valid"]]
    valid = [r for r in records if r["valid"]]
    tp = sum(r["status"] == "rejected" for r in invalid)
    fp = sum(r["status"] == "rejected" for r in valid)
    fn, tn = len(invalid)-tp, len(valid)-fp
    precision, recall = ratio(tp,tp+fp), ratio(tp,len(invalid))
    return {
        "cases": len(records), "invalid_cases": len(invalid), "valid_cases": len(valid),
        "tp_preexecution_rejections": tp, "fp_valid_rejections": fp,
        "fn_not_rejected_before_execution": fn, "tn_valid_not_rejected": tn,
        "interception_recall": recall, "precision": precision,
        "f1": ratio(2*tp, 2*tp+fp+fn),
        "invalid_execution_attempt_rate": ratio(fn,len(invalid)),
        "invalid_result_release_rate": ratio(sum(r["status"] == "returned" for r in invalid),len(invalid)),
        "valid_false_rejection_rate": ratio(fp,len(valid)),
        "valid_calculation_accuracy_all_cases": ratio(sum(r["numeric_correct"] for r in valid),len(valid)),
        "valid_answer_coverage": ratio(sum(r["status"] == "returned" for r in valid),len(valid)),
        "runtime_failures": sum(r["status"] == "runtime_error" for r in records),
    }

def percentile(values, fraction):
    values = sorted(values)
    if not values: return None
    index = (len(values)-1)*fraction
    low, high = math.floor(index), math.ceil(index)
    return values[low]*(high-index)+values[high]*(index-low) if low != high else values[low]

def paired_cluster_delta(full, baseline, draws=2000, seed=731):
    """Baseline minus full invalid-release rate, grouped by source case.

    This interval describes resampling of this constructed development corpus;
    it is not an uncertainty bound on clinical harm or natural LLM errors.
    """
    base = {r["case_id"]: r for r in baseline if not r["valid"]}
    groups = defaultdict(lambda: [0,0])
    for row in full:
        if row["valid"]: continue
        b = base[row["case_id"]]
        item = groups[row["group_id"]]
        item[0] += int(b["status"] == "returned") - int(row["status"] == "returned")
        item[1] += 1
    values = list(groups.values())
    rng = random.Random(seed)
    estimates = []
    for _ in range(draws):
        sample = rng.choices(values,k=len(values))
        estimates.append(sum(x[0] for x in sample)/sum(x[1] for x in sample))
    return {"baseline_minus_full": sum(x[0] for x in values)/sum(x[1] for x in values),
            "cluster_bootstrap_95_percentile": [percentile(estimates,.025),percentile(estimates,.975)],
            "source_groups":len(values), "resamples":draws,
            "interpretation":"Descriptive development-fixture interval; no clinical or unseen-model generalization claim."}
