"""Unified v0.5 MedCalc-Enforce runtime: paraphrase-resilient routing, extended unit repair,
and paragraph/section-level stateful discourse context verification.

Leaves medcalc/release_policy.py and medcalc/source_fallback.py untouched so all
historical v0.4 checksums and secondary_freeze.json hashes verify cleanly.
"""
from __future__ import annotations

import copy
import hashlib
import math
import re

from .enforcement import Rejected
from .expanded_registry import (
    BOOLEAN_FIELDS,
    INTEGER_SCORE_BOUNDS,
    SPECS_V05,
    calculate_v05,
    canonical_value_v05,
    resolve_output_unit,
    validate_domains_v05,
)
from .release_policy import (
    ADMISSION,
    LATER,
    NEGATED,
    NONOBSERVED,
    OBSERVED,
    OTHER_PERSON,
    OUTSIDE_OUTPUT,
    PATIENT,
    POSTQUALIFIER,
)
from .source_fallback import ALTERNATE_FORMULAS, COUNT, INVERSE, POST_LABEL, explicit_field
from .source_repair import LABELS, role_candidates, same

LABELS_V05 = {
    **LABELS,
    "bilirubin": r"(?:total\s+|serum\s+)?bilirubin",
    "respiratory_rate": r"respiratory\s+rate|respirations?",
    "inr": r"international\s+normalized\s+ratio|INR",
}

INTENTS_V05 = {
    "3": r"\b(?:CKD[- ]?EPI|glomerular filtration rate|eGFR|race[- ]free\s+(?:2021\s+)?(?:renal|creatinine)\s+(?:filtration|clearance|equation))\b",
    "5": r"\b(?:mean arterial(?: blood)? pressure|MAP)\b",
    "6": r"\b(?:BMI|body mass(?: mass)? index|Quetelet(?:'s)? index)\b",
    "7": r"\b(?:corrected calcium|calcium correction|albumin[- ]corrected(?: serum)? calcium|calcium adjusted for albumin|Payne(?:'s)?(?: calcium)? formula)\b",
    "11": r"\b(?:Bazett(?:'s)?|corrected QT|QTc(?:\s+interval)?|heart[- ]rate[- ]corrected QT)\b",
    "19": r"\b(?:fibrosis[- ]?4|FIB[- ]?4)\b",
    "26": r"\b(?:corrected(?: serum)? sodium|sodium correction|sodium corrected|Hillier(?:'s)?(?: sodium)?|hyperglycemia[- ]adjusted sodium)\b",
    "30": r"\b(?:(?:serum|plasma)\s+osmolality|calculated\s+osmolality|effective\s+osmolality\s+equation)\b",
    "39": r"\b(?:(?:serum|anion)\s+anion gap|anion gap)\b",
    "60": r"\b(?:body surface area|BSA|Mosteller(?:'s)?(?:\s+area|\s+BSA)?)\b",
    "61": r"\b(?:CHA2DS2[- ]?VASc|CHADS[- ]?VASc)\b",
    "62": r"\b(?:CURB[- ]?65)\b",
    "63": r"\b(?:Wells(?:'s)?\s+(?:score|criteria|rule)\s+for\s+(?:DVT|deep vein thrombosis)|Wells[- ]?DVT|Wells\s+DVT)\b",
    "64": r"\b(?:Glasgow Coma(?: Scale| Score)|GCS)\b",
    "65": r"\b(?:MELD[- ]?Na|sodium[- ]adjusted MELD)\b",
    "66": r"\b(?:Cockcroft[- ]?Gault|creatinine clearance|CrCl)\b",
}

ALTERNATE_FORMULAS_V05 = {
    **ALTERNATE_FORMULAS,
    "65": r"\b(?:MELD\s+3\.0|PELD)\b",
    "66": r"\b(?:CKD[- ]?EPI|MDRD)\b",
}

