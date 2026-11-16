"""Unit tests for v0.5 discourse guard, expanded 16-calculator registry,
output-unit conversion, bounded diagnostic repair, and semantic commit store."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from medcalc.bounded_repair import execute_bounded_repair, simulate_ungrounded_critic
from medcalc.commit_store import Encounter
from medcalc.discourse_guard import execute_v05
from medcalc.expanded_registry import SPECS_V05, calculate_v05, canonical_value_v05
from medcalc.semantic_commit import (
    connect_semantic,
    initialize_semantic,
    publish_semantic,
    put_note_semantic,
    stage_semantic,
    verify_audit_chain,
)


class TestV05BDCCUpgrades(unittest.TestCase):
    def test_cross_sentence_subject_and_time_inheritance(self):
        # Previously failed in v0.4 extended_cases.json
        r1 = execute_v05(
            "What is the patient's BMI?",
            "The following two adult measurements belong to his brother. Height 180 cm. Weight 90 kg. The patient's own measurements are unavailable.",
        )
        self.assertFalse(r1["released"])
        self.assertIn("OTHER_PERSON", r1["reason"])

        r2 = execute_v05(
            "What was the patient's admission BMI?",
            "Discharge measurements are listed below. Height 180 cm. Weight 90 kg. Admission values are missing.",
        )
        self.assertFalse(r2["released"])
        self.assertIn("OTHER_TIME", r2["reason"])

        # Paragraph reset restores patient scope after blank line
        r3 = execute_v05(
            "What is the patient's BMI?",
            "Family history: Brother is obese. Height 190 cm. Weight 120 kg.\n\nPatient exam: Height 180 cm. Weight 90 kg.",
        )
        self.assertTrue(r3["released"])
        self.assertAlmostEqual(r3["result"], 27.77777777777778, places=6)

    def test_platelet_mm3_and_qtc_seconds_output_unit(self):
        # Resolves official-283 mm^3 notation
        val = canonical_value_v05("platelets", 342000, "mm^3")
        self.assertAlmostEqual(val, 342.0, places=6)
        fib = execute_v05(
            "Calculate the FIB-4 index.",
            "54-year-old patient with AST 62 U/L, ALT 49 U/L, and platelet count 342,000/mm^3.",
        )
        self.assertTrue(fib["released"])
        self.assertAlmostEqual(fib["result"], (54 * 62) / (342.0 * 7.0), places=6)

        # Resolves MedCalc-Pro Bazett QTc in seconds vs ms
        qtc_s = execute_v05("Calculate Bazett QTc in seconds.", "Heart rate 60 bpm. QT interval 420 ms.")
        self.assertTrue(qtc_s["released"])
        self.assertEqual(qtc_s["output_unit"], "s")
        self.assertAlmostEqual(qtc_s["result"], 0.42, places=6)

        qtc_ms = execute_v05("Calculate Bazett QTc.", "Heart rate 60 bpm. QT interval 420 ms.")
        self.assertEqual(qtc_ms["output_unit"], "ms")
        self.assertAlmostEqual(qtc_ms["result"], 420.0, places=6)

    def test_six_expanded_clinical_calculators(self):
        self.assertEqual(len(SPECS_V05), 16)
        # CHA2DS2-VASc: 76yo Female (+2 age, +1 sex) + HTN (+1) + Stroke (+2) = 6
        self.assertEqual(
            calculate_v05("61", {"age": 76, "sex": "Female", "chf": False, "hypertension": True, "stroke_tia": True, "vascular_disease": False, "diabetes": False}),
            6.0,
        )
        # CURB-65: confusion(1) + BUN 24(1) + RR 32(1) + BP 85/55(1) + age 70(1) = 5
        self.assertEqual(
            calculate_v05("62", {"confusion": True, "bun": 24.0, "respiratory_rate": 32.0, "sbp": 85.0, "dbp": 55.0, "age": 70.0}),
            5.0,
        )
        # GCS: E4 V5 M6 = 15; out-of-bounds M7 raises ValueError
        self.assertEqual(calculate_v05("64", {"eye_opening": 4, "verbal_response": 5, "motor_response": 6}), 15.0)
        with self.assertRaises(ValueError):
            canonical_value_v05("motor_response", 7, "points")

    def test_semantic_commit_eliminates_benign_addendum_false_withhold(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "sem.sqlite")
            scope = Encounter("pat-1", "enc-1")
            with connect_semantic(db) as c1, connect_semantic(db) as c2:
                initialize_semantic(c1)
                r0 = put_note_semantic(c1, scope, "Admission vitals: Height 180 cm. Weight 81 kg.")
                tok, err = stage_semantic(c1, scope, "What was the patient's admission BMI?", expected_revision=r0)
                self.assertIsNotNone(tok)
                self.assertIsNone(err)

                # Concurrent addendum does NOT alter height, weight, or discourse context
                put_note_semantic(c2, scope, "Admission vitals: Height 180 cm. Weight 81 kg.\n\nAddendum: Diet order updated.")
                pub = publish_semantic(c1, scope, tok, allow_semantic_revalidation=True)
                self.assertEqual(pub.status, "published_revalidated")
                self.assertAlmostEqual(pub.result, 25.0, places=6)

                # Genuine concurrent weight mutation MUST be blocked
                r_curr = put_note_semantic(c1, scope, "Admission vitals: Height 180 cm. Weight 81 kg.")
                tok2, _ = stage_semantic(c1, scope, "What was the patient's admission BMI?", expected_revision=r_curr)
                put_note_semantic(c2, scope, "Admission vitals: Height 180 cm. Weight 95 kg.")
                pub2 = publish_semantic(c1, scope, tok2, allow_semantic_revalidation=True)
                self.assertEqual(pub2.status, "withheld")
                self.assertTrue(pub2.reason.startswith("SEMANTIC_DRIFT"))

                # Tamper-evident audit log check
                ok_chain, count = verify_audit_chain(c1)
                self.assertTrue(ok_chain)
                self.assertGreaterEqual(count, 4)
                with self.assertRaises(sqlite3.IntegrityError):
                    c1.execute("DELETE FROM audit_log WHERE seq=1")

    def test_bounded_diagnostic_repair(self):
        note = "Height 170 cm. Weight 72.25 kg."
        bad_call = {
            "calculator_id": "6",
            "formula_version": "wrong-version-tag",
            "arguments": {"height": {"value": 170, "unit": "m"}, "weight": {"value": 72.25, "unit": "kg"}},
        }
        k0 = execute_bounded_repair("What is the patient's BMI?", note, bad_call, max_retries=0)
        self.assertFalse(k0["released"])
        k1 = execute_bounded_repair("What is the patient's BMI?", note, bad_call, max_retries=1)
        self.assertTrue(k1["released"])
        self.assertAlmostEqual(k1["result"], 25.0, places=6)
        self.assertEqual(k1["attempts_used"], 1)



    def test_four_model_expansion_manifest_and_selection(self):
        import run_local_four_model_expansion as exp
        self.assertEqual(
            exp.selected_model_ids("phi3.5_mini_q4km", False),
            ["qwen2.5_7b_q4km", "phi3.5_mini_q4km"],
        )
        self.assertEqual(
            exp.selected_model_ids("both", True),
            ["phi3.5_mini_q4km", "llama3.1_8b_q4km"],
        )
        for m_id, meta in exp.EXPANSION_MODELS.items():
            for f in meta["files"]:
                self.assertEqual(len(f["sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
