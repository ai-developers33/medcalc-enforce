"""Field-projected semantic snapshot revalidation at commit and SHA-256 hash-chained audit store (v0.5).

Addresses the 24/108 false withholdings observed under whole-note revision pinning in commit_store.py:
- If notes.revision matches proposals.revision and digest matches, publishes immediately ("published").
- If notes.revision incremented after staging (e.g. an irrelevant clinical addendum or an edit-and-restore),
  re-evaluates execute_v05 inside BEGIN IMMEDIATE on the live snapshot:
  * If canonical inputs, calculator ID, output unit, and result remain invariant and discourse-clean,
    publishes safely ("published_revalidated") without false withholding.
  * If any bound measurement changed, became ambiguous, disappeared, or acquired a subject/timepoint conflict,
    withholds ("withheld", reason="SEMANTIC_DRIFT_AT_COMMIT").
- Appends every stage, publish, revalidation, and withhold decision to an immutable SHA-256 hash-chained
  audit_log table supporting full cryptographic tamper-evident verification.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import math
import sqlite3
import uuid

from .commit_store import Encounter
from .discourse_guard import execute_v05
from .source_repair import same

GENESIS_HASH = "0" * 64


@dataclass(frozen=True)
class SemanticPublication:
    status: str
    staged_revision: int | None = None
    published_revision: int | None = None
    result: float | None = None
    output_unit: str | None = None
    reason: str | None = None
    audit_hash: str | None = None


@contextmanager
def connect_semantic(path: str):
    conn = sqlite3.connect(path, isolation_level=None, timeout=15)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=15000")
        yield conn
    finally:
        conn.close()


def initialize_semantic(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS notes (
            patient TEXT NOT NULL,
            encounter TEXT NOT NULL,
            revision INTEGER NOT NULL CHECK (revision > 0),
            body TEXT NOT NULL,
            digest TEXT NOT NULL,
            PRIMARY KEY (patient, encounter)
        );
        CREATE TABLE IF NOT EXISTS semantic_proposals (
            token TEXT PRIMARY KEY NOT NULL,
            patient TEXT NOT NULL,
            encounter TEXT NOT NULL,
            revision INTEGER NOT NULL,
            digest TEXT NOT NULL,
            question TEXT NOT NULL,
            proposal_json TEXT,
            decision_json TEXT NOT NULL,
            calculator_id TEXT NOT NULL,
            canonical_inputs_json TEXT NOT NULL,
            result REAL NOT NULL,
            output_unit TEXT NOT NULL,
            FOREIGN KEY (patient, encounter) REFERENCES notes(patient, encounter)
        );
        CREATE TABLE IF NOT EXISTS semantic_publications (
            token TEXT PRIMARY KEY NOT NULL REFERENCES semantic_proposals(token),
            staged_revision INTEGER NOT NULL,
            published_revision INTEGER NOT NULL,
            mode TEXT NOT NULL,
            result REAL NOT NULL,
            output_unit TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS audit_log (
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            token TEXT NOT NULL,
            patient TEXT NOT NULL,
            encounter TEXT NOT NULL,
            revision INTEGER,
            reason TEXT,
            prev_hash TEXT NOT NULL,
            event_hash TEXT NOT NULL
        );
        CREATE TRIGGER IF NOT EXISTS immutable_sem_proposal BEFORE UPDATE ON semantic_proposals
        BEGIN SELECT RAISE(ABORT, 'semantic_proposals is immutable'); END;
        CREATE TRIGGER IF NOT EXISTS immutable_sem_publication BEFORE UPDATE ON semantic_publications
        BEGIN SELECT RAISE(ABORT, 'semantic_publications is immutable'); END;
        CREATE TRIGGER IF NOT EXISTS immutable_audit_update BEFORE UPDATE ON audit_log
        BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END;
        CREATE TRIGGER IF NOT EXISTS immutable_audit_delete BEFORE DELETE ON audit_log
        BEGIN SELECT RAISE(ABORT, 'audit_log cannot be deleted'); END;
    """)


