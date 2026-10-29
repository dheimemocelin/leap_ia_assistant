from enum import StrEnum

from pydantic import BaseModel, Field


class Confidence(StrEnum):
    GROUNDED = "grounded"
    INSUFFICIENT = "insufficient_evidence"


class AssistantResponse(BaseModel):
    """A reply must cite versioned source IDs or explicitly abstain."""

    text: str = Field(min_length=1, max_length=4000)
    confidence: Confidence
    source_ids: list[str] = Field(default_factory=list, max_length=10)
    handoff_required: bool = False

    def model_post_init(self, __context: object, /) -> None:
        if self.confidence == Confidence.GROUNDED and not self.source_ids:
            raise ValueError("Grounded responses require at least one source id")
        if self.confidence == Confidence.INSUFFICIENT and self.source_ids:
            raise ValueError("Abstentions cannot cite unsupported source ids")