PLATELET_MM3 = re.compile(
    r"(?<![\w.,+-])(?P<n>\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(?:(?:cells?|counts?)\s*)?/\s*mm(?:\^?3|³)\b",
    re.I,
)
RESP_RATE_OBS = re.compile(
    r"(?<![\w.,+-])(?P<n>\d+(?:\.\d+)?)\s*(?P<unit>breaths?\s*/\s*min(?:ute)?|rpm)\b",
    re.I,
)
INR_OBS = re.compile(
    r"\bINR\s*(?:of|was|is|:|=)?\s*(?P<n>\d+(?:\.\d+)?)(?:\s*ratio)?\b",
    re.I,
)
BILIRUBIN_OBS = re.compile(
    r"\b(?:total\s+|serum\s+)?bilirubin\s*(?:level|was|of|is|at|:|=|\s)*?(?P<n>\d+(?:\.\d+)?)\s*(?P<unit>mg/dL|µmol/L|umol/L|mmol/L)\b",
    re.I,
)
DELTA_CUE = re.compile(
    r"\b(?:lost|gained|(?:weight\s+)?(?:loss|gain)\s+of|(?:increas|decreas|drop|fall|fell|ris|rose)\w*\s+by)\b",
    re.I,
)
SENTENCE_SPLIT = re.compile(r"(?:[;\n]+|[.!?]+(?=\s|$))")

# Explicit forward-scoping framing headers/sentences that introduce subsequent measurements
FORWARD_FRAMING = re.compile(
    r"(?:"
    r"^\s*(?:family\s+(?:medical\s+)?history|caregiver\s+vitals?|admission(?:\s+\w+){0,3}|discharge(?:\s+\w+){0,3}|follow[- ]?up(?:\s+\w+){0,3})\s*:"
    r"|\b(?:following|below)\b[^.\n]{0,60}\b(?:belong|pertain|refer|apply|are|were|follow)"
    r"|\b(?:measurements?|values?|vitals?|labs?)\s+(?:belong(?:ing)?\s+to|for\s+(?:his|her|the)\s+\w+|are\s+listed\s+below|listed\s+below|follow\b)"
    r")",
    re.I | re.M,
)
PATIENT_RESET = re.compile(
    r"\b(?:(?:the|our|this)\s+patient(?:'s)?|patient\s+(?:is|was|has|had|presented|presents|vital|vitals|measurements?|labs?|exam)|physical\s+exam(?:ination)?)\b",
    re.I,
)


def select_calculator_v05(question: str) -> str:
    matches = [cid for cid, pattern in INTENTS_V05.items() if re.search(pattern, question, re.I)]
    if "3" in matches and "66" in matches:
        if re.search(r"\bCockcroft[- ]?Gault\b", question, re.I):
            matches = ["66"]
        elif re.search(r"\bCKD[- ]?EPI\b", question, re.I):
            matches = ["3"]
    if len(matches) != 1:
        raise Rejected("UNRESOLVED_CALCULATOR")
    cid = matches[0]
    alternate = ALTERNATE_FORMULAS_V05.get(cid)
    if alternate and re.search(alternate, question, re.I):
        raise Rejected("UNSUPPORTED_FORMULA")
    return cid


def _latest_cue(text: str, *labeled_patterns) -> str | None:
    hits = [(m.start(), label) for label, pattern in labeled_patterns for m in pattern.finditer(text)]
    return max(hits)[1] if hits else None


def target_phase_v05(question: str) -> str | None:
    early = bool(ADMISSION.search(question))
    late = bool(LATER.search(question))
    return "admission" if early and not late else ("later" if late and not early else None)


def _paragraphs_with_offsets(note: str) -> list[tuple[int, int, str]]:
    blocks = []
    pos = 0
    for chunk in re.split(r"(\n\s*\n)", note):
        if not chunk:
            continue
        start = pos
        end = pos + len(chunk)
        pos = end
        if not chunk.strip():
            continue
        lines = chunk.splitlines(keepends=True)
        sub_start = start
        buf = []
        cursor = start
        for line in lines:
            stripped = line.strip()
            is_standalone_header = bool(re.fullmatch(r"[A-Za-z][A-Za-z0-9 /_\-]{0,60}:", stripped))
            if is_standalone_header and buf:
                blocks.append((sub_start, cursor, "".join(buf)))
                sub_start = cursor
                buf = [line]
            else:
                buf.append(line)
            cursor += len(line)
        if buf:
            blocks.append((sub_start, cursor, "".join(buf)))
    return blocks if blocks else [(0, len(note), note)]


def _sentences_in_block(block_start: int, block_text: str) -> list[tuple[int, int, str]]:
    spans = []
    last = 0
    for m in SENTENCE_SPLIT.finditer(block_text):
        end = m.end()
        seg = block_text[last:end]
        if seg.strip():
            spans.append((block_start + last, block_start + end, seg))
        last = end
    if last < len(block_text) and block_text[last:].strip():
        spans.append((block_start + last, block_start + len(block_text), block_text[last:]))
    return spans


