"""Durable intent ledger; contains no bearer, transcript, audio or answer."""
import sqlite3
import time
import uuid
from pathlib import Path

TERMINAL = {'completed', 'failed', 'cancelled', 'interrupted', 'rejected'}


class Refusal(Exception):
    def __init__(self, code, status=409):
        self.code, self.status = code, status
        super().__init__(code)


class Ledger:
    def __init__(self, directory: Path, max_sessions=64, max_turns=10000):
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.db = sqlite3.connect(directory / 'intents.sqlite3')
        (directory / 'intents.sqlite3').chmod(0o600)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
            PRAGMA journal_mode=WAL;
            PRAGMA synchronous=FULL;
            CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, device TEXT NOT NULL, created REAL NOT NULL, backend_id TEXT UNIQUE NOT NULL);
            CREATE TABLE IF NOT EXISTS turns (
                id TEXT PRIMARY KEY, session TEXT NOT NULL, digest TEXT NOT NULL,
                run TEXT, status TEXT NOT NULL, created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS controls (
                turn TEXT, prompt TEXT, generation INTEGER, PRIMARY KEY(turn,prompt,generation));
        ''')
        self.max_sessions, self.max_turns = max_sessions, max_turns

    def close(self):
        self.db.close()

    def session(self, device, sid):
        row = self.db.execute('SELECT * FROM sessions WHERE id=? AND device=?', (sid, device)).fetchone()
        if row is None:
            raise Refusal('not_found', 404)
        return dict(row)

    def create_session(self, device, sid):
        existing = self.db.execute('SELECT * FROM sessions WHERE id=?', (sid,)).fetchone()
        if existing:
            return self.session(device, sid)
        # Per-device cap is explicit; no eviction that could permit old intents to replay.
        if self.db.execute('SELECT count(*) FROM sessions WHERE device=?', (device,)).fetchone()[0] >= self.max_sessions:
            raise Refusal('session_capacity_operator_cleanup_required', 429)
        with self.db:
            self.db.execute('INSERT INTO sessions VALUES (?,?,?,?)', (sid, device, time.time(), 'g2_' + uuid.uuid4().hex))
        return self.session(device, sid)

    def backend_session(self, sid):
        return self.db.execute('SELECT backend_id FROM sessions WHERE id=?', (sid,)).fetchone()[0]

    def turn(self, device, sid, tid):
        self.session(device, sid)
        row = self.db.execute('SELECT * FROM turns WHERE id=? AND session=?', (tid, sid)).fetchone()
        if row is None:
            raise Refusal('not_found', 404)
        return dict(row)

    def reserve(self, device, sid, tid, digest):
        self.session(device, sid)
        old = self.db.execute('SELECT * FROM turns WHERE id=?', (tid,)).fetchone()
        if old:
            if old['session'] != sid or old['digest'] != digest:
                raise Refusal('idempotency_conflict')
            return dict(old), False
        unresolved = self.db.execute("SELECT id FROM turns WHERE session=? AND status NOT IN ('completed','failed','cancelled','interrupted','rejected')", (sid,)).fetchone()
        if unresolved:
            raise Refusal('previous_turn_unresolved')
        if self.db.execute("SELECT count(*) FROM turns WHERE status NOT IN ('completed','failed','cancelled','interrupted','rejected')").fetchone()[0] >= 16:
            raise Refusal('active_capacity_reconcile_before_new_work', 429)
        if self.db.execute('SELECT count(*) FROM turns').fetchone()[0] >= self.max_turns:
            raise Refusal('intent_capacity_operator_cleanup_required', 429)
        with self.db:
            self.db.execute('INSERT INTO turns VALUES (?,?,?,NULL,?,?)', (tid, sid, digest, 'submitting', time.time()))
        return self.turn(device, sid, tid), True

    def reconcile(self, device, sid, tid):
        # No await between lookup and tombstone. A delayed submit either reserved
        # first (return its state), or cannot execute after this durable refusal.
        self.session(device, sid)
        old = self.db.execute('SELECT * FROM turns WHERE id=?', (tid,)).fetchone()
        if old:
            return self.turn(device, sid, tid)
        if self.db.execute("SELECT count(*) FROM turns WHERE session=? AND digest=''", (sid,)).fetchone()[0] >= 32:
            raise Refusal('reconciliation_capacity_use_new_session', 429)
        if self.db.execute('SELECT count(*) FROM turns').fetchone()[0] >= self.max_turns:
            raise Refusal('intent_capacity_operator_cleanup_required', 429)
        with self.db:
            self.db.execute('INSERT INTO turns VALUES (?,?,?,NULL,?,?)', (tid, sid, '', 'rejected', time.time()))
        return self.turn(device, sid, tid)

    def update(self, tid, *, run=None, status=None):
        with self.db:
            if run is not None:
                self.db.execute('UPDATE turns SET run=? WHERE id=?', (run, tid))
            if status is not None:
                self.db.execute('UPDATE turns SET status=? WHERE id=?', (status, tid))

    def claim_control(self, tid, prompt, generation):
        try:
            with self.db:
                self.db.execute('INSERT INTO controls VALUES (?,?,?)', (tid, prompt, generation))
        except sqlite3.IntegrityError:
            raise Refusal('approval_already_attempted') from None
