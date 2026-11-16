"""Expanded 16-calculator registry, extended analyte/count units, and output-unit contracts (v0.5).

Preserves medcalc/registry.py untouched for v0.3/v0.4 hash locks while adding:
1. Missing official benchmark unit aliases (e.g. mm^3, count/mm³, cells/uL on platelets for official-283).
2. Explicit output-unit conversion when requested by the clinical query (e.g. Bazett QTc in seconds vs ms).
3. Six discrete/hybrid clinical scores (CHA2DS2-VASc, CURB-65, Wells DVT, GCS, MELD-Na, Cockcroft-Gault)
   alongside the ten continuous calculators.
"""
from __future__ import annotations

import math
import re

from .registry import ALIASES as BASE_ALIASES, CANONICAL as BASE_CANONICAL, SPECS as BASE_SPECS
from .registry import calculate as base_calculate, normalized_unit, unit_factor as base_unit_factor

ALIASES = {
    **BASE_ALIASES,
    "congestive heart failure": "chf",
    "hypertension": "hypertension",
    "prior stroke or tia": "stroke_tia",
    "vascular disease": "vascular_disease",
    "diabetes": "diabetes",
    "confusion": "confusion",
    "respiratory rate": "respiratory_rate",
    "active cancer": "active_cancer",
    "paralysis or immobilization": "immobilization",
    "bedridden >3 days or major surgery": "bedridden_surgery",
    "localized tenderness": "localized_tenderness",
    "entire leg swollen": "entire_leg_swollen",
    "calf swelling >3 cm": "calf_swelling_3cm",
    "pitting edema": "pitting_edema",
    "collateral superficial veins": "collateral_veins",
    "previous dvt": "previous_dvt",
    "alternative diagnosis as likely": "alternative_dx_likely",
    "eye opening": "eye_opening",
    "verbal response": "verbal_response",
    "motor response": "motor_response",
    "bilirubin": "bilirubin",
    "total bilirubin": "bilirubin",
    "inr": "inr",
    "dialysis twice in past week": "dialysis_twice",
}

CANONICAL = {
    **BASE_CANONICAL,
    "chf": "boolean",
    "hypertension": "boolean",
    "stroke_tia": "boolean",
    "vascular_disease": "boolean",
    "diabetes": "boolean",
    "confusion": "boolean",
    "respiratory_rate": "breaths/min",
    "active_cancer": "boolean",
    "immobilization": "boolean",
    "bedridden_surgery": "boolean",
    "localized_tenderness": "boolean",
    "entire_leg_swollen": "boolean",
    "calf_swelling_3cm": "boolean",
    "pitting_edema": "boolean",
    "collateral_veins": "boolean",
    "previous_dvt": "boolean",
    "alternative_dx_likely": "boolean",
    "eye_opening": "points",
    "verbal_response": "points",
    "motor_response": "points",
    "bilirubin": "mg/dL",
    "inr": "ratio",
    "dialysis_twice": "boolean",
}

DISCRETE_SPECS = {
    "61": {
        "name": "CHA2DS2-VASc stroke risk score",
        "params": ["age", "sex", "chf", "hypertension", "stroke_tia", "vascular_disease", "diabetes"],
        "version": "CHA2DS2-VASc-2010",
        "kind": "rule_score",
        "default_output_unit": "points",
    },
    "62": {
        "name": "CURB-65 pneumonia severity score",
        "params": ["confusion", "bun", "respiratory_rate", "sbp", "dbp", "age"],
        "version": "CURB-65-Lim-2003",
        "kind": "rule_score",
        "default_output_unit": "points",
    },
    "63": {
        "name": "Wells score for DVT",
        "params": [
            "active_cancer", "immobilization", "bedridden_surgery", "localized_tenderness",
            "entire_leg_swollen", "calf_swelling_3cm", "pitting_edema", "collateral_veins",
            "previous_dvt", "alternative_dx_likely",
        ],
        "version": "Wells-DVT-2003",
        "kind": "rule_score",
        "default_output_unit": "points",
    },
    "64": {
        "name": "Glasgow Coma Scale (GCS)",
        "params": ["eye_opening", "verbal_response", "motor_response"],
        "version": "GCS-Teasdale-1974",
        "kind": "rule_score",
        "default_output_unit": "points",
    },
    "65": {
        "name": "MELD-Na (OPTN 2016)",
        "params": ["bilirubin", "inr", "creatinine", "sodium", "dialysis_twice"],
        "version": "MELD-Na-OPTN-2016",
        "kind": "hybrid_score",
        "default_output_unit": "points",
    },
    "66": {
        "name": "Cockcroft-Gault creatinine clearance",
        "params": ["sex", "age", "weight", "creatinine"],
        "version": "Cockcroft-Gault-1976",
        "kind": "equation",
        "default_output_unit": "mL/min",
    },
}

