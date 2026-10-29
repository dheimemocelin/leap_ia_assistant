from fastapi.testclient import TestClient

from app.api import routes
from app.main import app


def test_ready_reports_unavailable_when_database_fails(monkeypatch):
    class Connection:
        async def __aenter__(self):
            raise OSError("db unavailable")

        async def __aexit__(self, *args):
            return None

    class Engine:
        def connect(self):
            return Connection()

        async def dispose(self):
            pass

    class Redis:
        @classmethod
        def from_url(cls, *args, **kwargs):
            return cls()

        async def ping(self):
            return True

        async def aclose(self):
            pass

    monkeypatch.setattr(routes, "create_async_engine", lambda *args, **kwargs: Engine())
    monkeypatch.setattr(routes, "Redis", Redis)
    response = TestClient(app).get("/health/ready")
    assert response.status_code == 503


def test_live_probe_is_independent_of_dependencies():
    assert TestClient(app).get("/health/live").json() == {"status": "ok"}
