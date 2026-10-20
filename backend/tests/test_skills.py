import pytest

from aura.services.skills_service import (
    SkillError,
    SkillReadOnlyError,
    SkillsService,
    parse_skill_file,
)


def _write_skill(root, name: str, description: str = "Demo skill") -> None:
    directory = root / name
    directory.mkdir(parents=True)
    (directory / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n# Skill\n",
        encoding="utf-8",
    )


def test_parse_skill_frontmatter(tmp_path) -> None:
    _write_skill(tmp_path, "demo-skill", "Does a demo")
    info = parse_skill_file(tmp_path / "demo-skill" / "SKILL.md", "builtin")
    assert info is not None
    assert info.name == "demo-skill"
    assert info.description == "Does a demo"
    assert info.read_only is False


def test_user_skill_overrides_builtin_and_is_read_only(tmp_path) -> None:
    builtin = tmp_path / "builtin"
    user = tmp_path / "user"
    _write_skill(builtin, "demo", "builtin version")
    _write_skill(user, "demo", "user version")
    service = SkillsService(
        root=builtin,
        user_root=user,
        project_root=tmp_path / "project",
    )
    infos = service.scan_filesystem()
    assert len(infos) == 1
    assert infos[0].description == "user version"
    assert infos[0].source == "user"
    assert infos[0].read_only is True


def test_project_skill_wins_over_user_and_builtin(tmp_path) -> None:
    builtin = tmp_path / "builtin"
    user = tmp_path / "user"
    project = tmp_path / "project"
    _write_skill(builtin, "demo", "builtin version")
    _write_skill(user, "demo", "user version")
    _write_skill(project, "demo", "project version")
    service = SkillsService(root=builtin, user_root=user, project_root=project)
    infos = service.scan_filesystem()
    assert len(infos) == 1
    assert infos[0].description == "project version"
    assert infos[0].source == "project"
    assert infos[0].read_only is True


def test_create_and_materialize_skill(tmp_path) -> None:
    root = tmp_path / "skills"
    service = SkillsService(
        root=root,
        user_root=tmp_path / "user",
        project_root=tmp_path / "project",
    )
    content = "---\nname: new-skill\ndescription: New\n---\n\n# New\n"
    info = service.create("new-skill", content)
    assert info.name == "new-skill"
    assert info.read_only is False

    workspace = tmp_path / "workspace"
    links = service.materialize(["new-skill"], workspace)
    assert len(links) == 1
    assert links[0].is_symlink()
    assert (workspace / ".claude" / "skills" / "new-skill" / "SKILL.md").exists()


def test_invalid_skill_name_is_rejected(tmp_path) -> None:
    service = SkillsService(
        root=tmp_path / "skills",
        user_root=tmp_path / "user",
        project_root=tmp_path / "project",
    )
    with pytest.raises(SkillError):
        service.create("../escape", "---\nname: x\n---\n")


def test_update_external_skill_is_rejected(tmp_path) -> None:
    user = tmp_path / "user"
    _write_skill(user, "external", "user version")
    service = SkillsService(
        root=tmp_path / "builtin",
        user_root=user,
        project_root=tmp_path / "project",
    )
    with pytest.raises(SkillReadOnlyError):
        service.update("external", "---\nname: external\ndescription: changed\n---\n")


def test_create_rejects_existing_external_name(tmp_path) -> None:
    user = tmp_path / "user"
    _write_skill(user, "external", "user version")
    service = SkillsService(
        root=tmp_path / "builtin",
        user_root=user,
        project_root=tmp_path / "project",
    )
    with pytest.raises(SkillError):
        service.create("external", "---\nname: external\ndescription: duplicate\n---\n")


def test_builtin_skill_is_editable(tmp_path) -> None:
    service = SkillsService(
        root=tmp_path / "builtin",
        user_root=tmp_path / "user",
        project_root=tmp_path / "project",
    )
    service.create("editable", "---\nname: editable\ndescription: one\n---\n")
    updated = service.update("editable", "---\nname: editable\ndescription: two\n---\n")
    assert updated.description == "two"
    assert updated.read_only is False
