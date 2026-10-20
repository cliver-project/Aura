# Aura — Project Instructions for AI Agents

Aura is a local, single-user AI-native development center. It orchestrates
Claude Code agent processes around Gitea with a FastAPI backend and a React
frontend.

## Non-negotiable rules

- Keep the product UI bilingual: English and Simplified Chinese. Every
  user-visible string goes through `t()` and both locale files.
- The human owner is the only actor who may merge a pull request. Never add
  auto-merge.
- There is one human user. Do not add authentication, human roles, permissions,
  or multi-tenancy.
- Bind local services to `127.0.0.1`. Do not expose them on the network.

## Architecture map

- `backend/src/aura/main.py` — FastAPI app factory, lifespan, routers.
- `backend/src/aura/models.py` — SQLAlchemy models (projects, requirements,
  versions, artifacts, agents, pipelines, stages, runs, events, skills, MCP,
  settings).
- `backend/src/aura/db/` — `base.py` (declarative Base + deterministic naming
  convention), `session.py` (async engine, session factory, request
  dependency), `testing.py` (create/drop helpers for tests only).
- `backend/src/aura/alembic/` — Alembic environment and the single migration
  chain (`versions/0001_initial.py`). `backend/alembic.ini` is for authoring;
  `backend/src/aura/migrate.py` is the programmatic CLI.
- `backend/src/aura/services/onboarding.py`, `backend/src/aura/api/onboarding.py`
  — first-run identity setup: OS defaults, Gitea account, SSH key, Git config,
  and the dashboard gate.
- `backend/src/aura/services/` — the control plane:
  - `claude_runner.py` — Claude Code subprocess, stream-json parsing, cancellation.
  - `run_events.py` — event persistence and noise filtering.
  - `event_bus.py` — in-process live event fan-out.
  - `pipeline.py` — stage orchestration and Gitea/Git side effects.
  - `git_workspace.py` — per-run clones, commits, credential-safe pushes.
  - `gitea.py` — Gitea REST client.
  - `projects.py`, `requirements.py` — repository seeding and versioning.
  - `skills_service.py`, `mcp_service.py` — skills and MCP materialization.
    Skill roots, highest precedence first: project `.claude/skills` (read-only),
    user `~/.claude/skills` (read-only), built-in `skills/` (editable).
  - `settings_service.py` — environment/database settings precedence.
- `backend/src/aura/prompts/stages.py` — English stage prompts and deliverables.
- `frontend/src/pages/` — Onboarding, Dashboard, Projects, Project detail,
  Requirement detail, Agents, Skills, MCP, Runs, Settings.
- `frontend/src/locales/en.json`, `zh.json` — UI translations.
- `skills/` — built-in `SKILL.md` library. Skills installed by `npx skills`
  under `.claude/skills/` or `~/.claude/skills/` are discovered automatically,
  take precedence over built-in skills with the same name, and must remain
  read-only in the API and UI.
- `docker-compose.yml` — PostgreSQL, Gitea, optional runner.
- `infra/ragflow/` — RAGFlow v1.0.0-rc2 stack (Go backend, amd64 under
  emulation on macOS). `make rag-up` starts it; the onboarding wizard and
  Settings store `ragflow_url`/`ragflow_api_key` in the database.
- `backend/src/aura/services/ragflow.py`, `backend/src/aura/api/knowledge.py`
  — RAGFlow health, API-key provisioning, and dataset listing.
- `frontend/src/pages/KnowledgePage.tsx` — knowledge-base status and datasets.
- `scripts/bootstrap.sh` — secrets, containers, Gitea admin, API token.
- `scripts/dev.sh` — start/stop/status for backend and frontend.

## Commands

```sh
make bootstrap          # one-time local infrastructure bootstrap
make migrate            # apply database migrations
make up                 # background backend + frontend (migrates first)
make down               # stop app processes
make status             # process and container status
make check              # backend lint/tests + frontend typecheck/build
make rag-up             # start the RAGFlow v1.0.0-rc2 stack
make rag-down           # stop RAGFlow (volumes persist)
make rag-logs           # follow RAGFlow server logs
make actions-up         # optional Gitea Actions runner
```

Backend: `cd backend && uv run pytest -q` and `uv run ruff check src tests`.
Frontend: `cd frontend && pnpm typecheck && pnpm lint && pnpm build`.

## Pipeline contract

The default stage order is:

```
refine -> spec -> challenge -> consolidate -> implement -> verify -> code_review
```

- `challenge` fans out to three reviewer agents in parallel and commits their
  reports in one commit.
- `implement` creates branch `feature/REQ-###`, pushes it, and creates a pull
  request through the Gitea API.
- `verify` writes a report and posts a Gitea commit status whose target URL is
  the requirement page.
- `code_review` posts the review as a pull request comment.
- After `code_review`, the pipeline must stop at `awaiting_merge`.
- A stage succeeds only when its postcondition file exists and is meaningful,
  even if the Claude process exits zero.

## Development conventions

- Python 3.12, FastAPI, SQLAlchemy 2 async, Pydantic v2. Keep services small and
  explicit.
- React 19, TypeScript strict, Tailwind 4, TanStack Query. No new UI framework.
- Use the existing shadcn-style primitives in `frontend/src/components/ui/`.
- Prefer adding a test for every bug fix. Backend tests do not require Docker.
- Do not weaken or delete tests to make a change pass.
- Database schema changes require an Alembic migration. Never edit the live
  schema by hand and never call `create_all` from application startup.
  `create_all` lives only in `aura/db/testing.py` for tests and throwaway
  databases.
- `make migrate`, `make backend`, and `scripts/dev.sh` apply migrations before
  uvicorn starts. A directly launched uvicorn against an unmigrated database
  fails with `Run: make migrate`.
- Keep the existing `String(36)` UUIDs, application-side timestamp defaults,
  and `JSON` columns unless a dedicated data migration is approved.
- First-run onboarding state is the `app_settings.onboarding_completed` row.
  `GET /api/onboarding/status` is the source of truth, and the React gate must
  not render the application until it returns `completed: true`. The status
  includes Gitea, SSH, Git, and RAGFlow; RAGFlow is required and must be
  healthy with a valid API key.
  `POST /api/onboarding/reset` reopens the wizard; the Settings button uses it.
  `POST /api/onboarding/ragflow` creates an API key through the local RAGFlow
  admin when the key field is empty, then stores the URL/key in `app_settings`.
  Keep every onboarding action idempotent and never return passwords or
  tokens in API responses.

## Security

- Never log or return tokens. Redact secrets in commands and errors.
- Agent subprocesses inherit the local user's privileges. Keep the workspace
  clone per run and never point an agent at the Aura repository itself.
- Do not add network-exposed services.
