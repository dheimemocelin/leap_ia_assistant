"""Groq chat-completions adapter; no SDK, retries, prompts or credentials in telemetry."""

import json
import re
import time
from collections import deque

import httpx
from pydantic import SecretStr

from app.agent.llm import LLMProviderError, ModelReply, ToolCall


class ProviderError(LLMProviderError):
    pass


class GroqAdapter:
    def __init__(
        self,
        *,
        api_key: SecretStr,
        model: str,
        timeout: float = 15,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        if not api_key.get_secret_value():
            raise ValueError("GROQ_API_KEY required")
        if not re.fullmatch(r"[A-Za-z0-9_./:-]+", model):
            raise ValueError("Invalid LLM model identifier")
        self._api_key = api_key
        self.model, self.timeout, self.transport = model, timeout, transport
        self.metrics = deque(maxlen=32)

    async def complete(self, messages, tools):
        started = time.monotonic()
        metric = {
            "model_requested": self.model,
            "http_status": None,
            "input_tokens": None,
            "output_tokens": None,
            "outcome": "error",
        }
        try:
            body = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "temperature": 0,
                "max_completion_tokens": 512,
            }
            if tools:
                body.update(tools=tools, tool_choice="auto", parallel_tool_calls=False)
            async with httpx.AsyncClient(
                timeout=self.timeout, trust_env=False, transport=self.transport
            ) as client:
                response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": "Bearer " + self._api_key.get_secret_value()},
                    json=body,
                )
            metric["http_status"] = response.status_code
            if response.status_code != 200:
                raise ProviderError(f"groq_http_{response.status_code}")
            payload = response.json()
            message = payload["choices"][0]["message"]
            result = ModelReply(
                text=message.get("content") or "",
                tool_calls=[
                    ToolCall(
                        name=call["function"]["name"],
                        arguments=json.loads(call["function"]["arguments"]),
                    )
                    for call in message.get("tool_calls", [])
                ],
                input_tokens=payload.get("usage", {}).get("prompt_tokens"),
                output_tokens=payload.get("usage", {}).get("completion_tokens"),
            )
            effective_model = payload.get("model", self.model)
            if not isinstance(effective_model, str) or not re.fullmatch(
                r"[A-Za-z0-9_./:-]+", effective_model
            ):
                raise ValueError("Invalid model metadata")
            metric.update(
                model_effective=effective_model,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                outcome="ok",
                tool_calls=len(result.tool_calls),
            )
            return result
        except httpx.TimeoutException:
            raise ProviderError("groq_timeout") from None
        except httpx.RequestError:
            raise ProviderError("groq_connection_error") from None
        except (ValueError, KeyError, IndexError, TypeError):
            raise ProviderError("groq_invalid_response") from None
        finally:
            metric["latency_ms"] = round((time.monotonic() - started) * 1000, 2)
            self.metrics.append(metric)
