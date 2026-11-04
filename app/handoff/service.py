"""Durable, consent-scoped handoff. Adapters have no LLM-controlled destinations."""

import asyncio
import hashlib
import re
from datetime import datetime
from enum import StrEnum
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DeliveryStatus(StrEnum):
    PREPARED = "prepared"
    QUEUED = "queued"
    DELIVERED = "delivered"
    FAILED = "failed"
    ACKNOWLEDGED = "acknowledged"


class HandoffContract(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    opportunity_id: str
    idempotency_key: str
    model: str | None
    powertrain: Literal["BEV", "REEV"] | None
    vehicle_id: str | None
    needs: list[str] = Field(default_factory=list)
    usage: str | None = None
    reason: Literal["customer_requested", "offer_accepted"]
    summary: str
    consent: Literal["granted", "revoked"]
    consent_at: datetime
    consent_scope: str
    name: str | None = Field(default=None, min_length=1, max_length=100)
    phone: str | None = Field(default=None, pattern=r"^\d{10,15}$")
    status: DeliveryStatus = DeliveryStatus.PREPARED
    external_id: str | None = None
    failure_code: str | None = None


class DeliveryReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["queued", "delivered", "failed"]
    external_id: str | None = None

    @model_validator(mode="after")
    def require_receipt_id(self):
        if self.status == "delivered" and not self.external_id:
            raise ValueError("Delivery requires an external receipt ID")
        return self


class HandoffDispatcher(Protocol):
    """A server-selected adapter, never a URL/tool selected by the model."""

    async def dispatch(self, handoff: HandoffContract) -> DeliveryReceipt: ...


class LocalHandoffDispatcher:
    """Local queue only. This is not proof that a salesperson received anything."""

    async def dispatch(self, handoff):
        return DeliveryReceipt(status="queued")


class HandoffService:
    def __init__(self, store, dispatcher: HandoffDispatcher | None = None, *, timeout=5):
        self.store, self.dispatcher, self.timeout = store, dispatcher, timeout

    async def submit(self, owner, conversation_id, profile):
        # Verify the actual durable state as well as the caller's snapshot.
        persisted = self.store.load_state(owner, conversation_id).get("lead_profile", {})
        for p in (persisted, profile):
            if (
                p.get("consent") != "granted"
                or not p.get("consent_at")
                or not p.get("consent_scope")
            ):
                raise ValueError("Consent required")
            if not {"human_contact_requested", "handoff_offer_accepted"}.intersection(
                p.get("signals", [])
            ):
                raise ValueError("Customer authorization required")
            if not p.get("handoff_summary"):
                raise ValueError("Authorized summary required")
            if not p.get("contact_name") or not re.fullmatch(
                r"\d{10,15}", p.get("contact_phone") or ""
            ):
                raise ValueError("Minimum authorized contact required")
        if any(
            persisted.get(k) != profile.get(k)
            for k in ("consent_at", "consent_scope", "vehicle_id", "contact_name", "contact_phone")
        ):
            raise ValueError("Consent snapshot mismatch")
        scope = f"{profile.get('interest_model') or 'unspecified'}:{profile.get('powertrain') or 'unspecified'}"
        if profile["consent_scope"] != scope:
            raise ValueError("Consent scope mismatch")
        key = hashlib.sha256(
            f"{owner}:{conversation_id}:{profile['consent_at']}".encode()
        ).hexdigest()
        opportunity_id = hashlib.sha256(f"{owner}:{conversation_id}".encode()).hexdigest()[:32]
        record = HandoffContract(
            id="handoff-" + key[:32],
            opportunity_id=opportunity_id,
            idempotency_key=key,
            model=profile.get("interest_model"),
            powertrain=profile.get("powertrain"),
            vehicle_id=profile.get("vehicle_id"),
            needs=profile.get("needs", []),
            usage=profile.get("usage"),
            reason="customer_requested"
            if "human_contact_requested" in profile["signals"]
            else "offer_accepted",
            summary="; ".join(
                x
                for x in [
                    profile.get("interest_model"),
                    profile.get("powertrain"),
                    profile.get("usage"),
                    *profile.get("needs", []),
                ]
                if x
            )[:600]
            or "Pedido explícito de continuidade comercial.",
            consent="granted",
            consent_at=profile["consent_at"],
            consent_scope=scope,
            name=profile["contact_name"],
            phone=profile["contact_phone"],
        )
        saved = self.store.prepare_handoff(owner, conversation_id, record.model_dump(mode="json"))
        if self.dispatcher is not None and self.store.claim_handoff(saved["id"]):
            try:
                receipt = DeliveryReceipt.model_validate(
                    await asyncio.wait_for(
                        self.dispatcher.dispatch(HandoffContract.model_validate(saved)),
                        self.timeout,
                    )
                )
                self.store.update_handoff(
                    saved["id"], receipt.status, external_id=receipt.external_id
                )
            except Exception:  # noqa: BLE001 - no adapter response, contact or exception body logged
                self.store.update_handoff(
                    saved["id"], "failed", failure_code="dispatch_unconfirmed"
                )
        return HandoffContract.model_validate(self.store.get_handoff(saved["id"]))
