"""Keep ordinary tests away from the configured on-disk pilot database."""

import pytest

from app.config import settings


@pytest.fixture(autouse=True)
def isolated_pilot_default(monkeypatch):
    monkeypatch.setattr(settings, "pilot_db_path", "")
