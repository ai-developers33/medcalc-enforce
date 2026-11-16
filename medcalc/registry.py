"""Explicit formula versions and unit conversions for ten research calculators.

Formula specifications were checked against MedCalc-Bench-Verified v1.0.8.
The implementation is deliberately independent of the benchmark's executable code.
These functions reproduce benchmark arithmetic, not clinical recommendations.
"""

import math
import re

ALIASES = {
    "sex": "sex", "age": "age", "creatinine": "creatinine",
    "Systolic Blood Pressure": "sbp", "Diastolic Blood Pressure": "dbp",
    "height": "height", "weight": "weight", "Calcium": "calcium",
    "Albumin": "albumin", "Heart Rate or Pulse": "heart_rate",
    "QT Interval": "qt", "Alanine aminotransferase": "alt",
    "Aspartate aminotransferase": "ast", "Platelet count": "platelets",
    "Glucose": "glucose", "Sodium": "sodium", "Blood Urea Nitrogen (BUN)": "bun",
    "Chloride": "chloride", "Bicarbonate": "bicarbonate",
}

CANONICAL = {
    "sex": "category", "age": "years", "creatinine": "mg/dL",
    "sbp": "mmHg", "dbp": "mmHg", "height": "m", "weight": "kg",
    "calcium": "mg/dL", "albumin": "g/dL", "heart_rate": "bpm",
    "qt": "ms", "alt": "U/L", "ast": "U/L", "platelets": "10^9/L",
    "glucose": "mg/dL", "sodium": "mEq/L", "bun": "mg/dL",
    "chloride": "mEq/L", "bicarbonate": "mEq/L",
}

SPECS = {
    "3": {"name": "CKD-EPI 2021 creatinine", "params": ["sex", "age", "creatinine"], "version": "CKD-EPI-2021"},
    "5": {"name": "Mean arterial pressure", "params": ["sbp", "dbp"], "version": "SBP-plus-2DBP-over-3"},
    "6": {"name": "BMI", "params": ["height", "weight"], "version": "kg-over-m2"},
    "7": {"name": "Albumin-corrected calcium", "params": ["albumin", "calcium"], "version": "0.8-coefficient"},
    "11": {"name": "QTc Bazett", "params": ["heart_rate", "qt"], "version": "Bazett"},
    "19": {"name": "FIB-4", "params": ["age", "ast", "alt", "platelets"], "version": "age-AST-platelets-sqrtALT"},
    "26": {"name": "Corrected sodium", "params": ["sodium", "glucose"], "version": "Hillier-2.4"},
    "30": {"name": "Calculated serum osmolality", "params": ["sodium", "bun", "glucose"], "version": "2Na-BUN2.8-glucose18"},
    "39": {"name": "Anion gap without potassium", "params": ["sodium", "chloride", "bicarbonate"], "version": "Na-minus-Cl-HCO3"},
    "60": {"name": "Body surface area", "params": ["height", "weight"], "version": "Mosteller"},
}

def normalized_unit(unit):
    return str(unit).strip().replace("µ", "u").replace("μ", "u").replace(" ", "").lower()

