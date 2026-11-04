import asyncio
import hashlib
import json
import logging
import time
from pathlib import Path

from app.catalog.media_library import MediaSearchQuery, norm
from app.channels.audio import AudioError, validate_audio
from app.domain.response import AssistantResponse


def approved_image(agent, media_id):
    record = next((r for r in agent.catalog.media() if r.id == media_id), None)
    if record is None or record not in agent.media.search(
        MediaSearchQuery(vehicle_id=record.vehicle_id, limit=100)
    ):
        raise ValueError("Media unavailable")
    asset = Path(record.asset_path)
    if not asset.is_absolute():
        parts = asset.parts
        if parts[:2] == ("assets", "media"):
            asset = Path(*parts[2:])
        asset = agent.media.asset_root / asset
    asset = asset.resolve()
    if (
        not asset.is_relative_to(agent.media.asset_root)
        or not asset.is_file()
        or asset.stat().st_size > 10_000_000
    ):
        raise ValueError("Media unavailable")
    data = asset.read_bytes()
    if (
        record.mime_type != "image/jpeg"
        or not data.startswith(b"\xff\xd8\xff")
        or not data.endswith(b"\xff\xd9")
        or not record.sha256
        or hashlib.sha256(data).hexdigest() != record.sha256
    ):
        raise ValueError("Media unavailable")
    return data


