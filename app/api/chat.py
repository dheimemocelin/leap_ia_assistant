import hashlib
import json
import secrets
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from app.agent.groq import GroqAdapter
from app.agent.grounding import GroundingPolicy, ReviewedBrandFact, ReviewedFact, ReviewedTextFact
from app.agent.llm import DisabledLLM, OllamaAdapter
from app.agent.service import SalesAgent
from app.catalog.loader import load_catalog
from app.catalog.media_library import VehicleMediaLibrary
from app.catalog.repository import JsonCatalogRepository
from app.config import settings
from app.domain.response import AssistantResponse

router = APIRouter()


class ChatInput(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


def build_agent(*, reviewed_catalog=False, test_media=False):
    root = Path(__file__).resolve().parents[2]
    catalog_root = root / ("data/validation/grounding" if reviewed_catalog else "data/catalog")
    catalog = load_catalog(catalog_root)
    if reviewed_catalog:
        original = load_catalog(
            root / ("data/validation/media-chat" if test_media else "data/catalog")
        )
        vehicles = {v.id: v for v in original.vehicles()}
        vehicles.update({v.id: v for v in catalog.vehicles()})
        catalog = JsonCatalogRepository(list(vehicles.values()), original.media(), [])
    media = VehicleMediaLibrary.load(catalog, asset_root=root / "assets/media")
    if settings.llm_provider == "ollama":
        llm = OllamaAdapter(
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            timeout=settings.llm_timeout_seconds,
        )
    elif settings.llm_provider == "groq":
        llm = GroqAdapter(
            api_key=settings.groq_api_key,
            model=settings.llm_model,
            timeout=settings.llm_timeout_seconds,
        )
    elif settings.llm_provider == "disabled":
        llm = DisabledLLM()
    else:
        raise ValueError("Unknown LLM provider")
    grounding = None
    if reviewed_catalog:
        facts = [
            ReviewedFact.model_validate(f)
            for f in json.loads((catalog_root / "facts.json").read_text())
        ]
        knowledge_path = catalog_root / "knowledge.json"
        if knowledge_path.is_file():
            facts += [
                ReviewedTextFact.model_validate(f) for f in json.loads(knowledge_path.read_text())
            ]
        brand_path = catalog_root / "brand.json"
        brand = (
            ReviewedBrandFact.model_validate_json(brand_path.read_text())
            if brand_path.is_file()
            else None
        )
        grounding = GroundingPolicy(facts, catalog, brand=brand)
    return SalesAgent(
        catalog,
        media,
        llm,
        timeout=settings.llm_timeout_seconds,
        grounding=grounding,
        input_token_rate=settings.llm_input_usd_per_million,
        output_token_rate=settings.llm_output_usd_per_million,
    )


@router.post("/v1/conversations/{conversation_id}/messages", response_model=AssistantResponse)
async def chat(
    conversation_id: str,
    body: ChatInput,
    request: Request,
    authorization: str = Header(default=""),
    x_session_token: str = Header(default=""),
):
    if not settings.app_api_key:
        raise HTTPException(503, "Local API access is not configured")
    if not secrets.compare_digest(authorization, "Bearer " + settings.app_api_key):
        raise HTTPException(401, "Unauthorized")
    if len(x_session_token) < 32 or len(x_session_token) > 200:
        raise HTTPException(401, "Session token required")
    if not hasattr(request.app.state, "sales_agent"):
        request.app.state.sales_agent = build_agent()
    owner = hashlib.sha256(x_session_token.encode()).hexdigest()
    return await request.app.state.sales_agent.turn(conversation_id, body.text, owner=owner)
