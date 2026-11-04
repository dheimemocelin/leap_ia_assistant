"""Social speech acts: model-written phrasing, bounded independently of the provider."""

import re
from typing import Literal

from app.catalog.media_library import norm

Reaction = Literal["positive", "negative", "doubt", "more", "short"]


def social_intent(text: str) -> Reaction | None:
    text = norm(text).strip("!.? ")
    if re.fullmatch(
        r"(?:(?:ah|nossa|uau)[, ]+)?(?:achei |eu achei )?(?:que legal|muito legal?|legal|gostei|muito bonito|bonito|interessante|bacana|amei|adorei|curti|lindo|show|top)(?: mesmo| demais| bastante| muito)?",
        text,
    ):
        return "positive"
    if re.fullmatch(r"nao (?:gostei|curti)(?: muito)?", text):
        return "negative"
    if re.fullmatch(r"(?:eu )?tenho duvidas?", text):
        return "doubt"
    if re.fullmatch(r"(?:eu )?quero saber mais", text):
        return "more"
    if re.fullmatch(r"(?:ok|entendi|certo|beleza|obrigad[oa])(?: mesmo|,? entendi)?", text):
        return "short"
    return None


def fallback_social(kind: Reaction) -> str:
    # Provider failure is not absence of technical evidence. No forced question.
    return {
        "short": "Certo, seguimos a partir do que você já me contou.",
        "positive": "Podemos continuar explorando o que chamou sua atenção no carro.",
        "negative": "Entendi sua impressão. Podemos explorar o que você procura no carro.",
        "doubt": "Podemos esclarecer suas dúvidas por aqui, um ponto de cada vez.",
        "more": "Podemos continuar conhecendo o carro pelo que mais importa para você.",
    }[kind]


def playful_signal(text):
    """Unambiguous fast paths; open-ended tone interpretation stays in the router."""
    t = norm(text).strip("!.? ")
    compact = re.sub(r"\s+", "", t)
    if re.fullmatch(r"k{2,}|(?:ha){2,}|(?:rs){2,}|[😂🤣😄]+", compact):
        return "banter", ""
    if re.search(r"\b(?:lua|marte|voar)\b", t) and re.search(r"carro|veiculo|b10|c10", t):
        return "banter", ""
    match = re.search(r"\b(fusca|opala|kombi|uno)\b", t)
    if match and not re.search(r"\bb10\b|\bc10\b|troca|usado|avaliacao", t):
        return "outside_catalog", match[0]
    return None
