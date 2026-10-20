export interface ServiceStatus {
  name: string;
  status: "ok" | "error" | "off" | string;
  detail: string;
  url: string;
}

export interface Health {
  status: string;
  services: ServiceStatus[];
}

export interface Project {
  id: string;
  name: string;
  slug: string;
  description: string;
  repo_owner: string;
  repo_name: string;
  default_branch: string;
  template: string;
  status: string;
  ragflow_dataset_ids: string[];
  created_at: string;
  updated_at: string;
  requirement_count: number;
  repo_url: string;
}

export type RequirementStatus =
  | "draft"
  | "in_review"
  | "specified"
  | "ready"
  | "in_progress"
  | "verified"
  | "verification_failed"
  | "done"
  | "rejected"
  | string;

export interface Requirement {
  id: string;
  project_id: string;
  key: string;
  title: string;
  status: RequirementStatus;
  initial_idea: string;
  current_version: number;
  branch_name?: string | null;
  pr_number?: number | null;
  pr_url?: string | null;
  ci_status?: string | null;
  ci_target_url?: string | null;
  created_at: string;
  updated_at: string;
}

export interface RequirementVersion {
  id: string;
  requirement_id: string;
  version: number;
  content_md: string;
  source: string;
  author: string;
  git_commit?: string | null;
  created_at: string;
}

export interface Artifact {
  id: string;
  project_id: string;
  requirement_id: string;
  pipeline_run_id?: string | null;
  kind: string;
  title: string;
  path: string;
  version: number;
  content: string;
  created_at: string;
}

export interface Agent {
  id: string;
  name: string;
  role_key: string;
  description: string;
  system_prompt: string;
  model: string;
  allowed_tools: string[];
  skill_names: string[];
  mcp_server_ids: string[];
  env: Record<string, string>;
  enabled: boolean;
  is_builtin: boolean;
  created_at: string;
  updated_at: string;
}

export interface Skill {
  name: string;
  description: string;
  path: string;
  source: string;
  enabled: boolean;
  read_only: boolean;
}

export interface McpServer {
  id: string;
  name: string;
  description: string;
  transport: "stdio" | "http" | "sse" | string;
  command: string;
  args: string[];
  env: Record<string, string>;
  url: string;
  headers: Record<string, string>;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface AgentEvent {
  seq?: number;
  type: string;
  data: Record<string, unknown>;
}

export interface ModelUsage {
  inputTokens?: number;
  outputTokens?: number;
  cacheReadInputTokens?: number;
  cacheCreationInputTokens?: number;
  costUSD?: number;
  canonicalModel?: string;
  provider?: string;
}

export interface AgentRun {
  id: string;
  project_id: string;
  requirement_id?: string | null;
  stage_run_id?: string | null;
  agent_profile_id?: string | null;
  stage: string;
  status: string;
  prompt: string;
  system_prompt: string;
  command: string;
  workspace: string;
  pid?: number | null;
  exit_code?: number | null;
  session_id?: string | null;
  cost_usd?: number | null;
  model_usage: Record<string, ModelUsage>;
  total_tokens: number;
  result_text?: string | null;
  error?: string | null;
  log_path?: string | null;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface StageRun {
  id: string;
  pipeline_run_id: string;
  stage: string;
  status: string;
  agent_profile_id?: string | null;
  agent_run_id?: string | null;
  attempt: number;
  summary?: string | null;
  error?: string | null;
  cost_usd: number;
  total_tokens: number;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface PipelineRun {
  id: string;
  project_id: string;
  requirement_id: string;
  status: string;
  current_stage?: string | null;
  auto_mode: boolean;
  error?: string | null;
  total_cost_usd: number;
  total_tokens: number;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  stages: StageRun[];
}

export interface SettingsResponse {
  values: Record<string, unknown>;
  sources: Record<string, string>;
  warnings: string[];
}

export interface OnboardingSuggested {
  username: string;
  full_name: string;
  email: string;
}

export interface OnboardingGiteaInfo {
  username: string;
  exists: boolean;
  full_name: string;
  email: string;
  ssh_key_count: number;
  error: string;
}

export interface OnboardingGitInfo {
  user_name: string;
  user_email: string;
  matches_gitea: boolean;
}

export interface OnboardingSshKey {
  path: string;
  type: string;
  comment: string;
  fingerprint: string;
  registered: boolean;
}

export interface OnboardingSshInfo {
  keys: OnboardingSshKey[];
  any_registered: boolean;
}

export interface OnboardingRagflowInfo {
  url: string;
  web_url: string;
  account_email: string;
  account_password_configured: boolean;
  api_key_configured: boolean;
  key_valid: boolean;
  healthy: boolean;
  error: string;
}

export interface KnowledgeDataset {
  id: string;
  name?: string;
  description?: string;
  document_count?: number;
  chunk_count?: number;
}

export interface KnowledgeStatus {
  url: string;
  web_url: string;
  configured: boolean;
  healthy: boolean;
  key_valid: boolean;
  dataset_count: number;
  error: string;
}

export interface OnboardingStatus {
  completed: boolean;
  os_user: string;
  suggested: OnboardingSuggested;
  gitea: OnboardingGiteaInfo;
  git: OnboardingGitInfo;
  ssh: OnboardingSshInfo;
  ragflow: OnboardingRagflowInfo;
  missing: string[];
}
