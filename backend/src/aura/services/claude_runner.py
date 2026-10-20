"""Run one Claude Code CLI process and stream its structured events."""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aura.config import get_settings

SANITIZED_ENV_PREFIXES = (
    "CLAUDE_CODE_SESSION_ID",
    "CLAUDE_CODE_CHILD_SESSION",
    "CLAUDE_CODE_SESSION_ATTENDED",
    "CLAUDE_CODE_MESSAGING_",
    "CLAUDE_CODE_ENTRYPOINT",
    "CLAUDE_CODE_EXECPATH",
    "CLAUDE_PID",
)

EventCallback = Callable[[dict[str, Any]], Awaitable[None]]

ACTIVE_PROCESSES: dict[str, asyncio.subprocess.Process] = {}


@dataclass
class RunResult:
    exit_code: int
    result_text: str = ""
    session_id: str | None = None
    cost_usd: float | None = None
    model_usage: dict[str, Any] = field(default_factory=dict)
    is_error: bool = False
    stderr: str = ""


def sanitized_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if not any(key.startswith(prefix) for prefix in SANITIZED_ENV_PREFIXES)
    }
    if extra:
        env.update(extra)
    return env


def _redact(text: str, env: dict[str, str]) -> str:
    for key, value in env.items():
        if value and any(marker in key.upper() for marker in ("TOKEN", "SECRET", "PASSWORD", "KEY")):
            text = text.replace(value, "***")
    return text


def _redact_value(value: Any, env: dict[str, str]) -> Any:
    if isinstance(value, str):
        return _redact(value, env)
    if isinstance(value, list):
        return [_redact_value(item, env) for item in value]
    if isinstance(value, dict):
        return {key: _redact_value(item, env) for key, item in value.items()}
    return value


def build_command(
    claude_bin: str,
    prompt: str,
    system_prompt: str = "",
    model: str = "",
    permission_mode: str = "bypassPermissions",
    mcp_config_path: str | None = None,
    allowed_tools: list[str] | None = None,
    max_budget_usd: float | None = None,
) -> list[str]:
    command = [
        claude_bin,
        "-p",
        prompt,
        "--output-format",
        "stream-json",
        "--verbose",
        "--permission-mode",
        permission_mode,
    ]
    if permission_mode == "bypassPermissions":
        command.append("--dangerously-skip-permissions")
    if system_prompt:
        command.extend(["--append-system-prompt", system_prompt])
    if model:
        command.extend(["--model", model])
    if mcp_config_path:
        command.extend(["--mcp-config", mcp_config_path, "--strict-mcp-config"])
    if allowed_tools:
        command.append("--allowedTools")
        command.extend(allowed_tools)
    if max_budget_usd and max_budget_usd > 0:
        command.extend(["--max-budget-usd", str(max_budget_usd)])
    return command


class ClaudeRunner:
    """Spawn Claude Code, parse stream-json lines, and support cancellation."""

    def __init__(self, claude_bin: str | None = None) -> None:
        settings = get_settings()
        self.claude_bin = claude_bin or settings.claude_bin
        self.permission_mode = settings.permission_mode
        self.max_budget_usd = settings.max_budget_usd

    def build_command(
        self,
        prompt: str,
        system_prompt: str = "",
        model: str = "",
        mcp_config_path: str | None = None,
        allowed_tools: list[str] | None = None,
        max_budget_usd: float | None = None,
    ) -> list[str]:
        return build_command(
            self.claude_bin,
            prompt,
            system_prompt=system_prompt,
            model=model,
            permission_mode=self.permission_mode,
            mcp_config_path=mcp_config_path,
            allowed_tools=allowed_tools,
            max_budget_usd=max_budget_usd if max_budget_usd is not None else self.max_budget_usd,
        )

    async def run(
        self,
        run_id: str,
        cwd: Path,
        prompt: str,
        system_prompt: str = "",
        model: str = "",
        mcp_config_path: str | None = None,
        allowed_tools: list[str] | None = None,
        env: dict[str, str] | None = None,
        on_event: EventCallback | None = None,
        timeout: float | None = None,
    ) -> RunResult:
        command = self.build_command(
            prompt,
            system_prompt=system_prompt,
            model=model,
            mcp_config_path=mcp_config_path,
            allowed_tools=allowed_tools,
        )
        child_env = sanitized_env(env)
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=child_env,
            # Claude Code's stream-json events can contain large hook output or
            # tool results. The asyncio default of 64 KiB per line raises
            # "Separator is not found, and chunk exceed the limit".
            limit=32 * 1024 * 1024,
        )
        ACTIVE_PROCESSES[run_id] = process

        result_text = ""
        session_id: str | None = None
        cost_usd: float | None = None
        model_usage: dict[str, Any] = {}
        is_error = False

        async def consume_stderr() -> str:
            assert process.stderr is not None
            chunks: list[bytes] = []
            while True:
                chunk = await process.stderr.readline()
                if not chunk:
                    break
                chunks.append(chunk)
            return _redact(b"".join(chunks).decode("utf-8", errors="replace"), child_env)

        stderr_task = asyncio.create_task(consume_stderr())

        async def consume_stdout() -> None:
            nonlocal result_text, session_id, cost_usd, model_usage, is_error
            assert process.stdout is not None
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").strip()
                if not text:
                    continue
                try:
                    event = json.loads(text)
                except json.JSONDecodeError:
                    event = {"type": "stdout", "text": text}
                event = _redact_value(event, child_env)
                if event.get("type") == "system" and event.get("session_id"):
                    session_id = event["session_id"]
                if event.get("type") == "result":
                    result_text = str(event.get("result") or "")
                    session_id = event.get("session_id") or session_id
                    cost_usd = event.get("total_cost_usd")
                    raw_usage = event.get("modelUsage")
                    model_usage = raw_usage if isinstance(raw_usage, dict) else {}
                    is_error = bool(event.get("is_error")) or event.get("subtype") == "error"
                if on_event is not None:
                    await on_event(event)

        try:
            if timeout:
                await asyncio.wait_for(consume_stdout(), timeout=timeout)
                await asyncio.wait_for(process.wait(), timeout=5)
            else:
                await consume_stdout()
                await process.wait()
        except TimeoutError:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=5)
            except TimeoutError:
                process.kill()
                await process.wait()
            is_error = True
            result_text = result_text or "Claude Code timed out."
        finally:
            ACTIVE_PROCESSES.pop(run_id, None)

        stderr = await stderr_task
        exit_code = process.returncode if process.returncode is not None else -1
        if exit_code != 0:
            is_error = True
        return RunResult(
            exit_code=exit_code,
            result_text=result_text,
            session_id=session_id,
            cost_usd=cost_usd,
            model_usage=model_usage,
            is_error=is_error,
            stderr=stderr,
        )

    @staticmethod
    def cancel(run_id: str) -> bool:
        process = ACTIVE_PROCESSES.get(run_id)
        if process is None or process.returncode is not None:
            return False
        process.terminate()
        return True

    @staticmethod
    def is_running(run_id: str) -> bool:
        process = ACTIVE_PROCESSES.get(run_id)
        return process is not None and process.returncode is None
