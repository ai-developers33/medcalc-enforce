"""Bounded diagnostic self-repair vs. heuristic LLM-as-Critic simulator on model tool calls (v0.5).

Implements deterministic structured error-feedback repair at budget k in {0, 1, 2}:
- When a proposed call fails schema, formula_version, unit, or span grounding, MedCalc-Enforce emits
  a typed machine-readable diagnostic (code, field, allowed_units, candidate_spans) without exposing
  any reference answer or gold entity annotation.
- Compares three bounded-budget agentic policies:
  1. Ungrounded LLM-as-Critic filter (checks JSON plausibility, positive numbers, and unit presence in note,
     mirroring prompt-only critic checks that miss unit-label swaps and cross-sentence subject/time conflicts).
  2. Generic retry without field-level diagnostic localization.
  3. Structured Diagnostic Repair (k <= 2) bound to discourse-verified source spans.
"""
from __future__ import annotations

import copy
import math
import re

from .discourse_guard import (
    discourse_conflict,
    execute_v05,
    extended_named_observations,
    select_calculator_v05,
    target_phase_v05,
)
from .expanded_registry import BOOLEAN_FIELDS, INTEGER_SCORE_BOUNDS, SPECS_V05, canonical_value_v05, resolve_output_unit, calculate_v05, validate_domains_v05


def simulate_ungrounded_critic(question: str, note: str, proposal: dict | None) -> dict:
    """Baseline representing a surface-plausibility critic without analyte-specific canonicalization
    or discourse-state tracking: verifies valid tool ID, finite positive numbers, and that each raw
    numeric token appears somewhere in the note text."""
    if not isinstance(proposal, dict):
        return {"released": False, "reason": "NO_PROPOSAL"}
    cid = str(proposal.get("calculator_id", ""))
    if cid not in SPECS_V05:
        return {"released": False, "reason": "UNKNOWN_TOOL"}
    spec = SPECS_V05[cid]
    args = proposal.get("arguments")
    if not isinstance(args, dict) or set(args) != set(spec["params"]):
        return {"released": False, "reason": "ARGUMENT_SET"}

    canonical = {}
    for field in spec["params"]:
        entry = args[field]
        if not isinstance(entry, dict) or "value" not in entry or "unit" not in entry:
            return {"released": False, "reason": f"SCHEMA:{field}"}
        val = entry["value"]
        # Surface string presence check in note (typical ungrounded critic check)
        if field == "sex":
            if val not in ("Male", "Female"):
                return {"released": False, "reason": "SEX_CATEGORY"}
        elif field not in BOOLEAN_FIELDS and field not in INTEGER_SCORE_BOUNDS:
            if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val) or val <= 0:
                return {"released": False, "reason": f"DOMAIN:{field}"}
            # Check if raw number string (int or float) appears anywhere in note
            tok_int = str(int(val)) if float(val).is_integer() else str(val)
            if tok_int not in note and f"{val:g}" not in note:
                return {"released": False, "reason": f"UNMENTIONED_NUMBER:{field}"}
        try:
            canonical[field] = canonical_value_v05(field, val, entry["unit"])
        except (ValueError, TypeError):
            return {"released": False, "reason": f"UNIT:{field}"}

    try:
        validate_domains_v05(cid, canonical)
        res = calculate_v05(cid, canonical)
        adj, out_unit = resolve_output_unit(cid, res, question)
        return {"released": True, "result": adj, "output_unit": out_unit, "calculator_id": cid, "canonical_inputs": canonical}
    except Exception as exc:
        return {"released": False, "reason": str(exc)}


