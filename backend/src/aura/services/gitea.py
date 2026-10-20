"""Minimal async Gitea API client used by the control plane."""

from __future__ import annotations

from typing import Any

import httpx


class GiteaError(RuntimeError):
    def __init__(self, message: str, status: int = 0) -> None:
        super().__init__(message)
        self.status = status


class GiteaClient:
    def __init__(
        self,
        base_url: str,
        token: str = "",
        username: str = "",
        password: str = "",
        timeout: float = 30.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.username = username
        self.password = password
        self._client = client
        self._timeout = timeout

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        return headers

    def _auth(self) -> httpx.BasicAuth | None:
        if not self.token and self.username and self.password:
            return httpx.BasicAuth(self.username, self.password)
        return None

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any | None = None,
        params: dict[str, Any] | None = None,
        accept: str | None = None,
        auth: httpx.BasicAuth | None = None,
    ) -> Any:
        headers = self._headers()
        if auth is not None:
            headers.pop("Authorization", None)
        if accept:
            headers["Accept"] = accept
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self._timeout)
        try:
            response = await client.request(
                method,
                f"{self.base_url}{path}",
                json=json,
                params=params,
                headers=headers,
                auth=auth or self._auth(),
            )
        except httpx.HTTPError as exc:
            raise GiteaError(f"Gitea request failed: {exc}") from exc
        finally:
            if owns_client:
                await client.aclose()

        if response.status_code >= 400:
            detail = response.text[:500]
            raise GiteaError(
                f"Gitea {method} {path} returned {response.status_code}: {detail}",
                status=response.status_code,
            )
        if response.status_code == 204 or not response.content:
            return None
        if accept and "diff" in accept:
            return response.text
        return response.json()

    # --- repositories -------------------------------------------------------

    async def create_repo(
        self,
        name: str,
        description: str = "",
        private: bool = False,
        auto_init: bool = True,
        default_branch: str = "main",
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/api/v1/user/repos",
            json={
                "name": name,
                "description": description,
                "private": private,
                "auto_init": auto_init,
                "default_branch": default_branch,
            },
        )

    async def get_repo(self, owner: str, repo: str) -> dict[str, Any]:
        return await self._request("GET", f"/api/v1/repos/{owner}/{repo}")

    async def set_default_branch(self, owner: str, repo: str, branch: str = "main") -> None:
        await self._request(
            "PATCH",
            f"/api/v1/repos/{owner}/{repo}",
            json={"default_branch": branch},
        )

    async def delete_repo(self, owner: str, repo: str) -> None:
        await self._request("DELETE", f"/api/v1/repos/{owner}/{repo}")

    # --- users, SSH keys, and tokens ---------------------------------------

    async def get_user(self, username: str) -> dict[str, Any]:
        return await self._request("GET", f"/api/v1/users/{username}")

    async def create_user(
        self,
        username: str,
        email: str,
        password: str,
        full_name: str = "",
        login_name: str = "",
        must_change_password: bool = False,
        send_notify: bool = False,
        source_id: int = 0,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/api/v1/admin/users",
            json={
                "username": username,
                "email": email,
                "password": password,
                "full_name": full_name,
                "login_name": login_name or username,
                "must_change_password": must_change_password,
                "send_notify": send_notify,
                "source_id": source_id,
            },
        )

    async def update_user(self, username: str, **fields: Any) -> dict[str, Any]:
        return await self._request(
            "PATCH",
            f"/api/v1/admin/users/{username}",
            json=fields,
        )

    async def update_current_user_settings(
        self,
        language: str,
        username: str = "",
        password: str = "",
    ) -> dict[str, Any]:
        """PATCH /user/settings for the target user, not the admin token owner."""
        return await self._request(
            "PATCH",
            "/api/v1/user/settings",
            json={"language": language},
            auth=httpx.BasicAuth(username or self.username, password or self.password),
        )

    async def list_user_keys(self, username: str) -> list[dict[str, Any]]:
        return await self._request("GET", f"/api/v1/users/{username}/keys")

    async def add_user_key(
        self,
        username: str,
        title: str,
        key: str,
        read_only: bool = False,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/api/v1/admin/users/{username}/keys",
            json={"title": title, "key": key, "read_only": read_only},
        )

    async def create_user_token(
        self,
        username: str,
        password: str,
        name: str = "aura-onboarding",
        scopes: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create an access token for a user using their Basic credentials.

        The admin token belongs to another account, so this call intentionally
        uses BasicAuth instead of ``self._headers()``.
        """
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self._timeout)
        try:
            response = await client.post(
                f"{self.base_url}/api/v1/users/{username}/tokens",
                auth=httpx.BasicAuth(username, password),
                json={"name": name, "scopes": scopes or ["all"]},
                headers={"Accept": "application/json", "Content-Type": "application/json"},
            )
        except httpx.HTTPError as exc:
            raise GiteaError(f"Gitea token request failed: {exc}") from exc
        finally:
            if owns_client:
                await client.aclose()
        if response.status_code >= 400:
            raise GiteaError(
                f"Gitea token creation returned {response.status_code}: {response.text[:500]}",
                status=response.status_code,
            )
        return response.json()

    # --- pull requests ------------------------------------------------------

    async def create_pull_request(
        self,
        owner: str,
        repo: str,
        title: str,
        head: str,
        base: str,
        body: str = "",
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/api/v1/repos/{owner}/{repo}/pulls",
            json={"title": title, "head": head, "base": base, "body": body},
        )

    async def get_pull_request(self, owner: str, repo: str, index: int) -> dict[str, Any]:
        return await self._request("GET", f"/api/v1/repos/{owner}/{repo}/pulls/{index}")

    async def get_pull_request_diff(self, owner: str, repo: str, index: int) -> str:
        return await self._request(
            "GET",
            f"/api/v1/repos/{owner}/{repo}/pulls/{index}.diff",
            accept="text/plain",
        )

    async def comment_issue(self, owner: str, repo: str, index: int, body: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/api/v1/repos/{owner}/{repo}/issues/{index}/comments",
            json={"body": body},
        )

    async def merge_pull_request(
        self,
        owner: str,
        repo: str,
        index: int,
        message: str = "",
        delete_branch: bool = False,
    ) -> None:
        await self._request(
            "POST",
            f"/api/v1/repos/{owner}/{repo}/pulls/{index}/merge",
            json={
                "Do": "merge",
                "merge_message_field": message,
                "delete_branch_after_merge": delete_branch,
            },
        )

    async def close_pull_request(self, owner: str, repo: str, index: int) -> None:
        await self._request(
            "PATCH",
            f"/api/v1/repos/{owner}/{repo}/pulls/{index}",
            json={"state": "closed"},
        )

    # --- commit statuses ----------------------------------------------------

    async def create_commit_status(
        self,
        owner: str,
        repo: str,
        sha: str,
        state: str,
        target_url: str = "",
        description: str = "",
        context: str = "aura/verification",
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/api/v1/repos/{owner}/{repo}/statuses/{sha}",
            json={
                "state": state,
                "target_url": target_url,
                "description": description[:140],
                "context": context,
            },
        )
