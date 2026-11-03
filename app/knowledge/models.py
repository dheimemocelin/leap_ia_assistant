"""Evidence-bearing metadata; extraction is never publication approval."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: Literal[
        "manufacturer",
        "model",
        "powertrain",
        "market",
        "model_year",
        "document_type",
        "language",
        "document_version",
        "publication_date",
    ]
    value: str
    page: int = Field(ge=1)
    quote: str = Field(min_length=1, max_length=1000)
    basis: Literal["internal_text", "visual_review"] = "internal_text"


class PageAudit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page: int = Field(ge=1)
    text: str
    alternate_text: str
    issues: list[str]
    review_status: Literal["review_required"] = "review_required"
    quality_metrics: dict[str, float] = Field(default_factory=dict)
    images: int = 0
    extraction_methods: list[str]


class DocumentAudit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_id: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    size_bytes: int
    page_count: int
    files: list[str]
    pdf_metadata: dict[str, str | None]
    candidates: dict[str, list[str]] = Field(default_factory=dict)
    evidence: list[Evidence] = Field(default_factory=list)
    metadata_reviewed_by: str | None = None
    manufacturer: str | None = None
    model: Literal["B10", "C10"] | None = None
    powertrain: Literal["BEV", "REEV"] | None = None
    market: str | None = None
    model_year: int | None = None
    document_type: str | None = None
    language: str | None = None
    document_version: str | None = None
    publication_date: str | None = None
    approval_status: Literal["pending"] = "pending"
    extraction_status: Literal["extracted_unreviewed", "review_required", "failed"]
    issues: list[str]
    pages: list[PageAudit]
    pipeline_version: str
    extractor_versions: dict[str, str]


class MetadataReview(BaseModel):
    """Human/engineer metadata observations, not approval to answer customers."""

    model_config = ConfigDict(extra="forbid")
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    reviewed_by: str = Field(min_length=1, max_length=100)
    evidence: list[Evidence] = Field(min_length=1)
