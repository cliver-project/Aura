import json
import sys

from aura.services.claude_runner import ClaudeRunner, build_command, sanitized_env


def _script(tmp_path, body: str):
    script = tmp_path / "fake-claude"
    script.write_text(f"#!{sys.executable}\n{body}\n", encoding="utf-8")
    script.chmod(0o755)
    return script


async def test_runner_parses_stream_events(tmp_path) -> None:
    script = _script(
        tmp_path,
        """
import json
print(json.dumps({"type": "system", "subtype": "init", "session_id": "sess-1"}))
print(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "working"}]}}))
print(json.dumps({
    "type": "result", "subtype": "success", "result": "done",
    "total_cost_usd": 0.02, "session_id": "sess-1",
}))
""",
    )
    events = []
    runner = ClaudeRunner(claude_bin=str(script))
    result = await runner.run(
        "run-1",
        tmp_path,
        "do the task",
        on_event=lambda event: _collect(events, event),
    )
    assert result.exit_code == 0
    assert result.result_text == "done"
    assert result.session_id == "sess-1"
    assert result.cost_usd == 0.02
    assert len(events) == 3
    assert events[-1]["type"] == "result"


async def _collect(events, event) -> None:
    events.append(event)


async def test_runner_handles_large_stream_lines(tmp_path) -> None:
    script = _script(
        tmp_path,
        """
import json
print(json.dumps({"type": "stdout", "text": "x" * 200000}))
print(json.dumps({"type": "result", "subtype": "success", "result": "done"}))
""",
    )
    events = []
    runner = ClaudeRunner(claude_bin=str(script))
    result = await runner.run("run-large", tmp_path, "big line", on_event=lambda event: _collect(events, event))
    assert result.exit_code == 0
    assert result.result_text == "done"
    assert events[0]["text"] == "x" * 200000


async def test_runner_reports_failure(tmp_path) -> None:
    script = _script(
        tmp_path,
        """
import sys
print("fatal problem", file=sys.stderr)
sys.exit(3)
""",
    )
    runner = ClaudeRunner(claude_bin=str(script))
    result = await runner.run("run-2", tmp_path, "do the task")
    assert result.exit_code == 3
    assert result.is_error is True
    assert "fatal problem" in result.stderr


def test_command_contains_required_flags(tmp_path) -> None:
    command = build_command(
        "claude",
        "prompt",
        system_prompt="system",
        model="sonnet",
        mcp_config_path=str(tmp_path / ".mcp.json"),
    )
    assert command[:2] == ["claude", "-p"]
    assert "--output-format" in command
    assert command[command.index("--output-format") + 1] == "stream-json"
    assert "--dangerously-skip-permissions" in command
    assert "--append-system-prompt" in command
    assert "--mcp-config" in command
    assert "--strict-mcp-config" in command


async def test_runner_captures_model_usage(tmp_path) -> None:
    script = _script(
        tmp_path,
        """
import json
print(json.dumps({
    "type": "result",
    "subtype": "success",
    "result": "done",
    "modelUsage": {
        "example-model": {
            "inputTokens": 10,
            "outputTokens": 2,
            "cacheReadInputTokens": 1,
            "cacheCreationInputTokens": 3,
            "costUSD": 0.01
        }
    }
}))
""",
    )
    runner = ClaudeRunner(claude_bin=str(script))
    result = await runner.run("run-usage", tmp_path, "do the task")
    assert result.model_usage["example-model"]["inputTokens"] == 10
    assert result.model_usage["example-model"]["cacheCreationInputTokens"] == 3


async def test_runner_redacts_secret_from_stdout_events_and_result(tmp_path) -> None:
    script = _script(
        tmp_path,
        """
import json
print(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "token=sk-secret"}]}}))
print(json.dumps({"type": "result", "subtype": "success", "result": "token=sk-secret"}))
""",
    )
    events = []
    runner = ClaudeRunner(claude_bin=str(script))
    result = await runner.run(
        "run-redact-stdout",
        tmp_path,
        "do the task",
        env={"ANTHROPIC_AUTH_TOKEN": "sk-secret"},
        on_event=lambda event: _collect(events, event),
    )
    assert result.exit_code == 0
    assert "sk-secret" not in result.result_text
    assert "***" in result.result_text
    assert all("sk-secret" not in json.dumps(event) for event in events)


async def test_runner_redacts_api_key_from_stderr(tmp_path) -> None:
    script = _script(
        tmp_path,
        """
import os
import sys
print(f"using {os.environ['ANTHROPIC_API_KEY']}", file=sys.stderr)
sys.exit(1)
""",
    )
    runner = ClaudeRunner(claude_bin=str(script))
    result = await runner.run(
        "run-redact",
        tmp_path,
        "do the task",
        env={"ANTHROPIC_API_KEY": "sk-super-secret"},
    )
    assert "sk-super-secret" not in result.stderr
    assert "***" in result.stderr


def test_sanitized_env_removes_child_session_markers(monkeypatch) -> None:
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "parent")
    monkeypatch.setenv("CLAUDE_CODE_CHILD_SESSION", "1")
    monkeypatch.setenv("ANTHROPIC_MODEL", "example-model")
    env = sanitized_env()
    assert "CLAUDE_CODE_SESSION_ID" not in env
    assert "CLAUDE_CODE_CHILD_SESSION" not in env
    assert env["ANTHROPIC_MODEL"] == "example-model"
