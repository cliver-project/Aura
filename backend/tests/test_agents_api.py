from datetime import UTC, datetime
from types import SimpleNamespace

from aura.api.agents import _to_out


def test_agent_out_masks_secret_env_values() -> None:
    now = datetime.now(UTC)
    agent = SimpleNamespace(
        id="agent-1",
        name="Probe",
        role_key="probe",
        description="",
        system_prompt="",
        model="",
        allowed_tools=[],
        skill_names=[],
        mcp_server_ids=[],
        env={"ANTHROPIC_AUTH_TOKEN": "secret", "ANTHROPIC_MODEL": "model"},
        enabled=True,
        is_builtin=False,
        created_at=now,
        updated_at=now,
    )
    out = _to_out(agent)
    assert out.env["ANTHROPIC_AUTH_TOKEN"] == "********"
    assert out.env["ANTHROPIC_MODEL"] == "model"
