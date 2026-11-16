import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from threading import Barrier
import unittest

from medcalc.commit_store import Encounter, connect, execute_call, initialize, publish, put_note, stage_call
from medcalc.registry import SPECS
from run_commit_experiment import ATOMIC, READ_THEN_WRITE, trial


class CommitStoreTests(unittest.TestCase):
    def setUp(self):
        directory=TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root=Path(directory.name)
        self.database=self.root/"publication.db"
        self.scope=Encounter("P","A")
        self.note="Height 170 cm. Weight 60 kg."
        self.call={"calculator_id":"6","formula_version":SPECS["6"]["version"],"arguments":{
            "height":{"value":170,"unit":"m"},"weight":{"value":60,"unit":"kg"}}}
        with connect(self.database) as db:
            initialize(db)
            put_note(db,self.scope,self.note)

    def test_normal_entry_repairs_and_records_evidence(self):
        with connect(self.database) as db:
            result=execute_call(db,self.scope,self.call)
            self.assertEqual(result.status,"published")
            self.assertAlmostEqual(result.result,60/1.7**2)
            audit=json.loads(db.execute("SELECT payload FROM proposals").fetchone()[0])
            self.assertEqual(audit["repair"]["evidence"]["height"]["action"],"source_unit_repair")

    def test_immutable_staging_and_rejected_input(self):
        with connect(self.database) as db:
            token=stage_call(db,self.scope,self.call)
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("UPDATE proposals SET result=0 WHERE token=?",(token,))
            invalid=dict(self.call,formula_version="unknown")
            with self.assertRaises(ValueError):
                stage_call(db,self.scope,invalid)
            self.assertEqual(db.execute("SELECT count(*) FROM proposals").fetchone()[0],1)
            self.assertEqual(db.execute("SELECT count(*) FROM publications").fetchone()[0],0)

    def test_reject_wrong_identity_even_when_body_and_revision_equal(self):
        with connect(self.database) as db:
            token=stage_call(db,self.scope,self.call)
            for wrong in [Encounter("Q","A"),Encounter("P","B")]:
                put_note(db,wrong,self.note)
                self.assertEqual(publish(db,wrong,token).status,"withheld")
            self.assertEqual(publish(db,self.scope,token).status,"published")

    def test_reject_changed_and_restored_note(self):
        with connect(self.database) as db:
            token=stage_call(db,self.scope,self.call)
            put_note(db,self.scope,self.note.replace("60","70"))
            put_note(db,self.scope,self.note)
            self.assertEqual(publish(db,self.scope,token).status,"withheld")
            self.assertEqual(db.execute("SELECT count(*) FROM publications").fetchone()[0],0)

    def test_simultaneous_publish_is_idempotent_and_retry_tracks_old_revision(self):
        with connect(self.database) as db:
            token=stage_call(db,self.scope,self.call)
        barrier=Barrier(2)
        def attempt():
            with connect(self.database) as db:
                barrier.wait(timeout=5)
                return publish(db,self.scope,token).status
        with ThreadPoolExecutor(max_workers=2) as pool:
            first=pool.submit(attempt)
            second=pool.submit(attempt)
            self.assertCountEqual([first.result(timeout=10),second.result(timeout=10)],
                                  ["published","previously_published"])
        with connect(self.database) as db:
            put_note(db,self.scope,self.note.replace("60","70"))
            old=publish(db,self.scope,token)
            self.assertEqual((old.status,old.source_revision,old.result),("previously_published",1,None))
            self.assertEqual(db.execute("SELECT count(*) FROM publications").fetchone()[0],1)

    def test_caller_transaction_cannot_claim_durable_publication(self):
        with connect(self.database) as db:
            token=stage_call(db,self.scope,self.call)
            db.execute("BEGIN")
            with self.assertRaises(ValueError):
                publish(db,self.scope,token)
            db.rollback()
            self.assertEqual(db.execute("SELECT count(*) FROM publications").fetchone()[0],0)

    def test_concurrent_change_reproduces_stale_publication_only_in_comparator(self):
        schedule="changed_after_check"
        for method,expected in [(READ_THEN_WRITE,True),(ATOMIC,False)]:
            r=trial(self.root/f"{method}.db",schedule,method,1)
            self.assertEqual((r["stale_revision"],r["numerically_outdated"]),(expected,expected))


if __name__=="__main__":
    unittest.main()
