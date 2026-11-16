"""Bind calculator arguments to one requested, explicitly labeled timepoint.

The caller supplies its trusted target and source digest. The supported input
is a sectioned text export with one named measurement per line. Preadmission
values, narrative text, relative times and dates require a different adapter.
"""
import hashlib
import math
import re

from .enforcement import POLICIES, Rejected, validate
from .registry import SPECS, calculate, canonical_value
from .source_binding import observations
from .source_repair import same

SUPPORTED_PHASES = frozenset({"admission", "discharge"})
HEADER = re.compile(r"^([A-Za-z][A-Za-z0-9 /_\-]{0,79}):$")
FIELD_NAMES = {
    "age": ("age",), "sex": ("sex",), "height": ("height",),
    "weight": ("weight",), "blood pressure": ("sbp", "dbp"),
    "systolic blood pressure": ("sbp",), "diastolic blood pressure": ("dbp",),
    "heart rate": ("heart_rate",), "qt interval": ("qt",), "alt": ("alt",),
    "ast": ("ast",), "platelets": ("platelets",), "creatinine": ("creatinine",),
    "albumin": ("albumin",), "calcium": ("calcium",), "glucose": ("glucose",),
    "sodium": ("sodium",), "bun": ("bun",), "chloride": ("chloride",),
    "bicarbonate": ("bicarbonate",),
}


def target_lines(note, phase):
    sections = 0
    selected = False
    lines = []
    position = 0
    for line in note.splitlines(keepends=True):
        heading = HEADER.fullmatch(line.strip())
        if heading:
            selected = heading.group(1).casefold() == phase
            sections += int(selected)
        elif selected and line.strip():
            lines.append((position, line.rstrip("\r\n")))
        position += len(line)
    if sections != 1:
        raise Rejected("TIMEPOINT_SECTION_COUNT", phase)
    return lines


def parse_row(label, content, position):
    fields = FIELD_NAMES.get(label)
    if fields is None:
        raise Rejected("UNRECOGNIZED_TIMEPOINT_ROW")
    parsed = observations(content)
    if len(parsed) != len(fields):
        raise Rejected("UNSUPPORTED_MEASUREMENT", label)
    for field, item in zip(fields, parsed):
        if item["start"] != 0 or item["end"] != len(content):
            raise Rejected("UNSUPPORTED_MEASUREMENT", field)
        if item["field_hint"] and item["field_hint"] != field:
            raise Rejected("INCONSISTENT_MEASUREMENT_LABEL", field)
        try:
            value = canonical_value(field, item["value"], item["unit"])
        except (TypeError, ValueError) as exc:
            raise Rejected("UNIT_OR_VALUE", field) from exc
        yield field, value, {
            "value": item["value"], "unit": item["unit"], "start": position,
            "end": position + len(content), "source": content,
        }


def execute_at_timepoint(call, note, *, phase, expected_note_sha256):
    """Compute from one unambiguous phase or raise Rejected with a reason."""
    if not isinstance(note, str) or not isinstance(call, dict):
        raise Rejected("INVALID_TIMEPOINT_REQUEST")
    if not isinstance(phase, str) or phase not in SUPPORTED_PHASES:
        raise Rejected("UNSUPPORTED_REQUESTED_TIMEPOINT")
    digest = hashlib.sha256(note.encode("utf-8")).hexdigest()
    if expected_note_sha256 != digest:
        raise Rejected("SOURCE_CHANGED")
    cid = call.get("calculator_id")
    if not isinstance(cid, str) or cid not in SPECS:
        raise Rejected("UNKNOWN_TOOL")
    if call.get("formula_version") != SPECS[cid]["version"]:
        raise Rejected("FORMULA_VERSION")
    validate(call, {}, {}, POLICIES[1])
    bound = {}
    evidence = {}
    for offset, line in target_lines(note, phase):
        label, separator, raw = line.partition(":")
        if not separator:
            raise Rejected("UNRECOGNIZED_TIMEPOINT_ROW")
        content = raw.strip()
        position = offset + len(label) + 1 + len(raw) - len(raw.lstrip())
        for field, quantity, span in parse_row(label.strip().casefold(), content, position):
            if field not in call["arguments"]:
                continue
            if field in bound and not same(bound[field], quantity):
                raise Rejected("CONFLICTING_VALUES_AT_TIMEPOINT", field)
            if field not in bound:
                bound[field] = quantity
                evidence[field] = span

    arguments = {}
    for field in SPECS[cid]["params"]:
        if field not in evidence:
            raise Rejected("MISSING_AT_TIMEPOINT", field)
        span = evidence[field]
        arguments[field] = {
            "value": span["value"], "unit": span["unit"],
            "evidence_id": f"{phase}:{span['start']}:{span['end']}:{field}",
        }
    repaired = {**call, "arguments": arguments}
    values = validate(repaired, {}, {}, POLICIES[2])
    result = calculate(cid, values)
    if not math.isfinite(result):
        raise Rejected("NONFINITE_RESULT")
    return {
        "released": True, "result": result, "canonical_inputs": values,
        "evidence": evidence, "call": repaired, "timepoint": phase,
        "note_sha256": digest,
    }
