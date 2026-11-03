import json

import pytest

from app.agent.llm import ModelReply
from app.api.chat import build_agent
from scripts.evaluate_lia_quality import QualityModel


class SalesModel(QualityModel):
    async def complete(self, messages, tools):
        if not tools and messages[-1]["content"].startswith("{"):
            context = json.loads(messages[-1]["content"])
            if context.get("task") == "route_conversation":
                return ModelReply(text=json.dumps({"act": "other"}))
        return await super().complete(messages, tools)


@pytest.fixture
def agent():
    a = build_agent(reviewed_catalog=True, test_media=True, orchestration_enabled=True)
    a.sales_focus = True
    a.llm = SalesModel()
    return a


def profile(a):
    return a.sessions[("local", "sale")]["lead_profile"]


async def test_fault_conversation_is_not_misrepresented_as_sales_or_diagnosed(agent):
    for text in [
        "oi",
        "estou com problema no ar do b10",
        "pode me ajudar?",
        "então ele não está gelando",
        "ok",
    ]:
        reply = await agent.turn("sale", text)
        assert "Não consegui buscar" not in reply.text
        assert not reply.handoff_required
        assert not agent.sessions[("local", "sale")]["tool_events"]
        if "problema" in text or "gelando" in text:
            assert "assistência" in reply.text.lower() or "assistencia" in reply.text.lower()
    assert profile(agent)["contact_reason"] == "service_request"


async def test_sales_opening_has_one_purpose_and_no_name_gate(agent):
    reply = await agent.turn("sale", "oi")
    assert "Lia" in reply.text and "assistente virtual" in reply.text
    assert reply.text.count("?") == 1
    assert "próximo carro" in reply.text
    assert not profile(agent)["name_prompted"]


async def test_value_before_name_and_progression_to_store_visit(agent):
    await agent.turn("sale", "oi")
    await agent.turn("sale", "Quero conhecer o B10")
    photos = await agent.turn("sale", "BEV")
    assert photos.media_ids
    assert "chamar" in photos.text or "chamado" in photos.text
    named = await agent.turn("sale", "Pessoa Sintetica")
    assert profile(agent)["display_name"] == "Pessoa Sintetica"
    assert "dia a dia" in named.text
    await agent.turn("sale", "Vou usar na cidade")
    interested = await agent.turn("sale", "Gostei muito")
    assert "loja" in interested.text.lower()
    assert profile(agent)["pending_question"] == "visit"
    yes = await agent.turn("sale", "sim")
    assert profile(agent)["visit_interest"] is True
    assert "dia" in yes.text.lower() or "período" in yes.text.lower()
    await agent.turn("sale", "amanhã à tarde")
    assert profile(agent)["visit_preference"]
    assert profile(agent)["consent"] == "not_requested"
    assert not yes.handoff_required


async def test_service_context_does_not_trap_new_sales_interest(agent):
    await agent.turn("sale", "Meu ar não está gelando")
    reply = await agent.turn("sale", "Quero conhecer o C10 BEV")
    assert reply.media_ids
    assert profile(agent)["vehicle_id"] == "c10-bev"
    assert "assistência" not in reply.text


async def test_trade_in_and_visit_refusal_respected(agent):
    await agent.turn("sale", "B10 BEV")
    await agent.turn("sale", "Prefiro não informar nome")
    reply = await agent.turn("sale", "Tenho um carro na troca")
    assert profile(agent)["trade_in_interest"] is True
    assert "avaliação" in reply.text
    refused = await agent.turn("sale", "Não quero visitar a loja agora")
    assert profile(agent)["visit_interest"] is False
    assert not refused.handoff_required


async def test_price_keeps_store_direction_without_values_or_handoff(agent):
    await agent.turn("sale", "B10 BEV")
    reply = await agent.turn("sale", "Qual o preço?")
    assert "loja" in reply.text.lower()
    assert "R$" not in reply.text and not reply.handoff_required
    assert profile(agent)["pending_question"] == "visit"


async def test_sales_progress_is_persisted_locally_without_crm_consent(agent, tmp_path):
    from app.pilot_store import PilotStore

    store = PilotStore(str(tmp_path / "pilot.sqlite3"))
    thread = store.open_thread("synthetic-person", "whatsapp:synthetic")
    agent.memory_store = store
    for message in [
        "Quero conhecer o B10",
        "BEV",
        "Pessoa Sintetica",
        "Vou usar na cidade",
        "Gostei muito",
        "sim",
        "amanhã à tarde",
        "Tenho um carro na troca",
    ]:
        await agent.turn(thread["conversation_id"], message, owner=thread["owner"])
    saved = store.load_state(thread["owner"], thread["conversation_id"])["lead_profile"]
    assert saved["display_name"] == "Pessoa Sintetica"
    assert saved["vehicle_id"] == "b10-bev"
    assert saved["usage"] == "urbano" and saved["visit_interest"] is True
    assert saved["visit_preference"] and saved["trade_in_interest"] is True
    assert saved["consent"] == "not_requested"
    with store.connect() as db:
        payload = json.loads(
            db.execute(
                "SELECT payload FROM pilot_opportunities WHERE owner=?", (thread["owner"],)
            ).fetchone()[0]
        )
    assert payload["trade_in_interest"] and payload["visit_interest"]
    assert "authorized_handoff" not in payload


