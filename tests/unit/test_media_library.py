from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.catalog.loader import load_catalog
from app.catalog.media_library import MediaSearchQuery, VehicleMediaLibrary
from app.catalog.models import VehicleMedia, VehicleVersion

NOW = datetime(2026, 10, 29, tzinfo=UTC)


def vehicle(vehicle_id, *, approved=True):
    model, powertrain = vehicle_id.split("-")
    return VehicleVersion(
        id=vehicle_id,
        model=model.upper(),
        version=powertrain.upper(),
        powertrain=powertrain.upper(),
        updated_at=NOW,
        sources=[{"url": "https://example.org/synthetic", "retrieved_at": NOW}],
        approval_status="approved" if approved else "pending_review",
        approved_at=NOW if approved else None,
        approved_by="synthetic-reviewer" if approved else None,
    )


@pytest.fixture
def library(tmp_path):
    vehicles = [vehicle(v) for v in ["b10-bev", "b10-reev", "c10-bev"]]
    records = []
    for v in vehicles:
        for angle, category in [
            ("front_3_4", "exterior"),
            ("rear_3_4", "exterior"),
            ("cockpit", "interior"),
            ("front_seats_roof", "interior"),
        ]:
            path = tmp_path / (v.id + angle + ".jpg")
            path.write_bytes(b"synthetic fixture")
            records.append(
                VehicleMedia(
                    id=v.id + "-" + angle,
                    vehicle_id=v.id,
                    category=category,
                    subcategory=angle,
                    color="blue",
                    asset_path=str(path),
                    rights_basis="Synthetic permission",
                    provenance="Synthetic fixture",
                    retrieved_at=NOW,
                    approval_status="approved",
                    approved_at=NOW,
                    approved_by="synthetic-reviewer",
                    usage_rights_status="approved",
                    storage_uri="synthetic://" + path.name,
                )
            )
    return VehicleMediaLibrary(list(reversed(records)), vehicles=vehicles, asset_root=tmp_path)


@pytest.mark.parametrize("vehicle_id", ["b10-bev", "b10-reev", "c10-bev"])
def test_canonical_vehicle_isolation(library, vehicle_id):
    found = library.search(MediaSearchQuery(vehicle_id=vehicle_id))
    assert len(found) == 4
    assert {m.vehicle_id for m in found} == {vehicle_id}


@pytest.mark.parametrize(
    "powertrain,expected",
    [("elétrico", "b10-bev"), (" BEV ", "b10-bev"), ("híbrido", "b10-reev"), ("REEV", "b10-reev")],
)
def test_powertrain_synonyms(library, powertrain, expected):
    assert {
        r.vehicle_id for r in library.search(MediaSearchQuery(model="B10", powertrain=powertrain))
    } == {expected}


@pytest.mark.parametrize(
    "filters,expected",
    [
        ({"angle": "frente"}, 1),
        ({"angle": "traseira"}, 1),
        ({"angle": "painel"}, 1),
        ({"angle": "bancos"}, 1),
        ({"angle": "teto panorâmico"}, 1),
        ({"angle": "interior"}, 2),
        ({"category": "exterior"}, 2),
        ({"color": "azul"}, 4),
        ({"angle": "unknown"}, 0),
        ({"color": "verde"}, 0),
        ({"category": "dashboard"}, 0),
        ({"category": "exterior", "angle": "painel"}, 0),
    ],
)
def test_exact_filters(library, filters, expected):
    assert len(library.search(MediaSearchQuery(vehicle_id="b10-bev", **filters))) == expected


def test_ambiguous_versions_and_incomplete_filters(library):
    assert library.search(MediaSearchQuery(model="B10")) == []
    assert library.search(MediaSearchQuery(vehicle_id="b10-bev", powertrain="REEV")) == []
    assert library.search(MediaSearchQuery(vehicle_id="b10-bev", model="C10")) == []
    variant = vehicle("b10-bev")
    variant = VehicleVersion.model_validate(variant.model_dump() | {"id": "b10-bev-second"})
    library._vehicles[variant.id] = variant
    assert library.search(MediaSearchQuery(model="B10", powertrain="BEV")) == []


def test_order_and_limit(library):
    all_ids = [r.id for r in library.search(MediaSearchQuery(vehicle_id="b10-bev"))]
    assert all_ids == sorted(all_ids)
    assert [
        r.id for r in library.search(MediaSearchQuery(vehicle_id="b10-bev", limit=2))
    ] == all_ids[:2]
    with pytest.raises(ValidationError):
        MediaSearchQuery(limit=0)


def test_pending_media_vehicle_and_missing_asset_are_blocked(library):
    for r in library.records:
        object.__setattr__(r, "approval_status", "pending_review")
    assert library.search(MediaSearchQuery(vehicle_id="b10-bev")) == []
    real = load_catalog(Path("data/catalog"))
    canonical = [vehicle(v, approved=False) for v in ["b10-bev", "b10-reev", "c10-bev"]]
    lib = VehicleMediaLibrary(real.media(), vehicles=canonical, asset_root=Path("assets/media"))
    assert all(r.approval_status == "pending_review" for r in real.media())
    assert lib.search(MediaSearchQuery(vehicle_id="b10-bev")) == []


def test_unknown_vehicle_and_inconsistent_identity_rejected(library):
    with pytest.raises(ValueError, match="Unknown canonical vehicle"):
        VehicleMediaLibrary(library.records, vehicles=[], asset_root=library.asset_root)
    invalid = VehicleVersion.model_validate(
        vehicle("b10-bev").model_dump() | {"powertrain": "REEV"}
    )
    with pytest.raises(ValueError, match="identity mismatch"):
        VehicleMediaLibrary(
            [r for r in library.records if r.vehicle_id == "b10-bev"][:1],
            vehicles=[invalid],
            asset_root=library.asset_root,
        )


def test_missing_and_outside_files_are_not_returned(library, tmp_path):
    record = next(r for r in library.records if r.vehicle_id == "b10-bev")
    Path(record.asset_path).unlink()
    assert record.id not in {r.id for r in library.search(MediaSearchQuery(vehicle_id="b10-bev"))}
    outside = tmp_path.parent / (tmp_path.name + "-outside.jpg")
    try:
        outside.write_bytes(b"synthetic")
        record.asset_path = str(outside)
        assert record.id not in {
            r.id for r in library.search(MediaSearchQuery(vehicle_id="b10-bev"))
        }
    finally:
        outside.unlink(missing_ok=True)


def test_real_catalog_loads_but_remains_unavailable():
    catalog = load_catalog(Path("data/catalog"))
    lib = VehicleMediaLibrary.load(catalog, asset_root=Path("assets/media"))
    assert len(lib.records) == 12
    assert all(v.approval_status == "pending_review" for v in catalog.vehicles())
    for vid in ["b10-bev", "b10-reev", "c10-bev"]:
        assert lib.search(MediaSearchQuery(vehicle_id=vid)) == []
