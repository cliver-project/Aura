from pathlib import Path

import pytest

from aura.services.onboarding import (
    OnboardingError,
    find_key_by_path,
    find_public_keys,
    generate_ssh_key,
    key_body,
    reuse_existing_key,
    validate_email,
    validate_username,
)


def test_validate_username_normalizes_and_rejects_spaces() -> None:
    assert validate_username("LinGao") == "lingao"
    assert validate_username("lgao") == "lgao"
    with pytest.raises(OnboardingError):
        validate_username("lin gao")
    with pytest.raises(OnboardingError):
        validate_username("lin@example.com")


def test_validate_email() -> None:
    assert validate_email("aoingl@gmail.com") == "aoingl@gmail.com"
    with pytest.raises(OnboardingError):
        validate_email("not-an-email")


def test_key_body_ignores_comment() -> None:
    assert key_body("ssh-ed25519 AAAA comment here") == "ssh-ed25519 AAAA"


def test_find_public_keys(tmp_path) -> None:
    ssh_dir = tmp_path / ".ssh"
    ssh_dir.mkdir()
    (ssh_dir / "id_ed25519.pub").write_text(
        "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExample lgao@host\n",
        encoding="utf-8",
    )
    keys = find_public_keys(tmp_path)
    assert len(keys) == 1
    assert keys[0].type == "ssh-ed25519"
    assert keys[0].comment == "lgao@host"
    assert Path(keys[0].path) == ssh_dir / "id_ed25519.pub"


def test_find_key_by_path_rejects_outside_ssh(tmp_path) -> None:
    outside = tmp_path / "outside.pub"
    outside.write_text("ssh-ed25519 AAAA test", encoding="utf-8")
    with pytest.raises(OnboardingError):
        find_key_by_path(str(outside), tmp_path)


def test_reuse_existing_key_only_for_same_account() -> None:
    assert reuse_existing_key("", "key", "a@b.c", "a@b.c") is True
    assert reuse_existing_key("", "key", "a@b.c", "other@b.c") is False
    assert reuse_existing_key("new", "key", "a@b.c", "a@b.c") is False
    assert reuse_existing_key("", "", "a@b.c", "a@b.c") is False


def test_ragflow_info_does_not_expose_passwords() -> None:
    from aura.schemas import OnboardingRagflowInfo

    assert "admin_password" not in OnboardingRagflowInfo.model_fields
    assert "agent_password" not in OnboardingRagflowInfo.model_fields
    assert "account_password" not in OnboardingRagflowInfo.model_fields


def test_generate_ssh_key(tmp_path) -> None:
    keys = generate_ssh_key("aoingl@gmail.com", tmp_path)
    assert len(keys) == 1
    assert (tmp_path / ".ssh" / "id_ed25519").exists()
    assert (tmp_path / ".ssh" / "id_ed25519.pub").exists()
