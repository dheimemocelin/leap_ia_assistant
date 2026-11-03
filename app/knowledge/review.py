"""Explicit append-only decisions for bounded sections; never score-based approval."""

import hashlib
import json
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.knowledge.extraction import text_issues

ReviewStatus = Literal["pending", "review_required", "approved", "rejected"]


class Segment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    segment_id: str
    document_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)
    section_title: str = Field(min_length=1)
    text: str = Field(min_length=1)
    text_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_recovery_key: str
    content_type: Literal["text", "table", "warning"] = "text"
    equipment_condition: Literal["unknown", "conditional", "not_stated"] = "unknown"
    review_status: ReviewStatus = "pending"

    @model_validator(mode="after")
    def integrity(self):
        if self.page_end < self.page_start:
            raise ValueError("Inverted page interval")
        if hashlib.sha256(self.text.encode()).hexdigest() != self.text_sha256:
            raise ValueError("Segment content integrity mismatch")
        if self.segment_id != segment_identifier(
            self.document_sha256, self.page_start, self.page_end, self.text_sha256
        ):
            raise ValueError("Segment identifier mismatch")
        if self.review_status == "approved":
            raise ValueError("Approval requires a separate review event")
        return self


def segment_identifier(document_hash, start, end, content_hash):
    return (
        "seg-"
        + hashlib.sha256(f"{document_hash}:{start}:{end}:{content_hash}".encode()).hexdigest()
    )


def make_segment(document_hash, start, end, title, text, recovery_key, **fields):
    text_hash = hashlib.sha256(text.encode()).hexdigest()
    return Segment(
        segment_id=segment_identifier(document_hash, start, end, text_hash),
        document_sha256=document_hash,
        page_start=start,
        page_end=end,
        section_title=title,
        text=text,
        text_sha256=text_hash,
        source_recovery_key=recovery_key,
        **fields,
    )


class ReviewEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    segment_id: str
    text_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_recovery_key: str
    previous_event_sha256: str | None = None
    status: ReviewStatus
    reviewer: str = Field(min_length=1, max_length=120)
    reviewed_at: datetime
    reason: str = Field(min_length=1, max_length=2000)
    visual_comparison: bool = False
    scope: Literal["text_fidelity_only"] = "text_fidelity_only"

    @model_validator(mode="after")
    def explicit_review(self):
        if self.reviewed_at.tzinfo is None:
            raise ValueError("Review timestamp requires a timezone")
        if self.status == "approved" and not self.visual_comparison:
            raise ValueError("Approval requires recorded comparison with the original page")
        return self


def event_hash(event):
    return hashlib.sha256(
        json.dumps(event.model_dump(mode="json"), sort_keys=True).encode()
    ).hexdigest()


def effective_status(segment, events):
    """Fail closed on a stale decision, altered content, or broken decision chain."""
    segment = Segment.model_validate(segment.model_dump())
    status, previous = segment.review_status, None
    for event in events:
        event = ReviewEvent.model_validate(event.model_dump())
        if event.segment_id != segment.segment_id:
            continue
        if (
            event.text_sha256 != segment.text_sha256
            or event.source_recovery_key != segment.source_recovery_key
            or event.previous_event_sha256 != previous
        ):
            raise ValueError("Stale or broken review chain")
        if event.status == "approved" and any(
            i in text_issues(segment.text)
            for i in (
                "encoding_suspect",
                "fragmented_words",
                "untrusted_instruction_suspect",
                "editorial_translation_artifact",
            )
        ):
            raise ValueError("Unresolved extraction or instruction issue")
        previous, status = event_hash(event), event.status
    return status


def approved_segments(segments, events):
    # This is text-fidelity approval, not runtime authorization or equipment availability.
    return [s for s in segments if effective_status(s, events) == "approved"]


def select_blocks(artifact, page_number, indices, title, **fields):
    """Bind a bounded section to stored source blocks, not newly authored prose."""
    page = artifact["pages"][page_number - 1]
    if page["page"] != page_number or not indices or len(set(indices)) != len(indices):
        raise ValueError("Invalid section block selection")
    if digest_page(page["text"]) != page["text_sha256"]:
        raise ValueError("Recovered page integrity mismatch")
    blocks = [page["blocks"][index] for index in indices]
    text = "\n\n".join(b["text"] for b in blocks)
    return make_segment(
        artifact["config"]["original_sha256"],
        page_number,
        page_number,
        title,
        text,
        artifact["recovery_key"],
        **fields,
    )


def digest_page(text):
    return hashlib.sha256(text.encode()).hexdigest()
