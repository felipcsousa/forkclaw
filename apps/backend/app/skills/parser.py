from __future__ import annotations

import json
import re
from pathlib import Path

from app.skills.models import SkillDefinition, SkillOrigin

_FRONTMATTER_DELIMITER = "---"
_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


class SkillParseError(ValueError):
    """Raised when a skill file does not follow the v1 SKILL.md format."""


def parse_skill_document(path: Path, *, origin: SkillOrigin) -> SkillDefinition:
    raw_text = path.read_text(encoding="utf-8")
    frontmatter, body = _split_frontmatter(raw_text, path)
    values = _parse_frontmatter(frontmatter, path)
    name = _require_text(values, "name", path)
    description = _require_text(values, "description", path)
    metadata = _parse_metadata(values.get("metadata"), path)
    enabled_by_default = _parse_enabled(values.get("enabled"), path)
    content = body.strip()
    return SkillDefinition(
        key=_slugify(name),
        name=name,
        description=description,
        origin=origin,
        source_path=str(path.resolve()),
        content=content,
        metadata=metadata,
        enabled_by_default=enabled_by_default,
    )


def _split_frontmatter(raw_text: str, path: Path) -> tuple[list[str], str]:
    lines = raw_text.splitlines()
    if len(lines) < 3 or lines[0].strip() != _FRONTMATTER_DELIMITER:
        raise SkillParseError(f"{path}: expected leading frontmatter delimiter.")

    try:
        closing_index = next(
            index
            for index, line in enumerate(lines[1:], start=1)
            if line.strip() == _FRONTMATTER_DELIMITER
        )
    except StopIteration as exc:
        raise SkillParseError(f"{path}: missing closing frontmatter delimiter.") from exc

    return lines[1:closing_index], "\n".join(lines[closing_index + 1 :])


def _parse_frontmatter(lines: list[str], path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        if ":" not in line:
            raise SkillParseError(f"{path}: invalid frontmatter line `{raw_line}`.")
        key, raw_value = line.split(":", 1)
        values[key.strip()] = _unquote(raw_value.strip())
    return values


def _require_text(values: dict[str, str], key: str, path: Path) -> str:
    value = (values.get(key) or "").strip()
    if not value:
        raise SkillParseError(f"{path}: missing required frontmatter field `{key}`.")
    return value


def _parse_metadata(value: str | None, path: Path) -> dict[str, object]:
    if value is None:
        raise SkillParseError(f"{path}: missing required frontmatter field `metadata`.")
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise SkillParseError(f"{path}: metadata must be valid JSON.") from exc
    if not isinstance(parsed, dict):
        raise SkillParseError(f"{path}: metadata must decode to an object.")
    return parsed


def _parse_enabled(value: str | None, path: Path) -> bool:
    if value is None or value == "":
        return True
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    raise SkillParseError(f"{path}: enabled must be a boolean.")


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _slugify(value: str) -> str:
    normalized = _SLUG_PATTERN.sub("-", value.strip().lower()).strip("-")
    return normalized or "skill"
