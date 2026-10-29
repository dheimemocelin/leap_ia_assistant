"""Reviewed internal facts: exact match against approved catalog values and sources."""

import hashlib

from pydantic import BaseModel, ConfigDict

from app.policy.commercial import TECHNICAL_NUMBERS, CommercialPolicyEngine


def source_id(source):
    return (
        "src-"
        + hashlib.sha256((str(source.url) + source.retrieved_at.isoformat()).encode()).hexdigest()[
            :20
        ]
    )


class ReviewedFact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str
    vehicle_id: str
    specification: str
    value: float
    statement: str
    query_terms: list[str]
    source_id: str


class GroundingPolicy:
    def __init__(self, facts: list[ReviewedFact], catalog):
        self.catalog = catalog
        self.facts = {}
        for fact in facts:
            if fact.specification not in TECHNICAL_NUMBERS:
                raise ValueError("Only technical numeric facts are permitted")
            vehicle = catalog.vehicle(fact.vehicle_id)
            if vehicle is None or vehicle.approval_status != "approved":
                raise ValueError("Fact requires an approved canonical vehicle")
            if vehicle.specifications.get(fact.specification) != fact.value:
                raise ValueError("Fact value does not match catalog")
            if fact.source_id not in {source_id(s) for s in vehicle.sources}:
                raise ValueError("Fact source does not match catalog")
            if not CommercialPolicyEngine().validate_output(fact.statement):
                raise ValueError("Financial or prohibited fact")
            if fact.id in self.facts:
                raise ValueError("Duplicate fact id")
            self.facts[fact.id] = fact

    def for_vehicle(self, vehicle_id, question):
        from app.catalog.media_library import norm

        vehicle = self.catalog.vehicle(vehicle_id)
        if vehicle is None or vehicle.approval_status != "approved":
            return []
        question = norm(question)
        topics = {
            "range_km": ["autonomia", "alcance"],
            "battery_kwh": ["bateria", "capacidade da bateria"],
            "power_cv": ["potencia", "cavalos", "desempenho"],
            "trunk_liters": ["porta malas", "porta-malas", "bagageiro"],
        }
        requested = {field for field, terms in topics.items() if any(t in question for t in terms)}
        active_sources = {source_id(s) for s in vehicle.sources}
        return [
            f.model_dump()
            for f in self.facts.values()
            if f.vehicle_id == vehicle_id
            and vehicle.specifications.get(f.specification) == f.value
            and f.source_id in active_sources
            and (
                f.specification in requested
                if requested
                else any(term in question for term in f.query_terms)
            )
        ]

    def render(self, candidate: str, offered: list[dict]):
        import json

        value = json.loads(candidate)
        if set(value) != {"fact_ids"} or not isinstance(value["fact_ids"], list):
            raise ValueError("Expected only fact_ids")
        allowed = {f["id"]: ReviewedFact.model_validate(f) for f in offered}
        ids = value["fact_ids"]
        if not ids or len(ids) > 5 or any(not isinstance(i, str) or i not in allowed for i in ids):
            raise ValueError("Unknown or absent fact")
        selected = [allowed[i] for i in dict.fromkeys(ids)]
        return " ".join(f.statement for f in selected), list(
            dict.fromkeys(f.source_id for f in selected)
        )
