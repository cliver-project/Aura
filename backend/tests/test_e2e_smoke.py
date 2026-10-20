"""Real end-to-end smoke test.

Skipped unless AURA_E2E=1. Requires the Docker stack and the backend to be
running. It creates a throwaway project repository through the public API and
verifies that the requirement exists in both PostgreSQL and Gitea.
"""

from __future__ import annotations

import base64
import os
import time

import httpx
import pytest

from aura.config import get_settings

pytestmark = pytest.mark.skipif(
    os.environ.get("AURA_E2E") != "1",
    reason="Set AURA_E2E=1 to run against the live local stack",
)

API = "http://127.0.0.1:8000"


async def test_live_stack_creates_project_and_requirement() -> None:
    settings = get_settings()
    slug = f"aura-e2e-{int(time.time())}"

    async with httpx.AsyncClient(base_url=API, timeout=180.0) as client:
        health = await client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"

        project_response = await client.post(
            "/api/projects",
            json={
                "name": "Aura E2E Demo",
                "slug": slug,
                "description": "Created by the automated smoke test.",
                "template": "python-web",
            },
        )
        assert project_response.status_code == 201, project_response.text
        project = project_response.json()

        requirement_response = await client.post(
            f"/api/projects/{project['id']}/requirements",
            json={
                "title": "Smoke requirement",
                "idea": "A public page with a working health endpoint and one test.",
            },
        )
        assert requirement_response.status_code == 201, requirement_response.text
        requirement = requirement_response.json()
        assert requirement["key"] == "REQ-001"
        assert requirement["current_version"] == 1

        versions = await client.get(f"/api/requirements/{requirement['id']}/versions")
        assert versions.status_code == 200
        assert len(versions.json()) == 1
        assert versions.json()[0]["git_commit"]

    headers = {"Authorization": f"token {settings.gitea_token}"}
    async with httpx.AsyncClient(base_url=settings.gitea_web_url, timeout=30.0) as gitea:
        content = await gitea.get(
            f"/api/v1/repos/{project['repo_owner']}/{project['repo_name']}"
            f"/contents/docs/requirements/{requirement['key']}.md",
            headers=headers,
        )
        assert content.status_code == 200, content.text
        decoded = base64.b64decode(content.json()["content"]).decode("utf-8")
        assert "Smoke requirement" in decoded
