from datetime import UTC, date, datetime
from pathlib import Path
from typing import ClassVar

import pytest

from app.catalog.loader import load_catalog
from app.catalog.models import (
    ApprovalStatus,
    CommercialOffer,
    MediaCategory,
    SourceRecord,
    VehicleMedia,
    VehicleVersion,
)
from app.catalog.repository import JsonCatalogRepository
from app.tools.sales import LeadData, SalesTools, VehicleMediaFilter

NOW = datetime(2026, 10, 29, tzinfo=UTC)
SOURCE = SourceRecord(url="https://www.leapmotor.com.br/c10.html", retrieved_at=NOW)


def approved_vehicle(vehicle_id: str = "c10-bev", model: str = "C10") -> VehicleVersion:
    return VehicleVersion(
        id=vehicle_id,
        model=model,
        version="BEV",
        powertrain="BEV",
        sources=[SOURCE],
        updated_at=NOW,
        approval_status=ApprovalStatus.APPROVED,
        approved_at=NOW,
        approved_by="catalog-reviewer",
    )


def approved_media(media_id: str, *, color: str, category: MediaCategory) -> VehicleMedia:
    return VehicleMedia(
        id=media_id,
        vehicle_id="c10-bev",
        version="BEV",
        color=color,
        category=category,
        source_url="https://www.leapmotor.com.br/c10.html",
        storage_uri=f"s3://approved-media/{media_id}.jpg",
        rights_basis="Written permission ref MEDIA-001",
        provenance="Official product page image",
        retrieved_at=NOW,
        approval_status=ApprovalStatus.APPROVED,
        approved_at=NOW,
        approved_by="media-reviewer",
    )


def test_pending_fixture_never_reaches_sales_tools() -> None:
    repository = load_catalog(Path("tests/fixtures/catalog"))
    tools = SalesTools(repository, today=date(2026, 10, 29))
    assert tools.list_vehicles() == []
    assert tools.get_vehicle_details("c10-bev") is None


def test_list_details_compare_only_approved_catalog() -> None:
    repository = JsonCatalogRepository([approved_vehicle(), approved_vehicle("b10-bev", "B10")], [], [])
    tools = SalesTools(repository)
    assert [row["id"] for row in tools.list_vehicles()] == ["c10-bev", "b10-bev"]
    assert tools.get_vehicle_details("c10-bev")["model"] == "C10"
    assert tools.compare_vehicles(["c10-bev", "b10-bev"])["outcome"] == "ok"
    assert tools.compare_vehicles(["c10-bev", "missing"])["outcome"] == "not_found"


def test_media_search_filters_and_requires_approved_stored_asset() -> None:
    media = [
        approved_media("green-exterior", color="Verde Boreal", category=MediaCategory.EXTERIOR),
        approved_media("black-interior", color="Preto", category=MediaCategory.INTERIOR),
        approved_media("wrong-version", color="Verde Boreal", category=MediaCategory.EXTERIOR).model_copy(
            update={"version": "REEV", "approval_status": ApprovalStatus.PENDING_REVIEW}
        ),
    ]
    tools = SalesTools(JsonCatalogRepository([approved_vehicle()], media, []))
    found = tools.search_vehicle_media(
        VehicleMediaFilter(vehicle_id="c10-bev", color="verde boreal", category=MediaCategory.EXTERIOR)
    )
    assert [item["id"] for item in found] == ["green-exterior"]
    assert tools.search_vehicle_media(VehicleMediaFilter(vehicle_id="c10-bev", version="REEV")) == []


def test_offer_records_remain_catalog_data_but_are_not_queryable_by_sales_tools() -> None:
    offer = CommercialOffer(
        id="offer-1", vehicle_id="c10-bev", amount_brl=123000,
        valid_from=date(2026, 10, 1), valid_until=date(2026, 10, 31),
        source=SOURCE, approval_status=ApprovalStatus.APPROVED, approved_at=NOW, approved_by="reviewer",
    )
    tools = SalesTools(JsonCatalogRepository([approved_vehicle()], [], [offer]), today=date(2026, 10, 29))
    assert not hasattr(tools, "get_commercial_offer")


def test_crm_write_fails_closed_without_minimum_data_consent_or_adapter() -> None:
    calls = []

    class Adapter:
        seen: ClassVar[dict[str, str]] = {}

        def create_lead(self, *, lead, idempotency_key):
            calls.append(idempotency_key)
            return self.seen.setdefault(idempotency_key, "crm-1")

    class Consent:
        def is_valid_for_lead(self, *, consent_id, lead):
            return consent_id == "consent-1" and lead.consent_to_contact

    incomplete = LeadData()
    assert SalesTools.create_syonet_lead(incomplete, consent_id="c", idempotency_key="k", adapter=Adapter(), consent_verifier=Consent())["outcome"] == "blocked"
    valid = LeadData(name="Cliente sintético", phone="+5500000000000", interested_vehicle_id="c10-bev", consent_to_contact=True)
    assert SalesTools.create_syonet_lead(valid, consent_id=None, idempotency_key="k", adapter=Adapter(), consent_verifier=Consent())["reason"] == "consent_required"
    assert SalesTools.create_syonet_lead(valid, consent_id="consent-1", idempotency_key=None, adapter=Adapter(), consent_verifier=Consent())["reason"] == "idempotency_key_required"
    assert SalesTools.create_syonet_lead(valid, consent_id="consent-1", idempotency_key="k", adapter=None, consent_verifier=Consent())["reason"] == "syonet_not_configured"
    assert SalesTools.create_syonet_lead(valid, consent_id="fake", idempotency_key="k", adapter=Adapter(), consent_verifier=Consent())["reason"] == "consent_invalid_or_revoked"
    assert calls == []
    result1 = SalesTools.create_syonet_lead(valid, consent_id="consent-1", idempotency_key="idem-1", adapter=Adapter(), consent_verifier=Consent())
    result2 = SalesTools.create_syonet_lead(valid, consent_id="consent-1", idempotency_key="idem-1", adapter=Adapter(), consent_verifier=Consent())
    assert result1["crm_id"] == result2["crm_id"] == "crm-1"
    assert calls == ["idem-1", "idem-1"]


def test_invalid_approval_metadata_is_rejected() -> None:
    with pytest.raises(ValueError):
        VehicleVersion.model_validate(approved_vehicle().model_dump() | {"approved_by": None})
