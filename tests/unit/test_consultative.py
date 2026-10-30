"""Offline multi-turn acceptance tests; all contact details below are synthetic."""

import json

import pytest

from app.agent.consultative import LeadProfile
from app.agent.llm import ModelReply
from app.api.chat import build_agent
from app.policy.commercial import CommercialPolicyEngine


class ReviewedOnly:
    def __init__(self):
        self.messages = []

    async def complete(self, messages, tools):
        self.messages.append(messages)
        assert not tools
        if "variants" in messages[-1]["content"]:
            return ModelReply(text='{"variant":1}')
        evidence = json.loads(messages[-1]["content"].split(": ", 1)[1])
        return ModelReply(text=json.dumps({"fact_ids": [f["id"] for f in evidence["facts"]]}))


@pytest.fixture
def agent():
    agent = build_agent(reviewed_catalog=True, test_media=True)
    agent.llm = ReviewedOnly()
    return agent


def profile(agent, conversation="journey", owner="local"):
    return LeadProfile.model_validate(agent.sessions[(owner, conversation)]["lead_profile"])


async def test_customer_journey_visual_context_decline_and_price(agent):
    greeting = await agent.turn("journey", "Olá")
    assert greeting.text.count("?") <= 1
    ambiguous = await agent.turn("journey", "Tenho interesse no B10")
    assert "BEV" in ambiguous.text and "REEV" in ambiguous.text
    assert not ambiguous.media_ids
    selected = await agent.turn("journey", "BEV")
    assert len(selected.media_ids) == 3
    assert all("b10-bev" in x for x in selected.media_ids)
    urban = await agent.turn("journey", "Uso na cidade")
    assert "dia a dia?" not in urban.text
    family = await agent.turn("journey", "Tenho dois filhos e preciso de espaço")
    assert "405" in family.text and family.source_ids
    assert "espaco" in profile(agent).needs and profile(agent).usage == "urbano"
    objection = await agent.turn("journey", "Tenho receio de carro elétrico")
    assert "recarga ou autonomia" in objection.text
    visit = await agent.turn("journey", "Quero conhecer o carro presencialmente")
    assert "autoriza" in visit.text and profile(agent).temperature == "quente"
    refused = await agent.turn("journey", "Não quero contato")
    assert profile(agent).consent == "declined"
    price = await agent.turn("journey", "Qual o preço?")
    assert "autoriza" not in price.text and price.handoff_required
    assert not profile(agent).handoff_summary
    switched = await agent.turn("journey", "Agora quero ver o C10 BEV")
    assert switched.media_ids and all("c10-bev" in x for x in switched.media_ids)
    assert profile(agent).vehicle_id != "b10-bev"
    for result in [
        greeting,
        ambiguous,
        selected,
        urban,
        family,
        objection,
        visit,
        refused,
        price,
        switched,
    ]:
        assert result.text.count("?") <= 1
        assert CommercialPolicyEngine().validate_output(result.text)


async def test_consent_contact_summary_and_private_history(agent):
    await agent.turn("journey", "B10 BEV")
    await agent.turn("journey", "Quero visitar")
    await agent.turn("journey", "sim")
    assert profile(agent).consent == "granted"
    await agent.turn("journey", "Pessoa Sintetica")
    prepared = await agent.turn("journey", "11000000000")
    summary = profile(agent).handoff_summary
    assert summary["status"] == "prepared_not_sent"
    assert summary["contact"]["phone"] == "11000000000"
    assert summary["consent"]["at"] and summary["vehicle_id"]
    assert "não foram enviados" in prepared.text
    assert "Pessoa Sintetica" not in json.dumps(agent.sessions[("local", "journey")]["history"])
    await agent.turn("journey", "Qual a potência do B10 BEV?")
    assert "11000000000" not in json.dumps(agent.llm.messages)
    assert "Pessoa Sintetica" not in json.dumps(agent.llm.messages)
    await agent.turn("journey", "Não autorizo")
    assert profile(agent).handoff_summary is None
    assert profile(agent).contact_phone is None


async def test_no_auto_consent_or_cross_session_state(agent):
    await agent.turn("journey", "B10 REEV")
    await agent.turn("journey", "sim")
    assert profile(agent).consent == "not_requested"
    await agent.turn("journey", "Oi", owner="other")
    assert profile(agent, owner="other").vehicle_id is None
    assert not profile(agent, owner="other").needs


async def test_known_brand_and_insufficient_catalog(agent):
    known = await agent.turn("journey", "Já conheço a marca")
    assert "direto" in known.text and profile(agent).knows_brand
    await agent.turn("journey", "B10 REEV")
    family = await agent.turn("journey", "Preciso de espaço para minha família")
    assert not family.source_ids and "evidência aprovada" in family.text
    missing = await agent.turn("journey", "Qual a capacidade da bateria?")
    assert missing.handoff_required and not missing.source_ids


