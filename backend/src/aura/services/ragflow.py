"""Small RAGFlow v1.0.x HTTP client used for onboarding and knowledge status."""

from __future__ import annotations

from typing import Any

import httpx


class RagflowError(RuntimeError):
    """RAGFlow request or authentication failed."""


class RagflowClient:
    def __init__(
        self,
        base_url: str,
        api_key: str = "",
        account_email: str = "",
        account_password: str = "",
        timeout: float = 10.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.account_email = account_email
        self.account_password = account_password
        self.timeout = timeout
        self._client = client

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        request_headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if headers:
            request_headers.update(headers)
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self.timeout)
        try:
            response = await client.request(
                method,
                f"{self.base_url}{path}",
                json=json,
                params=params,
                headers=request_headers,
            )
        except httpx.HTTPError as exc:
            raise RagflowError(f"RAGFlow request failed: {exc}") from exc
        finally:
            if owns_client:
                await client.aclose()
        if response.status_code >= 400:
            raise RagflowError(f"RAGFlow {method} {path} returned {response.status_code}: {response.text[:500]}")
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError as exc:
            raise RagflowError("RAGFlow returned a non-JSON response") from exc

    async def _post_for_session(self, path: str, payload: dict[str, Any]) -> str:
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self.timeout)
        try:
            response = await client.post(
                f"{self.base_url}{path}",
                json=payload,
                headers={"Accept": "application/json", "Content-Type": "application/json"},
            )
        except httpx.HTTPError as exc:
            raise RagflowError(f"RAGFlow request failed: {exc}") from exc
        finally:
            if owns_client:
                await client.aclose()
        if response.status_code >= 400:
            raise RagflowError(f"RAGFlow {path} returned {response.status_code}: {response.text[:500]}")
        token = response.headers.get("authorization")
        if not token:
            raise RagflowError("RAGFlow returned no Authorization header")
        return token

    async def health(self) -> bool:
        try:
            await self._request("GET", "/api/v1/system/healthz")
            return True
        except RagflowError:
            return False

    async def login(self) -> str:
        """Log in as the configured tenant account and return the session header.

        RAGFlow's Go API accepts the plaintext password and RSA-encrypts it in
        the browser. Sending base64 here would make the stored hash differ from
        the one the Web UI produces, so the UI login would fail.
        """
        return await self._post_for_session(
            "/api/v1/auth/login",
            {"email": self.account_email, "password": self.account_password},
        )

    async def register(self) -> str:
        """Create the configured tenant account if it does not exist yet."""
        return await self._post_for_session(
            "/api/v1/users",
            {
                "email": self.account_email,
                "password": self.account_password,
                "nickname": "Aura",
            },
        )

    async def create_api_key(self, name: str = "aura") -> str:
        """Create an API key for the configured tenant account.

        RAGFlow v1.0 refuses the token endpoint for a superuser, so the key
        belongs to a normal tenant owner. The account is registered on first
        use and logged in on later runs.
        """
        try:
            session_token = await self.login()
        except RagflowError:
            try:
                session_token = await self.register()
            except RagflowError as exc:
                raise RagflowError(
                    "RAGFlow login and automatic registration both failed. "
                    "If the existing account uses a different password, update it and retry."
                ) from exc
        data = await self._request(
            "POST",
            "/api/v1/system/tokens",
            json={"name": name},
            headers={"Authorization": session_token},
        )
        payload = data.get("data") if isinstance(data, dict) else None
        token = payload.get("token") if isinstance(payload, dict) else None
        if not token:
            raise RagflowError("RAGFlow did not return an API token")
        return str(token)

    async def list_datasets(self, page_size: int = 100) -> list[dict[str, Any]]:
        if not self.api_key:
            raise RagflowError("RAGFlow API key is not configured")
        data = await self._request(
            "GET",
            "/api/v1/datasets",
            params={"page_size": page_size},
            headers={"Authorization": f"Bearer {self.api_key}"},
        )
        if isinstance(data, dict):
            items = data.get("data")
            return items if isinstance(items, list) else []
        return data if isinstance(data, list) else []

    async def update_language(self, language: str) -> None:
        if not self.api_key:
            raise RagflowError("RAGFlow API key is not configured")
        await self._request(
            "PATCH",
            "/api/v1/users/me",
            json={"language": language},
            headers={"Authorization": f"Bearer {self.api_key}"},
        )

    async def ensure_api_key(self) -> str:
        if self.api_key:
            await self.list_datasets(page_size=1)
            return self.api_key
        return await self.create_api_key()
