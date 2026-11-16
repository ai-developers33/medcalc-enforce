import copy
import json
import unittest
from pathlib import Path
from medcalc.enforcement import POLICIES, Rejected, enforce
from medcalc.fixtures import make_cases
from medcalc.metrics import summarize
from medcalc.registry import calculate, canonical_value

ROOT = Path(__file__).resolve().parents[1]
FULL = next(p for p in POLICIES if p.name == "B4_commit_revalidation")
STATIC = next(p for p in POLICIES if p.name == "B3_evidence_at_validation")

def run(case, policy=FULL):
    return enforce(case["call"],case["context"],case["before"],case["after"],policy)

class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=[json.loads(s) for s in (ROOT/"data/pilot_rows.jsonl").read_text().splitlines()]
        cls.base=make_cases(next(r for r in cls.rows if r["calculator_id"] == "6"))[0]

    def test_nkf_independent_reference_vectors(self):
        # Rounded reference eGFR values from NKF implementation verification Table S1.
        for age,sex,creatinine,expected in [(18,"Male",.9,127),(18,"Male",.91,125),
                                         (18,"Female",.7,128),(18,"Female",.71,126),
                                         (90,"Male",.5,97),(90,"Male",1.5,44),
                                         (90,"Female",.5,89),(90,"Female",1.5,33)]:
            with self.subTest(age=age,sex=sex,creatinine=creatinine):
                self.assertEqual(round(calculate("3",dict(age=age,sex=sex,creatinine=creatinine))),expected)

    def test_known_unit_quantities(self):
        self.assertAlmostEqual(canonical_value("height",170,"cm"),1.7)
        self.assertAlmostEqual(canonical_value("weight",1000,"g"),1)
        self.assertAlmostEqual(canonical_value("albumin",40,"g/L"),4)
        self.assertAlmostEqual(canonical_value("sodium",140,"mmol/L"),140)
        self.assertAlmostEqual(canonical_value("platelets",150000,"uL"),150)
        self.assertAlmostEqual(canonical_value("calcium",2.5,"mmol/L"),10.02)

    def test_analytes_do_not_share_molar_conversion(self):
        glucose=canonical_value("glucose",1,"mmol/L")
        creatinine=canonical_value("creatinine",1,"mmol/L")
        self.assertNotEqual(glucose,creatinine)
        with self.assertRaises(ValueError): canonical_value("height",12,"mg/dL")

    def test_bool_is_not_a_measurement(self):
        c=copy.deepcopy(self.base);c["call"]["arguments"]["height"]["value"]=True
        with self.assertRaises(Rejected):run(c)

    def test_source_identity_even_if_numeric_value_is_identical(self):
        c=copy.deepcopy(self.base)
        eid=c["call"]["arguments"]["weight"]["evidence_id"]
        c["before"]["observations"][eid]["patient_id"]="another-patient"
        with self.assertRaisesRegex(Rejected,"PATIENT"):run(c)

    def test_late_arrival_requires_revalidation(self):
        c=copy.deepcopy(self.base)
        eid=c["call"]["arguments"]["weight"]["evidence_id"]
        new=copy.deepcopy(c["after"]["observations"][eid]);new.update(id="new-weight",time=99)
        c["after"]["observations"]["new-weight"]=new
        run(c,STATIC)
        with self.assertRaisesRegex(Rejected,"STALE_OBSERVATION"):run(c)

    def test_equal_timestamp_conflict_abstains(self):
        c=copy.deepcopy(self.base)
        eid=c["call"]["arguments"]["weight"]["evidence_id"]
        new=copy.deepcopy(c["before"]["observations"][eid]);new.update(id="conflicting-weight",value=1)
        c["before"]["observations"]["conflicting-weight"]=new
        with self.assertRaisesRegex(Rejected,"AMBIGUOUS_LATEST"):run(c)

    def test_retroactive_query_ignores_future_observation(self):
        c=copy.deepcopy(self.base)
        eid=c["call"]["arguments"]["weight"]["evidence_id"]
        new=copy.deepcopy(c["after"]["observations"][eid]);new.update(id="future-weight",time=101,value=1)
        c["after"]["observations"]["future-weight"]=new
        self.assertEqual(run(c),run(self.base))

    def test_does_not_mutate_payload_and_uses_copied_values(self):
        c=copy.deepcopy(self.base);prior=copy.deepcopy(c)
        values=run(c)
        self.assertEqual(c,prior)
        c["call"]["arguments"]["height"]["value"]=99
        self.assertNotEqual(values["height"],99)

    def test_tampered_trusted_ledger_is_outside_guarantee(self):
        c=copy.deepcopy(self.base)
        field="weight";entry=c["call"]["arguments"][field]
        entry["value"]*=1.25
        for store in (c["before"],c["after"]):
            o=store["observations"][entry["evidence_id"]]
            o["value"],o["unit"]=entry["value"],entry["unit"]
        self.assertEqual(run(c)[field],entry["value"])

    def test_metric_denominators_and_runtime_errors(self):
        rows=[dict(valid=False,status="rejected",numeric_correct=False),
              dict(valid=False,status="returned",numeric_correct=False),
              dict(valid=False,status="runtime_error",numeric_correct=False),
              dict(valid=True,status="rejected",numeric_correct=False),
              dict(valid=True,status="returned",numeric_correct=True)]
        m=summarize(rows)
        self.assertAlmostEqual(m["interception_recall"],1/3)
        self.assertAlmostEqual(m["invalid_execution_attempt_rate"],2/3)
        self.assertAlmostEqual(m["invalid_result_release_rate"],1/3)
        self.assertEqual(m["valid_false_rejection_rate"],.5)
        self.assertEqual(m["precision"],.5)
        self.assertEqual(m["f1"],.4)

if __name__ == "__main__":unittest.main()
