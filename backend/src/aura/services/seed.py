"""Default agent profiles and startup reconciliation helpers."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aura.models import AgentProfile, AppSetting, McpServer

RAGFLOW_MCP_NAME = "ragflow"
RAGFLOW_MCP_URL = "{{ragflow_mcp_url}}"
RAGFLOW_MCP_HEADERS = {"api_key": "{{ragflow_api_key}}"}
LEGACY_RAGFLOW_MCP_URL = "{{ragflow_url}}/api/v1/mcp"
KNOWLEDGE_SKILL = "knowledge-base"
KNOWLEDGE_DEFAULTS_KEY = "knowledge_defaults_applied"
KNOWLEDGE_ROLE_KEYS = frozenset(
    {"ba", "architect", "risk-reviewer", "test-reviewer", "architecture-reviewer"}
)


def knowledge_skill_names(role_key: str, existing: list[str]) -> list[str]:
    if role_key not in KNOWLEDGE_ROLE_KEYS or KNOWLEDGE_SKILL in existing:
        return list(existing)
    return [*existing, KNOWLEDGE_SKILL]


def knowledge_mcp_ids(role_key: str, ragflow_id: str, existing: list[str]) -> list[str]:
    if role_key not in KNOWLEDGE_ROLE_KEYS or not ragflow_id or ragflow_id in existing:
        return list(existing)
    return [*existing, ragflow_id]

COMMON_RULES = """
You are an autonomous agent inside Aura, a local single-user development center.
The human owner is the only decision maker and the only actor allowed to merge
pull requests. Work autonomously: never ask the human a question, never wait for
confirmation, and record reasonable assumptions in your deliverable.

Rules:
- Write code, code comments, commit messages, prompts, and documentation in English.
- Work only inside the repository checkout you were given. Never read or write
  files under the user's home secrets (for example ~/.ssh, ~/.aws, ~/.config).
- Never print, commit, or copy API tokens, passwords, or .env contents.
- Do not run destructive commands against the host. Do not modify Git
  configuration or credentials.
- Read the repository's CLAUDE.md and existing code before changing anything.
- Produce exactly the deliverable named in your task. Extra files are allowed
  only when the task requires them.
