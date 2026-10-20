"""Seed files for a newly created project repository."""

from __future__ import annotations

from pathlib import Path

DOC_DIRECTORIES = (
    "docs/requirements",
    "docs/specs",
    "docs/reviews",
    "docs/reports",
)

COMMON_CLAUDE_MD = """# Project Instructions

This project is developed and maintained with Aura agents.

## Rules

- Read this file and the technical specification before changing code.
- Keep changes focused; do not rewrite unrelated code.
- Never commit secrets, `.env` files, tokens, or local credentials.
- The human owner is the only person who merges pull requests.
- When you are an autonomous agent, do not ask questions. Make a reasonable
  assumption and record it in the deliverable.

## Documentation layout

- `docs/requirements/` - versioned requirement documents.
- `docs/specs/` - technical specifications.
- `docs/reviews/` - adversarial reviews and responses.
- `docs/reports/` - verification reports.

## Commands
"""

PYTHON_WEB_CLAUDE = """
```sh
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest -q
.venv/bin/uvicorn app.main:app --reload
```
""".strip()

BLANK_CLAUDE = """
No build system is defined yet. The technical specification must choose one and
update this file with the exact build, test, and run commands.
""".strip()

PYPROJECT = """[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "{slug}"
version = "0.1.0"
description = "{description}"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "jinja2>=3.1",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3",
    "httpx>=0.27",
]

[tool.setuptools.packages.find]
include = ["app*"]

[tool.setuptools.package-data]
app = ["templates/*.html"]

[tool.pytest.ini_options]
testpaths = ["tests"]
"""

APP_MAIN = """from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

app = FastAPI(title="{name}")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@app.get("/health")
def health() -> dict[str, str]:
    return {{"status": "ok"}}


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={{"title": "{name}"}},
    )
"""

APP_INIT = '"""Application package."""\n'

INDEX_HTML = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{{ title }}</title>
    <style>
      body { font-family: system-ui, sans-serif; max-width: 42rem; margin: 4rem auto; padding: 0 1rem; }
      h1 { font-size: 1.75rem; }
      code { background: #f2f2f2; padding: 0.1rem 0.3rem; border-radius: 0.25rem; }
    </style>
  </head>
  <body>
    <h1>{{ title }}</h1>
    <p>This starter page was created by Aura. The implementation agents will extend it.</p>
    <p>Health endpoint: <code>/health</code></p>
  </body>
</html>
"""

TEST_HEALTH = """from fastapi.testclient import TestClient

from app.main import app


def test_health() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
"""

CI_WORKFLOW = """name: ci
on:
  push:
  pull_request:
jobs:
  test:
    # The Aura act_runner uses the node:20-bookworm image, which supports
    # actions/checkout but does not ship Python. uv installs a standalone
    # Python 3.12 that matches the project requirement on every host arch.
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install uv
        run: curl -LsSf https://astral.sh/uv/install.sh | sh
      - name: Install and test
        run: |
          export PATH="$HOME/.local/bin:$PATH"
          uv python install 3.12
          uv venv --python 3.12 .venv
          uv pip install --python .venv/bin/python -e ".[dev]"
          .venv/bin/python -m pytest -q
"""

BLANK_CI_WORKFLOW = """name: ci
on:
  push:
  pull_request:
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Placeholder
        run: echo "No build system defined yet."
"""

GITIGNORE = """# Python
__pycache__/
*.py[cod]
.venv/
*.egg-info/
.pytest_cache/
.coverage
htmlcov/

# Node
node_modules/
dist/

# Local
.env
.env.*
!.env.example
.claude/
.aura/
.DS_Store
"""


def seed_files(
    name: str,
    slug: str,
    description: str,
    template: str = "python-web",
) -> dict[str, str]:
    """Return the files for a new repository, keyed by repository-relative path."""
    files: dict[str, str] = {
        "README.md": (
            f"# {name}\n\n{description or 'Created with Aura.'}\n\n"
            "## Documentation\n\n"
            "- `docs/requirements/` - versioned requirements.\n"
            "- `docs/specs/` - technical specifications.\n"
            "- `docs/reviews/` - adversarial reviews.\n"
            "- `docs/reports/` - verification reports.\n"
        ),
        ".gitignore": GITIGNORE,
    }
    for directory in DOC_DIRECTORIES:
        files[f"{directory}/.gitkeep"] = ""

    if template == "python-web":
        files["CLAUDE.md"] = COMMON_CLAUDE_MD + "\n" + PYTHON_WEB_CLAUDE + "\n"
        files["pyproject.toml"] = PYPROJECT.format(slug=slug, description=description.replace('"', "'"))
        files["app/__init__.py"] = APP_INIT
        files["app/main.py"] = APP_MAIN.format(name=name)
        files["app/templates/index.html"] = INDEX_HTML
        files["tests/test_health.py"] = TEST_HEALTH
        files[".gitea/workflows/ci.yml"] = CI_WORKFLOW
    else:
        files["CLAUDE.md"] = COMMON_CLAUDE_MD + "\n" + BLANK_CLAUDE + "\n"
        files[".gitea/workflows/ci.yml"] = BLANK_CI_WORKFLOW

    return files


def write_files(root: Path, files: dict[str, str]) -> None:
    for relative_path, content in files.items():
        target = root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
