from __future__ import annotations

from app.tools.catalog import build_tool_catalog
from app.tools.policies import (
    get_tool_policy_profile,
    list_tool_policy_profiles,
    resolve_effective_permission_level,
)


def test_tool_catalog_exposes_canonical_metadata() -> None:
    catalog = build_tool_catalog()
    tool_ids = {item.id for item in catalog}

    assert {
        "list_files",
        "read_file",
        "write_file",
        "edit_file",
        "clipboard_read",
        "clipboard_write",
        "web_search",
        "web_fetch",
    } <= tool_ids

    by_id = {item.id: item for item in catalog}
    assert by_id["list_files"].group == "group:fs"
    assert by_id["write_file"].risk == "high"
    assert by_id["web_search"].status == "experimental"
    assert by_id["web_fetch"].group == "group:web"


def test_minimal_profile_denies_web_tools_by_default() -> None:
    profile = get_tool_policy_profile("minimal")

    assert profile.defaults["group:web"] == "deny"
    assert (
        resolve_effective_permission_level(
            profile_id="minimal",
            tool_group="group:web",
            override_level=None,
        )
        == "deny"
    )


def test_override_wins_over_profile_default() -> None:
    assert (
        resolve_effective_permission_level(
            profile_id="research",
            tool_group="group:web",
            override_level="ask",
        )
        == "ask"
    )


def test_profiles_are_listed_in_stable_order() -> None:
    profiles = list_tool_policy_profiles()

    assert [profile.id for profile in profiles] == ["minimal", "coding", "research", "full"]