""".strip()


def _prompt(role: str, mission: str, extra: str = "") -> str:
    sections = [COMMON_RULES, f"Your role: {role}.", f"Mission: {mission}"]
    if extra:
        sections.append(extra.strip())
    return "\n\n".join(sections)


DEFAULT_AGENTS: list[dict[str, object]] = [
    {
        "role_key": "ceo",
        "name": "CEO Agent",
        "description": "Strategy, priorities, and cross-project direction.",
        "system_prompt": _prompt(
            "Chief Executive Officer",
            "Clarify direction, priorities, and trade-offs. Produce concise, decision-ready briefs.",
        ),
        "skill_names": [],
    },
    {
        "role_key": "cfo",
        "name": "CFO Agent",
        "description": "Budget, cost, and investment analysis.",
        "system_prompt": _prompt(
            "Chief Financial Officer",
            "Analyze cost, budget, and return on investment. Prefer quantified reasoning and explicit assumptions.",
        ),
        "skill_names": [],
    },
    {
        "role_key": "pm",
        "name": "Product Manager Agent",
        "description": "Roadmap, scope, and product decisions.",
        "system_prompt": _prompt(
            "Product Manager",
            "Turn goals into scoped product increments with clear priorities and acceptance criteria.",
        ),
        "skill_names": ["requirement-refinement"],
    },
    {
        "role_key": "ba",
        "name": "Business Analyst Agent",
        "description": "Requirement refinement and acceptance criteria.",
        "system_prompt": _prompt(
            "Business Analyst",
            "Refine raw ideas into unambiguous, testable requirements. Separate goals, users, "
            "functional requirements, non-functional requirements, acceptance criteria, and out-of-scope work.",
        ),
        "skill_names": ["requirement-refinement"],
    },
    {
        "role_key": "architect",
        "name": "Architect Agent",
        "description": "Technical specifications and design decisions.",
        "system_prompt": _prompt(
            "Software Architect",
            "Produce implementation-ready technical specifications. Name concrete interfaces, data models, "
            "failure modes, and test seams. Prefer the simplest design that satisfies the requirement.",
        ),
        "skill_names": ["tech-spec", "adversarial-review"],
    },
    {
        "role_key": "risk-reviewer",
        "name": "Risk Reviewer Agent",
        "description": "Adversarial review focused on risk and failure modes.",
        "system_prompt": _prompt(
            "Risk Reviewer",
            "Challenge the specification from a risk perspective: security, privacy, data loss, abuse, "
            "operational failure, and irreversible actions. Rank findings by severity and give concrete tests.",
        ),
        "skill_names": ["adversarial-review"],
    },
    {
        "role_key": "test-reviewer",
        "name": "Test Reviewer Agent",
        "description": "Adversarial review focused on test scenarios and data.",
        "system_prompt": _prompt(
            "Test Reviewer",
            "Challenge the specification from a verification perspective: boundary conditions, invalid input, "
            "concurrency, state transitions, and realistic test data. Give executable scenario descriptions.",
        ),
        "skill_names": ["adversarial-review"],
    },
    {
        "role_key": "architecture-reviewer",
        "name": "Architecture Reviewer Agent",
        "description": "Adversarial review focused on design coherence.",
        "system_prompt": _prompt(
            "Architecture Reviewer",
            "Challenge the specification for coupling, missing interfaces, data model gaps, scalability, "
            "and maintainability. Prefer concrete alternatives over abstract criticism.",
        ),
        "skill_names": ["adversarial-review"],
    },
    {
        "role_key": "developer",
        "name": "Developer Agent",
        "description": "Implementation and unit tests.",
        "system_prompt": _prompt(
            "Senior Software Developer",
            "Implement the technical specification in small, coherent steps. Add focused tests, run them, "
            "and leave the repository in a clean, working state. Do not rewrite unrelated code.",
        ),
        "skill_names": ["implementation"],
    },
    {
        "role_key": "qe",
        "name": "Quality Engineer Agent",
        "description": "Verification, live checks, and test coverage.",
        "system_prompt": _prompt(
            "Quality Engineer",
            "Verify the implementation against the requirement and specification. Run the test suite, "
            "perform a live smoke check where possible, and report evidence. Do not hide failures.",
        ),
        "skill_names": ["verification"],
    },
    {
        "role_key": "code-reviewer",
        "name": "Code Reviewer Agent",
        "description": "Independent pull request review.",
        "system_prompt": _prompt(
            "Code Reviewer",
            "Review the pull request diff for correctness, security, maintainability, and missing tests. "
            "Comment on concrete lines and rank findings by severity. Approve only when the change is sound.",
        ),
        "skill_names": ["code-review"],
    },
    {
        "role_key": "marketing",
        "name": "Marketing Agent",
        "description": "Positioning, release notes, and audience-facing copy.",
        "system_prompt": _prompt(
            "Marketing Lead",
            "Turn product changes into clear positioning, release notes, and audience-facing copy. "
            "Be specific and avoid unverifiable claims.",
        ),
        "skill_names": [],
    },
]


async def seed_default_mcp_servers(session: AsyncSession) -> McpServer | None:
    """Create the built-in RAGFlow MCP server row if it is missing."""
    existing = (
        await session.execute(select(McpServer).where(McpServer.name == RAGFLOW_MCP_NAME))
    ).scalar_one_or_none()
    if existing is not None:
        if existing.url in ("", LEGACY_RAGFLOW_MCP_URL):
            existing.url = RAGFLOW_MCP_URL
            existing.transport = "sse"
            existing.headers = dict(RAGFLOW_MCP_HEADERS)
            await session.commit()
        return existing
    server = McpServer(
        name=RAGFLOW_MCP_NAME,
        description="RAGFlow knowledge base retrieval, configured from Aura settings.",
        transport="sse",
        url=RAGFLOW_MCP_URL,
        headers=dict(RAGFLOW_MCP_HEADERS),
        enabled=True,
    )
    session.add(server)
    await session.commit()
    await session.refresh(server)
    return server


async def seed_default_agents(session: AsyncSession) -> None:
    """Insert built-in agent profiles that do not exist yet."""
    ragflow = (
        await session.execute(select(McpServer).where(McpServer.name == RAGFLOW_MCP_NAME))
    ).scalar_one_or_none()
    existing = set((await session.execute(select(AgentProfile.role_key))).scalars().all())
    for definition in DEFAULT_AGENTS:
        role_key = str(definition["role_key"])
        if role_key in existing:
            continue
        skill_names = knowledge_skill_names(role_key, list(definition["skill_names"]))  # type: ignore[arg-type]
        mcp_ids = knowledge_mcp_ids(role_key, ragflow.id if ragflow else "", [])
        session.add(
            AgentProfile(
                name=str(definition["name"]),
                role_key=role_key,
                description=str(definition["description"]),
                system_prompt=str(definition["system_prompt"]),
                skill_names=skill_names,
                mcp_server_ids=mcp_ids,
                is_builtin=True,
                enabled=True,
            )
        )
    await session.commit()


async def apply_knowledge_defaults(session: AsyncSession) -> None:
    """Backfill knowledge access into existing built-in profiles once."""
    marker = await session.get(AppSetting, KNOWLEDGE_DEFAULTS_KEY)
    if marker is not None:
        return
    ragflow = (
        await session.execute(select(McpServer).where(McpServer.name == RAGFLOW_MCP_NAME))
    ).scalar_one_or_none()
    profiles = (
        await session.execute(select(AgentProfile).where(AgentProfile.is_builtin.is_(True)))
    ).scalars()
    for profile in profiles:
        if profile.role_key not in KNOWLEDGE_ROLE_KEYS:
            continue
        profile.skill_names = knowledge_skill_names(profile.role_key, list(profile.skill_names or []))
        if ragflow is not None:
            profile.mcp_server_ids = knowledge_mcp_ids(
                profile.role_key,
                ragflow.id,
                list(profile.mcp_server_ids or []),
            )
    session.add(AppSetting(key=KNOWLEDGE_DEFAULTS_KEY, value=True))
    await session.commit()


async def reconcile_stale_runs(session: AsyncSession) -> None:
    """Mark runs left in a running state by a previous process as failed."""
    from sqlalchemy import update

    from aura.models import AgentRun, PipelineRun, StageRun, utcnow

    now = utcnow()
    stale_stages = await session.execute(select(StageRun).where(StageRun.status == "running"))
    stage_ids = [row.id for row in stale_stages.scalars().all()]
    if stage_ids:
        await session.execute(
            update(StageRun)
            .where(StageRun.id.in_(stage_ids))
            .values(
                status="failed",
                error="Backend restarted while the stage was running.",
                finished_at=now,
            )
        )

    stale_runs = await session.execute(select(AgentRun).where(AgentRun.status == "running"))
    run_ids = [row.id for row in stale_runs.scalars().all()]
    if run_ids:
        await session.execute(
            update(AgentRun)
            .where(AgentRun.id.in_(run_ids))
            .values(
                status="failed",
                error="Backend restarted while the agent was running.",
                finished_at=now,
            )
        )

    stale_pipelines = await session.execute(select(PipelineRun).where(PipelineRun.status.in_(["queued", "running"])))
    pipeline_ids = [row.id for row in stale_pipelines.scalars().all()]
    if pipeline_ids:
        await session.execute(
            update(PipelineRun)
            .where(PipelineRun.id.in_(pipeline_ids))
            .values(
                status="failed",
                error="Backend restarted while the pipeline was running.",
                finished_at=now,
            )
        )
    await session.commit()
