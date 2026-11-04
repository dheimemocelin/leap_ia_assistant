"""Regressions from pilot screenshots; synthetic data and simulated LLM only."""

import json

import pytest

from app.agent.llm import ModelReply
from tests.unit.test_lia_v2 import make_agent
from tests.unit.test_sales_delivery import SalesModel


class MisreadingRouter(SalesModel):
    async def complete(self, messages, tools):
        if not tools and "route_conversation" in messages[-1]["content"]:
            return ModelReply(text=json.dumps({"act": "fact_question"}))
        return await super().complete(messages, tools)


async def test_contextual_fear_is_not_a_technical_request_even_when_router_would_misread():
    a = make_agent()
    a.llm = MisreadingRouter()
    await a.turn("s", "B10 BEV")
    answer = await a.turn("s", "entendi, sabe eu fico com receio de pegar esse tipo de carro")
    state = a.sessions[("local", "s")]
    assert not state["tool_events"]
    assert "dado específico" not in answer.text
    assert state["lead_profile"]["objections"]
    assert not answer.handoff_required


@pytest.mark.parametrize("message", ["manda fotos novamente", "só rever as fotos"])
async def test_repeat_from_legacy_history_without_last_gallery_metadata(message):
    a = make_agent()
    first = await a.turn("s", "B10 BEV")
    state = a.sessions[("local", "s")]
    state.pop("last_shown_media_ids", None)
    state.pop("last_media_vehicle_id", None)
    answer = await a.turn("s", message)
    assert answer.media_ids == first.media_ids
    assert "Já mostrei" not in answer.text


async def test_more_details_delivers_verified_content_even_when_all_facts_seen():
    a = make_agent()
    await a.turn("s", "B10 BEV")
    state = a.sessions[("local", "s")]
    state["presented_fact_ids"] = (
        [f.id for f in a.grounding.facts]
        if isinstance(a.grounding.facts, list)
        else list(a.grounding.facts)
    )
    answer = await a.turn("s", "quero saber mais detalhes")
    assert answer.source_ids


async def test_composer_cannot_turn_a_fear_into_missing_technical_evidence():
    class BadComposer(MisreadingRouter):
        async def complete(self, messages, tools):
            if not tools and "compose_conversation" in messages[-1]["content"]:
                return ModelReply(
                    text=json.dumps(
                        {
                            "text": "Não tenho esse dado específico para te passar com segurança.",
                            "fact_ids": [],
                            "question": None,
                        }
                    )
                )
            return await super().complete(messages, tools)

    a = make_agent()
    a.llm = BadComposer()
    await a.turn("s", "B10 BEV")
    answer = await a.turn("s", "Fico com receio de pegar esse tipo de carro")
    assert "dado específico" not in answer.text
    assert "receio" in answer.text and "?" in answer.text
    assert not a.sessions[("local", "s")]["tool_events"]
