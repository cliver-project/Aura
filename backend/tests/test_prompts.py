import pytest

from aura.prompts.stages import StageContext, build_stage_prompt


def _context(**overrides) -> StageContext:
    values = {
        "project_name": "Demo",
        "project_slug": "demo",
        "requirement_id": "req-1",
        "requirement_key": "REQ-001",
        "requirement_title": "Content site",
        "requirement_path": "docs/requirements/REQ-001.md",
        "requirement_content": "A public page with comments.",
        "branch": "main",
        "spec_path": "docs/specs/REQ-001-tech-spec.md",
    }
    values.update(overrides)
    return StageContext(**values)


def test_refine_prompt_names_deliverable_and_language() -> None:
    prompt = build_stage_prompt("refine", _context())
    assert "docs/requirements/REQ-001.md" in prompt
    assert "English" in prompt
    assert "version: 2" in prompt
    assert "A public page with comments." in prompt


def test_spec_prompt_requires_acceptance_mapping() -> None:
    prompt = build_stage_prompt("spec", _context())
    assert "docs/specs/REQ-001-tech-spec.md" in prompt
    assert "acceptance criterion" in prompt
    assert "Do not implement code" in prompt


def test_challenge_prompt_uses_angle_and_all_reviews() -> None:
    prompt = build_stage_prompt("challenge", _context(angle="risk"))
    assert "docs/reviews/REQ-001-risk.md" in prompt
    assert "**risk**" in prompt


def test_consolidate_prompt_lists_reviews() -> None:
    prompt = build_stage_prompt(
        "consolidate",
        _context(review_paths=["docs/reviews/REQ-001-risk.md", "docs/reviews/REQ-001-test.md"]),
    )
    assert "docs/reviews/REQ-001-risk.md" in prompt
    assert "docs/reviews/REQ-001-test.md" in prompt
    assert "docs/reviews/REQ-001-response.md" in prompt


def test_delivery_prompts_include_human_merge_rule() -> None:
    for stage in ("implement", "verify", "code_review"):
        prompt = build_stage_prompt(stage, _context())
        assert "Do not create a pull request" in prompt or "Do not commit or push" in prompt


def test_knowledge_guardrail_is_included_for_refine_when_enabled() -> None:
    prompt = build_stage_prompt(
        "refine",
        _context(knowledge_enabled=True, knowledge_dataset_ids=["ds-1", "ds-2"]),
    )
    assert "ragflow_retrieval" in prompt
    assert "ds-1" in prompt and "ds-2" in prompt
    assert "Knowledge base references" in prompt


def test_knowledge_guardrail_is_absent_when_disabled() -> None:
    prompt = build_stage_prompt("refine", _context(knowledge_enabled=False))
    assert "ragflow_retrieval" not in prompt


def test_delivery_stages_do_not_require_a_citation_section() -> None:
    prompt = build_stage_prompt(
        "implement",
        _context(knowledge_enabled=True, knowledge_dataset_ids=["ds-1"]),
    )
    assert "ragflow_retrieval" in prompt
    assert "Knowledge base references" not in prompt


def test_knowledge_guardrail_handles_no_bound_datasets() -> None:
    prompt = build_stage_prompt(
        "spec",
        _context(knowledge_enabled=True, knowledge_dataset_ids=[]),
    )
    assert "ragflow_list_datasets" in prompt
    assert "all datasets" in prompt
    assert "pass all returned dataset IDs" in prompt


def test_unknown_stage_is_rejected() -> None:
    with pytest.raises(ValueError):
        build_stage_prompt("unknown", _context())
