"""Deterministic gate prototype. No gold answers or fault labels enter this module.

The trusted ledger is an oracle-backed *simulation* in this pilot. A real EHR
adapter, trusted provenance extraction, concurrent transaction handling, and
clinical review remain future work.
"""

import math
from dataclasses import dataclass
from .registry import SPECS, canonical_value

class Rejected(ValueError):
    def __init__(self, code, field=None):
        self.code, self.field = code, field
        super().__init__(f"{code}:{field or ''}")

@dataclass(frozen=True)
class Policy:
    name: str
    schema: bool = True
    units: bool = True
    domain: bool = True
    applicability: bool = True
    provenance: bool = True
    context: bool = True
    commit: bool = True

POLICIES = [
    Policy("B0_unchecked_python", False, False, False, False, False, False, False),
    Policy("B1_schema", True, False, False, False, False, False, False),
    Policy("B2_static_semantics", True, True, True, True, False, False, False),
    Policy("B3_evidence_at_validation", True, True, True, True, True, True, False),
    Policy("B4_commit_revalidation"),
    Policy("A_no_argument_normalization", units=False),
    Policy("A_no_domain", domain=False),
    Policy("A_no_applicability", applicability=False),
    Policy("A_no_provenance", provenance=False),
    Policy("A_no_context", context=False),
]

def equal_value(a, b):
    if isinstance(a, str) or isinstance(b, str): return a == b
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-10)

def validate(call, context, store, policy):
    cid = call.get("calculator_id")
    if cid not in SPECS: raise Rejected("UNKNOWN_TOOL")
    spec = SPECS[cid]
    args = call.get("arguments", {})
    if policy.schema:
        if not isinstance(args, dict) or set(args) != set(spec["params"]):
            raise Rejected("ARGUMENT_SET")
        for field in spec["params"]:
            entry = args[field]
            if not isinstance(entry, dict) or set(entry) != {"value", "unit", "evidence_id"}:
                raise Rejected("ARGUMENT_SCHEMA", field)
            if not isinstance(entry["unit"], str) or not isinstance(entry["evidence_id"], str):
                raise Rejected("ARGUMENT_SCHEMA", field)
            if field == "sex":
                if entry["value"] not in ("Male", "Female"): raise Rejected("CATEGORY", field)
            elif isinstance(entry["value"], bool) or not isinstance(entry["value"], (int, float)) or not math.isfinite(entry["value"]):
                raise Rejected("FINITE_NUMBER", field)
    # Values are copied into a new mapping. Every baseline uses this frozen
    # validated payload, so mere post-validation caller mutation is not a strawman.
    values = {}
    for field in spec["params"]:
        entry = args[field]
        if policy.units:
            try: values[field] = canonical_value(field, entry["value"], entry["unit"])
            except ValueError: raise Rejected("UNIT_OR_VALUE", field)
        else:
            values[field] = entry["value"]
    if policy.domain:
        # Only documented arithmetic domains / measurement identities; no blanket
        # healthy-range filter that would reject valid critically abnormal values.
        for field, value in values.items():
            if field != "sex" and value <= 0: raise Rejected("POSITIVE_DOMAIN", field)
        if cid == "5" and values["sbp"] < values["dbp"]:
            raise Rejected("PRESSURE_ORDER")
    if policy.applicability and cid == "3" and values["age"] < 18:
        raise Rejected("ADULT_EQUATION", "age")
    if policy.context and call.get("formula_version") != store["registry"][cid]:
        raise Rejected("FORMULA_VERSION")
    for field, value in values.items():
        if not (policy.provenance or policy.context): continue
        obs = store["observations"].get(args[field]["evidence_id"])
        if obs is None:
            if policy.provenance: raise Rejected("MISSING_EVIDENCE", field)
            continue
        if policy.provenance:
            if obs["field"] != field: raise Rejected("EVIDENCE_VARIABLE", field)
            try: source = canonical_value(field, obs["value"], obs["unit"])
            except ValueError: raise Rejected("SOURCE_UNIT", field)
            # Provenance and unit normalization are separate gates: without the
            # unit gate, provenance compares semantic quantities, not the raw
            # numbers that the deliberately ablated executor will consume.
            try: asserted = canonical_value(field, args[field]["value"], args[field]["unit"])
            except ValueError: raise Rejected("ASSERTED_UNIT", field)
            if not equal_value(source, asserted): raise Rejected("SOURCE_VALUE", field)
        if policy.context:
            if obs["patient_id"] != context["patient_id"]: raise Rejected("PATIENT", field)
            if obs["encounter_id"] != context["encounter_id"]: raise Rejected("ENCOUNTER", field)
            if obs["time"] > context["as_of"]: raise Rejected("FUTURE_OBSERVATION", field)
            eligible = [o for o in store["observations"].values()
                        if o["field"] == field and o["patient_id"] == context["patient_id"]
                        and o["encounter_id"] == context["encounter_id"] and o["time"] <= context["as_of"]]
            if not eligible: raise Rejected("NO_ELIGIBLE_EVIDENCE", field)
            newest = max(o["time"] for o in eligible)
            newest_obs = [o for o in eligible if o["time"] == newest]
            if len(newest_obs) != 1: raise Rejected("AMBIGUOUS_LATEST", field)
            if obs["id"] != newest_obs[0]["id"]: raise Rejected("STALE_OBSERVATION", field)
    return values

def enforce(call, context, before, after, policy):
    values = validate(call, context, before, policy)
    if policy.commit:
        values = validate(call, context, after, policy)
    return values
