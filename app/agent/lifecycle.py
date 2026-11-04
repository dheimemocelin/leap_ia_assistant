"""Session lifecycle decisions; customer memory is retained independently."""

import re
import secrets
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.catalog.media_library import norm


class SessionStatus(StrEnum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    CLOSED = "CLOSED"
    HANDOFF_PENDING = "HANDOFF_PENDING"
    TRANSFERRED = "TRANSFERRED"


class CommercialState(StrEnum):
    DISCOVERY = "DISCOVERY"
    EXPLORING = "EXPLORING"
    INTERESTED = "INTERESTED"
    AWAITING_CONSENT = "AWAITING_CONSENT"
    HANDOFF_PENDING = "HANDOFF_PENDING"
    HANDOFF_CONFIRMED = "HANDOFF_CONFIRMED"
    PAUSED = "PAUSED"
    CLOSED = "CLOSED"


class ConversationSession(BaseModel):
    id: str = Field(default_factory=lambda: secrets.token_hex(16))
    status: SessionStatus = SessionStatus.ACTIVE
    opened_at: str
    last_interaction_at: str
    ended_at: str | None = None
    end_reason: str | None = None
    resumed_from: str | None = None


def timestamp(value):
    return datetime.fromtimestamp(value, UTC).isoformat()


def begin_session(previous, now, inactivity_seconds):
    """No timer sends messages. Inactivity is evaluated only on incoming input."""
    at = timestamp(now)
    if not previous:
        return ConversationSession(opened_at=at, last_interaction_at=at), None
    old = ConversationSession.model_validate(previous)
    elapsed = now - datetime.fromisoformat(old.last_interaction_at).timestamp()
    expired = old.status == SessionStatus.ACTIVE and elapsed >= inactivity_seconds
    if old.status in {SessionStatus.CLOSED, SessionStatus.PAUSED} or expired:
        if expired:
            old.status = SessionStatus.PAUSED
            old.ended_at = timestamp(
                datetime.fromisoformat(old.last_interaction_at).timestamp() + inactivity_seconds
            )
            old.end_reason = "inactivity"
        current = ConversationSession(opened_at=at, last_interaction_at=at, resumed_from=old.id)
        return current, old.model_dump(mode="json")
    old.last_interaction_at = at
    return old, None


def greeting(text):
    return norm(text).strip("!.? ") in {"oi", "ola", "opa", "bom dia", "boa tarde", "boa noite"}


def end_intent(text, pending_question):
    t = norm(text).strip("!.? ,")
    # A refusal to share data or visit belongs to the consent/visit handler.
    if re.search(r"nao.*(?:contato|consultor|vendedor|autoriz|visitar|loja)", t):
        return None
    if re.fullmatch(r"(?:nao tenho|estou sem) interesse(?: no carro| agora)?", t):
        return SessionStatus.CLOSED, "no_interest"
    if re.search(r"\b(?:ate mais|ate logo|tchau|encerrar atendimento|encerrar conversa)\b", t):
        return SessionStatus.CLOSED, "farewell"
    if re.fullmatch(
        r"(?:obrigad[oa][, ]+)?(?:vou pensar|depois eu vejo|agora nao|mais tarde|outro dia)(?:[, ]+obrigad[oa])?",
        t,
    ):
        return SessionStatus.PAUSED, "considering" if "pensar" in t else "later"
    if (
        re.fullmatch(r"(?:muito )?obrigad[oa](?: pela ajuda| por tudo)?", t)
        and not pending_question
    ):
        return SessionStatus.CLOSED, "thanks"
    return None


def media_mode(text, has_gallery):
    t = norm(text).strip("!.? ")
    if re.search(r"foto|imagem", t) and re.search(r"outra|outras|diferente|mais", t):
        return "another"
    if re.search(
        r"(?:manda|mande|mostra|mostre|envia|envie|reenvia|reenvie).*(?:novamente|de novo)|cade.*(?:foto|imagem)|reenvia|reenvie",
        t,
    ):
        return "repeat"
    if has_gallery and t == "cade":
        return "repeat"
    if re.search(r"foto|imagem|(?:ver|mostra|manda).*(?:traseira|frente|interior|painel)", t):
        return "normal"
    return None


def commercial_state(profile, session):
    if session["status"] == SessionStatus.TRANSFERRED:
        return CommercialState.HANDOFF_CONFIRMED
    if session["status"] in {SessionStatus.CLOSED, SessionStatus.PAUSED}:
        return CommercialState(session["status"])
    if session["status"] == SessionStatus.HANDOFF_PENDING:
        return CommercialState.HANDOFF_PENDING
    if profile.get("consent") == "offered" or profile.get("handoff_offer_pending"):
        return CommercialState.AWAITING_CONSENT
    if profile.get("visit_interest") or profile.get("buying_intent"):
        return CommercialState.INTERESTED
    if profile.get("vehicle_id"):
        return CommercialState.EXPLORING
    return CommercialState.DISCOVERY
