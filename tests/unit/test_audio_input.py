import base64
import io
import json
import struct
import wave

import httpx
import pytest
from test_evolution import agent as build_test_agent
from test_evolution import event, headers
from test_evolution import inbox as inbox  # noqa: PLC0414 - re-export the pytest fixture

from app.channels.audio import AudioError, GroqSpeechToText, validate_audio
from app.channels.evolution import EvolutionAdapter, parse_message
from app.channels.evolution_worker import EvolutionWorker
from app.config import settings


def wav_bytes(seconds=0.1):
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\0\0" * int(16000 * seconds))
    return output.getvalue()


def ogg_bytes():
    def page(body, sequence, flags, granule):
        header = (
            b"OggS\0"
            + bytes([flags])
            + struct.pack("<QII", granule, 7, sequence)
            + b"\0" * 4
            + b"\x01"
            + bytes([len(body)])
        )
        data = bytearray(header + body)
        crc = 0
        for byte in data:
            crc ^= byte << 24
            for _ in range(8):
                crc = ((crc << 1) ^ (0x04C11DB7 if crc & 0x80000000 else 0)) & 0xFFFFFFFF
        data[22:26] = struct.pack("<I", crc)
        return data

    head = b"OpusHead" + b"\x01\x01" + struct.pack("<HIhB", 312, 48000, 0, 0)
    # Container-validation fixture only; this is not a recorded or decoded voice.
    return bytes(page(head, 0, 2, 0) + page(b"synthetic-opus-packet", 1, 4, 48312))


def voice(identifier="voice-1"):
    body = event(identifier=identifier)
    body["data"]["message"] = {
        "audioMessage": {
            "mimetype": "audio/ogg; codecs=opus",
            "seconds": 1,
            "fileLength": "1000",
            "ptt": True,
            "url": "http://169.254.169.254/private",
            "mediaKey": "never-persist-this",
        }
    }
    return body


class FakeSTT:
    def __init__(self, text="Me chamo Pessoa Sintetica, qual a autonomia do C10 BEV?"):
        self.text, self.calls = text, 0

    async def transcribe(self, audio):
        self.calls += 1
        return self.text


class FakeChannel:
    def __init__(self, content=None):
        self.content = wav_bytes() if content is None else content
        self.sent, self.downloads = [], 0

    async def download_audio(self, reference, **kwargs):
        assert set(reference) == {"message_id", "mime", "bytes", "seconds"}
        self.downloads += 1
        return self.content, "audio/wav"

    async def send_text(self, recipient, response):
        self.sent.append(response.text)
        return "synthetic-provider-id"

    async def send_image(self, *args):
        pytest.fail("Voice replies must be text-only")


def test_normalized_voice_keeps_no_url_key_or_audio_bytes():
    normalized = parse_message(voice(), "test-instance")
    assert normalized.input_type == "audio" and normalized.text == ""
    serialized = json.dumps(normalized.audio)
    assert "169.254" not in serialized and "never-persist" not in serialized
    assert normalized.audio["bytes"] == 1000


def test_validate_wav_and_ogg_container_duration_and_integrity():
    assert validate_audio(wav_bytes(), "audio/wav").duration == pytest.approx(0.1)
    assert validate_audio(ogg_bytes(), "audio/ogg; codecs=opus").duration == pytest.approx(1)
    damaged = bytearray(ogg_bytes())
    damaged[-1] ^= 1
    with pytest.raises(AudioError):
        validate_audio(damaged, "audio/ogg")


@pytest.mark.parametrize(
    "content,mime,limits",
    [
        (b"", "audio/wav", {}),
        (b"not audio", "audio/wav", {}),
        (wav_bytes(), "image/jpeg", {}),
        (wav_bytes(), "audio/mp4", {}),
        (wav_bytes(), "audio/wav", {"max_bytes": 10}),
        (wav_bytes(1), "audio/wav", {"max_seconds": 0.5}),
        (wav_bytes()[:-100], "audio/wav", {}),
    ],
)
def test_invalid_empty_oversize_or_long_audio_is_rejected(content, mime, limits):
    with pytest.raises(AudioError):
        validate_audio(content, mime, **limits)


