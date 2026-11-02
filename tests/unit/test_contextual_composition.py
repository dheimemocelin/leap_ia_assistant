import json
from pathlib import Path

import pytest

from app.agent.llm import ModelReply
from app.api.chat import build_agent
from app.policy.commercial import CommercialPolicyEngine
from scripts.evaluate_lia_quality import QualityModel


class Writer(QualityModel):
    def __init__(self, text):
        self.text = text

    async def complete(self, messages, tools):
        if not tools and messages[-1]["content"].startswith("{"):
            context = json.loads(messages[-1]["content"])
            if context.get("task") == "compose_conversation" or "reaction" in context:
                return ModelReply(text=json.dumps({"text": self.text, "question": None}))
        return await super().complete(messages, tools)


@pytest.fixture
def agent():
    value = build_agent(reviewed_catalog=True, test_media=True)
    value.llm = QualityModel()
    return value


async def test_free_social_wording_without_closed_vocabulary(agent):
    await agent.turn("quality", "Fotos do B10 BEV")
    wording = "Bacana perceber sua reação. Podemos explorar a escolha com tranquilidade, respeitando suas prioridades."
    agent.llm = Writer(wording)
    response = await agent.turn("quality", "Gostei")
    assert response.text == wording
    state = agent.sessions[("local", "quality")]
    assert state["composition"]["origin"] == "llm"
    assert not state["tool_events"]


async def test_acknowledgement_after_charging_uses_writer_not_technical_fallback(agent):
    await agent.turn("quality", "B10 REEV")
    await agent.turn("quality", "Vou usar em viagens")
    await agent.turn("quality", "Uns 500 km")
    response = await agent.turn("quality", "Em casa")
    assert "mencionou recarga em casa" in response.text
    assert "precisam ser verificados" not in response.text
    assert agent.sessions[("local", "quality")]["composition"]["origin"] == "llm"


@pytest.mark.parametrize(
    "text",
    [
        "Gostei bastante",
        "Achei muito bonito",
        "Ok",
        "Obrigado",
        "Amei",
        "Nossa, muito legal",
        "Curti",
        "Não curti",
    ],
)
async def test_paraphrases_and_short_turns_do_not_query_technical_tools(agent, text):
    await agent.turn("quality", "Fotos do B10 BEV")
    await agent.turn("quality", text)
    state = agent.sessions[("local", "quality")]
    assert not state["tool_events"]
    assert state["composition"]["origin"] == "llm"


@pytest.mark.parametrize(
    "unsafe",
    [
        "Preço R$ 100.",
        "Sai por vinte mil.",
        "São doze parcelas.",
        "É aprovado para Uber.",
        "Aceita Uber sem problemas.",
        "O carro é econômico.",
        "Roda bastante sem carregar.",
        "O B10 BEV tem bancos aquecidos.",
        "Interior amplo e teto panorâmico.",
        "Podemos explorar o BYD Dolphin.",
        "Podemos explorar o tesla.",
        "O C10 BEV chamou sua atenção.",
        "O B10 REEV chamou sua atenção.",
        "Veja https://example.invalid.",
        "Seu telefone é 11000000000.",
        "Sou a Lia, assistente virtual.",
        "Vamos falar com um consultor.",
        "Autonomia de 999 km.",
        "src-forged",
        "assets/media/private.jpeg",
    ],
)
async def test_unsafe_free_prose_fails_closed_with_reason(agent, unsafe):
    await agent.turn("quality", "Fotos do B10 BEV")
    agent.llm = Writer(unsafe)
    response = await agent.turn("quality", "Gostei")
    assert response.text != unsafe
    assert not response.source_ids and not response.handoff_required
    telemetry = agent.sessions[("local", "quality")]["composition"]
    assert telemetry["origin"] == "fallback" and telemetry["fallback_reason"]
    assert CommercialPolicyEngine().validate_output(response.text)


async def test_technical_prose_and_evidence_are_separate_and_revocable(agent):
    class FactWriter(QualityModel):
        async def complete(self, messages, tools):
            context = json.loads(messages[-1]["content"])
            if context.get("intent") == "technical":
                return ModelReply(
                    text=json.dumps(
                        {
                            "text": "Vamos olhar esse ponto a partir da informação verificada.",
                            "fact_ids": [context["facts"][0]["id"]],
                        }
                    )
                )
            return await super().complete(messages, tools)

    agent.llm = FactWriter()
    result = await agent.turn("quality", "Qual a autonomia do C10 BEV?")
    assert "informação verificada" in result.text and "338" in result.text
    assert result.source_ids == [agent.grounding.facts["c10-bev-range-pbev"].source_id]
    assert agent.sessions[("local", "quality")]["composition"]["origin"] == "llm"


async def test_model_cannot_change_question_plan_or_supply_media_ids(agent):
    class Attack(QualityModel):
        async def complete(self, messages, tools):
            return ModelReply(
                text=json.dumps(
                    {
                        "text": "Entendi sua impressão.",
                        "media_ids": ["other-model"],
                        "question": {"key": "phone", "text": "Qual seu telefone?"},
                    }
                )
            )

    await agent.turn("quality", "B10 BEV")
    agent.llm = Attack()
    response = await agent.turn("quality", "Gostei")
    assert not response.media_ids and not response.handoff_required
    assert agent.sessions[("local", "quality")]["lead_profile"]["consent"] == "not_requested"


