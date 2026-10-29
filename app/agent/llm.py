"""Provider-neutral port and opt-in local Ollama HTTP adapter."""

from typing import Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field


class ToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    arguments: dict = Field(default_factory=dict)


class ModelReply(BaseModel):
    text: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list, max_length=3)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)


class LLMAdapter(Protocol):
    async def complete(self, messages: list[dict], tools: list[dict]) -> ModelReply: ...


class DisabledLLM:
    async def complete(self, messages, tools):
        raise RuntimeError("LLM is disabled")


class OllamaAdapter:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout: float = 15,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        if not model:
            raise ValueError("LLM model is required")
        self.transport = transport
        self.base_url, self.model, self.timeout = base_url.rstrip("/"), model, timeout

    async def complete(self, messages, tools):
        async with httpx.AsyncClient(
            timeout=self.timeout, trust_env=False, transport=self.transport
        ) as client:
            response = await client.post(
                self.base_url + "/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "tools": tools,
                    "stream": False,
                    "options": {"num_predict": 300, "temperature": 0},
                },
            )
            response.raise_for_status()
            payload = response.json()
        message = payload["message"]
        return ModelReply(
            text=message.get("content", ""),
            tool_calls=[
                ToolCall(name=c["function"]["name"], arguments=c["function"].get("arguments", {}))
                for c in message.get("tool_calls", [])
            ],
            input_tokens=payload.get("prompt_eval_count"),
            output_tokens=payload.get("eval_count"),
        )