async def test_authenticated_download_uses_only_server_message_id_not_webhook_url():
    def transport(request):
        assert request.headers["apikey"] == "synthetic-key"
        assert (
            request.url == "https://evolution.invalid/chat/getBase64FromMediaMessage/test-instance"
        )
        assert json.loads(request.content) == {
            "message": {"key": {"id": "voice-1"}},
            "convertToMp4": False,
        }
        return httpx.Response(
            200, json={"base64": base64.b64encode(wav_bytes()).decode(), "mimetype": "audio/wav"}
        )

    channel = EvolutionAdapter(
        "https://evolution.invalid",
        "synthetic-key",
        "test-instance",
        transport=httpx.MockTransport(transport),
    )
    content, mime = await channel.download_audio(
        {"message_id": "voice-1", "url": "http://169.254.169.254/"}, max_bytes=10000
    )
    assert validate_audio(content, mime).duration > 0


@pytest.mark.parametrize(
    "status,payload",
    [
        (302, {}),
        (404, {}),
        (200, {"base64": "!invalid", "mimetype": "audio/wav"}),
        (200, {"base64": "A" * 100000, "mimetype": "audio/wav"}),
    ],
)
async def test_media_errors_and_size_are_bounded(status, payload):
    channel = EvolutionAdapter(
        "https://evolution.invalid",
        "synthetic-key",
        "test-instance",
        transport=httpx.MockTransport(lambda r: httpx.Response(status, json=payload)),
    )
    with pytest.raises(AudioError):
        await channel.download_audio({"message_id": "voice-1"}, max_bytes=100)


async def test_groq_stt_uploads_binary_portuguese_and_rejects_silence():
    requests = []

    def transport(request):
        requests.append(request)
        assert request.headers["Authorization"] == "Bearer synthetic-key"
        assert b'filename="voice.wav"' in request.content and b"\r\npt\r\n" in request.content
        return httpx.Response(
            200, json={"text": "Quero conhecer o C10", "segments": [{"no_speech_prob": 0.01}]}
        )

    stt = GroqSpeechToText("synthetic-key", transport=httpx.MockTransport(transport))
    assert await stt.transcribe(validate_audio(wav_bytes(), "audio/wav")) == "Quero conhecer o C10"
    assert len(requests) == 1
    stt.transport = httpx.MockTransport(
        lambda r: httpx.Response(200, json={"text": "", "segments": []})
    )
    with pytest.raises(AudioError):
        await stt.transcribe(validate_audio(wav_bytes(), "audio/wav"))


async def test_voice_and_text_share_memory_and_duplicates_do_not_transcribe_twice(
    inbox, monkeypatch
):
    store, client = inbox
    monkeypatch.setattr(settings, "evolution_audio_enabled", True)
    channel, stt = FakeChannel(), FakeSTT()
    worker = EvolutionWorker(store, build_test_agent(), channel, stt=stt, send_enabled=True)
    path = "/hooks/evolution/test-instance"
    assert client.post(path, json=voice(), headers=headers()).json() == {"status": "queued"}
    assert client.post(path, json=voice(), headers=headers()).json() == {"status": "duplicate"}
    await worker.once()
    await worker.once()
    assert stt.calls == channel.downloads == 1 and "338" in channel.sent[0]
    assert client.post(
        path, json=event("Qual meu nome?", "text-after-voice"), headers=headers()
    ).json() == {"status": "queued"}
    await worker.once()
    await worker.once()
    assert "Pessoa Sintetica" in channel.sent[-1] and stt.calls == 1
    with store.connect() as db:
        assert db.execute("SELECT count(*) FROM pilot_people").fetchone()[0] == 1
        for row in db.execute("SELECT audio_ref,text FROM pilot_wa_inbox"):
            assert row[0] == row[1] == ""
        metrics = json.loads(
            db.execute("SELECT metrics FROM pilot_wa_inbox WHERE input_type='audio'").fetchone()[0]
        )
        assert metrics["stt_duration_seconds"] == pytest.approx(0.1)


