import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent


class ReviewerFixesV06Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((ROOT / "results/v0_5_bdcc/reviewer_fixes_v06.json").read_text())

    def test_fix1_provenance_and_regex_rescue(self):
        f1 = self.data["fix1_provenance_and_regex_attribution"]
        self.assertEqual(f1["pure_regex_note_only_124"]["matched"], 94)
        self.assertEqual(f1["pure_regex_note_only_124"]["discrete_scores_120_matched"], 0)
        self.assertEqual(f1["pooled_620"]["total_released"], 565)
        self.assertEqual(f1["pooled_620"]["proposal_path_released"], 529)
        self.assertEqual(
            f1["per_model_official_124"]["llama3.1_8b_q4km"]["tiers"]["tier_0_70_named_fallback"]["released"],
            0,
        )

    def test_fix2_frozen_guard_oov_transfer(self):
        f2 = self.data["fix2_zero_tuning_oov_discourse_transfer"]
        with (ROOT / "medcalc/discourse_guard.py").open("rb") as fh1, (ROOT / "medcalc/release_policy.py").open("rb") as fh2:
            dg_sha = hashlib.file_digest(fh1, "sha256").hexdigest()
            rp_sha = hashlib.file_digest(fh2, "sha256").hexdigest()
        self.assertEqual(dg_sha, f2["frozen_code_verification"]["discourse_guard_py_sha256"])
        self.assertEqual(rp_sha, f2["frozen_code_verification"]["release_policy_py_sha256"])
        self.assertEqual(f2["strata"]["adversarial_oov_surface"]["v05_false_release"], 0)
        self.assertEqual(f2["valid_multisection_control"]["v05_unsafe"] if "valid_multisection_control" in f2 else f2["valid_multisection_controls_32"]["v05_unsafe"], 0)

    def test_fix3_residual_11_errors_accounted(self):
        f3 = self.data["fix3_residual_11_of_620_taxonomy"]
        self.assertEqual(f3["total_residual_unsafe"], 11)
        self.assertEqual(len(f3["unique_case_ids"]), 6)

    def test_fix6_clustered_620_stats(self):
        f6 = self.data["fix6_clustered_620_inference"]
        self.assertEqual(f6["n_runs"], 620)
        self.assertEqual(f6["n_independent_patient_clusters"], 124)
        self.assertGreater(f6["delta_agreement_clustered_ci95"][0], 0.05)
        self.assertLess(f6["delta_unsafe_clustered_ci95"][1], -0.10)


if __name__ == "__main__":
    unittest.main()