DEFAULT_OUTPUT_UNITS = {
    "3": "mL/min/1.73m^2",
    "5": "mmHg",
    "6": "kg/m^2",
    "7": "mg/dL",
    "11": "ms",
    "19": "index",
    "26": "mEq/L",
    "30": "mOsm/kg",
    "39": "mEq/L",
    "60": "m^2",
}

SPECS_V05 = {
    **{
        cid: {**spec, "kind": "equation", "default_output_unit": DEFAULT_OUTPUT_UNITS[cid]}
        for cid, spec in BASE_SPECS.items()
    },
    **DISCRETE_SPECS,
}

BOOLEAN_FIELDS = {field for field, unit in CANONICAL.items() if unit == "boolean"}
INTEGER_SCORE_BOUNDS = {
    "eye_opening": (1, 4),
    "verbal_response": (1, 5),
    "motor_response": (1, 6),
}


def unit_factor_v05(field: str, unit: str) -> float:
    """Extend unit_factor with missing official count-volume spellings and new analytes."""
    u = normalized_unit(unit).replace("³", "^3")
    if field == "platelets":
        platelet_aliases = {
            "10^9/l": 1.0,
            "x10^9/l": 1.0,
            "10^3/ul": 1.0,
            "x10^3/ul": 1.0,
            "10^3/mm^3": 1.0,
            "10^3/mm3": 1.0,
            "k/ul": 1.0,
            "k/mm^3": 1.0,
            "k/mm3": 1.0,
            "l": 1e-9,
            "/l": 1e-9,
            "cells/l": 1e-9,
            "count/l": 1e-9,
            "ul": 0.001,
            "/ul": 0.001,
            "cells/ul": 0.001,
            "count/ul": 0.001,
            "mm^3": 0.001,
            "mm3": 0.001,
            "/mm^3": 0.001,
            "/mm3": 0.001,
            "count/mm^3": 0.001,
            "count/mm3": 0.001,
            "cells/mm^3": 0.001,
            "cells/mm3": 0.001,
            "percubicmillimeter": 0.001,
            "percubicmillimetre": 0.001,
        }
        if u in platelet_aliases:
            return platelet_aliases[u]
    if field == "respiratory_rate":
        if u in {"breaths/min", "breathsperminute", "/min", "rpm", "min^-1", "breaths/minute"}:
            return 1.0
        raise ValueError(f"unsupported unit {unit!r} for respiratory_rate")
    if field == "inr":
        if u in {"ratio", "unitless", "inr", "1", ""}:
            return 1.0
        raise ValueError(f"unsupported unit {unit!r} for inr")
    if field == "bilirubin":
        # Molecular mass of bilirubin C33H36N4O6 = 584.66 g/mol -> 1 mg/dL = 17.104 umol/L
        match = re.fullmatch(r"(g|mg|ug|mol|mmol|umol)/(l|dl|ml)", u)
        if not match:
            raise ValueError(f"unsupported unit {unit!r} for bilirubin")
        num, den = match.groups()
        per_l = {"l": 1.0, "dl": 10.0, "ml": 1000.0}[den]
        mass = 584.66
        if num in ("g", "mg", "ug"):
            g_per_l = {"g": 1.0, "mg": 0.001, "ug": 1e-6}[num] * per_l
        else:
            g_per_l = {"mol": 1.0, "mmol": 0.001, "umol": 1e-6}[num] * mass * per_l
        return g_per_l * 100.0  # canonical mg/dL
    return base_unit_factor(field, unit)


def canonical_value_v05(field: str, value, unit: str):
    """Canonicalize continuous, categorical, boolean, and bounded-integer inputs."""
    if field == "sex":
        if unit != "category" or value not in ("Female", "Male"):
            raise ValueError("unsupported sex category")
        return value
    if field in BOOLEAN_FIELDS:
        if unit not in ("boolean", "category"):
            raise ValueError(f"unsupported boolean unit {unit!r} for {field}")
        if isinstance(value, bool):
            return value
        if isinstance(value, int) and value in (0, 1):
            return bool(value)
        if isinstance(value, str) and value.strip().lower() in ("true", "yes", "present", "false", "no", "absent"):
            return value.strip().lower() in ("true", "yes", "present")
        raise ValueError(f"boolean value required for {field}")
    if field in INTEGER_SCORE_BOUNDS:
        if unit not in ("points", "score", "category"):
            raise ValueError(f"unsupported score unit {unit!r} for {field}")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"finite integer score required for {field}")
        ival = int(value)
        if float(value) != float(ival):
            raise ValueError(f"non-integer subscore {value!r} for {field}")
        lo, hi = INTEGER_SCORE_BOUNDS[field]
        if not (lo <= ival <= hi):
            raise ValueError(f"{field} score {ival} outside [{lo}, {hi}]")
        return ival
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("finite numeric value required")
    return float(value) * unit_factor_v05(field, unit)


