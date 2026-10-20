from aura.services.run_events import is_noise


def test_thinking_tokens_are_noise() -> None:
    assert is_noise({"type": "system", "subtype": "thinking_tokens"}) is True


def test_hook_events_are_noise() -> None:
    assert is_noise({"type": "system", "subtype": "hook_started"}) is True


def test_conversation_events_are_kept() -> None:
    assert is_noise({"type": "assistant", "message": {}}) is False
    assert is_noise({"type": "result", "subtype": "success"}) is False
    assert is_noise({"type": "system", "subtype": "init"}) is False
