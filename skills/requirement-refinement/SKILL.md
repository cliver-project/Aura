---
name: requirement-refinement
description: Turn a raw product idea into a structured, testable requirement document with acceptance criteria.
---

# Requirement Refinement

Use this skill when asked to refine, clarify, or rewrite a product requirement.

## Output contract

Write the requirement to the exact path named in your task. Keep the existing
front matter and increment the version only when your task tells you to. Use
Markdown with these sections, in this order:

1. **Summary** - two or three sentences a busy reader can act on.
2. **Problem and motivation** - the concrete problem, who has it, and why now.
3. **Goals** - measurable outcomes.
4. **Non-goals** - explicitly out of scope for this version.
5. **Users and scenarios** - primary actors and the moments they use the product.
6. **Functional requirements** - numbered `FR-1`, `FR-2`, ... Each item is a single
   testable behavior.
7. **Non-functional requirements** - performance, reliability, security, privacy,
   accessibility, and operability. Include concrete numbers when known.
8. **Acceptance criteria** - numbered `AC-1`, ... in Given/When/Then form. Every
   functional requirement must be covered by at least one criterion.
9. **Edge cases and failure modes** - invalid input, empty state, concurrency,
   abuse, and recovery.
10. **Open questions and assumptions** - assumptions you made instead of asking.
11. **Out of scope for this version**.

## Rules

- Preserve the user's intent. Do not shrink scope silently; move uncertain items
  to non-goals or open questions.
- Prefer measurable statements over adjectives. Replace "fast" with a budget,
  "secure" with a specific control, and "user-friendly" with a concrete flow.
- Never invent external integrations the idea does not imply.
- If the idea is a content site, make the content model, public read path, and
  comment write path explicit.
- Write in English. Use a neutral, professional product-document voice.
