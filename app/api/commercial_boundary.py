"""Fail-closed HTTP boundary for all current/future customer routes under /v1/."""

import json

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.domain.response import AssistantResponse, Confidence
from app.policy.commercial import CommercialPolicyEngine, PolicyDecision


def fallback_response(status_code=200):
    return JSONResponse(
        {
            "text": CommercialPolicyEngine.safe_response(PolicyDecision.REFUSE_FINANCIAL),
            "confidence": Confidence.INSUFFICIENT,
            "source_ids": [],
            "handoff_required": True,
        },
        status_code=status_code,
    )


class CommercialOutputBoundary(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if not request.url.path.startswith("/v1/"):
            return await call_next(request)
        try:
            response = await call_next(request)
            if response.status_code >= 400:
                return fallback_response(response.status_code)
            if response.headers.get("content-type", "").split(";")[0] != "application/json":
                # No token is released until a complete response can be validated.
                return fallback_response()
            body = bytearray()
            async for chunk in response.body_iterator:
                body.extend(chunk)
                if len(body) > 65536:
                    return fallback_response()
            candidate = AssistantResponse.model_validate(json.loads(body))
            return JSONResponse(candidate.model_dump(mode="json"), status_code=response.status_code)
        except Exception:  # noqa: BLE001 - last HTTP boundary must sanitize all application errors
            # Never expose exception text or unvalidated tool results.
            return fallback_response(500)
