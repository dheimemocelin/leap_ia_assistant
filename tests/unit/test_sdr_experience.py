"""Synthetic multi-turn regression journeys, with no inference service calls."""

import json

import pytest

from app.agent.llm import ModelReply
from app.api.chat import build_agent


class SDRModel:
    def __init__(self, invalid=False, timeout=False):
        self.calls = []
        self.invalid, self.timeout = invalid, timeout

    async def complete(self, messages, tools):
        self.calls.append(messages)
        if self.timeout:
            raise TimeoutError("synthetic timeout")
        if messages[-1]["content"].startswith("{"):
            context = json.loads(messages[-1]["content"])
            if context.get("task") == "compose_conversation":
                from scripts.evaluate_lia_quality import QualityModel

                if self.invalid:
                    return ModelReply(text="É aprovado para Uber e garante economia de R$ 500.")
                return await QualityModel().complete(messages, tools)
        if "variants" in messages[-1]["content"]:
            if self.invalid:
                return ModelReply(text="É aprovado para Uber e garante economia de R$ 500.")
            return ModelReply(text='{"variant":1}')
        evidence = json.loads(messages[-1]["content"].split(": ", 1)[1])
        return ModelReply(text=json.dumps({"fact_ids": [f["id"] for f in evidence["facts"]]}))


@pytest.fixture
def agent():
    agent = build_agent(reviewed_catalog=True, test_media=True)
    agent.llm = SDRModel()
    return agent


def state(agent):
    return agent.sessions[("local", "sdr")]["lead_profile"]


async def test_exact_uber_incident_continues_discovery(agent):
    autonomy = await agent.turn("sdr", "Qual a autonomia do C10 BEV?")
    assert "338" in autonomy.text and autonomy.source_ids
    photos = await agent.turn("sdr", "Manda fotos.")
    assert photos.media_ids and all("c10-bev" in x for x in photos.media_ids)
    reply = await agent.turn("sdr", "Pensei em utilizar para Uber.")
    assert not reply.handoff_required
    assert "aplicativo" in reply.text and "quilômetros" in reply.text
    assert "confirmar" not in reply.text and not reply.source_ids and not reply.media_ids
    assert state(agent)["usage"] == "aplicativos"
    assert state(agent)["next_action"] == "ENGAGE"
    assert state(agent)["temperature"] == "morno"
    recorded = await agent.turn("sdr", "Uns 200 km")
    assert state(agent)["daily_distance_km"] == 200
    assert "?" not in recorded.text
    repeated = await agent.turn("sdr", "Vou usar para Uber")
    assert "?" not in repeated.text
    assert not repeated.handoff_required


async def test_family_first_electric_charging_visit_and_decline(agent):
    await agent.turn("sdr", "B10")
    photos = await agent.turn("sdr", "BEV")
    assert photos.media_ids
    family = await agent.turn("sdr", "Vou usar com minha família")
    assert "família" in family.text and "405" not in family.text
    first = await agent.turn("sdr", "Nunca tive um elétrico")
    assert "recarga ou" in first.text
    assert state(agent)["first_electric"]
    charging = await agent.turn("sdr", "Tenho dúvidas sobre recarga")
    assert "casa ou no trabalho" in charging.text
    assert "recarga" in state(agent)["objections"]
    changed = await agent.turn("sdr", "Agora quero C10 BEV")
    assert changed.media_ids and all("c10-bev" in x for x in changed.media_ids)
    visit = await agent.turn("sdr", "Quero conhecer presencialmente")
    assert "autoriza" not in visit.text and not visit.handoff_required
    refused = await agent.turn("sdr", "Não quero falar com vendedor")
    assert not refused.media_ids and state(agent)["consent"] == "declined"
    await agent.turn("sdr", "Qual o preço?")
    assert not state(agent)["handoff_summary"]


@pytest.mark.parametrize("invalid,timeout", [(True, False), (False, True)])
async def test_unsafe_or_failed_model_keeps_consultative_safe_fallback(agent, invalid, timeout):
    await agent.turn("sdr", "C10 BEV")
    agent.llm = SDRModel(invalid=invalid, timeout=timeout)
    response = await agent.turn("sdr", "Vou usar para Uber")
    assert "aplicativo" in response.text and not response.handoff_required
    assert "500" not in response.text and "garante" not in response.text
    assert not response.source_ids
    assert agent.sessions[("local", "sdr")]["usage"]["calls"] == 1


