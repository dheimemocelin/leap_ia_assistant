import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.testclient import TestClient

from app.domain.response import AssistantResponse, Confidence
from app.policy.commercial import model_safe_vehicle


@pytest.mark.parametrize("factory", [AssistantResponse, AssistantResponse.model_validate])
def test_normal_response_cannot_bypass_policy(factory):
    values = {"text": "Preço R$ 180.000", "confidence": "insufficient_evidence"}
    response = factory(values) if factory == AssistantResponse.model_validate else factory(**values)
    assert "180.000" not in response.model_dump_json()
    assert response.handoff_required


def test_projection_blocks_nested_financial_fields_and_lists():
    original = {
        "id": "c10-bev",
        "specifications": {"range_km": 338, "price": 180000, "nested": [{"discount": 1000}]},
        "features": ["R$ 180.000"],
        "sources": [{"notes": "Parcela R$ 2.000"}],
    }
    safe = model_safe_vehicle(original)
    assert safe["specifications"] == {"range_km": 338}
    assert "180000" not in str(safe) and "R$" not in str(safe)
    assert original["specifications"]["price"] == 180000


def test_http_boundary_normal_tools_errors_and_future_streaming():
    from app.api.commercial_boundary import CommercialOutputBoundary

    app = FastAPI()
    app.add_middleware(CommercialOutputBoundary)

    @app.get("/v1/normal")
    def normal():
        return {"text": "Conheça os veículos.", "confidence": "insufficient_evidence"}

    @app.get("/v1/financial")
    def financial():
        return {"text": "Preço R$ 180.000", "confidence": "insufficient_evidence"}

    @app.get("/v1/tool")
    def tool():
        return {"result": {"nested": [{"price": 180000}]}}

    @app.get("/v1/error")
    def error():
        return JSONResponse({"detail": "Preço R$ 180.000"}, status_code=400)

    @app.get("/v1/exception")
    def exception():
        raise ValueError("Preço R$ 180.000")

    @app.get("/v1/stream")
    def stream():
        return StreamingResponse(iter(["Preço R$", " 180.000"]), media_type="text/event-stream")

    client = TestClient(app)
    assert client.get("/v1/normal").json()["text"] == "Conheça os veículos."
    for path in ["financial", "tool", "error", "exception", "stream"]:
        response = client.get("/v1/" + path)
        assert "180" not in response.text
        assert not response.json()["handoff_required"]
        assert "consultor" not in response.json()["text"]


def test_unvalidated_copy_is_checked_on_serialization():
    response = AssistantResponse.model_construct(
        text="Preço R$ 180.000",
        confidence=Confidence.INSUFFICIENT,
        source_ids=[],
        handoff_required=False,
    )
    assert "180.000" not in response.model_dump_json()


def test_recursive_technical_lists_drop_unknown_fields():
    payload = {
        "specifications": {
            "motors": [
                {"power_kw": 160, "price": 1000, "motor": {"torque_nm": 300, "installment": 100}}
            ]
        }
    }
    assert model_safe_vehicle(payload)["specifications"] == {
        "motors": [{"power_kw": 160, "motor": {"torque_nm": 300}}]
    }


def test_financial_source_metadata_cannot_leak():
    response = AssistantResponse(
        text="Conheça os veículos.", confidence="grounded", source_ids=["Preço R$ 180.000"]
    )
    assert "180.000" not in response.model_dump_json()
    assert response.handoff_required
