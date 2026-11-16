# Commit-time freshness experiment

A separate writer changed the source note between an initial check and publication. The read-then-write baseline published a result computed from a superseded revision in 36 of its 108 trials. The transactional store published zero stale revisions in 108 trials. Twelve of the 36 stale baseline publications returned an outdated numerical value. The 24 others used a superseded revision with the same numerical answer.

| Scheduled event | Baseline publications / 12 | Atomic publications / 12 | Baseline stale revisions / 12 |
|---|---:|---:|---:|
| Stable note | 12 | 12 | 0 |
| Source update before initial check | 0 | 0 | 0 |
| Changed weight after initial check | 12 | 0 | 12 |
| Changed weight then restored original note after initial check | 12 | 0 | 12 |
| Added irrelevant documentation after initial check | 12 | 0 | 12 |
| Updated a different encounter for the same patient | 12 | 12 | 0 |
| Updated the same encounter identifier under another patient | 12 | 12 | 0 |
| Updated the source after publication | 12 | 12 | 0 |
| Requested publication under the wrong encounter | 0 | 0 | 0 |

## Method

Each trial created an isolated SQLite database in WAL mode. The calculator execution connection read a note identified by synthetic patient and encounter identifiers, executed the packaged source-repair method on a BMI proposal, and staged the output and evidence. The writer thread opened a different connection and committed according to the schedule. Event barriers ordered all operations. Height and weight varied across the 12 repetitions of each event, with identical inputs for both methods. No language model, paid service, clinical system or personal record was used.

Both methods received the same initial revision and digest check. The baseline then published the staged result in a separate write. The transactional method used a single conditional insertion to check patient, encounter, revision and digest at publication. The database journal recorded the revision current at insertion. The experiment compared this revision with the staged revision and compared the recorded BMI with an independently computed fixture answer at publication.

Strict revision pinning withholds an otherwise numerically matching result when an unrelated addendum or edit-and-restore supersedes the source. Late edits can invalidate the usefulness of an answer already delivered to a caller. Correctness here refers to the local publication instant. This study covers nine deliberately enforced schedules for one calculator. Repeat counts show reproducibility under these schedules. They do not estimate clinical event frequencies, operational error rates or distributed-system performance. SQLite conditional writes use standard database semantics. The contribution tested here is their application to the existing calculator repair boundary.

## Reproduce

Use Python 3.10+ with SQLite 3.35+ to support SQL RETURNING.

```sh
python3 run_commit_experiment.py --repeats 12
python3 -m unittest discover -s tests -p test_commit_store.py -v
```

The default output directory contains the measured counts and per-trial events. Runtime versions and code digests are in `summary.json`. In `traces.jsonl`, each record contains the ordered publication and update events, the value expected at publication and the result actually written, if any.

## Use from existing calculator code

```python
from medcalc.commit_store import Encounter, connect, execute_call, initialize, put_note

with connect("experiment.sqlite") as db:
    initialize(db)
    scope = Encounter(patient="synthetic-patient", encounter="synthetic-visit")
    put_note(db, scope, "Height 170 cm. Weight 60 kg.")
    # generated_call is the ordinary calculator-call dictionary from the extractor.
    decision = execute_call(db, scope, generated_call)
    if decision.status == "published":
        value = decision.result
```

Use `stage_call(db, scope, generated_call)` followed by `publish(db, scope, token)` when computation and publication happen on different connections. Retries with the same token create at most one publication and return the prior revision without re-releasing its numerical result. An absent, stale, or mismatched-scope proposal yields a withheld decision. Invalid calculator proposals fail the underlying repair before staging.

The invariant assumes every source update and publication goes through this local store. The host application must provide trustworthy identity and an authoritative note. Source revisions cover the whole note. Multi-record transactions, remote EHR synchronization, external alerts, multi-instance failures, process crash tests, causal outcome attribution and timepoint selection within a note are outside this experiment.
