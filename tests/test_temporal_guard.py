import hashlib
import unittest

from medcalc.enforcement import Rejected
from medcalc.registry import SPECS
from medcalc.temporal_guard import execute_at_timepoint


def digest(note):
    return hashlib.sha256(note.encode("utf-8")).hexdigest()


class TemporalGuardTests(unittest.TestCase):
    def setUp(self):
        self.call = {
            "calculator_id": "6", "formula_version": SPECS["6"]["version"],
            "arguments": {key: {"value": val, "unit": unit, "evidence_id": "proposed"}
                          for key, val, unit in [("height", 2, "m"), ("weight", 100, "kg")]},
        }
        self.note = "Admission:\r\n Height: 2 m\r\n Weight: 80 kg\r\nDischarge:\r\n Height: 2 m\r\n Weight: 100 kg"

    def run_admission(self, note):
        return execute_at_timepoint(self.call, note, phase="admission", expected_note_sha256=digest(note))

    def test_rebinds_wrong_time_and_preserves_duplicate_text_offsets(self):
        result = self.run_admission(self.note)
        self.assertEqual(result["result"], 20)
        for item in result["evidence"].values():
            self.assertEqual(self.note[item["start"]:item["end"]], item["source"])
            self.assertLess(item["end"], self.note.index("Discharge"))
        self.assertEqual(self.call["arguments"]["weight"]["value"], 100)

    def test_scope_ends_at_other_section(self):
        with self.assertRaisesRegex(Rejected, "MISSING_AT_TIMEPOINT:weight"):
            self.run_admission("Admission:\nHeight: 2 m\nHistory:\nWeight: 80 kg")

    def test_conflicting_and_duplicate_sections(self):
        for addition, code in [("Weight: 99 kg", "CONFLICTING_VALUES"), ("Admission:", "SECTION_COUNT")]:
            with self.subTest(code=code), self.assertRaisesRegex(Rejected, code):
                self.run_admission("Admission:\nHeight: 2 m\nWeight: 80 kg\n" + addition)

    def test_equal_measurements_with_different_units(self):
        result = self.run_admission("Admission:\nHeight: 2 m\nHeight: 200 cm\nWeight: 80 kg")
        self.assertEqual(result["result"], 20)

    def test_partial_quantity_and_unsupported_prose_reject(self):
        for content in ["80 kg/m²", "80 kg at follow-up", "80 kg and 81 kg", "previously 80 kg"]:
            with self.subTest(content=content), self.assertRaisesRegex(Rejected, "UNSUPPORTED_MEASUREMENT"):
                self.run_admission("Admission:\nHeight: 2 m\nWeight: " + content)

    def test_previous_digest_cannot_authorize_updated_note(self):
        with self.assertRaisesRegex(Rejected, "SOURCE_CHANGED"):
            execute_at_timepoint(self.call, self.note.replace("80 kg", "82 kg"),
                                 phase="admission", expected_note_sha256=digest(self.note))

    def test_malformed_caller_parameters_reject_consistently(self):
        for call, note, phase in [(None, self.note, "admission"),
                                  (self.call, None, "admission"),
                                  (self.call, self.note, []),
                                  ({**self.call, "calculator_id": {}}, self.note, "admission")]:
            with self.subTest(call=call, note=note, phase=phase), self.assertRaises(Rejected):
                execute_at_timepoint(call, note, phase=phase, expected_note_sha256=digest(self.note))

    def test_unsupported_target_is_rejected(self):
        with self.assertRaisesRegex(Rejected, "UNSUPPORTED_REQUESTED"):
            execute_at_timepoint(self.call, self.note, phase="first", expected_note_sha256=digest(self.note))
