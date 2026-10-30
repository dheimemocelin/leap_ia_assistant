"""Social speech acts: model-written phrasing, bounded independently of the provider."""

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.catalog.media_library import norm
from app.policy.commercial import CommercialPolicyEngine

Reaction = Literal["positive", "negative", "doubt", "more"]


def social_intent(text: str) -> Reaction | None:
    text = norm(text).strip("!.? ")
    if re.fullmatch(
        r"(?:ah[, ]+)?(?:que legal|legal|gostei|muito bonito|bonito|interessante|bacana)(?: mesmo| demais)?",
        text,
    ):
        return "positive"
    if re.fullmatch(r"nao gostei(?: muito)?", text):
        return "negative"
    if re.fullmatch(r"(?:eu )?tenho duvidas?", text):
        return "doubt"
    if re.fullmatch(r"(?:eu )?quero saber mais", text):
        return "more"
    return None


class SocialQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: Literal["usage", "priority", "doubt", "objection"]
    text: str = Field(min_length=1, max_length=140)


class SocialDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    acknowledgement: str = Field(min_length=1, max_length=240)
    question: SocialQuestion | None = None


# Words, not sentence templates: the model composes its own short social response.
# Technical attributes, numbers, financial claims, promises and external actions cannot
# be introduced via this surface. Facts remain on the existing reviewed-fact path.
_SOCIAL_VOCABULARY = """a ao aos as o os um uma de da das do dos em no na nos nas por para pra com sem e ou mas se que
como qual quais isso esse essa este esta nesse nessa deste dessa esses essas ele ela dele dela
voce voces seu sua seus suas eu me mim te aqui ja ainda agora mais tambem entao sim nao tudo
bem certo entendi entender entendo percebi perceber chamou chama atencao visual aparencia
interesse olhar vendo ver explorar continuar continuamos podemos pode posso pelo pela pelos
pelas jeito forma sentido faz quer quero quiser procura procurando pretende usar uso rotina dia
dias trabalho familia viagens conhecer conhecendo conversa conversar ponto pontos aspecto
aspectos esclarecer duvida duvidas primeiro primeira proximo proxima prioridade prioridades
importa importante interessa interessante gostou gostei agradou agrada gosto preferencia melhor
preferencias descobrir deseja desejaria prefere levar seguir seguimos sobre quanto deles desse
foi era obrigado obrigada tranquilo b10 c10 bev reev modelo carro veiculo impressao"""
SOCIAL_WORDS = frozenset(_SOCIAL_VOCABULARY.split())


def safe_social_text(text: str, *, question=False) -> bool:
    if not re.fullmatch(r"[\w\s.,!?;:…—–'\-]+", text):
        return False
    if not CommercialPolicyEngine().validate_output(text):
        return False
    if text.count("?") != (1 if question else 0):
        return False
    words = set(re.findall(r"\b\w+\b", norm(text)))
    if not words or not words <= SOCIAL_WORDS:
        return False
    # Prevent attribute/ownership assertions, even with otherwise conversational words.
    return not re.search(
        r"\b(?:b10|c10|bev|reev|modelo|carro|veiculo)\s+(?:e|tem|faz|foi|era)\b", norm(text)
    )


def render_social(draft: SocialDraft, profile, kind: Reaction) -> str:
    combined = draft.acknowledgement + (" " + draft.question.text if draft.question else "")
    models = set(re.findall(r"\b(?:b10|c10)\b", norm(combined)))
    powertrains = set(re.findall(r"\b(?:bev|reev)\b", norm(combined)))
    if models - {norm(profile.interest_model or "")} or powertrains - {
        norm(profile.powertrain or "")
    }:
        raise ValueError("Different vehicle in social turn")
    if not safe_social_text(draft.acknowledgement):
        raise ValueError("Unapproved social wording")
    text = draft.acknowledgement
    if draft.question is None:
        return text
    question = draft.question
    if not safe_social_text(question.text, question=True):
        raise ValueError("Unapproved social question")
    allowed_keys = {
        "positive": {"usage", "priority"},
        "negative": {"objection"},
        "doubt": {"doubt"},
        "more": {"priority", "usage"},
    }
    if question.key not in allowed_keys[kind]:
        raise ValueError("Question unrelated to speech act")
    key = "usage" if question.key == "usage" else "social_" + question.key
    if (
        key in profile.asked
        or question.key == "usage"
        and profile.usage
        or question.key == "priority"
        and profile.needs
    ):
        return text
    profile.asked.append(key)
    profile.pending_question = key
    return text + " " + question.text


def fallback_social(kind: Reaction) -> str:
    # Provider failure is not absence of technical evidence. No forced question.
    return {
        "positive": "Podemos continuar explorando o que chamou sua atenção no carro.",
        "negative": "Entendi sua impressão. Podemos explorar o que você procura no carro.",
        "doubt": "Podemos esclarecer suas dúvidas por aqui, um ponto de cada vez.",
        "more": "Podemos continuar conhecendo o carro pelo que mais importa para você.",
    }[kind]
