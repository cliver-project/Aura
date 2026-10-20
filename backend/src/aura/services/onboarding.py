"""First-run onboarding: Gitea identity, SSH key, and Git config."""

from __future__ import annotations

import contextlib
import getpass
import os
import pwd
import re
import socket
import subprocess
import time
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from aura.config import get_settings
from aura.models import AppSetting
from aura.schemas import (
    GiteaIdentityRequest,
    GitIdentityRequest,
    OnboardingGiteaInfo,
    OnboardingGitInfo,
    OnboardingRagflowInfo,
    OnboardingSshInfo,
    OnboardingSshKey,
    OnboardingStatus,
    OnboardingSuggested,
    RagflowConfigRequest,
)
from aura.services.gitea import GiteaError
from aura.services.languages import apply_gitea_language, apply_ragflow_language
from aura.services.projects import gitea_client
from aura.services.ragflow import RagflowClient, RagflowError
from aura.services.settings_service import SettingsService

ONBOARDING_KEY = "onboarding_completed"
DEFAULT_RAGFLOW_URL = "http://127.0.0.1:9380"
USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,38}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PREFERRED_KEYS = ("id_ed25519.pub", "id_ecdsa.pub", "id_rsa.pub")


class OnboardingError(RuntimeError):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def _run(command: list[str], timeout: float = 20.0) -> str:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise OnboardingError(f"Command failed: {command[0]}: {exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "command failed").strip()
        raise OnboardingError(detail[:500])
    return result.stdout.strip()


def _git_value(key: str) -> str:
    result = subprocess.run(
        ["git", "config", "--global", "--get", key],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def read_git_identity() -> tuple[str, str]:
    return _git_value("user.name"), _git_value("user.email")


def os_full_name() -> str:
    try:
        gecos = pwd.getpwuid(os.getuid()).pw_gecos
    except (KeyError, OSError):
        return ""
    return gecos.split(",")[0].strip()


def suggest_identity() -> OnboardingSuggested:
    try:
        os_user = getpass.getuser()
    except OSError:
        os_user = os.environ.get("USER", "user")
    git_name, git_email = read_git_identity()
    return OnboardingSuggested(
        username=os_user,
        full_name=git_name or os_full_name() or os_user,
        email=git_email,
    )


def validate_username(username: str) -> str:
    normalized = username.strip().lower()
    if not USERNAME_RE.match(normalized):
        raise OnboardingError("Gitea username must use lowercase letters, digits, dots, underscores, or hyphens.")
    return normalized


def validate_email(email: str) -> str:
    normalized = email.strip()
    if not EMAIL_RE.match(normalized):
        raise OnboardingError("Enter a valid email address.")
    return normalized


def reuse_existing_key(
    request_key: str,
    existing_key: str,
    account_email: str,
    existing_email: str,
) -> bool:
    """Keep the current key when only non-account RAGFlow settings changed."""
    return (
        not request_key.strip()
        and bool(existing_key)
        and account_email.strip().lower() == existing_email.strip().lower()
    )


def key_body(public_key: str) -> str:
    parts = public_key.split()
    return " ".join(parts[:2]) if len(parts) >= 2 else ""


def _key_files(ssh_dir: Path) -> list[Path]:
    preferred = [ssh_dir / name for name in PREFERRED_KEYS if (ssh_dir / name).is_file()]
    others = [path for path in sorted(ssh_dir.glob("*.pub")) if path.is_file() and path not in preferred]
    return preferred + others


def _fingerprint(path: Path) -> str:
    try:
        output = _run(["ssh-keygen", "-lf", str(path)])
    except OnboardingError:
        return ""
    parts = output.split()
    return parts[1] if len(parts) >= 2 else ""


def find_public_keys(home: Path | None = None) -> list[OnboardingSshKey]:
    ssh_dir = (home or Path.home()) / ".ssh"
    keys: list[OnboardingSshKey] = []
    for path in _key_files(ssh_dir):
        try:
            text = path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        parts = text.split()
        if len(parts) < 2:
            continue
        keys.append(
            OnboardingSshKey(
                path=str(path),
                type=parts[0],
                comment=" ".join(parts[2:]),
                fingerprint=_fingerprint(path),
            )
        )
    return keys


def find_key_by_path(path_value: str | None, home: Path | None = None) -> OnboardingSshKey:
    ssh_dir = ((home or Path.home()) / ".ssh").resolve()
    if path_value:
        path = Path(path_value).expanduser().resolve()
        if ssh_dir not in path.parents or path.suffix != ".pub" or not path.is_file():
            raise OnboardingError("SSH key must be a public key inside ~/.ssh.")
    else:
        keys = find_public_keys(home)
        if not keys:
            raise OnboardingError("No SSH public key found. Generate one first.")
        return keys[0]

    text = path.read_text(encoding="utf-8").strip()
    parts = text.split()
    if len(parts) < 2:
        raise OnboardingError("The selected file is not a valid SSH public key.")
    return OnboardingSshKey(
        path=str(path),
        type=parts[0],
        comment=" ".join(parts[2:]),
        fingerprint=_fingerprint(path),
    )


def generate_ssh_key(email: str | None = None, home: Path | None = None) -> list[OnboardingSshKey]:
    existing = find_public_keys(home)
    if existing:
        return existing

    ssh_dir = (home or Path.home()) / ".ssh"
    ssh_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    ssh_dir.chmod(0o700)
    private_path = ssh_dir / "id_ed25519"
    if private_path.exists():
        raise OnboardingError(
            "A private key exists at ~/.ssh/id_ed25519 but no public key was found. "
            "Run: ssh-keygen -y -f ~/.ssh/id_ed25519 > ~/.ssh/id_ed25519.pub"
        )
    comment = email or f"{getpass.getuser()}@aura"
    _run(
        [
            "ssh-keygen",
            "-t",
            "ed25519",
            "-N",
            "",
            "-C",
            comment,
            "-f",
            str(private_path),
        ]
    )
    return find_public_keys(home)


def _key_is_registered(local_key: OnboardingSshKey, gitea_keys: list[dict]) -> bool:
    try:
        text = Path(local_key.path).read_text(encoding="utf-8")
    except OSError:
        return False
    body = key_body(text)
    return bool(body) and any(key_body(str(item.get("key") or "")) == body for item in gitea_keys)


async def _gitea_user_info(client, username: str) -> tuple[OnboardingGiteaInfo, list[dict], str]:
    try:
        user = await client.get_user(username)
    except GiteaError as exc:
        if exc.status == 404:
            return (
                OnboardingGiteaInfo(username=username, exists=False),
                [],
                "",
            )
        return (
            OnboardingGiteaInfo(username=username, error=str(exc)[:300]),
            [],
            str(exc),
        )
    try:
        keys = await client.list_user_keys(username)
    except GiteaError:
        keys = []
    return (
        OnboardingGiteaInfo(
            username=username,
            exists=True,
            full_name=str(user.get("full_name") or ""),
            email=str(user.get("email") or ""),
            ssh_key_count=len(keys),
        ),
        keys,
        "",
    )


async def _ragflow_info(runtime: dict) -> OnboardingRagflowInfo:
    settings = get_settings()
    url = str(runtime.get("ragflow_url") or DEFAULT_RAGFLOW_URL).rstrip("/")
    key = str(runtime.get("ragflow_api_key") or "")
    suggested_email = suggest_identity().email
    account_email = str(runtime.get("ragflow_account_email") or suggested_email)
    account_password = str(
        runtime.get("ragflow_account_password")
        or settings.ragflow_account_password
        or settings.gitea_password
    )
    info = OnboardingRagflowInfo(
        url=url,
        web_url=settings.ragflow_web_url,
        account_email=account_email,
        account_password_configured=bool(account_password),
        api_key_configured=bool(key),
    )
    client = RagflowClient(
        url,
        api_key=key,
        account_email=account_email,
        account_password=account_password,
        timeout=5.0,
    )
    try:
        info.healthy = await client.health()
        if not info.healthy:
            info.error = "RAGFlow is not reachable at this URL."
        elif key:
            await client.list_datasets(page_size=1)
            info.key_valid = True
    except RagflowError as exc:
        info.error = str(exc)[:300]
    return info


async def get_status(session: AsyncSession) -> OnboardingStatus:
    runtime = await SettingsService.effective_raw(session)
    os_user = getpass.getuser()
    suggested = suggest_identity()
    gitea_username = str(runtime.get("gitea_user") or os_user)
    git_name, git_email = read_git_identity()
    local_keys = find_public_keys()

    gitea_info = OnboardingGiteaInfo(username=gitea_username)
    gitea_keys: list[dict] = []
    gitea_error = ""
    try:
        client = gitea_client(runtime)
        gitea_info, gitea_keys, gitea_error = await _gitea_user_info(client, gitea_username)
    except Exception as exc:  # noqa: BLE001 - status must not fail when Gitea is down
        gitea_error = str(exc)[:300]
        gitea_info = OnboardingGiteaInfo(username=gitea_username, error=gitea_error)

    for key in local_keys:
        key.registered = _key_is_registered(key, gitea_keys)

    ssh_info = OnboardingSshInfo(
        keys=local_keys,
        any_registered=any(key.registered for key in local_keys),
    )
    matches_gitea = bool(git_email and gitea_info.email and git_email.lower() == gitea_info.email.lower())
    git_info = OnboardingGitInfo(
        user_name=git_name,
        user_email=git_email,
        matches_gitea=matches_gitea,
    )

    identity_ok = bool(gitea_info.exists and gitea_info.full_name.strip() and gitea_info.email.strip())
    git_ok = bool(git_name and git_email and matches_gitea)
    ragflow_info = await _ragflow_info(runtime)
    ragflow_ok = ragflow_info.healthy and ragflow_info.key_valid
    inferred = identity_ok and ssh_info.any_registered and git_ok and ragflow_ok

    row = await session.get(AppSetting, ONBOARDING_KEY)
    if row is not None:
        completed = bool(row.value) and ragflow_ok
    else:
        completed = inferred
        if completed:
            session.add(AppSetting(key=ONBOARDING_KEY, value=True))
            await session.commit()

    missing: list[str] = []
    if not identity_ok:
        missing.append("gitea_identity")
    if not ssh_info.any_registered:
        missing.append("ssh_key")
    if not git_ok:
        missing.append("git_identity")
    if not ragflow_ok:
        missing.append("ragflow")

    return OnboardingStatus(
        completed=completed,
        os_user=os_user,
        suggested=suggested,
        gitea=gitea_info,
        git=git_info,
        ssh=ssh_info,
        ragflow=ragflow_info,
        missing=missing,
    )


async def configure_gitea_user(session: AsyncSession, request: GiteaIdentityRequest) -> OnboardingStatus:
    username = validate_username(request.username)
    email = validate_email(request.email)
    full_name = request.full_name.strip() or username
    password = get_settings().gitea_password
    if not password:
        raise OnboardingError("Gitea admin password is not configured. Run: make bootstrap")

    runtime = await SettingsService.effective_raw(session)
    client = gitea_client(runtime)
    created = False
    try:
        await client.get_user(username)
    except GiteaError as exc:
        if exc.status != 404:
            raise OnboardingError(str(exc), 502) from exc
        try:
            await client.create_user(
                username=username,
                email=email,
                password=password,
                full_name=full_name,
                login_name=username,
                must_change_password=False,
                send_notify=False,
                source_id=0,
            )
        except GiteaError as create_error:
            if create_error.status == 422:
                raise OnboardingError(
                    "Gitea could not create the account. The email or username may already be used by another account."
                ) from create_error
            raise OnboardingError(str(create_error), 502) from create_error
        created = True

    try:
        await client.update_user(
            username,
            full_name=full_name,
            email=email,
            login_name=username,
            source_id=0,
        )
    except GiteaError as exc:
        raise OnboardingError(str(exc), 502) from exc

    # Best effort: the account is the single human owner.
    with contextlib.suppress(GiteaError):
        await client.update_user(username, admin=True)

    updates: dict[str, object] = {
        "gitea_user": username,
        "gitea_owner": username,
    }
    if created or str(runtime.get("gitea_user") or "") != username:
        try:
            token_response = await client.create_user_token(
                username,
                password,
                name=f"aura-onboarding-{int(time.time())}",
            )
            token = str(token_response.get("sha1") or "")
            if token:
                updates["gitea_token"] = token
        except GiteaError:
            # The existing admin token still works for repository operations.
            pass

    try:
        await SettingsService.update(session, updates)
    except PermissionError as exc:
        raise OnboardingError(
            "Gitea identity is pinned by the process environment. Update the environment and restart Aura."
        ) from exc
    updated_runtime = await SettingsService.effective_raw(session)
    await apply_gitea_language(
        updated_runtime,
        str(updated_runtime.get("gitea_language") or get_settings().gitea_language),
    )
    return await get_status(session)


async def register_ssh_key(session: AsyncSession, path_value: str | None) -> OnboardingStatus:
    runtime = await SettingsService.effective_raw(session)
    username = str(runtime.get("gitea_user") or getpass.getuser())
    key = find_key_by_path(path_value)
    client = gitea_client(runtime)
    try:
        await client.add_user_key(
            username,
            title=f"Aura {socket.gethostname()}",
            key=Path(key.path).read_text(encoding="utf-8").strip(),
        )
    except GiteaError as exc:
        if exc.status not in (409, 422):
            raise OnboardingError(str(exc), 502) from exc

    try:
        gitea_keys = await client.list_user_keys(username)
    except GiteaError as exc:
        raise OnboardingError(str(exc), 502) from exc
    if not _key_is_registered(key, gitea_keys):
        raise OnboardingError("Gitea did not register the SSH key. Try again.", 502)
    return await get_status(session)


async def set_git_identity(session: AsyncSession, request: GitIdentityRequest) -> OnboardingStatus:
    name = request.user_name.strip()
    email = validate_email(request.user_email)
    if not name:
        raise OnboardingError("Git user name cannot be empty.")
    try:
        _run(["git", "config", "--global", "user.name", name])
        _run(["git", "config", "--global", "user.email", email])
    except OnboardingError as exc:
        raise OnboardingError(f"Could not update global Git config: {exc}", 500) from exc
    return await get_status(session)


async def configure_ragflow(session: AsyncSession, request: RagflowConfigRequest) -> OnboardingStatus:
    settings = get_settings()
    runtime = await SettingsService.effective_raw(session)
    url = request.url.strip().rstrip("/")
    if not url.startswith(("http://", "https://")):
        raise OnboardingError("RAGFlow URL must start with http:// or https://.")
    suggested_email = suggest_identity().email
    account_email = request.account_email.strip() or str(
        runtime.get("ragflow_account_email") or suggested_email
    )
    if not account_email:
        raise OnboardingError("RAGFlow account email is required.")
    if not EMAIL_RE.match(account_email):
        raise OnboardingError("Tenant email is not a valid email address.")
    account_password = request.account_password or str(
        runtime.get("ragflow_account_password")
        or settings.ragflow_account_password
        or settings.gitea_password
        or "aura"
    )
    client = RagflowClient(
        url,
        api_key=request.api_key.strip(),
        account_email=account_email,
        account_password=account_password,
        timeout=10.0,
    )
    try:
        if not await client.health():
            raise OnboardingError("RAGFlow is not reachable. Start it with `make rag-up` and try again.")
        existing_key = str(runtime.get("ragflow_api_key") or "")
        existing_email = str(runtime.get("ragflow_account_email") or "")
        key = request.api_key.strip()
        if key:
            client.api_key = key
            await client.list_datasets(page_size=1)
        elif reuse_existing_key(key, existing_key, account_email, existing_email):
            client.api_key = existing_key
            await client.list_datasets(page_size=1)
            key = existing_key
        elif request.auto_create:
            key = await client.create_api_key(name="aura")
        else:
            raise OnboardingError("Paste a RAGFlow API key or enable auto-create.")
    except RagflowError as exc:
        raise OnboardingError(
            f"RAGFlow setup failed: {exc}. You can also create an API key in the "
            f"RAGFlow UI at {settings.ragflow_web_url} and paste it here.",
            502,
        ) from exc

    await SettingsService.update(
        session,
        {
            "ragflow_url": url,
            "ragflow_api_key": key,
            "ragflow_account_email": account_email,
            "ragflow_account_password": account_password,
        },
    )
    updated_runtime = await SettingsService.effective_raw(session)
    await apply_ragflow_language(
        updated_runtime,
        str(updated_runtime.get("ragflow_language") or settings.ragflow_language),
    )
    return await get_status(session)


async def complete_onboarding(session: AsyncSession) -> OnboardingStatus:
    status = await get_status(session)
    if status.missing:
        raise OnboardingError("Complete these steps first: " + ", ".join(status.missing), 409)
    row = await session.get(AppSetting, ONBOARDING_KEY)
    if row is None:
        session.add(AppSetting(key=ONBOARDING_KEY, value=True))
    else:
        row.value = True
    await session.commit()
    status.completed = True
    return status


async def reset_onboarding(session: AsyncSession) -> OnboardingStatus:
    row = await session.get(AppSetting, ONBOARDING_KEY)
    if row is None:
        session.add(AppSetting(key=ONBOARDING_KEY, value=False))
    else:
        row.value = False
    await session.commit()
    return await get_status(session)
