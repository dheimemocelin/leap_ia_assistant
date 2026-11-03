import pytest

from app.api.chat import build_agent
from app.knowledge.runtime import CatalogKnowledge
from scripts.evaluate_lia_quality import QualityModel


class FakeEmbeddings:
    model_id = "synthetic-runtime-test"

    def __init__(self):
        self.calls = 0

    def encode(self, texts, query=False):
        self.calls += 1
        return [[1.0, 0.0] for _ in texts]


@pytest.fixture
def agent(tmp_path):
    a = build_agent(reviewed_catalog=True, test_media=True, orchestration_enabled=True)
    a.llm = QualityModel()
    a.knowledge = CatalogKnowledge(a.grounding, FakeEmbeddings(), tmp_path / "knowledge.sqlite3")
    return a


async def test_whatsapp_agent_graph_uses_knowledge_with_canonical_sources(agent):
    result = await agent.turn("runtime", "Qual a autonomia do C10 BEV?")
    events = agent.sessions[("local", "runtime")]["tool_events"]
    assert events[0]["name"] == "search_knowledge"
    assert result.source_ids and "338" in result.text
    assert not result.handoff_required


async def test_social_name_and_photos_do_not_query_rag(agent):
    await agent.turn("runtime", "Oi")
    assert not agent.sessions[("local", "runtime")]["tool_events"]
    await agent.turn("runtime", "Me chamo Pessoa Sintetica")
    await agent.turn("runtime", "Fotos do B10 BEV")
    assert agent.sessions[("local", "runtime")]["tool_events"][0]["name"] == "search_vehicle_media"
    assert agent.knowledge.embedder.calls == 0


def test_only_live_approved_vehicle_facts_can_be_retrieved(agent):
    facts = agent.knowledge.retrieve("b10-bev", "o que você tem confirmado")
    assert facts
    assert all(f["vehicle_id"] == "b10-bev" for f in facts)
    assert all(agent.knowledge.validate(f, "b10-bev") for f in facts)
    assert not any(agent.knowledge.validate(f, "b10-reev") for f in facts)


def test_unsupported_optional_feature_is_not_inferred_from_related_charging_fact(agent):
    assert agent.knowledge.retrieve("b10-bev", "Tem carregamento programado?") == []


async def test_price_does_not_query_or_leak_financial_values(agent):
    reply = await agent.turn("runtime", "Qual o preço do B10 BEV?")
    assert not agent.sessions[("local", "runtime")]["tool_events"]
    assert agent.knowledge.embedder.calls == 0
    assert "R$" not in reply.text and not reply.handoff_required


def test_source_revocation_invalidates_cached_facts(agent):
    result = agent.knowledge.retrieve("c10-bev", "autonomia")
    assert result
    vehicle = agent.catalog.vehicle("c10-bev")
    vehicle.sources.clear()
    assert not any(agent.knowledge.validate(f, "c10-bev") for f in result)
    assert not agent.knowledge.retrieve("c10-bev", "autonomia")


async def test_knowledge_tool_requires_configured_backend(agent):
    agent.knowledge = None
    response = await agent.turn("runtime", "Qual a autonomia do C10 BEV?")
    assert agent.sessions[("local", "runtime")]["tool_events"][0]["name"] == "get_vehicle_details"
    assert "338" in response.text
