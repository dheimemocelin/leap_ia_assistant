import json
from pathlib import Path

from app.catalog.models import CommercialOffer, VehicleMedia, VehicleVersion
from app.catalog.repository import JsonCatalogRepository


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

    return JsonCatalogRepository(
        [VehicleVersion.model_validate(row) for row in read("vehicles.json")],
        [VehicleMedia.model_validate(row) for row in read("media.json")],
        [CommercialOffer.model_validate(row) for row in read("offers.json")],
    )
