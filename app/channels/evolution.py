"""Evolution v2 contract: inbound-only destinations, no model-controlled actions."""

import asyncio
import hashlib
import hmac
import re
from dataclasses import dataclass
from urllib.parse import quote, urlsplit

import httpx

from app.domain.response import AssistantResponse


@dataclass(frozen=True)
class IncomingMessage:
    message_id: str
    recipient: str
    text: str


def parse_message(payload: dict, instance: str) -> IncomingMessage | None:
    if (
        payload.get("instance") != instance
        or str(payload.get("event", "")).lower().replace("_", ".") != "messages.upsert"
    ):
        return None
    data = payload.get("data")
    if not isinstance(data, dict) or data.get("type", "notify") != "notify":
        return None
    key = data.get("key", {})
    if not isinstance(key, dict) or key.get("fromMe") is not False:
        return None
    # Prefer the phone alias when Baileys supplies an @lid primary identifier.
    jid = key.get("remoteJid", "")
    if isinstance(jid, str) and jid.endswith("@lid"):
        jid = key.get("remoteJidAlt", "")
    if not isinstance(jid, str) or not re.fullmatch(r"[0-9]{8,15}@s\.whatsapp\.net", jid):
        return None
    message = data.get("message", {})
    if not isinstance(message, dict):
        return None
    text = message.get("conversation")
    if text is None:
        extended = message.get("extendedTextMessage", {})
        text = extended.get("text") if isinstance(extended, dict) else None
    identifier = key.get("id")
    if (
        not isinstance(identifier, str)
        or not 1 <= len(identifier) <= 200
        or not isinstance(text, str)
        or not 1 <= len(text.strip()) <= 4000
    ):
        return None
    return IncomingMessage(identifier, jid.split("@")[0], text.strip())


def private_id(secret: str, value: str) -> str:
    return hmac.new(secret.encode(), value.encode(), hashlib.sha256).hexdigest()


class DeliveryError(Exception):
    """Sanitized and intentionally ambiguous: never replay uncertain delivery."""


class EvolutionAdapter:
    def __init__(self, base_url, api_key, instance, *, transport=None, timeout=15):
        parts = urlsplit(base_url)
        if (
            parts.username
            or parts.password
            or parts.query
            or parts.fragment
            or not parts.netloc
            or (
                parts.scheme != "https"
                and not (
                    parts.scheme == "http"
                    and parts.hostname in {"127.0.0.1", "localhost", "host.docker.internal"}
                )
            )
        ):
            raise ValueError("Invalid Evolution endpoint")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", instance) or not api_key:
            raise ValueError("Invalid Evolution configuration")
        self.url, self.key, self.instance = base_url.rstrip("/"), api_key, instance
        self.transport, self.timeout = transport, timeout

    async def _post(self, action, **payload):
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(
                    transport=self.transport,
                    timeout=self.timeout,
                    follow_redirects=False,
                    trust_env=False,
                ) as client:
                    result = await client.post(
                        f"{self.url}/message/{action}/{quote(self.instance, safe='')}",
                        headers={"apikey": self.key},
                        **payload,
                    )
                if result.status_code == 429 and attempt < 2:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                if not 200 <= result.status_code < 300:
                    raise DeliveryError("provider_delivery_unconfirmed")
                data = result.json()
                message_id = data.get("key", {}).get("id") if isinstance(data, dict) else None
                if not isinstance(message_id, str) or not message_id:
                    raise DeliveryError("provider_delivery_unconfirmed")
                return message_id
            except httpx.ConnectError:
                if attempt < 2:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                raise DeliveryError("provider_unreachable") from None
            except (httpx.HTTPError, ValueError):
                raise DeliveryError("provider_delivery_unconfirmed") from None
        raise DeliveryError("provider_delivery_unconfirmed")

    async def send_text(self, recipient, response: AssistantResponse):
        if not re.fullmatch(r"[0-9]{8,15}", recipient):
            raise ValueError("Invalid recipient")
        safe = AssistantResponse.model_validate(response.model_dump(mode="json"))
        return await self._post(
            "sendText", json={"number": recipient, "text": safe.text, "linkPreview": False}
        )

    async def send_image(self, recipient, content: bytes):
        if not re.fullmatch(r"[0-9]{8,15}", recipient):
            raise ValueError("Invalid recipient")
        return await self._post(
            "sendMedia",
            data={"number": recipient, "mediatype": "image", "mimetype": "image/jpeg"},
            files={"file": ("vehicle.jpeg", content, "image/jpeg")},
        )
