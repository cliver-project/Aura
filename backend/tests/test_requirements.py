from aura.services.requirements import allocate_key, render_requirement


def test_allocate_key_starts_at_one() -> None:
    assert allocate_key([]) == "REQ-001"


def test_allocate_key_uses_highest_number() -> None:
    assert allocate_key(["REQ-001", "REQ-007", "REQ-003"]) == "REQ-008"


def test_allocate_key_ignores_malformed_keys() -> None:
    assert allocate_key(["NOPE", "REQ-XYZ", "REQ-002"]) == "REQ-003"


def test_render_requirement_contains_frontmatter_and_idea() -> None:
    content = render_requirement("REQ-001", "Content site", "A public page with comments.")
    assert content.startswith("---\nkey: REQ-001\n")
    assert "title: Content site" in content
    assert "A public page with comments." in content
    assert "## History" in content
