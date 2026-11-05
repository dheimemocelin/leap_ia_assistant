"""Finish visit qualification without claiming a booking that was not made."""

import json

from app.pilot_store import PilotStore
from tests.unit.test_lia_v2 import make_agent


async def prepared_visit(tmp_path):
    store = PilotStore(str(tmp_path / "pilot.db"))
    thread = store.open_thread("synthetic", "whatsapp:test")
    a = make_agent(store)
    for message in [
        "B10 BEV",
        "Pessoa Sintetica",
        "Vou usar na cidade",
        "Gostei muito",
        "Claro",
        "Quinta às 10h",
    ]:
        answer = await a.turn(thread["conversation_id"], message, owner=thread["owner"])
    return a, store, thread, answer


async def test_screenshot_visit_request_records_time_and_no_trade_in_then_stops_discovery(tmp_path):
    a, store, t, _ = await prepared_visit(tmp_path)
    answer = await a.turn(t["conversation_id"], "Pode agendar, não tenho carro", owner=t["owner"])
    state = store.load_state(t["owner"], t["conversation_id"])
    p = state["lead_profile"]
    assert p["trade_in_interest"] is False
    assert "quinta" in p["visit_preference"] and "10h" in p["visit_preference"]
    assert "10h" in answer.text and "sem veículo" in answer.text.lower()
    assert "ainda não" in answer.text.lower() and "agendada" in answer.text.lower()
    assert not p["pending_question"] and "?" not in answer.text
    assert "Podemos partir" not in answer.text
    assert not answer.handoff_required and p["consent"] == "not_requested"
    with store.connect() as db:
        payload = json.loads(db.execute("SELECT payload FROM pilot_opportunities").fetchone()[0])
    assert payload["visit_booking_status"] == "confirmation_required"
    await a.turn(t["conversation_id"], "Obrigado", owner=t["owner"])
    assert (
        store.load_state(t["owner"], t["conversation_id"])["conversation_session"]["status"]
        == "CLOSED"
    )


async def test_visit_acceptance_is_not_replaced_by_another_priority_question(tmp_path):
    a, store, t, _ = await prepared_visit(tmp_path)
    answer = await a.turn(t["conversation_id"], "Não tenho carro", owner=t["owner"])
    assert "?" not in answer.text
    assert "10h" in answer.text
    assert not store.load_state(t["owner"], t["conversation_id"])["lead_profile"][
        "pending_question"
    ]


async def test_model_cannot_claim_a_visit_was_booked(tmp_path):
    from app.agent.llm import ModelReply
    from tests.unit.test_sales_delivery import SalesModel

    a, store, t, _ = await prepared_visit(tmp_path)

    class BookingClaim(SalesModel):
        async def complete(self, messages, tools):
            if not tools and "compose_conversation" in messages[-1]["content"]:
                return ModelReply(
                    text=json.dumps(
                        {
                            "text": "Agendei sua visita, está confirmada.",
                            "fact_ids": [],
                            "question": None,
                        }
                    )
                )
            return await super().complete(messages, tools)

    a.llm = BookingClaim()
    answer = await a.turn(t["conversation_id"], "Pode agendar, não tenho carro", owner=t["owner"])
    assert "Agendei" not in answer.text and "está confirmada" not in answer.text
    assert "ainda não está agendada" in answer.text
    assert (
        store.load_state(t["owner"], t["conversation_id"])["lead_profile"]["visit_booking_status"]
        == "confirmation_required"
    )


async def test_minutes_and_trade_in_follow_through_without_valuation_promise(tmp_path):
    a, store, t, _ = await prepared_visit(tmp_path)
    state = store.load_state(t["owner"], t["conversation_id"])
    state["lead_profile"]["pending_question"] = "visit_preference"
    store.save_state(t["owner"], t["conversation_id"], state)
    await a.turn(t["conversation_id"], "Sexta às 14:30", owner=t["owner"])
    answer = await a.turn(t["conversation_id"], "Tenho carro na troca", owner=t["owner"])
    saved = store.load_state(t["owner"], t["conversation_id"])
    assert "14h30" in saved["lead_profile"]["visit_preference"]
    assert "14h30" in answer.text and "presencial" in answer.text
    assert "?" not in answer.text and not answer.handoff_required
    assert saved["lead_profile"]["trade_in_interest"] is True


async def test_request_to_schedule_does_not_require_answering_optional_trade_in_question(tmp_path):
    a, store, t, _ = await prepared_visit(tmp_path)
    answer = await a.turn(t["conversation_id"], "Pode agendar", owner=t["owner"])
    saved = store.load_state(t["owner"], t["conversation_id"])["lead_profile"]
    assert saved["trade_in_interest"] is None
    assert saved["pending_question"] is None
    assert "10h" in answer.text and "ainda não está agendada" in answer.text
    assert "?" not in answer.text and "troca" not in answer.text
