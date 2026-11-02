import json

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from test_sdr_experience import SDRModel

from app.api.chat import build_agent
from app.channels.evolution import DeliveryError, EvolutionAdapter, parse_message
from app.channels.evolution_store import EvolutionStore
from app.channels.evolution_worker import EvolutionWorker
from app.config import settings
from app.domain.response import AssistantResponse, Confidence
from app.main import app

NUMBER = "5511000000000"


def event(text="oi", identifier="synthetic-message", **key):
    return {
        "event": "messages.upsert",
        "instance": "test-instance",
        "data": {
            "key": {
                "remoteJid": NUMBER + "@s.whatsapp.net",
                "fromMe": False,
                "id": identifier,
                **key,
            },
            "message": {"conversation": text},
        },
    }


@pytest.fixture
def inbox(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "pilot_db_path", str(tmp_path / "wa.sqlite3"))
    monkeypatch.setattr(settings, "evolution_enabled", True)
    monkeypatch.setattr(settings, "evolution_instance", "test-instance")
    monkeypatch.setattr(settings, "evolution_api_key", SecretStr("synthetic-api-key"))
    monkeypatch.setattr(
        settings, "evolution_webhook_secret", SecretStr("synthetic-webhook-secret-" + "x" * 32)
    )
    monkeypatch.setattr(
        settings, "evolution_identity_key", SecretStr("synthetic-identity-key-" + "x" * 32)
    )
    monkeypatch.setattr(settings, "evolution_allowed_numbers", NUMBER)
    repository = EvolutionStore(settings.pilot_db_path)
    app.state.evolution_store = repository
    yield repository, TestClient(app)
    del app.state.evolution_store


def headers():
    return {"X-Webhook-Secret": settings.evolution_webhook_secret.get_secret_value()}


def test_authenticated_webhook_queue_dedup_and_no_client_password(inbox):
    store, client = inbox
    assert client.post("/hooks/evolution/test-instance", json=event()).status_code == 401
    path = "/hooks/evolution/test-instance"
    assert client.post(path, json=event(), headers=headers()).json() == {"status": "queued"}
    assert client.post(path, json=event(), headers=headers()).json() == {"status": "duplicate"}
    assert store.counts() == {"queued": 1}
    assert client.post("/hooks/evolution/other", json=event(), headers=headers()).status_code == 404


@pytest.mark.parametrize(
    "key",
    [
        {"fromMe": True},
        {"remoteJid": "123@g.us"},
        {"remoteJid": "status@broadcast"},
        {"remoteJid": "123@lid"},
        {"fromMe": "false"},
    ],
)
def test_ignore_loops_groups_status_and_unresolved_identifiers(key):
    assert parse_message(event(**key), "test-instance") is None


def test_extended_text_and_phone_alias():
    body = event(remoteJid="123@lid", remoteJidAlt=NUMBER + "@s.whatsapp.net")
    body["data"]["message"] = {"extendedTextMessage": {"text": "Olá"}}
    assert parse_message(body, "test-instance").text == "Olá"
    body["event"] = "MESSAGES_UPSERT"
    assert parse_message(body, "test-instance").recipient == NUMBER


def test_allowlist_size_and_invalid_payload(inbox):
    _, client = inbox
    path = "/hooks/evolution/test-instance"
    assert client.post(
        path, json=event(remoteJid="5511000000001@s.whatsapp.net"), headers=headers()
    ).json() == {"status": "ignored"}
    assert client.post(path, content=b"x" * 65537, headers=headers()).status_code == 413
    assert client.post(path, content=b"invalid", headers=headers()).status_code == 400


def test_public_pilot_accepts_unknown_sender_but_preserves_auth_and_loop_guards(inbox, monkeypatch):
    store, client = inbox
    monkeypatch.setattr(settings, "evolution_allowed_numbers", "*")
    path = "/hooks/evolution/test-instance"
    body = event(remoteJid="5511000000001@s.whatsapp.net")
    assert client.post(path, json=body).status_code == 401
    assert client.post(path, json=body, headers=headers()).json() == {"status": "queued"}
    for key in ({"fromMe": True}, {"remoteJid": "123@g.us"}):
        assert client.post(path, json=event(**key), headers=headers()).json() == {"status": "ignored"}
    assert store.counts() == {"queued": 1}


