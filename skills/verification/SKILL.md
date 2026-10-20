---
name: verification
description: Verify an implementation against the requirement and specification with real commands and evidence.
---

# Verification

Use this skill when asked to verify an implementation on a feature branch.

## Process

1. Read the requirement, the technical specification, and the implementation
   diff (`git diff origin/main...HEAD`).
2. Install dependencies exactly as `CLAUDE.md` describes.
3. Run the full automated test suite. Capture the command and the summarized
   result.
4. Run the build or typecheck command.
5. Perform a live smoke check when the project exposes a runnable surface:
   start the app on a spare local port, call the health endpoint and the primary
   user flow, then stop the process. Never leave a server running.
6. Map every acceptance criterion to evidence: a test name, a command result, or
   a manual check.
7. Check negative paths: invalid input, empty state, duplicate submission, and at
   least one failure/recovery scenario.
8. Review the diff for secrets, debug leftovers, and unrelated changes.

## Output contract

Write the report to the exact path named in your task:

- **Verdict** - `pass`, `pass with risks`, or `fail`.
- **Environment** - runtime and dependency versions.
- **Commands and results** - exact commands, exit codes, and summarized output.
- **Acceptance criteria coverage** - table of criterion, evidence, status.
- **Failures and risks** - what failed, reproduction steps, and severity.
- **Untested areas** - explicit list, never implied.
- **Recommendation** - merge, fix first, or reject.

## Rules

- Never claim a command passed unless you ran it and saw the result.
- Never weaken or delete a test to make verification pass.
- Do not fix implementation code in this stage; report the defect. The developer
  stage owns fixes.
- Do not commit or push; the orchestrator handles Git.
- Write in English.
