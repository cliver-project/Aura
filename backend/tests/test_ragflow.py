import json

import httpx
import pytest

from aura.services.ragflow import RagflowClient, RagflowError


def test_account_defaults_are_not_hardcoded() -> None:
    client = RagflowClient("http://ragflow.test")
    assert client.account_email == ""
    assert client.account_password == ""


async def test_account_login_and_create_key_use_session_header() -> None:
    seen: list[tuple[str, str, str | None, dict | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        seen.append(
            (
                request.method,
                request.url.path,
                request.headers.get("authorization"),
                body,
            )
        )
        if request.url.path.endswith("/auth/login"):
            return httpx.Response(
                200,
                json={"code": 0, "data": {}},
                headers={"Authorization": "session-token"},
            )
        if request.url.path.endswith("/system/tokens"):
            return httpx.Response(
                200,
                json={"code": 0, "data": {"token": "ragflow-test-token"}},
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = RagflowClient(
            "http://ragflow.test",
            account_email="aoingl@gmail.com",
            account_password="secret",
            client=http,
        )
        token = await client.create_api_key("aura")

    assert token == "ragflow-test-token"
    login = seen[0]
    assert login[0] == "POST" and login[1] == "/api/v1/auth/login"
    assert login[3]["email"] == "aoingl@gmail.com"
    assert login[3]["password"] == "secret"
    token_request = seen[1]
    assert token_request[1] == "/api/v1/system/tokens"
    assert token_request[2] == "session-token"
    assert token_request[3] == {"name": "aura"}


async def test_list_datasets_uses_bearer_api_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/datasets"
        assert request.headers.get("authorization") == "Bearer ragflow-key"
        return httpx.Response(200, json={"code": 0, "data": [{"id": "ds-1", "name": "Docs"}]})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = RagflowClient("http://ragflow.test", api_key="ragflow-key", client=http)
        datasets = await client.list_datasets()

    assert datasets == [{"id": "ds-1", "name": "Docs"}]


async def test_update_language_uses_bearer_api_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PATCH"
        assert request.url.path == "/api/v1/users/me"
        assert request.headers.get("authorization") == "Bearer ragflow-key"
        assert json.loads(request.content) == {"language": "zh-Hans"}
        return httpx.Response(200, json={"code": 0, "data": True})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = RagflowClient("http://ragflow.test", api_key="ragflow-key", client=http)
        await client.update_language("zh-Hans")


async def test_create_key_reports_existing_account_password_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"code": 102, "message": "Email already registered"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = RagflowClient(
            "http://ragflow.test",
            account_email="aoingl@gmail.com",
            account_password="wrong",
            client=http,
        )
        with pytest.raises(RagflowError, match="existing account"):
            await client.create_api_key("aura")


async def test_health_returns_false_on_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="not ready")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = RagflowClient("http://ragflow.test", client=http)
        assert await client.health() is False
