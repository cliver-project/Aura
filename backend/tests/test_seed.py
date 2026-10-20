from aura.services.seed import (
    DEFAULT_AGENTS,
    KNOWLEDGE_ROLE_KEYS,
    RAGFLOW_MCP_HEADERS,
    RAGFLOW_MCP_URL,
    knowledge_mcp_ids,
    knowledge_skill_names,
)


def test_default_agent_roles_are_unique() -> None:
    roles = [str(agent["role_key"]) for agent in DEFAULT_AGENTS]
    assert len(roles) == len(set(roles))


def test_pipeline_roles_are_seeded() -> None:
    roles = {str(agent["role_key"]) for agent in DEFAULT_AGENTS}
    required = {
        "ba",
        "architect",
        "risk-reviewer",
        "test-reviewer",
        "architecture-reviewer",
        "developer",
        "qe",
        "code-reviewer",
    }
    assert required <= roles


def test_knowledge_roles_include_pipeline_roles() -> None:
    assert {"ba", "architect", "risk-reviewer", "test-reviewer", "architecture-reviewer"} <= KNOWLEDGE_ROLE_KEYS


def test_ragflow_mcp_defaults_use_standalone_sse() -> None:
    assert RAGFLOW_MCP_URL == "{{ragflow_mcp_url}}"
    assert RAGFLOW_MCP_HEADERS == {"api_key": "{{ragflow_api_key}}"}


def test_knowledge_defaults_are_idempotent() -> None:
    assert knowledge_skill_names("ba", ["knowledge-base"]) == ["knowledge-base"]
    assert knowledge_skill_names("ba", []) == ["knowledge-base"]
    assert knowledge_skill_names("developer", []) == []
    assert knowledge_mcp_ids("ba", "server-1", ["server-1"]) == ["server-1"]
    assert knowledge_mcp_ids("ba", "server-1", []) == ["server-1"]
    assert knowledge_mcp_ids("developer", "server-1", []) == []
