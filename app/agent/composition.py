"""Conversational wording is generated; evidence and permissions are server-owned.

Free prose is never a carrier for vehicle facts: approved fact IDs are rendered
separately. Structural, entity and assertion checks are conservative heuristics,
not a general semantic entailment proof. See the adversarial evaluation limits.
"""

import re
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.catalog.media_library import norm
from app.policy.commercial import CommercialPolicyEngine


class CompositionRejected(ValueError):
    pass


class ConversationQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: Literal[
        "usage",
        "priority",
        "doubt",
        "objection",
        "daily_distance",
        "charging_context",
        "family_priority",
        "professional_routine",
        "travel_pattern",
        "use_priority",
        "first_electric_priority",
        "electric_concern",
        "photos",
        "preferred_name",
        "model_interest",
        "brand_interest",
        "purchase_priority",
        "purchase_timeline",
        "visit",
        "visit_preference",
        "trade_in",
    ]
    text: str = Field(min_length=1, max_length=180)


class ConversationDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(
        default="",
        max_length=650,
        validation_alias=AliasChoices("text", "acknowledgement"),
    )
    fact_ids: list[str] = Field(default_factory=list, max_length=5)
    question: ConversationQuestion | None = None


class ConversationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intent: Literal[
        "positive",
        "negative",
        "doubt",
        "more",
        "short",
        "usage",
        "charging_context",
        "distance_context",
        "technical",
        "missing_evidence",
        "first_electric",
        "objection",
        "welcome",
        "brand",
        "other",
        "purchase",
    ]
    action: str | None = None
    question_keys: list[str] = Field(default_factory=list, max_length=3)
    suggested_question: ConversationQuestion | None = None
    facts: list[dict] = Field(default_factory=list, max_length=5)
    require_facts: bool = False


def validate_prose(text: str, profile: dict, *, question=False):
    """Reject external actions, ungrounded claims, PII and cross-vehicle entities.

    This is a negative assertion/entity filter, not a closed vocabulary. Even
    allowed fact values must enter through approved fact_ids, not free text.
    """
    if not text.strip() or not CommercialPolicyEngine().validate_output(text):
        raise CompositionRejected("commercial_policy")
    t = norm(text)
    entities = set(re.findall(r"\b(?:b\d{2}|c\d{2}|bev|reev)\b", t))
    allowed = {norm(profile.get("interest_model") or ""), norm(profile.get("powertrain") or "")}
    if not profile.get("interest_model"):
        allowed.update({"b10", "c10"})
    if entities - allowed:
        raise CompositionRejected("cross_vehicle_entity")
    acronyms = set(re.findall(r"\b[A-Z][A-Z0-9-]+\b", text))
    if acronyms - {value.upper() for value in allowed} - {"OK"}:
        raise CompositionRejected("unapproved_entity")
    if re.search(r"\b(?:tesla|byd|dolphin|corolla|volvo|t03)\b", t):
        raise CompositionRejected("unapproved_entity")
    if re.search(r"\b(?:leapmotor|fundad[oa]|fabricante|chinesa|china|stellantis)\b", t):
        raise CompositionRejected("institutional_evidence_required")
    without_entities = re.sub(r"\b(?:b10|c10)\b", "", t)
    if re.search(
        r"\d|https?://|www\.|@|<|>|\[|\]|\{|\}|src-|base64|assets/|/home/", without_entities
    ):
        raise CompositionRejected("untrusted_identifier_or_value")
    if re.search(r"\b(?:vinte|trinta|quarenta|cinquenta|cem|cento|mil|milhao|milhoes)\b", t):
        raise CompositionRejected("unverified_spelled_value")
    if re.search(r"consultor|vendedor|humano|\blia\b|assistente virtual|me chamo|sou uma?", t):
        raise CompositionRejected("identity_or_handoff")
    if re.search(
        r"\b(?:agendei|agendamos|agendad[oa]|confirmad[oa]|aceitamos|avaliamos)\b|"
        r"\b(?:visita|horario|agendamento)\s+(?:esta|foi|ficou)\s+confirmad",
        t,
    ):
        raise CompositionRejected("unauthorized_store_commitment")
    if text.count("?") != (1 if question else 0):
        raise CompositionRejected("question_shape")
    if (
        not question
        and re.search(r"(?:recarga|carregar) em casa", t)
        and profile.get("charging_access") != "home"
    ):
        raise CompositionRejected("unsupported_customer_context")
    if (
        not question
        and "aplicativo" in t
        and "aplicativos"
        not in [
            profile.get("usage"),
            *profile.get("use_contexts", []),
        ]
    ):
        raise CompositionRejected("unsupported_customer_context")
    # Units in a planned question (e.g. daily distance) do not assert a value.
    if question:
        t = re.sub(r"\b(?:quilometros|km|litros|cavalos|cv|kwh)\b", "", t)
    # No technical, commercial, comparative or capability assertions in prose.
    # Discussing the customer's concern is different from claiming a capability.
    if re.search(
        r"\b(?:garant\w*|promet\w*|aprovad[oa]s?|homologad[oa]s?|estoque|disponivel|"
        r"rentab\w*|lucro|economiza\w*|economico|confortavel|espacoso|silencioso|"
        r"seguro|superior|melhor que|ideal para|perfeito para|aceito|compativel|"
        r"quilowatt|cavalos|cv|kwh|litros|km|quilometros|reais|por cento)\b",
        t,
    ):
        # "base aprovada" and "fatos aprovados" are about evidence, not the car.
        stripped = re.sub(r"\b(?:base aprovada|fatos aprovados|informacoes aprovadas)\b", "", t)
        if re.search(
            r"\b(?:garant\w*|promet\w*|aprovad[oa]s?|homologad[oa]s?|estoque|disponivel|"
            r"rentab\w*|lucro|economiza\w*|economico|confortavel|espacoso|silencioso|"
            r"seguro|superior|melhor que|ideal para|perfeito para|aceito|compativel|"
            r"quilowatt|cavalos|cv|kwh|litros|km|quilometros|reais|por cento)\b",
            stripped,
        ):
            raise CompositionRejected("unsupported_assertion")
    if re.search(
        r"\b(?:ele|ela|esse|essa|este|esta|carro|veiculo|modelo|b10|c10|bev|reev)\s+"
        r"(?:(?:bev|reev)\s+)?(?:e(?!\s+(?:o\s+)?(?:b10|c10)\b)|eh|sao|tem|possui|oferece|conta|faz|roda|rende|"
        r"consome|carrega|permite|pode|vai|entrega|atende|proporciona|traz)\b",
        t,
    ):
        raise CompositionRejected("vehicle_predication")
    if re.search(
        r"\b(?:bateria|motor|autonomia|recarga|porta.malas)\s+(?:e|tem|possui|oferece|permite)\b", t
    ):
        raise CompositionRejected("technical_predication")
    if not question and re.search(
        r"\b(?:roda|rende|consome|dura|comporta|acomoda|acelera|alcanca|cabe|cabem|"
        r"reduz|otimiza|protege|assegura|suporta|possibilita|aquecid[oa]s?|"
        r"panoramico|airbags?|adas|amplo|ampla|aceita|aceitam|rodar|economizar)\b",
        t,
    ):
        raise CompositionRejected("unsupported_capability")