def _append_audit_in_tx(
    conn: sqlite3.Connection,
    event_type: str,
    token: str,
    patient: str,
    encounter: str,
    revision: int | None,
    reason: str | None,
) -> str:
    last = conn.execute("SELECT event_hash FROM audit_log ORDER BY seq DESC LIMIT 1").fetchone()
    prev_hash = last[0] if last else GENESIS_HASH
    body = json.dumps(
        {
            "event_type": event_type,
            "token": token,
            "patient": patient,
            "encounter": encounter,
            "revision": revision,
            "reason": reason,
            "prev_hash": prev_hash,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    event_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
    conn.execute(
        "INSERT INTO audit_log(event_type, token, patient, encounter, revision, reason, prev_hash, event_hash) VALUES (?,?,?,?,?,?,?,?)",
        (event_type, token, patient, encounter, revision, reason, prev_hash, event_hash),
    )
    return event_hash


def verify_audit_chain(conn: sqlite3.Connection) -> tuple[bool, int]:
    """Verify every SHA-256 link in audit_log from GENESIS_HASH."""
    rows = conn.execute(
        "SELECT seq, event_type, token, patient, encounter, revision, reason, prev_hash, event_hash FROM audit_log ORDER BY seq ASC"
    ).fetchall()
    expected_prev = GENESIS_HASH
    for _, event_type, token, patient, encounter, revision, reason, prev_hash, event_hash in rows:
        if prev_hash != expected_prev:
            return False, len(rows)
        body = json.dumps(
            {
                "event_type": event_type,
                "token": token,
                "patient": patient,
                "encounter": encounter,
                "revision": revision,
                "reason": reason,
                "prev_hash": prev_hash,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        if hashlib.sha256(body.encode("utf-8")).hexdigest() != event_hash:
            return False, len(rows)
        expected_prev = event_hash
    return True, len(rows)


def put_note_semantic(conn: sqlite3.Connection, scope: Encounter, note: str) -> int:
    digest = hashlib.sha256(note.encode("utf-8")).hexdigest()
    return conn.execute(
        """
        INSERT INTO notes VALUES (?, ?, 1, ?, ?)
        ON CONFLICT(patient, encounter) DO UPDATE SET
            revision = notes.revision + 1,
            body = excluded.body,
            digest = excluded.digest
        RETURNING revision
        """,
        (scope.patient, scope.encounter, note, digest),
    ).fetchall()[0][0]


def stage_semantic(
    conn: sqlite3.Connection,
    scope: Encounter,
    question: str,
    proposal: dict | None = None,
    *,
    expected_revision: int | None = None,
) -> tuple[str | None, str | None]:
    """Stage a discourse-verified calculation on the current snapshot and append an audit record."""
    if conn.isolation_level is not None or conn.in_transaction:
        raise ValueError("Use a clean autocommit connection for staging")
    row = conn.execute(
        "SELECT revision, body, digest FROM notes WHERE patient=? AND encounter=?",
        (scope.patient, scope.encounter),
    ).fetchone()
    token = uuid.uuid4().hex
    if row is None:
        conn.execute("BEGIN IMMEDIATE")
        try:
            _append_audit_in_tx(conn, "stage_rejected", token, scope.patient, scope.encounter, None, "MISSING_NOTE")
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        return None, "MISSING_NOTE"
    revision, note, digest = row
    if expected_revision is not None and revision != expected_revision:
        conn.execute("BEGIN IMMEDIATE")
        try:
            _append_audit_in_tx(conn, "stage_rejected", token, scope.patient, scope.encounter, revision, "REVISION_BEFORE_STAGE")
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        return None, "REVISION_BEFORE_STAGE"
    if hashlib.sha256(note.encode("utf-8")).hexdigest() != digest:
        raise ValueError("Stored digest corrupted")

    decision = execute_v05(question, note, proposal)
    if not decision["released"]:
        conn.execute("BEGIN IMMEDIATE")
        try:
            _append_audit_in_tx(conn, "stage_rejected", token, scope.patient, scope.encounter, revision, decision["reason"])
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        return None, decision["reason"]

    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(
            """
            INSERT INTO semantic_proposals(
                token, patient, encounter, revision, digest, question, proposal_json,
                decision_json, calculator_id, canonical_inputs_json, result, output_unit
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                token,
                scope.patient,
                scope.encounter,
                revision,
                digest,
                question,
                json.dumps(proposal, sort_keys=True) if proposal is not None else None,
                json.dumps(decision, sort_keys=True, allow_nan=False),
                decision["calculator_id"],
                json.dumps(decision["canonical_inputs"], sort_keys=True, allow_nan=False),
                float(decision["result"]),
                decision["output_unit"],
            ),
        )
        _append_audit_in_tx(conn, "staged", token, scope.patient, scope.encounter, revision, "OK")
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return token, None


def _inputs_equal(a: dict, b: dict) -> bool:
    if set(a) != set(b):
        return False
    for k in a:
        if not same(a[k], b[k]):
            return False
    return True


def publish_semantic(
    conn: sqlite3.Connection,
    scope: Encounter,
    token: str,
    *,
    allow_semantic_revalidation: bool = True,
) -> SemanticPublication:
    """Atomically publish a staged calculation, revalidating projected clinical fields if the note changed."""
    if conn.isolation_level is not None or conn.in_transaction:
        raise ValueError("Use a clean autocommit connection for publication")
    conn.execute("BEGIN IMMEDIATE")
    try:
        existing = conn.execute(
            """
            SELECT x.staged_revision, x.published_revision, x.result, x.output_unit
            FROM semantic_publications x
            JOIN semantic_proposals p ON p.token = x.token
            WHERE x.token=? AND p.patient=? AND p.encounter=?
            """,
            (token, scope.patient, scope.encounter),
        ).fetchone()
        if existing is not None:
            ah = _append_audit_in_tx(conn, "idempotent_retry", token, scope.patient, scope.encounter, existing[1], "ALREADY_PUBLISHED")
            conn.execute("COMMIT")
            return SemanticPublication(
                status="previously_published",
                staged_revision=existing[0],
                published_revision=existing[1],
                audit_hash=ah,
            )

        prop = conn.execute(
            """
            SELECT revision, digest, question, proposal_json, calculator_id, canonical_inputs_json, result, output_unit
            FROM semantic_proposals
            WHERE token=? AND patient=? AND encounter=?
            """,
            (token, scope.patient, scope.encounter),
        ).fetchone()
        if prop is None:
            ah = _append_audit_in_tx(conn, "publish_withheld", token, scope.patient, scope.encounter, None, "SCOPE_OR_TOKEN_MISMATCH")
            conn.execute("COMMIT")
            return SemanticPublication(status="withheld", reason="SCOPE_OR_TOKEN_MISMATCH", audit_hash=ah)

        staged_rev, staged_digest, question, proposal_json, cid, inputs_json, staged_result, out_unit = prop
        note_row = conn.execute(
            "SELECT revision, body, digest FROM notes WHERE patient=? AND encounter=?",
            (scope.patient, scope.encounter),
        ).fetchone()
        if note_row is None:
            ah = _append_audit_in_tx(conn, "publish_withheld", token, scope.patient, scope.encounter, None, "NOTE_DELETED")
            conn.execute("COMMIT")
            return SemanticPublication(status="withheld", reason="NOTE_DELETED", audit_hash=ah)

        cur_rev, cur_body, cur_digest = note_row
        if hashlib.sha256(cur_body.encode("utf-8")).hexdigest() != cur_digest:
            conn.execute("ROLLBACK")
            raise ValueError("Live note digest mismatch")

        if cur_rev == staged_rev and cur_digest == staged_digest:
            conn.execute(
                "INSERT INTO semantic_publications VALUES (?, ?, ?, 'exact_snapshot', ?, ?)",
                (token, staged_rev, cur_rev, staged_result, out_unit),
            )
            ah = _append_audit_in_tx(conn, "published", token, scope.patient, scope.encounter, cur_rev, "EXACT_SNAPSHOT")
            conn.execute("COMMIT")
            return SemanticPublication(
                status="published",
                staged_revision=staged_rev,
                published_revision=cur_rev,
                result=staged_result,
                output_unit=out_unit,
                reason="EXACT_SNAPSHOT",
                audit_hash=ah,
            )

        if not allow_semantic_revalidation:
            ah = _append_audit_in_tx(conn, "publish_withheld", token, scope.patient, scope.encounter, cur_rev, "STRICT_REVISION_CHANGED")
            conn.execute("COMMIT")
            return SemanticPublication(
                status="withheld",
                staged_revision=staged_rev,
                published_revision=cur_rev,
                reason="STRICT_REVISION_CHANGED",
                audit_hash=ah,
            )

        # Re-run deterministic discourse + field projection on the updated live snapshot inside BEGIN IMMEDIATE!
        proposal_obj = json.loads(proposal_json) if proposal_json is not None else None
        recheck = execute_v05(question, cur_body, proposal_obj)
        staged_inputs = json.loads(inputs_json)
        if (
            recheck.get("released")
            and recheck.get("calculator_id") == cid
            and recheck.get("output_unit") == out_unit
            and _inputs_equal(staged_inputs, recheck.get("canonical_inputs", {}))
            and math.isclose(staged_result, float(recheck["result"]), rel_tol=1e-9, abs_tol=1e-10)
        ):
            conn.execute(
                "INSERT INTO semantic_publications VALUES (?, ?, ?, 'semantic_revalidated', ?, ?)",
                (token, staged_rev, cur_rev, staged_result, out_unit),
            )
            ah = _append_audit_in_tx(conn, "published_revalidated", token, scope.patient, scope.encounter, cur_rev, "INVARIANT_PROJECTION")
            conn.execute("COMMIT")
            return SemanticPublication(
                status="published_revalidated",
                staged_revision=staged_rev,
                published_revision=cur_rev,
                result=staged_result,
                output_unit=out_unit,
                reason="INVARIANT_PROJECTION",
                audit_hash=ah,
            )

        drift_reason = f"SEMANTIC_DRIFT:{recheck.get('reason', 'VALUE_CHANGED')}"
        ah = _append_audit_in_tx(conn, "publish_withheld", token, scope.patient, scope.encounter, cur_rev, drift_reason)
        conn.execute("COMMIT")
        return SemanticPublication(
            status="withheld",
            staged_revision=staged_rev,
            published_revision=cur_rev,
            reason=drift_reason,
            audit_hash=ah,
        )
    except Exception:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
