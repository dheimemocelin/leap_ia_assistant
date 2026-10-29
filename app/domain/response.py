import re
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator

from app.policy.commercial import CommercialPolicyEngine, PolicyDecision


class Confidence(StrEnum):
    GROUNDED = "grounded"
    INSUFFICIENT = "insufficient_evidence"


class AssistantResponse(BaseModel):
    """A reply must cite versioned source IDs or explicitly abstain."""

    model_config = ConfigDict(frozen=True, extra="forbid", revalidate_instances="always")

    text: str = Field(min_length=1, max_length=4000)
    confidence: Confidence
    source_ids: list[str] = Field(default_factory=list, max_length=10)
    handoff_required: bool = False

    @classmethod
    def validated(cls, **values: object) -> "AssistantResponse":
        return cls(**values)

    @model_validator(mode="before")
    @classmethod
    def enforce_policy(cls, values):
        if isinstance(values, dict) and (
            isinstance(values.get("text"), str)
            and not CommercialPolicyEngine().validate_output(values["text"])
            or any(
                not isinstance(item, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,200}", item)
                for item in (values.get("source_ids") or [])
            )
        ):
            return {
                "text": CommercialPolicyEngine.safe_response(PolicyDecision.REFUSE_FINANCIAL),
                "confidence": Confidence.INSUFFICIENT,
                "source_ids": [],
                "handoff_required": True,
            }
        return values

    @model_serializer(mode="wrap")
    def serialize_safely(self, handler):
        # model_construct/model_copy are trusted Pydantic APIs which bypass validation.
        # Recheck on serialization as well as at the HTTP boundary.
        data = handler(self)
        return self.enforce_policy(data)

    def model_post_init(self, __context: object, /) -> None:
        if self.confidence == Confidence.GROUNDED and not self.source_ids:
            raise ValueError("Grounded responses require at least one source id")
        if self.confidence == Confidence.INSUFFICIENT and self.source_ids:
            raise ValueError("Abstentions cannot cite unsupported source ids")
