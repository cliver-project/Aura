"""English prompts for every pipeline stage."""

from __future__ import annotations

from dataclasses import dataclass, field

STAGE_DELIVERABLES = {
    "refine": "docs/requirements/{key}.md",
    "spec": "docs/specs/{key}-tech-spec.md",
    "challenge": "docs/reviews/{key}-{angle}.md",
    "consolidate": "docs/specs/{key}-tech-spec.md and docs/reviews/{key}-response.md",
    "implement": "working code and tests on the feature branch",
    "verify": "docs/reports/{key}-verification.md",
    "code_review": "docs/reviews/{key}-code-review.md",
}


@dataclass
class StageContext:
    project_name: str
    project_slug: str
    requirement_id: str
    requirement_key: str
    requirement_title: str
    requirement_path: str
    requirement_content: str
    branch: str
    repo_url: str = ""
    target_version: int = 2
    angle: str = ""
    spec_path: str = ""
    review_paths: list[str] = field(default_factory=list)
    knowledge_enabled: bool = False
    knowledge_dataset_ids: list[str] = field(default_factory=list)


KNOWLEDGE_HINTS = {
    "refine": "Search for business rules, domain terminology, prior requirements, and constraints.",
    "spec": "Search for architecture decisions, existing interfaces, conventions, and deployment limits.",
    "challenge": "Search for past incidents, security policies, edge cases, and previous failures.",
    "consolidate": "Search for prior decisions and accepted trade-offs the reviews depend on.",
    "implement": "Search when project conventions or prior decisions would change your implementation.",
    "verify": "Search when project conventions or prior decisions affect expected behavior.",
    "code_review": "Search when project conventions or prior decisions affect the review.",
}


def _knowledge_section(context: StageContext, stage: str) -> str:
    if not context.knowledge_enabled:
        return ""
    if context.knowledge_dataset_ids:
        ids = ", ".join(context.knowledge_dataset_ids)
        scope = (
            f"Bound dataset IDs: {ids}. Pass them as `dataset_ids` to `ragflow_retrieval`."
        )
    else:
        scope = (
            "No datasets are bound to this project. Call `ragflow_list_datasets` first, "
            "then pass all returned dataset IDs as `dataset_ids` to `ragflow_retrieval`; "
            "the tool also searches across all datasets when the list is omitted."
        )
    hint = KNOWLEDGE_HINTS.get(stage, "Search when project knowledge would change your work.")
    if stage in {"implement", "verify", "code_review"}:
        return f"""
Knowledge base:
- You have the `ragflow` MCP server with `ragflow_list_datasets` and `ragflow_retrieval`.
- Use the `knowledge-base` skill when project knowledge would change your work. {hint}
- {scope}
- Retrieval is optional for this stage. An unavailable or empty knowledge base must
  never block the stage.
"""
    return f"""
Knowledge base:
- You have the `ragflow` MCP server with `ragflow_list_datasets` and `ragflow_retrieval`.
- Use the `knowledge-base` skill. {hint}
- {scope}
- Before writing the deliverable, run at least one focused `ragflow_retrieval` query.
- Add a `## Knowledge base references` section listing each dataset ID, document ID,
  and a short quote you used. If retrieval returns nothing relevant, write
  "No relevant knowledge base results" and continue.
- Retrieval is supporting context. An unavailable or empty knowledge base must
  never block the stage.
"""


def _header(context: StageContext, stage: str) -> str:
    return f"""You are working on the project "{context.project_name}" ({context.project_slug}).

Requirement: {context.requirement_key} - {context.requirement_title}
Requirement document: {context.requirement_path}
Current branch: {context.branch}
Repository: {context.repo_url}

Stage: {stage}
Deliverable: {STAGE_DELIVERABLES[stage].format(key=context.requirement_key, angle=context.angle or "review")}

Use the skills available in .claude/skills. Read the requirement document and
the existing repository before writing. Do not ask questions. Make reasonable
assumptions and record them in your deliverable. Write everything in English.
{_knowledge_section(context, stage)}"""


def _require_path(context: StageContext, path: str) -> str:
    return f"You MUST write the deliverable to `{path}`. Finish only after the file exists and is complete.\n"