def discourse_conflict(note: str, start: int, end: int, requested_phase: str | None) -> str | None:
    """Evaluate local clause cues AND explicit forward-framing paragraph/section headers."""
    before = note[:start]
    boundary = next((m.end() for m in reversed(list(SENTENCE_SPLIT.finditer(before)))), 0)
    local_prefix = before[boundary:]
    qualifier_match = POSTQUALIFIER.match(note[end : end + 64])
    local_scope = local_prefix + " " + (qualifier_match.group(0) if qualifier_match else "")

    local_subject = _latest_cue(local_scope, ("other", OTHER_PERSON), ("patient", PATIENT))
    if local_subject == "other":
        return "OTHER_PERSON"
    if NEGATED.search(local_scope) or DELTA_CUE.search(local_prefix[-48:]) or _latest_cue(local_scope, ("nonobserved", NONOBSERVED), ("observed", OBSERVED)) == "nonobserved":
        return "NONOBSERVED"
    local_phase = _latest_cue(local_scope, ("admission", ADMISSION), ("later", LATER))
    if requested_phase and local_phase and local_phase != requested_phase:
        return "OTHER_TIME"

    # Stateful paragraph/section inheritance strictly from forward-scoping framing sentences/headers
    for b_start, b_end, b_text in _paragraphs_with_offsets(note):
        if not (b_start <= start < b_end):
            continue
        inherited_subject = None
        inherited_phase = None
        for s_start, s_end, s_text in _sentences_in_block(b_start, b_text):
            if s_start > start:
                break
            if start < s_end:
                eff_subject = local_subject or inherited_subject
                eff_phase = local_phase or inherited_phase
                if eff_subject == "other":
                    return "OTHER_PERSON"
                if requested_phase and eff_phase and eff_phase != requested_phase:
                    return "OTHER_TIME"
                break
            s_subj = _latest_cue(s_text, ("other", OTHER_PERSON), ("patient", PATIENT_RESET))
            s_phase = _latest_cue(s_text, ("admission", ADMISSION), ("later", LATER))
            if FORWARD_FRAMING.search(s_text):
                if s_subj is not None:
                    inherited_subject = s_subj
                if s_phase is not None:
                    inherited_phase = s_phase
            elif s_subj == "patient":
                inherited_subject = "patient"
        break
    return None


def _explicit_field_v05(note: str, start: int) -> str | None:
    prefix = note[max(0, start - 90) : start]
    for field, pattern in LABELS_V05.items():
        if field == "other":
            continue
        if re.search(r"(?<![a-z])(?:" + pattern + r")\s*(?:\)|level|count|was|of|is|at|:|=|\s)*$", prefix, re.I):
            return field
    return explicit_field(note, start)


def extended_named_observations(note: str) -> list[dict]:
    """Extend named_observations with count/mm^3, respiratory rate, bilirubin, and INR."""
    extra = []
    for pattern in (COUNT, INVERSE):
        for match in pattern.finditer(note):
            start, end = match.span()
            if re.search(r"\d\s*[-–]\s*$", note[max(0, start - 16) : start]):
                continue
            value = float(match["n"])
            unit = "U/L"
            if pattern is COUNT:
                exponent = next(group for group in match.groups()[1:4] if group)
                exponent = exponent.translate(str.maketrans("¹²³⁴⁵⁶⁷⁸⁹", "123456789"))
                value *= 10 ** int(exponent)
                unit = "L" if match["vol"].lower() == "l" else "uL"
            extra.append({
                "value": value,
                "unit": unit,
                "start": start,
                "end": end,
                "source": note[start:end],
                "rule": "extended_count",
                "field_hint": _explicit_field_v05(note, start),
            })

    for match in PLATELET_MM3.finditer(note):
        start, end = match.span()
        if any(x["start"] < end and start < x["end"] for x in extra):
            continue
        if re.search(r"\d\s*[-–]\s*$", note[max(0, start - 16) : start]):
            continue
        extra.append({
            "value": float(match["n"].replace(",", "")),
            "unit": "mm^3",
            "start": start,
            "end": end,
            "source": note[start:end],
            "rule": "platelet_mm3",
            "field_hint": _explicit_field_v05(note, start) or ("platelets" if "platelet" in note[max(0, start - 90) : start].lower() else None),
        })

    for match in RESP_RATE_OBS.finditer(note):
        start, end = match.span()
        if any(x["start"] < end and start < x["end"] for x in extra):
            continue
        extra.append({
            "value": float(match["n"]),
            "unit": "breaths/min",
            "start": start,
            "end": end,
            "source": note[start:end],
            "rule": "respiratory_rate",
            "field_hint": "respiratory_rate",
        })

    for match in INR_OBS.finditer(note):
        start, end = match.span()
        if any(x["start"] < end and start < x["end"] for x in extra):
            continue
        extra.append({
            "value": float(match["n"]),
            "unit": "ratio",
            "start": start,
            "end": end,
            "source": note[start:end],
            "rule": "inr_ratio",
            "field_hint": "inr",
        })

    for match in BILIRUBIN_OBS.finditer(note):
        start, end = match.span()
        if any(x["start"] < end and start < x["end"] for x in extra):
            continue
        u = match["unit"].replace("µ", "u")
        extra.append({
            "value": float(match["n"]),
            "unit": u,
            "start": start,
            "end": end,
            "source": note[start:end],
            "rule": "bilirubin",
            "field_hint": "bilirubin",
        })

    results = []
    for obs in role_candidates(note):
        if any(x["start"] < obs["end"] and obs["start"] < x["end"] for x in extra):
            continue
        obs = dict(obs)
        # Re-classify bilirubin or respiratory_rate if v0.4 grouped them under 'other'
        if obs.get("field_hint") == "other":
            re_hint = _explicit_field_v05(note, obs["start"])
            if re_hint in ("bilirubin", "respiratory_rate", "inr"):
                obs["field_hint"] = re_hint
        suffix = POST_LABEL.match(note[obs["end"] : obs["end"] + 70])
        if suffix:
            name = suffix.group(1)
            obs["field_hint"] = next(
                field for field, pattern in LABELS.items() if re.fullmatch(pattern, name, re.I)
            )
        results.append(obs)
    results.extend(extra)
    results.sort(key=lambda o: (o["start"], o["end"]))
    for idx, item in enumerate(results):
        item.setdefault("id", f"v05_q{idx:03d}")
    return results


