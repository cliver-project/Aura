---
name: code-review
description: Review a pull request diff for correctness, security, maintainability, and missing tests.
---

# Code Review

Use this skill when asked to review a pull request.

## Process

1. Read the requirement, the technical specification, and the full diff.
2. Check correctness first: does the code do what the requirement says, including
   error paths?
3. Check security: input validation, injection, path traversal, secret handling,
   unsafe subprocess use, and unbounded resource consumption.
4. Check maintainability: naming, duplication, dead code, and whether the change
   follows existing patterns.
5. Check tests: every new behavior and every fixed bug has a test; negative paths
   are covered.
6. Check the diff for unrelated changes, debug output, and committed secrets.

## Output contract

Write the review to the exact path named in your task:

- **Verdict** - `approve`, `approve with comments`, or `request changes`.
- **Findings** - numbered, each with severity (`critical`, `high`, `medium`,
  `low`), file and line, the problem, the failure scenario, and a concrete fix.
- **Test gaps** - missing cases with suggested inputs.
- **What is good** - at most three bullets; keep this short and specific.

## Rules

- Comment on the code, not the author. Be direct and concrete.
- Do not report style preferences as defects unless they harm readability or
  correctness.
- Do not request a rewrite for a working change that satisfies the requirement.
- Do not approve when a critical or high finding is unresolved.
- Do not modify code in this stage.
- Write in English.
