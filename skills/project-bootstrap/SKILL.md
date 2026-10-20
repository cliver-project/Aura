---
name: project-bootstrap
description: Bootstrap a new project repository with a minimal, testable application skeleton and conventions.
---

# Project Bootstrap

Use this skill when asked to initialize a new project from a product idea.

## Deliverables

1. A minimal runnable application that demonstrates the primary user flow.
2. A test that exercises the health endpoint or the primary flow.
3. `CLAUDE.md` with the exact install, test, build, and run commands.
4. `.gitignore` covering dependencies, build output, environment files, and local
   agent state.
5. A continuous-integration workflow that installs dependencies and runs tests.
6. Documentation placeholders under `docs/requirements`, `docs/specs`,
   `docs/reviews`, and `docs/reports`.

## Rules

- Choose the simplest stack that satisfies the requirement. Prefer the stack
  already present in the repository; for an empty repository, prefer Python with
  FastAPI, SQLite, and server-rendered pages unless the requirement demands
  otherwise.
- Every generated project must have at least one automated test.
- Pin nothing to a cloud service. The project must run locally.
- Write code, comments, and documentation in English.
- Do not create a pull request or merge anything; the orchestrator owns Git.
