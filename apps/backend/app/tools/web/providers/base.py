from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SearchResultItem:
    title: str
    url: str
    snippet: str


@dataclass(frozen=True)
class SearchProviderResponse:
    provider: str
    query: str
    results: list[SearchResultItem]


class WebSearchProvider(Protocol):
    def search(self, query: str, count: int) -> SearchProviderResponse:
        """Execute a provider-backed web search."""
