from collections.abc import AsyncIterator

import httpx
import pytest

from aura.api import health as health_module
from aura.db import get_session
from aura.main import create_app
from aura.schemas import ServiceStatus


class FakeSession:
    async def execute(self, *_args, **_kwargs) -> None:
        return None


async def _fake_session() -> AsyncIterator[FakeSession]:
    yield FakeSession()


@pytest.fixture
def app():
    application = create_app(startup=False)
    application.dependency_overrides[get_session] = _fake_session
    return application


async def test_health_reports_services(app, monkeypatch) -> None:
    async def fake_gitea() -> ServiceStatus:
        return ServiceStatus(name="gitea", status="ok", detail="Gitea test")

    async def fake_ragflow(_session) -> ServiceStatus:
        return ServiceStatus(name="ragflow", status="off", detail="Not configured")

    monkeypatch.setattr(health_module, "_check_gitea", fake_gitea)
    monkeypatch.setattr(health_module, "_check_ragflow", fake_ragflow)
    monkeypatch.setattr(
        health_module,
        "_check_claude",
        lambda: ServiceStatus(name="claude", status="ok", detail="/usr/bin/claude"),
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert {item["name"] for item in payload["services"]} == {
        "database",
        "gitea",
        "claude",
        "ragflow",
    }