@pytest.mark.parametrize("failure", ["invalid_file", "empty_stt", "unavailable"])
async def test_audio_failure_returns_useful_text_through_same_outbox(inbox, monkeypatch, failure):
    store, client = inbox
    monkeypatch.setattr(settings, "evolution_audio_enabled", True)
    channel, stt = (
        FakeChannel(b"invalid" if failure == "invalid_file" else None),
        FakeSTT("" if failure == "empty_stt" else "oi"),
    )
    if failure == "unavailable":

        async def unavailable(*args, **kwargs):
            raise AudioError("media_unavailable")

        channel.download_audio = unavailable
    worker = EvolutionWorker(store, build_test_agent(), channel, stt=stt, send_enabled=True)
    client.post("/hooks/evolution/test-instance", json=voice(), headers=headers())
    await worker.once()
    await worker.once()
    assert len(channel.sent) == 1 and "Não consegui entender esse áudio" in channel.sent[0]
    assert store.counts() == {"sent": 1}


def test_old_inbox_migrates_and_retention_clears_audio_references(inbox):
    store, _ = inbox
    store.enqueue(
        "old", "synthetic", "test-instance", "5511000000000", "", "audio", {"message_id": "old"}
    )
    with store.connect() as db:
        db.execute("UPDATE pilot_wa_inbox SET created_at=1 WHERE event_id='old'")
    store.purge_content()
    with store.connect() as db:
        row = db.execute(
            "SELECT state,audio_ref,person FROM pilot_wa_inbox WHERE event_id='old'"
        ).fetchone()
        assert tuple(row) == ("cancelled", "", "")


async def test_stt_timeout_and_no_speech_are_explicit_failures():
    async def timeout(request):
        raise httpx.ReadTimeout("synthetic provider body")

    stt = GroqSpeechToText("synthetic-key", transport=httpx.MockTransport(timeout))
    with pytest.raises(AudioError, match="stt_timeout"):
        await stt.transcribe(validate_audio(wav_bytes(), "audio/wav"))
    stt.transport = httpx.MockTransport(
        lambda r: httpx.Response(
            200, json={"text": "hallucinated noise", "segments": [{"no_speech_prob": 0.99}]}
        )
    )
    with pytest.raises(AudioError, match="no_speech"):
        await stt.transcribe(validate_audio(wav_bytes(), "audio/wav"))


async def test_audio_metadata_limit_rejects_before_download(inbox, monkeypatch):
    store, client = inbox
    monkeypatch.setattr(settings, "evolution_audio_enabled", True)
    channel, stt = FakeChannel(), FakeSTT()
    worker = EvolutionWorker(store, build_test_agent(), channel, stt=stt, send_enabled=True)
    body = voice()
    body["data"]["message"]["audioMessage"]["seconds"] = 999
    client.post("/hooks/evolution/test-instance", json=body, headers=headers())
    await worker.once()
    await worker.once()
    assert stt.calls == channel.downloads == 0
    assert "Não consegui entender" in channel.sent[0]


async def test_voice_deletion_requires_text_confirmation(inbox, monkeypatch):
    store, client = inbox
    monkeypatch.setattr(settings, "evolution_audio_enabled", True)
    channel, stt = FakeChannel(), FakeSTT("Apagar meus dados")
    worker = EvolutionWorker(store, build_test_agent(), channel, stt=stt, send_enabled=True)
    client.post("/hooks/evolution/test-instance", json=voice(), headers=headers())
    await worker.once()
    await worker.once()
    assert 'escreva "Apagar meus dados"' in channel.sent[0]


def test_voice_is_opt_in(inbox, monkeypatch):
    _, client = inbox
    monkeypatch.setattr(settings, "evolution_audio_enabled", False)
    assert client.post(
        "/hooks/evolution/test-instance", json=voice(), headers=headers()
    ).json() == {"status": "ignored"}


def test_additive_schema_migration_preserves_old_rows(tmp_path):
    import sqlite3
    import time

    from app.channels.evolution_store import EvolutionStore

    path = tmp_path / "old.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute(
            "CREATE TABLE pilot_wa_inbox(event_id TEXT PRIMARY KEY,person TEXT,instance TEXT,recipient TEXT,text TEXT,state TEXT DEFAULT 'queued',response TEXT,created_at INTEGER)"
        )
        db.execute(
            "INSERT INTO pilot_wa_inbox(event_id,person,instance,recipient,text,created_at) VALUES ('synthetic','p','i','5511000000000','synthetic text',?)",
            (int(time.time()),),
        )
    store = EvolutionStore(str(path))
    with store.connect() as db:
        row = db.execute("SELECT text,input_type,audio_ref FROM pilot_wa_inbox").fetchone()
        assert tuple(row) == ("synthetic text", "text", "")
