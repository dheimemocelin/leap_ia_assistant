import hashlib
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from test_media_library import vehicle

from app.api import web_chat
from app.catalog.media_library import VehicleMediaLibrary
from app.catalog.models import VehicleMedia
from app.catalog.repository import JsonCatalogRepository
from app.config import settings
from app.domain.response import AssistantResponse
from app.main import app


@pytest.fixture
def media_browser(tmp_path, monkeypatch):
    now = datetime.now(UTC)
    path = tmp_path / "synthetic.jpeg"
    data = bytes.fromhex("ffd8ff") + b"synthetic-image-fixture" + bytes.fromhex("ffd9")
    path.write_bytes(data)
    record = VehicleMedia(
        id="fixture-photo",
        vehicle_id="b10-bev",
        category="exterior",
        asset_path=str(path),
        storage_uri="test://fixture",
        sha256=hashlib.sha256(data).hexdigest(),
        mime_type="image/jpeg",
        rights_basis="synthetic rights",
        provenance="synthetic test",
        retrieved_at=now,
        approval_status="approved",
        approved_at=now,
        approved_by="test",
        usage_rights_status="approved",
    )
    catalog = JsonCatalogRepository([vehicle("b10-bev")], [record], [])

    class Fake:
        def __init__(self):
            self.catalog = catalog
            self.media = VehicleMediaLibrary(
                [record], vehicles=catalog.vehicles(), asset_root=tmp_path
            )

        async def turn(self, *args, **kwargs):
            return AssistantResponse(
                text="Separei uma foto.",
                confidence="insufficient_evidence",
                media_ids=["fixture-photo"],
            )

    monkeypatch.setattr(settings, "web_chat_password", SecretStr("synthetic-web-password"))
    monkeypatch.setattr(web_chat, "MEDIA_ROOT", tmp_path)
    app.state.browser_sessions = web_chat.BrowserSessions()
    app.state.web_agent_reviewed = Fake()
    client = TestClient(app)
    headers = {"Origin": "http://testserver"}
    client.post("/web/login", json={"password": "synthetic-web-password"}, headers=headers)
    yield client, record, path, headers
    del app.state.browser_sessions
    del app.state.web_agent_reviewed


def grant(client, headers):
    client.post("/v1/web/messages", json={"text": "Fotos B10 BEV"}, headers=headers)
    response = client.post(
        "/web/media/resolve", json={"media_ids": ["fixture-photo"]}, headers=headers
    )
    assert response.status_code == 200
    return response.json()["images"][0]["url"]


def test_authenticated_image_inline_no_paths_or_base64(media_browser):
    client, _, path, headers = media_browser
    url = grant(client, headers)
    assert "fixture-photo" not in url and str(path) not in url
    result = client.get(url)
    assert result.status_code == 200 and result.headers["content-type"] == "image/jpeg"
    assert result.content == path.read_bytes()
    assert "no-store" in result.headers["cache-control"]
    assert TestClient(app).get(url).status_code == 401


def test_unrequested_media_and_other_session_are_blocked(media_browser):
    client, _, _, headers = media_browser
    assert (
        client.post(
            "/web/media/resolve", json={"media_ids": ["fixture-photo"]}, headers=headers
        ).status_code
        == 403
    )
    url = grant(client, headers)
    other = TestClient(app)
    other.post("/web/login", json={"password": "synthetic-web-password"}, headers=headers)
    assert other.get(url).status_code == 404


@pytest.mark.parametrize("failure", ["pending", "missing", "hash", "mime"])
def test_recheck_approval_existence_integrity_and_mime(media_browser, failure):
    client, record, path, headers = media_browser
    url = grant(client, headers)
    if failure == "pending":
        record.approval_status = "pending_review"
    elif failure == "missing":
        path.unlink()
    elif failure == "hash":
        path.write_bytes(b"corrupt")
    else:
        record.mime_type = "text/html"
    assert client.get(url).status_code in {404, 415}


def test_authorized_test_snapshot_does_not_publish_original_catalog():
    from pathlib import Path

    from app.api.chat import build_agent
    from app.catalog.loader import load_catalog
    from app.catalog.media_library import MediaSearchQuery

    test_agent = build_agent(reviewed_catalog=True, test_media=True)
    ordinary_agent = build_agent(reviewed_catalog=True)
    for vid in ["b10-bev", "b10-reev", "c10-bev"]:
        assert len(test_agent.media.search(MediaSearchQuery(vehicle_id=vid))) == 4
        assert ordinary_agent.media.search(MediaSearchQuery(vehicle_id=vid)) == []
    assert all(
        m.approval_status == "pending_review" for m in load_catalog(Path("data/catalog")).media()
    )