async def test_intro_once_name_voluntary_and_topic_changes(agent):
    hello = await agent.turn("sdr", "Oi")
    assert "Lia" in hello.text and "IA" in hello.text
    assert "prefere ser chamado" in hello.text
    named = await agent.turn("sdr", "Me chamo Pessoa Sintetica")
    assert "Lia" not in named.text and "Pessoa Sintetica" in named.text
    await agent.turn("sdr", "B10 REEV")
    await agent.turn("sdr", "Uso na cidade")
    returned = await agent.turn("sdr", "Oi")
    assert "Lia" not in returned.text and "prefere ser chamado" not in returned.text
    assert state(agent)["powertrain"] == "REEV"
    assert state(agent)["display_name"] == "Pessoa Sintetica"
    assert "Pessoa Sintetica" not in json.dumps(agent.llm.calls)


async def test_declining_name_does_not_block_service(agent):
    await agent.turn("sdr", "Oi")
    await agent.turn("sdr", "Prefiro não")
    photos = await agent.turn("sdr", "C10 BEV")
    assert photos.media_ids and not state(agent)["display_name"]
    assert state(agent)["consent"] == "not_requested"


async def test_first_specific_request_answered_before_secondary_question(agent):
    response = await agent.turn("sdr", "Qual a autonomia do C10 BEV?")
    assert response.text.index("338") < response.text.index("prefere ser chamado")
    assert response.text.count("?") == 1
    assert state(agent)["vehicle_id"] == "c10-bev"
    assert state(agent)["contact_reason"] == "vehicle_interest"
    assert state(agent)["greeted"]


async def test_name_and_specific_question_in_first_message(agent):
    response = await agent.turn(
        "sdr", "Oi, me chamo Pessoa Sintetica, qual a autonomia do C10 BEV?"
    )
    assert "338" in response.text and response.source_ids
    assert "prefere ser chamado" not in response.text
    assert state(agent)["display_name"] == "Pessoa Sintetica"
    assert "Pessoa Sintetica" not in json.dumps(agent.llm.calls)
    assert state(agent)["consent"] == "not_requested"


async def test_missing_charging_fact_still_allows_consultative_question(agent):
    # Explicitly remove charging evidence: the expanded official catalog now
    # covers this topic in ordinary use.
    agent.grounding.facts = {
        key: fact for key, fact in agent.grounding.facts.items() if fact.specification != "charging"
    }
    await agent.turn("sdr", "C10 BEV")
    response = await agent.turn("sdr", "Como funciona a recarga?")
    assert not response.source_ids and "detalhe de recarga" in response.text
    assert "casa ou no trabalho" in response.text
    assert response.text.count("?") == 1
    repeated = await agent.turn("sdr", "Como funciona a recarga?")
    assert "?" not in repeated.text


async def test_buying_intent_prepares_only_authorized_handoff(agent):
    await agent.turn("sdr", "C10 BEV")
    result = await agent.turn("sdr", "Pretendo comprar em 2 meses")
    assert "autoriza" not in result.text and not result.handoff_required
    assert state(agent)["buying_intent"]
    assert state(agent)["purchase_timeline"] == "em 2 meses"
    assert state(agent)["temperature"] == "quente"
    assert state(agent)["commercial_stage"] == "interest"
    assert not state(agent)["handoff_summary"]


async def test_declining_name_after_specific_request_keeps_vehicle_context(agent):
    await agent.turn("sdr", "Qual a autonomia do C10 BEV?")
    response = await agent.turn("sdr", "Prefiro não")
    assert "Qual modelo" not in response.text
    assert state(agent)["vehicle_id"] == "c10-bev"
    assert state(agent)["display_name"] is None


async def test_screenshot_trip_and_economy_context_does_not_dead_end(agent):
    for text in ["oi", "Pessoa Sintetica", "o b10", "reev"]:
        await agent.turn("sdr", text)
    result = await agent.turn("sdr", "bom é pra viagem e economia")
    assert not result.handoff_required
    assert "viag" in result.text.lower() and "distância" in result.text
    assert "consultor" not in result.text
    assert state(agent)["usage"] == "viagens"
    assert "economia" in state(agent)["needs"]
    followup = await agent.turn("sdr", "uns 500 km")
    assert not followup.handoff_required
    assert state(agent)["trip_distance_km"] == 500
    assert "consultor" not in followup.text


