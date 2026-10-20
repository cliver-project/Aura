from aura.services.projects import slugify
from aura.services.repo_seed import seed_files


def test_slugify() -> None:
    assert slugify("My Content Site!") == "my-content-site"
    assert slugify("  ").startswith("project-")


def test_python_web_seed_contains_required_files() -> None:
    files = seed_files("Demo", "demo", "A demo", "python-web")
    for path in (
        "README.md",
        "CLAUDE.md",
        ".gitignore",
        "pyproject.toml",
        "app/main.py",
        "app/templates/index.html",
        "tests/test_health.py",
        ".gitea/workflows/ci.yml",
        "docs/requirements/.gitkeep",
        "docs/specs/.gitkeep",
        "docs/reviews/.gitkeep",
        "docs/reports/.gitkeep",
    ):
        assert path in files
    # Global conventions live in the user-level ~/.claude/CLAUDE.md, not in
    # every generated project repository. The docs/superpowers convention is
    # specific to the Aura repository and is not imposed on generated projects.
    assert "Write all code, code comments" not in files["CLAUDE.md"]
    assert "docs/superpowers/" not in files[".gitignore"]
    assert "pytest" in files["CLAUDE.md"]


def test_blank_seed_has_no_python_app() -> None:
    files = seed_files("Demo", "demo", "", "blank")
    assert "pyproject.toml" not in files
    assert "app/main.py" not in files
    assert "CLAUDE.md" in files
