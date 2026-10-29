from datetime import date, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl, model_validator


class ApprovalStatus(StrEnum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class Powertrain(StrEnum):
    BEV = "BEV"
    REEV = "REEV"


class MediaCategory(StrEnum):
    EXTERIOR = "exterior"
    INTERIOR = "interior"
    DASHBOARD = "dashboard"
    TRUNK = "trunk"
    DETAIL = "detail"


class SourceRecord(BaseModel):
    url: HttpUrl
    retrieved_at: datetime
    source_type: str = "official_website"
    notes: str | None = None


class VehicleVersion(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    model: str
    version: str
    model_year: int | None = Field(default=None, ge=2000, le=2100)
    powertrain: Powertrain
    specifications: dict[str, Any] = Field(default_factory=dict)
    features: list[str] = Field(default_factory=list)
    standard_equipment: list[str] = Field(default_factory=list)
    colors: list[str] = Field(default_factory=list)
    sources: list[SourceRecord] = Field(min_length=1)
    updated_at: datetime
    approval_status: ApprovalStatus = ApprovalStatus.DRAFT
    approved_at: datetime | None = None
    approved_by: str | None = None

    @model_validator(mode="after")
    def approval_requires_auditor(self) -> "VehicleVersion":
        if self.approval_status == ApprovalStatus.APPROVED and not (self.approved_at and self.approved_by):
            raise ValueError("Approved catalog entries require approver and timestamp")
        return self


class VehicleMedia(BaseModel):
    id: str
    vehicle_id: str
    version: str | None = None
    model_year: int | None = Field(default=None, ge=2000, le=2100)
    color: str | None = None
    category: MediaCategory
    source_url: HttpUrl | None = None
    storage_uri: str | None = None
    asset_path: str | None = None
    sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    mime_type: str | None = None
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    subcategory: str | None = None
    source_type: str | None = None
    usage_rights_status: str = "pending_confirmation"
    model_confirmation: str | None = None
    tags: list[str] = Field(default_factory=list)
    rights_basis: str
    provenance: str
    retrieved_at: datetime
    approval_status: ApprovalStatus = ApprovalStatus.DRAFT
    approved_at: datetime | None = None
    approved_by: str | None = None

    @model_validator(mode="after")
    def approval_requires_auditor(self) -> "VehicleMedia":
        if self.approval_status == ApprovalStatus.APPROVED:
            if not (self.approved_at and self.approved_by and self.storage_uri):
                raise ValueError("Approved media requires approver, timestamp, and stored asset")
            if self.usage_rights_status != "approved":
                raise ValueError("Approved media requires usage rights approval")
        return self


class CommercialOffer(BaseModel):
    id: str
    vehicle_id: str
    audience: str | None = None
    amount_brl: int = Field(gt=0)
    valid_from: date
    valid_until: date
    source: SourceRecord
    approval_status: ApprovalStatus = ApprovalStatus.PENDING_REVIEW
    approved_at: datetime | None = None
    approved_by: str | None = None

    @model_validator(mode="after")
    def validate_offer(self) -> "CommercialOffer":
        if self.valid_until < self.valid_from:
            raise ValueError("Offer validity interval is inverted")
        if self.approval_status == ApprovalStatus.APPROVED and not (self.approved_at and self.approved_by):
            raise ValueError("Approved offers require approver and timestamp")
        return self
