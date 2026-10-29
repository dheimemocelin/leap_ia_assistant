import asyncio
import json
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from test_media_library import vehicle

from app.agent.llm import ModelReply, ToolCall
from app.agent.service import SalesAgent
from app.catalog.media_library import VehicleMediaLibrary
from app.catalog.models import VehicleMedia
from app.catalog.repository import JsonCatalogRepository
from app.config import settings
from app.main import app


class FakeLLM:
    def __init__(self, result=None):
        self.calls = []
        self.result = result or ModelReply(
            text="Conheça as características aprovadas.", input_tokens=10, output_tokens=5
        )

    async def complete(self, messages, tools):
        self.calls.append((messages, tools))
        return self.result


@pytest.fixture
def agent(tmp_path):
    vehicles = [vehicle(v) for v in ["b10-bev", "b10-reev", "c10-bev"]]
    records = []
    for v in vehicles:
        path = tmp_path / (v.id + ".jpg")
        path.write_bytes(b"synthetic")
        records.append(
            VehicleMedia(
                id=v.id + "-front",
                vehicle_id=v.id,
                category="exterior",
                subcategory="front_3_4",
                asset_path=str(path),
                storage_uri="test://private",
                rights_basis="synthetic rights",
                provenance="synthetic",
                retrieved_at=datetime.now(UTC),
                approval_status="approved",
                approved_at=datetime.now(UTC),
                approved_by="test",
                usage_rights_status="approved",
            )
        )
    catalog = JsonCatalogRepository(vehicles, records, [])
    return SalesAgent(
        catalog,
        VehicleMediaLibrary(records, vehicles=vehicles, asset_root=tmp_path),
        FakeLLM(),
        timeout=0.05,
    )


@pytest.mark.parametrize("vehicle_id", ["b10-bev", "b10-reev", "c10-bev"])
async def test_photos_sources_and_ids(agent, vehicle_id):
    response = await agent.turn(vehicle_id, "Fotos do " + vehicle_id.replace("-", " "))
    assert response.media_ids == [vehicle_id + "-front"]
    assert response.source_ids
    assert agent.sessions[("local", vehicle_id)]["usage"]["calls"] == 0
    model_input = json.dumps(agent.llm.calls)
    assert "asset_path" not in model_input and "storage_uri" not in model_input
    assert "base64" not in model_input and "get_commercial_offer" not in model_input


async def test_details_and_compact_context(agent):
    result = await agent.turn("one", "Características do C10 BEV")
    assert result.source_ids == [] and result.handoff_required
    assert result.media_ids == []
    photos = await agent.turn("one", "Quero fotos")
    assert photos.media_ids == ["c10-bev-front"]
    assert len(agent.sessions[("local", "one")]["history"]) == 4


async def test_ambiguity_and_followup(agent):
    result = await agent.turn("one", "Fotos B10")
    assert "BEV" in result.text and not agent.llm.calls
    result = await agent.turn("one", "REEV")
    assert result.source_ids
    assert agent.sessions[("local", "one")]["powertrain"] == "REEV"


@pytest.mark.parametrize(
    "text", ["Qual preço do B10 BEV?", "Quero negociar o C10 BEV", "Reserve B10 BEV"]
)
async def test_financial_and_sales_actions_blocked_without_model(agent, text):
    result = await agent.turn("one", text)
    assert result.handoff_required
    assert not agent.llm.calls and not result.media_ids


async def test_isolation_by_conversation_and_owner(agent):
    await agent.turn("one", "Fotos B10 REEV")
    await agent.turn("two", "Fotos C10 BEV")
    assert agent.sessions[("local", "one")]["model"] == "b10"
    assert agent.sessions[("local", "two")]["model"] == "c10"
    await agent.turn("one", "Fotos B10", owner="different")
    assert agent.sessions[("different", "one")]["powertrain"] is None


async def test_tool_failure(agent, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("private internal data")

    monkeypatch.setattr(agent.media, "search", fail)
    result = await agent.turn("one", "Fotos B10 BEV")
    assert result.handoff_required and "private" not in result.text


async def test_timeout(agent):
    class Slow:
        async def complete(self, *args):
            await asyncio.sleep(1)

    agent.llm = Slow()
    result = await agent.turn("one", "Me ajude a escolher")
    assert result.handoff_required
    assert agent.sessions[("local", "one")]["usage"]["calls"] == 1


async def test_model_tool_call_allowlist(agent):
    agent.llm = FakeLLM(ModelReply(tool_calls=[ToolCall(name="create_syonet_lead")]))
    result = await agent.turn("one", "Ajude-me a escolher")
    assert result.handoff_required
    assert len(agent.llm.calls) == 1


async def test_model_tool_call_list_and_call_budget(agent):
    class Planner(FakeLLM):
        async def complete(self, messages, tools):
            self.calls.append((messages, tools))
            return (
                ModelReply(tool_calls=[ToolCall(name="list_vehicles")])
                if tools
                else ModelReply(text="Qual modelo você prefere?")
            )

    agent.llm = Planner()
    await agent.turn("one", "Quais veículos existem?")
    assert len(agent.llm.calls) == 2
    assert len(agent.llm.calls[0][1]) == 3


def test_http_policy_and_session_access(agent, monkeypatch):
    monkeypatch.setattr(settings, "app_api_key", "synthetic-api-key")
    app.state.sales_agent = agent
    headers = {"Authorization": "Bearer synthetic-api-key", "X-Session-Token": "x" * 32}
    try:
        client = TestClient(app)
        assert (
            client.post(
                "/v1/conversations/one/messages", json={"text": "Fotos B10 BEV"}
            ).status_code
            == 401
        )
        response = client.post(
            "/v1/conversations/one/messages", json={"text": "Fotos B10 BEV"}, headers=headers
        )
        assert response.status_code == 200 and response.json()["media_ids"] == ["b10-bev-front"]
    finally:
        del app.state.sales_agent


async def test_model_cannot_invent_financial_or_image_links_in_photo_reply(agent):
    agent.llm = FakeLLM(ModelReply(text="Preço R$ 180.000"))
    result = await agent.turn("one", "Fotos B10 BEV")
    assert result.media_ids == ["b10-bev-front"]
    assert not agent.llm.calls
    assert "180" not in result.text and "http" not in result.text


async def test_ambiguous_photos_never_guess_model(agent):
    result = await agent.turn("one", "Quero fotos")
    assert not result.media_ids and not agent.llm.calls


async def test_pending_real_catalog_is_not_exposed(tmp_path):
    from pathlib import Path

    from app.catalog.loader import load_catalog

    catalog = load_catalog(Path("data/catalog"))
    media = VehicleMediaLibrary.load(catalog, asset_root=Path("assets/media"))
    llm = FakeLLM()
    local = SalesAgent(catalog, media, llm)
    result = await local.turn("one", "Fotos B10 BEV")
    assert not result.media_ids and not llm.calls


async def test_consultative_presentation_uses_only_synthetic_approved_media(agent):
    ambiguous = await agent.turn("consultative", "B10")
    assert not ambiguous.media_ids
    selected = await agent.turn("consultative", "BEV")
    assert selected.media_ids == ["b10-bev-front"]
    repeated = await agent.turn("consultative", "mais fotos")
    assert not repeated.media_ids
    changed = await agent.turn("consultative", "B10 REEV")
    assert changed.media_ids == ["b10-reev-front"]
    assert not agent.llm.calls
