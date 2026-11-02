"""Bounded audio validation and a provider-independent STT port. No disk storage."""

import io
import json
import math
import struct
import wave
from dataclasses import dataclass
from typing import Protocol

import httpx


class AudioError(ValueError):
    """Static, sanitized reason codes only."""

    CODES = frozenset(
        {
            "invalid_ogg",
            "invalid_ogg_crc",
            "invalid_ogg_sequence",
            "unsupported_ogg_codec",
            "invalid_ogg_duration",
            "audio_size",
            "unsupported_wav",
            "truncated_wav",
            "invalid_wav",
            "unsupported_audio_type",
            "audio_duration",
            "stt_provider_error",
            "stt_response_size",
            "empty_or_oversize_transcript",
            "no_speech",
            "stt_timeout",
            "stt_connection_error",
            "stt_invalid_response",
            "invalid_audio_reference",
            "media_unavailable",
            "audio_download_size",
            "invalid_media_response",
            "media_timeout",
            "media_connection_error",
            "stt_disabled",
            "audio_metadata_limit",
        }
    )

    def __init__(self, code):
        super().__init__(code if code in self.CODES else "audio_error")


@dataclass(frozen=True)
class AudioFile:
    content: bytes
    mime: str
    filename: str
    duration: float


def _ogg_duration(data):
    offset, serial, sequence, granule, pre_skip = 0, None, 0, None, None
    ended = False
    while offset < len(data):
        if data[offset : offset + 4] != b"OggS" or offset + 27 > len(data):
            raise AudioError("invalid_ogg")
        header = data[offset : offset + 27]
        if header[4] != 0 or header[5] & ~7:
            raise AudioError("invalid_ogg")
        segments = header[26]
        table = data[offset + 27 : offset + 27 + segments]
        end = offset + 27 + segments + sum(table)
        if len(table) != segments or end > len(data):
            raise AudioError("invalid_ogg")
        page = bytearray(data[offset:end])
        expected = int.from_bytes(page[22:26], "little")
        page[22:26] = b"\0" * 4
        crc = 0
        for byte in page:
            crc ^= byte << 24
            for _ in range(8):
                crc = ((crc << 1) ^ (0x04C11DB7 if crc & 0x80000000 else 0)) & 0xFFFFFFFF
        if crc != expected:
            raise AudioError("invalid_ogg_crc")
        page_serial, page_sequence = struct.unpack_from("<II", header, 14)
        if page_sequence != sequence or serial not in (None, page_serial) or ended:
            raise AudioError("invalid_ogg_sequence")
        serial, sequence = page_serial, sequence + 1
        body = data[offset + 27 + segments : end]
        if offset == 0:
            if (
                not header[5] & 2
                or len(body) < 19
                or not body.startswith(b"OpusHead")
                or body[8] != 1
                or body[9] not in (1, 2)
            ):
                raise AudioError("unsupported_ogg_codec")
            pre_skip = int.from_bytes(body[10:12], "little")
        position = int.from_bytes(header[6:14], "little")
        if position != 2**64 - 1:
            if granule is not None and position < granule:
                raise AudioError("invalid_ogg_duration")
            granule = position
        ended = bool(header[5] & 4)
        offset = end
    if not ended or granule is None or pre_skip is None or granule <= pre_skip:
        raise AudioError("invalid_ogg_duration")
    return (granule - pre_skip) / 48000


def validate_audio(content, mime, *, max_bytes=2_000_000, max_seconds=120):
    if not content or len(content) > max_bytes:
        raise AudioError("audio_size")
    mime = mime.split(";", 1)[0].strip().lower()
    if mime == "audio/ogg" and content.startswith(b"OggS"):
        duration = _ogg_duration(content)
        filename = "voice.ogg"
    elif (
        mime in {"audio/wav", "audio/x-wav"}
        and content.startswith(b"RIFF")
        and content[8:12] == b"WAVE"
    ):
        try:
            with wave.open(io.BytesIO(content)) as audio:
                if audio.getnchannels() not in (1, 2) or not 8000 <= audio.getframerate() <= 48000:
                    raise AudioError("unsupported_wav")
                expected = audio.getnframes() * audio.getnchannels() * audio.getsampwidth()
                if len(audio.readframes(audio.getnframes())) != expected:
                    raise AudioError("truncated_wav")
                duration = audio.getnframes() / audio.getframerate()
        except (wave.Error, EOFError):
            raise AudioError("invalid_wav") from None
        filename, mime = "voice.wav", "audio/wav"
    else:
        raise AudioError("unsupported_audio_type")
    if not math.isfinite(duration) or not 0 < duration <= max_seconds:
        raise AudioError("audio_duration")
    return AudioFile(content, mime, filename, duration)


class SpeechToText(Protocol):
    async def transcribe(self, audio: AudioFile) -> str: ...


class GroqSpeechToText:
    def __init__(self, key, model="whisper-large-v3-turbo", *, timeout=30, transport=None):
        if not key or model not in {"whisper-large-v3-turbo", "whisper-large-v3"}:
            raise ValueError("Invalid STT configuration")
        self.key, self.model, self.timeout, self.transport = key, model, timeout, transport

    async def transcribe(self, audio):
        try:
            async with (
                httpx.AsyncClient(
                    timeout=self.timeout,
                    trust_env=False,
                    follow_redirects=False,
                    transport=self.transport,
                ) as client,
                client.stream(
                    "POST",
                    "https://api.groq.com/openai/v1/audio/transcriptions",
                    headers={"Authorization": "Bearer " + self.key},
                    data={
                        "model": self.model,
                        "language": "pt",
                        "response_format": "verbose_json",
                        "temperature": "0",
                    },
                    files={"file": (audio.filename, audio.content, audio.mime)},
                ) as response,
            ):
                if response.status_code != 200:
                    raise AudioError("stt_provider_error")
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > 131072:
                        raise AudioError("stt_response_size")
            result = json.loads(body)
            text = result.get("text")
            if not isinstance(text, str) or not 1 <= len(text.strip()) <= 4000:
                raise AudioError("empty_or_oversize_transcript")
            segments = result.get("segments", [])
            if segments and all(s.get("no_speech_prob", 0) > 0.8 for s in segments):
                raise AudioError("no_speech")
            return text.strip()
        except httpx.TimeoutException:
            raise AudioError("stt_timeout") from None
        except httpx.HTTPError:
            raise AudioError("stt_connection_error") from None
        except (json.JSONDecodeError, TypeError, AttributeError):
            raise AudioError("stt_invalid_response") from None
