"""Pydantic request and response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- health -----------------------------------------------------------------


class ServiceStatus(BaseModel):
    name: str
    status: str
    detail: str = ""
    url: str = ""


class HealthOut(BaseModel):
    status: str
    services: list[ServiceStatus]


# --- projects ---------------------------------------------------------------


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(default="", max_length=120)
    description: str = ""
    template: str = "python-web"


class ProjectUpdate(BaseModel):
    ragflow_dataset_ids: list[str] | None = None


class ProjectOut(ORMModel):
    id: str
    name: str
    slug: str
    description: str
    repo_owner: str
    repo_name: str
    default_branch: str
    template: str
    status: str
    ragflow_dataset_ids: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    requirement_count: int = 0
    repo_url: str = ""


# --- requirements -----------------------------------------------------------


class RequirementCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    idea: str = Field(min_length=1)


class RequirementOut(ORMModel):
    id: str
    project_id: str
    key: str
    title: str
    status: str
    initial_idea: str
    current_version: int
    branch_name: str | None = None
    pr_number: int | None = None
    pr_url: str | None = None
    ci_status: str | None = None
    ci_target_url: str | None = None
    created_at: datetime
    updated_at: datetime


class RequirementVersionOut(ORMModel):
    id: str
    requirement_id: str
    version: int
    content_md: str
    source: str
    author: str
    git_commit: str | None = None
    created_at: datetime


class ArtifactOut(ORMModel):
    id: str
    project_id: str
    requirement_id: str
    pipeline_run_id: str | None = None
    kind: str
    title: str
    path: str
    version: int
    content: str
    created_at: datetime


# --- agents -----------------------------------------------------------------


class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    role_key: str = Field(min_length=1, max_length=80)
    description: str = ""
    system_prompt: str = ""
    model: str = ""
    allowed_tools: list[str] = Field(default_factory=list)
    skill_names: list[str] = Field(default_factory=list)
    mcp_server_ids: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    enabled: bool = True


class AgentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    model: str | None = None
    allowed_tools: list[str] | None = None
    skill_names: list[str] | None = None
    mcp_server_ids: list[str] | None = None
    env: dict[str, str] | None = None
    enabled: bool | None = None


class AgentOut(ORMModel):
    id: str
    name: str
    role_key: str
    description: str
    system_prompt: str
    model: str
    allowed_tools: list[str]
    skill_names: list[str]
    mcp_server_ids: list[str]
    env: dict[str, str] = Field(default_factory=dict)
    enabled: bool
    is_builtin: bool
    created_at: datetime
    updated_at: datetime


# --- MCP --------------------------------------------------------------------


class McpCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str = ""
    transport: str = "stdio"
    command: str = ""
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    url: str = ""
    headers: dict[str, str] = Field(default_factory=dict)
    enabled: bool = True


class McpUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    transport: str | None = None
    command: str | None = None
    args: list[str] | None = None
    env: dict[str, str] | None = None
    url: str | None = None
    headers: dict[str, str] | None = None
    enabled: bool | None = None


class McpOut(ORMModel):
    id: str
    name: str
    description: str
    transport: str
    command: str
    args: list[str]
    env: dict[str, str]
    url: str
    headers: dict[str, str]
    enabled: bool
    created_at: datetime
    updated_at: datetime


# --- skills -----------------------------------------------------------------


class SkillOut(BaseModel):
    name: str
    description: str
    path: str
    source: str
    enabled: bool = True
    read_only: bool = False


class SkillContent(BaseModel):
    content: str


class SkillCreate(SkillContent):
    name: str = Field(min_length=1, max_length=150)


# --- runs -------------------------------------------------------------------


class AgentEventOut(ORMModel):
    id: str
    agent_run_id: str
    seq: int
    type: str
    data: dict[str, Any]
    created_at: datetime


class AgentRunOut(ORMModel):
    id: str
    project_id: str
    requirement_id: str | None = None
    stage_run_id: str | None = None
    agent_profile_id: str | None = None
    stage: str
    status: str
    prompt: str
    system_prompt: str
    command: str
    workspace: str
    pid: int | None = None
    exit_code: int | None = None
    session_id: str | None = None
    cost_usd: float | None = None
    model_usage: dict[str, Any] = Field(default_factory=dict)
    total_tokens: int = 0
    result_text: str | None = None
    error: str | None = None
    log_path: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class StageRunOut(ORMModel):
    id: str
    pipeline_run_id: str
    stage: str
    status: str
    agent_profile_id: str | None = None
    agent_run_id: str | None = None
    attempt: int
    summary: str | None = None
    error: str | None = None
    cost_usd: float = 0.0
    total_tokens: int = 0
    started_at: datetime | None = None
    finished_at: datetime | None = None


class PipelineRunOut(ORMModel):
    id: str
    project_id: str
    requirement_id: str
    status: str
    current_stage: str | None = None
    auto_mode: bool
    error: str | None = None
    total_cost_usd: float = 0.0
    total_tokens: int = 0
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    stages: list[StageRunOut] = Field(default_factory=list)


class PipelineStart(BaseModel):
    start_stage: str | None = None
    auto: bool = True


class RejectRequest(BaseModel):
    reason: str = ""


# --- settings ---------------------------------------------------------------


class SettingsOut(BaseModel):
    values: dict[str, Any]
    sources: dict[str, str]
    warnings: list[str] = Field(default_factory=list)


class SettingsUpdate(BaseModel):
    values: dict[str, Any]


# --- onboarding -------------------------------------------------------------


class OnboardingSuggested(BaseModel):
    username: str
    full_name: str = ""
    email: str = ""


class OnboardingGiteaInfo(BaseModel):
    username: str
    exists: bool = False
    full_name: str = ""
    email: str = ""
    ssh_key_count: int = 0
    error: str = ""


class OnboardingGitInfo(BaseModel):
    user_name: str = ""
    user_email: str = ""
    matches_gitea: bool = False


class OnboardingSshKey(BaseModel):
    path: str
    type: str
    comment: str = ""
    fingerprint: str = ""
    registered: bool = False


class OnboardingSshInfo(BaseModel):
    keys: list[OnboardingSshKey] = Field(default_factory=list)
    any_registered: bool = False


class OnboardingRagflowInfo(BaseModel):
    url: str
    web_url: str = ""
    account_email: str = ""
    account_password_configured: bool = False
    api_key_configured: bool = False
    key_valid: bool = False
    healthy: bool = False
    error: str = ""


class OnboardingStatus(BaseModel):
    completed: bool
    os_user: str
    suggested: OnboardingSuggested
    gitea: OnboardingGiteaInfo
    git: OnboardingGitInfo
    ssh: OnboardingSshInfo
    ragflow: OnboardingRagflowInfo
    missing: list[str] = Field(default_factory=list)


class GiteaIdentityRequest(BaseModel):
    username: str = Field(min_length=1, max_length=39)
    full_name: str = Field(default="", max_length=255)
    email: str = Field(min_length=3, max_length=255)


class SshKeyRequest(BaseModel):
    path: str | None = None


class GenerateSshKeyRequest(BaseModel):
    email: str | None = None


class GitIdentityRequest(BaseModel):
    user_name: str = Field(min_length=1, max_length=255)
    user_email: str = Field(min_length=3, max_length=255)


class RagflowConfigRequest(BaseModel):
    url: str = Field(default="http://127.0.0.1:9380", min_length=8, max_length=500)
    api_key: str = ""
    auto_create: bool = True
    account_email: str = ""
    account_password: str = ""


class KnowledgeStatus(BaseModel):
    url: str
    web_url: str
    configured: bool = False
    healthy: bool = False
    key_valid: bool = False
    dataset_count: int = 0
    error: str = ""