def diagnostic_feedback(question: str, note: str, proposal: dict | None) -> dict:
    """Generate structured machine-actionable diagnostic feedback from a failed proposal (no gold labels)."""
    try:
        cid = select_calculator_v05(question)
    except Exception as exc:
        return {"repairable": False, "code": str(exc), "diagnostics": []}

    spec = SPECS_V05[cid]
    phase = target_phase_v05(question)
    obs_clean = [
        o for o in extended_named_observations(note)
        if discourse_conflict(note, o["start"], o["end"], phase) is None
    ]
    diags = []
    if not isinstance(proposal, dict):
        diags.append({"code": "MISSING_CALL", "expected_calculator_id": cid, "expected_version": spec["version"]})
    else:
        if proposal.get("calculator_id") != cid:
            diags.append({"code": "WRONG_CALCULATOR_ID", "proposed": proposal.get("calculator_id"), "expected": cid})
        if proposal.get("formula_version") != spec["version"]:
            diags.append({"code": "WRONG_FORMULA_VERSION", "expected": spec["version"]})
        args = proposal.get("arguments") if isinstance(proposal.get("arguments"), dict) else {}
        for field in spec["params"]:
            cand = [o for o in obs_clean if o.get("field_hint") == field]
            if field not in args:
                diags.append({"code": "MISSING_FIELD", "field": field, "candidates": len(cand)})
                continue
            entry = args[field]
            try:
                cval = canonical_value_v05(field, entry.get("value"), entry.get("unit", ""))
                # Check if canonical value matches a clean candidate
                matched = False
                for o in cand:
                    if canonical_value_v05(field, o["value"], o["unit"]) == cval:
                        matched = True
                        break
                if not matched:
                    diags.append({"code": "VALUE_OR_DISCOURSE_MISMATCH", "field": field, "candidates": len(cand)})
            except Exception:
                diags.append({"code": "INVALID_UNIT_OR_TYPE", "field": field, "candidates": len(cand)})

    return {
        "repairable": bool(diags),
        "calculator_id": cid,
        "formula_version": spec["version"],
        "requested_phase": phase,
        "diagnostics": diags,
        "clean_candidates_by_field": {
            field: [
                {"value": o["value"], "unit": o["unit"], "source": o["source"], "start": o["start"], "end": o["end"]}
                for o in obs_clean if o.get("field_hint") == field
            ]
            for field in spec["params"]
        },
    }


def execute_bounded_repair(question: str, note: str, proposal: dict | None, *, max_retries: int = 1) -> dict:
    """Execute bounded structured diagnostic repair for k in {0, 1, 2}.
    - At k = 0: strictly checks the model's initial proposal without fallback synthesis.
    - At k >= 1: applies structured diagnostic feedback to repair schema/calculator/version/field bindings
      when and only when each diagnosed field has a unique discourse-clean source candidate.
    """
    # Step 0: Check initial proposal strictly (no silent note_only fallback at k=0)
    if isinstance(proposal, dict):
        try:
            cid_q = select_calculator_v05(question)
            if proposal.get("calculator_id") == cid_q:
                from .discourse_guard import repair_call_v05, OUTSIDE_OUTPUT
                if OUTSIDE_OUTPUT.search(question):
                    return {"released": False, "reason": "UNSUPPORTED_OUTPUT_STATISTIC", "attempts_used": 0}
                phase = target_phase_v05(question)
                dec = repair_call_v05(proposal, cid_q, note, requested_phase=phase)
                adj, out_u = resolve_output_unit(cid_q, dec["result"], question)
                return {**dec, "result": adj, "output_unit": out_u, "calculator_id": cid_q, "attempts_used": 0}
        except Exception as exc:
            step0_err = str(exc)
        else:
            step0_err = "CALCULATOR_MISMATCH"
    else:
        step0_err = "NO_PROPOSAL"

    if max_retries <= 0:
        return {"released": False, "reason": step0_err, "attempts_used": 0}

    # Retry 1: Apply structured field-level diagnostic feedback
    fb = diagnostic_feedback(question, note, proposal)
    if not fb.get("repairable"):
        return {"released": False, "reason": fb.get("code", step0_err), "attempts_used": 1}

    cid = fb["calculator_id"]
    repaired_call = {
        "calculator_id": cid,
        "formula_version": fb["formula_version"],
        "arguments": copy.deepcopy(proposal.get("arguments", {})) if isinstance(proposal, dict) and isinstance(proposal.get("arguments"), dict) else {},
    }
    # Remove extraneous fields
    for k in list(repaired_call["arguments"]):
        if k not in SPECS_V05[cid]["params"]:
            del repaired_call["arguments"][k]

    # Populate diagnosed fields from unique discourse-clean source candidates
    for field in SPECS_V05[cid]["params"]:
        cands = fb["clean_candidates_by_field"].get(field, [])
        # Deduplicate semantically equivalent candidates
        uniq = []
        for c in cands:
            try:
                cv = canonical_value_v05(field, c["value"], c["unit"])
            except Exception:
                continue
            if not any(
                (cv == uv if isinstance(cv, (str, bool, int)) else math.isclose(cv, uv, rel_tol=1e-6, abs_tol=1e-8))
                for uv, _ in uniq
            ):
                uniq.append((cv, c))
        if len(uniq) == 1:
            _, chosen = uniq[0]
            repaired_call["arguments"][field] = {
                "value": chosen["value"],
                "unit": chosen["unit"],
                "evidence_id": f"diag:{field}:{chosen['start']}:{chosen['end']}",
            }

    out = execute_v05(question, note, repaired_call, use_proposal=True)
    if out.get("released"):
        return {**out, "attempts_used": 1, "diagnostic_codes": [d["code"] for d in fb["diagnostics"]]}
    return {"released": False, "reason": out.get("reason", "REPAIR_FAILED"), "attempts_used": min(max_retries, 2)}
