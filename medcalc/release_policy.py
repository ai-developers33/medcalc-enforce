"""Conservative textual checks on a candidate result before it is returned.

The checks recognize explicit conflicting cues local to the selected evidence.
Unmarked or implicit subject, measurement status and time remain unresolved.
"""
import re

from .source_fallback import execute

OTHER_PERSON = re.compile(
    r"\b(?:father|mother|son|daughter|sister|brother|spouse|husband|wife|"
    r"sibling|partner|caregiver|grandfather|grandmother|twin)\b", re.I
)
PATIENT = re.compile(r"\b(?:the |our )?patient(?:['’]s)?\b", re.I)
NONOBSERVED = re.compile(
    r"\b(?:target|goal|ideal|recommended|predicted|hypothetical|proposed|desired)\b", re.I
)
OBSERVED = re.compile(r"\b(?:actual|measured|observed)\b", re.I)
# Honor negation of an otherwise positive status marker.
NEGATED = re.compile(r"\b(?:not|never)\s+(?:measured|observed|recorded)\b", re.I)
ADMISSION = re.compile(
    r"\b(?:admission|(?:first|initially) admitted|on presentation|at presentation|"
    r"before (?:any )?treatment|prior to (?:any )?treatment)\b", re.I
)
LATER = re.compile(
    r"\b(?:discharge|follow[- ]?up|after (?:initial )?treatment|"
    r"post[- ]?treatment|later|hospital day [2-9]\d*)\b", re.I
)
OUTSIDE_OUTPUT = re.compile(
    r"\b(?:percentiles?|centiles?|z[- ]?scores?|standard deviation score|"
    r"percentage change|percent change|change in|difference in)\b", re.I
)
BREAK = re.compile(r"[;\n]|[.!?](?=\s|$)")
POSTQUALIFIER = re.compile(
    r"^\s*(?:(?:at|on|after|before|prior to|during|in|for|as|of)\b\s*|\()"
    r"[^,;.\n]{0,48}", re.I
)


def _latest(text, *labeled_patterns):
    """Return the label of the last explicit cue inside the measurement's clause."""
    hits = [(m.start(), label) for label, pattern in labeled_patterns for m in pattern.finditer(text)]
    return max(hits)[1] if hits else None


def _target_phase(question):
    early = bool(ADMISSION.search(question))
    late = bool(LATER.search(question))
    return "admission" if early and not late else ("later" if late and not early else None)


def _scope(note, start, end):
    before = note[:start]
    boundary = next((m.end() for m in reversed(list(BREAK.finditer(before)))), 0)
    prefix = before[boundary:]
    qualifier = POSTQUALIFIER.match(note[end:end + 64])
    # A tail beginning "for the father" or "at discharge" qualifies the actual
    # selected number. Adjacent text after an ordinary sentence boundary does not.
    return prefix + " " + (qualifier.group(0) if qualifier else "")


def _conflict(scope, phase):
    if _latest(scope, ("other", OTHER_PERSON), ("patient", PATIENT)) == "other":
        return "OTHER_PERSON"
    if NEGATED.search(scope) or _latest(scope, ("nonobserved", NONOBSERVED), ("observed", OBSERVED)) == "nonobserved":
        return "NONOBSERVED"
    observed = _latest(scope, ("admission", ADMISSION), ("later", LATER))
    if phase and observed and observed != phase:
        return "OTHER_TIME"
    return None


def execute_reviewed(question, note, proposal=None):
    """Apply the frozen candidate calculator and withhold explicitly conflicting evidence."""
    if isinstance(question, str) and OUTSIDE_OUTPUT.search(question):
        return {"released": False, "reason": "UNSUPPORTED_OUTPUT_STATISTIC", "policy": "reviewed"}
    result = execute(question, note, proposal)
    if not result["released"]:
        return {**result, "policy": "reviewed"}
    phase = _target_phase(question)
    for field, evidence in result["evidence"].items():
        start, end = evidence["start"], evidence["end"]
        if not (0 <= start < end <= len(note)) or note[start:end] != evidence["source"]:
            reason = "SOURCE_SPAN_MISMATCH"
        else:
            reason = _conflict(_scope(note, start, end), phase)
        if reason:
            return {"released": False, "reason": reason, "field": field,
                    "source_span": [start, end], "policy": "reviewed",
                    "calculator_id": result["calculator_id"], "route": result["route"]}
    return {**result, "policy": "reviewed"}