def build_stage_prompt(stage: str, context: StageContext) -> str:
    if stage not in STAGE_DELIVERABLES:
        raise ValueError(f"Unknown pipeline stage: {stage}")
    header = _header(context, stage)

    if stage == "refine":
        return (
            header
            + _require_path(context, context.requirement_path)
            + f"""
Rewrite the requirement into a structured, testable document using the
requirement-refinement skill. Preserve the YAML front matter fields `key` and
`title`; set `version: {context.target_version}` and `status: in_review`.
Cover summary, problem, goals, non-goals, users, functional requirements,
non-functional requirements, acceptance criteria, edge cases, and open
questions. Preserve the original intent.

Current requirement content:

```markdown
{context.requirement_content}
```
"""
        )

    if stage == "spec":
        spec_path = context.spec_path or f"docs/specs/{context.requirement_key}-tech-spec.md"
        return (
            header
            + _require_path(context, spec_path)
            + f"""
Write an implementation-ready technical specification using the tech-spec skill.
The repository is a {context.project_slug} project. Read the requirement at
`{context.requirement_path}` and inspect the existing code and `CLAUDE.md`.
Name concrete files, interfaces, data models, failure modes, test cases, and an
ordered implementation plan. Map every acceptance criterion to a design element
and a test. Do not implement code in this stage.
"""
        )

    if stage == "challenge":
        angle = context.angle or "review"
        path = f"docs/reviews/{context.requirement_key}-{angle}.md"
        return (
            header
            + _require_path(context, path)
            + f"""
Challenge the specification from the **{angle}** angle using the
adversarial-review skill. Read the requirement and the technical specification
at `{context.spec_path or f"docs/specs/{context.requirement_key}-tech-spec.md"}`.
Find missing failure modes, unsafe assumptions, boundary conditions, and test
gaps. Rank findings by severity. Every finding needs a concrete failure
scenario, input data, and a test that would expose it. Do not implement code.
"""
        )

    if stage == "consolidate":
        spec_path = context.spec_path or f"docs/specs/{context.requirement_key}-tech-spec.md"
        review_list = "\n".join(f"- `{path}`" for path in context.review_paths)
        return (
            header
            + _require_path(context, spec_path)
            + f"""
Read the technical specification and every adversarial review listed below.
Update `{spec_path}` so it resolves or explicitly rejects each finding, and
write a response log to `docs/reviews/{context.requirement_key}-response.md` with
a table: finding, decision (accepted/rejected/deferred), rationale, and the spec
section that changed. Add missing tests and failure handling to the spec. Do not
implement code.

Reviews:
{review_list}
"""
        )

    if stage == "implement":
        return (
            header
            + f"""
Implement the technical specification at
`{context.spec_path or f"docs/specs/{context.requirement_key}-tech-spec.md"}`
using the implementation skill. The branch `{context.branch}` is already checked
out. Read the requirement and `CLAUDE.md`, run the existing tests first, then
implement the specified behavior with focused tests. Run the full test suite.
Do not create a pull request; the orchestrator commits and pushes your changes.
Leave the repository clean and working. Summarize files changed, commands run,
and test results in your final response.
"""
        )

    if stage == "verify":
        return (
            header
            + _require_path(context, f"docs/reports/{context.requirement_key}-verification.md")
            + f"""
Verify the implementation using the verification skill. Read the requirement,
the specification, and the diff against `origin/main`
(`git diff origin/main...HEAD`). Install dependencies,
run the full test suite and build/typecheck, and perform a live smoke check if
the project starts a server. Map every acceptance criterion to evidence. Write
the report to `docs/reports/{context.requirement_key}-verification.md` with a
clear verdict. Do not modify application code. Do not commit or push.
"""
        )

    if stage == "code_review":
        return (
            header
            + _require_path(context, f"docs/reviews/{context.requirement_key}-code-review.md")
            + f"""
Review the pull request diff using the code-review skill. Read the requirement,
the specification, and `git diff origin/main...HEAD`. Check correctness,
security, maintainability, and test coverage. Write severity-ranked findings
with file, line, failure scenario, and a concrete fix to
`docs/reviews/{context.requirement_key}-code-review.md`. Give a clear verdict.
Do not modify code. Do not commit or push.
"""
        )

    raise ValueError(f"Unknown pipeline stage: {stage}")


class PromptBuilder:
    """Compatibility wrapper used by the pipeline."""

    @staticmethod
    def system(profile) -> str:
        return str(profile.system_prompt)

    @staticmethod
    def stage(stage: str, context: StageContext) -> str:
        return build_stage_prompt(stage, context)