async def test_fact_revoked_during_provider_call_is_not_rendered(agent):
    class Revoke(QualityModel):
        async def complete(self, messages, tools):
            context = json.loads(messages[-1]["content"])
            agent.catalog.vehicle("c10-bev").approval_status = "pending_review"
            return ModelReply(
                text=json.dumps(
                    {"text": "Vamos olhar esse ponto.", "fact_ids": [context["facts"][0]["id"]]}
                )
            )

    agent.llm = Revoke()
    result = await agent.turn("quality", "Qual a autonomia do C10 BEV?")
    assert not result.source_ids and "338" not in result.text


async def test_timeout_is_recorded_without_raw_exception(agent):
    class Timeout(QualityModel):
        async def complete(self, messages, tools):
            raise TimeoutError("sensitive fake provider body")

    await agent.turn("quality", "B10 BEV")
    agent.llm = Timeout()
    response = await agent.turn("quality", "Gostei")
    telemetry = agent.sessions[("local", "quality")]["composition"]
    assert telemetry["fallback_reason"] == "provider_timeout"
    assert "sensitive" not in response.text + json.dumps(telemetry)


async def test_persistent_return_recovers_context_without_reintroducing_or_asking_name(tmp_path):
    from app.pilot_store import PilotStore

    store = PilotStore(str(tmp_path / "synthetic.sqlite3"))
    thread = store.open_thread("synthetic-person", "whatsapp:synthetic-instance")
    first = build_agent(reviewed_catalog=True, test_media=True)
    first.llm, first.memory_store = QualityModel(), store
    for message in ["Oi", "Me chamo Pessoa Sintetica", "B10 BEV", "Uso na cidade"]:
        await first.turn(thread["conversation_id"], message, owner=thread["owner"])
    returned = build_agent(reviewed_catalog=True, test_media=True)
    returned.llm, returned.memory_store = QualityModel(), store
    response = await returned.turn(thread["conversation_id"], "Gostei", owner=thread["owner"])
    state = returned.sessions[(thread["owner"], thread["conversation_id"])]
    assert state["lead_profile"]["display_name"] == "Pessoa Sintetica"
    assert state["lead_profile"]["vehicle_id"] == "b10-bev"
    assert "Sou a Lia" not in response.text and "prefere ser chamado" not in response.text
    assert not response.media_ids and state["composition"]["origin"] == "llm"


@pytest.mark.parametrize(
    "payload",
    [
        {"text": "Vamos olhar esse ponto.", "fact_ids": ["invented-fact"]},
        {"text": "Podemos continuar.", "source_ids": ["src-invented"]},
        {"text": "Qual sua prioridade? Qual sua rotina?"},
        {"text": "Entendi.", "question": {"key": "photos", "text": "Quer ver fotos?"}},
        {"text": "Você mencionou recarga em casa."},
    ],
)
async def test_structural_evidence_and_question_constraints(agent, payload):
    class InvalidDraft(QualityModel):
        async def complete(self, messages, tools):
            return ModelReply(text=json.dumps(payload))

    await agent.turn("quality", "B10 BEV")
    agent.llm = InvalidDraft()
    response = await agent.turn("quality", "Gostei")
    assert not response.source_ids and not response.media_ids and not response.handoff_required
    assert agent.sessions[("local", "quality")]["composition"]["origin"] == "fallback"


async def test_injection_cannot_invoke_tool_from_composition(agent):
    from app.agent.llm import ToolCall

    class ToolAttack(QualityModel):
        async def complete(self, messages, tools):
            assert not tools
            return ModelReply(tool_calls=[ToolCall(name="create_syonet_lead")])

    await agent.turn("quality", "B10 BEV")
    agent.llm = ToolAttack()
    response = await agent.turn("quality", "Gostei")
    state = agent.sessions[("local", "quality")]
    assert not response.handoff_required and not state["tool_events"]
    assert state["composition"]["fallback_reason"] == "unexpected_tool_call"


SCENARIOS = json.loads(Path("tests/fixtures/conversations/lia-quality.json").read_text())


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s["id"])
async def test_complete_conversation_scenarios(agent, scenario):
    assert len(SCENARIOS) >= 20
    seen_media = set()
    approved_sources = {f.source_id for f in agent.grounding.facts.values()}
    approved_sources.update("src-media-" + m.sha256[:20] for m in agent.media.records if m.sha256)
    for item in scenario["messages"]:
        kind = item.get("type", "text") if isinstance(item, dict) else "text"
        message = item["transcript"] if isinstance(item, dict) else item
        response = await agent.turn("quality", message, input_type=kind)
        state = agent.sessions[("local", "quality")]
        assert CommercialPolicyEngine().validate_output(response.text)
        assert response.text.count("?") <= 1
        assert state["usage"]["calls"] <= 2
        assert set(response.source_ids) <= approved_sources
        # Explicit angle requests may intentionally revisit a previously shown image.
        explicit_angle = any(word in message.lower() for word in ["interior", "exterior", "painel", "bancos", "teto", "frente", "traseira", "lateral"])
        if not explicit_angle:
            assert not seen_media.intersection(response.media_ids)
        else:
            records = {m.id: m for m in agent.media.records}
            assert all(records[i].vehicle_id == state["lead_profile"]["vehicle_id"] for i in response.media_ids)
        seen_media.update(response.media_ids)
        assert state["composition"]["origin"] in {
            "llm",
            "fallback",
            "deterministic",
            "evidence_selection",
        }
        if response.handoff_required:
            assert "human_contact_requested" in state["lead_profile"]["signals"]
            assert state["lead_profile"]["consent"] in {"offered", "granted"}
        from app.agent.social import social_intent

        if social_intent(message):
            assert not state["tool_events"]
