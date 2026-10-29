"""Deterministic progressive qualification; no model authority or outbound CRM action."""

import re
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.catalog.media_library import norm
from app.domain.response import AssistantResponse

YES = {"sim", "quero", "pode", "claro", "autorizo", "pode sim", "sim por favor"}
NO = {"nao", "nao quero", "prefiro nao", "agora nao"}


class LeadProfile(BaseModel):
    interest_model: str | None = None
    powertrain: str | None = None
    vehicle_id: str | None = None
    usage: str | None = None
    needs: list[str] = Field(default_factory=list)
    objections: list[str] = Field(default_factory=list)
    knows_brand: bool = False
    visit_interest: bool | None = None
    purchase_timeline: str | None = None
    buying_intent: bool = False
    signals: list[str] = Field(default_factory=list)
    consent: Literal["not_requested", "offered", "granted", "declined"] = "not_requested"
    consent_at: str | None = None
    consent_scope: str | None = None
    display_name: str | None = None
    name_prompted: bool = False
    contact_name: str | None = None
    contact_phone: str | None = None
    pending_question: str | None = None
    asked: list[str] = Field(default_factory=list)
    greeted: bool = False
    next_action: str = "understand_interest"
    temperature: Literal["frio", "morno", "quente"] = "frio"
    qualification_reasons: list[str] = Field(default_factory=list)
    handoff_summary: dict | None = None


def response(text, *, sources=None, media=None, handoff=False):
    return AssistantResponse(
        text=text,
        source_ids=sources or [],
        media_ids=media or [],
        confidence="grounded" if sources else "insufficient_evidence",
        handoff_required=handoff,
    ).model_dump(mode="json")


def classify(profile: LeadProfile):
    reasons = []
    if profile.interest_model:
        reasons.append("modelo identificado")
    if profile.usage:
        reasons.append("uso informado")
    if profile.needs:
        reasons.append("prioridade informada")
    if profile.visit_interest:
        reasons.append("interesse explícito em visita")
    if profile.buying_intent:
        reasons.append("intenção explícita de compra")
    if profile.purchase_timeline:
        reasons.append("prazo informado espontaneamente")
    profile.temperature = (
        "quente"
        if profile.visit_interest or profile.buying_intent
        else "morno"
        if profile.interest_model and (profile.usage or profile.needs or profile.signals)
        else "frio"
    )
    profile.qualification_reasons = reasons


def offer_contact(profile: LeadProfile):
    if profile.consent == "declined":
        return response(
            "Esse assunto precisa de um consultor. Como você preferiu não compartilhar seus dados, não vou solicitar contato.",
            handoff=True,
        )
    if profile.consent == "granted":
        return collect_contact(profile)
    profile.consent = "offered"
    profile.pending_question = "consent"
    profile.next_action = "await_contact_consent"
    return response(
        "Posso preparar a continuidade com um consultor. Você autoriza compartilhar seu nome, telefone e interesse neste veículo para esse contato?",
        handoff=True,
    )


def collect_contact(profile: LeadProfile):
    if profile.consent == "granted" and not profile.contact_name and profile.display_name:
        profile.contact_name = profile.display_name
    if not profile.contact_name:
        profile.pending_question = "name"
        profile.next_action = "collect_name"
        return response("Como você gostaria que eu registrasse seu nome?", handoff=True)
    if not profile.contact_phone:
        profile.pending_question = "phone"
        profile.next_action = "collect_phone"
        return response("Qual telefone, com DDD, você prefere usar para o contato?", handoff=True)
    classify(profile)
    profile.pending_question = None
    profile.next_action = "handoff_prepared"
    profile.handoff_summary = {
        "status": "prepared_not_sent",
        "model": profile.interest_model,
        "powertrain": profile.powertrain,
        "vehicle_id": profile.vehicle_id,
        "usage": profile.usage,
        "needs": profile.needs,
        "objections": profile.objections,
        "visit_interest": profile.visit_interest,
        "purchase_timeline": profile.purchase_timeline,
        "temperature": profile.temperature,
        "qualification_reasons": profile.qualification_reasons,
        "contact": {"name": profile.contact_name, "phone": profile.contact_phone},
        "consent": {
            "status": "granted",
            "at": profile.consent_at,
            "purpose": "contact_by_human_consultant",
            "scope": profile.consent_scope,
        },
    }
    return response(
        "Obrigado. Deixei o resumo e o contato preparados nesta conversa. Ainda não foram enviados a um consultor.",
        handoff=True,
    )


def next_question(profile: LeadProfile):
    choices = []
    if profile.usage is None:
        choices.append(("usage", "Como você pretende usar o carro no dia a dia?"))
    if not profile.needs:
        choices.append(("need", "O que pesa mais na sua escolha: espaço, conforto ou autonomia?"))
    if profile.visit_interest is None and (profile.usage or profile.needs):
        choices.append(("visit", "Você gostaria de conhecer o carro presencialmente?"))
    if profile.purchase_timeline is None and profile.buying_intent:
        choices.append(("timeline", "Você tem algum prazo em mente para a compra?"))
    for key, text in choices:
        if key not in profile.asked:
            profile.asked.append(key)
            profile.pending_question = key
            profile.next_action = "understand_" + key
            return text
    profile.pending_question = None
    profile.next_action = "answer_customer"
    return ""


