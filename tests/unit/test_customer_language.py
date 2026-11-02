import json

import pytest

from app.agent.llm import ModelReply
from app.api.chat import build_agent
from app.pilot_store import PilotStore
from scripts.evaluate_lia_quality import QualityModel


def make_agent(store=None):
    agent = build_agent(reviewed_catalog=True, test_media=True)
    agent.llm = QualityModel()
    agent.memory_store = store
    return agent


def assert_customer_language(response):
    lowered = response.text.lower()
    for technical in [
        "base aprovada",
        "resumo institucional",
        "fotos aprovadas",
        "contexto está preservado",
    ]:
        assert technical not in lowered
    assert response.text.count("?") <= 1


async def test_new_customer_screenshot_journey_can_choose_first_option_without_codes():
    agent = make_agent()
    for message in [
        "Boa noite",
        "Ana Sintetica",
        "Qual você tem? Ainda não conheço sobre a marca",
        "Ok",
        "Pode ser",
    ]:
        response = await agent.turn("new-customer", message)
        assert_customer_language(response)
        assert "BEV" not in response.text and "REEV" not in response.text
    offered = agent.sessions[("local", "new-customer")]["offered_vehicle_ids"]
    assert offered == ["b10-bev", "b10-reev", "c10-bev"]
    response = await agent.turn("new-customer", "A primeira opção")
    state = agent.sessions[("local", "new-customer")]
    assert state["lead_profile"]["vehicle_id"] == "b10-bev"
    assert state["lead_profile"]["display_name"] == "Ana Sintetica"
    assert response.media_ids and state["usage"]["calls"] == 0
    assert "B10 elétrico" in response.text
    assert "BEV" not in response.text and "REEV" not in response.text
    records = {m.id: m for m in agent.media.records}
    assert all(records[mid].vehicle_id == "b10-bev" for mid in response.media_ids)
    assert not response.handoff_required


async def test_unknown_ordinal_is_clarified_without_guessing_or_provider_call():
    agent = make_agent()
    response = await agent.turn("no-menu", "A primeira opção")
    assert not response.media_ids and not response.source_ids
    assert agent.sessions[("local", "no-menu")]["usage"]["calls"] == 0
    assert agent.sessions[("local", "no-menu")]["lead_profile"]["vehicle_id"] is None


async def test_friendly_variant_menu_and_simple_explanation_preserve_context():
    agent = make_agent()
    response = await agent.turn("explain", "Quero conhecer o B10")
    assert "elétrica" in response.text and "ultra-híbrida" in response.text
    assert "BEV" not in response.text and "REEV" not in response.text
    explanation = await agent.turn("explain", "Não entendi essas siglas BEV e REEV")
    assert "só bateria" in explanation.text and "motor a combustão" in explanation.text
    state = agent.sessions[("local", "explain")]
    assert state["lead_profile"]["vehicle_id"] is None
    assert not explanation.media_ids and explanation.source_ids
    response = await agent.turn("explain", "A segunda opção")
    assert agent.sessions[("local", "explain")]["lead_profile"]["vehicle_id"] == "b10-reev"
    assert response.media_ids and "ultra-híbrido" in response.text


async def test_offered_options_survive_server_restart_without_cross_contact_memory(tmp_path):
    store = PilotStore(str(tmp_path / "contacts.sqlite3"))
    one = store.open_thread("synthetic-contact-one", "whatsapp:test")
    two = store.open_thread("synthetic-contact-two", "whatsapp:test")
    agent = make_agent(store)
    await agent.turn(one["conversation_id"], "Quero conhecer o B10", owner=one["owner"])
    restarted = make_agent(PilotStore(str(tmp_path / "contacts.sqlite3")))
    selected = await restarted.turn(one["conversation_id"], "A segunda opção", owner=one["owner"])
    assert selected.media_ids
    assert (
        restarted.sessions[(one["owner"], one["conversation_id"])]["lead_profile"]["vehicle_id"]
        == "b10-reev"
    )
    other = await restarted.turn(two["conversation_id"], "A segunda opção", owner=two["owner"])
    assert not other.media_ids
    assert (
        restarted.sessions[(two["owner"], two["conversation_id"])]["lead_profile"]["vehicle_id"]
        is None
    )


async def test_explicit_model_change_invalidates_old_menu():
    agent = make_agent()
    await agent.turn("change", "Quero conhecer o B10")
    await agent.turn("change", "Agora quero o C10")
    response = await agent.turn("change", "A primeira opção")
    assert not response.media_ids
    assert agent.sessions[("local", "change")]["lead_profile"]["vehicle_id"] == "c10-bev"


@pytest.mark.parametrize(
    "message",
    ["O que é BEV?", "O que significa Beev?", "Qual a diferença entre elétrico e híbrido?"],
)
async def test_terms_are_explained_without_forcing_a_model_choice(message):
    agent = make_agent()
    response = await agent.turn("terms", message)
    assert "só bateria" in response.text and response.source_ids
    assert not response.media_ids
    assert agent.sessions[("local", "terms")]["lead_profile"]["vehicle_id"] is None


async def test_model_internal_jargon_never_reaches_customer():
    class Jargon(QualityModel):
        async def complete(self, messages, tools):
            return ModelReply(
                text=json.dumps(
                    {"text": "Nossa base aprovada ainda não tem um resumo institucional revisado."}
                )
            )

    agent = make_agent()
    await agent.turn("jargon", "B10 elétrico")
    agent.llm = Jargon()
    response = await agent.turn("jargon", "Muito legal")
    assert_customer_language(response)
    assert (
        agent.sessions[("local", "jargon")]["composition"]["fallback_reason"] == "internal_jargon"
    )


async def test_ordinal_cannot_authorize_negotiation():
    agent = make_agent()
    await agent.turn("policy", "Quero conhecer o B10")
    response = await agent.turn("policy", "A primeira opção com desconto")
    assert not response.media_ids and not response.handoff_required
    assert agent.sessions[("local", "policy")]["usage"]["calls"] == 0


async def test_pre_update_server_menu_can_be_resumed_but_user_text_cannot_forge_it(tmp_path):
    store = PilotStore(str(tmp_path / "legacy.sqlite3"))
    template = "Podemos explorar B10 BEV, B10 REEV, C10 BEV. Qual você quer conhecer primeiro?"
    for role, expected_media in [("assistant", True), ("user", False)]:
        thread = store.open_thread("synthetic-" + role, "whatsapp:test")
        store.save_state(
            thread["owner"],
            thread["conversation_id"],
            {
                "history": [{"role": role, "content": template}],
                "lead_profile": {"greeted": True},
            },
        )
        agent = make_agent(store)
        response = await agent.turn(
            thread["conversation_id"], "A primeira opção", owner=thread["owner"]
        )
        assert bool(response.media_ids) == expected_media