def validate_domains_v05(cid: str, values: dict) -> None:
    """Enforce arithmetic domains, physiological coupling, and formula applicability."""
    if cid not in SPECS_V05:
        raise ValueError(f"unknown calculator {cid}")
    for field, val in values.items():
        if field == "sex" or field in BOOLEAN_FIELDS or field in INTEGER_SCORE_BOUNDS:
            continue
        if val <= 0:
            raise ValueError(f"POSITIVE_DOMAIN:{field}")
    if cid in ("5", "62") and values["sbp"] < values["dbp"]:
        raise ValueError("PRESSURE_ORDER:")
    if cid == "3" and values["age"] < 18:
        raise ValueError("ADULT_EQUATION:age")
    if cid == "66" and values["age"] < 18:
        raise ValueError("ADULT_EQUATION:age")


def calculate_v05(cid: str, x: dict) -> float:
    """Compute canonical calculator result across all 16 supported calculators."""
    if cid in BASE_SPECS:
        return float(base_calculate(cid, x))
    if cid == "61":  # CHA2DS2-VASc
        pts = 0
        if x["chf"]:
            pts += 1
        if x["hypertension"]:
            pts += 1
        if x["age"] >= 75:
            pts += 2
        elif x["age"] >= 65:
            pts += 1
        if x["diabetes"]:
            pts += 1
        if x["stroke_tia"]:
            pts += 2
        if x["vascular_disease"]:
            pts += 1
        # Sc (female sex) adds 1 point; note 0-point male / 1-point lone-female convention matches standard sum
        if x["sex"] == "Female":
            pts += 1
        return float(pts)
    if cid == "62":  # CURB-65
        pts = 0
        if x["confusion"]:
            pts += 1
        # BUN > 19 mg/dL corresponds to Urea > 7 mmol/L (7 * 2.801 = 19.6 mg/dL; standard US cutoff > 19 mg/dL)
        if x["bun"] > 19.0:
            pts += 1
        if x["respiratory_rate"] >= 30.0:
            pts += 1
        if x["sbp"] < 90.0 or x["dbp"] <= 60.0:
            pts += 1
        if x["age"] >= 65.0:
            pts += 1
        return float(pts)
    if cid == "63":  # Wells DVT
        pts = (
            int(x["active_cancer"])
            + int(x["immobilization"])
            + int(x["bedridden_surgery"])
            + int(x["localized_tenderness"])
            + int(x["entire_leg_swollen"])
            + int(x["calf_swelling_3cm"])
            + int(x["pitting_edema"])
            + int(x["collateral_veins"])
            + int(x["previous_dvt"])
            - (2 if x["alternative_dx_likely"] else 0)
        )
        return float(pts)
    if cid == "64":  # GCS
        return float(x["eye_opening"] + x["verbal_response"] + x["motor_response"])
    if cid == "65":  # MELD-Na (OPTN 2016)
        bili = max(1.0, float(x["bilirubin"]))
        inr = max(1.0, float(x["inr"]))
        cr = 4.0 if x["dialysis_twice"] else min(4.0, max(1.0, float(x["creatinine"])))
        meld_i = 0.957 * math.log(cr) + 0.378 * math.log(bili) + 1.120 * math.log(inr) + 0.643
        meld = round(meld_i * 10.0)
        if meld > 11:
            na = min(137.0, max(125.0, float(x["sodium"])))
            meld_na = meld + 1.32 * (137.0 - na) - (0.033 * meld * (137.0 - na))
            meld = round(meld_na)
        return float(min(40, max(6, int(meld))))
    if cid == "66":  # Cockcroft-Gault CrCl
        crcl = ((140.0 - x["age"]) * x["weight"]) / (72.0 * x["creatinine"])
        if x["sex"] == "Female":
            crcl *= 0.85
        return float(crcl)
    raise ValueError(f"unknown calculator {cid}")


SECONDS_REQUEST = re.compile(
    r"\b(?:in\s+seconds?|in\s+sec\b|\(\s*s\s*\)|\(\s*sec(?:onds?)?\s*\)|expressed\s+in\s+seconds?)\b",
    re.I,
)
MILLISECONDS_REQUEST = re.compile(
    r"\b(?:in\s+milliseconds?|in\s+ms(?:ec)?\b|\(\s*ms(?:ec)?\s*\))\b",
    re.I,
)


def resolve_output_unit(cid: str, result: float, question: str) -> tuple[float, str]:
    """Honor explicit output-unit requests (e.g. QTc in seconds vs milliseconds)."""
    default_unit = SPECS_V05[cid]["default_output_unit"]
    if cid == "11" and isinstance(question, str):
        if SECONDS_REQUEST.search(question) and not MILLISECONDS_REQUEST.search(question):
            return result / 1000.0, "s"
    return result, default_unit
