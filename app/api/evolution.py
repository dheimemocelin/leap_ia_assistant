"""Authenticated durable inbox. WhatsApp participants never log in to LEAP."""

import asyncio
import json
import secrets
import sqlite3
from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from app.channels.evolution import parse_message, private_id
from app.channels.evolution_store import EvolutionStore
from app.config import settings

router = APIRouter()


def configuration_ready():
    return (
        settings.evolution_enabled
        and settings.pilot_db_path
        and settings.evolution_api_key.get_secret_value()
        and settings.evolution_instance
        and len(settings.evolution_webhook_secret.get_secret_value()) >= 32
        and len(settings.evolution_identity_key.get_secret_value()) >= 32
    )


def repository(request):
    if not hasattr(request.app.state, "evolution_store"):
        request.app.state.evolution_store = EvolutionStore(settings.pilot_db_path)
    return request.app.state.evolution_store


class WebhookAck(BaseModel):
    status: Literal["queued", "duplicate", "ignored"]


@router.post("/hooks/evolution/{instance}", response_model=WebhookAck)
async def inbound(instance: str, request: Request, x_webhook_secret: str = Header(default="")):
    if not configuration_ready():
        raise HTTPException(503, "WhatsApp pilot not configured")
    if not secrets.compare_digest(
        x_webhook_secret, settings.evolution_webhook_secret.get_secret_value()
    ):
        raise HTTPException(401, "Unauthorized")
    if instance != settings.evolution_instance:
        raise HTTPException(404, "Unknown instance")
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 65536:
            raise HTTPException(413, "Event too large")
    try:
        payload = json.loads(body)
    except (ValueError, UnicodeError):
        raise HTTPException(400, "Invalid event") from None
    if not isinstance(payload, dict):
        raise HTTPException(400, "Invalid event")
    message = parse_message(payload, instance)
    allowed = {n.strip() for n in settings.evolution_allowed_numbers.split(",") if n.strip()}
    if message is None or ("*" not in allowed and message.recipient not in allowed):
        return {"status": "ignored"}
    if message.input_type == "audio" and not settings.evolution_audio_enabled:
        return {"status": "ignored"}
    key = settings.evolution_identity_key.get_secret_value()
    person = private_id(key, "person:" + instance + ":" + message.recipient)
    event = private_id(key, "message:" + instance + ":" + message.message_id)
    try:
        accepted = await asyncio.to_thread(
            repository(request).enqueue,
            event,
            person,
            instance,
            message.recipient,
            message.text,
            message.input_type,
            message.audio,
        )
    except ValueError:
        raise HTTPException(429, "Pilot message limit reached") from None
    except (sqlite3.Error, OSError):
        raise HTTPException(503, "Inbox unavailable") from None
    return {"status": "queued" if accepted else "duplicate"}
