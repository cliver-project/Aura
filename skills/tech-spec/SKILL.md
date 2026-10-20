---
name: tech-spec
description: Produce an implementation-ready technical specification from a refined requirement.
---

# Technical Specification

Use this skill when asked to design or update a technical specification.

## Output contract

Write the specification to the exact path named in your task. Required sections:

1. **Context and constraints** - the requirement version this spec implements,
   existing repository state, and hard constraints.
2. **Proposed architecture** - components, boundaries, and a short data-flow
   description. Prefer the simplest design that satisfies the requirement.
3. **Data model** - tables/collections, fields, types, constraints, indexes, and
   migrations. Name the storage engine.
4. **Interfaces** - HTTP routes or functions with request/response shapes, status
   codes, validation, and error cases. Use exact names.
5. **UI behavior** - pages, states, empty/error cases, accessibility, and
   internationalization. The product UI must support English and Chinese.
6. **Security and privacy** - authentication assumptions, input validation,
   injection risks, secret handling, and abuse controls. This is a local
   single-user product; do not add a multi-user permission model.
7. **Failure modes and recovery** - what happens on partial failure, restart,
   duplicate submission, and dependency outage.
8. **Test plan** - unit, integration, and live verification. Name concrete test
   cases with input data and expected results.
9. **Implementation plan** - ordered file-level steps, each independently
   testable.
10. **Decisions and trade-offs** - alternatives considered and why they lost.

## Rules

- Read the repository before designing. Reuse the existing stack when it exists.
- Every acceptance criterion in the requirement must map to a component and a
  test. Call out any criterion you cannot satisfy.
- Do not introduce a new database, framework, or service without a concrete
  reason.
- Prefer boring, local-first technology. No cloud dependencies.
- Write in English.
