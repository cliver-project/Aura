# Aura

Aura is a local, single-user development center for the super-individual era.
It turns a one-sentence idea into a versioned requirement, a technical
specification, adversarial reviews, an implementation, a verified pull request,
and a code review — then waits for the human to merge.

Aura orchestrates a team of role-based [Claude Code](https://claude.com/claude-code)
processes around self-hosted [Gitea](https://github.com/go-gitea/gitea), with a
unified web UI for projects, requirements, agents, skills, MCP servers, runs, and
global settings.

## What it does

1. Create a project. Aura creates a public Gitea repository on the local-only
   instance, with a documented
   layout and, optionally, a small Python web starter.
2. Describe a requirement in plain language. Aura writes version 1 of the
   requirement into Git and records it in PostgreSQL.
3. Run the pipeline:
   - **refine** — a Business Analyst agent rewrites the idea into a structured,
     testable requirement.
   - **spec** — an Architect agent writes an implementation-ready technical
     specification.
   - **challenge** — risk, test, and architecture reviewers attack the spec in
     parallel and produce severity-ranked findings with concrete test data.
   - **consolidate** — the Architect resolves or records every finding.
   - **implement** — a Developer agent implements the change on a feature branch;
     Aura pushes it and opens a pull request.
   - **verify** — a Quality Engineer agent runs the tests and a live smoke check,
     writes a report, and Aura posts a Gitea commit status.
   - **code_review** — a Code Reviewer agent reviews the diff; Aura posts the
     review as a pull request comment.
4. Aura pauses at **awaiting merge**. The human reviews the pull request, CI
   status, and code review, then merges or rejects. Nothing is auto-merged.
   Merging marks the requirement **done**; that delivery cycle is terminal.
   Create a new requirement for follow-up work.

Every agent run is a separate Claude Code process. Its structured events are
streamed to the UI and persisted, with the exit code, session ID, cost, and
per-model token usage. Model prices are configured in **Settings → Model
pricing** (USD per 1M tokens); configured prices override the cost reported by
Claude Code. The requirement page shows the total cost and tokens for the
pipeline run, plus per-stage costs.

The stage order is fixed. You can run a single stage from the requirement page,
cancel a running pipeline, or cancel an individual agent run from **Runs**.
Pause/resume and fully custom pipeline definitions are not implemented yet.

## Architecture

```
React 19 + Vite + TypeScript
        |
        | REST /api/* + WebSocket /api/ws/*
        v
FastAPI (Python 3.12)
  |-- PostgreSQL (projects, requirements, versions, runs, events, settings)
  |-- Gitea API (repositories, pull requests, comments, commit statuses)
  |-- Claude Code CLI subprocesses (one per agent run)
  |-- per-run Git clones under var/workspaces
  |-- skill library under skills/ and ~/.claude/skills/
  v
Docker Compose
  |-- PostgreSQL 16 (pgvector image)
  |-- Gitea
  |-- optional: Gitea Actions runner (profile "actions")
  |-- RAGFlow v1.0.0-rc2 (Elasticsearch, MySQL, MinIO, Kvrocks, NATS, ClickHouse)
```

Design and planning notes live in `docs/superpowers/`, which is intentionally
gitignored: they are local working documents, not part of the product history.

## Prerequisites

- macOS or Linux with Docker Desktop / Docker Engine
- Python 3.12 (managed through `uv`)
- Node.js 20+ and `pnpm`
- Claude Code CLI installed and authenticated (`claude -p "hello"` must work)
- Git

## Quick start

```sh
make bootstrap   # generate .env, start PostgreSQL + Gitea, create admin + token
make up          # start backend and frontend in the background
```

Open <http://127.0.0.1:5173>.

## First-run onboarding

On the first launch, Aura checks whether your local identity is mapped to
Gitea. Until it is, the dashboard stays locked and a setup wizard is shown:

1. **Gitea identity** — username (defaults to your OS user), full name, and
   primary email. Aura creates or updates the Gitea account.
2. **SSH authentication** — reuse an existing `~/.ssh/*.pub` key or generate an
   ed25519 key, then register it with Gitea.
3. **Git identity** — align the global `git config user.name` and `user.email`
   with the Gitea primary email.
4. **Knowledge base** — point Aura at the local RAGFlow v1.0.0-rc2 API and
   choose one tenant account. The email defaults to your local Git email; the
   password defaults to `AURA_GITEA_PASSWORD` and can be changed later in
   Settings. Leave the API key empty to let Aura log in or register that account
   and create a key, or paste a key created in the RAGFlow UI. Use the same
   account in the RAGFlow UI so the datasets you create there are visible to
   Aura.
5. **Finish** — Aura validates every step, including RAGFlow health, and
   unlocks the dashboard.

The Gitea password is `AURA_GITEA_PASSWORD` in `.env`. It is a random
48-character hex string generated by `openssl rand -hex 24` — plaintext, not a
base64 value or hash. RAGFlow reuses that password for its tenant account by
default. Aura does not keep a separate RAGFlow admin account; it uses the one
tenant account configured in the database. Changing the RAGFlow password in
Aura does not rewrite the password stored inside RAGFlow; update both to the
same value. The wizard can be re-run from **Settings → Onboarding**; this resets
only Aura's onboarding gate, not your Gitea or RAGFlow accounts.

**Gitea and RAGFlow UI languages** can be set under
**Settings → External service languages**. The values come from
`AURA_GITEA_LANGUAGE` and `AURA_RAGFLOW_LANGUAGE` in `.env` as initial defaults
and remain editable. Changing them in Settings updates the configured accounts
immediately; Gitea's instance default (`DEFAULT_LANG`) uses
`AURA_GITEA_LANGUAGE` on container restart.

Useful commands:

| Command | Purpose |
| --- | --- |
| `make up` | Bootstrap and start everything in the background |
| `make down` | Stop backend and frontend (containers keep running) |
| `make containers-down` | Stop all Aura/RAGFlow containers (volumes persist) |
| `make status` | Show process and container status |
| `make db-admin` | Start the pgweb database browser (http://127.0.0.1:8081) |
| `make purge-volumes` | Delete all Aura/RAGFlow named volumes (prompts; irreversible) |
| `make migrate` | Apply database migrations |
| `make backend` | Apply migrations, then run the backend with reload |
| `make web` | Run the frontend in the foreground |
| `make infra-down` | Alias of `make containers-down` |
| `make check` | Backend lint + tests, frontend typecheck + build |
| `make rag-up` | Start the RAGFlow v1.0.0-rc2 knowledge base |
| `make rag-down` | Stop RAGFlow (volumes persist) |
| `make rag-logs` | Follow the RAGFlow server logs |
| `make actions-up` | Start the optional Gitea Actions runner |

## Database migrations

Aura uses Alembic with one linear migration chain. `make up`, `make backend`,
and `scripts/dev.sh` apply pending migrations before starting uvicorn. A
directly launched `uvicorn` does not create tables; if the schema is not at the
current revision, startup fails with a message telling you to run `make migrate`.

```sh
make migrate                                      # upgrade to head
cd backend && uv run python -m aura.migrate current
cd backend && uv run python -m aura.migrate check  # models vs database drift
```

After changing `models.py`, generate and review a migration:

```sh
cd backend
uv run alembic -c alembic.ini revision --autogenerate -m "describe the change"
# review src/aura/alembic/versions/<rev>_<slug>.py
make migrate
```

The migration chain is a single `0001_initial` that creates the complete
current schema. Fresh databases apply it with `upgrade head`. The local
development database was reset, so the incremental migrations were collapsed
into this file. Add a new migration for future schema changes instead of
editing `0001_initial` once it has been applied elsewhere.

## Ports

| Service | Address |
| --- | --- |
| Web UI | <http://127.0.0.1:5173> |
| Backend | <http://127.0.0.1:8000> (OpenAPI at `/docs`) |
| Gitea | <http://127.0.0.1:3000> |
| Gitea SSH | `ssh://git@127.0.0.1:2222` |
| PostgreSQL | `127.0.0.1:5433` |
| Database browser (pgweb) | <http://127.0.0.1:8081> |
| RAGFlow UI | <http://127.0.0.1:8080> |
| RAGFlow API | <http://127.0.0.1:9380> |
| RAGFlow admin | <http://127.0.0.1:9381> |
| RAGFlow MySQL | `127.0.0.1:3307` |
| RAGFlow Elasticsearch | `127.0.0.1:1200` |
| RAGFlow MinIO | `127.0.0.1:9000` (console 9001) |

## Named volumes and destructive reset

Persistent data lives in named Docker volumes:

- Aura: PostgreSQL (`aura_aura_pg_data`), Gitea (`aura_aura_gitea_data`), and
  the optional Actions runner (`aura_aura_runner_data`).
- RAGFlow: MySQL, MinIO, Elasticsearch, ClickHouse, Kvrocks, NATS, and the
  optional profile databases, plus `ragflow_logs`.

Configuration files, init SQL, entrypoint scripts, and the Docker socket remain
bind-mounted because they are code/config, not data. `make containers-down`
stops every Aura and RAGFlow container, including optional profiles; all named
volumes survive. `make down` stops only the backend/frontend processes.

`make purge-volumes` stops the app processes and permanently deletes every
Aura/RAGFlow named volume. It lists the exact volumes, warns that the database,
Gitea repositories, RAGFlow datasets, and run data will be lost, and requires
typing `DELETE`. Unrelated Docker volumes on the host are not touched. After it
runs, `make up` recreates empty services and onboarding starts from scratch.

## Database browser

`docker compose up -d` starts `db-admin`, the open-source
[pgweb](https://github.com/sosedoff/pgweb) PostgreSQL browser, at
<http://127.0.0.1:8081>. It connects to the `aura` database automatically and
supports table listing, row inspection, and SQL queries. The sidebar
**Database** link and **Settings → Database browser** open it in a new tab.

The container is bound to loopback and uses the same
`AURA_POSTGRES_PASSWORD` as the application. It has read/write access, so take a
backup before running destructive SQL.

## First walkthrough

1. Open **Projects** and create a project. Choose the **Python web starter** to
   give agents a runnable FastAPI skeleton, or **Blank** to let the architect
   choose the stack.
2. Open the project, create a requirement, and write the idea in plain language.
   For example: “A public content site with pages and comments stored in the
   database.”
3. On the requirement page, click **Run full pipeline**. Watch the stage
   timeline and open **View logs** to see the Claude Code stream.
4. When the pipeline reaches **Awaiting merge**, open the pull request link,
   inspect the diff and verification report, then click **Merge pull request**
   or **Reject**. Once merged, the requirement is delivered and the page no
   longer offers pipeline runs; create a new requirement for follow-up work.

The same actions are available stage-by-stage with **Run this stage** before
the requirement is delivered.

## Configuration

Aura reads configuration in this order:

1. Process environment variables (`AURA_*`)
2. Values saved in the database from **Settings**
3. `.env` values generated by `make bootstrap`
4. Built-in defaults

`scripts/bootstrap.sh` generates `.env` with random PostgreSQL and Gitea
passwords and a Gitea API token. The file is chmod 600 and gitignored. The
Settings page shows each value's source and refuses to edit values pinned by the
process environment.

Important keys:

| Key | Meaning |
| --- | --- |
| `AURA_GITEA_URL` | Gitea base URL (default `http://localhost:3000`) |
| `AURA_GITEA_TOKEN` | API token generated by bootstrap |
| `AURA_DATABASE_URL` | Async PostgreSQL URL (host port 5433) |
| `AURA_CLAUDE_BIN` / `claude_bin` | Claude Code executable |
| `AURA_DEFAULT_MODEL` / `default_model` | Optional model override for all agents |
| `AURA_PERMISSION_MODE` | Claude Code permission mode |
| `AURA_MAX_CONCURRENT_RUNS` | Parallel agent process limit (default 3) |
| `AURA_MAX_BUDGET_USD` | Per-run budget cap |
| `AURA_WORKSPACE_DIR` | Per-run clone root (`var/workspaces`) |
| `AURA_DATABASE_ADMIN_URL` / `database_admin_url` | pgweb URL shown in the sidebar (default `http://127.0.0.1:8081`) |
| `AURA_GITEA_LANGUAGE` | Initial Gitea UI language (`en-US`, `zh-CN`, `zh-TW`; default `en-US`) |
| `AURA_RAGFLOW_LANGUAGE` | Initial RAGFlow UI language (`en`, `zh-Hans`, `zh-Hant`; default `en`) |
| `AURA_RAGFLOW_URL` | RAGFlow API URL (default `http://127.0.0.1:9380`) |
| `AURA_RAGFLOW_API_KEY` | RAGFlow API key, stored in the database after onboarding |
| `AURA_RAGFLOW_ACCOUNT_EMAIL` / `AURA_RAGFLOW_ACCOUNT_PASSWORD` | Single tenant account used to create the API key (email defaults to the local Git email; password defaults to `AURA_GITEA_PASSWORD`) |
| `AURA_RAGFLOW_MCP_URL` | RAGFlow standalone MCP SSE endpoint (default `http://127.0.0.1:9382/sse`) |
| `AURA_ANTHROPIC_BASE_URL` / `AURA_ANTHROPIC_AUTH_TOKEN` | Optional Claude Code provider endpoint and token |
| `AURA_ANTHROPIC_MODEL` / `AURA_ANTHROPIC_DEFAULT_*_MODEL` | Optional provider model aliases |
| `AURA_CLAUDE_CODE_SUBAGENT_MODEL` / `AURA_CLAUDE_CODE_EFFORT_LEVEL` | Optional Claude Code runtime tuning |

## Skills and MCP

- **Skills** are discovered from three roots, highest precedence first:
  `.claude/skills/<name>/` in the Aura project (project-scoped
  `npx skills add`), `~/.claude/skills/<name>/` (global `npx skills add -g`),
  and `skills/<name>/` (Aura built-in). Built-in skills are editable in the UI.
  Project and user skills installed outside Aura are listed but read-only;
  manage them with `npx skills`:

  ```sh
  npx skills add cliver-project/cliver-playbook --skill <name>
  npx skills add cliver-project/cliver-playbook --skill <name> -g
  ```

  Each agent profile selects the skills it activates; Aura symlinks them into
  the run's `.claude/skills/` directory.
- **MCP servers** are defined in the UI (stdio, HTTP, or SSE). Their settings
  live in the database; placeholders such as `{{ragflow_api_key}}` are resolved
  at run time. Aura writes a temporary config **outside the cloned repository**
  containing only the servers selected on the agent profile, passes it with
  `--mcp-config` and `--strict-mcp-config`, and deletes it after the run.
- **RAGFlow** is a first-class service. `make up` starts the v1.0.0-rc2 stack
  alongside PostgreSQL/Gitea; `make rag-up` starts it alone. The first-run
  wizard creates the tenant account and API key, stores `ragflow_url`,
  `ragflow_api_key`, and `ragflow_account_email` in the database, and the
  Knowledge page lists datasets. Settings also expose `ragflow_mcp_url`.
  RAGFlow v1.0.0-rc2 is a Go backend; on macOS it runs under Docker's amd64
  emulation. The RAGFlow UI is at <http://127.0.0.1:8080>; the API is at
  <http://127.0.0.1:9380>; the standalone MCP SSE endpoint is at
  <http://127.0.0.1:9382/sse>.
- **Knowledge retrieval** is agent-driven. The built-in `knowledge-base` skill
  and stage prompts tell refine/spec/challenge agents to call
  `ragflow_retrieval`; projects can bind specific datasets, and an empty binding
  lets the agent list and search all datasets visible to the tenant.
- **Model provider** environment values are configured globally in Settings and
  can be overridden per agent with `KEY=VALUE` lines on the agent profile. This
  lets a local DeepSeek/Anthropic-compatible endpoint drive Claude Code without
  changing the shell environment.

## Security posture

- Every service binds to `127.0.0.1`; nothing is exposed to the network.
- There is one human user and no authentication, roles, or permissions. This is
  deliberate.
- Gitea registration is disabled and a single admin account is created locally.
- Secrets stay in `.env` or the database and are masked in API responses and the
  UI. Agent commands and logs redact token values.
- **Agents run with the local user's full privileges** because Claude Code needs
  to execute commands in the workspace. This is acceptable only on a trusted
  single-user machine. Do not run Aura on a shared host or with untrusted
  repository content. Sandboxing is a roadmap item.
- Agents never merge. The human is the only actor who can merge or reject.
- Prompt injection from repository content is possible. Mitigations: fresh clone
  per run, manual diff review, manual merge, and no secret exposure in prompts.

## Troubleshooting

- **Gitea is restarting:** check `docker compose logs gitea`. The container's
  system SSH daemon occupies port 22; Aura's built-in Gitea SSH server listens on
  2223 inside the container and is published on host port 2222.
- **Claude runs fail immediately:** verify `claude -p "reply OK"` works in the
  same shell that starts the backend. The backend inherits its environment.
- **A pipeline is stuck:** use the requirement page's **Cancel pipeline** action.
  On backend restart, stale running rows are reconciled to failed so the
  requirement can be retried.
- **Token generation failed during bootstrap:** create a token at
  <http://127.0.0.1:3000/user/settings/applications> and set
  `AURA_GITEA_TOKEN` in `.env`, then restart the backend.
- **Port conflict:** change the host ports in `docker-compose.yml`,
  `frontend/vite.config.ts`, and `AURA_DATABASE_URL`.
- **Backend says the schema is not managed by Alembic:** run `make migrate`.
  The startup guard refuses to serve traffic against an unmigrated database.

## Development

```sh
make install
make check
```

Backend tests: `cd backend && uv run pytest -q`.
Frontend typecheck/build: `cd frontend && pnpm typecheck && pnpm build`.

## License

Private personal project. See `LICENSE`.
