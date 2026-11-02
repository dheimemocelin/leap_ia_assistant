import asyncio
import hashlib
import logging
from pathlib import Path

from app.catalog.media_library import MediaSearchQuery, norm
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
    def __init__(self, store, agent, adapter, *, send_enabled=False):
        self.store, self.agent, self.adapter = store, agent, adapter
        self.agent.memory_store = store
        self.send_enabled = send_enabled
        self.stop = asyncio.Event()

    async def once(self):
        event = await asyncio.to_thread(self.store.claim)
        if event is None:
            return False
        identifier = event["event_id"]
        try:
            if event["state"] == "queued":
                if norm(event["text"]).strip("!.? ") in {
                    "apagar meus dados",
                    "esquecer meus dados",
                }:
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
                )
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
            await asyncio.to_thread(self.store.finish, identifier, "sent")
        except Exception:  # noqa: BLE001 - no raw provider messages, recipients or keys in logs
            await asyncio.to_thread(self.store.finish, identifier, "review")
        return True

    async def run(self):
        await asyncio.to_thread(self.store.recover)
        while not self.stop.is_set():
            try:
                if await self.once():
                    continue
            except Exception:  # noqa: BLE001 - durable records remain for recovery
                logging.getLogger(__name__).error("whatsapp_worker_storage_unavailable")
            try:
                await asyncio.wait_for(self.stop.wait(), timeout=1)
            except TimeoutError:
                continue