def _compatible_v05(field: str, obs: dict) -> bool:
    if obs.get("field_hint") and obs["field_hint"] != field:
        return False
    try:
        canonical_value_v05(field, obs["value"], obs["unit"])
        return True
    except (ValueError, TypeError):
        return False


def _unique_semantic_v05(field: str, items: list[dict]) -> list[dict]:
    out = []
    for o in items:
        val = canonical_value_v05(field, o["value"], o["unit"])
        if not any(same(val, canonical_value_v05(field, x["value"], x["unit"])) for x in out):
            out.append(o)
    return out


def repair_call_v05(call: dict, cid: str, note: str, requested_phase: str | None = None, chained_tokens: dict | None = None) -> dict:
    """Repair and validate a proposed calculator call against discourse-clean source observations."""
    if cid not in SPECS_V05 or call.get("calculator_id") != cid:
        raise Rejected("UNKNOWN_TOOL")
    spec = SPECS_V05[cid]
    if call.get("formula_version") != spec["version"]:
        raise Rejected("FORMULA_VERSION")
    args = call.get("arguments")
    if not isinstance(args, dict) or set(args) != set(spec["params"]):
        raise Rejected("ARGUMENT_SET")

    obs_all = extended_named_observations(note)
    obs_clean = [
        o for o in obs_all
        if discourse_conflict(note, o["start"], o["end"], requested_phase) is None
    ]
    note_hash = hashlib.sha256(note.encode("utf-8")).hexdigest()
    repaired_args = {}
    canonical_inputs = {}
    audit = {}

    for field in spec["params"]:
        proposal = args[field]
        if not isinstance(proposal, dict) or "value" not in proposal or "unit" not in proposal:
            raise Rejected("ARGUMENT_SCHEMA", field)
        if not isinstance(proposal["unit"], str):
            raise Rejected("UNIT_TYPE", field)

        if chained_tokens and field in chained_tokens:
            tok = chained_tokens[field]
            if tok.get("note_sha256") != note_hash or not tok.get("released"):
                raise Rejected("INVALID_CHAINED_TOKEN", field)
            cval = canonical_value_v05(field, tok["result"], tok["output_unit"])
            repaired_args[field] = {
                "value": tok["result"],
                "unit": tok["output_unit"],
                "evidence_id": f"chain:{tok['calculator_id']}",
            }
            canonical_inputs[field] = cval
            audit[field] = {
                "action": "verified_chained_output",
                "upstream_calculator_id": tok["calculator_id"],
                "source": f"chained:{tok['calculator_id']}",
                "start": 0,
                "end": 0,
            }
            continue

        if field in BOOLEAN_FIELDS or field in INTEGER_SCORE_BOUNDS:
            cval = canonical_value_v05(field, proposal["value"], proposal["unit"])
            quote = proposal.get("source_quote") or proposal.get("evidence_quote")
            if not isinstance(quote, str) or not quote.strip() or quote not in note:
                raise Rejected("MISSING_DISCRETE_EVIDENCE", field)
            q_start = note.index(quote)
            q_end = q_start + len(quote)
            conflict = discourse_conflict(note, q_start, q_end, requested_phase)
            if conflict:
                raise Rejected(conflict, field)
            repaired_args[field] = {
                "value": cval,
                "unit": proposal["unit"],
                "evidence_id": f"{field}:{q_start}:{q_end}",
            }
            canonical_inputs[field] = cval
            audit[field] = {
                "action": "verified_discrete_span",
                "proposal": copy.deepcopy(proposal),
                "source": quote,
                "start": q_start,
                "end": q_end,
            }
            continue

        candidates = [o for o in obs_clean if _compatible_v05(field, o)]
        named = [o for o in candidates if o.get("field_hint") == field]
        pool = named if named else candidates
        try:
            asserted = canonical_value_v05(field, proposal["value"], proposal["unit"])
        except (ValueError, TypeError):
            asserted = None

        exact = [
            o for o in pool
            if asserted is not None and same(asserted, canonical_value_v05(field, o["value"], o["unit"]))
        ]
        if exact:
            chosen = exact[0]
            action = "canonical_source_match"
        else:
            raw = [o for o in pool if same(o["value"], proposal["value"])]
            raw = _unique_semantic_v05(field, raw)
            if len(raw) == 1:
                chosen = raw[0]
                action = "source_unit_repair"
            else:
                # Require global uniqueness across all named observations unless explicitly phase-anchored
                all_named = _unique_semantic_v05(field, [o for o in obs_all if o.get("field_hint") == field and _compatible_v05(field, o)])
                sole = _unique_semantic_v05(field, named)
                if len(sole) != 1 or (len(all_named) > 1 and not requested_phase):
                    if all_named and not named:
                        reasons = [discourse_conflict(note, o["start"], o["end"], requested_phase) for o in all_named]
                        first_reason = next((r for r in reasons if r), "AMBIGUOUS_OR_UNSUPPORTED_SOURCE")
                        raise Rejected(first_reason, field)
                    raise Rejected("AMBIGUOUS_OR_UNSUPPORTED_SOURCE", field)
                chosen = sole[0]
                action = "unique_named_source_repair"

        cval = canonical_value_v05(field, chosen["value"], chosen["unit"])
        repaired_args[field] = {
            "value": chosen["value"],
            "unit": chosen["unit"],
            "evidence_id": chosen["id"],
        }
        canonical_inputs[field] = cval
        audit[field] = {
            "action": action,
            "proposal": copy.deepcopy(proposal),
            "source_id": chosen["id"],
            "source": chosen["source"],
            "start": chosen["start"],
            "end": chosen["end"],
            "field_hint": chosen.get("field_hint"),
        }

    try:
        validate_domains_v05(cid, canonical_inputs)
    except ValueError as exc:
        code, _, fld = str(exc).partition(":")
        raise Rejected(code, fld or None) from exc

    raw_result = calculate_v05(cid, canonical_inputs)
    if not math.isfinite(raw_result):
        raise Rejected("NONFINITE_RESULT")
    return {
        "released": True,
        "result": raw_result,
        "call": {"calculator_id": cid, "formula_version": spec["version"], "arguments": repaired_args},
        "canonical_inputs": canonical_inputs,
        "evidence": audit,
        "note_sha256": note_hash,
    }


