"""Per-run Git clones with credential-safe push helpers."""

from __future__ import annotations

import asyncio
import os
import shutil
from pathlib import Path
from urllib.parse import quote, urlparse, urlunparse

from aura.config import get_settings


class GitError(RuntimeError):
    """A Git command failed."""


def authenticated_url(repo_url: str, token: str = "", username: str = "aura") -> str:
    """Return a clone/push URL with credentials, without persisting it."""
    if not token:
        return repo_url
    parsed = urlparse(repo_url)
    host = parsed.hostname or "localhost"
    port = f":{parsed.port}" if parsed.port else ""
    netloc = f"{quote(username, safe='')}:{quote(token, safe='')}@{host}{port}"
    return urlunparse(parsed._replace(netloc=netloc))


def redact(text: str, token: str) -> str:
    return text.replace(token, "***") if token else text


AGENT_EXCLUDES = (".claude/", ".mcp.json", ".aura/")


def ensure_agent_excludes(repo: Path) -> None:
    """Keep agent-local files out of ``git add -A`` even if .gitignore misses them."""
    info_dir = repo / ".git" / "info"
    info_dir.mkdir(parents=True, exist_ok=True)
    exclude = info_dir / "exclude"
    try:
        lines = exclude.read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []
    missing = [line for line in AGENT_EXCLUDES if line not in lines]
    if not missing:
        return
    with exclude.open("a", encoding="utf-8") as handle:
        if lines and lines[-1].strip():
            handle.write("\n")
        for line in missing:
            handle.write(f"{line}\n")


async def _git(
    cwd: Path,
    *args: str,
    token: str = "",
    timeout: float = 180.0,
    check: bool = True,
) -> tuple[int, str, str]:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    safe_command = redact(" ".join(args), token)
    process = await asyncio.create_subprocess_exec(
        "git",
        *args,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except TimeoutError as exc:
        process.kill()
        await process.wait()
        raise GitError(f"git {safe_command} timed out") from exc

    out = redact(stdout.decode("utf-8", errors="replace"), token)
    err = redact(stderr.decode("utf-8", errors="replace"), token)
    if check and process.returncode != 0:
        raise GitError(f"git {safe_command} failed ({process.returncode}): {err.strip()}")
    return process.returncode, out, err


class GitWorkspace:
    """Create and manipulate one isolated clone per agent run."""

    def __init__(self, root: Path | None = None) -> None:
        # Resolve once: a relative workspace root combined with a relative
        # subprocess cwd would otherwise be interpreted twice.
        self.root = (root or get_settings().workspace_dir).expanduser().resolve()

    def path_for(self, run_id: str) -> Path:
        return self.root / run_id

    async def prepare(
        self,
        repo_url: str,
        branch: str,
        run_id: str,
        token: str = "",
        username: str = "aura",
    ) -> Path:
        target = self.path_for(run_id)
        if target.exists():
            shutil.rmtree(target)
        target.parent.mkdir(parents=True, exist_ok=True)

        clone_url = authenticated_url(repo_url, token, username)
        # A full clone (not shallow) keeps origin/main available so verification
        # and code review can compute diffs against the base branch. Workspace
        # repositories are small; clone cost is negligible.
        code, _, err = await _git(
            target.parent,
            "clone",
            "--branch",
            branch,
            clone_url,
            str(target),
            token=token,
        )
        if code != 0:
            # Empty repositories have no branch to clone yet.
            await _git(target.parent, "clone", clone_url, str(target), token=token)
            await _git(target, "checkout", "-B", branch, token=token)

        # Never persist the token in .git/config. Pushes re-inject it for the
        # duration of a single command.
        await _git(target, "remote", "set-url", "origin", repo_url, token=token)
        ensure_agent_excludes(target)
        return target

    async def create_branch(self, path: Path, branch: str) -> None:
        await _git(path, "checkout", "-B", branch)

    async def commit_all(
        self,
        path: Path,
        message: str,
        author_name: str = "Aura Agent",
        author_email: str = "aura@local",
    ) -> str | None:
        await _git(path, "add", "-A")
        _, status, _ = await _git(path, "status", "--porcelain")
        if not status.strip():
            return None
        await _git(
            path,
            "-c",
            f"user.name={author_name}",
            "-c",
            f"user.email={author_email}",
            "commit",
            "-m",
            message,
        )
        _, sha, _ = await _git(path, "rev-parse", "HEAD")
        return sha.strip()

    async def push(
        self,
        path: Path,
        branch: str,
        token: str = "",
        username: str = "aura",
    ) -> None:
        _, remote, _ = await _git(path, "remote", "get-url", "origin")
        push_url = authenticated_url(remote.strip(), token, username)
        await _git(path, "push", push_url, f"HEAD:refs/heads/{branch}", token=token)

    async def head_sha(self, path: Path) -> str:
        _, sha, _ = await _git(path, "rev-parse", "HEAD")
        return sha.strip()

    async def commits_ahead(self, path: Path, base_ref: str = "origin/main") -> int:
        code, output, _ = await _git(path, "rev-list", "--count", f"{base_ref}..HEAD", check=False)
        value = output.strip()
        return int(value) if code == 0 and value.isdigit() else 0

    async def current_branch(self, path: Path) -> str:
        _, name, _ = await _git(path, "rev-parse", "--abbrev-ref", "HEAD")
        return name.strip()

    async def diff(self, path: Path, base_ref: str = "origin/main") -> str:
        try:
            _, output, _ = await _git(path, "diff", f"{base_ref}...HEAD")
            return output
        except GitError:
            _, output, _ = await _git(path, "diff", "HEAD~1...HEAD", check=False)
            return output

    def cleanup(self, path: Path) -> None:
        shutil.rmtree(path, ignore_errors=True)
