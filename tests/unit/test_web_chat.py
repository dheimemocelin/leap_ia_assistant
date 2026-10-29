import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.api.web_chat import BrowserSessions
from app.config import settings
from app.domain.response import AssistantResponse
from app.main import app


@pytest.fixture
def browser(monkeypatch):
    monkeypatch.setattr(settings, "web_chat_password", SecretStr("synthetic-access-password"))
    app.state.browser_sessions = BrowserSessions()

    class Fake:
        def __init__(self):
            self.conversations = []

        async def turn(self, conversation_id, text, *, owner):
            self.conversations.append(conversation_id)
            return AssistantResponse(
                text="Preço R$ 180.000" if "preço" in text else "Olá, como posso ajudar?",
                confidence="insufficient_evidence",
            )

    fake = Fake()
    app.state.web_agent_reviewed = fake
    yield TestClient(app), fake
    del app.state.web_agent_reviewed
    del app.state.browser_sessions


def login(client, password="synthetic-access-password"):
    return client.post(
        "/web/login", json={"password": password}, headers={"Origin": "http://testserver"}
    )


def test_page_static_files_and_no_secrets(browser):
    client, _ = browser
    response = client.get("/")
    assert response.status_code == 200
    assert "frame-ancestors" in response.headers["content-security-policy"]
    assert "synthetic-access-password" not in response.text
    assert client.get("/web/chat.js").status_code == 200
    assert client.get("/web/chat.css").status_code == 200
    assert client.get("/.env").status_code == 404


def test_login_cookie_and_authenticated_chat(browser):
    client, fake = browser
    response = login(client)
    assert response.status_code == 200
    assert (
        "HttpOnly" in response.headers["set-cookie"]
        and "SameSite=strict" in response.headers["set-cookie"]
    )
    assert client.get("/web/session").json()["authenticated"]
    response = client.post(
        "/v1/web/messages", json={"text": "Olá"}, headers={"Origin": "http://testserver"}
    )
    assert response.status_code == 200 and response.json()["text"] == "Olá, como posso ajudar?"
    assert len(fake.conversations) == 1


def test_invalid_login_csrf_and_no_session_blocked(browser):
    client, _ = browser
    assert login(client, password="wrong").status_code == 401
    assert (
        client.post(
            "/web/login",
            json={"password": "synthetic-access-password"},
            headers={"Origin": "https://evil.invalid"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/v1/web/messages", json={"text": "Olá"}, headers={"Origin": "http://testserver"}
        ).status_code
        == 401
    )
    login(client)
    assert (
        client.post(
            "/v1/web/messages", json={"text": "Olá"}, headers={"Origin": "https://evil.invalid"}
        ).status_code
        == 403
    )


def test_cookie_isolation_reset_logout_and_policy(browser):
    client, fake = browser
    login(client)
    headers = {"Origin": "http://testserver"}
    client.post("/v1/web/messages", json={"text": "Olá"}, headers=headers)
    first = fake.conversations[-1]
    client.post("/web/reset", json={}, headers=headers)
    result = client.post("/v1/web/messages", json={"text": "preço"}, headers=headers)
    assert fake.conversations[-1] != first
    assert "180" not in result.text and result.json()["handoff_required"]
    second = TestClient(app)
    login(second)
    second.post("/v1/web/messages", json={"text": "Olá"}, headers=headers)
    assert len(set(fake.conversations)) == 3
    client.post("/web/logout", json={}, headers=headers)
    assert not client.get("/web/session").json()["authenticated"]
    assert second.get("/web/session").json()["authenticated"]


def test_secure_cookie_on_https_and_expiry(browser):
    _, _ = browser
    client = TestClient(app, base_url="https://testserver")
    result = client.post(
        "/web/login",
        json={"password": "synthetic-access-password"},
        headers={"Origin": "https://testserver"},
    )
    assert "Secure" in result.headers["set-cookie"]
    for session in app.state.browser_sessions.sessions.values():
        session["expires"] = 0
    assert not client.get("/web/session").json()["authenticated"]


def test_login_rate_limit_and_message_budget(browser):
    client, _ = browser
    for _ in range(20):
        login(client, password="wrong")
    assert login(client).status_code == 429
    app.state.browser_sessions = BrowserSessions()
    login(client)
    session = next(iter(app.state.browser_sessions.sessions.values()))
    session["turns"] = 30
    assert (
        client.post(
            "/v1/web/messages", json={"text": "Olá"}, headers={"Origin": "http://testserver"}
        ).status_code
        == 429
    )