def note_only_v05(cid: str, note: str, requested_phase: str | None = None) -> dict:
    """Deterministic fallback over uniquely named observations, followed by discourse verification."""
    spec = SPECS_V05[cid]
    if any(f in BOOLEAN_FIELDS or f in INTEGER_SCORE_BOUNDS for f in spec["params"]):
        raise Rejected("DISCRETE_REQUIRES_STRUCTURED_PROPOSAL")
    obs_all = extended_named_observations(note)
    arguments, evidence, canonical_inputs = {}, {}, {}
    for field in spec["params"]:
        # First check all named observations in the note (same conservative uniqueness rule as v0.4)
        all_supported = []
        for obs in obs_all:
            if obs.get("field_hint") != field:
                continue
            try:
                val = canonical_value_v05(field, obs["value"], obs["unit"])
            except (ValueError, OverflowError, TypeError):
                continue
            if not any(same(other[0], val) for other in all_supported):
                all_supported.append((val, obs))
        # Filter out explicitly wrong-person / non-observed spans (e.g. father's weight or target weight)
        subject_status_clean = [
            (val, obs) for val, obs in all_supported
            if discourse_conflict(note, obs["start"], obs["end"], None) not in ("OTHER_PERSON", "NONOBSERVED")
        ]
        if len(subject_status_clean) != 1:
            if len(all_supported) > 0 and len(subject_status_clean) == 0:
                reason = discourse_conflict(note, all_supported[0][1]["start"], all_supported[0][1]["end"], requested_phase)
                raise Rejected(reason or "NONUNIQUE_NAMED_MEASUREMENT", field)
            raise Rejected("NONUNIQUE_NAMED_MEASUREMENT", field)
        cval, obs = subject_status_clean[0]
        # Verify temporal phase discourse conflict on the unique candidate
        t_conflict = discourse_conflict(note, obs["start"], obs["end"], requested_phase)
        if t_conflict:
            raise Rejected(t_conflict, field)
        start, end = obs["start"], obs["end"]
        arguments[field] = {
            "value": obs["value"],
            "unit": obs["unit"],
            "evidence_id": f"{field}:{start}:{end}",
        }
        canonical_inputs[field] = cval
        evidence[field] = {"start": start, "end": end, "source": note[start:end]}

    try:
        validate_domains_v05(cid, canonical_inputs)
    except ValueError as exc:
        code, _, fld = str(exc).partition(":")
        raise Rejected(code, fld or None) from exc

    raw_result = calculate_v05(cid, canonical_inputs)
    if not math.isfinite(raw_result):
        raise Rejected("NONFINITE_RESULT")
    return {
        "released": True,
        "result": raw_result,
        "call": {"calculator_id": cid, "formula_version": spec["version"], "arguments": arguments},
        "canonical_inputs": canonical_inputs,
        "evidence": evidence,
        "note_sha256": hashlib.sha256(note.encode("utf-8")).hexdigest(),
    }


