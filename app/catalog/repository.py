from datetime import date
from typing import Protocol

from app.catalog.models import ApprovalStatus, CommercialOffer, VehicleMedia, VehicleVersion


class CatalogRepository(Protocol):
    def vehicles(self) -> list[VehicleVersion]: ...
    def vehicle(self, vehicle_id: str) -> VehicleVersion | None: ...
    def media(self) -> list[VehicleMedia]: ...
    def offers(self) -> list[CommercialOffer]: ...


class JsonCatalogRepository:
    """Read-only local catalog. JSON files are curated fixtures, never scraped live at runtime."""

    def __init__(self, vehicles: list[VehicleVersion], media: list[VehicleMedia], offers: list[CommercialOffer]):
        self._vehicles = vehicles
        self._media = media
        self._offers = offers

    def vehicles(self) -> list[VehicleVersion]:
        return list(self._vehicles)

    def vehicle(self, vehicle_id: str) -> VehicleVersion | None:
        return next((item for item in self._vehicles if item.id == vehicle_id), None)

    def media(self) -> list[VehicleMedia]:
        return list(self._media)

    def offers(self) -> list[CommercialOffer]:
        return list(self._offers)


def approved_vehicles(repository: CatalogRepository) -> list[VehicleVersion]:
    return [v for v in repository.vehicles() if v.approval_status == ApprovalStatus.APPROVED]


def current_approved_offers(repository: CatalogRepository, today: date) -> list[CommercialOffer]:
    return [
        offer for offer in repository.offers()
        if offer.approval_status == ApprovalStatus.APPROVED
        and offer.approved_at is not None
        and offer.approved_by is not None
        and offer.valid_from <= today <= offer.valid_until
    ]
