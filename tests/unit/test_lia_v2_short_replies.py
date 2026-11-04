"""Short replies stay tied to the last question, without invented service topics."""

import json

from app.agent.llm import ModelReply
from tests.unit.test_lia_v2 import authorized_handoff, make_agent
from tests.unit.test_lia_v2_field_regressions import MisreadingRouter
from tests.unit.test_sales_delivery import SalesModel


async def test_road_reply_to_usage_question_is_not_a_technical_lookup():
    a = make_agent()
    a.llm = MisreadingRouter()
    for text in ["B10 REEV", "Pessoa Sintetica"]:
        await a.turn("s", text)
    answer = await a.turn("s", "Na estrada mesmo")
    state = a.sessions[("local", "s")]
    assert state["lead_profile"]["usage"] == "viagens"
    assert not state["tool_events"]
    assert "dado específico" not in answer.text


class InventedRepair(SalesModel):
    async def complete(self, messages, tools):
        if not tools and "compose_conversation" in messages[-1]["content"]:
            return ModelReply(
                text=json.dumps(
                    {
                        "text": "Entendo que você quer saber como proceder com a manutenção do seu B10 em viagens.",
                        "fact_ids": [],
                        "question": None,
                    }
                )
            )
        return await super().complete(messages, tools)


async def test_how_requests_repair_of_last_answer_not_invented_maintenance():
    a = make_agent()
    await a.turn("s", "B10 REEV")
    a.llm = InventedRepair()
    answer = await a.turn("s", "Como?")
    assert not any(w in answer.text.lower() for w in ["manutenção", "reparo", "oficina"])
    assert not a.sessions[("local", "s")]["tool_events"]


async def test_local_handoff_copy_is_customer_facing_and_does_not_claim_delivery(tmp_path):
    _, store, _, answer = await authorized_handoff(tmp_path, mode="local")
    assert store.handoff_metrics() == {"queued": 1}
    assert not any(w in answer.text.lower() for w in ["fila local", "resumo", "recebimento"])
    assert "ainda não foi enviado" in answer.text


async def test_road_reply_clarifies_range_when_previous_question_was_about_range():
    a = make_agent()
    await a.turn("s", "B10 REEV")
    await a.turn("s", "Qual a autonomia?")
    answer = await a.turn("s", "Na estrada mesmo")
    state = a.sessions[("local", "s")]
    assert "medição específica de autonomia na estrada" in answer.text
    assert state["lead_profile"]["usage"] is None
    assert "dado específico" not in answer.text
    assert not state["tool_events"]
