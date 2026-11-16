import hashlib
from pathlib import Path
import tempfile
import unittest

from medcalc.checked_store import execute_and_publish, stage_reviewed
from medcalc.commit_store import Encounter, connect, initialize, publish, put_note


class IntegratedPublicationTests(unittest.TestCase):
    def test_intervening_edit_and_retry(self):
        note = "Height 180 cm. Weight 81 kg."
        question = "What is the patient's BMI?"
        scope = Encounter("test-patient", "first")
        digest = hashlib.sha256(note.encode()).hexdigest()
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "research.db"
            with connect(db) as reader, connect(db) as writer:
                initialize(reader)
                revision = put_note(writer, scope, note)
                staged = stage_reviewed(reader, scope, revision, digest, question)
                self.assertIsNotNone(staged.token)
                put_note(writer, scope, note.replace("81", "72"))
                self.assertIsNone(publish(reader, scope, staged.token).result)
                self.assertIsNone(execute_and_publish(reader, scope, revision, digest, question).result)
                newest = put_note(writer, scope, note)
                decision = execute_and_publish(reader, scope, newest, digest, question)
                self.assertAlmostEqual(decision.result, 25)

    def test_rejected_semantics_never_creates_a_proposal(self):
        note = "Height 180 cm. Target weight 81 kg."
        scope = Encounter("test-patient", "first")
        with connect(":memory:") as database:
            initialize(database)
            version = put_note(database, scope, note)
            staged = stage_reviewed(database, scope, version, hashlib.sha256(note.encode()).hexdigest(), "BMI?")
            self.assertEqual(staged.reason, "NONOBSERVED")
            self.assertEqual(database.execute("SELECT COUNT(*) FROM proposals").fetchone()[0], 0)