def execute_v05(
    question: str,
    note: str,
    proposal: dict | None = None,
    *,
    use_proposal: bool = True,
    chained_tokens: dict | None = None,
) -> dict:
    """Unified v0.5 MedCalc-Enforce policy with discourse tracking and output-unit normalization."""
    if not isinstance(question, str) or not isinstance(note, str):
        return {"released": False, "reason": "INVALID_INPUT_TEXT", "policy": "v0.5_discourse"}
    if OUTSIDE_OUTPUT.search(question):
        return {"released": False, "reason": "UNSUPPORTED_OUTPUT_STATISTIC", "policy": "v0.5_discourse"}
    try:
        cid = select_calculator_v05(question)
    except Rejected as exc:
        return {"released": False, "reason": str(exc), "policy": "v0.5_discourse"}

    phase = target_phase_v05(question)
    prior = "NO_PROPOSAL"
    if use_proposal and isinstance(proposal, dict):
        prior = "CALCULATOR_MISMATCH"
        if proposal.get("calculator_id") == cid:
            try:
                decision = repair_call_v05(proposal, cid, note, requested_phase=phase, chained_tokens=chained_tokens)
                adj_result, out_unit = resolve_output_unit(cid, decision["result"], question)
                return {
                    **decision,
                    "result": adj_result,
                    "canonical_result": decision["result"],
                    "output_unit": out_unit,
                    "route": "checked_model_proposal",
                    "calculator_id": cid,
                    "requested_phase": phase,
                    "policy": "v0.5_discourse",
                }
            except (ValueError, ArithmeticError, TypeError, KeyError) as exc:
                prior = str(exc)

    try:
        decision = note_only_v05(cid, note, requested_phase=phase)
        adj_result, out_unit = resolve_output_unit(cid, decision["result"], question)
        return {
            **decision,
            "result": adj_result,
            "canonical_result": decision["result"],
            "output_unit": out_unit,
            "route": "named_measurements",
            "calculator_id": cid,
            "proposal_status": prior,
            "requested_phase": phase,
            "policy": "v0.5_discourse",
        }
    except (ValueError, ArithmeticError, TypeError) as exc:
        return {
            "released": False,
            "reason": str(exc),
            "route": "named_measurements",
            "calculator_id": cid,
            "proposal_status": prior,
            "requested_phase": phase,
            "policy": "v0.5_discourse",
        }
