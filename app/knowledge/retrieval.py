"""Local hybrid RAG preview. Customer tool additionally requires verified applicability.

SQLite belongs exclusively to Knowledge, never to Evolution or contact memory.
"""

import hashlib
import json
import math
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.knowledge.review import ReviewEvent, Segment, approved_segments
from app.policy.commercial import CommercialPolicyEngine, PolicyDecision


class KnowledgeQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=1000)
    model: Literal["B10", "C10"]
    powertrain: Literal["BEV", "REEV"]
    model_year: int | None = Field(default=None, ge=2026, le=2100)
    market: Literal["BR"] = "BR"
    category: Literal["sales", "technical"] = "sales"
    limit: int = Field(default=3, ge=1, le=5)


def bundle_segments(path):
    bundle = json.loads(Path(path).read_text())
    segments = [Segment.model_validate(s) for s in bundle["segments"]]
    events = [ReviewEvent.model_validate(e) for e in bundle["events"]]
    return approved_segments(segments, events)


def allowed_question(text):
    if CommercialPolicyEngine().classify_request(text) != PolicyDecision.ALLOW:
        return False
    return not re.search(
        r"desmont|alta tens[aã]o|desativar.*airbag|reparar|abrir.*bateria|emerg[eê]ncia",
        text,
        re.IGNORECASE,
    )