def observe(profile: LeadProfile, text: str):
    """Return a response override, plus whether input must be omitted from model history."""
    t = norm(text).strip("!.? ")
    # Preferred name is local personalization, never permission to share a lead.
    named = re.fullmatch(
        r"(?:meu nome [ée]|me chamo|pode me chamar de|sou o|sou a) (.+?)[.! ]*",
        text.strip(),
        re.IGNORECASE,
    )
    awaiting_name = profile.pending_question == "display_name"
    if awaiting_name and t in {"nao", "prefiro nao", "nao quero informar", "nao quero dizer"}:
        profile.pending_question = None
        return response("Tudo bem, seguimos sem nome. Qual modelo você quer conhecer?"), True
    candidate = named.group(1) if named else text.strip() if awaiting_name else ""
    if (
        candidate
        and (
            named
            or not re.search(
                r"\b(quero|uso|cidade|fotos|autonomia|recarga|familia|interesse|potencia|painel|preco|obrigado)\b",
                t,
            )
        )
        and len(candidate) <= 60
        and len(candidate.split()) <= 3
        and re.fullmatch(r"[^\W\d_]+(?:[ '\-][^\W\d_]+)*", candidate, re.UNICODE)
        and t
        not in YES | NO | {"oi", "ola", "bev", "reev", "eletrico", "eletrica", "hibrido", "hibrida"}
    ):
        # Validate before rendering a user supplied name; never treat it as instructions.
        from app.policy.commercial import CommercialPolicyEngine

        if CommercialPolicyEngine().validate_output(candidate):
            profile.display_name = candidate
            profile.name_prompted = True
            profile.pending_question = None
            return response(f"Prazer, {candidate}. Qual modelo você quer conhecer?"), True
    if awaiting_name:
        profile.pending_question = None
    explicit_contact = bool(
        re.search(r"quero (?:falar|conversar) com (?:um |o )?(?:consultor|vendedor)", t)
    ) and not t.startswith("nao")
    decline = (
        "nao quero contato" in t
        or "nao autorizo" in t
        or "nao quero falar com" in t
        or profile.pending_question == "consent"
        and t in NO
    )
    if decline:
        profile.consent = "declined"
        profile.pending_question = None
        profile.contact_name = None
        profile.contact_phone = None
        profile.handoff_summary = None
        profile.next_action = "respect_no_contact"
        return response(
            "Tudo bem, seguimos por aqui sem compartilhar seus dados. Você pode continuar vendo o carro no seu ritmo."
        ), True
    if explicit_contact and profile.consent == "declined":
        profile.consent = "not_requested"
    if profile.pending_question == "consent" and t in YES:
        profile.consent = "granted"
        profile.consent_at = datetime.now(UTC).isoformat()
        profile.consent_scope = (
            f"{profile.interest_model or 'unspecified'}:{profile.powertrain or 'unspecified'}"
        )
        return collect_contact(profile), True
    if profile.consent == "granted" and profile.pending_question in {"name", "phone"}:
        if profile.pending_question == "name":
            if (
                len(text.strip()) >= 2
                and len(text.strip()) <= 100
                and re.fullmatch(r"[^\W\d_]+(?:[ '\-][^\W\d_]+)*", text.strip(), re.UNICODE)
            ):
                profile.contact_name = text.strip()
            else:
                return response(
                    "Não consegui identificar o nome. Como você gostaria de ser chamado?",
                    handoff=True,
                ), True
        else:
            digits = re.sub(r"\D", "", text)
            if re.fullmatch(r"[+\d() .-]+", text.strip()) and 10 <= len(digits) <= 13:
                profile.contact_phone = digits
            else:
                return response(
                    "Não consegui identificar o telefone. Pode informar DDD e número?", handoff=True
                ), True
        return collect_contact(profile), True
    if re.search(r"\bcidade\b|\burbano\b|dia a dia|\btrabalho\b", t):
        profile.usage = "urbano"
    elif re.search(r"estrada|viajar|viagens", t):
        profile.usage = "viagens"
    for pattern, need in [
        (r"espaco|familia|filhos", "espaco"),
        (r"conforto", "conforto"),
        (r"preciso.*autonomia|prioridade.*autonomia", "autonomia"),
    ]:
        if re.search(pattern, t) and need not in profile.needs:
            profile.needs.append(need)
    if (
        re.search(r"receio|medo|preocup|duvida", t)
        and re.search(r"eletric|recarga|bateria|autonomia", t)
        and "mobilidade_eletrica" not in profile.objections
    ):
        profile.objections.append("mobilidade_eletrica")
    if "ja conheco a marca" in t or "ja conheco a leap" in t:
        profile.knows_brand = True
    if re.search(r"quero comprar|pretendo comprar|vou comprar", t) and not t.startswith("nao"):
        profile.buying_intent = True
    match = re.search(r"(?:em|daqui a|nos proximos) (\d{1,2}) (dias|meses|mes)", t)
    if match:
        profile.purchase_timeline = match.group(0)
    if re.search(
        r"conhecer.*(?:presencial|pessoalmente)|ver.*pessoalmente|quero visitar|test[ -]?drive", t
    ) and not t.startswith("nao"):
        profile.visit_interest = True
        if "visit_requested" not in profile.signals:
            profile.signals.append("visit_requested")
        classify(profile)
        return offer_contact(profile), False
    if profile.pending_question == "visit" and t in YES:
        profile.visit_interest = True
        classify(profile)
        return offer_contact(profile), False
    if profile.pending_question == "visit" and t in NO:
        profile.visit_interest = False
        profile.pending_question = None
        return response("Sem problema. Podemos continuar conhecendo o carro por aqui."), False
    if explicit_contact:
        if "human_contact_requested" not in profile.signals:
            profile.signals.append("human_contact_requested")
        return offer_contact(profile), False
    if re.search(r"\d[\d ()+.-]{8,}\d|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text):
        return offer_contact(profile), True
    classify(profile)
    return None, False


def redact_history(text: str):
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[contato omitido]", text)
    return re.sub(r"\+?\d[\d ()+.-]{8,}\d", "[contato omitido]", text)
