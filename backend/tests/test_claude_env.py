from aura.services.claude_env import (
    build_claude_env,
    is_secret_env_key,
    mask_env,
    restore_masked_env,
)


def test_global_provider_env_maps_all_reference_variables() -> None:
    runtime = {
        "anthropic_base_url": "https://api.deepseek.com/anthropic",
        "anthropic_auth_token": "tok",
        "anthropic_model": "deepseek-v4-flash",
        "anthropic_default_opus_model": "deepseek-v4-flash",
        "anthropic_default_sonnet_model": "deepseek-v4-flash",
        "anthropic_default_haiku_model": "deepseek-v4-flash",
        "claude_code_subagent_model": "deepseek-v4-flash",
        "claude_code_effort_level": "max",
        "claude_code_auto_compact_window": "1000000",
        "claude_code_disable_unknown_model_window_enforcement": True,
    }
    env = build_claude_env(runtime)
    assert env["ANTHROPIC_BASE_URL"] == "https://api.deepseek.com/anthropic"
    assert env["ANTHROPIC_AUTH_TOKEN"] == "tok"
    assert env["ANTHROPIC_MODEL"] == "deepseek-v4-flash"
    assert env["ANTHROPIC_DEFAULT_OPUS_MODEL"] == "deepseek-v4-flash"
    assert env["CLAUDE_CODE_SUBAGENT_MODEL"] == "deepseek-v4-flash"
    assert env["CLAUDE_CODE_EFFORT_LEVEL"] == "max"
    assert env["CLAUDE_CODE_AUTO_COMPACT_WINDOW"] == "1000000"
    assert env["CLAUDE_CODE_DISABLE_UNKNOWN_MODEL_WINDOW_ENFORCEMENT"] == "1"


def test_agent_overrides_win_and_empty_values_are_omitted() -> None:
    runtime = {"anthropic_base_url": "https://global", "anthropic_model": "global-model"}
    env = build_claude_env(
        runtime,
        {"ANTHROPIC_BASE_URL": "https://agent", "ANTHROPIC_MODEL": ""},
    )
    assert env["ANTHROPIC_BASE_URL"] == "https://agent"
    assert env["ANTHROPIC_MODEL"] == "global-model"


def test_secret_detection_and_masking() -> None:
    assert is_secret_env_key("ANTHROPIC_AUTH_TOKEN") is True
    assert is_secret_env_key("CLAUDE_CODE_EFFORT_LEVEL") is False
    masked = mask_env({"ANTHROPIC_AUTH_TOKEN": "secret", "ANTHROPIC_MODEL": "m"})
    assert masked["ANTHROPIC_AUTH_TOKEN"] == "********"
    assert masked["ANTHROPIC_MODEL"] == "m"


def test_masked_update_preserves_existing_secret() -> None:
    current = {"ANTHROPIC_AUTH_TOKEN": "secret", "ANTHROPIC_MODEL": "old"}
    updated = restore_masked_env(
        current,
        {"ANTHROPIC_AUTH_TOKEN": "********", "ANTHROPIC_MODEL": "new"},
    )
    assert updated == {"ANTHROPIC_AUTH_TOKEN": "secret", "ANTHROPIC_MODEL": "new"}
