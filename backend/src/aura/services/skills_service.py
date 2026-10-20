"""Filesystem-backed skill library."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aura.config import REPO_ROOT, get_settings
from aura.models import Skill

SKILL_NAME_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


class SkillError(ValueError):
    pass


class SkillReadOnlyError(SkillError):
    pass


@dataclass
class SkillInfo:
    name: str
    description: str
    path: str
    source: str
    content: str = ""
    enabled: bool = True

    @property
    def read_only(self) -> bool:
        """Only Aura-managed ``skills/`` entries are editable."""
        return self.source != "builtin"


def parse_skill_file(path: Path, source: str) -> SkillInfo | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    match = FRONTMATTER.match(text)
    if not match:
        return None
    try:
        metadata = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return None
    if not isinstance(metadata, dict):
        return None
    name = str(metadata.get("name") or path.parent.name)
    description = str(metadata.get("description") or "")
    return SkillInfo(
        name=name,
        description=description,
        path=str(path.parent),
        source=source,
        content=text,
    )


class SkillsService:
    def __init__(
        self,
        root: Path | None = None,
        user_root: Path | None = None,
        project_root: Path | None = None,
    ) -> None:
        settings = get_settings()
        self.root = root or settings.skills_dir
        self.user_root = user_root or (Path.home() / ".claude" / "skills")
        # Project-scoped `npx skills add` installs into .claude/skills.
        self.project_root = project_root or (REPO_ROOT / ".claude" / "skills")

    def _roots(self) -> list[tuple[Path, str]]:
        # Highest precedence first: project > user > built-in.
        return [
            (self.project_root, "project"),
            (self.user_root, "user"),
            (self.root, "builtin"),
        ]

    def scan_filesystem(self) -> list[SkillInfo]:
        """Discover skills. Project skills override user and built-in skills."""
        found: dict[str, SkillInfo] = {}
        # Iterate lowest precedence first so the highest wins on duplicate names.
        for root, source in reversed(self._roots()):
            if not root.exists():
                continue
            for skill_file in sorted(root.glob("*/SKILL.md")):
                info = parse_skill_file(skill_file, source)
                if info is not None:
                    found[info.name] = info
        return sorted(found.values(), key=lambda item: item.name)

    async def refresh(self, session: AsyncSession) -> list[SkillInfo]:
        infos = self.scan_filesystem()
        rows = {row.name: row for row in (await session.execute(select(Skill))).scalars().all()}
        for info in infos:
            row = rows.get(info.name)
            if row is None:
                row = Skill(
                    name=info.name,
                    description=info.description,
                    path=info.path,
                    source=info.source,
                    enabled=True,
                )
                session.add(row)
                rows[info.name] = row
            else:
                row.description = info.description
                row.path = info.path
                row.source = info.source
            info.enabled = row.enabled
        current_names = {info.name for info in infos}
        for name, row in rows.items():
            if name not in current_names:
                await session.delete(row)
        await session.commit()
        return infos

    async def list(self, session: AsyncSession) -> list[SkillInfo]:
        return await self.refresh(session)

    def create(self, name: str, content: str) -> SkillInfo:
        self._validate_name(name)
        if self.resolve(name) is not None:
            raise SkillError(f"Skill already exists: {name}")
        directory = self.root / name
        skill_file = directory / "SKILL.md"
        directory.mkdir(parents=True, exist_ok=True)
        skill_file.write_text(content, encoding="utf-8")
        info = parse_skill_file(skill_file, "builtin")
        if info is None:
            skill_file.unlink()
            directory.rmdir()
            raise SkillError("Skill content must begin with YAML front matter.")
        return info

    def update(self, name: str, content: str) -> SkillInfo:
        self._validate_name(name)
        info = next((item for item in self.scan_filesystem() if item.name == name), None)
        if info is None:
            raise SkillError(f"Skill not found: {name}")
        if info.source != "builtin":
            raise SkillReadOnlyError(f"Skill '{name}' was installed outside Aura and is read-only.")
        skill_file = self.root / name / "SKILL.md"
        if not skill_file.exists():
            raise SkillError(f"Skill not found: {name}")
        skill_file.write_text(content, encoding="utf-8")
        info = parse_skill_file(skill_file, "builtin")
        if info is None:
            raise SkillError("Skill content must begin with YAML front matter.")
        return info

    def _validate_name(self, name: str) -> None:
        if not SKILL_NAME_PATTERN.match(name) or ".." in name or "/" in name:
            raise SkillError("Skill name must be lowercase kebab-case.")

    def resolve(self, name: str) -> Path | None:
        for info in self.scan_filesystem():
            if info.name == name:
                return Path(info.path)
        return None

    def read(self, name: str) -> str:
        path = self.resolve(name)
        if path is None:
            raise SkillError(f"Skill not found: {name}")
        return (path / "SKILL.md").read_text(encoding="utf-8")

    def materialize(self, skill_names: list[str], workspace: Path) -> list[Path]:
        """Symlink selected skills into the run workspace for Claude discovery."""
        target_root = workspace / ".claude" / "skills"
        materialized: list[Path] = []
        for name in skill_names:
            source = self.resolve(name)
            if source is None:
                continue
            target_root.mkdir(parents=True, exist_ok=True)
            link = target_root / name
            if link.exists() or link.is_symlink():
                link.unlink()
            link.symlink_to(source, target_is_directory=True)
            materialized.append(link)
        return materialized
