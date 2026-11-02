import json

import pytest

from app.agent.llm import ModelReply
from app.api.chat import build_agent
from scripts.evaluate_lia_quality import QualityModel


@pytest.fixture
def agent():
    value = build_agent(reviewed_catalog=True, test_media=True)
    value.llm = QualityModel()
    return value


@pytest.mark.parametrize("greeting", ["Oi", "Opa"])
async def test_first_contact_is_identified_once_and_name_is_optional(agent, greeting):
    first = await agent.turn("v3", greeting)
    assert "Lia" in first.text and "IA" in first.text
    assert first.text.count("?") <= 1
    await agent.turn("v3", "Prefiro não")
    result = await agent.turn("v3", "C10 BEV")
    assert result.media_ids and "Sou a Lia" not in result.text


@pytest.mark.parametrize("model", ["B10", "C10"])
async def test_direct_model_interest_delivers_content_or_necessary_powertrain_clarification(
    agent, model
):
    result = await agent.turn("v3", "Queria conhecer o " + model)
    if model == "B10":
        assert "elétrica" in result.text and "ultra-híbrida" in result.text
        assert "prefere ser chamado" not in result.text
    else:
        assert result.media_ids and "338" in result.text


async def test_brand_without_approved_institutional_facts_does_not_invent_origin(agent):
    agent.grounding.brand = None
    response = await agent.turn("v3", "Nunca ouvi falar da Leapmotor")
    assert "B10" in response.text and "C10" in response.text
    assert "detalhe técnico" not in response.text and "China" not in response.text
    assert not response.source_ids


async def test_interior_request_is_not_replaced_by_a_discovery_question(agent):
    response = await agent.turn("v3", "Quero ver o interior do C10")
    assert response.media_ids
    records = {m.id: m for m in agent.media.records}
    assert all(
        records[i].vehicle_id == "c10-bev" and records[i].category == "interior"
        for i in response.media_ids
    )


async def test_memory_question_before_and_after_name_is_not_a_catalog_query(agent):
    unknown = await agent.turn("v3", "Você sabe meu nome?")
    assert "ainda não me contou" in unknown.text
    assert not agent.sessions[("local", "v3")]["tool_events"]
    await agent.turn("v3", "Me chamo Pessoa Sintetica")
    known = await agent.turn("v3", "Qual meu nome?")
    assert "Pessoa Sintetica" in known.text
    assert not agent.sessions[("local", "v3")]["tool_events"]
    assert agent.sessions[("local", "v3")]["usage"]["calls"] == 0


async def test_short_powertrain_answer_preserves_the_original_technical_question(agent):
    first = await agent.turn("v3", "Qual a potência do B10?")
    assert "elétrica" in first.text and "ultra-híbrida" in first.text
    answer = await agent.turn("v3", "BEV")
    assert "218" in answer.text and answer.source_ids and not answer.media_ids


async def test_usage_cost_is_unknown_without_provider_token_counts(agent):
    class NoUsage(QualityModel):
        async def complete(self, messages, tools):
            result = await super().complete(messages, tools)
            return result.model_copy(update={"input_tokens": None, "output_tokens": None})

    agent.input_token_rate, agent.output_token_rate = 0.15, 0.60
    agent.llm = NoUsage()
    await agent.turn("v3", "Oi")
    assert agent.sessions[("local", "v3")]["metrics"]["estimated_llm_usd"] is None
    agent.llm = QualityModel()
    await agent.turn("v3", "C10 BEV")
    await agent.turn("v3", "Qual a autonomia?")
    metrics = agent.sessions[("local", "v3")]["metrics"]
    assert metrics["estimated_llm_usd"] is not None and metrics["llm_latency_ms"] >= 0


