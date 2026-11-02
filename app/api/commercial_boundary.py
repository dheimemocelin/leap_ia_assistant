"""Fail-closed HTTP boundary for all current/future customer routes under /v1/."""

import json

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.domain.response import AssistantResponse, Confidence


def fallback_response(status_code=200):
    return JSONResponse(
        {
            "text": "Não consegui concluir essa resposta agora. Você pode tentar novamente por aqui.",
            "confidence": Confidence.INSUFFICIENT,
            "source_ids": [],
            "media_ids": [],
            "handoff_required": False,
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
            original = json.loads(body)
            candidate = AssistantResponse.model_validate(original)
            if candidate.text != original.get("text"):
                # A policy replacement is not customer consent to human contact.
                return fallback_response(response.status_code)
            return JSONResponse(candidate.model_dump(mode="json"), status_code=response.status_code)
        except Exception:  # noqa: BLE001 - last HTTP boundary must sanitize all application errors
            # Never expose exception text or unvalidated tool results.
            return fallback_response(500)