async def test_no_repeated_default_photos_and_fresh_model(agent):
    first = await agent.turn("journey", "B10 BEV")
    second = await agent.turn("journey", "Mais fotos")
    assert not set(first.media_ids) & set(second.media_ids)
    third = await agent.turn("journey", "Mais fotos")
    assert not third.media_ids
    changed = await agent.turn("journey", "C10 BEV")
    assert changed.media_ids and all("c10-bev" in x for x in changed.media_ids)


async def test_pending_media_are_not_approved_by_conversation(agent):
    from pathlib import Path

    from app.catalog.loader import load_catalog
    from app.catalog.media_library import VehicleMediaLibrary

    catalog = load_catalog(Path("data/catalog"))
    agent.media = VehicleMediaLibrary.load(catalog, asset_root=Path("assets/media"))
    result = await agent.turn("journey", "B10 BEV")
    assert not result.media_ids
    assert "fotos aprovadas" in result.text


async def test_repeated_use_does_not_repeat_question(agent):
    await agent.turn("journey", "B10 BEV")
    first = await agent.turn("journey", "Uso urbano")
    again = await agent.turn("journey", "Uso na cidade")
    assert first.text != again.text
    assert "Como você pretende usar" not in again.text


async def test_selection_interrupts_contact_collection_and_invalidates_consent(agent):
    await agent.turn("journey", "B10 BEV")
    await agent.turn("journey", "Quero visitar")
    await agent.turn("journey", "sim")
    changed = await agent.turn("journey", "REEV")
    assert changed.media_ids and all("b10-reev" in m for m in changed.media_ids)
    assert profile(agent).consent == "not_requested"
    assert profile(agent).contact_name is None
    assert profile(agent).handoff_summary is None


async def test_technical_question_with_usage_does_not_get_intercepted(agent):
    result = await agent.turn("journey", "Qual a autonomia do C10 BEV na cidade?")
    assert "338" in result.text and result.source_ids
    assert profile(agent).usage == "urbano"


async def test_repeated_greeting_does_not_repeat_showroom_script(agent):
    first = await agent.turn("journey", "Oi")
    second = await agent.turn("journey", "Oi")
    assert first.text != second.text
    assert "?" not in second.text


async def test_c10_without_powertrain_uses_only_approved_canonical_variant(agent):
    response = await agent.turn("journey", "Quero conhecer o C10")
    assert response.media_ids and all("c10-bev" in x for x in response.media_ids)
    assert profile(agent).powertrain == "BEV"


async def test_no_new_contact_data_without_explicit_consent(agent):
    response = await agent.turn("journey", "Meu telefone é 11000000000")
    assert "autoriza" in response.text
    assert profile(agent).consent == "offered"
    assert profile(agent).contact_phone is None
    assert "11000000000" not in json.dumps(agent.sessions[("local", "journey")]["history"])


async def test_objection_replaces_previous_visit_question(agent):
    await agent.turn("journey", "B10 BEV")
    await agent.turn("journey", "Uso na cidade")
    await agent.turn("journey", "Preciso de espaço para família")
    assert profile(agent).pending_question == "family_priority"
    await agent.turn("journey", "Tenho receio de carro elétrico")
    assert profile(agent).pending_question == "electric_concern"
    await agent.turn("journey", "sim")
    assert profile(agent).consent == "not_requested"
    assert profile(agent).visit_interest is None


async def test_preferred_name_optional_private_and_asked_once(agent):
    greeting = await agent.turn("journey", "Oi")
    assert "prefere ser chamado" in greeting.text
    answer = await agent.turn("journey", "Pessoa Sintetica")
    assert "Pessoa Sintetica" in answer.text
    assert profile(agent).display_name == "Pessoa Sintetica"
    assert profile(agent).consent == "not_requested"
    assert profile(agent).contact_name is None
    await agent.turn("journey", "B10 BEV")
    again = await agent.turn("journey", "Oi")
    assert "prefere ser chamado" not in again.text
    assert "Pessoa Sintetica" not in json.dumps(agent.sessions[("local", "journey")]["history"])
    await agent.turn("journey", "Quero visitar")
    consented = await agent.turn("journey", "sim")
    assert "telefone" in consented.text
    assert profile(agent).contact_name == "Pessoa Sintetica"


async def test_name_can_be_skipped_without_blocking_vehicle_request(agent):
    await agent.turn("journey", "Oi")
    result = await agent.turn("journey", "B10 BEV")
    assert result.media_ids
    assert profile(agent).display_name is None
    assert profile(agent).name_prompted
