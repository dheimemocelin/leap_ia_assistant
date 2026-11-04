"""Idle sessions start fresh without erasing confirmed customer memory."""

import pytest

from tests.unit.test_lia_v2 import make_agent


@pytest.mark.parametrize("status", ["ACTIVE", "HANDOFF_PENDING"])
async def test_two_hour_gap_opens_new_attendance_without_pushing_old_car(status):
    a = make_agent()
    now = [1800000000.0]
    a.clock = lambda: now[0]
    for message in ["Oi", "Pessoa Sintetica", "B10 BEV"]:
        await a.turn("s", message)
    before = a.sessions[("local", "s")]["conversation_session"].copy()
    a.sessions[("local", "s")]["conversation_session"]["status"] = status
    now[0] += 7200
    answer = await a.turn("s", "Oi")
    state = a.sessions[("local", "s")]
    assert state["conversation_session"]["id"] != before["id"]
    assert "Pessoa Sintetica" in answer.text
    assert "B10" not in answer.text and "continuar" not in answer.text
    assert state["lead_profile"]["vehicle_id"] == "b10-bev"
    assert "chamar" not in answer.text
    remembered = await a.turn("s", "Quero continuar")
    assert a.sessions[("local", "s")]["lead_profile"]["vehicle_id"] == "b10-bev"
    assert "B10" in remembered.text


async def test_confirmed_human_transfer_is_not_reopened_by_inactivity():
    from app.agent.lifecycle import SessionStatus, begin_session

    session, _ = begin_session(None, 1800000000, 3600)
    session.status = SessionStatus.TRANSFERRED
    after, archived = begin_session(session.model_dump(), 1800007200, 3600)
    assert after.id == session.id and after.status == "TRANSFERRED" and archived is None


async def test_greeting_does_not_force_previous_topic_even_within_active_session():
    a = make_agent()
    await a.turn("s", "B10 BEV")
    session = a.sessions[("local", "s")]["conversation_session"]["id"]
    answer = await a.turn("s", "Oi")
    assert "B10" not in answer.text and "continuar" not in answer.text
    assert a.sessions[("local", "s")]["conversation_session"]["id"] == session
