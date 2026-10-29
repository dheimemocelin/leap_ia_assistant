import json

import httpx
import pytest
from pydantic import SecretStr

from app.agent.groq import GroqAdapter, ProviderError
from app.config import Settings


async def test_groq_tool_call_protocol_usage_and_no_network():
    def handler(request):
        assert request.url == "https://api.groq.com/openai/v1/chat/completions"
        body = json.loads(request.content)
        assert body["model"] == "synthetic-model" and body["stream"] is False
        assert body["tools"][0]["function"]["name"] == "list_vehicles"
        assert body["parallel_tool_calls"] is False
        assert request.headers["authorization"] == "Bearer synthetic-key"
        return httpx.Response(
            200,
            json={
                "model": "synthetic-model",
                "choices": [
                    {
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "function": {
                                        "name": "list_vehicles",
                                        "arguments": '{"model":"B10"}',
                                    }
                                }
                            ],
                        }
                    }
                ],
                "usage": {"prompt_tokens": 22, "completion_tokens": 9},
            },
        )

    adapter = GroqAdapter(
        api_key=SecretStr("synthetic-key"),
        model="synthetic-model",
        transport=httpx.MockTransport(handler),
    )
    result = await adapter.complete(
        [{"role": "user", "content": "test"}],
        [{"type": "function", "function": {"name": "list_vehicles"}}],
    )
    assert result.tool_calls[0].arguments == {"model": "B10"}
    assert result.input_tokens == 22 and result.output_tokens == 9
    assert "synthetic-key" not in str(adapter.metrics)


@pytest.mark.parametrize("status", [401, 429, 500])
async def test_provider_errors_are_sanitized_no_retry(status):
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(status, text="DO NOT LOG synthetic-key provider response")

    adapter = GroqAdapter(
        api_key=SecretStr("synthetic-key"),
        model="synthetic-model",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(ProviderError, match=f"^groq_http_{status}$"):
        await adapter.complete([], [])
    assert len(calls) == 1
    assert "synthetic-key" not in str(adapter.metrics)


async def test_invalid_tool_json_and_timeout():
    def malformed(request):
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {
                                    "function": {
                                        "name": "list_vehicles",
                                        "arguments": "synthetic-key",
                                    }
                                }
                            ]
                        }
                    }
                ]
            },
        )

    adapter = GroqAdapter(
        api_key=SecretStr("synthetic-key"),
        model="synthetic-model",
        transport=httpx.MockTransport(malformed),
    )
    with pytest.raises(ProviderError, match="^groq_invalid_response$"):
        await adapter.complete([], [])

    def timeout(request):
        raise httpx.ReadTimeout("synthetic-key")

    adapter.transport = httpx.MockTransport(timeout)
    with pytest.raises(ProviderError, match="^groq_timeout$"):
        await adapter.complete([], [])


def test_secret_setting_is_masked(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "synthetic-key")
    settings = Settings(_env_file=None)
    assert settings.groq_api_key.get_secret_value() == "synthetic-key"
    assert "synthetic-key" not in repr(settings)


async def test_groq_adapter_through_existing_graph_and_policy(tmp_path):
    from test_sales_agent import agent as make_agent

    local = make_agent.__wrapped__(tmp_path)
    requests = []

    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        message = {"content": "Preço R$ 180.000"}
        if body.get("tools"):
            message = {
                "content": None,
                "tool_calls": [{"function": {"name": "list_vehicles", "arguments": "{}"}}],
            }
        return httpx.Response(
            200,
            json={
                "choices": [{"message": message}],
                "usage": {"prompt_tokens": 30, "completion_tokens": 10},
            },
        )

    local.llm = GroqAdapter(
        api_key=SecretStr("synthetic-key"),
        model="synthetic-model",
        transport=httpx.MockTransport(handler),
    )
    result = await local.turn("one", "Quais veículos existem?")
    assert len(requests) == 2
    assert local.sessions[("local", "one")]["usage"]["input_tokens"] == 60
    assert result.handoff_required and "180" not in result.text
    assert len(requests[0]["tools"]) == 3


async def test_groq_error_becomes_handoff_without_provider_payload(tmp_path):
    from test_sales_agent import agent as make_agent

    local = make_agent.__wrapped__(tmp_path)
    local.llm = GroqAdapter(
        api_key=SecretStr("synthetic-key"),
        model="synthetic-model",
        transport=httpx.MockTransport(lambda request: httpx.Response(429, text="synthetic-key")),
    )
    result = await local.turn("one", "Fotos B10 REEV")
    assert result.handoff_required and "synthetic-key" not in result.text
    assert len(local.llm.metrics) == 1
