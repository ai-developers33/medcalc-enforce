import unittest

from score_execution_policies import evaluate, exact_p, index


class ScoringRegressionTests(unittest.TestCase):
    def test_numerical_coincidence_cannot_rescue_wrong_tool(self):
        reference = {"calculator_id": "6", "lower": "20", "upper": "21"}
        self.assertEqual(evaluate({"released": True, "result": 20.5}, "60", reference), "nonmatching")
        self.assertEqual(evaluate({"released": False}, "6", reference), "unanswered")
        self.assertEqual(evaluate({"released": True, "result": 20.0}, "6", reference), "matching")

    def test_repeated_source_row_cannot_enter_scores_twice(self):
        with self.assertRaises(ValueError):
            index([{"case_id": "source-a"}, {"case_id": "source-a"}], "case_id")

    def test_paired_significance_uses_discordant_cases(self):
        self.assertEqual(exact_p(5,3), 0.7265625)
        self.assertEqual(exact_p(0,0), 1.0)
