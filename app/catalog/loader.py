import json
from pathlib import Path

from app.catalog.models import CommercialOffer, VehicleMedia, VehicleVersion
from app.catalog.repository import JsonCatalogRepository


def normalize_external_media_record(record: dict, *, source_file: Path, index: int) -> VehicleMedia:
    """Translate the supplied media manifest at the import boundary, not in the canonical model."""
    row = dict(record)
    media_id = row.pop("media_id", None)
    canonical_id = row.get("id")
    if media_id is not None and canonical_id is not None and media_id != canonical_id:
        raise ValueError(f"{source_file}: record {index}: id conflicts with media_id")
    if canonical_id is None:
        if media_id is None:
            raise ValueError(f"{source_file}: record {index}: missing id and media_id")
        row["id"] = media_id

    # The external manifest has relative_path but no public/source URL or storage URI.
    row.pop("relative_path", None)
    row.pop("vehicle_model", None)
    row.pop("color_visual", None)
    if "source_url" not in row:
        row["source_url"] = None
    if "storage_uri" not in row:
        row["storage_uri"] = None
    try:
        return VehicleMedia.model_validate(row)
    except Exception as exc:
        raise ValueError(f"{source_file}: record {index} ({row.get('id', media_id)!r}): {exc}") from exc


def load_catalog(directory: Path) -> JsonCatalogRepository:
    """Load a reviewed catalog snapshot. Invalid files fail closed."""
    def read(name: str) -> list[dict]:
        path = directory / name
        if not path.exists():
            return []
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, list):
            raise TypeError(f"{name} must contain a JSON array")
        return value

    vehicle_rows = read("vehicles.json")
    media_rows = read("media.json")
    offer_rows = read("offers.json")
    media_path = directory / "media.json"
    return JsonCatalogRepository(
        [VehicleVersion.model_validate(row) for row in vehicle_rows],
        [normalize_external_media_record(row, source_file=media_path, index=i) for i, row in enumerate(media_rows, 1)],
        [CommercialOffer.model_validate(row) for row in offer_rows],
    )