async def test_text_adapter_revalidates_policy_and_auth():
    requests = []

    def transport(request):
        requests.append(request)
        assert request.headers["apikey"] == "synthetic-key"
        return httpx.Response(201, json={"key": {"id": "accepted-id"}})

    adapter = EvolutionAdapter(
        "https://evolution.invalid",
        "synthetic-key",
        "test-instance",
        transport=httpx.MockTransport(transport),
    )
    response = AssistantResponse.model_construct(
        text="Preço R$ 100",
        confidence=Confidence.INSUFFICIENT,
        source_ids=[],
        media_ids=[],
        handoff_required=False,
    )
    await adapter.send_text(NUMBER, response)
    assert "R$" not in json.loads(requests[0].content)["text"]
    assert requests[0].url.path == "/message/sendText/test-instance"


async def test_uncertain_delivery_is_not_retried():
    requests = []

    def transport(request):
        requests.append(request)
        raise httpx.ReadTimeout("synthetic")

    adapter = EvolutionAdapter(
        "https://evolution.invalid",
        "synthetic-key",
        "test-instance",
        transport=httpx.MockTransport(transport),
    )
    with pytest.raises(DeliveryError, match="provider_delivery_unconfirmed"):
        await adapter.send_text(
            NUMBER, AssistantResponse(text="Olá", confidence="insufficient_evidence")
        )
    assert len(requests) == 1


def agent():
    value = build_agent(reviewed_catalog=True, test_media=True)
    value.llm = SDRModel()
    return value


async def test_worker_restart_memory_durable_reply_and_duplicate_no_resend(inbox):
    store, client = inbox
    requests = []

    def transport(request):
        requests.append(request)
        return httpx.Response(201, json={"key": {"id": "accepted-" + str(len(requests))}})

    adapter = EvolutionAdapter(
        "https://evolution.invalid",
        "synthetic-key",
        "test-instance",
        transport=httpx.MockTransport(transport),
    )
    worker = EvolutionWorker(store, agent(), adapter, send_enabled=True)
    path = "/hooks/evolution/test-instance"
    client.post(path, json=event("Me chamo Pessoa Sintetica", "name"), headers=headers())
    assert await worker.once() and await worker.once()
    assert store.counts() == {"sent": 1}
    client.post(path, json=event("Me chamo Pessoa Sintetica", "name"), headers=headers())
    assert not await worker.once() and len(requests) == 1
    worker = EvolutionWorker(
        EvolutionStore(settings.pilot_db_path), agent(), adapter, send_enabled=True
    )
    client.post(path, json=event("Oi", "hello"), headers=headers())
    assert await worker.once() and await worker.once()
    assert "prefere ser chamado" not in json.loads(requests[-1].content)["text"]
    assert len(worker.agent.sessions) == 1


async def test_media_binary_approved_only_and_partial_delivery_not_replayed(inbox):
    store, client = inbox
    requests = []

    def transport(request):
        requests.append(request)
        if request.url.path.endswith("/sendMedia/test-instance"):
            assert "multipart/form-data" in request.headers["content-type"]
            assert b'filename="vehicle.jpeg"' in request.content
            assert b"\xff\xd8\xff" in request.content
            raise httpx.ReadTimeout("synthetic")
        return httpx.Response(201, json={"key": {"id": "accepted-text"}})

    adapter = EvolutionAdapter(
        "https://evolution.invalid",
        "synthetic-key",
        "test-instance",
        transport=httpx.MockTransport(transport),
    )
    worker = EvolutionWorker(store, agent(), adapter, send_enabled=True)
    client.post("/hooks/evolution/test-instance", json=event("Fotos do B10 BEV"), headers=headers())
    await worker.once()
    await worker.once()
    assert store.counts() == {"review": 1}
    assert not await worker.once()
    assert len(requests) == 2
    with store.connect() as db:
        assert db.execute("SELECT state FROM pilot_wa_outbox WHERE part=0").fetchone()[0] == "sent"
        assert (
            db.execute("SELECT state FROM pilot_wa_outbox WHERE part=1").fetchone()[0]
            == "uncertain"
        )


async def test_dry_run_never_calls_provider_and_recovery_never_regenerates(inbox):
    store, _ = inbox

    class Never:
        async def send_text(self, *args):
            raise AssertionError("must not send")

    store.enqueue("dry", "person", "test-instance", NUMBER, "Oi")
    worker = EvolutionWorker(store, agent(), Never(), send_enabled=False)
    await worker.once()
    await worker.once()
    assert store.counts() == {"dry_run": 1}
    store.enqueue("interrupted", "person", "test-instance", NUMBER, "Oi")
    assert store.claim()["event_id"] == "interrupted"
    store.recover()
    assert store.counts() == {"dry_run": 1, "review": 1}
    assert not await worker.once()


