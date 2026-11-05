"""Local pilot persistence. No outbound integrations; opaque browser identities only."""

import json
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime
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
            columns = {row[1] for row in db.execute("PRAGMA table_info(pilot_people)")}
            if "profile_json" not in columns:
                db.execute(
                    "ALTER TABLE pilot_people ADD COLUMN profile_json TEXT NOT NULL DEFAULT '{}' "
                )
            db.executescript("""
                CREATE TABLE IF NOT EXISTS pilot_sessions (
                    id TEXT PRIMARY KEY, owner TEXT NOT NULL, payload TEXT NOT NULL,
                    FOREIGN KEY(owner) REFERENCES pilot_threads(owner) ON DELETE CASCADE);
                CREATE TABLE IF NOT EXISTS pilot_handoffs (
                    id TEXT PRIMARY KEY, owner TEXT NOT NULL, conversation_id TEXT NOT NULL,
                    idempotency_key TEXT UNIQUE NOT NULL, payload TEXT NOT NULL,
                    status TEXT NOT NULL, attempted INTEGER NOT NULL DEFAULT 0,
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
                "SELECT t.state,p.display_name,p.profile_json FROM pilot_threads t JOIN pilot_people p ON p.id=t.person_id WHERE t.owner=? AND t.conversation_id=?",
                (owner, conversation_id),
            ).fetchone()
        if row is None:
            raise ValueError("Unknown pilot conversation")
        state = json.loads(row["state"])
        if not state:
            customer = json.loads(row["profile_json"])
            state = {
                **customer,
                "history": customer.get("history", []),
                "lead_profile": {
                    **customer.get("lead_profile", {}),
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
            "visit_booking_status",
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
            and {"human_contact_requested", "handoff_offer_accepted"}.intersection(
                profile.get("signals", [])
            )
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
            if profile.get("consent") == "declined":
                for h in db.execute(
                    "SELECT id,payload FROM pilot_handoffs WHERE owner=?", (owner,)
                ).fetchall():
                    record = json.loads(h["payload"])
                    record.update(
                        name=None,
                        phone=None,
                        needs=[],
                        usage=None,
                        summary="Consentimento revogado.",
                        external_id=None,
                        consent="revoked",
                    )
                    db.execute(
                        "UPDATE pilot_handoffs SET payload=?,attempted=1 WHERE id=?",
                        (json.dumps(record), h["id"]),
                    )
            if state.get("conversation_session"):
                customer = {
                    k: state.get(k)
                    for k in (
                        "model",
                        "powertrain",
                        "history",
                        "shown_media_ids",
                        "last_shown_media_ids",
                        "last_media_vehicle_id",
                        "last_delivered_media_ids",
                        "introduced_vehicle_ids",
                        "presented_fact_ids",
                    )
                }
                customer_fields = (set(fields) - {"consent"}) | {
                    "first_electric",
                    "greeted",
                    "name_prompted",
                    "asked",
                    "knows_brand",
                    "showroom_presented",
                    "handoff_offer_made",
                }
                customer["lead_profile"] = {
                    k: v for k, v in profile.items() if k in customer_fields
                }
                db.execute(
                    "UPDATE pilot_people SET profile_json=? WHERE id=?",
                    (json.dumps(customer, ensure_ascii=False), row["person_id"]),
                )
                sessions = [state["conversation_session"]]
                if state.get("session_archive"):
                    sessions.append(state["session_archive"])
                for session in sessions:
                    db.execute(
                        "INSERT INTO pilot_sessions(id,owner,payload) VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload",
                        (session["id"], owner, json.dumps(session)),
                    )
            if profile.get("vehicle_id") or {
                "human_contact_requested",
                "handoff_offer_accepted",
            }.intersection(profile.get("signals", [])):
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
            old = db.execute("SELECT state FROM pilot_threads WHERE owner=?", (owner,)).fetchone()
            state = json.loads(old["state"]) if old else {}
            if state.get("conversation_session"):
                from app.agent.lifecycle import timestamp

                session = state["conversation_session"]
                session.update(
                    status="CLOSED", end_reason="manual_reset", ended_at=timestamp(time.time())
                )
                db.execute(
                    "INSERT INTO pilot_sessions(id,owner,payload) VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload",
                    (session["id"], owner, json.dumps(session)),
                )
            else:
                state = {}
            db.execute(
                "UPDATE pilot_threads SET conversation_id=?,state=?,updated_at=? WHERE owner=?",
                (conversation_id, json.dumps(state), int(time.time()), owner),
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

    def prepare_handoff(self, owner, conversation_id, payload):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT state FROM pilot_threads WHERE owner=? AND conversation_id=?",
                (owner, conversation_id),
            ).fetchone()
            if row is None:
                raise ValueError("Unknown opportunity")
            profile = json.loads(row["state"]).get("lead_profile", {})
            if profile.get("consent") != "granted" or not self.same_consent_time(
                profile.get("consent_at"), payload["consent_at"]
            ):
                raise ValueError("Consent revoked or stale")
            db.execute(
                "INSERT OR IGNORE INTO pilot_handoffs(id,owner,conversation_id,idempotency_key,payload,status) VALUES (?,?,?,?,?,?)",
                (
                    payload["id"],
                    owner,
                    conversation_id,
                    payload["idempotency_key"],
                    json.dumps(payload),
                    payload["status"],
                ),
            )
            saved = db.execute(
                "SELECT payload FROM pilot_handoffs WHERE idempotency_key=?",
                (payload["idempotency_key"],),
            ).fetchone()
            return json.loads(saved["payload"])

    def get_handoff(self, identifier):
        with self.connect() as db:
            row = db.execute(
                "SELECT payload FROM pilot_handoffs WHERE id=?", (identifier,)
            ).fetchone()
            return json.loads(row["payload"]) if row else None

    def claim_handoff(self, identifier):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT h.owner,h.conversation_id,h.payload,t.state FROM pilot_handoffs h JOIN pilot_threads t ON t.owner=h.owner WHERE h.id=? AND h.attempted=0 AND h.status='prepared'",
                (identifier,),
            ).fetchone()
            if row is None:
                return False
            profile = json.loads(row["state"]).get("lead_profile", {})
            payload = json.loads(row["payload"])
            if profile.get("consent") != "granted" or not self.same_consent_time(
                profile.get("consent_at"), payload["consent_at"]
            ):
                return False
            payload["status"] = "queued"
            db.execute(
                "UPDATE pilot_handoffs SET attempted=1,status='queued',payload=? WHERE id=?",
                (json.dumps(payload), identifier),
            )
            return True

    def update_handoff(self, identifier, status, *, external_id=None, failure_code=None):
        allowed = {"queued": {"queued", "delivered", "failed"}, "delivered": {"acknowledged"}}
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT payload,status FROM pilot_handoffs WHERE id=?", (identifier,)
            ).fetchone()
            if row is None or status not in allowed.get(row["status"], set()):
                raise ValueError("Invalid handoff transition")
            payload = json.loads(row["payload"])
            if status in {"delivered", "acknowledged"} and (
                payload.get("consent") != "granted"
                or not (external_id or payload.get("external_id"))
            ):
                raise ValueError("Authorized external receipt required")
            payload.update(
                status=status,
                external_id=external_id or payload.get("external_id"),
                failure_code=failure_code,
            )
            db.execute(
                "UPDATE pilot_handoffs SET status=?,payload=? WHERE id=?",
                (status, json.dumps(payload), identifier),
            )

    def handoff_metrics(self):
        with self.connect() as db:
            return {
                r[0]: r[1]
                for r in db.execute("SELECT status,COUNT(*) FROM pilot_handoffs GROUP BY status")
            }

    def mark_media_delivery(self, person, scope, media_id=None, *, failed=False):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT owner,state FROM pilot_threads WHERE person_id=? AND scope=?",
                (person, scope),
            ).fetchone()
            if row is None:
                return
            state = json.loads(row["state"])
            if not state.get("conversation_session"):
                return
            if media_id:
                delivered = [
                    x
                    for x in state.get("last_delivered_media_ids", [])
                    if x in state.get("last_shown_media_ids", [])
                ]
                if media_id not in state.get("last_shown_media_ids", []):
                    return
                state["last_delivered_media_ids"] = list(dict.fromkeys([*delivered, media_id]))
            state["media_delivery_status"] = "unconfirmed" if failed else "delivered"
            db.execute(
                "UPDATE pilot_threads SET state=? WHERE owner=?", (json.dumps(state), row["owner"])
            )

    def conversion_metrics(self):
        with self.connect() as db:
            rows = [json.loads(r[0]) for r in db.execute("SELECT payload FROM pilot_opportunities")]
            return {
                "opportunities": len(rows),
                "visit_interest": sum(p.get("visit_interest") is True for p in rows),
                "authorized_handoffs": sum("authorized_handoff" in p for p in rows),
            }

    @staticmethod
    def same_consent_time(left, right):
        try:
            return datetime.fromisoformat(left) == datetime.fromisoformat(right)
        except (ValueError, TypeError):
            return False
