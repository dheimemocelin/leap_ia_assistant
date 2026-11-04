"""Durable SQLite pilot inbox/outbox; no assumed provider exactly-once guarantee."""

import json
import time

from app.pilot_store import PilotStore


class EvolutionStore(PilotStore):
    def __init__(self, path):
        super().__init__(path)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS pilot_wa_inbox (
                    event_id TEXT PRIMARY KEY, person TEXT NOT NULL, instance TEXT NOT NULL,
                    recipient TEXT NOT NULL, text TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'queued',
                    response TEXT, created_at INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS pilot_wa_outbox (
                    event_id TEXT NOT NULL, part INTEGER NOT NULL, kind TEXT NOT NULL,
                    content TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'pending', provider_id TEXT,
                    PRIMARY KEY(event_id,part));
            """)
            columns = {row[1] for row in db.execute("PRAGMA table_info(pilot_wa_inbox)")}
            for name, definition in {
                "input_type": "TEXT NOT NULL DEFAULT 'text'",
                "audio_ref": "TEXT NOT NULL DEFAULT ''",
                "metrics": "TEXT NOT NULL DEFAULT '{}'",
            }.items():
                if name not in columns:
                    db.execute(f"ALTER TABLE pilot_wa_inbox ADD COLUMN {name} {definition}")
        self.purge_content()

    def enqueue(self, event_id, person, instance, recipient, text, input_type="text", audio=None):
        if text.casefold().strip("!.? ") in {"apagar meus dados", "esquecer meus dados"}:
            text = text.casefold().strip("!.? ")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM pilot_wa_inbox WHERE event_id=?", (event_id,)).fetchone():
                return False
            count = db.execute(
                "SELECT COUNT(*) FROM pilot_wa_inbox WHERE person=? AND created_at>?",
                (person, int(time.time()) - 86400),
            ).fetchone()[0]
            if count >= 40 and text.casefold().strip("!.? ") not in {
                "apagar meus dados",
                "esquecer meus dados",
            }:
                raise ValueError("Pilot daily turn limit")
            db.execute(
                "INSERT INTO pilot_wa_inbox(event_id,person,instance,recipient,text,created_at,input_type,audio_ref) VALUES (?,?,?,?,?,?,?,?)",
                (
                    event_id,
                    person,
                    instance,
                    recipient,
                    text,
                    int(time.time()),
                    input_type,
                    json.dumps(audio) if audio else "",
                ),
            )
            return True

    def recover(self):
        with self.connect() as db:
            db.execute(
                "UPDATE pilot_wa_inbox SET state='review' WHERE state IN ('processing','delivering')"
            )
            db.execute("UPDATE pilot_wa_outbox SET state='uncertain' WHERE state='sending'")

    def claim(self):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM pilot_wa_inbox WHERE state IN ('queued','ready') ORDER BY CASE WHEN lower(text) IN ('apagar meus dados','esquecer meus dados') THEN 0 ELSE 1 END, rowid LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            db.execute(
                "UPDATE pilot_wa_inbox SET state=? WHERE event_id=?",
                ("processing" if row["state"] == "queued" else "delivering", row["event_id"]),
            )
            return dict(row)

    def response_ready(self, event_id, response):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "UPDATE pilot_wa_inbox SET state='ready',audio_ref='',response=? WHERE event_id=?",
                (json.dumps(response), event_id),
            )
            parts = [("text", response["text"])] + [("image", x) for x in response["media_ids"]]
            db.executemany(
                "INSERT OR IGNORE INTO pilot_wa_outbox(event_id,part,kind,content) VALUES (?,?,?,?)",
                [(event_id, index, kind, content) for index, (kind, content) in enumerate(parts)],
            )

    def claim_part(self, event_id):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM pilot_wa_outbox WHERE event_id=? AND state='pending' ORDER BY part LIMIT 1",
                (event_id,),
            ).fetchone()
            if row is None:
                return None
            db.execute(
                "UPDATE pilot_wa_outbox SET state='sending' WHERE event_id=? AND part=?",
                (event_id, row["part"]),
            )
            return dict(row)

    def part_done(self, event_id, part, provider_id):
        with self.connect() as db:
            db.execute(
                "UPDATE pilot_wa_outbox SET state='sent',provider_id=? WHERE event_id=? AND part=?",
                (provider_id, event_id, part),
            )

    def finish(self, event_id, state):
        with self.connect() as db:
            db.execute(
                "UPDATE pilot_wa_inbox SET state=?,text='',recipient='',audio_ref='' WHERE event_id=?",
                (state, event_id),
            )
            if state == "review":
                db.execute(
                    "UPDATE pilot_wa_outbox SET state='uncertain' WHERE event_id=? AND state='sending'",
                    (event_id,),
                )

    def redact_person(self, person, current_event):
        with self.connect() as db:
            db.execute(
                "UPDATE pilot_wa_outbox SET content='',provider_id=NULL WHERE event_id IN (SELECT event_id FROM pilot_wa_inbox WHERE person=? AND event_id<>?)",
                (person, current_event),
            )
            db.execute(
                "UPDATE pilot_wa_inbox SET text='',recipient='',audio_ref='',response=NULL,state=CASE WHEN state IN ('queued','ready','processing','delivering') THEN 'cancelled' ELSE state END WHERE person=? AND event_id<>?",
                (person, current_event),
            )
            db.execute("UPDATE pilot_wa_inbox SET person='' WHERE person=?", (person,))

    def record_metrics(self, event_id, values):
        allowed = {
            "input_type",
            "audio_latency_ms",
            "stt_latency_ms",
            "stt_duration_seconds",
            "stt_estimated_usd",
            "audio_failure",
            "llm_calls",
            "intent",
            "action",
            "composition_origin",
            "fallback_reason",
            "specialist",
            "conversation_act",
            "routing_origin",
            "routing_failure",
            "session_status",
            "commercial_state",
            "session_reopened",
            "handoff_status",
        }
        with self.connect() as db:
            db.execute(
                "UPDATE pilot_wa_inbox SET metrics=? WHERE event_id=?",
                (json.dumps({k: v for k, v in values.items() if k in allowed}), event_id),
            )

    def purge_content(self):
        cutoff = int(time.time()) - 30 * 86400
        with self.connect() as db:
            db.execute("DELETE FROM pilot_people WHERE updated_at<?", (cutoff,))
            db.execute(
                "UPDATE pilot_wa_outbox SET content='',provider_id=NULL WHERE event_id IN (SELECT event_id FROM pilot_wa_inbox WHERE created_at<?)",
                (cutoff,),
            )
            db.execute(
                "UPDATE pilot_wa_inbox SET person='',text='',recipient='',audio_ref='',response=NULL,metrics='{}',state=CASE WHEN state IN ('queued','ready','processing','delivering') THEN 'cancelled' ELSE state END WHERE created_at<?",
                (cutoff,),
            )

    def counts(self):
        with self.connect() as db:
            return {
                row[0]: row[1]
                for row in db.execute("SELECT state,COUNT(*) FROM pilot_wa_inbox GROUP BY state")
            }
