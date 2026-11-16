"""Controlled transformations of development annotations, NOT observed LLM errors.

Labels follow the declared transformation specification, not a call to the
enforcer. The same research team authored fixtures and contracts; independent
clinical adjudication and adversarial authorship are not claimed.
"""

import copy
from .registry import SPECS, CANONICAL, ALTERNATE_UNITS, canonical_value, unit_factor

def base_case(row):
    cid, rid = row["calculator_id"], row["source_row"]
    patient, encounter = f"sim-patient-{row['group_id']}", f"sim-encounter-{rid}"
    obs, args = {}, {}
    for field in SPECS[cid]["params"]:
        q = row["quantities"][field]
        eid = f"obs-{rid}-{field}"
        obs[eid] = {"id": eid, "field": field, **q, "patient_id": patient, "encounter_id": encounter, "time": 90}
        args[field] = {"value": canonical_value(field, **q), "unit": CANONICAL[field], "evidence_id": eid}
    store = {"observations": obs, "registry": {cid: SPECS[cid]["version"]}}
    return {"base_id": f"train-{rid}-calc-{cid}", "group_id": row["group_id"],
            "calculator_id": cid, "kind": "valid_canonical", "valid": True,
            "numeric_reference": float(row["ground_truth"]),
            "context": {"patient_id": patient, "encounter_id": encounter, "as_of": 100},
            "call": {"calculator_id": cid, "formula_version": SPECS[cid]["version"], "arguments": args},
            "before": store, "after": copy.deepcopy(store)}

def variant(base, kind, valid=False):
    result = copy.deepcopy(base)
    result.update(kind=kind, valid=valid)
    return result

def update_observation(case, field, value, unit=None):
    entry = case["call"]["arguments"][field]
    entry["value"] = value
    if unit is not None: entry["unit"] = unit
    for store in (case["before"], case["after"]):
        obs = store["observations"][entry["evidence_id"]]
        obs["value"], obs["unit"] = entry["value"], entry["unit"]

def make_cases(row):
    base = base_case(row)
    cid = row["calculator_id"]
    fields = SPECS[cid]["params"]
    field = next(f for f in fields if f in ALTERNATE_UNITS)
    canonical = base["call"]["arguments"][field]["value"]
    eid = base["call"]["arguments"][field]["evidence_id"]
    cases = [base]

    c = variant(base, "valid_equivalent_units", True)
    for f, arg in c["call"]["arguments"].items():
        if f in ALTERNATE_UNITS:
            arg["unit"] = ALTERNATE_UNITS[f]
            arg["value"] /= unit_factor(f, arg["unit"])
    cases.append(c)

    c = variant(base, "valid_historical_query", True)
    c["context"]["as_of"] = 95
    for store in (c["before"], c["after"]):
        future = copy.deepcopy(store["observations"][eid])
        future.update(id=eid+"-future", time=120, value=canonical*1.2, unit=CANONICAL[field])
        store["observations"][future["id"]] = future
    cases.append(c)

    c = variant(base, "valid_unrelated_update", True)
    unrelated = copy.deepcopy(c["after"]["observations"][eid])
    unrelated.update(id=eid+"-unrelated", field="unrequested_measurement", time=99)
    c["after"]["observations"][unrelated["id"]] = unrelated
    cases.append(c)

    c = variant(base, "fabricated_value")
    c["call"]["arguments"][field]["value"] *= 1.25
    cases.append(c)

    c = variant(base, "unit_relabel_without_conversion")
    c["call"]["arguments"][field]["unit"] = ALTERNATE_UNITS[field]
    cases.append(c)

    c = variant(base, "missing_evidence")
    c["call"]["arguments"][field]["evidence_id"] = "nonexistent-evidence"
    cases.append(c)

    for kind, key in [("wrong_patient", "patient_id"), ("wrong_encounter", "encounter_id")]:
        c = variant(base, kind)
        foreign = copy.deepcopy(c["before"]["observations"][eid])
        foreign.update(id=eid+"-foreign")
        foreign[key] = "foreign-context"
        for store in (c["before"], c["after"]): store["observations"][foreign["id"]] = copy.deepcopy(foreign)
        c["call"]["arguments"][field]["evidence_id"] = foreign["id"]
        cases.append(c)

    c = variant(base, "stale_observation")
    old = copy.deepcopy(c["before"]["observations"][eid])
    old.update(id=eid+"-old", time=40, value=canonical*.8, unit=CANONICAL[field])
    for store in (c["before"], c["after"]): store["observations"][old["id"]] = copy.deepcopy(old)
    c["call"]["arguments"][field].update(evidence_id=old["id"], value=canonical*.8)
    cases.append(c)

    c = variant(base, "late_observation_between_validation_and_execution")
    new = copy.deepcopy(c["after"]["observations"][eid])
    new.update(id=eid+"-late", time=98, value=canonical*1.2, unit=CANONICAL[field])
    c["after"]["observations"][new["id"]] = new
    cases.append(c)

    c = variant(base, "formula_revoked_between_validation_and_execution")
    c["after"]["registry"][cid] = SPECS[cid]["version"]+"-replacement-required"
    cases.append(c)

    c = variant(base, "unsupported_unit")
    c["call"]["arguments"][field]["unit"] = "unrecognized-unit"
    cases.append(c)

    c = variant(base, "negative_measurement_with_matching_source")
    update_observation(c, field, -abs(canonical))
    cases.append(c)

    if cid == "3":
        c = variant(base, "adult_equation_for_child")
        update_observation(c, "age", 16, "years")
        cases.append(c)
    if cid == "5":
        c = variant(base, "inverted_pressure_pair")
        sbp = c["call"]["arguments"]["sbp"]["value"]
        dbp = c["call"]["arguments"]["dbp"]["value"]
        update_observation(c, "sbp", min(sbp,dbp)-5, "mmHg")
        update_observation(c, "dbp", max(sbp,dbp)+5, "mmHg")
        cases.append(c)
    for c in cases: c["case_id"] = c["base_id"]+":"+c["kind"]
    return cases
