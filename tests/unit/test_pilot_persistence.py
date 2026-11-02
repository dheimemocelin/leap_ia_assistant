import json
import sqlite3

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from test_sdr_experience import SDRModel

from app.api.chat import build_agent
from app.api.web_chat import BrowserSessions
from app.config import settings
from app.main import app
from app.pilot_store import PilotStore

HEADERS = {"Origin": "http://testserver"}


def new_agent():
    agent = build_agent(reviewed_catalog=True, test_media=True)
    agent.llm = SDRModel()
    return agent


@pytest.fixture
def pilot(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "pilot_db_path", str(tmp_path / "pilot.sqlite3"))
    monkeypatch.setattr(settings, "web_chat_password", SecretStr("synthetic-access-password"))
    for key in ["pilot_store", "browser_sessions", "web_agent_reviewed", "web_agent_pending"]:
        if hasattr(app.state, key):
            delattr(app.state, key)
    app.state.browser_sessions = BrowserSessions()
    app.state.web_agent_reviewed = new_agent()
    yield TestClient(app), tmp_path / "pilot.sqlite3"
    for key in ["pilot_store", "browser_sessions", "web_agent_reviewed", "web_agent_pending"]:
        if hasattr(app.state, key):
            delattr(app.state, key)


def login(client):
    response = client.post(
        "/web/login", json={"password": "synthetic-access-password"}, headers=HEADERS
    )
    assert response.status_code == 200
    return response


def say(client, text):
    response = client.post("/v1/web/messages", json={"text": text}, headers=HEADERS)
    assert response.status_code == 200, response.text
    return response.json()


def test_name_survives_logout_server_restart_and_reset(pilot):
    client, path = pilot
    login(client)
    say(client, "Me chamo Pessoa Sintetica")
    say(client, "B10 BEV")
    say(client, "Uso na cidade")
    client.post("/web/logout", json={}, headers=HEADERS)
    app.state.browser_sessions = BrowserSessions()
    app.state.web_agent_reviewed = new_agent()
    del app.state.pilot_store
    login(client)
    result = say(client, "Oi")
    assert "prefere ser chamado" not in result["text"]
    client.post("/web/reset", json={}, headers=HEADERS)
    result = say(client, "Oi")
    assert "prefere ser chamado" not in result["text"]
    assert "Lia" in result["text"]
    with sqlite3.connect(path) as db:
        assert (
            db.execute("SELECT display_name FROM pilot_people").fetchone()[0] == "Pessoa Sintetica"
        )
    assert path.stat().st_mode & 0o777 == 0o600


def test_two_browsers_same_password_do_not_share_name(pilot):
    first, _ = pilot
    second = TestClient(app)
    login(first)
    say(first, "Me chamo Pessoa Sintetica")
    login(second)
    result = say(second, "Oi")
    assert "prefere ser chamado" in result["text"]
    assert "Pessoa Sintetica" not in result["text"]


def test_opportunity_upsert_and_consent_are_persisted_only_locally(pilot):
    client, path = pilot
    login(client)
    say(client, "Me chamo Pessoa Sintetica")
    say(client, "B10 BEV")
    say(client, "Uso na cidade")
    say(client, "Quero visitar")
    say(client, "Quero visitar")
    with sqlite3.connect(path) as db:
        rows = db.execute("SELECT payload FROM pilot_opportunities").fetchall()
        assert len(rows) == 1
        assert "authorized_handoff" not in json.loads(rows[0][0])
    say(client, "Quero falar com um vendedor")
    say(client, "sim")
    say(client, "11000000000")
    with sqlite3.connect(path) as db:
        payload = json.loads(db.execute("SELECT payload FROM pilot_opportunities").fetchone()[0])
        assert payload["authorized_handoff"]["status"] == "prepared_not_sent"
    say(client, "Não autorizo")
    with sqlite3.connect(path) as db:
        payload = json.loads(db.execute("SELECT payload FROM pilot_opportunities").fetchone()[0])
        assert "authorized_handoff" not in payload
        assert "11000000000" not in json.dumps(payload)


def test_forget_removes_identity_states_and_opportunities(pilot):
    client, path = pilot
    login(client)
    say(client, "Me chamo Pessoa Sintetica")
    say(client, "B10 BEV")
    say(client, "Uso na cidade")
    assert (
        client.post("/web/forget", json={}, headers={"Origin": "https://evil.invalid"}).status_code
        == 403
    )
    assert client.post("/web/forget", json={}, headers=HEADERS).status_code == 200
    assert not client.get("/web/session").json()["authenticated"]
    with sqlite3.connect(path) as db:
        for table in ["pilot_people", "pilot_threads", "pilot_opportunities"]:
            assert db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
    login(client)
    assert "prefere ser chamado" in say(client, "Oi")["text"]


def test_pilot_ready_and_unknown_thread_fail_closed(pilot):
    client, path = pilot
    assert client.get("/health/ready").status_code == 200
    repository = PilotStore(str(path))
    with pytest.raises(ValueError, match="Unknown pilot conversation"):
        repository.load_state("unknown", "unknown")
    with pytest.raises(ValueError, match="Unknown pilot conversation"):
        repository.save_state("unknown", "unknown", {})


def test_database_write_failure_is_visible_and_does_not_claim_success(pilot, monkeypatch):
    client, path = pilot
    login(client)
    repository = app.state.pilot_store
    original = repository.save_state

    def fail(*args):
        raise sqlite3.OperationalError("synthetic-private-details")

    monkeypatch.setattr(repository, "save_state", fail)
    response = client.post(
        "/v1/web/messages", json={"text": "Me chamo Pessoa Sintetica"}, headers=HEADERS
    )
    assert response.status_code == 503
    assert "synthetic-private-details" not in response.text
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT display_name FROM pilot_people").fetchone()[0] is None
    monkeypatch.setattr(repository, "save_state", original)
    say(client, "Me chamo Pessoa Sintetica")
    with sqlite3.connect(path) as db:
        assert (
            db.execute("SELECT display_name FROM pilot_people").fetchone()[0] == "Pessoa Sintetica"
        )


def test_forged_browser_cookie_cannot_recover_another_person(pilot):
    client, _ = pilot
    login(client)
    say(client, "Me chamo Pessoa Sintetica")
    intruder = TestClient(app)
    intruder.cookies.set("leap_browser_identity", "A" * 43)
    login(intruder)
    assert "prefere ser chamado" in say(intruder, "Oi")["text"]


def test_reviewed_and_pending_threads_do_not_share_conversation_state(pilot):
    _, path = pilot
    repository = PilotStore(str(path))
    first = repository.open_thread("synthetic-person", "reviewed")
    second = repository.open_thread("synthetic-person", "pending")
    assert first["owner"] != second["owner"]
    repository.save_state(
        first["owner"],
        first["conversation_id"],
        {
            "history": [],
            "lead_profile": {"display_name": "Pessoa Sintetica", "vehicle_id": "b10-bev"},
        },
    )
    restored = repository.load_state(second["owner"], second["conversation_id"])
    assert restored["lead_profile"]["display_name"] == "Pessoa Sintetica"
    assert "vehicle_id" not in restored["lead_profile"]
