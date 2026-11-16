"""Transactional publication of a source-repaired result in one local SQLite store.

The caller supplies authenticated patient and encounter IDs. All note writes and
result publications must use this same store. This module provides neither an
identity provider nor federation with an external EHR.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass

from .source_repair import make_source_packet, repair_call


@dataclass(frozen=True)
class Encounter:
    patient: str
    encounter: str

    def __post_init__(self):
        if not all(isinstance(item, str) and item for item in (self.patient, self.encounter)):
            raise ValueError("Both patient and encounter identifiers are required")


@dataclass(frozen=True)
class Publication:
    status: str
    source_revision: int | None = None
    result: float | None = None


@contextmanager
def connect(path):
    connection = sqlite3.connect(path, isolation_level=None, timeout=10)
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        yield connection
    finally:
        connection.close()


def initialize(connection):
    connection.execute("PRAGMA journal_mode=WAL")
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS notes (
            patient TEXT NOT NULL, encounter TEXT NOT NULL,
            revision INTEGER NOT NULL CHECK (revision > 0),
            body TEXT NOT NULL, digest TEXT NOT NULL,
            PRIMARY KEY (patient, encounter)
        );
        CREATE TABLE IF NOT EXISTS proposals (
            token TEXT PRIMARY KEY NOT NULL, patient TEXT NOT NULL, encounter TEXT NOT NULL,
            revision INTEGER NOT NULL, digest TEXT NOT NULL, payload TEXT NOT NULL,
            result REAL NOT NULL, FOREIGN KEY (patient,encounter) REFERENCES notes
        );
        CREATE TABLE IF NOT EXISTS publications (
            token TEXT PRIMARY KEY NOT NULL REFERENCES proposals(token),
            revision_at_publish INTEGER NOT NULL
        );
        CREATE TRIGGER IF NOT EXISTS immutable_proposal BEFORE UPDATE ON proposals
        BEGIN SELECT RAISE(ABORT, 'staged proposal is immutable'); END;
        CREATE TRIGGER IF NOT EXISTS immutable_publication BEFORE UPDATE ON publications
        BEGIN SELECT RAISE(ABORT, 'publication is immutable'); END;
    """)


def put_note(connection, scope, note):
    """Install a complete note and monotonically increment its encounter revision."""
    digest = hashlib.sha256(note.encode()).hexdigest()
    return connection.execute("""
        INSERT INTO notes VALUES (?, ?, 1, ?, ?)
        ON CONFLICT(patient, encounter) DO UPDATE SET revision=notes.revision+1,
            body=excluded.body, digest=excluded.digest RETURNING revision
    """, (scope.patient, scope.encounter, note, digest)).fetchone()[0]


def stage_call(connection, scope, call):
    """Run the existing repair against a consistent snapshot and retain its evidence."""
    row = connection.execute("""
        SELECT revision, body, digest FROM notes WHERE patient=? AND encounter=?
    """, (scope.patient, scope.encounter)).fetchone()
    if row is None:
        raise KeyError("Encounter source is unavailable")
    revision, note, digest = row
    packet = make_source_packet(call["calculator_id"], note)
    if packet["note_sha256"] != digest:
        raise ValueError("Stored source digest disagrees with the note")
    outcome = repair_call(call, packet, note)
    payload = json.dumps({"proposal":call, "repair":outcome}, sort_keys=True, allow_nan=False)
    token = uuid.uuid4().hex
    connection.execute("INSERT INTO proposals VALUES (?, ?, ?, ?, ?, ?, ?)",
                       (token, scope.patient, scope.encounter, revision, digest, payload, outcome["result"]))
    return token


def publish(connection, scope, token):
    """Check revision and digest in the same statement that exposes the result.

    Previous publications are identified as historical on retries. A withheld
    proposal returns no numerical output. SQLite autocommit is necessary so
    "published" means the write is durable before control returns.
    """
    if connection.isolation_level is not None or connection.in_transaction:
        raise ValueError("Use a clean autocommit connection for publication")
    identity = (token, scope.patient, scope.encounter)
    inserted = connection.execute("""
        INSERT INTO publications (token, revision_at_publish)
        SELECT p.token, n.revision FROM proposals p
          JOIN notes n ON p.patient=n.patient AND p.encounter=n.encounter
        WHERE p.token=? AND p.patient=? AND p.encounter=?
          AND p.revision=n.revision AND p.digest=n.digest
        ON CONFLICT(token) DO NOTHING RETURNING token
    """, identity).fetchall()
    row = connection.execute("""
        SELECT x.revision_at_publish, p.result FROM publications x
        JOIN proposals p ON p.token=x.token
        WHERE p.token=? AND p.patient=? AND p.encounter=?
    """, identity).fetchone()
    if row is None:
        return Publication("withheld")
    if inserted:
        return Publication("published", *row)
    return Publication("previously_published", source_revision=row[0])


def execute_call(connection, scope, call):
    """Prepare and transactionally publish a model-generated calculator call."""
    return publish(connection, scope, stage_call(connection, scope, call))
