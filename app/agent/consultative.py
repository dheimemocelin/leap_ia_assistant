"""Deterministic progressive qualification; no model authority or outbound CRM action."""

import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from app.agent.social import social_intent
from app.catalog.media_library import norm
from app.domain.response import AssistantResponse

YES = {"sim", "quero", "pode", "claro", "autorizo", "pode sim", "sim por favor"}
NO = {"nao", "nao quero", "prefiro nao", "agora nao"}


class SDRAction(StrEnum):
    WELCOME = "WELCOME"
    DISCOVER = "DISCOVER"
    SHOWCASE = "SHOWCASE"
    EDUCATE = "EDUCATE"
    ENGAGE = "ENGAGE"
    QUALIFY = "QUALIFY"
    HANDOFF = "HANDOFF"
    RESPECT_DECLINE = "RESPECT_DECLINE"


class LeadProfile(BaseModel):
    interest_model: str | None = None
    powertrain: str | None = None
    vehicle_id: str | None = None
    usage: str | None = None
    use_contexts: list[str] = Field(default_factory=list)
    first_electric: bool = False
    daily_distance_km: int | None = None
    trip_distance_km: int | None = None
    charging_access: Literal["home", "work", "none"] | None = None
    contact_reason: str | None = None
    commercial_stage: str = "discovery"
    needs: list[str] = Field(default_factory=list)
    objections: list[str] = Field(default_factory=list)
    knows_brand: bool = False
    visit_interest: bool | None = None
    visit_preference: str | None = None
    trade_in_interest: bool | None = None
    purchase_timeline: str | None = None
    buying_intent: bool = False
    signals: list[str] = Field(default_factory=list)
    consent: Literal["not_requested", "offered", "granted", "declined"] = "not_requested"
    consent_at: str | None = None
    consent_scope: str | None = None
    display_name: str | None = None
    name_prompted: bool = False
    showroom_presented: bool = False
    contact_name: str | None = None
    contact_phone: str | None = None
    pending_question: str | None = None
    asked: list[str] = Field(default_factory=list)
    greeted: bool = False
    next_action: str = "understand_interest"
    temperature: Literal["frio", "morno", "quente"] = "frio"
    qualification_reasons: list[str] = Field(default_factory=list)
    handoff_summary: dict | None = None
    handoff_offer_pending: bool = False
    handoff_offer_made: bool = False


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
    if profile.visit_preference:
        reasons.append("preferência de visita informada")
    if profile.trade_in_interest is not None:
        reasons.append("intenção de troca informada")
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
    profile.commercial_stage = (
        "handoff"
        if profile.consent in {"offered", "granted"}
        else "interest"
        if profile.temperature != "frio"
        else "discovery"
    )


def offer_contact(profile: LeadProfile):
    if profile.consent == "declined":
        return response(
            "Seguimos por aqui, respeitando sua preferência de não compartilhar contato.",
        )
    if profile.consent == "granted":
        return collect_contact(profile)
    profile.commercial_stage = "handoff"
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
        "visit_preference": profile.visit_preference,
        "trade_in_interest": profile.trade_in_interest,
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
    """One useful invitation at presentation, never a sequential qualification form."""
    if profile.usage is None and "usage" not in profile.asked:
        profile.asked.append("usage")
        profile.pending_question = "usage"
        profile.next_action = "explore"
        return "Como você pretende usar o carro no dia a dia?"
    profile.pending_question = None
    profile.next_action = "present"
    return ""


