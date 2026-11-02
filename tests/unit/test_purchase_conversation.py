import json

import pytest

from app.agent.llm import ModelReply
from app.api.chat import build_agent
from scripts.evaluate_lia_quality import QualityModel


class PurchaseWriter(QualityModel):
    async def complete(self, messages, tools):
        if not tools and messages[-1]["content"].startswith("{"):
            ctx = json.loads(messages[-1]["content"])
            if ctx.get("task") == "compose_conversation" and ctx["intent"] == "purchase":
                return ModelReply(
                    text=json.dumps(
                        {
                            "text": "Vamos partir do que falta para você decidir sobre o B10 BEV.",
                            "question": ctx.get("suggested_question"),
                        }
                    )
                )
        return await super().complete(messages, tools)


@pytest.fixture
def agent():
    value = build_agent(reviewed_catalog=True, test_media=True)
    value.llm = PurchaseWriter()
    return value


async def test_screenshot_journey_continues_into_purchase_instead_of_missing_knowledge(agent):
    for message in ["Oi", "Pessoa Sintetica", "Então quero saber do b10", "BEV", "Muito lega"]:
        await agent.turn("purchase", message)
    result = await agent.turn("purchase", "Como é a questão da compra")
    state = agent.sessions[("local", "purchase")]
    assert state["composition"]["intent"] == "purchase"
    assert state["composition"]["origin"] == "llm"
    assert not state["tool_events"] and not result.media_ids
    assert result.text.count("?") == 1
    assert "não disponho" not in result.text.lower()
    assert not result.handoff_required
    assert state["lead_profile"]["consent"] == "not_requested"
    assert not state["lead_profile"]["buying_intent"]  # Inquiry is not commitment.
    assert state["lead_profile"]["next_action"] == "QUALIFY"


async def test_explicit_buying_intent_uses_writer_without_contact_or_financial_tools(agent):
    await agent.turn("purchase", "B10 BEV")
    result = await agent.turn("purchase", "Pretendo comprar em 2 meses")
    state = agent.sessions[("local", "purchase")]
    assert state["composition"]["intent"] == "purchase"
    assert state["lead_profile"]["buying_intent"]
    assert state["lead_profile"]["purchase_timeline"] == "em 2 meses"
    assert not state["tool_events"] and not result.handoff_required
    assert state["lead_profile"]["consent"] == "not_requested"
    assert state["lead_profile"]["pending_question"] != "purchase_timeline"


async def test_purchase_question_is_not_repeated_and_decline_stays_respected(agent):
    await agent.turn("purchase", "B10 BEV")
    await agent.turn("purchase", "Não quero falar com vendedor")
    first = await agent.turn("purchase", "Como funciona a compra?")
    again = await agent.turn("purchase", "Como funciona a compra?")
    profile = agent.sessions[("local", "purchase")]["lead_profile"]
    assert first.text.count("?") == 1
    assert "?" not in again.text
    assert profile["consent"] == "declined"
    assert not again.handoff_required


@pytest.mark.parametrize(
    "message", ["Quero comprar com desconto", "Quero comprar agora", "Qual o preço para comprar?"]
)
async def test_purchase_route_cannot_override_commercial_policy(agent, message):
    await agent.turn("purchase", "B10 BEV")
    result = await agent.turn("purchase", message)
    state = agent.sessions[("local", "purchase")]
    assert state["usage"]["calls"] == 0
    assert not state["tool_events"] and not result.handoff_required
    assert not result.source_ids


async def test_social_typo_after_gallery_is_recognized_without_technical_lookup(agent):
    await agent.turn("purchase", "B10 BEV")
    await agent.turn("purchase", "Muito lega")
    state = agent.sessions[("local", "purchase")]
    assert state["composition"]["intent"] == "positive"
    assert not state["tool_events"]


