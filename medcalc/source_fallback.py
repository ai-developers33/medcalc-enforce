"""Research execution policies for the ten supported calculator intents.

The note-only policy requires an explicit field association for every quantity.
The combined policy checks the existing model proposal first, then tries the
note-only calculation if the proposal is absent or cannot be executed.
"""
import hashlib
import math
import re

from .enforcement import POLICIES, Rejected, validate
from .registry import SPECS, calculate, canonical_value
from .source_repair import LABELS, make_source_packet, repair_call, role_candidates, same

INTENTS = {
    "3": r"\b(?:CKD[- ]EPI|glomerular filtration rate|eGFR)\b",
    "5": r"\bmean arterial pressure\b",
    "6": r"\b(?:BMI|body mass(?: mass)? index)\b",
    "7": r"\b(?:corrected calcium|calcium correction|albumin.corrected calcium)\b",
    "11": r"\b(?:Bazett|corrected QT|QTc)\b",
    "19": r"\b(?:fibrosis[- ]?4|FIB[- ]?4)\b",
    "26": r"\b(?:corrected sodium|sodium correction|sodium corrected)\b",
    "30": r"\b(?:serum|plasma) osmolality\b",
    "39": r"\banion gap\b",
    "60": r"\b(?:body surface area|BSA)\b",
}
# Known alternate formula specifications require different arithmetic.
ALTERNATE_FORMULAS = {
    "3": r"\b(?:2009|MDRD|cystatin)\b",
    "5": r"\b(?:waveform|area under)\b",
    "7": r"\bionized calcium\b",
    "11": r"\b(?:Fridericia|Framingham|Hodges)\b",
    "26": r"\bKatz\b",
    "39": r"\b(?:with|including|include) (?:serum )?potassium\b",
    "60": r"\b(?:Du\s*Bois|Haycock|Gehan)\b",
}
# Extra forms have an explicit measurement unit printed in the source.
COUNT = re.compile(r"(?<![\w.,+-])(?P<n>\d+(?:\.\d+)?)\s*[×x]\s*10(?:\^([1-9])|([1-9])|([¹²³⁴⁵⁶⁷⁸⁹]))\s*/\s*(?P<vol>[uµμ]L|mm[3³]|L)\b", re.I)
INVERSE = re.compile(r"(?<![\w.,+-])(?P<n>\d+(?:\.\d+)?)\s*(?P<unit>IU|U)\s+L\s*[−⁻-][1¹](?![\w/])", re.I)
POST_LABEL = re.compile(r"^\s+of\s+(?:(?:serum|plasma|blood)\s+)?(" +
                        "|".join(f"(?:{pattern})" for pattern in LABELS.values()) + r")(?![a-z])", re.I)


def select_calculator(question):
    matches = [cid for cid, pattern in INTENTS.items() if re.search(pattern, question, re.I)]
    if len(matches) != 1:
        raise Rejected("UNRESOLVED_CALCULATOR")
    cid = matches[0]
    alternate = ALTERNATE_FORMULAS.get(cid)
    if alternate and re.search(alternate, question, re.I):
        raise Rejected("UNSUPPORTED_FORMULA")
    return cid


def explicit_field(note, start):
    prefix = note[max(0, start - 90):start]
    for field, pattern in LABELS.items():
        if re.search(r"(?<![a-z])(?:" + pattern + r")\s*(?:\)|level|count|was|of|is|at|:|=|\s)*$", prefix, re.I):
            return field
    return None


def named_observations(note):
    extra = []
    for pattern in (COUNT, INVERSE):
        for match in pattern.finditer(note):
            start, end = match.span()
            if re.search(r"\d\s*[-–]\s*$", note[max(0, start-16):start]):
                continue
            value = float(match["n"])
            unit = "U/L"
            if pattern is COUNT:
                exponent = next(group for group in match.groups()[1:4] if group)
                exponent = exponent.translate(str.maketrans("¹²³⁴⁵⁶⁷⁸⁹", "123456789"))
                value *= 10 ** int(exponent)
                unit = "L" if match["vol"].lower() == "l" else "uL"
            extra.append({"value": value, "unit": unit, "start": start, "end": end,
                          "field_hint": explicit_field(note, start)})
    for obs in role_candidates(note):
        if any(x["start"] < obs["end"] and obs["start"] < x["end"] for x in extra):
            continue
        suffix = POST_LABEL.match(note[obs["end"]:obs["end"] + 70])
        if suffix:
            name = suffix.group(1)
            obs["field_hint"] = next(field for field, pattern in LABELS.items()
                                     if re.fullmatch(pattern, name, re.I))
        yield obs
    yield from extra


def note_only(cid, note):
    observations = list(named_observations(note))
    arguments, evidence = {}, {}
    for field in SPECS[cid]["params"]:
        supported = []
        for obs in observations:
            if obs["field_hint"] != field:
                continue
            try:
                value = canonical_value(field, obs["value"], obs["unit"])
            except (ValueError, OverflowError):
                continue
            if not any(same(other[0], value) for other in supported):
                supported.append((value, obs))
        if len(supported) != 1:
            raise Rejected("NONUNIQUE_NAMED_MEASUREMENT", field)
        _, obs = supported[0]
        start, end = obs["start"], obs["end"]
        arguments[field] = {"value": obs["value"], "unit": obs["unit"],
                            "evidence_id": f"{field}:{start}:{end}"}
        evidence[field] = {"start": start, "end": end, "source": note[start:end]}
    call = {"calculator_id": cid, "formula_version": SPECS[cid]["version"], "arguments": arguments}
    normalized = validate(call, {}, {}, POLICIES[2])
    result = calculate(cid, normalized)
    if not math.isfinite(result):
        raise Rejected("NONFINITE_RESULT")
    return {"released": True, "result": result, "call": call, "canonical_inputs": normalized,
            "evidence": evidence, "note_sha256": hashlib.sha256(note.encode()).hexdigest()}


def execute(question, note, proposal=None, *, use_proposal=True):
    """Return an auditable decision. Inputs are benchmark question, note and optional call."""
    if not isinstance(question, str) or not isinstance(note, str):
        return {"released": False, "reason": "INVALID_INPUT_TEXT"}
    try:
        cid = select_calculator(question)
    except Rejected as exc:
        return {"released": False, "reason": str(exc)}
    prior = "NO_PROPOSAL"
    if use_proposal and isinstance(proposal, dict):
        prior = "CALCULATOR_MISMATCH"
        if proposal.get("calculator_id") == cid:
            try:
                decision = repair_call(proposal, make_source_packet(cid, note), note)
                return {**decision, "route": "checked_model_proposal", "calculator_id": cid}
            except (ValueError, ArithmeticError, TypeError, KeyError) as exc:
                prior = str(exc)
    try:
        decision = note_only(cid, note)
    except (ValueError, ArithmeticError, TypeError) as exc:
        decision = {"released": False, "reason": str(exc)}
    return {**decision, "route": "named_measurements", "calculator_id": cid, "proposal_status": prior}
