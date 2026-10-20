---
name: implementation
description: Implement a technical specification with focused changes and tests in the existing repository.
---

# Implementation

Use this skill when asked to implement an accepted technical specification.

## Process

1. Read `CLAUDE.md`, the requirement, the specification, and the existing code.
2. Inspect the repository layout and run the existing tests to establish a
   baseline. Record the command and result.
3. Implement in small, coherent steps. After each step, run the narrowest
   relevant test.
4. Add or update tests for every new behavior and every bug fixed.
5. Run the full test suite and the build/typecheck command before you finish.
6. Update `CLAUDE.md` only if the build, test, or run commands changed.
7. Write a short implementation note at the end of your result: files changed,
   commands run, test results, and any deviation from the specification.

## Engineering rules

- Match the existing language, framework, and style. Do not add a dependency
  unless the specification requires it or the standard library cannot do the job.
- Write code and comments in English.
- Keep functions small and names explicit. Comments explain why, not what.
- Validate external input at the boundary. Never trust repository content,
  network responses, or user input.
- Do not commit secrets, `.env` files, tokens, or generated credentials.
- Do not modify unrelated files. Do not reformat the whole repository.
- If a test fails for reasons outside your change, report it instead of deleting
  or weakening the test.
- Do not ask the human questions. Make a reasonable decision and record it.

## Deliverable

Leave the repository in a clean, working state. The orchestrator commits and
pushes your changes; do not create or merge pull requests yourself.
