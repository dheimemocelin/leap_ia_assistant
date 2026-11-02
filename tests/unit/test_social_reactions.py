import json

import pytest
from test_sdr_experience import SDRModel

from app.agent.llm import ModelReply
from app.api.chat import build_agent


class SocialWriter(SDRModel):
    def __init__(self, *, draft=None, fail=False):
        super().__init__()
        self.draft, self.fail = draft, fail

    async def complete(self, messages, tools):
        if messages[-1]["content"].startswith("{"):
            context = json.loads(messages[-1]["content"])
            if "reaction" in context:
                self.calls.append(messages)
                assert not tools
                if self.fail:
                    raise TimeoutError("synthetic")
                if self.draft is not None:
                    return ModelReply(
                        text=json.dumps(self.draft), input_tokens=40, output_tokens=20
                    )
                label = " ".join(x for x in context["vehicle"].values() if x)
                kind = context["reaction"]
                ack = {
                    "positive": f"O visual do {label} chamou sua atenção.",
                    "negative": f"Entendi sua impressão sobre o {label}.",
                    "doubt": f"Podemos esclarecer suas dúvidas sobre o {label}.",
                    "more": f"Podemos continuar pelo que mais te interessa no {label}.",
                }[kind]
                key, question = {
                    "positive": ("usage", f"Como você pretende usar o {label} no dia a dia?"),
                    "negative": ("objection", "O que não te agradou no visual?"),
                    "doubt": ("doubt", "Qual ponto você quer esclarecer primeiro?"),
                    "more": ("priority", "O que você quer conhecer melhor nesse modelo?"),
                }[kind]
                return ModelReply(
                    text=json.dumps(
                        {"acknowledgement": ack, "question": {"key": key, "text": question}}
                    ),
                    input_tokens=40,
                    output_tokens=20,
                )
        return await super().complete(messages, tools)


@pytest.fixture
def agent():
    agent = build_agent(reviewed_catalog=True, test_media=True)
    agent.llm = SocialWriter()
    return agent


@pytest.mark.parametrize(
    "text",
    [
        "Que legal",
        "Gostei",
        "Muito bonito",
        "Interessante",
        "Não gostei",
        "Tenho dúvidas",
        "Quero saber mais",
        "Uso para trabalhar",
        "Pensei em usar para Uber",
    ],
)
async def test_non_technical_turn_after_photos_does_not_query_technical_facts(agent, text):
    await agent.turn("social", "Me chamo Pessoa Sintetica")
    await agent.turn("social", "Fotos do B10 BEV")
    result = await agent.turn("social", text)
    session = agent.sessions[("local", "social")]
    assert not session["tool_events"]
    assert "detalhe técnico" not in result.text
    assert not result.media_ids and not result.source_ids and not result.handoff_required
    assert result.text.count("?") <= 1
    assert session["lead_profile"]["vehicle_id"] == "b10-bev"
    assert session["lead_profile"]["display_name"] == "Pessoa Sintetica"
    if text in {"Que legal", "Gostei", "Muito bonito", "Interessante"}:
        assert "O visual do B10 elétrico chamou sua atenção." in result.text
        assert session["usage"] == {"calls": 1, "input_tokens": 40, "output_tokens": 20}


async def test_social_reaction_is_not_mistaken_for_preferred_name(agent):
    await agent.turn("social", "Fotos do B10 BEV")
    await agent.turn("social", "Que legal")
    assert agent.sessions[("local", "social")]["lead_profile"]["display_name"] is None


@pytest.mark.parametrize(
    "ack",
    ["Podemos explorar o que chamou sua atenção no B10 BEV.", "Entendi seu interesse no B10 BEV."],
)
async def test_model_writes_different_natural_responses_without_fixed_variant_ids(agent, ack):
    await agent.turn("social", "Fotos do B10 BEV")
    agent.llm = SocialWriter(draft={"acknowledgement": ack, "question": None})
    response = await agent.turn("social", "Gostei")
    assert response.text == ack.replace("B10 BEV", "B10 elétrico")
    assert "?" not in response.text