async def test_visit_goal_trade_in_and_customer_details_are_saved_and_reloaded(agent, tmp_path):
    from app.pilot_store import PilotStore

    store = PilotStore(str(tmp_path / "pilot.sqlite3"))
    thread = store.open_thread("synthetic-whatsapp-contact", "whatsapp:synthetic-instance")
    agent.memory_store = store
    turns = []
    for text in [
        "Oi",
        "Me chamo Pessoa Sintetica",
        "B10 BEV",
        "Muito legal",
        "Como é a questão da compra",
        "Sim",
        "Sábado de manhã",
        "Tenho um carro na troca",
    ]:
        result = await agent.turn(thread["conversation_id"], text, owner=thread["owner"])
        turns.append(result)
        assert result.text.count("?") <= 1
        assert not result.handoff_required
    assert "loja" in turns[4].text
    assert "dia e período" in turns[5].text
    assert "troca" in turns[6].text
    saved = store.load_state(thread["owner"], thread["conversation_id"])["lead_profile"]
    assert saved["display_name"] == "Pessoa Sintetica"
    assert saved["vehicle_id"] == "b10-bev"
    assert saved["visit_interest"] is True
    assert saved["visit_preference"] == "sabado / manha"
    assert saved["trade_in_interest"] is True
    assert saved["consent"] == "not_requested"
    with store.connect() as db:
        payload = json.loads(db.execute("select payload from pilot_opportunities").fetchone()[0])
    assert payload["visit_preference"] == "sabado / manha"
    assert payload["trade_in_interest"] is True and payload["status"] == "local_only"
    assert "authorized_handoff" not in payload
    reopened = PilotStore(str(tmp_path / "pilot.sqlite3"))
    assert reopened.load_state(thread["owner"], thread["conversation_id"])["lead_profile"] == saved


@pytest.mark.parametrize("answer", ["Não", "Não quero ir à loja"])
async def test_visit_refusal_is_respected_without_repeated_invitation(agent, answer):
    await agent.turn("purchase", "B10 BEV")
    await agent.turn("purchase", "Como é a compra?")
    declined = await agent.turn("purchase", answer)
    assert "?" not in declined.text
    repeated = await agent.turn("purchase", "Como é a compra?")
    assert "conhecer o carro de perto na loja?" not in repeated.text
    assert agent.sessions[("local", "purchase")]["lead_profile"]["visit_interest"] is False


async def test_no_trade_in_is_saved_without_valuation_or_contact_consent(agent):
    for text in ["B10 BEV", "Quero comprar", "Sim", "Sábado à tarde", "Não tenho carro"]:
        result = await agent.turn("purchase", text)
    profile = agent.sessions[("local", "purchase")]["lead_profile"]
    assert profile["trade_in_interest"] is False
    assert profile["visit_preference"] == "sabado / tarde"
    assert not profile["handoff_summary"] and not result.handoff_required
    assert profile["consent"] == "not_requested"


async def test_trade_in_valuation_stays_blocked_by_existing_policy(agent):
    await agent.turn("purchase", "B10 BEV")
    result = await agent.turn("purchase", "Quanto vale meu usado na troca?")
    state = agent.sessions[("local", "purchase")]
    assert state["usage"]["calls"] == 0
    assert not state["tool_events"] and not result.handoff_required


async def test_visit_preference_never_claims_a_confirmed_appointment(agent):
    for text in ["B10 BEV", "Quero comprar", "Sim", "Sábado de manhã"]:
        result = await agent.turn("purchase", text)
    assert "agendad" not in result.text.lower()
    assert "confirmad" not in result.text.lower()
    assert (
        agent.sessions[("local", "purchase")]["lead_profile"]["visit_preference"]
        == "sabado / manha"
    )


async def test_model_cannot_confirm_an_appointment_or_accept_trade_in(agent):
    class FalseCommitment(PurchaseWriter):
        async def complete(self, messages, tools):
            if not tools and messages[-1]["content"].startswith("{"):
                ctx = json.loads(messages[-1]["content"])
                if ctx.get("task") == "compose_conversation" and ctx["intent"] == "purchase":
                    return ModelReply(
                        text=json.dumps(
                            {"text": "Sua visita está agendada e aceitamos seu carro na troca."}
                        )
                    )
            return await super().complete(messages, tools)

    await agent.turn("purchase", "B10 BEV")
    agent.llm = FalseCommitment()
    result = await agent.turn("purchase", "Como é a compra?")
    assert "agendada" not in result.text and "aceitamos" not in result.text
    assert (
        agent.sessions[("local", "purchase")]["composition"]["fallback_reason"]
        == "unauthorized_store_commitment"
    )
    assert not result.handoff_required
