import pytest

from aura.services.git_workspace import GitError, _git, ensure_agent_excludes


async def test_git_error_does_not_include_token(tmp_path) -> None:
    with pytest.raises(GitError) as exc:
        await _git(
            tmp_path,
            "not-a-real-command",
            "http://user:secret-token@example/repo.git",
            token="secret-token",
        )
    message = str(exc.value)
    assert "secret-token" not in message
    assert "***" in message


def test_ensure_agent_excludes_adds_agent_paths(tmp_path) -> None:
    (tmp_path / ".git" / "info").mkdir(parents=True)
    exclude = tmp_path / ".git" / "info" / "exclude"
    exclude.write_text("existing\n", encoding="utf-8")
    ensure_agent_excludes(tmp_path)
    text = exclude.read_text(encoding="utf-8")
    assert "existing" in text
    assert ".claude/" in text
    assert ".mcp.json" in text
    assert ".aura/" in text


def test_ensure_agent_excludes_is_idempotent(tmp_path) -> None:
    (tmp_path / ".git" / "info").mkdir(parents=True)
    exclude = tmp_path / ".git" / "info" / "exclude"
    exclude.write_text("", encoding="utf-8")
    ensure_agent_excludes(tmp_path)
    first = exclude.read_text(encoding="utf-8")
    ensure_agent_excludes(tmp_path)
    assert exclude.read_text(encoding="utf-8") == first
