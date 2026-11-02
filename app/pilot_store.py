"""Local pilot persistence. No outbound integrations; opaque browser identities only."""

import json
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path


class PilotStore:
    def __init__(self, path: str):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        os.close(descriptor)
        os.chmod(self.path, 0o600)
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS pilot_people (
                    id TEXT PRIMARY KEY, display_name TEXT, updated_at INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS pilot_threads (
                    owner TEXT PRIMARY KEY, person_id TEXT NOT NULL,
                    scope TEXT NOT NULL, conversation_id TEXT NOT NULL,
                    state TEXT NOT NULL DEFAULT '{}', updated_at INTEGER NOT NULL,
                    UNIQUE(person_id, scope),
                    FOREIGN KEY(person_id) REFERENCES pilot_people(id) ON DELETE CASCADE);
                CREATE TABLE IF NOT EXISTS pilot_opportunities (
                    owner TEXT NOT NULL, conversation_id TEXT NOT NULL,
                    payload TEXT NOT NULL, updated_at INTEGER NOT NULL,
                    PRIMARY KEY(owner, conversation_id),
                    FOREIGN KEY(owner) REFERENCES pilot_threads(owner) ON DELETE CASCADE);
            """)
            db.execute(
                "DELETE FROM pilot_people WHERE updated_at < ?", (int(time.time()) - 30 * 86400,)
            )

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def known_person(self, person):
        with self.connect() as db:
            return (
                db.execute("SELECT 1 FROM pilot_people WHERE id=?", (person,)).fetchone()
                is not None
            )

    def open_thread(self, person, scope):
        now = int(time.time())
        with self.connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO pilot_people(id,updated_at) VALUES (?,?)", (person, now)
            )
            db.execute(
                "INSERT OR IGNORE INTO pilot_threads(owner,person_id,scope,conversation_id,updated_at) VALUES (?,?,?,?,?)",
                (secrets.token_hex(24), person, scope, secrets.token_hex(16), now),
            )
            row = db.execute(
                "SELECT owner,conversation_id FROM pilot_threads WHERE person_id=? AND scope=?",
                (person, scope),
            ).fetchone()
            return dict(row)

    def load_state(self, owner, conversation_id):
        with self.connect() as db:
            row = db.execute(
                "SELECT t.state,p.display_name FROM pilot_threads t JOIN pilot_people p ON p.id=t.person_id WHERE t.owner=? AND t.conversation_id=?",
                (owner, conversation_id),
            ).fetchone()
        if row is None:
            raise ValueError("Unknown pilot conversation")
        state = json.loads(row["state"])
        if not state:
            state = {
                "history": [],
                "lead_profile": {
                    "display_name": row["display_name"],
                    "name_prompted": bool(row["display_name"]),
                },
            }
        return state

    def save_state(self, owner, conversation_id, state):
        profile = state.get("lead_profile") or {}
        now = int(time.time())
        # Only internal qualification data. Contact is included only in an authorized summary.
        fields = [
            "interest_model",
            "powertrain",
            "vehicle_id",
            "usage",
            "use_contexts",
            "needs",
            "objections",
            "daily_distance_km",
            "trip_distance_km",
            "visit_interest",
            "visit_preference",
            "trade_in_interest",
            "purchase_timeline",
            "buying_intent",
            "signals",
            "temperature",
            "qualification_reasons",
            "commercial_stage",
            "next_action",
            "charging_access",
            "consent",
        ]
        payload = {key: profile.get(key) for key in fields}
        payload["status"] = "local_only"
        summary = profile.get("handoff_summary")
        if (
            profile.get("consent") == "granted"
            and "human_contact_requested" in profile.get("signals", [])
            and summary
        ):
            payload["authorized_handoff"] = summary
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT person_id FROM pilot_threads WHERE owner=? AND conversation_id=?",
                (owner, conversation_id),
            ).fetchone()
            if row is None:
                raise ValueError("Unknown pilot conversation")
            db.execute(
                "UPDATE pilot_threads SET state=?,updated_at=? WHERE owner=? AND conversation_id=?",
                (json.dumps(state, ensure_ascii=False), now, owner, conversation_id),
            )
            db.execute(
                "UPDATE pilot_people SET display_name=?,updated_at=? WHERE id=?",
                (profile.get("display_name"), now, row["person_id"]),
            )
            if profile.get("vehicle_id") or "human_contact_requested" in profile.get("signals", []):
                db.execute(
                    "INSERT INTO pilot_opportunities(owner,conversation_id,payload,updated_at) VALUES (?,?,?,?) ON CONFLICT(owner,conversation_id) DO UPDATE SET payload=excluded.payload,updated_at=excluded.updated_at",
                    (owner, conversation_id, json.dumps(payload, ensure_ascii=False), now),
                )
            elif profile.get("consent") == "declined":
                db.execute(
                    "DELETE FROM pilot_opportunities WHERE owner=? AND conversation_id=?",
                    (owner, conversation_id),
                )

    def reset_thread(self, owner):
        conversation_id = secrets.token_hex(16)
        with self.connect() as db:
            db.execute(
                "UPDATE pilot_threads SET conversation_id=?,state='{}',updated_at=? WHERE owner=?",
                (conversation_id, int(time.time()), owner),
            )
        return conversation_id

    def forget(self, person):
        with self.connect() as db:
            owners = [
                r[0]
                for r in db.execute("SELECT owner FROM pilot_threads WHERE person_id=?", (person,))
            ]
            db.execute("DELETE FROM pilot_people WHERE id=?", (person,))
            return owners