def unit_factor(field, unit):
    """Multiply by this factor to obtain the field's declared canonical unit.

    Mass/molar conversions are analyte-specific. Unknown units are rejected.
    Benchmark platelet units 'L' and 'uL' denote counts per that volume.
    """
    u = normalized_unit(unit)
    simple = {
        "height": {"m": 1, "cm": .01, "mm": .001, "in": .0254, "ft": .3048},
        "weight": {"kg": 1, "g": .001, "lb": .45359237, "lbs": .45359237},
        "age": {"year": 1, "years": 1, "month": 1/12, "months": 1/12, "weeks": 1/52.1429, "days": 1/365},
        "sbp": {"mmhg": 1, "kpa": 7.500616827},
        "dbp": {"mmhg": 1, "kpa": 7.500616827},
        "heart_rate": {"bpm": 1, "beatsperminute": 1, "hz": 60},
        "qt": {"ms": 1, "msec": 1, "s": 1000},
        "alt": {"u/l": 1}, "ast": {"u/l": 1},
        "platelets": {"10^9/l": 1, "l": 1e-9, "ul": .001, "10^3/ul": 1},
    }
    if field in simple:
        if u not in simple[field]:
            raise ValueError(f"unsupported unit {unit!r} for {field}")
        return simple[field][u]
    # Molecular masses match the benchmark's declared analyte definitions.
    masses = {"creatinine": 113.12, "calcium": 40.08, "albumin": 66500,
              "glucose": 180.16, "bun": 28.02, "sodium": 22.99,
              "chloride": 35.45, "bicarbonate": 61.02}
    valence = {"calcium": 2, "sodium": 1, "chloride": 1, "bicarbonate": 1}
    match = re.fullmatch(r"(g|mg|ug|mol|mmol|umol|eq|meq)/(l|dl|ml)", u)
    if not match or field not in masses:
        raise ValueError(f"unsupported unit {unit!r} for {field}")
    numerator, denominator = match.groups()
    per_liter = {"l": 1., "dl": 10., "ml": 1000.}[denominator]
    mass = masses[field]
    if numerator in ("g", "mg", "ug"):
        grams_liter = {"g": 1., "mg": .001, "ug": 1e-6}[numerator] * per_liter
    elif numerator in ("mol", "mmol", "umol"):
        grams_liter = {"mol": 1., "mmol": .001, "umol": 1e-6}[numerator] * mass * per_liter
    else:
        if field not in valence:
            raise ValueError(f"no equivalent conversion defined for {field}")
        grams_liter = {"eq": 1., "meq": .001}[numerator] * mass / valence[field] * per_liter
    if CANONICAL[field] == "mg/dL":
        return grams_liter * 100
    if CANONICAL[field] == "g/dL":
        return grams_liter / 10
    return grams_liter / mass * 1000 * valence[field]

def canonical_value(field, value, unit):
    if field == "sex":
        if unit != "category" or value not in ("Female", "Male"):
            raise ValueError("unsupported coefficient category")
        return value
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("finite numeric value required")
    return float(value) * unit_factor(field, unit)

def map_entities(entities):
    mapped = {}
    for source_key, value in entities.items():
        if source_key not in ALIASES:
            raise ValueError(f"unmapped entity {source_key}")
        key = ALIASES[source_key]
        if key == "sex":
            mapped[key] = {"value": value, "unit": "category"}
        else:
            if not isinstance(value, list) or len(value) != 2:
                raise ValueError(f"unsupported composite quantity {source_key}")
            mapped[key] = {"value": value[0], "unit": value[1]}
    return mapped

def calculate(calculator_id, x):
    """Pure arithmetic, with canonical quantities. No implicit clinical policy."""
    if calculator_id == "3":
        female = x["sex"] == "Female"
        k, a = (.7, -.241) if female else (.9, -.302)
        ratio = x["creatinine"] / k
        return 142 * min(ratio, 1)**a * max(ratio, 1)**(-1.2) * .9938**x["age"] * (1.012 if female else 1)
    if calculator_id == "5": return (x["sbp"] + 2*x["dbp"])/3
    if calculator_id == "6": return x["weight"] / x["height"]**2
    if calculator_id == "7": return x["calcium"] + .8 * (4 - x["albumin"])
    if calculator_id == "11": return x["qt"] / math.sqrt(60 / x["heart_rate"])
    if calculator_id == "19": return x["age"] * x["ast"] / (x["platelets"] * math.sqrt(x["alt"]))
    if calculator_id == "26": return x["sodium"] + .024 * (x["glucose"] - 100)
    if calculator_id == "30": return 2*x["sodium"] + x["bun"]/2.8 + x["glucose"]/18
    if calculator_id == "39": return x["sodium"] - x["chloride"] - x["bicarbonate"]
    if calculator_id == "60": return math.sqrt(x["weight"] * x["height"] * 100 / 3600)
    raise ValueError(f"unknown calculator {calculator_id}")

ALTERNATE_UNITS = {"age": "months", "creatinine": "umol/L", "sbp": "kPa", "dbp": "kPa",
                   "height": "cm", "weight": "lbs", "calcium": "mmol/L", "albumin": "g/L",
                   "heart_rate": "Hz", "qt": "s", "platelets": "uL", "glucose": "mmol/L",
                   "sodium": "mg/dL", "bun": "mmol/L", "chloride": "mg/dL", "bicarbonate": "mmol/dL"}
