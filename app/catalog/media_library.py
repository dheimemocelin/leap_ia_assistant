import unicodedata
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field

from app.catalog.models import ApprovalStatus, MediaCategory, VehicleMedia, VehicleVersion


class MediaAngle(StrEnum):
    FRONT = "front"
    REAR = "rear"
    SIDE = "side"
    DASHBOARD = "dashboard"
    SEATS = "seats"
    ROOF = "roof"


ANGLE_SYNONYMS = {
    "frente": MediaAngle.FRONT,
    "frontal": MediaAngle.FRONT,
    "traseira": MediaAngle.REAR,
    "traseiro": MediaAngle.REAR,
    "lateral": MediaAngle.SIDE,
    "perfil": MediaAngle.SIDE,
    "painel": MediaAngle.DASHBOARD,
    "cockpit": MediaAngle.DASHBOARD,
    "bancos": MediaAngle.SEATS,
    "assentos": MediaAngle.SEATS,
    "teto": MediaAngle.ROOF,
    "teto panorâmico": MediaAngle.ROOF,
}
CATEGORY_SYNONYMS = {
    "interior": MediaCategory.INTERIOR,
    "exterior": MediaCategory.EXTERIOR,
}
POWERTRAIN_SYNONYMS = {"bev": "BEV", "elétrico": "BEV", "reev": "REEV", "híbrido": "REEV"}


def norm(value: str) -> str:
    return "".join(
        c
        for c in unicodedata.normalize("NFKD", value.strip().casefold())
        if not unicodedata.combining(c)
    )


def powertrain_key(value: str) -> str | None:
    return {norm(k): v for k, v in POWERTRAIN_SYNONYMS.items()}.get(norm(value))


def color_key(value: str) -> str:
    key = norm(value)
    return {"preto": "black", "branco": "white", "azul": "blue", "verde": "green"}.get(key, key)


class MediaSearchQuery(BaseModel):
    """Use canonical vehicle_id, or an exact model plus powertrain pair."""

    vehicle_id: str | None = None
    model: str | None = None
    powertrain: str | None = None
    category: MediaCategory | None = None
    color: str | None = None
    angle: str | None = None
    limit: int = Field(default=12, ge=1, le=100)


class VehicleMediaLibrary:
    def __init__(
        self,
        records: list[VehicleMedia],
        *,
        vehicles: list[VehicleVersion],
        asset_root: Path,
    ):
        self.records = records
        self.asset_root = asset_root.resolve()
        if len({v.id for v in vehicles}) != len(vehicles):
            raise ValueError("Duplicate canonical vehicle identifiers")
        self._vehicles = {vehicle.id: vehicle for vehicle in vehicles}
        if len({r.id for r in records}) != len(records):
            raise ValueError("Duplicate media identifiers")
        for record in records:
            vehicle = self._vehicles.get(record.vehicle_id)
            if vehicle is None:
                raise ValueError(f"Unknown canonical vehicle: {record.vehicle_id}")
            if record.vehicle_id in {"b10-bev", "b10-reev", "c10-bev"}:
                model, powertrain = record.vehicle_id.split("-")
                if norm(vehicle.model) != model or norm(vehicle.powertrain.value) != powertrain:
                    raise ValueError(f"Canonical vehicle identity mismatch: {vehicle.id}")
            if record.version and record.version != vehicle.version:
                raise ValueError(f"Media version mismatch: {record.id}")
        self._index: dict[str, list[VehicleMedia]] = {}
        for record in records:
            self._index.setdefault(record.vehicle_id, []).append(record)

    @classmethod
    def load(cls, catalog, *, asset_root: Path) -> "VehicleMediaLibrary":
        return cls(catalog.media(), vehicles=catalog.vehicles(), asset_root=asset_root)

    def search(self, query: MediaSearchQuery) -> list[VehicleMedia]:
        vehicle_id = self._resolve_vehicle_id(query)
        if vehicle_id is None:
            return []
        vehicle = self._vehicles.get(vehicle_id)
        if vehicle is None or vehicle.approval_status != ApprovalStatus.APPROVED:
            return []

        angle_key = (query.angle or "").casefold().strip()
        angle = {norm(k): v for k, v in ANGLE_SYNONYMS.items()}.get(norm(angle_key))
        if query.angle and angle is None and norm(angle_key) not in CATEGORY_SYNONYMS:
            return []
        category = query.category or CATEGORY_SYNONYMS.get(norm(angle_key))
        matches = []
        for record in self._index.get(vehicle_id, []):
            if record.approval_status != ApprovalStatus.APPROVED:
                continue
            if not (
                record.approved_at
                and record.approved_by
                and record.usage_rights_status == "approved"
                and record.storage_uri
            ):
                continue
            if query.color and color_key(record.color or "") != color_key(query.color):
                continue
            if category and record.category != category:
                continue
            if angle and not self._matches_angle(record, angle):
                continue
            if not self._asset_exists(record):
                continue
            matches.append(record)
        return sorted(matches, key=lambda record: record.id)[: query.limit]

    def _resolve_vehicle_id(self, query: MediaSearchQuery) -> str | None:
        if query.vehicle_id:
            vehicle = self._vehicles.get(query.vehicle_id)
            if vehicle is None:
                return None
            if query.powertrain and powertrain_key(query.powertrain) != vehicle.powertrain.value:
                return None
            if query.model and norm(query.model) != norm(vehicle.model):
                return None
            return vehicle.id
        if not query.model or not query.powertrain:
            return None
        powertrain = powertrain_key(query.powertrain)
        if powertrain is None:
            return None
        matches = [
            vehicle.id
            for vehicle in self._vehicles.values()
            if norm(vehicle.model) == norm(query.model)
            and vehicle.powertrain.value == powertrain
            and vehicle.approval_status == ApprovalStatus.APPROVED
        ]
        return matches[0] if len(matches) == 1 else None

    @staticmethod
    def _matches_angle(record: VehicleMedia, angle: MediaAngle) -> bool:
        labels = {
            MediaAngle.FRONT: {"front", "front_3_4", "frente", "frontal"},
            MediaAngle.REAR: {"rear", "rear_3_4", "traseira", "traseiro"},
            MediaAngle.SIDE: {"side", "side_profile", "lateral", "perfil"},
            MediaAngle.DASHBOARD: {"cockpit", "dashboard", "painel"},
            MediaAngle.SEATS: {"front_seats", "front_seats_roof", "seats", "bancos"},
            MediaAngle.ROOF: {"panoramic_roof", "front_seats_roof", "roof", "teto"},
        }
        return norm(record.subcategory or "") in labels[angle]

    def _asset_exists(self, record: VehicleMedia) -> bool:
        if not record.asset_path:
            return False
        path = Path(record.asset_path)
        if path.is_absolute():
            resolved = path.resolve()
        else:
            parts = path.parts
            if parts[:2] == ("assets", "media"):
                path = Path(*parts[2:])
            resolved = (self.asset_root / path).resolve()
        return resolved.is_relative_to(self.asset_root) and resolved.is_file()