async def test_whatsapp_forget_command_erases_private_memory_and_drafts(inbox):
    store, client = inbox

    class Never:
        async def send_text(self, *args):
            raise AssertionError("dry run")

    worker = EvolutionWorker(store, agent(), Never(), send_enabled=False)
    path = "/hooks/evolution/test-instance"
    for index, text in enumerate(
        ["Me chamo Pessoa Sintetica", "B10 BEV", "Uso na cidade", "Apagar meus dados"]
    ):
        client.post(path, json=event(text, str(index)), headers=headers())
        await worker.once()
        await worker.once()
    with store.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM pilot_people").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM pilot_opportunities").fetchone()[0] == 0
        assert not any(
            "Pessoa Sintetica" in str(tuple(row))
            for row in db.execute("SELECT * FROM pilot_wa_inbox")
        )
        assert not any(
            "Pessoa Sintetica" in row[0]
            for row in db.execute("SELECT content FROM pilot_wa_outbox")
        )
    assert not worker.agent.sessions


async def test_channel_phone_is_reused_only_after_explicit_sharing_consent(inbox):
    store, client = inbox

    class Never:
        async def send_text(self, *args):
            raise AssertionError("dry run")

    worker = EvolutionWorker(store, agent(), Never(), send_enabled=False)
    path = "/hooks/evolution/test-instance"
    for index, text in enumerate(["Me chamo Pessoa Sintetica", "Quero falar com um vendedor"]):
        client.post(path, json=event(text, str(index)), headers=headers())
        await worker.once()
        await worker.once()
    profile = next(iter(worker.agent.sessions.values()))["lead_profile"]
    assert profile["contact_phone"] is None and profile["consent"] == "offered"
    client.post(path, json=event("sim", "authorized"), headers=headers())
    await worker.once()
    await worker.once()
    profile = next(iter(worker.agent.sessions.values()))["lead_profile"]
    assert profile["consent"] == "granted" and profile["contact_phone"] == NUMBER
    assert profile["handoff_summary"]["status"] == "prepared_not_sent"
    assert NUMBER not in json.dumps(worker.agent.llm.calls)


async def test_rate_limit_retries_are_bounded_and_server_errors_are_not_retried(monkeypatch):
    import app.channels.evolution as module

    waits = []

    async def sleep(delay):
        if delay:
            waits.append(delay)

    monkeypatch.setattr(module.asyncio, "sleep", sleep)
    calls = []

    def rate(request):
        calls.append(request)
        if len(calls) < 3:
            return httpx.Response(429)
        return httpx.Response(201, json={"key": {"id": "accepted"}})

    adapter = EvolutionAdapter(
        "https://evolution.invalid",
        "synthetic-key",
        "test-instance",
        transport=httpx.MockTransport(rate),
    )
    response = AssistantResponse(text="Olá", confidence="insufficient_evidence")
    assert await adapter.send_text(NUMBER, response) == "accepted"
    assert len(calls) == 3 and waits == [0.5, 1]
    calls.clear()

    def failure(request):
        calls.append(request)
        return httpx.Response(500, json={"private": "must not be exposed"})

    adapter.transport = httpx.MockTransport(failure)
    with pytest.raises(DeliveryError, match="^provider_delivery_unconfirmed$"):
        await adapter.send_text(NUMBER, response)
    assert len(calls) == 1


async def test_erasure_bypasses_turn_limit_and_cancels_pending_work(inbox):
    store, _ = inbox
    for index in range(40):
        store.enqueue(str(index), "person", "test-instance", NUMBER, "oi")
    with pytest.raises(ValueError):
        store.enqueue("over", "person", "test-instance", NUMBER, "oi")
    store.enqueue("erase", "person", "test-instance", NUMBER, "Apagar meus dados!")

    class Never:
        async def send_text(self, *args):
            raise AssertionError("dry run")

    worker = EvolutionWorker(store, agent(), Never(), send_enabled=False)
    await worker.once()
    await worker.once()
    assert store.counts() == {"cancelled": 40, "dry_run": 1}
    assert not await worker.once()
    assert not worker.agent.llm.calls
