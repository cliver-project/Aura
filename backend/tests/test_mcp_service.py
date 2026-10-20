from pathlib import Path
from types import SimpleNamespace

from aura.services.mcp_service import (
    McpService,
    build_mcp_config,
    cleanup_runtime_configs,
    mask_mapping,
    remove_runtime_config,
    resolve_placeholders,
    write_mcp_config,
)


def _server(**overrides):
    values = {
        "name": "files",
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem"],
        "env": {"API_TOKEN": "secret", "ROOT": "/tmp"},
        "url": "",
        "headers": {},
        "enabled": True,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_stdio_config_shape() -> None:
    config, warnings = build_mcp_config([_server()])
    assert config == {
        "mcpServers": {
            "files": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem"],
                "env": {"API_TOKEN": "secret", "ROOT": "/tmp"},
            }
        }
    }
    assert warnings == []


def test_stdio_server_ignores_url_and_header_placeholders() -> None:
    server = _server(url="{{missing}}", headers={"X-Test": "{{missing}}"})
    config, warnings = build_mcp_config([server], {})
    assert "files" in config["mcpServers"]
    assert warnings == []


def test_http_config_shape_and_disabled_filter() -> None:
    config, _warnings = build_mcp_config(
        [
            _server(name="remote", transport="http", command="", args=[], url="http://localhost:9000"),
            _server(name="off", enabled=False),
        ]
    )
    assert config["mcpServers"]["remote"] == {
        "type": "http",
        "url": "http://localhost:9000",
        "headers": {},
    }
    assert "off" not in config["mcpServers"]


def test_secret_headers_are_masked() -> None:
    masked = mask_mapping({"Authorization": "Bearer secret", "X-Other": "visible"})
    assert masked["Authorization"] == "********"
    assert masked["X-Other"] == "visible"


def test_placeholders_resolve_from_runtime() -> None:
    server = _server(
        name="ragflow",
        transport="http",
        command="",
        args=[],
        url="{{ragflow_url}}/api/v1/mcp",
        headers={"Authorization": "Bearer {{ragflow_api_key}}"},
    )
    runtime = {"ragflow_url": "http://127.0.0.1:9380", "ragflow_api_key": "secret"}
    config, warnings = build_mcp_config([server], runtime)
    assert config["mcpServers"]["ragflow"]["url"] == "http://127.0.0.1:9380/api/v1/mcp"
    assert config["mcpServers"]["ragflow"]["headers"]["Authorization"] == "Bearer secret"
    assert warnings == []


def test_env_placeholders_resolve_too() -> None:
    server = _server(env={"TOKEN": "{{ragflow_api_key}}", "ROOT": "/tmp"})
    config, _warnings = build_mcp_config([server], {"ragflow_api_key": "secret"})
    assert config["mcpServers"]["files"]["env"]["TOKEN"] == "secret"


def test_server_with_unresolved_placeholder_is_omitted() -> None:
    server = _server(
        name="ragflow",
        transport="http",
        command="",
        args=[],
        url="{{ragflow_url}}/api/v1/mcp",
        headers={"Authorization": "Bearer {{ragflow_api_key}}"},
    )
    config, warnings = build_mcp_config([server], {"ragflow_url": "http://x", "ragflow_api_key": ""})
    assert "ragflow" not in config["mcpServers"]
    assert any("ragflow" in warning for warning in warnings)


def test_non_stdio_server_without_url_is_omitted() -> None:
    config, warnings = build_mcp_config([_server(name="remote", transport="http", url="")])
    assert "remote" not in config["mcpServers"]
    assert any("remote" in warning for warning in warnings)


def test_resolve_placeholders_returns_none_for_empty_value() -> None:
    assert resolve_placeholders("{{a}}/x", {"a": "v"}) == "v/x"
    assert resolve_placeholders("{{a}}/x", {"a": ""}) is None
    assert resolve_placeholders("plain", {}) == "plain"


def test_runtime_config_is_written_outside_workspace_with_0600(tmp_path) -> None:
    path = write_mcp_config({"mcpServers": {}}, "run-1", directory=tmp_path)
    assert path.parent == tmp_path
    assert oct(path.stat().st_mode & 0o777) == "0o600"


def test_remove_runtime_config_is_safe_for_missing_and_none(tmp_path) -> None:
    path = tmp_path / "run.json"
    path.write_text("{}", encoding="utf-8")
    remove_runtime_config(path)
    assert not path.exists()
    remove_runtime_config(path)
    remove_runtime_config(None)


def test_cleanup_runtime_configs_removes_secret_files_only(tmp_path) -> None:
    (tmp_path / "run-1.json").write_text("{}", encoding="utf-8")
    (tmp_path / "keep.txt").write_text("x", encoding="utf-8")
    assert cleanup_runtime_configs(tmp_path) == 1
    assert not (tmp_path / "run-1.json").exists()
    assert (tmp_path / "keep.txt").exists()


async def test_prepare_writes_empty_config_when_no_servers(monkeypatch) -> None:
    calls: list[tuple[dict, str]] = []

    def fake_write(config: dict, run_id: str) -> Path:
        calls.append((config, run_id))
        return Path("/tmp/empty-mcp.json")

    monkeypatch.setattr("aura.services.mcp_service.write_mcp_config", fake_write)
    path, warnings = await McpService.prepare([], {}, "run-empty")
    assert path == Path("/tmp/empty-mcp.json")
    assert calls == [({"mcpServers": {}}, "run-empty")]
    assert warnings == []


def test_relative_config_directory_is_resolved(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    path = write_mcp_config({"mcpServers": {}}, "run-relative", directory=Path("mcp"))
    assert path.is_absolute()
    assert path.parent == (tmp_path / "mcp").resolve()
