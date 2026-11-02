"""Reviewed internal facts: exact match against approved catalog values and sources."""

import hashlib
import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.catalog.models import SourceRecord
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


class ReviewedTextFact(BaseModel):
    """Curated technical statements; extracted documents never become facts automatically."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str
    vehicle_id: str
    specification: Literal[
        "charging", "drivetrain", "comfort", "connectivity", "safety", "range_context"
    ]
    statement: str = Field(min_length=1, max_length=550)
    query_terms: list[str]
    source_id: str
    evidence_text: str = Field(min_length=1, max_length=2000)
    evidence_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    page_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_section: str
    approval_status: Literal["pending_review", "approved", "rejected"] = "pending_review"
    approved_at: datetime | None = None
    approved_by: str | None = None
    market: Literal["BR"] = "BR"


class ReviewedBrandFact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str
    statement: str = Field(min_length=1, max_length=400)
    source: SourceRecord
    evidence_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    evidence_text: str = Field(min_length=1, max_length=1200)
    approval_status: Literal["pending_review", "approved"] = "pending_review"
    approved_at: datetime | None = None
    approved_by: str | None = None
    powertrain_explanations: dict[Literal["BEV", "REEV"], str] = Field(default_factory=dict)


def public_fact(fact):
    fields = {"id", "vehicle_id", "specification", "value", "statement", "query_terms", "source_id"}
    return fact.model_dump(include=fields)


class GroundingPolicy:
    def __init__(self, facts: list[ReviewedFact | ReviewedTextFact], catalog, *, brand=None):
        self.catalog = catalog
        self.brand = brand
        if brand is not None:
            if str(brand.source.url) != "https://www.leapmotor.com.br/sobre-a-leapmotor.html":
                raise ValueError("Institutional source must be the official configured page")
            if hashlib.sha256(brand.evidence_text.encode()).hexdigest() != brand.evidence_sha256:
                raise ValueError("Institutional evidence integrity mismatch")
            if not CommercialPolicyEngine().validate_output(brand.statement):
                raise ValueError("Prohibited institutional content")
            if any(
                not text or len(text) > 400 or not CommercialPolicyEngine().validate_output(text)
                for text in brand.powertrain_explanations.values()
            ):
                raise ValueError("Prohibited powertrain explanation")
            if brand.approval_status == "approved" and not (
                brand.approved_at and brand.approved_by
            ):
                raise ValueError("Institutional statement requires explicit review")
        self.facts = {}
        for fact in facts:
            if isinstance(fact, ReviewedTextFact) and fact.approval_status != "approved":
                continue
            if isinstance(fact, ReviewedFact) and fact.specification not in TECHNICAL_NUMBERS:
                raise ValueError("Only technical numeric facts are permitted")
            vehicle = catalog.vehicle(fact.vehicle_id)
            if vehicle is None or vehicle.approval_status != "approved":
                raise ValueError("Fact requires an approved canonical vehicle")
            if (
                isinstance(fact, ReviewedFact)
                and vehicle.specifications.get(fact.specification) != fact.value
            ):
                raise ValueError("Fact value does not match catalog")
            if fact.source_id not in {source_id(s) for s in vehicle.sources}:
                raise ValueError("Fact source does not match catalog")
            if not CommercialPolicyEngine().validate_output(fact.statement):
                raise ValueError("Financial or prohibited fact")
            if isinstance(fact, ReviewedTextFact):
                if not fact.approved_by or fact.approved_at is None:
                    raise ValueError("Text fact requires an explicit review record")
                if hashlib.sha256(fact.evidence_text.encode()).hexdigest() != fact.evidence_sha256:
                    raise ValueError("Text evidence integrity mismatch")

                def numeric_tokens(text):
                    text = re.sub(r"\b(?:B10|C10)\b", "", text, flags=re.IGNORECASE)
                    return set(re.findall(r"\d+(?:[.,]\d+)?", text.replace(",", ".")))

                if numeric_tokens(fact.statement) - numeric_tokens(fact.evidence_text):
                    raise ValueError("Text fact introduces an unsupported numerical value")
                if re.search(
                    r"ignore.*instru|system prompt|execute|tool_call|apikey|api_key|R\$|https?://",
                    fact.evidence_text + " " + fact.statement,
                    re.IGNORECASE,
                ):
                    raise ValueError("Untrusted instructions or financial evidence")
                # Text review may paraphrase, but cannot introduce another car or engine.
                entities = {
                    x.upper()
                    for x in re.findall(r"\b(?:B10|C10|BEV|REEV)\b", fact.statement, re.IGNORECASE)
                }
                if entities - {vehicle.model.upper(), vehicle.powertrain.value}:
                    raise ValueError("Text fact vehicle association mismatch")
                if not any(
                    str(s.url).startswith("https://www.leapmotor.com.br/")
                    and source_id(s) == fact.source_id
                    for s in vehicle.sources
                ):
                    raise ValueError("Text facts require a reviewed official Brazilian source")
            if fact.id in self.facts:
                raise ValueError("Duplicate fact id")
            self.facts[fact.id] = fact

    def for_brand(self):
        if self.brand is None or self.brand.approval_status != "approved":
            return []
        return [
            {
                "id": self.brand.id,
                "statement": self.brand.statement,
                "source_id": source_id(self.brand.source),
            }
        ]

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
            "torque_nm": ["torque"],
            "length_mm": ["comprimento", "dimensoes", "tamanho"],
            "width_mm": ["largura", "dimensoes", "tamanho"],
            "height_mm": ["altura", "dimensoes", "tamanho"],
            "charging": ["recarga", "carregar", "carregamento", "wallbox", "tomada"],
            "drivetrain": ["motorizacao", "tecnologia", "gerador", "como funciona"],
            "comfort": ["bancos", "teto", "panoramico", "ventilacao", "aquecimento"],
            "connectivity": ["multimidia", "carplay", "android", "conectividade", "tela"],
            "safety": ["airbag", "seguranca"],
            "range_context": ["combinada", "total", "wltp"],
        }
        requested = {field for field, terms in topics.items() if any(t in question for t in terms)}
        if "charging" in requested:
            requested.discard("drivetrain")
        if not requested and re.search(
            r"quanto.*(?:faz|roda|rende)|quantos.*(?:km|quilometros)|consumo.*estrada", question
        ):
            requested = {"range_km"}
        if "range_km" in requested and vehicle.powertrain.value == "REEV":
            requested.add("range_context")
        active_sources = {source_id(s) for s in vehicle.sources}
        return [
            public_fact(f)
            for f in self.facts.values()
            if f.vehicle_id == vehicle_id
            and (
                f.approval_status == "approved"
                if isinstance(f, ReviewedTextFact)
                else vehicle.specifications.get(f.specification) == f.value
            )
            and f.source_id in active_sources
            and (
                not isinstance(f, ReviewedTextFact)
                or any(term in question for term in f.query_terms)
            )
            and (
                f.specification in requested
                if requested
                else any(term in question for term in f.query_terms)
            )
        ][:5]

    def render(self, candidate: str, offered: list[dict]):
        import json

        value = json.loads(candidate)
        if set(value) != {"fact_ids"} or not isinstance(value["fact_ids"], list):
            raise ValueError("Expected only fact_ids")
        allowed = {
            f["id"]: self.facts[f["id"]]
            for f in offered
            if f["id"] in self.facts and f == public_fact(self.facts[f["id"]])
        }
        ids = value["fact_ids"]
        if not ids or len(ids) > 5 or any(not isinstance(i, str) or i not in allowed for i in ids):
            raise ValueError("Unknown or absent fact")
        selected = [allowed[i] for i in dict.fromkeys(ids)]
        return " ".join(f.statement for f in selected), list(
            dict.fromkeys(f.source_id for f in selected)
        )
