"""Pipeline orchestration for requirement delivery."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aura.config import get_settings
from aura.db import SessionLocal
from aura.models import (
    AgentProfile,
    AgentRun,
    Artifact,
    McpServer,
    PipelineRun,
    Project,
    Requirement,
    RequirementVersion,
    StageRun,
    utcnow,
)
from aura.prompts.stages import StageContext, build_stage_prompt
from aura.services.claude_env import build_claude_env
from aura.services.claude_runner import ClaudeRunner
from aura.services.git_workspace import GitError, GitWorkspace
from aura.services.mcp_service import McpService, remove_runtime_config
from aura.services.projects import gitea_client
from aura.services.requirements import add_requirement_version
from aura.services.run_events import RunEventRecorder, is_noise
from aura.services.settings_service import SettingsService
from aura.services.skills_service import SkillsService

STAGES: tuple[str, ...] = (
    "refine",
    "spec",
    "challenge",
    "consolidate",
    "implement",
    "verify",
    "code_review",
)

STAGE_ROLE = {
    "refine": "ba",
    "spec": "architect",
    "consolidate": "architect",
    "implement": "developer",
    "verify": "qe",
    "code_review": "code-reviewer",
}

CHALLENGE_ANGLES = {
    "risk": "risk-reviewer",
    "test": "test-reviewer",
    "architecture": "architecture-reviewer",
}

TERMINAL_PIPELINE_STATUSES = {"done", "failed", "cancelled", "rejected"}

PIPELINE_TASKS: dict[str, asyncio.Task] = {}
_SEMAPHORE: asyncio.Semaphore | None = None
logger = logging.getLogger(__name__)


def stage_sequence(start_stage: str | None = None, auto: bool = True) -> list[str]:
    if start_stage is None:
        stages = list(STAGES)
    else:
        if start_stage not in STAGES:
            raise ValueError(f"Unknown pipeline stage: {start_stage}")
        stages = list(STAGES[STAGES.index(start_stage) :])
    return stages if auto else stages[:1]


def start_block_reason(requirement_status: str) -> str | None:
    """A merged requirement is terminal until a new requirement is created."""
    if requirement_status == "done":
        return "Requirement is already delivered. Create a new requirement for follow-up work."
    return None


def knowledge_available(
    runtime: dict,
    mcp_server_ids: list[str],
    skill_names: list[str],
    ragflow_mcp_id: str | None,
) -> bool:
    """Only promise knowledge tools to an agent that actually has them."""
    return (
        bool(runtime.get("ragflow_api_key"))
        and bool(ragflow_mcp_id)
        and ragflow_mcp_id in mcp_server_ids
        and "knowledge-base" in skill_names
    )


def meaningful_file(path: Path, min_chars: int = 100) -> bool:
    try:
        return path.exists() and len(path.read_text(encoding="utf-8").strip()) >= min_chars
    except OSError:
        return False


def _clean_markdown_line(line: str) -> str:
    without_prefix = re.sub(r"^[\s>*_#`-]+", "", line)
    return without_prefix.replace("*", "").replace("`", "").strip().lower()


def report_verdict(content: str) -> str:
    """Extract the verdict from the Verdict section only.

    Scanning the whole document is unsafe: a passing report often contains
    phrases such as "0 failed" or "fail fast" outside the verdict.
    """
    lines = content.splitlines()
    for index, line in enumerate(lines):
        cleaned = _clean_markdown_line(line)
        if not cleaned.startswith("verdict"):
            continue
        candidates = [cleaned]
        for following in lines[index + 1 : index + 5]:
            candidate = _clean_markdown_line(following)
            if candidate:
                candidates.append(candidate)
                break
        joined = " ".join(candidates)
        if "pass with risks" in joined:
            return "pass_with_risks"
        if re.search(r"\bfail(?:ed|ure)?\b", joined):
            return "fail"
        if "pass" in joined:
            return "pass"
    return "unknown"


def _semaphore(limit: int) -> asyncio.Semaphore:
    global _SEMAPHORE
    if _SEMAPHORE is None:
        _SEMAPHORE = asyncio.Semaphore(max(1, limit))
    return _SEMAPHORE


@dataclass
class AgentOutcome:
    run_id: str
    success: bool
    result_text: str = ""
    error: str = ""
    workspace: Path | None = None
    files: dict[str, str] = field(default_factory=dict)


@dataclass
class StageOutcome:
    success: bool
    summary: str = ""
    error: str = ""


class PipelineEngine:
    def __init__(self) -> None:
        self.git = GitWorkspace()
        self.skills = SkillsService()

    # --- public API ---------------------------------------------------------

    async def start(
        self,
        session: AsyncSession,
        requirement_id: str,
        start_stage: str | None = None,
        auto: bool = True,
    ) -> PipelineRun:
        requirement = await session.get(Requirement, requirement_id)
        if requirement is None:
            raise ValueError("Requirement not found")
        block_reason = start_block_reason(requirement.status)
        if block_reason is not None:
            raise ValueError(block_reason)
        running = (
            await session.execute(
                select(PipelineRun).where(
                    PipelineRun.requirement_id == requirement_id,
                    PipelineRun.status.in_(["queued", "running"]),
                )
            )
        ).scalar_one_or_none()
        if running is not None:
            raise ValueError("A pipeline is already running for this requirement")
        awaiting = (
            await session.execute(
                select(PipelineRun).where(
                    PipelineRun.requirement_id == requirement_id,
                    PipelineRun.status == "awaiting_merge",
                )
            )
        ).scalar_one_or_none()
        if awaiting is not None:
            raise ValueError("A pipeline is awaiting your merge decision. Merge or reject it before starting another.")
        stage_sequence(start_stage, auto)  # validate before creating a row

        pipeline = PipelineRun(
            project_id=requirement.project_id,
            requirement_id=requirement.id,
            status="queued",
            current_stage=start_stage or STAGES[0],
            auto_mode=auto,
        )
        session.add(pipeline)
        await session.commit()
        await session.refresh(pipeline)
        PIPELINE_TASKS[pipeline.id] = asyncio.create_task(self._run(pipeline.id))
        return pipeline

    async def cancel(self, session: AsyncSession, pipeline_run_id: str) -> None:
        pipeline = await session.get(PipelineRun, pipeline_run_id)
        if pipeline is None:
            raise ValueError("Pipeline not found")
        pipeline.status = "cancelled"
        pipeline.error = "Cancelled by the user."
        pipeline.finished_at = utcnow()
        await session.commit()

        stage_ids = (
            (await session.execute(select(StageRun.id).where(StageRun.pipeline_run_id == pipeline_run_id)))
            .scalars()
            .all()
        )
        run_ids = []
        if stage_ids:
            run_ids = (
                (
                    await session.execute(
                        select(AgentRun.id).where(
                            AgentRun.stage_run_id.in_(list(stage_ids)),
                            AgentRun.status.in_(["queued", "running"]),
                        )
                    )
                )
                .scalars()
                .all()
            )
        for run_id in run_ids:
            ClaudeRunner.cancel(run_id)
        task = PIPELINE_TASKS.get(pipeline_run_id)
        if task is not None and not task.done():
            task.cancel()

    async def merge(self, session: AsyncSession, pipeline_run_id: str) -> PipelineRun:
        pipeline = await session.get(PipelineRun, pipeline_run_id)
        if pipeline is None:
            raise ValueError("Pipeline not found")
        if pipeline.status != "awaiting_merge":
            raise ValueError("Pipeline is not awaiting a merge decision")
        requirement = await session.get(Requirement, pipeline.requirement_id)
        project = await session.get(Project, pipeline.project_id)
        if requirement is None or project is None or requirement.pr_number is None:
            raise ValueError("Pull request is not available")

        runtime = await SettingsService.effective_raw(session)
        client = gitea_client(runtime)
        await client.merge_pull_request(
            project.repo_owner,
            project.repo_name,
            requirement.pr_number,
            message=f"Merge {requirement.key}: {requirement.title}",
        )
        requirement.status = "done"
        pipeline.status = "done"
        pipeline.finished_at = utcnow()
        await session.commit()
        return pipeline

    async def reject(self, session: AsyncSession, pipeline_run_id: str, reason: str) -> PipelineRun:
        pipeline = await session.get(PipelineRun, pipeline_run_id)
        if pipeline is None:
            raise ValueError("Pipeline not found")
        requirement = await session.get(Requirement, pipeline.requirement_id)
        project = await session.get(Project, pipeline.project_id)
        if requirement is None or project is None:
            raise ValueError("Requirement not found")

        if requirement.pr_number is not None:
            runtime = await SettingsService.effective_raw(session)
            client = gitea_client(runtime)
            body = f"Aura rejected this change.\n\n{reason or 'No reason provided.'}"
            try:
                await client.comment_issue(project.repo_owner, project.repo_name, requirement.pr_number, body)
                await client.close_pull_request(project.repo_owner, project.repo_name, requirement.pr_number)
            except Exception:
                # The decision still stands even if Gitea is unreachable.
                pass
        requirement.status = "rejected"
        pipeline.status = "rejected"
        pipeline.error = reason or "Rejected by the user."
        pipeline.finished_at = utcnow()
        await session.commit()
        return pipeline

    # --- execution ----------------------------------------------------------

    async def _run(self, pipeline_id: str) -> None:
        try:
            await self._execute(pipeline_id)
        except asyncio.CancelledError:
            async with SessionLocal() as session:
                pipeline = await session.get(PipelineRun, pipeline_id)
                if pipeline is not None and pipeline.status not in TERMINAL_PIPELINE_STATUSES:
                    pipeline.status = "cancelled"
                    pipeline.finished_at = utcnow()
                    await session.commit()
            raise
        except Exception as exc:  # noqa: BLE001 - every failure must be visible
            async with SessionLocal() as session:
                pipeline = await session.get(PipelineRun, pipeline_id)
                if pipeline is not None:
                    pipeline.status = "failed"
                    pipeline.error = str(exc)[:2000]
                    pipeline.finished_at = utcnow()
                    await session.commit()
        finally:
            PIPELINE_TASKS.pop(pipeline_id, None)

    async def _execute(self, pipeline_id: str) -> None:
        async with SessionLocal() as session:
            pipeline = await session.get(PipelineRun, pipeline_id)
            if pipeline is None:
                return
            stages = stage_sequence(pipeline.current_stage, pipeline.auto_mode)
            pipeline.status = "running"
            pipeline.started_at = utcnow()
            await session.commit()

        for stage in stages:
            async with SessionLocal() as session:
                pipeline = await session.get(PipelineRun, pipeline_id)
                if pipeline is None or pipeline.status == "cancelled":
                    return
                pipeline.current_stage = stage
                await session.commit()

            outcome = await self._execute_stage(pipeline_id, stage)
            if not outcome.success:
                return
            if stage == "code_review":
                async with SessionLocal() as session:
                    pipeline = await session.get(PipelineRun, pipeline_id)
                    if pipeline is not None:
                        pipeline.status = "awaiting_merge"
                        pipeline.current_stage = "awaiting_merge"
                        await session.commit()
                return

        async with SessionLocal() as session:
            pipeline = await session.get(PipelineRun, pipeline_id)
            if pipeline is not None:
                pipeline.status = "done" if not pipeline.auto_mode else "done"
                pipeline.finished_at = utcnow()
                await session.commit()

    async def _execute_stage(self, pipeline_id: str, stage: str) -> StageOutcome:
        async with SessionLocal() as session:
            stage_run = StageRun(
                pipeline_run_id=pipeline_id,
                stage=stage,
                status="running",
                started_at=utcnow(),
            )
            session.add(stage_run)
            await session.commit()
            await session.refresh(stage_run)
            stage_run_id = stage_run.id

        try:
            if stage == "challenge":
                outcome = await self._run_challenge(pipeline_id, stage_run_id)
            else:
                outcome = await self._run_single_stage(pipeline_id, stage_run_id, stage)
        except Exception as exc:  # noqa: BLE001
            outcome = StageOutcome(success=False, error=str(exc)[:2000])

        async with SessionLocal() as session:
            stage_run = await session.get(StageRun, stage_run_id)
            if stage_run is not None:
                stage_run.status = "succeeded" if outcome.success else "failed"
                stage_run.summary = outcome.summary[:4000] if outcome.summary else None
                stage_run.error = outcome.error[:4000] if outcome.error else None
                stage_run.finished_at = utcnow()
                if outcome.error:
                    pipeline = await session.get(PipelineRun, pipeline_id)
                    if pipeline is not None:
                        pipeline.status = "failed"
                        pipeline.error = outcome.error[:2000]
                        pipeline.finished_at = utcnow()
                await session.commit()
        return outcome

    async def _run_single_stage(self, pipeline_id: str, stage_run_id: str, stage: str) -> StageOutcome:
        role_key = STAGE_ROLE[stage]
        async with SessionLocal() as session:
            pipeline = await session.get(PipelineRun, pipeline_id)
            assert pipeline is not None
            requirement = await session.get(Requirement, pipeline.requirement_id)
            project = await session.get(Project, pipeline.project_id)
            profile = await self._profile(session, role_key)
            if requirement is None or project is None or profile is None:
                return StageOutcome(success=False, error=f"Missing context for stage {stage}")
            runtime = await SettingsService.effective_raw(session)
            context = self._context(requirement, project, stage)
            ragflow_server = (
                await session.execute(select(McpServer).where(McpServer.name == "ragflow"))
            ).scalar_one_or_none()
            ragflow_mcp_id = ragflow_server.id if ragflow_server and ragflow_server.enabled else None
            context.knowledge_enabled = knowledge_available(
                runtime,
                list(profile.mcp_server_ids or []),
                list(profile.skill_names or []),
                ragflow_mcp_id,
            )
            context.knowledge_dataset_ids = list(project.ragflow_dataset_ids or [])
            if stage == "refine":
                latest = (
                    await session.execute(
                        select(RequirementVersion)
                        .where(RequirementVersion.requirement_id == requirement.id)
                        .order_by(RequirementVersion.version.desc())
                        .limit(1)
                    )
                ).scalar_one_or_none()
                if latest is not None:
                    context.requirement_content = latest.content_md

        branch = self._branch_for_stage(stage, requirement)
        outcome = await self._run_agent(
            pipeline_id=pipeline_id,
            stage_run_id=stage_run_id,
            stage=stage,
            profile=profile,
            requirement=requirement,
            project=project,
            runtime=runtime,
            branch=branch,
            create_from_main=stage == "implement",
            context=context,
        )
        if not outcome.success:
            if stage == "verify" and requirement.pr_number is not None:
                await self._post_status(project, requirement, runtime, "failure", outcome.error)
            return StageOutcome(success=False, error=outcome.error or "Agent run failed")

        try:
            if stage == "refine":
                return await self._finish_refine(pipeline_id, requirement, project, runtime, outcome)
            if stage == "spec":
                return await self._finish_spec(pipeline_id, requirement, project, runtime, outcome)
            if stage == "consolidate":
                return await self._finish_consolidate(pipeline_id, requirement, project, runtime, outcome)
            if stage == "implement":
                return await self._finish_implement(requirement, project, runtime, outcome)
            if stage == "verify":
                return await self._finish_verify(pipeline_id, requirement, project, runtime, outcome)
            if stage == "code_review":
                return await self._finish_code_review(pipeline_id, requirement, project, runtime, outcome)
        except Exception as exc:  # noqa: BLE001
            return StageOutcome(success=False, error=str(exc)[:2000])
        return StageOutcome(success=False, error=f"Unhandled stage: {stage}")

    async def _run_challenge(self, pipeline_id: str, stage_run_id: str) -> StageOutcome:
        async with SessionLocal() as session:
            pipeline = await session.get(PipelineRun, pipeline_id)
            assert pipeline is not None
            requirement = await session.get(Requirement, pipeline.requirement_id)
            project = await session.get(Project, pipeline.project_id)
            if requirement is None or project is None:
                return StageOutcome(success=False, error="Missing context for challenge")
            runtime = await SettingsService.effective_raw(session)
            profiles = {}
            for angle, role_key in CHALLENGE_ANGLES.items():
                profile = await self._profile(session, role_key)
                if profile is None:
                    return StageOutcome(success=False, error=f"Missing agent role: {role_key}")
                profiles[angle] = profile
            context = self._context(requirement, project, "challenge")
            context.knowledge_dataset_ids = list(project.ragflow_dataset_ids or [])
            ragflow_server = (
                await session.execute(select(McpServer).where(McpServer.name == "ragflow"))
            ).scalar_one_or_none()
            ragflow_mcp_id = ragflow_server.id if ragflow_server and ragflow_server.enabled else None

        async def run_angle(angle: str, profile: AgentProfile) -> AgentOutcome:
            angle_context = StageContext(**{**context.__dict__, "angle": angle})
            angle_context.knowledge_enabled = knowledge_available(
                runtime,
                list(profile.mcp_server_ids or []),
                list(profile.skill_names or []),
                ragflow_mcp_id,
            )
            return await self._run_agent(
                pipeline_id=pipeline_id,
                stage_run_id=stage_run_id,
                stage="challenge",
                profile=profile,
                requirement=requirement,
                project=project,
                runtime=runtime,
                branch=project.default_branch,
                create_from_main=False,
                context=angle_context,
            )

        outcomes = await asyncio.gather(*(run_angle(angle, profile) for angle, profile in profiles.items()))
        failures = [outcome.error for outcome in outcomes if not outcome.success]
        if failures:
            return StageOutcome(success=False, error="; ".join(failures)[:2000])

        files: dict[str, str] = {}
        for (angle, _profile), outcome in zip(profiles.items(), outcomes, strict=True):
            path = f"docs/reviews/{requirement.key}-{angle}.md"
            content = outcome.files.get(path, "")
            if len(content.strip()) < 100:
                return StageOutcome(
                    success=False, error=f"Review agent for angle '{angle}' produced no meaningful report"
                )
            files[path] = content

        sha = await self._commit_docs(project, runtime, files, f"docs({requirement.key}): add challenge reviews")
        async with SessionLocal() as session:
            for angle in profiles:
                path = f"docs/reviews/{requirement.key}-{angle}.md"
                session.add(
                    Artifact(
                        project_id=project.id,
                        requirement_id=requirement.id,
                        pipeline_run_id=pipeline_id,
                        kind="review",
                        title=f"{angle} review",
                        path=path,
                        content=files[path],
                    )
                )
            await session.commit()
        return StageOutcome(
            success=True,
            summary=f"Three adversarial reviews completed and committed at {sha or 'existing tree'}.",
        )

    async def _run_agent(
        self,
        *,
        pipeline_id: str,
        stage_run_id: str,
        stage: str,
        profile: AgentProfile,
        requirement: Requirement,
        project: Project,
        runtime: dict,
        branch: str,
        create_from_main: bool,
        context: StageContext,
    ) -> AgentOutcome:
        settings = get_settings()
        run_id = str(__import__("uuid").uuid4())
        clone_url = f"{str(runtime['gitea_url']).rstrip('/')}/{project.repo_owner}/{project.repo_name}.git"
        token = str(runtime.get("gitea_token") or "")
        username = str(runtime.get("gitea_user") or project.repo_owner)
        prompt = build_stage_prompt(stage, context)
        system_prompt = profile.system_prompt

        async with SessionLocal() as session:
            agent_run = AgentRun(
                id=run_id,
                project_id=project.id,
                requirement_id=requirement.id,
                stage_run_id=stage_run_id,
                agent_profile_id=profile.id,
                stage=stage,
                status="queued",
                prompt=prompt,
                system_prompt=system_prompt,
                log_path=str(settings.log_dir / "agent-runs" / f"{run_id}.jsonl"),
            )
            session.add(agent_run)
            await session.commit()

        workspace: Path | None = None
        mcp_path: Path | None = None
        try:
            try:
                workspace = await self.git.prepare(clone_url, branch, run_id, token=token, username=username)
            except GitError:
                if not create_from_main:
                    raise
                workspace = await self.git.prepare(
                    clone_url, project.default_branch, run_id, token=token, username=username
                )
                await self.git.create_branch(workspace, branch)

            self.skills.materialize(list(profile.skill_names or []), workspace)
            mcp_path, mcp_warnings = await McpService.prepare(
                list(profile.mcp_server_ids or []), runtime, run_id
            )
            for warning in mcp_warnings:
                logger.warning(warning)

            runner = ClaudeRunner(claude_bin=str(runtime.get("claude_bin") or "") or None)
            runner.permission_mode = str(runtime.get("permission_mode") or runner.permission_mode)
            runner.max_budget_usd = float(runtime.get("max_budget_usd") or runner.max_budget_usd)
            command = runner.build_command(
                prompt,
                system_prompt=system_prompt,
                model=str(profile.model or runtime.get("default_model") or ""),
                mcp_config_path=str(mcp_path) if mcp_path else None,
                allowed_tools=list(profile.allowed_tools or []),
            )

            log_path = Path(agent_run.log_path or "")
            log_path.parent.mkdir(parents=True, exist_ok=True)
            recorder = await RunEventRecorder.create(run_id)

            async def on_event(event: dict) -> None:
                if is_noise(event):
                    return
                with log_path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(event, ensure_ascii=False) + "\n")
                await recorder.record(event)

            async with SessionLocal() as session:
                stored = await session.get(AgentRun, run_id)
                if stored is not None:
                    stored.workspace = str(workspace)
                    stored.command = shlex.join(command)[:8000]
                    stored.status = "running"
                    stored.started_at = utcnow()
                    await session.commit()

            async with _semaphore(int(runtime.get("max_concurrent_runs") or 3)):
                result = await runner.run(
                    run_id=run_id,
                    cwd=workspace,
                    prompt=prompt,
                    system_prompt=system_prompt,
                    model=str(profile.model or runtime.get("default_model") or ""),
                    mcp_config_path=str(mcp_path) if mcp_path else None,
                    allowed_tools=list(profile.allowed_tools or []),
                    env=build_claude_env(runtime, profile.env or {}),
                    on_event=on_event,
                    timeout=float(runtime.get("agent_timeout_seconds") or settings.agent_timeout_seconds),
                )

            files = {}
            for relative in self._expected_files(stage, requirement, context):
                target = workspace / relative
                if target.exists():
                    files[relative] = target.read_text(encoding="utf-8")

            success = result.exit_code == 0 and not result.is_error
            error = "" if success else (result.stderr or result.result_text or "Claude Code failed")
            async with SessionLocal() as session:
                stored = await session.get(AgentRun, run_id)
                if stored is not None:
                    stored.status = "succeeded" if success else "failed"
                    stored.exit_code = result.exit_code
                    stored.session_id = result.session_id
                    stored.cost_usd = result.cost_usd
                    stored.model_usage = result.model_usage
                    stored.result_text = result.result_text[:20000]
                    stored.error = error[:4000] or None
                    stored.finished_at = utcnow()
                    await session.commit()
            return AgentOutcome(
                run_id=run_id,
                success=success,
                result_text=result.result_text,
                error=error,
                workspace=workspace,
                files=files,
            )
        except Exception as exc:  # noqa: BLE001
            async with SessionLocal() as session:
                stored = await session.get(AgentRun, run_id)
                if stored is not None:
                    stored.status = "failed"
                    stored.error = str(exc)[:4000]
                    stored.finished_at = utcnow()
                    await session.commit()
            return AgentOutcome(run_id=run_id, success=False, error=str(exc)[:2000], workspace=workspace)
        finally:
            remove_runtime_config(mcp_path)

    # --- stage finishers ----------------------------------------------------

    async def _finish_refine(
        self,
        pipeline_id: str,
        requirement: Requirement,
        project: Project,
        runtime: dict,
        outcome: AgentOutcome,
    ) -> StageOutcome:
        path = f"docs/requirements/{requirement.key}.md"
        content = outcome.files.get(path, "")
        if len(content.strip()) < 200:
            return StageOutcome(success=False, error="Refined requirement is missing or too short")
        if outcome.workspace is None:
            return StageOutcome(success=False, error="Workspace is missing")
        sha = await self._commit_stage(outcome.workspace, f"docs({requirement.key}): refine requirement")
        if sha is None:
            return StageOutcome(success=False, error="The refinement agent made no changes")
        await self.git.push(
            outcome.workspace,
            project.default_branch,
            token=str(runtime.get("gitea_token") or ""),
            username=str(runtime.get("gitea_user") or project.repo_owner),
        )
        async with SessionLocal() as session:
            stored_requirement = await session.get(Requirement, requirement.id)
            assert stored_requirement is not None
            stored_requirement.status = "in_review"
            await add_requirement_version(
                session,
                stored_requirement,
                content,
                source="agent",
                author="ba",
                git_commit=sha,
            )
            session.add(
                Artifact(
                    project_id=project.id,
                    requirement_id=requirement.id,
                    pipeline_run_id=pipeline_id,
                    kind="requirement",
                    title=f"Refined requirement v{stored_requirement.current_version}",
                    path=path,
                    version=stored_requirement.current_version,
                    content=content,
                )
            )
            await session.commit()
        return StageOutcome(success=True, summary=f"Requirement refined and committed at {sha}.")

    async def _finish_spec(
        self,
        pipeline_id: str,
        requirement: Requirement,
        project: Project,
        runtime: dict,
        outcome: AgentOutcome,
    ) -> StageOutcome:
        path = f"docs/specs/{requirement.key}-tech-spec.md"
        content = outcome.files.get(path, "")
        if len(content.strip()) < 200:
            return StageOutcome(success=False, error="Technical specification is missing or too short")
        if outcome.workspace is None:
            return StageOutcome(success=False, error="Workspace is missing")
        sha = await self._commit_stage(outcome.workspace, f"docs({requirement.key}): add technical spec")
        if sha is not None:
            await self.git.push(
                outcome.workspace,
                project.default_branch,
                token=str(runtime.get("gitea_token") or ""),
                username=str(runtime.get("gitea_user") or project.repo_owner),
            )
        async with SessionLocal() as session:
            session.add(
                Artifact(
                    project_id=project.id,
                    requirement_id=requirement.id,
                    pipeline_run_id=pipeline_id,
                    kind="spec",
                    title="Technical specification",
                    path=path,
                    content=content,
                )
            )
            stored_requirement = await session.get(Requirement, requirement.id)
            if stored_requirement is not None:
                stored_requirement.status = "specified"
            await session.commit()
        return StageOutcome(success=True, summary=f"Technical specification committed at {sha or 'existing tree'}.")

    async def _finish_consolidate(
        self,
        pipeline_id: str,
        requirement: Requirement,
        project: Project,
        runtime: dict,
        outcome: AgentOutcome,
    ) -> StageOutcome:
        spec_path = f"docs/specs/{requirement.key}-tech-spec.md"
        response_path = f"docs/reviews/{requirement.key}-response.md"
        spec = outcome.files.get(spec_path, "")
        response = outcome.files.get(response_path, "")
        if len(spec.strip()) < 200 or len(response.strip()) < 100:
            return StageOutcome(success=False, error="Consolidated spec or response log is missing or too short")
        if outcome.workspace is None:
            return StageOutcome(success=False, error="Workspace is missing")
        sha = await self._commit_stage(outcome.workspace, f"docs({requirement.key}): consolidate adversarial reviews")
        if sha is not None:
            await self.git.push(
                outcome.workspace,
                project.default_branch,
                token=str(runtime.get("gitea_token") or ""),
                username=str(runtime.get("gitea_user") or project.repo_owner),
            )
        async with SessionLocal() as session:
            session.add_all(
                [
                    Artifact(
                        project_id=project.id,
                        requirement_id=requirement.id,
                        pipeline_run_id=pipeline_id,
                        kind="spec",
                        title="Consolidated technical specification",
                        path=spec_path,
                        content=spec,
                    ),
                    Artifact(
                        project_id=project.id,
                        requirement_id=requirement.id,
                        pipeline_run_id=pipeline_id,
                        kind="review",
                        title="Adversarial review response",
                        path=response_path,
                        content=response,
                    ),
                ]
            )
            stored_requirement = await session.get(Requirement, requirement.id)
            if stored_requirement is not None:
                stored_requirement.status = "ready"
            await session.commit()
        return StageOutcome(success=True, summary=f"Specification consolidated at {sha or 'existing tree'}.")

    async def _finish_implement(
        self,
        requirement: Requirement,
        project: Project,
        runtime: dict,
        outcome: AgentOutcome,
    ) -> StageOutcome:
        if outcome.workspace is None:
            return StageOutcome(success=False, error="Workspace is missing")
        branch = self._branch_for_stage("implement", requirement)
        sha = await self._commit_stage(outcome.workspace, f"feat({requirement.key}): implement {requirement.title}")
        if sha is None:
            return StageOutcome(success=False, error="The developer agent made no code changes")
        await self.git.push(
            outcome.workspace,
            branch,
            token=str(runtime.get("gitea_token") or ""),
            username=str(runtime.get("gitea_user") or project.repo_owner),
        )
        client = gitea_client(runtime)
        pr = await client.create_pull_request(
            project.repo_owner,
            project.repo_name,
            title=f"{requirement.key}: {requirement.title}",
            head=branch,
            base=project.default_branch,
            body=(
                f"Implements requirement **{requirement.key} - {requirement.title}**.\n\n"
                f"Requirement document: `docs/requirements/{requirement.key}.md`\n"
                f"Technical specification: `docs/specs/{requirement.key}-tech-spec.md`\n"
                f"Aura requirement page: {str(runtime.get('public_url') or '').rstrip('/')}"
                f"/requirements/{requirement.id}\n\n"
                "Generated by Aura agents. A human must review and merge."
            ),
        )
        async with SessionLocal() as session:
            stored = await session.get(Requirement, requirement.id)
            if stored is not None:
                stored.branch_name = branch
                stored.pr_number = int(pr.get("number") or 0) or None
                stored.pr_url = str(pr.get("html_url") or "")
                stored.status = "in_progress"
            await session.commit()
        return StageOutcome(
            success=True,
            summary=f"Implementation pushed to {branch}; pull request opened.",
        )

    async def _finish_verify(
        self,
        pipeline_id: str,
        requirement: Requirement,
        project: Project,
        runtime: dict,
        outcome: AgentOutcome,
    ) -> StageOutcome:
        path = f"docs/reports/{requirement.key}-verification.md"
        content = outcome.files.get(path, "")
        if len(content.strip()) < 100:
            await self._post_status(project, requirement, runtime, "failure", "Verification report missing")
            return StageOutcome(success=False, error="Verification report is missing or too short")
        if outcome.workspace is None:
            return StageOutcome(success=False, error="Workspace is missing")
        sha = await self._commit_stage(outcome.workspace, f"docs({requirement.key}): add verification report")
        branch = self._branch_for_stage("verify", requirement)
        if sha is not None:
            await self.git.push(
                outcome.workspace,
                branch,
                token=str(runtime.get("gitea_token") or ""),
                username=str(runtime.get("gitea_user") or project.repo_owner),
            )
        head = await self.git.head_sha(outcome.workspace)
        verdict = report_verdict(content)
        passed = verdict != "fail"
        await self._post_status(
            project,
            requirement,
            runtime,
            "success" if passed else "failure",
            "Verification passed" if passed else "Verification failed",
            head,
        )
        async with SessionLocal() as session:
            session.add(
                Artifact(
                    project_id=project.id,
                    requirement_id=requirement.id,
                    pipeline_run_id=pipeline_id,
                    kind="verification",
                    title="Verification report",
                    path=path,
                    content=content,
                )
            )
            stored = await session.get(Requirement, requirement.id)
            if stored is not None:
                stored.ci_status = "success" if passed else "failure"
                stored.status = "verified" if passed else "verification_failed"
            await session.commit()
        if not passed:
            return StageOutcome(
                success=False,
                error=f"Verification verdict: {verdict}. See {path}.",
            )
        return StageOutcome(
            success=True,
            summary=f"Verification report committed at {sha or head} (verdict: {verdict}).",
        )

    async def _finish_code_review(
        self,
        pipeline_id: str,
        requirement: Requirement,
        project: Project,
        runtime: dict,
        outcome: AgentOutcome,
    ) -> StageOutcome:
        path = f"docs/reviews/{requirement.key}-code-review.md"
        content = outcome.files.get(path, "")
        if len(content.strip()) < 100:
            return StageOutcome(success=False, error="Code review report is missing or too short")
        if requirement.pr_number is None:
            return StageOutcome(success=False, error="No pull request is linked to this requirement")
        client = gitea_client(runtime)
        await client.comment_issue(
            project.repo_owner,
            project.repo_name,
            requirement.pr_number,
            f"## Aura code review\n\n{content}",
        )
        async with SessionLocal() as session:
            session.add(
                Artifact(
                    project_id=project.id,
                    requirement_id=requirement.id,
                    pipeline_run_id=pipeline_id,
                    kind="code_review",
                    title="Code review",
                    path=path,
                    content=content,
                )
            )
            await session.commit()
        return StageOutcome(success=True, summary="Code review posted to the pull request.")

    # --- helpers ------------------------------------------------------------

    async def _profile(self, session: AsyncSession, role_key: str) -> AgentProfile | None:
        return (
            await session.execute(
                select(AgentProfile).where(AgentProfile.role_key == role_key, AgentProfile.enabled.is_(True))
            )
        ).scalar_one_or_none()

    def _context(self, requirement: Requirement, project: Project, stage: str) -> StageContext:
        return StageContext(
            project_name=project.name,
            project_slug=project.slug,
            requirement_id=requirement.id,
            requirement_key=requirement.key,
            requirement_title=requirement.title,
            requirement_path=f"docs/requirements/{requirement.key}.md",
            requirement_content=requirement.initial_idea,
            branch=self._branch_for_stage(stage, requirement),
            repo_url=f"{project.repo_owner}/{project.repo_name}",
            target_version=requirement.current_version + 1,
            spec_path=f"docs/specs/{requirement.key}-tech-spec.md",
            review_paths=[f"docs/reviews/{requirement.key}-{angle}.md" for angle in CHALLENGE_ANGLES],
        )

    def _branch_for_stage(self, stage: str, requirement: Requirement) -> str:
        if stage in {"implement", "verify", "code_review"}:
            return requirement.branch_name or f"feature/{requirement.key}"
        return "main"

    def _expected_files(self, stage: str, requirement: Requirement, context: StageContext) -> list[str]:
        if stage == "refine":
            return [f"docs/requirements/{requirement.key}.md"]
        if stage == "spec":
            return [f"docs/specs/{requirement.key}-tech-spec.md"]
        if stage == "challenge":
            return [f"docs/reviews/{requirement.key}-{context.angle}.md"]
        if stage == "consolidate":
            return [
                f"docs/specs/{requirement.key}-tech-spec.md",
                f"docs/reviews/{requirement.key}-response.md",
            ]
        if stage == "verify":
            return [f"docs/reports/{requirement.key}-verification.md"]
        if stage == "code_review":
            return [f"docs/reviews/{requirement.key}-code-review.md"]
        return []

    async def _commit_stage(self, workspace: Path, message: str) -> str | None:
        """Commit working-tree changes, or accept commits the agent made itself."""
        sha = await self.git.commit_all(workspace, message)
        if sha is not None:
            return sha
        if await self.git.commits_ahead(workspace) > 0:
            return await self.git.head_sha(workspace)
        return None

    async def _commit_docs(
        self,
        project: Project,
        runtime: dict,
        files: dict[str, str],
        message: str,
    ) -> str | None:
        clone_url = f"{str(runtime['gitea_url']).rstrip('/')}/{project.repo_owner}/{project.repo_name}.git"
        token = str(runtime.get("gitea_token") or "")
        username = str(runtime.get("gitea_user") or project.repo_owner)
        run_id = f"docs-{__import__('uuid').uuid4().hex[:10]}"
        path = await self.git.prepare(clone_url, project.default_branch, run_id, token=token, username=username)
        try:
            for relative, content in files.items():
                target = path / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
            sha = await self.git.commit_all(path, message)
            if sha is not None:
                await self.git.push(path, project.default_branch, token=token, username=username)
            return sha
        finally:
            self.git.cleanup(path)

    async def _post_status(
        self,
        project: Project,
        requirement: Requirement,
        runtime: dict,
        state: str,
        description: str,
        sha: str | None = None,
    ) -> None:
        client = gitea_client(runtime)
        if sha is None and requirement.pr_number is not None:
            pr = await client.get_pull_request(project.repo_owner, project.repo_name, requirement.pr_number)
            sha = ((pr.get("head") or {}).get("sha")) or None
        if not sha:
            return
        public_url = str(runtime.get("public_url") or get_settings().public_url)
        target_url = f"{public_url.rstrip('/')}/requirements/{requirement.id}"
        await client.create_commit_status(
            project.repo_owner,
            project.repo_name,
            sha,
            state,
            target_url=target_url,
            description=description,
        )
        async with SessionLocal() as session:
            stored = await session.get(Requirement, requirement.id)
            if stored is not None:
                stored.ci_status = state
                stored.ci_target_url = target_url
                await session.commit()


engine = PipelineEngine()
