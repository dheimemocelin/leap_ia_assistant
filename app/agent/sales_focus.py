"""Pilot sales decisions in the existing graph; no tools or external actions."""

import re

from app.catalog.media_library import norm


def support_context(text, profile):
    t = norm(text)
    fault = bool(
        re.search(
            r"problema.*\b(?:ar|carro|b10|c10)\b|\b(?:ar|carro|b10|c10)\b.*problema|nao (?:esta |ta )?gelando|defeito|quebrou|nao liga",
            t,
        )
    )
    new_sale = bool(
        re.search(
            r"quero conhecer|quero comprar|pretendo comprar|me (?:mostra|apresenta)|manda.*foto|fotos|trocar.*carro|comprar.*carro",
            t,
        )
    )
    human = bool(re.search(r"(?:falar|conversar).*?(?:vendedor|consultor|humano)", t))
    new_sale = new_sale or bool(
        re.fullmatch(r"(?:o |a )?(?:b10|c10)(?: (?:bev|reev|eletrico|hibrido))?", t.strip("!.? "))
    )
    new_sale = new_sale or bool(re.search(r"\b(?:comprar|compra|pesquisando|escolher)\b", t))
    if human or new_sale:
        return False
    return fault or profile.get("contact_reason") == "service_request"


def support_reply(text, history):
    t = norm(text).strip("!.? ")
    if t in {"ok", "certo", "entendi", "obrigado", "obrigada"}:
        return "Certo. Se depois quiser conhecer os modelos ou pensar numa troca, posso ajudar por aqui."
    previous = " ".join(m["content"] for m in history if m["role"] == "assistant")
    if "assistência técnica" in previous:
        return "Para esse sintoma, o próximo passo é uma avaliação da assistência técnica. Por aqui, meu atendimento é voltado à escolha e compra de um carro."
    return "Eu te ajudo a conhecer os modelos e escolher seu próximo Leapmotor. Para verificar um defeito no ar-condicionado, é necessário atendimento de assistência técnica."


def add_visit_question(plan, profile):
    if (
        plan.get("intent") == "positive"
        and profile.vehicle_id
        and profile.usage
        and profile.visit_interest is None
        and "visit" not in profile.asked
    ):
        plan = {
            **plan,
            "question_keys": ["visit"],
            "suggested_question": {
                "key": "visit",
                "text": "Você gostaria de passar na loja para conhecer o carro de perto?",
            },
        }
    return plan


def showroom_question(text):
    t = norm(text)
    if re.search(
        r"endereco|localizacao|que horas|qual.*horario|horario.*(?:abre|atende|funciona)|como (?:chego|chegar)",
        t,
    ):
        return True
    if re.search(
        r"onde.*(?:loja|shopping|fica|ficam)|(?:qual|em qual).*(?:shopping|piso|entrada)", t
    ):
        return True
    return bool(re.fullmatch(r"onde (?:fica|e|ficam|voces ficam)(?: a loja)?[?!. ]*", t))


def showroom_text(showroom, *, hours=False):
    if hours:
        return (
            ("O horário de atendimento é " + showroom["hours"] + ".")
            if showroom.get("hours")
            else "Ainda não tenho o horário de atendimento confirmado para te passar."
        )
    landmarks = re.sub(
        r"\bpela entrada\b", "pelo acesso", showroom.get("landmarks", ""), flags=re.IGNORECASE
    )
    landmarks = re.sub(r"\bentrada\b", "acesso", landmarks, flags=re.IGNORECASE)
    return f"A loja {showroom['name']} fica {showroom['location']}. {landmarks}".strip()
