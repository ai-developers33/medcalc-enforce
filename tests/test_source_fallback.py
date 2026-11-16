import unittest

from medcalc.source_fallback import execute, named_observations


class SourceFallbackTests(unittest.TestCase):
    def test_shared_unit_input_and_route(self):
        decision = execute("What is the mean arterial pressure?", "Blood pressure 120/75 mmHg.")
        self.assertEqual(decision["result"], 90)
        self.assertEqual(decision["route"], "named_measurements")

    def test_count_exponents_and_inverse_units_preserve_original_spans(self):
        for exp in ("^5", "⁵", "5"):
            note = f"A 60-year-old man. AST 11 U L−1. ALT 16 U/L. Platelet count of 1.79×10{exp}/µL."
            with self.subTest(exp=exp):
                decision = execute("Fibrosis 4 index?", note)
                self.assertAlmostEqual(decision["result"], 60*11/(179*4))
                for obs in decision["evidence"].values():
                    self.assertEqual(note[obs["start"]:obs["end"]], obs["source"])

    def test_missing_units_and_conflicting_named_values(self):
        for note in ("BP 120/75", "BP 120/75 mmHg. Later BP 110/70 mmHg."):
            self.assertFalse(execute("Mean arterial pressure?", note)["released"])

    def test_multiple_or_unknown_intents(self):
        for question in ("BMI and mean arterial pressure?", "What is the score?"):
            self.assertFalse(execute(question, "Height 1.7 m; weight 60 kg.")["released"])

    def test_explicit_alternate_formula_abstains(self):
        decision = execute("Body surface area using Du Bois?", "Height 1.7 m. Weight 60 kg.")
        self.assertFalse(decision["released"])
        self.assertIn("UNSUPPORTED_FORMULA", decision["reason"])

    def test_postposed_variable_name(self):
        obs = list(named_observations("Measured 2.8 g/dL of serum albumin."))
        self.assertEqual(obs[0]["field_hint"], "albumin")
