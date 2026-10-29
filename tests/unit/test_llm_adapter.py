import httpx
import pytest

from app.agent.llm import OllamaAdapter


async def test_ollama_tool_protocol_without_network():
    def handler(request):
        import json

        body = json.loads(request.content)
        assert body["stream"] is False and body["model"] == "synthetic-model"
        assert body["tools"][0]["function"]["name"] == "list_vehicles"
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": "",
                    "tool_calls": [
                        {"function": {"name": "list_vehicles", "arguments": {"model": "B10"}}}
                    ],
                },
                "prompt_eval_count": 12,
                "eval_count": 8,
            },
        )

    adapter = OllamaAdapter(
        base_url="http://local.invalid",
        model="synthetic-model",
        transport=httpx.MockTransport(handler),
    )
    result = await adapter.complete(
        [{"role": "user", "content": "Olá"}],
        [{"type": "function", "function": {"name": "list_vehicles"}}],
    )
    assert result.tool_calls[0].arguments == {"model": "B10"}
    assert result.input_tokens == 12 and result.output_tokens == 8


def test_model_configuration_required():
    with pytest.raises(ValueError):
        OllamaAdapter(base_url="http://local.invalid", model="")