def render_draft(draft, profile, facts, *, allowed_question_keys, previous_texts):
    if draft.text:
        validate_prose(draft.text, profile)
    allowed = {f["id"]: f for f in facts}
    if len(set(draft.fact_ids)) != len(draft.fact_ids) or any(
        i not in allowed for i in draft.fact_ids
    ):
        raise CompositionRejected("unsupported_fact_id")
    statements = [allowed[i]["statement"] for i in draft.fact_ids]
    parts = [draft.text, *statements]
    accepted_question = None
    if draft.question:
        if draft.question.key not in allowed_question_keys:
            raise CompositionRejected("unplanned_question")
        validate_prose(draft.question.text, profile, question=True)
        key = draft.question.key
        actual_key = "social_" + key if key in {"priority", "doubt", "objection"} else key
        if key == "preferred_name":
            actual_key = "display_name"
        if (
            actual_key not in profile.get("asked", [])
            and not (key == "usage" and profile.get("usage"))
            and not (key == "priority" and profile.get("needs"))
            and not (key == "charging_context" and profile.get("charging_access"))
            and not (key == "daily_distance" and profile.get("daily_distance_km"))
            and not (
                key == "preferred_name"
                and (profile.get("display_name") or profile.get("name_prompted"))
            )
            and not any(norm(draft.question.text) in norm(previous) for previous in previous_texts)
        ):
            parts.append(draft.question.text)
            accepted_question = actual_key
    text = " ".join(p for p in parts if p).strip()
    if not text:
        raise CompositionRejected("empty_draft")
    if any(norm(text) == norm(previous) for previous in previous_texts):
        raise CompositionRejected("repeated_response")
    return (
        text,
        list(dict.fromkeys(allowed[i]["source_id"] for i in draft.fact_ids)),
        accepted_question,
    )
