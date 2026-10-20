import pytest

from aura.services.pipeline import (
    STAGES,
    knowledge_available,
    meaningful_file,
    report_verdict,
    stage_sequence,
    start_block_reason,
)


def test_delivered_requirement_cannot_start_again() -> None:
    assert "delivered" in (start_block_reason("done") or "").lower()
    assert start_block_reason("in_review") is None
    assert start_block_reason("rejected") is None


def test_knowledge_available_requires_key_mcp_and_skill() -> None:
    runtime = {"ragflow_api_key": "key"}
    assert knowledge_available(runtime, ["server-1"], ["knowledge-base"], "server-1") is True
    assert knowledge_available({}, ["server-1"], ["knowledge-base"], "server-1") is False
    assert knowledge_available(runtime, [], ["knowledge-base"], "server-1") is False
    assert knowledge_available(runtime, ["server-1"], [], "server-1") is False
    assert knowledge_available(runtime, ["server-1"], ["knowledge-base"], None) is False


def test_full_stage_sequence() -> None:
    assert stage_sequence() == list(STAGES)


def test_start_stage_truncates_sequence() -> None:
    assert stage_sequence("implement") == [
        "implement",
        "verify",
        "code_review",
    ]


def test_non_auto_runs_exactly_one_stage() -> None:
    assert stage_sequence("spec", auto=False) == ["spec"]


def test_unknown_start_stage_is_rejected() -> None:
    with pytest.raises(ValueError):
        stage_sequence("deploy")


def test_meaningful_file_requires_content(tmp_path) -> None:
    path = tmp_path / "doc.md"
    path.write_text("short", encoding="utf-8")
    assert meaningful_file(path) is False
    path.write_text("x" * 200, encoding="utf-8")
    assert meaningful_file(path) is True


def test_report_verdict_parsing() -> None:
    assert report_verdict("## Verdict\n- **Verdict** - fail\n") == "fail"
    assert report_verdict("- **Verdict** - pass with risks") == "pass_with_risks"
    assert report_verdict("- **Verdict** - pass") == "pass"
    assert report_verdict("no verdict here") == "unknown"


def test_verdict_section_wins_over_body_text() -> None:
    report = """# Verification

## Verdict

**pass with risks**

## Commands

- 242 passed, 0 failed
- startup failure is handled with fail fast
"""
    assert report_verdict(report) == "pass_with_risks"


def test_pass_verdict_with_failure_words_elsewhere_is_not_a_fail() -> None:
    report = """## Verdict
**pass**

## Negative paths
- 0 failed
- fail fast on corrupt schema
"""
    assert report_verdict(report) == "pass"
