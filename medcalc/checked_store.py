"""Apply the reviewed research policy to the exact snapshot used by the caller.

Use the same connection factory, encounter type and publication API as
medcalc.commit_store. The caller supplies an authenticated encounter identity.
"""
from dataclasses import dataclass
import hashlib
import json
import uuid

from .commit_store import Publication, publish
from .release_policy import execute_reviewed


@dataclass(frozen=True)
class StagedDecision:
    token: str | None = None
    reason: str | None = None


def stage_reviewed(connection, scope, revision, source_digest, question, proposal=None):
    """Stage only a numerical decision derived from the requested local snapshot."""
    if connection.isolation_level is not None or connection.in_transaction:
        raise ValueError("Staging requires a clean autocommit connection")
    snapshot = connection.execute(
        "SELECT revision, body, digest FROM notes WHERE patient=? AND encounter=?",
        (scope.patient, scope.encounter),
    ).fetchone()
    if snapshot is None or snapshot[0] != revision or snapshot[2] != source_digest:
        return StagedDecision(reason="SOURCE_REVISION_CHANGED")
    _, note, digest = snapshot
    if hashlib.sha256(note.encode()).hexdigest() != digest:
        return StagedDecision(reason="SOURCE_DIGEST_MISMATCH")
    decision = execute_reviewed(question, note, proposal)
    if not decision["released"]:
        return StagedDecision(reason=decision["reason"])
    audit_record = {"question": question, "proposal": proposal, "decision": decision}
    staged_token = uuid.uuid4().hex
    connection.execute(
        "INSERT INTO proposals(token, patient, encounter, revision, digest, payload, result) VALUES(?,?,?,?,?,?,?)",
        (staged_token, scope.patient, scope.encounter, revision, digest,
         json.dumps(audit_record, sort_keys=True, allow_nan=False), decision["result"]),
    )
    return StagedDecision(token=staged_token)


def execute_and_publish(connection, scope, revision, source_digest, question, proposal=None):
    """Return a result only after the atomic database publication check succeeds."""
    staged = stage_reviewed(connection, scope, revision, source_digest, question, proposal)
    if staged.token is None:
        return Publication("withheld")
    return publish(connection, scope, staged.token)
