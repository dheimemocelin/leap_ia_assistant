from pathlib import Path

from app.catalog.loader import load_catalog
from app.catalog.models import ApprovalStatus


def test_imports_all_twelve_media_manifest_records() -> None:
    catalog = load_catalog(Path("data/catalog"))

    assert len(catalog.media()) == 12
    assert all(media.id for media in catalog.media())
    assert all(media.approval_status == ApprovalStatus.PENDING_REVIEW for media in catalog.media())
    assert {media.vehicle_id for media in catalog.media()} == {"b10-bev", "b10-reev", "c10-bev"}