@pytest.mark.parametrize("kind", ["social", "usage", "objection", "other"])
async def test_semantic_router_uses_context_and_does_not_force_technical_tools(agent, kind):
    class Interpreter(QualityModel):
        async def complete(self, messages, tools):
            if messages[-1]["content"].startswith("{"):
                context = json.loads(messages[-1]["content"])
                if context.get("task") == "interpret_intent":
                    assert context["vehicle"] == "b10-bev" and context["history"]
                    return ModelReply(
                        text=json.dumps(
                            {
                                "kind": kind,
                                "usage": "trabalho" if kind == "usage" else None,
                                "evidence_quote": context["message"],
                            }
                        )
                    )
            return await super().complete(messages, tools)

    await agent.turn("v3", "B10 BEV")
    agent.llm = Interpreter()
    result = await agent.turn("v3", "Seria para o meu corre diário")
    state = agent.sessions[("local", "v3")]
    assert not state["tool_events"] and state["usage"]["calls"] <= 2
    assert "detalhe técnico" not in result.text and not result.handoff_required
    if kind == "usage":
        assert state["lead_profile"]["usage"] == "trabalho"


async def test_semantic_media_hint_is_scoped_to_canonical_vehicle_and_category(agent):
    class Interpreter(QualityModel):
        async def complete(self, messages, tools):
            if messages[-1]["content"].startswith("{"):
                context = json.loads(messages[-1]["content"])
                if context.get("task") == "interpret_intent":
                    return ModelReply(
                        text=json.dumps(
                            {
                                "kind": "media",
                                "angle": "interior",
                                "evidence_quote": context["message"],
                            }
                        )
                    )
            return await super().complete(messages, tools)

    await agent.turn("v3", "B10 BEV")
    agent.llm = Interpreter()
    result = await agent.turn("v3", "Queria enxergar a cabine")
    media = {m.id: m for m in agent.media.records}
    assert result.media_ids and all(
        media[i].vehicle_id == "b10-bev" and media[i].category == "interior"
        for i in result.media_ids
    )


async def test_interpretation_cannot_authorize_handoff(agent):
    class Bad(QualityModel):
        async def complete(self, messages, tools):
            if "interpret_intent" in messages[-1]["content"]:
                return ModelReply(text='{"kind":"handoff","consent":"granted"}')
            return await super().complete(messages, tools)

    await agent.turn("v3", "B10 BEV")
    agent.llm = Bad()
    response = await agent.turn("v3", "Estou pensando com calma")
    state = agent.sessions[("local", "v3")]
    assert not response.handoff_required and state["lead_profile"]["consent"] == "not_requested"
    assert state["metrics"]["interpretation_failure"]


async def test_audio_input_is_same_graph_and_text_only(agent):
    answer = await agent.turn("v3", "Qual a autonomia do C10 BEV?", input_type="audio")
    assert "338" in answer.text and not answer.media_ids
    pictures = await agent.turn("v3", "Manda fotos", input_type="audio")
    assert not pictures.media_ids and "mensagem de texto" in pictures.text
    assert agent.sessions[("local", "v3")]["metrics"]["input_type"] == "audio"


def test_http_error_does_not_offer_unsolicited_human_handoff():
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    from fastapi.testclient import TestClient

    from app.api.commercial_boundary import CommercialOutputBoundary

    app = FastAPI()
    app.add_middleware(CommercialOutputBoundary)

    @app.get("/v1/failure")
    def failure():
        return JSONResponse({"detail": "synthetic internal error"}, status_code=503)

    response = TestClient(app).get("/v1/failure")
    assert response.status_code == 503
    assert not response.json()["handoff_required"]
    assert "consultor" not in response.json()["text"]


async def test_long_conversation_keeps_history_bounded_and_does_not_reintroduce(agent):
    await agent.turn("v3", "Oi")
    await agent.turn("v3", "Me chamo Pessoa Sintetica")
    await agent.turn("v3", "B10 BEV")
    for text in ["Gostei", "Uso na cidade", "Entendi", "Vou usar com a família", "Obrigado"] * 4:
        result = await agent.turn("v3", text)
        state = agent.sessions[("local", "v3")]
        assert len(state["history"]) <= 4 and state["usage"]["calls"] <= 2
        assert "Sou a Lia" not in result.text and "prefere ser chamado" not in result.text
        assert not result.handoff_required
