import argparse

parser = argparse.ArgumentParser(
    description="Opt-in: up to six paid Groq calls using internally reviewed public facts"
)
parser.add_argument("--allow-real-groq", action="store_true")
if not parser.parse_args().allow_real_groq:
    parser.error("Explicit --allow-real-groq required; no network call performed")
import json
import secrets
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from fastapi.testclient import TestClient

from app.agent.groq import GroqAdapter
from app.agent.grounding import GroundingPolicy, ReviewedFact
from app.agent.service import SalesAgent
from app.catalog.loader import load_catalog
from app.catalog.media_library import VehicleMediaLibrary
from app.config import settings
from app.main import app
from app.policy.commercial import CommercialPolicyEngine

root = Path("data/validation/grounding")
catalog = load_catalog(root)
facts = [ReviewedFact.model_validate(f) for f in json.loads((root / "facts.json").read_text())]
assert settings.groq_api_key.get_secret_value()
assert settings.llm_model == "openai/gpt-oss-20b"
llm = GroqAdapter(api_key=settings.groq_api_key, model=settings.llm_model, timeout=20)


class Budget:
    def __init__(self):
        self.calls = 0

    async def complete(self, messages, tools):
        if self.calls >= 6:
            raise RuntimeError("Real smoke budget exhausted")
        self.calls += 1
        return await llm.complete(messages, tools)


budget = Budget()
agent = SalesAgent(
    catalog,
    VehicleMediaLibrary([], vehicles=catalog.vehicles(), asset_root=Path("assets/media")),
    budget,
    grounding=GroundingPolicy(facts, catalog),
    prefer_tool_calling=True,
    timeout=20,
)
original = settings.app_api_key
if not settings.app_api_key:
    settings.app_api_key = secrets.token_urlsafe(32)
token = secrets.token_urlsafe(32)
import hashlib

owner = hashlib.sha256(token.encode()).hexdigest()
headers = {"Authorization": "Bearer " + settings.app_api_key, "X-Session-Token": token}
app.state.sales_agent = agent
results = []
try:
    with TestClient(app) as client:
        for i, question in enumerate(
            [
                "Qual a autonomia do C10 BEV no ciclo PBEV?",
                "Qual a capacidade da bateria do B10 BEV?",
                "Qual o preço do C10 BEV? Podemos negociar desconto?",
            ],
            1,
        ):
            before = len(llm.metrics)
            start = time.monotonic()
            r = client.post(
                f"/v1/conversations/grounding-{i}/messages",
                json={"text": question},
                headers=headers,
            )
            answer = r.json()
            events = agent.sessions.get((owner, f"grounding-{i}"), {}).get("tool_events", [])
            known = {f.source_id for f in facts}
            results.append(
                {
                    "case": i,
                    "question": question,
                    "http_status": r.status_code,
                    "response": answer,
                    "latency_ms": round((time.monotonic() - start) * 1000, 2),
                    "provider_metrics": list(llm.metrics)[before:],
                    "tool_events": events,
                    "policy_valid": CommercialPolicyEngine().validate_output(
                        answer.get("text", "")
                    ),
                    "exact_reviewed_fact": answer.get("text") == facts[0].statement,
                    "sources_resolve": set(answer.get("source_ids", [])).issubset(known),
                }
            )
finally:
    settings.app_api_key = original
    del app.state.sales_agent
out = {
    "model": settings.llm_model,
    "maximum_provider_calls": 6,
    "actual_provider_calls": budget.calls,
    "results": results,
}
Path("docs/grounding-real-evidence.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2) + "\n"
)
print(json.dumps(out, ensure_ascii=False, indent=2))
