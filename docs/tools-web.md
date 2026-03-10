# Web tools and tool registration

## Registered web tools

### `web_search`

Request payload:

```json
{
  "query": "nanobot",
  "count": 3
}
```

Response payload:

```json
{
  "provider": "brave",
  "query": "nanobot",
  "results": [
    {
      "title": "Nanobot Docs",
      "url": "https://docs.example.com/nanobot",
      "snippet": "Canonical docs result."
    }
  ],
  "cached": false
}
```

Example agent call:

```text
tool:web_search query='nanobot' count=3
```

Notes:
- Provider adapters live under `apps/backend/app/tools/web/providers/`.
- The first provider is Brave Search and requires `BRAVE_API_KEY`.
- Results are cached in SQLite via `tool_cache_entries`.

### `web_fetch`

Request payload:

```json
{
  "url": "https://example.com/article",
  "extract_mode": "markdown",
  "max_chars": 2000
}
```

Response payload:

```json
{
  "url": "https://example.com/article",
  "final_url": "https://example.com/article",
  "title": "Example article",
  "extract_mode": "markdown",
  "content": "# Example article\n\nBody paragraph from the web.",
  "truncated": false,
  "cached": false
}
```

Example agent call:

```text
tool:web_fetch url='https://example.com/article' extract_mode=markdown max_chars=2000
```

Notes:
- `web_fetch` only allows `http` and `https`.
- Private, loopback, link-local and similar hosts are blocked.
- The implementation is intentionally non-headless in this phase.

## How to register a new tool

1. Add the executable tool implementation to `apps/backend/app/tools/registry.py` with a `ToolDescriptor`.
2. Add the canonical catalog entry to `apps/backend/app/tools/catalog.py` with `id`, `label`, `description`, `group`, `risk`, `status`, schemas and workspace requirement.
3. Make sure the tool group has a default permission in `apps/backend/app/tools/policies.py`.
4. If the tool needs config or cache behavior, wire it through `ToolExecutionContext` and `apps/backend/app/core/config.py`.
5. Expose any frontend metadata by consuming `/tools/catalog` and `/tools/policy`; the frontend should not hardcode tool definitions.