def observe(profile: LeadProfile, text: str, *, channel_phone: str | None = None):
    """Return a response override, plus whether input must be omitted from model history."""
    t = norm(text).strip("!.? ")
    # Preferred name is local personalization, never permission to share a lead.
    named = re.fullmatch(
        r"(?:(?:oi|olá)[,! ]+)?(?:meu nome [ée]|me chamo|pode me chamar de|sou o|sou a) (.+?)[.! ]*",
        text.strip(),
        re.IGNORECASE,
    )
    trailing_request = ""
    if named and "," in named.group(1):
        candidate_name, trailing_request = named.group(1).split(",", 1)
    else:
        candidate_name = named.group(1) if named else ""
    awaiting_name = profile.pending_question == "display_name"
    if awaiting_name and t in {"nao", "prefiro nao", "nao quero informar", "nao quero dizer"}:
        profile.pending_question = None
        return response(
            "Tudo bem, seguimos sem nome. "
            + (
                "Podemos continuar conhecendo o carro por aqui."
                if profile.interest_model
                else "Qual modelo você quer conhecer?"
            )
        ), True
    candidate = candidate_name if named else text.strip() if awaiting_name else ""
    if (
        candidate
        and (named or social_intent(text) is None)
        and (
            named
            or not re.search(
                r"\b(quero|uso|vou|tenho|trabalhar|uber|aplicativo|filhos|cidade|fotos|autonomia|recarga|familia|interesse|potencia|painel|preco|obrigado)\b",
                t,
            )
        )
        and len(candidate) <= 60
        and len(candidate.split()) <= 3
        and re.fullmatch(r"[^\W\d_]+(?:[ '\-][^\W\d_]+)*", candidate, re.UNICODE)
        and t
        not in YES
        | NO
        | {"oi", "ola", "opa", "bev", "reev", "eletrico", "eletrica", "hibrido", "hibrida"}
    ):
        # Validate before rendering a user supplied name; never treat it as instructions.
        from app.policy.commercial import CommercialPolicyEngine

        if CommercialPolicyEngine().validate_output(candidate):
            profile.display_name = candidate
            profile.name_prompted = True
            profile.pending_question = None
            if not trailing_request:
                return response(
                    f"Prazer, {candidate}. "
                    + (
                        "Podemos continuar explorando o carro por aqui."
                        if profile.interest_model
                        else "Qual modelo você quer conhecer?"
                    )
                ), True
    if awaiting_name:
        profile.pending_question = None
    explicit_contact = bool(
        re.search(
            r"(?:quero|posso|preciso|gostaria de|pode).*?(?:falar|conversar).*?(?:consultor|vendedor|humano)|(?:me encaminh|me pass|cham[ae]|falar com).*?(?:consultor|vendedor|humano)",
            t,
        )
    ) and not re.search(r"nao.*(?:consultor|vendedor|humano|falar|contato)", t)
    decline = (
        bool(re.search(r"nao.*(?:quero|desejo).*?(?:contato|consultor|vendedor|humano)", t))
        or "nao autorizo" in t
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
        if channel_phone and re.fullmatch(r"[0-9]{8,15}", channel_phone):
            profile.contact_phone = channel_phone
        profile.consent_at = datetime.now(UTC).isoformat()
        profile.consent_scope = (
            f"{profile.interest_model or 'unspecified'}:{profile.powertrain or 'unspecified'}"
        )
        return collect_contact(profile), True
    if (
        profile.consent == "granted"
        and profile.pending_question in {"name", "phone"}
        and social_intent(text) is None
    ):
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
    if re.search(r"uber|99|aplicativo", t) and not re.search(r"nao.*(?:uber|aplicativo)", t):
        profile.usage = "aplicativos"
        if "aplicativos" not in profile.use_contexts:
            profile.use_contexts.append("aplicativos")
    if re.search(r"nunca (?:tive|usei|dirigi).*eletric|primeir[oa].*eletric", t):
        profile.first_electric = True
    if "recarga" in t and "recarga" not in profile.objections:
        profile.objections.append("recarga")
    distance = re.search(r"\b(\d{1,4})\s*(?:km|quilometros)\b", t)
    if distance and profile.pending_question == "travel_pattern":
        profile.trip_distance_km = int(distance.group(1))
        profile.pending_question = None
    if profile.pending_question == "charging_context":
        if re.search(r"em casa|na garagem", t):
            profile.charging_access = "home"
            profile.pending_question = None
        elif "no trabalho" in t:
            profile.charging_access = "work"
            profile.pending_question = None
        elif t in {"nao", "nao tenho", "nao teria"}:
            profile.charging_access = "none"
            profile.pending_question = None
    if distance and profile.pending_question == "daily_distance":
        profile.daily_distance_km = int(distance.group(1))
        profile.pending_question = None
    if re.search(r"familia|filhos", t) and "familia" not in profile.use_contexts:
        profile.use_contexts.append("familia")
    if re.search(r"\bcidade\b|\burbano\b|dia a dia|\btrabalh(?:o|ar)\b", t) and not re.search(
        r"uber|99|aplicativo", t
    ):
        profile.usage = (
            "trabalho" if re.search(r"\btrabalh(?:o|ar)\b", t) and "cidade" not in t else "urbano"
        )
    elif re.search(r"\bestrada\b|\bviajar\b|\bviage(?:m|ns)\b", t):
        profile.usage = "viagens"
    if profile.usage and profile.usage not in profile.use_contexts:
        profile.use_contexts.append(profile.usage)
    for pattern, need in [
        (r"espaco|familia|filhos", "espaco"),
        (r"conforto", "conforto"),
        (r"\beconomia\b|\beconomizar\b", "economia"),
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
    if re.search(r"\b(?:na|para|pra) troca\b|trocar (?:o )?meu (?:carro|veiculo)", t):
        profile.trade_in_interest = not bool(re.search(r"nao.*(?:tenho|troca|trocar)", t))
    if profile.pending_question == "trade_in":
        if t in YES or re.search(r"\btenho\b", t) and not re.search(r"\bnao\b", t):
            profile.trade_in_interest = True
            profile.pending_question = None
        elif t in NO or re.search(r"\bnao tenho\b|sem (?:carro|veiculo)", t):
            profile.trade_in_interest = False
            profile.pending_question = None
    if re.search(r"nao (?:quero|pretendo|posso).*?(?:visitar|loja|presencial)", t):
        profile.visit_interest = False
        profile.pending_question = None
    if explicit_contact:
        if "human_contact_requested" not in profile.signals:
            profile.signals.append("human_contact_requested")
        return offer_contact(profile), False
    if re.search(
        r"conhecer.*(?:presencial|pessoalmente)|ver.*pessoalmente|quero visitar|test[ -]?drive", t
    ) and not t.startswith("nao"):
        profile.visit_interest = True
        if "visit_requested" not in profile.signals:
            profile.signals.append("visit_requested")
        classify(profile)
    if profile.pending_question == "visit" and t in YES:
        profile.visit_interest = True
        profile.pending_question = None
        classify(profile)
    if profile.pending_question == "visit" and t in NO:
        profile.visit_interest = False
        profile.pending_question = None
    if profile.visit_interest is not False and profile.pending_question in {
        "visit",
        "visit_preference",
    }:
        day = re.search(r"\b(hoje|amanha|segunda|terca|quarta|quinta|sexta|sabado|domingo)\b", t)
        period = re.search(r"\b(manha|tarde|noite)\b", t)
        if day or period:
            profile.visit_interest = True
            profile.visit_preference = " / ".join(
                value.group(1) for value in (day, period) if value
            )
            profile.pending_question = None
    if explicit_contact:
        if "human_contact_requested" not in profile.signals:
            profile.signals.append("human_contact_requested")
        return offer_contact(profile), False
    if re.search(r"\d[\d ()+.-]{8,}\d|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text):
        return response(
            "Não é necessário informar contato para continuar conhecendo o carro por aqui."
        ), True
    classify(profile)
    return None, bool(trailing_request)


def redact_history(text: str):
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[contato omitido]", text)
    return re.sub(r"\+?\d[\d ()+.-]{8,}\d", "[contato omitido]", text)


def purchase_plan(profile: LeadProfile, text: str, *, interpreted=False, before=None):
    """Discuss the customer's decision, without inventing a sales process.

    This plan grants no contact, negotiation or transaction permissions. Inquiry
    alone is not a buying commitment; explicit intent is observed separately.
    """
    t = norm(text)
    if re.search(r"nao.*\bcompr", t):
        return None
    changed = before and any(
        getattr(profile, key) != before.get(key)
        for key in ("visit_interest", "visit_preference", "trade_in_interest")
    )
    if not interpreted and not changed and not re.search(r"\b(?:compra|comprar|aquisicao)\b", t):
        return None
    if "purchase_inquiry" not in profile.signals:
        profile.signals.append("purchase_inquiry")
    profile.next_action = SDRAction.QUALIFY
    key, question = None, None
    if not changed and profile.pending_question in {
        "visit",
        "visit_preference",
        "trade_in",
        "purchase_priority",
        "purchase_timeline",
    }:
        pass  # A repeated inquiry must not stack questions while an answer is pending.
    elif changed and profile.visit_interest is False:
        pass  # Respect the refusal without immediately replacing it with another question.
    elif profile.visit_interest is True and not profile.visit_preference:
        key = "visit_preference"
        question = "Que dia e período seriam melhores para você conhecer o carro na loja?"
    elif profile.visit_interest is True and profile.trade_in_interest is None:
        key = "trade_in"
        question = "Você pensa em incluir seu carro atual na troca?"
    elif profile.visit_interest is None and profile.vehicle_id and "visit" not in profile.asked:
        key = "visit"
        question = "Você gostaria de conhecer o carro de perto na loja?"
    elif profile.buying_intent and not profile.purchase_timeline:
        key = "purchase_timeline"
        question = "Você já tem algum prazo em mente para essa compra?"
    elif "purchase_priority" not in profile.asked:
        key = "purchase_priority"
        question = "O que você ainda quer esclarecer antes de decidir?"
    if key in profile.asked:
        key, question = None, None
    return {
        "intent": "purchase",
        "action": SDRAction.QUALIFY,
        "question_keys": [key] if key else [],
        "suggested_question": {"key": key, "text": question} if key else None,
        "facts": [],
    }


class NextBestAction(BaseModel):
    """Server-owned intent and allowed wording; the model cannot introduce claims."""

    action: SDRAction
    variants: list[str]
    question: str = ""


def choose_next_action(profile: LeadProfile, before: dict) -> NextBestAction | None:
    question = ""
    if profile.first_electric and not before.get("first_electric"):
        key = "first_electric_priority"
        variants = [
            "Podemos começar pelo que muda na sua rotina, sem pressupor experiência com elétricos.",
            "Vamos explorar isso a partir do seu dia a dia, sem pular suas dúvidas.",
        ]
        question = "Você quer começar pela recarga ou pela autonomia?"
        action = SDRAction.DISCOVER
    elif profile.objections != before["objections"]:
        key = "charging_context" if "recarga" in profile.objections else "electric_concern"
        variants = [
            "Vamos olhar essa dúvida com calma e considerar sua rotina.",
            "Esse ponto merece atenção antes de você decidir.",
        ]
        question = (
            "Você teria onde carregar em casa ou no trabalho?"
            if key == "charging_context"
            else "Sua dúvida é mais sobre recarga ou autonomia?"
        )
        action = SDRAction.DISCOVER
    elif profile.usage != before["usage"] or profile.needs != before["needs"]:
        if profile.usage == "aplicativos" and profile.needs == before["needs"]:
            key = "daily_distance"
            variants = [
                "Para trabalhar com aplicativo, vale entender sua rotina de uso antes de avaliar o carro.",
                "Entendi: o carro faria parte do seu trabalho com aplicativo. Podemos avaliar o que você precisa nessa rotina.",
            ]
            question = (
                "Em um dia de trabalho, aproximadamente quantos quilômetros você pretende rodar?"
            )
        elif "espaco" in profile.needs:
            key = "family_priority"
            variants = [
                "Para usar com a família, podemos olhar o espaço e o que vocês costumam levar.",
                "Vamos considerar também sua rotina com a família ao explorar o carro.",
            ]
            question = "O que costuma exigir mais espaço: passageiros, bagagem ou os dois?"
        elif profile.usage == "trabalho":
            key = "professional_routine"
            variants = [
                "Vamos considerar sua rotina de trabalho ao explorar o carro.",
                "Entendi que o carro fará parte do seu trabalho. Podemos partir dessa rotina.",
            ]
            question = "Como você pretende usar o carro no trabalho?"
        elif profile.usage == "viagens":
            key = "travel_pattern"
            variants = [
                "Vamos considerar seus trajetos de viagem ao conhecer o carro.",
                "Entendi, as viagens também fazem parte da escolha.",
            ]
            question = "Você costuma fazer qual distância nessas viagens?"
        else:
            key = "use_priority"
            variants = [
                "Para seu uso na cidade, vou considerar as prioridades que você trouxer.",
                "Vamos partir da sua rotina para escolher o que vale explorar no carro.",
            ]
            question = "O que mais importa para você nesse uso?"
        action = SDRAction.ENGAGE
    else:
        return None
    if key in profile.asked:
        question = ""
    else:
        profile.asked.append(key)
    profile.pending_question = key if question else None
    profile.next_action = action
    return NextBestAction(action=action, variants=variants, question=question)
