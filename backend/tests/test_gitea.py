import json

import httpx
import pytest

from aura.services.gitea import GiteaClient, GiteaError


async def test_create_repo_sends_expected_request() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("authorization")
        captured["body"] = json.loads(request.content)
        return httpx.Response(201, json={"name": "demo", "full_name": "aura/demo"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = GiteaClient("http://gitea.test", token="secret", client=http)
        repo = await client.create_repo("demo", description="Demo project")

    assert repo["name"] == "demo"
    assert captured["url"] == "http://gitea.test/api/v1/user/repos"
    assert captured["auth"] == "token secret"
    assert captured["body"]["auto_init"] is True
    assert captured["body"]["private"] is False


async def test_update_current_user_settings_uses_basic_auth() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        captured["auth"] = request.headers.get("authorization")
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"language": "zh-CN"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = GiteaClient("http://gitea.test", token="admin-token", client=http)
        result = await client.update_current_user_settings(
            "zh-CN",
            username="lgao",
            password="password",
        )

    assert result["language"] == "zh-CN"
    assert captured["method"] == "PATCH"
    assert captured["path"] == "/api/v1/user/settings"
    assert str(captured["auth"]).startswith("Basic ")
    assert captured["body"] == {"language": "zh-CN"}


async def test_commit_status_and_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/statuses/abc"):
            return httpx.Response(200, json={"state": "success"})
        return httpx.Response(404, text="not found")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = GiteaClient("http://gitea.test", token="secret", client=http)
        status = await client.create_commit_status("aura", "demo", "abc", "success")
        assert status["state"] == "success"
        with pytest.raises(GiteaError) as error:
            await client.get_repo("aura", "missing")
        assert error.value.status == 404


async def test_user_key_and_token_endpoints() -> None:
    requests: list[tuple[str, str, str | None, dict | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        requests.append(
            (
                request.method,
                request.url.path,
                request.headers.get("authorization"),
                body,
            )
        )
        if request.url.path.endswith("/tokens"):
            return httpx.Response(201, json={"sha1": "token-123", "name": "aura-onboarding"})
        if request.url.path.endswith("/keys") and request.method == "POST":
            return httpx.Response(201, json={"id": 1, "key": "ssh-ed25519 AAAA test"})
        if request.url.path.endswith("/keys"):
            return httpx.Response(200, json=[{"id": 1, "key": "ssh-ed25519 AAAA test"}])
        if request.method == "PATCH":
            return httpx.Response(200, json={"login": "lgao"})
        if request.method == "POST":
            return httpx.Response(201, json={"login": "lgao"})
        return httpx.Response(200, json={"login": "lgao"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = GiteaClient("http://gitea.test", token="admin-token", client=http)
        assert (await client.get_user("lgao"))["login"] == "lgao"
        await client.create_user("lgao", "aoingl@gmail.com", "password", full_name="Lin Gao")
        await client.update_user("lgao", full_name="Lin Gao", email="aoingl@gmail.com")
        keys = await client.list_user_keys("lgao")
        assert keys[0]["key"].startswith("ssh-ed25519")
        await client.add_user_key("lgao", "Aura host", "ssh-ed25519 AAAA test")
        token = await client.create_user_token("lgao", "password")
        assert token["sha1"] == "token-123"

    paths = [(method, path) for method, path, _auth, _body in requests]
    assert ("POST", "/api/v1/admin/users") in paths
    assert ("PATCH", "/api/v1/admin/users/lgao") in paths
    assert ("GET", "/api/v1/users/lgao/keys") in paths
    assert ("POST", "/api/v1/admin/users/lgao/keys") in paths
    assert ("POST", "/api/v1/users/lgao/tokens") in paths
    token_request = next(item for item in requests if item[1].endswith("/tokens"))
    assert token_request[2] is not None
    assert token_request[2].startswith("Basic ")
    assert token_request[3] == {"name": "aura-onboarding", "scopes": ["all"]}
