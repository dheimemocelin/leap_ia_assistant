from datetime import date
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, Field

from app.catalog.models import ApprovalStatus, MediaCategory
from app.catalog.repository import CatalogRepository, approved_vehicles
from app.policy.commercial import model_safe_vehicle


class ToolOutcome(StrEnum):
    OK = "ok"
    NOT_FOUND = "not_found"
    NEEDS_HUMAN = "needs_human"
    BLOCKED = "blocked"


class VehicleFilter(BaseModel):
    model: str | None = None
    powertrain: str | None = None


class VehicleMediaFilter(BaseModel):
    vehicle_id: str
    version: str | None = None
    model_year: int | None = None
    color: str | None = None
    category: MediaCategory | None = None


class LeadData(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=254)
    interested_vehicle_id: str | None = None
    purchase_timeline: str | None = None
    preferred_contact_channel: str | None = None
    city: str | None = Field(default=None, max_length=100)
    consent_to_contact: bool = False


class LeadQualification(BaseModel):
    qualified: bool
    missing_fields: list[str]
    summary: str
    crm_authorized: bool


class SyonetLeadAdapter(Protocol):
    """Adapter must persist/dedupe idempotency_key across retries."""

    def create_lead(self, *, lead: LeadData, idempotency_key: str) -> str: ...


class ConsentVerifier(Protocol):
    def is_valid_for_lead(self, *, consent_id: str, lead: LeadData) -> bool: ...


class HandoffAdapter(Protocol):
    def handoff(self, *, conversation_id: str, reason: str, summary: str) -> str: ...


class SalesTools:
    def __init__(self, catalog: CatalogRepository, today: date | None = None):
        self.catalog = catalog
        self.today = today or date.today()

    def list_vehicles(self, filters: VehicleFilter | None = None) -> list[dict]:
        filters = filters or VehicleFilter()
        results = approved_vehicles(self.catalog)
        if filters.model:
            results = [v for v in results if v.model.casefold() == filters.model.casefold()]
        if filters.powertrain:
            results = [v for v in results if v.powertrain.value.casefold() == filters.powertrain.casefold()]
        return [model_safe_vehicle(v.model_dump(mode="json")) for v in results]

    def get_vehicle_details(self, vehicle_id: str) -> dict | None:
        vehicle = self.catalog.vehicle(vehicle_id)
        if vehicle is None or vehicle.approval_status != ApprovalStatus.APPROVED:
            return None
        return model_safe_vehicle(vehicle.model_dump(mode="json"))

    def search_vehicle_media(self, filters: VehicleMediaFilter) -> list[dict]:
        vehicle = self.catalog.vehicle(filters.vehicle_id)
        if vehicle is None or vehicle.approval_status != ApprovalStatus.APPROVED:
            return []
        results = []
        for media in self.catalog.media():
            if media.vehicle_id != filters.vehicle_id or media.approval_status != ApprovalStatus.APPROVED:
                continue
            if not (media.approved_at and media.approved_by and media.storage_uri):
                continue
            if filters.version and media.version != filters.version:
                continue
            if filters.model_year and media.model_year != filters.model_year:
                continue
            if filters.color and (media.color or "").casefold() != filters.color.casefold():
                continue
            if filters.category and media.category != filters.category:
                continue
            results.append(media.model_dump(mode="json"))
        return results

    def compare_vehicles(self, vehicle_ids: list[str]) -> dict:
        if len(vehicle_ids) < 2 or len(vehicle_ids) > 4:
            raise ValueError("Comparison requires between 2 and 4 vehicle IDs")
        vehicles = [self.get_vehicle_details(vehicle_id) for vehicle_id in vehicle_ids]
        if any(vehicle is None for vehicle in vehicles):
            return {"outcome": ToolOutcome.NOT_FOUND, "vehicles": []}
        return {"outcome": ToolOutcome.OK, "vehicles": vehicles}

    @staticmethod
    def qualify_lead(lead: LeadData) -> LeadQualification:
        required = {"name": lead.name, "phone": lead.phone, "interested_vehicle_id": lead.interested_vehicle_id}
        missing = [key for key, value in required.items() if not value]
        return LeadQualification(
            qualified=not missing,
            missing_fields=missing,
            summary=f"Interesse em {lead.interested_vehicle_id or 'veículo não especificado'}",
            crm_authorized=not missing and lead.consent_to_contact,
        )

    @classmethod
    def create_syonet_lead(
        cls,
        lead: LeadData,
        *,
        consent_id: str | None,
        idempotency_key: str | None,
        adapter: SyonetLeadAdapter | None,
        consent_verifier: ConsentVerifier | None,
    ) -> dict:
        qualification = cls.qualify_lead(lead)
        if not qualification.qualified:
            return {"outcome": ToolOutcome.BLOCKED, "reason": "missing_required_fields", "missing_fields": qualification.missing_fields}
        if not lead.consent_to_contact or not consent_id or consent_verifier is None:
            return {"outcome": ToolOutcome.BLOCKED, "reason": "consent_required"}
        if not consent_verifier.is_valid_for_lead(consent_id=consent_id, lead=lead):
            return {"outcome": ToolOutcome.BLOCKED, "reason": "consent_invalid_or_revoked"}
        if not idempotency_key:
            return {"outcome": ToolOutcome.BLOCKED, "reason": "idempotency_key_required"}
        if adapter is None:
            return {"outcome": ToolOutcome.BLOCKED, "reason": "syonet_not_configured"}
        crm_id = adapter.create_lead(lead=lead, idempotency_key=idempotency_key)
        return {"outcome": ToolOutcome.OK, "crm_id": crm_id}

    @staticmethod
    def handoff_to_human(
        *, conversation_id: str, reason: str, summary: str, adapter: HandoffAdapter | None
    ) -> dict:
        if not adapter:
            return {"outcome": ToolOutcome.NEEDS_HUMAN, "reason": "handoff_adapter_not_configured"}
        handoff_id = adapter.handoff(conversation_id=conversation_id, reason=reason, summary=summary)
        return {"outcome": ToolOutcome.OK, "handoff_id": handoff_id}
