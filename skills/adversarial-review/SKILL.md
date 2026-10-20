---
name: adversarial-review
description: Attack a requirement or technical specification from a specific angle and produce severity-ranked findings.
---

# Adversarial Review

Use this skill when asked to challenge a requirement, specification, or test plan.

You are not a cheerleader. Your job is to find the assumptions that will break,
the cases the author skipped, and the tests that would catch them.

## Output contract

Write the review to the exact path named in your task, with this structure:

1. **Angle** - the perspective assigned to you (risk, testing, or architecture).
2. **Summary** - the three most important problems, in one sentence each.
3. **Findings** - numbered, each with:
   - severity: `critical`, `high`, `medium`, or `low`
   - the exact requirement/spec section it targets
   - the failure scenario with concrete inputs or state
   - why the current design does not handle it
   - a concrete recommendation
   - a test that would expose it
4. **Test scenarios and data** - a table of scenario, input/data, expected result,
   and which acceptance criterion it validates. Include boundaries, invalid input,
   empty state, concurrent writes, and recovery after failure.
5. **Questions that remain** - only questions that cannot be resolved by a
   reasonable assumption.

## Rules

- Rank by user impact and likelihood, not by how interesting the issue is.
- Do not report style preferences as defects.
- Do not propose a rewrite unless the current structure cannot satisfy a
  requirement.
- Every finding must include a failure scenario. If you cannot describe one,
  drop the finding.
- Do not implement code. This stage produces analysis only.
- Write in English.
