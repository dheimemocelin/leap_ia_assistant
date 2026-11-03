"""Read-only RAG bridge over the existing approved catalog authority.

Unverified manual previews are deliberately not loaded into the customer runtime.
"""

import hashlib
import json
import re
import sqlite3
import threading
from pathlib import Path

from app.agent.grounding import public_fact
from app.knowledge.retrieval import allowed_question


class CatalogKnowledge:
    def __init__(self, grounding, embedder, cache_path, *, minimum_similarity=0.86):
        self.grounding, self.embedder = grounding, embedder
        self.path = Path(cache_path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.minimum_similarity = minimum_similarity
        self.lock = threading.Lock()
        with sqlite3.connect(self.path) as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS catalog_embeddings(key TEXT PRIMARY KEY,vector TEXT NOT NULL)"
            )
        self.path.chmod(0o600)

    def active_facts(self, vehicle_id):
        result = []
        for fact in self.grounding.facts.values():
            if fact.vehicle_id != vehicle_id:
                continue
            projected = public_fact(fact)
            if any(
                projected in self.grounding.for_vehicle(vehicle_id, term)
                for term in fact.query_terms
            ):
                result.append(projected)
        return result

    def validate(self, fact, vehicle_id):
        return fact in self.active_facts(vehicle_id)

    def retrieve(self, vehicle_id, question):
        if not allowed_question(question):
            return []
        facts = self.active_facts(vehicle_id)
        if not facts:
            return []
        # Related charging data must not be presented as proof of an optional feature.
        required = re.findall(r"programad\w*|agend\w*|sem fio|wireless", question.casefold())
        if required:
            facts = [
                f for f in facts if any(term[:6] in f["statement"].casefold() for term in required)
            ]
            if not facts:
                return []
        lexical = self.grounding.for_vehicle(vehicle_id, question)
        if lexical:
            return [f for f in lexical if f in facts][:2]
        # Only compact approved statements are embedded. No customer text is persisted.
        with self.lock, sqlite3.connect(self.path) as db:
            vectors = []
            for fact in facts:
                key = hashlib.sha256(
                    (self.embedder.model_id + fact["source_id"] + fact["statement"]).encode()
                ).hexdigest()
                cached = db.execute(
                    "SELECT vector FROM catalog_embeddings WHERE key=?", (key,)
                ).fetchone()
                vector = (
                    json.loads(cached[0])
                    if cached
                    else self.embedder.encode([fact["statement"]])[0]
                )
                if not cached:
                    db.execute(
                        "INSERT OR IGNORE INTO catalog_embeddings VALUES (?,?)",
                        (key, json.dumps(vector)),
                    )
                vectors.append(vector)
            query = self.embedder.encode([question], query=True)[0]
        ranked = []
        for fact, vector in zip(facts, vectors, strict=True):
            if len(query) != len(vector):
                raise ValueError("Embedding dimension mismatch")
            score = sum(a * b for a, b in zip(query, vector, strict=True))
            if score >= self.minimum_similarity:
                ranked.append((score, fact))
        ranked.sort(key=lambda item: (-item[0], item[1]["id"]))
        return [fact for _, fact in ranked[:2]]
