from __future__ import annotations

from typing import Any

from app.repositories.tools import ToolingRepository
from app.tools.base import ToolCachePort


class SqlToolCacheStore(ToolCachePort):
    def __init__(self, repository: ToolingRepository):
        self.repository = repository

    def get_json(self, *, tool_name: str, cache_key: str) -> dict[str, Any] | None:
        return self.repository.get_valid_cache_payload(tool_name, cache_key)

    def set_json(
        self,
        *,
        tool_name: str,
        cache_key: str,
        value: dict[str, Any],
        ttl_seconds: int,
    ) -> None:
        self.repository.save_cache_payload(
            tool_name=tool_name,
            cache_key=cache_key,
            payload=value,
            ttl_seconds=ttl_seconds,
        )