@pytest.mark.parametrize(
    "message",
    [
        "Quero visitar",
        "Pretendo comprar em 2 meses",
        "Qual o preço?",
        "Qual a bateria?",
        "bom é pra viagem e economia",
    ],
)
async def test_no_automatic_consultant_for_interest_or_missing_facts(agent, message):
    await agent.turn("sdr", "B10 REEV")
    response = await agent.turn("sdr", message)
    assert not response.handoff_required
    assert "consultor" not in response.text.lower() and "vendedor" not in response.text.lower()
    assert "precisa de confirmação por um consultor" not in response.text
    assert state(agent)["consent"] == "not_requested"
    assert not state(agent)["handoff_summary"]


async def test_only_explicit_human_request_starts_handoff_and_topic_can_change(agent):
    await agent.turn("sdr", "B10 BEV")
    await agent.turn("sdr", "Quero visitar")
    request = await agent.turn("sdr", "Pode me passar para um vendedor?")
    assert request.handoff_required and "autoriza" in request.text
    assert state(agent)["next_action"] == "HANDOFF"
    await agent.turn("sdr", "Qual a potência?")
    assert state(agent)["pending_question"] != "consent"
    assert state(agent)["consent"] == "not_requested"
    await agent.turn("sdr", "sim")
    assert state(agent)["consent"] != "granted"


async def test_trip_distance_and_charging_reply_complete_the_discovery(agent):
    await agent.turn("sdr", "B10 REEV")
    await agent.turn("sdr", "pra viagem e economia")
    await agent.turn("sdr", "Uns 500 km")
    answer = await agent.turn("sdr", "Em casa")
    assert state(agent)["charging_access"] == "home"
    assert not answer.handoff_required and "?" not in answer.text
    assert "consultor" not in answer.text


async def test_full_sdr_v2_journey_actions_grounding_and_authorized_summary(agent):
    turns = [
        "oi",
        "Me chamo Pessoa Sintetica",
        "B10",
        "BEV",
        "Vou usar para Uber",
        "Uns 200 km",
        "Vou usar com minha família",
        "Nunca tive um elétrico",
        "Tenho dúvidas sobre recarga",
        "Em casa",
        "Qual o preço?",
        "Quero conhecer presencialmente",
        "Não quero falar com vendedor",
        "Agora quero C10 BEV",
        "Qual a autonomia?",
        "Quero falar com um consultor",
        "sim",
        "11000000000",
    ]
    actions, all_media = [], set()
    for index, text in enumerate(turns):
        result = await agent.turn("sdr", text)
        actions.append(state(agent)["next_action"])
        assert result.text.count("?") <= 1
        assert "Essa informação ainda precisa de confirmação por um consultor" not in result.text
        assert not all_media.intersection(result.media_ids)
        all_media.update(result.media_ids)
        if index < 15:
            assert not result.handoff_required
            assert "consultor" not in result.text.lower() and "vendedor" not in result.text.lower()
        if text == "BEV":
            assert result.media_ids and all("b10-bev" in m for m in result.media_ids)
            assert "?" not in result.text  # objective presentation is sufficient here
        if text == "Qual a autonomia?":
            assert "338" in result.text and result.source_ids
    assert set(actions) == {
        "WELCOME",
        "DISCOVER",
        "SHOWCASE",
        "EDUCATE",
        "ENGAGE",
        "QUALIFY",
        "HANDOFF",
        "RESPECT_DECLINE",
    }
    summary = state(agent)["handoff_summary"]
    assert summary["status"] == "prepared_not_sent"
    assert summary["consent"]["status"] == "granted"
    assert summary["contact"]["phone"] == "11000000000"
    assert summary["vehicle_id"] == "c10-bev"
    assert state(agent)["daily_distance_km"] == 200
    assert "Pessoa Sintetica" not in json.dumps(agent.llm.calls)


async def test_model_cannot_initiate_handoff_or_keep_unused_sources(agent):
    from app.agent.llm import ToolCall

    class ReferralModel:
        async def complete(self, messages, tools):
            if tools:
                return ModelReply(tool_calls=[ToolCall(name="list_vehicles")])
            return ModelReply(text="Sugiro falar com um consultor.")

    agent.llm = ReferralModel()
    response = await agent.turn("sdr", "Quais modelos existem?")
    assert not response.handoff_required
    assert "consultor" not in response.text
    assert not response.source_ids
    assert not state(agent)["handoff_summary"]
