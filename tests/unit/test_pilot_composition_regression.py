import json

import pytest

from app.agent.llm import ModelReply
from app.api.chat import build_agent
from scripts.evaluate_lia_quality import QualityModel


class MissingFactIDs(QualityModel):
    async def complete(self, messages, tools):
        if not tools and messages[-1]["content"].startswith("{"):
            context = json.loads(messages[-1]["content"])
            if context.get("task") == "compose_conversation" and context["intent"] == "technical":
                return ModelReply(
                    text=json.dumps({"text": "Vamos conhecer esse ponto do B10.", "fact_ids": []})
                )
        return await super().complete(messages, tools)


@pytest.mark.asyncio
async def test_returning_greeting_does_not_enter_unknown_intent():
    agent = build_agent(reviewed_catalog=True, test_media=True)
    agent.llm = QualityModel()
    await agent.turn("pilot-regression", "Fotos do B10 BEV")
    await agent.turn("pilot-regression", "Oi")
    state = agent.sessions[("local", "pilot-regression")]
    assert state["composition"]["intent"] == "welcome"
    assert state["usage"]["calls"] == 1
    assert not state["tool_events"]


@pytest.mark.asyncio
async def test_missing_fact_selection_does_not_discard_available_approved_answer():
    agent = build_agent(reviewed_catalog=True, test_media=True)
    agent.llm = MissingFactIDs()
    await agent.turn("pilot-regression", "Fotos do B10 BEV")
    response = await agent.turn("pilot-regression", "Saber sobre o b10")
    assert response.source_ids
    assert "218" in response.text or "405" in response.text
    assert "Não consegui concluir" not in response.text
    assert not response.handoff_required
