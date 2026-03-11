from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.skills.loader import SkillEntryConfig, resolve_skills
from app.skills.parser import SkillParseError, parse_skill_document
from app.skills.runtime import runtime_env, runtime_env_overlay


def _write_skill(
    root: Path,
    directory: str,
    *,
    name: str,
    description: str,
    metadata: str,
    body: str,
    enabled: str | None = None,
) -> Path:
    skill_dir = root / directory
    skill_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "---",
        f"name: {name}",
        f"description: {description}",
    ]
    if enabled is not None:
        lines.append(f"enabled: {enabled}")
    lines.extend(
        [
            f"metadata: {metadata}",
            "---",
            body,
        ]
    )
    path = skill_dir / "SKILL.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def test_parse_skill_document_reads_frontmatter_and_body(tmp_path: Path) -> None:
    path = _write_skill(
        tmp_path,
        "code-review",
        name="Code Review",
        description="Review risky changes.",
        metadata='{"forkclaw":{"requires":{"tools":["read_file"],"env":["REVIEW_TOKEN"]}}}',
        body="Always inspect tests before approving.",
        enabled="true",
    )

    parsed = parse_skill_document(path, origin="workspace")

    assert parsed.key == "code-review"
    assert parsed.name == "Code Review"
    assert parsed.description == "Review risky changes."
    assert parsed.origin == "workspace"
    assert parsed.enabled_by_default is True
    assert parsed.metadata["forkclaw"]["requires"]["tools"] == ["read_file"]
    assert parsed.content == "Always inspect tests before approving."


def test_parse_skill_document_rejects_missing_required_fields(tmp_path: Path) -> None:
    path = tmp_path / "broken" / "SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "---",
                "name: Missing Description",
                "metadata: {}",
                "---",
                "Body",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(SkillParseError, match="description"):
        parse_skill_document(path, origin="bundled")


def test_parse_skill_document_rejects_malformed_metadata_json(tmp_path: Path) -> None:
    path = _write_skill(
        tmp_path,
        "broken-json",
        name="Broken JSON",
        description="Bad metadata payload.",
        metadata='{"forkclaw": }',
        body="Body",
    )

    with pytest.raises(SkillParseError, match="metadata"):
        parse_skill_document(path, origin="bundled")


def test_resolve_skills_applies_precedence_and_gating(tmp_path: Path) -> None:
    bundled_root = tmp_path / "bundled"
    user_root = tmp_path / "user"
    workspace_root = tmp_path / "workspace"
    for root in (bundled_root, user_root, workspace_root):
        root.mkdir(parents=True, exist_ok=True)

    _write_skill(
        bundled_root,
        "review",
        name="Code Review",
        description="Bundled",
        metadata='{"forkclaw":{"requires":{"tools":["read_file"]}}}',
        body="Bundled body",
    )
    _write_skill(
        user_root,
        "review",
        name="Code Review",
        description="User",
        metadata='{"forkclaw":{"requires":{"tools":["read_file"]}}}',
        body="User body",
    )
    _write_skill(
        workspace_root,
        "review",
        name="Code Review",
        description="Workspace",
        metadata='{"forkclaw":{"requires":{"tools":["read_file"]}}}',
        body="Workspace body",
    )
    _write_skill(
        workspace_root,
        "darwin-only",
        name="Darwin Helper",
        description="OS constrained",
        metadata='{"forkclaw":{"os":["darwin"]}}',
        body="Only for macOS.",
    )
    _write_skill(
        workspace_root,
        "needs-env",
        name="Needs Env",
        description="Requires env",
        metadata='{"forkclaw":{"requires":{"env":["SPECIAL_TOKEN"]}}}',
        body="Needs token.",
    )

    result = resolve_skills(
        bundled_root=bundled_root,
        user_root=user_root,
        workspace_root=workspace_root,
        os_name="linux",
        available_tools={"read_file"},
        available_env={"SPECIAL_TOKEN": "configured"},
        config_by_key={},
    )

    by_key = {item.key: item for item in result.items}

    assert result.strategy == "all_eligible"
    assert [item.key for item in result.selected] == ["code-review", "needs-env"]
    assert by_key["code-review"].origin == "workspace"
    assert by_key["code-review"].content == "Workspace body"
    assert by_key["darwin-helper"].eligible is False
    assert by_key["darwin-helper"].blocked_reasons == ["unsupported_os"]
    assert by_key["needs-env"].eligible is True


def test_resolve_skills_uses_config_enablement_and_rejects_realpath_escape(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)
    external_root = tmp_path / "external"
    external_root.mkdir(parents=True, exist_ok=True)

    _write_skill(
        workspace_root,
        "toggle-me",
        name="Toggle Me",
        description="Config controlled",
        metadata="{}",
        body="Body",
    )
    _write_skill(
        external_root,
        "escaped",
        name="Escaped",
        description="Should be ignored",
        metadata="{}",
        body="Outside root",
    )
    (workspace_root / "symlinked").symlink_to(external_root / "escaped", target_is_directory=True)

    result = resolve_skills(
        bundled_root=tmp_path / "missing-bundled",
        user_root=tmp_path / "missing-user",
        workspace_root=workspace_root,
        os_name="linux",
        available_tools=set(),
        available_env={},
        config_by_key={
            "toggle-me": SkillEntryConfig(enabled=False),
        },
    )

    assert [item.key for item in result.items] == ["toggle-me"]
    assert result.items[0].eligible is False
    assert result.items[0].blocked_reasons == ["disabled"]


def test_runtime_env_overlay_is_scoped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BASE_TOKEN", "base-value")
    monkeypatch.delenv("SCOPED_TOKEN", raising=False)

    assert runtime_env("BASE_TOKEN") == "base-value"
    assert runtime_env("SCOPED_TOKEN") is None

    with runtime_env_overlay({"SCOPED_TOKEN": "scoped-value"}):
        assert runtime_env("BASE_TOKEN") == "base-value"
        assert runtime_env("SCOPED_TOKEN") == "scoped-value"

    assert runtime_env("SCOPED_TOKEN") is None
    assert os.getenv("SCOPED_TOKEN") is None