class EvolutionWorker:
    def __init__(
        self,
        store,
        agent,
        adapter,
        *,
        send_enabled=False,
        stt=None,
        audio_max_bytes=2_000_000,
        audio_max_seconds=120,
        stt_timeout=30,
        stt_hourly_usd=None,
    ):
        self.store, self.agent, self.adapter = store, agent, adapter
        self.agent.memory_store = store
        self.send_enabled = send_enabled
        self.stop = asyncio.Event()
        self.stt = stt
        self.audio_max_bytes, self.audio_max_seconds = audio_max_bytes, audio_max_seconds
        self.stt_timeout, self.stt_hourly_usd = stt_timeout, stt_hourly_usd

    async def normalize_audio(self, event, metrics):
        started = time.monotonic()
        stt_started = None
        try:
            if self.stt is None:
                raise AudioError("stt_disabled")
            reference = json.loads(event["audio_ref"])
            if (
                not 0 <= reference["bytes"] <= self.audio_max_bytes
                or not 0 <= reference["seconds"] <= self.audio_max_seconds
            ):
                raise AudioError("audio_metadata_limit")
            content, mime = await self.adapter.download_audio(
                reference, max_bytes=self.audio_max_bytes
            )
            audio = await asyncio.to_thread(
                validate_audio,
                content,
                mime,
                max_bytes=self.audio_max_bytes,
                max_seconds=self.audio_max_seconds,
            )
            metrics["stt_duration_seconds"] = round(audio.duration, 3)
            stt_started = time.monotonic()
            text = await asyncio.wait_for(self.stt.transcribe(audio), timeout=self.stt_timeout)
            if not isinstance(text, str) or not 1 <= len(text.strip()) <= 4000:
                raise AudioError("empty_or_oversize_transcript")
            if self.stt_hourly_usd:
                metrics["stt_estimated_usd"] = round(
                    max(10, audio.duration) * self.stt_hourly_usd / 3600, 8
                )
            return text.strip()
        finally:
            metrics["audio_latency_ms"] = round((time.monotonic() - started) * 1000, 2)
            metrics["stt_latency_ms"] = (
                round((time.monotonic() - stt_started) * 1000, 2) if stt_started else None
            )

    async def once(self):
        event = await asyncio.to_thread(self.store.claim)
        if event is None:
            return False
        identifier = event["event_id"]
        try:
            if event["state"] == "queued":
                metrics = {"input_type": event.get("input_type", "text")}
                if metrics["input_type"] == "audio":
                    try:
                        event["text"] = await self.normalize_audio(event, metrics)
                    except Exception as exc:  # noqa: BLE001 - sanitized user recovery, no raw media/provider body
                        metrics["audio_failure"] = (
                            str(exc)
                            if isinstance(exc, AudioError)
                            else "stt_timeout"
                            if isinstance(exc, TimeoutError)
                            else "audio_normalization_failed"
                        )
                        await asyncio.to_thread(self.store.record_metrics, identifier, metrics)
                        answer = AssistantResponse(
                            text="Não consegui entender esse áudio. Você consegue mandar de novo ou escrever por aqui?",
                            confidence="insufficient_evidence",
                        )
                        await asyncio.to_thread(
                            self.store.response_ready, identifier, answer.model_dump(mode="json")
                        )
                        return True
                if norm(event["text"]).strip("!.? ") in {
                    "apagar meus dados",
                    "esquecer meus dados",
                }:
                    if metrics["input_type"] == "audio":
                        answer = AssistantResponse(
                            text='Para apagar os dados locais, escreva "Apagar meus dados" por aqui.',
                            confidence="insufficient_evidence",
                        )
                        await asyncio.to_thread(self.store.record_metrics, identifier, metrics)
                        await asyncio.to_thread(
                            self.store.response_ready, identifier, answer.model_dump(mode="json")
                        )
                        return True
                    owners = await asyncio.to_thread(self.store.forget, event["person"])
                    for key in list(self.agent.sessions):
                        if key[0] in owners:
                            self.agent.sessions.pop(key, None)
                            self.agent.locks.pop(key, None)
                    await asyncio.to_thread(self.store.redact_person, event["person"], identifier)
                    answer = AssistantResponse(
                        text="Apaguei seu nome, contexto e oportunidades locais deste atendimento. Podemos começar uma nova conversa quando você quiser.",
                        confidence="insufficient_evidence",
                    )
                    await asyncio.to_thread(
                        self.store.response_ready, identifier, answer.model_dump(mode="json")
                    )
                    return True
                thread = await asyncio.to_thread(
                    self.store.open_thread, event["person"], "whatsapp:" + event["instance"]
                )
                answer = await self.agent.turn(
                    thread["conversation_id"],
                    event["text"],
                    owner=thread["owner"],
                    trusted_contact_phone=event["recipient"],
                    input_type=metrics["input_type"],
                )
                state = self.agent.sessions[(thread["owner"], thread["conversation_id"])]
                if getattr(self.agent, "conversation_v2_enabled", False) and state.get(
                    "suppress_delivery"
                ):
                    await asyncio.to_thread(self.store.finish, identifier, "human_hold")
                    return True
                metrics.update(
                    {
                        "llm_calls": state["usage"]["calls"],
                        "intent": state.get("composition", {}).get("intent"),
                        "action": state["lead_profile"]["next_action"],
                        "composition_origin": state.get("composition", {}).get("origin"),
                        "fallback_reason": state.get("composition", {}).get("fallback_reason"),
                        **{
                            k: state.get("metrics", {}).get(k)
                            for k in (
                                "specialist",
                                "conversation_act",
                                "routing_origin",
                                "routing_failure",
                                "session_status",
                                "commercial_state",
                                "session_reopened",
                                "handoff_status",
                            )
                            if k in state.get("metrics", {})
                        },
                    }
                )
                await asyncio.to_thread(self.store.record_metrics, identifier, metrics)
                await asyncio.to_thread(
                    self.store.response_ready, identifier, answer.model_dump(mode="json")
                )
                return True
            if not self.send_enabled:
                await asyncio.to_thread(self.store.finish, identifier, "dry_run")
                return True
            while part := await asyncio.to_thread(self.store.claim_part, identifier):
                if part["kind"] == "text":
                    answer = AssistantResponse(
                        text=part["content"], confidence="insufficient_evidence"
                    )
                    provider_id = await self.adapter.send_text(event["recipient"], answer)
                else:
                    image = await asyncio.to_thread(approved_image, self.agent, part["content"])
                    provider_id = await self.adapter.send_image(event["recipient"], image)
                await asyncio.to_thread(self.store.part_done, identifier, part["part"], provider_id)
                if part["kind"] == "image" and getattr(
                    self.agent, "conversation_v2_enabled", False
                ):
                    await asyncio.to_thread(
                        self.store.mark_media_delivery,
                        event["person"],
                        "whatsapp:" + event["instance"],
                        part["content"],
                    )
            await asyncio.to_thread(self.store.finish, identifier, "sent")
        except Exception:  # noqa: BLE001 - no raw provider messages, recipients or keys in logs
            if getattr(self.agent, "conversation_v2_enabled", False):
                await asyncio.to_thread(
                    self.store.mark_media_delivery,
                    event["person"],
                    "whatsapp:" + event["instance"],
                    failed=True,
                )
            await asyncio.to_thread(self.store.finish, identifier, "review")
        return True

    async def run(self):
        await asyncio.to_thread(self.store.recover)
        next_cleanup = time.monotonic() + 3600
        while not self.stop.is_set():
            try:
                if time.monotonic() >= next_cleanup:
                    await asyncio.to_thread(self.store.purge_content)
                    next_cleanup = time.monotonic() + 3600
                if await self.once():
                    continue
            except Exception:  # noqa: BLE001 - durable records remain for recovery
                logging.getLogger(__name__).error("whatsapp_worker_storage_unavailable")
            try:
                await asyncio.wait_for(self.stop.wait(), timeout=1)
            except TimeoutError:
                continue