async def test_no_repeated_question_or_facts_and_context_contains_only_reviewed_history(agent):
    await agent.turn("social", "Me chamo Pessoa Sintetica")
    photos = await agent.turn("social", "Fotos do B10 BEV")
    first = await agent.turn("social", "Que legal")
    second = await agent.turn("social", "Gostei")
    assert first.text.count("?") == 1 and "?" not in second.text
    assert not set(photos.media_ids) & set(second.media_ids)
    context = json.loads(agent.llm.calls[-1][-1]["content"])
    assert context["vehicle"] == {"model": "B10", "powertrain": "BEV"}
    assert context["reviewed_facts_already_presented"]
    assert "Pessoa Sintetica" not in json.dumps(agent.llm.calls)
    assert "asset_path" not in json.dumps(context) and "base64" not in json.dumps(context)
    assert "218" not in second.text and "405" not in second.text


@pytest.mark.parametrize(
    "ack",
    [
        "Autonomia de 999 km.",
        "Preço R$ 100.",
        "É aprovado para Uber e garante economia.",
        "Vamos falar com um consultor.",
        "O visual do C10 REEV chamou sua atenção.",
    ],
)
async def test_unsafe_invented_or_cross_vehicle_social_output_is_rejected(agent, ack):
    await agent.turn("social", "Fotos do B10 BEV")
    agent.llm = SocialWriter(draft={"acknowledgement": ack, "question": None})
    response = await agent.turn("social", "Que legal")
    assert response.text != ack and "999" not in response.text and "100" not in response.text
    assert "consultor" not in response.text and not response.handoff_required
    assert not agent.sessions[("local", "social")]["tool_events"]


async def test_social_timeout_preserves_conversation_without_technical_fallback(agent):
    await agent.turn("social", "Fotos do B10 BEV")
    agent.llm = SocialWriter(fail=True)
    response = await agent.turn("social", "Que legal")
    assert "detalhe técnico" not in response.text and not response.handoff_required
    assert agent.sessions[("local", "social")]["usage"]["calls"] == 1


async def test_mixed_reaction_and_technical_or_financial_question_still_obeys_original_paths(agent):
    await agent.turn("social", "Fotos do C10 BEV")
    technical = await agent.turn("social", "Gostei, qual a autonomia?")
    assert "338" in technical.text and technical.source_ids
    assert agent.sessions[("local", "social")]["tool_events"][0]["name"] == "get_vehicle_details"
    financial = await agent.turn("social", "Que legal, qual o preço?")
    assert not financial.source_ids and not financial.handoff_required
    assert agent.sessions[("local", "social")]["usage"]["calls"] == 0


async def test_explicit_human_request_and_consent_are_not_social_reactions(agent):
    await agent.turn("social", "Fotos do B10 BEV")
    response = await agent.turn("social", "Gostei, quero falar com um vendedor")
    assert response.handoff_required and "autoriza" in response.text
    assert agent.sessions[("local", "social")]["lead_profile"]["consent"] == "offered"


async def test_reaction_does_not_replace_pending_distance_or_contact_name(agent):
    await agent.turn("social", "Fotos do B10 BEV")
    await agent.turn("social", "Pensei em usar para Uber")
    await agent.turn("social", "Que legal")
    await agent.turn("social", "Uns 200 km")
    assert agent.sessions[("local", "social")]["lead_profile"]["daily_distance_km"] == 200
    await agent.turn("social", "Quero falar com um vendedor")
    await agent.turn("social", "sim")
    await agent.turn("social", "Gostei")
    profile = agent.sessions[("local", "social")]["lead_profile"]
    assert profile["consent"] == "granted"
    assert profile["contact_name"] is None and profile["pending_question"] == "name"