class KnowledgeIndex:
    def __init__(self, path, bundle_path, embedder):
        self.path, self.bundle_path, self.embedder = Path(path), Path(bundle_path), embedder
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS chunks(id TEXT PRIMARY KEY,document_sha256 TEXT NOT NULL,
                    content TEXT NOT NULL,metadata TEXT NOT NULL,vector TEXT NOT NULL,model_id TEXT NOT NULL);
                CREATE VIRTUAL TABLE IF NOT EXISTS lexical USING fts5(id UNINDEXED,content,tokenize='unicode61 remove_diacritics 2');
                CREATE TABLE IF NOT EXISTS embedding_cache(cache_key TEXT PRIMARY KEY,vector TEXT NOT NULL);
            """)
        self.path.chmod(0o600)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def build(self, identities=None):
        segments = bundle_segments(self.bundle_path)
        if len({s.segment_id for s in segments}) != len(segments):
            raise ValueError("Duplicate section identifiers")
        identities = identities or {}
        with self.connect() as db:
            prepared = []
            for s in segments:
                if not CommercialPolicyEngine().validate_output(s.text):
                    raise ValueError("Prohibited commercial content in knowledge section")
                key = hashlib.sha256(
                    (self.embedder.model_id + ":passage:" + s.text_sha256).encode()
                ).hexdigest()
                row = db.execute(
                    "SELECT vector FROM embedding_cache WHERE cache_key=?", (key,)
                ).fetchone()
                if row:
                    vector = json.loads(row[0])
                else:
                    vector = self.embedder.encode([s.text])[0]
                    db.execute(
                        "INSERT INTO embedding_cache VALUES (?,?)", (key, json.dumps(vector))
                    )
                if not vector or any(not math.isfinite(x) for x in vector):
                    raise ValueError("Invalid embedding")
                metadata = {
                    **s.model_dump(exclude={"text"}),
                    **identities.get(s.document_sha256, {}),
                }
                prepared.append(
                    (
                        s.segment_id,
                        s.document_sha256,
                        s.text,
                        json.dumps(metadata),
                        json.dumps(vector),
                        self.embedder.model_id,
                    )
                )
            # Full replacement only after successful validation/embedding of every approved segment.
            db.execute("DELETE FROM chunks")
            db.execute("DELETE FROM lexical")
            db.executemany("INSERT INTO chunks VALUES (?,?,?,?,?,?)", prepared)
            db.executemany("INSERT INTO lexical VALUES (?,?)", [(r[0], r[2]) for r in prepared])
        return len(prepared)

    def search_preview(self, question, *, document_sha256, limit=3, mode="hybrid"):
        """Engineering document-scoped preview; deliberately absent from agent tools."""
        if not allowed_question(question):
            return []
        if not 1 <= limit <= 5 or mode not in {"lexical", "vector", "hybrid"}:
            raise ValueError("Invalid retrieval limit or mode")
        # Re-read decisions every query: revocation/content changes take effect immediately.
        current = {s.segment_id: s for s in bundle_segments(self.bundle_path)}
        with self.connect() as db:
            rows = {
                r["id"]: dict(r)
                for r in db.execute(
                    "SELECT * FROM chunks WHERE document_sha256=?", (document_sha256,)
                )
                if r["id"] in current
                and r["content"] == current[r["id"]].text
                and r["model_id"] == self.embedder.model_id
            }
            words = re.findall(r"[^\W_]+", question.lower())[:40]
            expression = " OR ".join('"' + w + '"' for w in words)
            lexical = (
                [
                    r["id"]
                    for r in db.execute(
                        "SELECT id FROM lexical WHERE lexical MATCH ? ORDER BY bm25(lexical),id",
                        (expression,),
                    )
                    if r["id"] in rows
                ]
                if expression
                else []
            )
        vector = []
        similarities = {}
        if mode in {"vector", "hybrid"} and rows:
            query = self.embedder.encode([question], query=True)[0]
            for ident, row in rows.items():
                v = json.loads(row["vector"])
                if len(v) != len(query):
                    raise ValueError("Embedding dimensions differ")
                denominator = math.sqrt(sum(x * x for x in v)) * math.sqrt(
                    sum(x * x for x in query)
                )
                similarities[ident] = (
                    sum(a * b for a, b in zip(v, query, strict=True)) / denominator
                    if denominator
                    else 0
                )
            vector = sorted(rows, key=lambda i: (-similarities[i], i))
        scores = {}
        ranks = (
            [lexical] if mode == "lexical" else [vector] if mode == "vector" else [lexical, vector]
        )
        for ranking in ranks:
            for rank, ident in enumerate(ranking, 1):
                scores[ident] = scores.get(ident, 0) + 1 / (60 + rank)
        results = []
        for ident in sorted(scores, key=lambda i: (-scores[i], i))[:limit]:
            row = rows[ident]
            meta = json.loads(row["metadata"])
            results.append(
                {
                    "evidence_id": ident,
                    "document_sha256": row["document_sha256"],
                    "page_start": meta["page_start"],
                    "page_end": meta["page_end"],
                    "section_title": meta["section_title"],
                    "text": row["content"],
                    "relevance": scores[ident],
                    "vector_similarity": similarities.get(ident),
                    "approval_status": "approved",
                    "approval_scope": "text_fidelity_only",
                    "equipment_condition": meta["equipment_condition"],
                    "applicability_verified": bool(meta.get("identity_verified")),
                    "requires_answer_grounding": True,
                    "channels": [
                        c for c, r in [("lexical", lexical), ("vector", vector)] if ident in r
                    ],
                }
            )
        return results

    def search_knowledge(self, query: KnowledgeQuery):
        """Strict customer contract. Preview cannot bypass vehicle/year isolation."""
        if not allowed_question(query.question):
            return {"status": "blocked", "evidence": []}
        with self.connect() as db:
            candidates = list(db.execute("SELECT DISTINCT document_sha256,metadata FROM chunks"))
        eligible = set()
        for row in candidates:
            meta = json.loads(row["metadata"])
            if (
                meta.get("identity_verified")
                and meta.get("model") == query.model
                and meta.get("powertrain") == query.powertrain
                and meta.get("market") == query.market
                and query.model_year is not None
                and meta.get("model_year") == query.model_year
                and meta.get("knowledge_tier", "sales") == query.category
            ):
                eligible.add(row["document_sha256"])
        if not eligible:
            return {"status": "needs_configuration_confirmation", "evidence": []}
        evidence = []
        for doc in sorted(eligible):
            evidence.extend(
                self.search_preview(query.question, document_sha256=doc, limit=query.limit)
            )
        evidence = sorted(evidence, key=lambda e: (-e["relevance"], e["evidence_id"]))[
            : query.limit
        ]
        return {
            "status": "evidence_found" if evidence else "insufficient_evidence",
            "evidence": evidence,
        }
