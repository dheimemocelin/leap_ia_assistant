import json
from pathlib import Path

import pytest

from app.agent.grounding import GroundingPolicy, ReviewedFact
from app.agent.llm import ModelReply, ToolCall
from app.agent.service import SalesAgent
from app.catalog.loader import load_catalog
from app.catalog.media_library import VehicleMediaLibrary

ROOT = Path("data/validation/grounding")


@pytest.fixture
def grounded():
    catalog = load_catalog(ROOT)
    facts = [ReviewedFact.model_validate(f) for f in json.loads((ROOT / "facts.json").read_text())]
    policy = GroundingPolicy(facts, catalog)

    class Fake:
        calls = 0

        async def complete(self, messages, tools):
            self.calls += 1
            if tools:
                return ModelReply(
                    tool_calls=[
                        ToolCall(name="get_vehicle_details", arguments={"vehicle_id": "c10-bev"})
                    ]
                )
            return ModelReply(text='{"fact_ids":["c10-bev-range-pbev"]}')

    agent = SalesAgent(
        catalog,
        VehicleMediaLibrary([], vehicles=catalog.vehicles(), asset_root=Path("assets/media")),
        Fake(),
        grounding=policy,
        prefer_tool_calling=True,
    )
    return agent


async def test_real_tool_dispatch_and_exact_grounded_response(grounded):
    result = await grounded.turn("one", "Qual a autonomia do C10 BEV?")
    fact = next(iter(grounded.grounding.facts.values()))
    assert result.text == fact.statement
    assert result.source_ids == [fact.source_id]
    events = grounded.sessions[("local", "one")]["tool_events"]
    assert events[0]["selection_origin"] == "llm"
    assert events[0]["name"] == "get_vehicle_details"
    assert events[0]["result"]["specifications"] == {"range_km": 338}
    assert grounded.llm.calls == 2


async def test_insufficient_evidence_never_asks_model_to_invent(grounded):
    result = await grounded.turn("one", "Qual a capacidade da bateria do C10 BEV?")
    assert result.handoff_required and not result.source_ids
    assert grounded.llm.calls == 1


async def test_unknown_fact_and_extra_claim_are_rejected(grounded):
    class Bad:
        async def complete(self, messages, tools):
            return ModelReply(text='{"fact_ids":["c10-bev-range-pbev"],"claim":"999 km"}')

    grounded.prefer_tool_calling = False
    grounded.llm = Bad()
    result = await grounded.turn("one", "Qual a autonomia do C10 BEV?")
    assert result.handoff_required and "999" not in result.text and not result.source_ids


async def test_nested_financial_data_cannot_become_fact_or_tool_context(grounded):
    vehicle = grounded.catalog.vehicle("c10-bev")
    vehicle.specifications.update(
        {"price": 180000, "motors": [{"power_kw": 160, "discount": 1000}]}
    )
    await grounded.turn("one", "Qual a autonomia do C10 BEV?")
    result = grounded.sessions[("local", "one")]["tool_events"][0]["result"]
    assert "price" not in str(result) and "discount" not in str(result)
    assert result["specifications"]["motors"] == [{"power_kw": 160}]


def test_fact_value_and_source_binding_rejected(grounded):
    fact = next(iter(grounded.grounding.facts.values()))
    with pytest.raises(ValueError, match="value"):
        GroundingPolicy(
            [ReviewedFact.model_validate(fact.model_dump() | {"value": 999})], grounded.catalog
        )
    with pytest.raises(ValueError, match="source"):
        GroundingPolicy(
            [ReviewedFact.model_validate(fact.model_dump() | {"source_id": "fake"})],
            grounded.catalog,
        )


@pytest.mark.parametrize("change", ["value", "approval", "source"])
async def test_changed_or_revoked_fact_abstains(grounded, change):
    vehicle = grounded.catalog.vehicle("c10-bev")
    if change == "value":
        vehicle.specifications["range_km"] = 999
    elif change == "approval":
        vehicle.approval_status = "pending_review"
    else:
        vehicle.sources = []
    response = await grounded.turn("changed", "Qual a autonomia do C10 BEV?")
    assert response.handoff_required and not response.source_ids
    assert grounded.llm.calls == (0 if change == "approval" else 1)


async def test_model_cannot_switch_requested_canonical_vehicle(grounded):
    class Wrong:
        async def complete(self, messages, tools):
            return ModelReply(
                tool_calls=[
                    ToolCall(name="get_vehicle_details", arguments={"vehicle_id": "b10-bev"})
                ]
            )

    grounded.llm = Wrong()
    result = await grounded.turn("wrong", "Qual a autonomia do C10 BEV?")
    assert result.handoff_required and not result.source_ids


def test_unoffered_and_financial_facts_rejected(grounded):
    fact = next(iter(grounded.grounding.facts.values()))
    with pytest.raises(ValueError, match="Unknown"):
        grounded.grounding.render('{"fact_ids":["made-up"]}', [fact.model_dump()])
    with pytest.raises(ValueError, match="technical"):
        GroundingPolicy(
            [ReviewedFact.model_validate(fact.model_dump() | {"specification": "price"})],
            grounded.catalog,
        )
