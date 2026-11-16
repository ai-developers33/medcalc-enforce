import unittest

from medcalc.release_policy import execute_reviewed


class ReviewedReleaseTests(unittest.TestCase):
    def test_subject_conflict_and_self_control(self):
        for role in ("father", "sibling", "caregiver"):
            with self.subTest(role=role):
                result = execute_reviewed("Patient BMI?", f"Height 180 cm. The {role}'s weight was 90 kg.")
                self.assertEqual(result["reason"], "OTHER_PERSON")
        control = execute_reviewed("Patient BMI?", "His father was present. Patient height 180 cm. His weight was 90 kg.")
        self.assertTrue(control["released"])

    def test_goal_and_observed_weight(self):
        for status in ("target", "ideal", "recommended"):
            with self.subTest(status=status):
                result = execute_reviewed("What is the patient's BMI?", f"Height 180 cm. {status} weight 90 kg.")
                self.assertEqual(result["reason"], "NONOBSERVED")
        self.assertTrue(execute_reviewed("Patient BMI?", "Height 180 cm. Observed weight 90 kg.")["released"])

    def test_time_conflicts_before_and_after_measurement(self):
        for note in ("At discharge, height was 180 cm and weight was 90 kg.",
                     "Height 180 cm. Weight 90 kg at discharge."):
            with self.subTest(note=note):
                self.assertEqual(execute_reviewed("Admission BMI?", note)["reason"], "OTHER_TIME")
        self.assertTrue(execute_reviewed("Admission BMI?", "On admission height 180 cm and weight 90 kg.")["released"])

    def test_statistic_mismatch(self):
        for question in ("What is the BMI percentile?", "What is the change in BMI?", "What is the BMI z-score?"):
            with self.subTest(question=question):
                self.assertEqual(execute_reviewed(question, "Height 180 cm. Weight 90 kg.")["reason"], "UNSUPPORTED_OUTPUT_STATISTIC")
