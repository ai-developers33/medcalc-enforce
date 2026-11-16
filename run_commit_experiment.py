"""Controlled SQLite two-connection experiment. Uses synthetic inputs and no LLM."""
import argparse
import hashlib
import json
import math
import platform
import sqlite3
import tempfile
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

from medcalc.commit_store import Encounter, connect, initialize, publish, put_note, stage_call
from medcalc.registry import SPECS

ROOT = Path(__file__).resolve().parent
SCHEDULES = ("stable", "changed_before_check", "changed_after_check", "change_then_restore",
             "irrelevant_addendum", "other_encounter", "other_patient", "changed_after_publish",
             "wrong_destination")
READ_THEN_WRITE = "read_then_write"
ATOMIC = "atomic_publish"


def initial_check(connection, scope, token):
    return bool(connection.execute("""
        SELECT 1 FROM proposals p JOIN notes n
          ON p.patient=n.patient AND p.encounter=n.encounter
        WHERE p.token=? AND p.patient=? AND p.encounter=?
          AND p.revision=n.revision AND p.digest=n.digest
    """, (token, scope.patient, scope.encounter)).fetchone())


def publish_without_recheck(connection, token):
    # Comparator only. Audit the head revision actually present at insertion.
    connection.execute("""
        INSERT INTO publications SELECT p.token, n.revision FROM proposals p
        JOIN notes n ON p.patient=n.patient AND p.encounter=n.encounter WHERE p.token=?
    """, (token,))


def trial(database, schedule, method, repeat):
    scope = Encounter("P1", "V1")
    other_visit = Encounter("P1", "V2")
    other_patient = Encounter("P2", "V1")
    height, weight = 160 + repeat % 20, 60 + repeat % 17
    original = f"Height {height} cm. Weight {weight} kg."
    replacement = f"Height {height} cm. Weight {weight + 12} kg."
    call = {"calculator_id":"6","formula_version":SPECS["6"]["version"],"arguments":{
        "height":{"value":height,"unit":"cm"},"weight":{"value":weight,"unit":"kg"}}}
    events = []
    allow_writer = Event()

    def update():
        if not allow_writer.wait(10):
            raise TimeoutError("Writer never received the scheduled boundary")
        with connect(database) as writer:
            if schedule in {"stable", "wrong_destination"}:
                return []
            target = {"other_patient":other_patient, "other_encounter":other_visit}.get(schedule,scope)
            new_note = original + " Documentation reviewed." if schedule=="irrelevant_addendum" else replacement
            revisions = [put_note(writer,target,new_note)]
            if schedule=="change_then_restore":
                revisions.append(put_note(writer,target,original))
            return [{"event":"note_update","scope":[target.patient,target.encounter],"revision":r}
                    for r in revisions]

    with connect(database) as evaluator:
        initialize(evaluator)
        for encounter in (scope,other_visit,other_patient):
            put_note(evaluator,encounter,original)
        token = stage_call(evaluator,scope,call)
        events.append({"event":"staged","revision":1})
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(update)
            def run_writer():
                allow_writer.set()
                events.extend(future.result(timeout=12))
            if schedule=="changed_before_check":
                run_writer()
            destination = other_visit if schedule=="wrong_destination" else scope
            ready = initial_check(evaluator,destination,token)
            events.append({"event":"precheck","accepted":ready})
            if schedule not in {"changed_before_check","changed_after_publish"}:
                run_writer()
            if method==ATOMIC:
                # Always exercise the actual authority even if the advisory precheck failed.
                status = publish(evaluator,destination,token).status
            elif ready:
                publish_without_recheck(evaluator,token)
                status = "published"
            else:
                status = "withheld"
            row = evaluator.execute("""
                SELECT p.revision, x.revision_at_publish, p.result
                FROM proposals p JOIN publications x USING(token) WHERE p.token=?
            """,(token,)).fetchone()
            events.append({"event":"publication","status":status,
                           "current_revision":row[1] if row else None})
            if schedule=="changed_after_publish":
                run_writer()
    released = row is not None
    assert released == (status=="published")
    stale = released and row[0]!=row[1]
    current_weight = weight+12 if schedule in {"changed_before_check","changed_after_check"} else weight
    expected_number = current_weight/(height/100)**2
    numerically_outdated = released and not math.isclose(row[2],expected_number,rel_tol=1e-10)
    return {"schedule":schedule,"method":method,"repeat":repeat,"events":events,
            "released":released,"stale_revision":stale,"numerically_outdated":numerically_outdated,
            "expected_at_publish":expected_number,"recorded_result":row[2] if row else None}


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--repeats",type=int,default=12)
    cli.add_argument("--output",type=Path,default=ROOT/"results"/"commit_publication")
    args=cli.parse_args()
    if args.repeats<1:
        cli.error("--repeats must be positive")
    traces=[]
    with tempfile.TemporaryDirectory() as tmp:
        for repeat in range(args.repeats):
            for schedule in SCHEDULES:
                for method in (READ_THEN_WRITE,ATOMIC):
                    db=Path(tmp)/f"{repeat}-{schedule}-{method}.db"
                    traces.append(trial(db,schedule,method,repeat))
    by_schedule=defaultdict(lambda:defaultdict(Counter))
    totals=defaultdict(Counter)
    for record in traces:
        counts={"trials":1, "released":int(record["released"]),
                "withheld":int(not record["released"]), "stale_revision":int(record["stale_revision"]),
                "numerically_outdated":int(record["numerically_outdated"])}
        by_schedule[record["schedule"]][record["method"]].update(counts)
        totals[record["method"]].update(counts)
    summary={"fixture":"synthetic BMI measurements","repeats_per_schedule":args.repeats,
             "schedules":by_schedule,"total":totals,
             "runtime":{"python":platform.python_version(),"sqlite":sqlite3.sqlite_version},
             "code_sha256":{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
                 for name in ("medcalc/commit_store.py","medcalc/source_repair.py","run_commit_experiment.py")},
             "scope":"Deterministically ordered local SQLite operations, not sampled workload rates."}
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/"traces.jsonl").write_text("".join(json.dumps(r)+"\n" for r in traces))
    (args.output/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    print(json.dumps(totals,indent=2))


if __name__=="__main__":
    main()
