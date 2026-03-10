from __future__ import annotations

import os

import httpx

from app.core.config import get_settings
from app.tools.web.providers.base import SearchProviderResponse, SearchResultItem

_BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"


class BraveWebSearchProvider:
    provider_id = "brave"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        timeout_seconds: float | None = None,
    ):
        self.api_key = (api_key or os.getenv("BRAVE_API_KEY", "")).strip()
        if not self.api_key:
            msg = "BRAVE_API_KEY is required to use web_search."
            raise ValueError(msg)
        self.timeout_seconds = timeout_seconds or get_settings().tool_timeout_seconds

    def search(self, query: str, count: int) -> SearchProviderResponse:
        params = {
            "q": query,
            "count": count,
            "text_decorations": "0",
            "result_filter": "web",
        }
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self.api_key,
        }
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.get(_BRAVE_SEARCH_URL, params=params, headers=headers)
            response.raise_for_status()

        payload = response.json()
        web_payload = payload.get("web") or {}
        raw_results = web_payload.get("results") or []

        results: list[SearchResultItem] = []
        for item in raw_results[:count]:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            url = str(item.get("url") or "").strip()
            snippet = str(item.get("description") or item.get("snippet") or "").strip()
            if not title or not url:
                continue
            results.append(
                SearchResultItem(
                    title=title,
                    url=url,
                    snippet=snippet,
                )
            )

        return SearchProviderResponse(
            provider=self.provider_id,
            query=query,
            results=results,
        )
