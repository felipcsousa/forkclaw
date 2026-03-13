# Memory Recall V1

Memory Recall V1 adds an audited backend-only read path for memory search and recall preview. It uses SQLite FTS5 first, then applies recall precedence and ranking in the service layer.

## Endpoints

### `GET /memory/search`

Inspection-only lexical search. This endpoint does not write `memory_recall_log`.

Example:

```http
GET /memory/search?q=banana&session_id=session-123&scope=current_conversation&scope=agent
```

Example response:

```json
{
  "query": "banana",
  "normalized_query": "banana",
  "applied_scopes": ["current_conversation", "agent"],
  "context": {
    "agent_id": "agent-1",
    "session_id": "session-123",
    "root_session_id": "session-123",
    "workspace_path": "/tmp/workspace",
    "user_scope_key": "local-user"
  },
  "items": [
    {
      "record_type": "memory_entry",
      "id": "mem-1",
      "summary": "banana briefing",
      "body": "banana launch protocol",
      "source_kind": "manual",
      "importance": 0.9,
      "score": 2.250001,
      "score_breakdown": {
        "lexical": 1.000001,
        "recency": 0.6,
        "importance": 0.9,
        "manual": 0.75,
        "duplicate_penalty": 0.0,
        "pre_duplicate_total": 3.250001,
        "final": 3.250001
      },
      "origin": {
        "table": "memory_entries",
        "agent_id": "agent-1",
        "session_id": "session-123",
        "root_session_id": "session-123",
        "origin_message_id": null,
        "origin_task_run_id": null,
        "workspace_path": null,
        "matched_scopes": ["current_conversation", "agent"]
      },
      "override": {
        "status": "none",
        "target_id": null,
        "effective_id": "mem-1",
        "selected_via_substitution": false
      }
    }
  ]
}
```

### `GET /memory/recall/preview`

Applies recall precedence and writes one row per returned memory to `memory_recall_log`.

Example:

```http
GET /memory/recall/preview?q=pineapple&session_id=session-123&run_id=run-123
```

Example response:

```json
{
  "query": "pineapple",
  "normalized_query": "pineapple",
  "run_id": "run-123",
  "applied_scopes": [
    "current_conversation",
    "current_session_tree",
    "agent",
    "user",
    "workspace"
  ],
  "context": {
    "agent_id": "agent-1",
    "session_id": "session-123",
    "root_session_id": "session-123",
    "workspace_path": "/tmp/workspace",
    "user_scope_key": "local-user"
  },
  "items": [
    {
      "record_type": "memory_entry",
      "id": "manual-9",
      "summary": "manual replacement",
      "body": "Operator correction",
      "source_kind": "manual",
      "importance": 0.2,
      "score": 1.550001,
      "score_breakdown": {
        "lexical": 1.000001,
        "recency": 0.6,
        "importance": 0.2,
        "manual": 0.75,
        "duplicate_penalty": 0.0,
        "pre_duplicate_total": 2.550001,
        "final": 2.550001
      },
      "origin": {
        "table": "memory_entries",
        "agent_id": null,
        "session_id": "session-123",
        "root_session_id": "session-123",
        "origin_message_id": null,
        "origin_task_run_id": null,
        "workspace_path": null,
        "matched_scopes": ["current_conversation", "current_session_tree"]
      },
      "override": {
        "status": "overrides_automatic",
        "target_id": "auto-7",
        "effective_id": "manual-9",
        "selected_via_substitution": true
      }
    }
  ]
}
```

### `GET /memory/scopes`

Returns supported scopes, resolved context, and the default scopes that will be used when the client omits `scope`.

Example response without `session_id`:

```json
{
  "context": {
    "agent_id": "agent-1",
    "session_id": null,
    "root_session_id": null,
    "workspace_path": "/tmp/workspace",
    "user_scope_key": "local-user"
  },
  "default_scopes": ["agent", "user", "workspace"],
  "supported_scopes": [
    {"name": "current_conversation", "available": false},
    {"name": "current_session_tree", "available": false},
    {"name": "agent", "available": true},
    {"name": "user", "available": true},
    {"name": "workspace", "available": true}
  ]
}
```

## Scope Rules

- With `session_id`, default scopes are `current_conversation`, `current_session_tree`, `agent`, `user`, and `workspace`.
- Without `session_id`, default scopes are `agent`, `user`, and `workspace`.
- Requesting `current_conversation` or `current_session_tree` without `session_id` returns `400`.
- Unknown `session_id` returns `404`.

## Precedence Rules

Recall preview always enforces these rules before the final ranking is returned:

1. `hidden_from_recall = true` never returns directly.
2. Soft-deleted rows (`deleted_at IS NOT NULL`) never return.
3. If an automatic memory has an active manual override, the manual memory replaces the automatic one in recall.
4. If that manual override is hidden, the automatic base is still suppressed.
5. If the manual override is soft-deleted, the automatic base becomes eligible again.
6. Duplicate effective results collapse to one item before duplicate penalties are applied.

## Ranking V1

Final ranking uses:

- lexical base from `-bm25(...)`
- recency boost: `<=1d +0.6`, `<=7d +0.3`, `<=30d +0.1`
- importance boost: `+importance`
- manual boost: `+0.75`
- duplicate penalty: `-0.2` for each earlier item with the same normalized content hash

The API returns the full score breakdown, and `memory_recall_log.reason_json` stores the same breakdown plus the substitution context when applicable.