@pytest.fixture
def showroom_agent(agent):
    agent.showroom = {
        "name": "Leapmotor Autovema Mobility",
        "location": "no 1º piso do Porto Velho Shopping",
        "landmarks": "Acesso próximo pela Entrada F, perto da CVC.",
        "hours": "",
    }
    return agent


async def test_showroom_location_is_answered_without_llm_or_vehicle_selection(showroom_agent):
    reply = await showroom_agent.turn("sale", "Onde fica a loja?")
    assert "Porto Velho Shopping" in reply.text and "acesso F" in reply.text
    assert "CVC" in reply.text and reply.source_ids
    assert showroom_agent.sessions[("local", "sale")]["usage"]["calls"] == 0
    assert not showroom_agent.sessions[("local", "sale")]["tool_events"]


async def test_unknown_showroom_hours_are_not_invented(showroom_agent):
    reply = await showroom_agent.turn("sale", "Qual o horário da loja?")
    assert "não tenho o horário" in reply.text
    assert not any(x in reply.text for x in ["9h", "10h", "22h"])


async def test_visit_invitation_includes_configured_location_once(showroom_agent):
    a = showroom_agent
    for text in ["B10 BEV", "Pessoa Sintetica", "Vou usar na cidade", "Gostei muito"]:
        reply = await a.turn("sale", text)
    assert "Porto Velho Shopping" in reply.text
    assert profile(a)["showroom_presented"] is True
    next_reply = await a.turn("sale", "sim")
    assert "acesso F" not in next_reply.text


async def test_showroom_info_does_not_override_visit_refusal(showroom_agent):
    await showroom_agent.turn("sale", "B10 BEV")
    result = await showroom_agent.turn("sale", "Não quero visitar a loja agora")
    assert profile(showroom_agent)["visit_interest"] is False
    assert not result.handoff_required


async def test_explicit_store_interest_is_saved_without_booking_promise(showroom_agent):
    await showroom_agent.turn("sale", "B10 BEV")
    result = await showroom_agent.turn("sale", "Quero ir na loja amanhã à tarde")
    assert profile(showroom_agent)["visit_interest"] is True
    assert profile(showroom_agent)["visit_preference"]
    assert "confirmada" not in result.text.lower() and not result.handoff_required


async def test_work_and_economy_is_usage_even_when_classifier_fails(agent):
    class BrokenClassifier(SalesModel):
        async def complete(self, messages, tools):
            if "route_conversation" in messages[-1].get("content", ""):
                raise TimeoutError("synthetic")
            return await super().complete(messages, tools)

    agent.llm = BrokenClassifier()
    for message in ["B10 BEV", "Pessoa Sintetica"]:
        await agent.turn("sale", message)
    reply = await agent.turn("sale", "Então quero trabalhar e economizar")
    assert profile(agent)["usage"] == "trabalho"
    assert "economia" in profile(agent)["needs"]
    assert "Pode me contar o que você quer saber" not in reply.text
    assert "trabalho" in reply.text.lower() or "rotina" in reply.text.lower()


async def test_electric_liters_question_is_explained_with_approved_range(agent):
    await agent.turn("sale", "B10 BEV")
    reply = await agent.turn("sale", "Ele faz quanto com litro?")
    assert "por carga" in reply.text.lower()
    assert "elétrico" in reply.text.lower()
    assert "288" in reply.text and reply.source_ids
    assert agent.sessions[("local", "sale")]["usage"]["calls"] == 0
    assert not agent.sessions[("local", "sale")]["tool_events"]
    assert not reply.handoff_required


async def test_general_vehicle_discovery_lists_approved_models_without_engine_quiz(agent):
    reply = await agent.turn("sale", "Quero saber mais sobre os veículos")
    assert "B10" in reply.text and "C10" in reply.text
    assert "motorização você deseja" not in reply.text
    assert agent.sessions[("local", "sale")]["tool_events"][0]["name"] == "list_vehicles"


async def test_classifier_failure_preserves_deterministically_observed_family_need(agent):
    class BrokenClassifier(SalesModel):
        async def complete(self, messages, tools):
            if "route_conversation" in messages[-1].get("content", ""):
                raise TimeoutError("synthetic")
            return await super().complete(messages, tools)

    agent.llm = BrokenClassifier()
    await agent.turn("sale", "B10 BEV")
    await agent.turn("sale", "Pessoa Sintetica")
    reply = await agent.turn("sale", "Levar os meus filhos")
    assert "espaco" in profile(agent)["needs"]
    assert "Pode me contar o que você quer saber" not in reply.text
    assert agent.sessions[("local", "sale")]["usage"]["calls"] == 1


async def test_trunk_liters_are_not_confused_with_fuel_economy(agent):
    await agent.turn("sale", "B10 BEV")
    reply = await agent.turn("sale", "Quantos litros tem o porta-malas?")
    assert "405" in reply.text and "por carga" not in reply.text


async def test_repeated_work_context_does_not_fall_into_missing_technical_facts(agent):
    for text in ["B10 BEV", "Pessoa Sintetica", "Então quero trabalhar e economizar"]:
        await agent.turn("sale", text)
    reply = await agent.turn("sale", "Quero trabalhar e economizar")
    assert not agent.sessions[("local", "sale")]["tool_events"]
    assert "loja" in reply.text
    assert profile(agent)["pending_question"] == "visit"
