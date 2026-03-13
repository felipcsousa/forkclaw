# Memory V1 Operations

## Scope

This runbook is the shortest path to validate Memory V1 locally on top of the integrated backend and desktop app.

Use it for:

- local setup
- migration validation
- runtime memory injection checks
- recall and search checks
- Memory Studio validation

For architecture details, see:

- `docs/architecture-memory-v1.md`
- `docs/memory-admin-core.md`
- `docs/memory-runtime-injection.md`
- `docs/memory-recall.md`
- `docs/memory-studio-ui.md`

## Local setup

From the repository root:

```bash
npm install
cd apps/backend
uv python install 3.11
uv sync
cd ../..
npm run migrate --workspace @nanobot/backend
npm run seed --workspace @nanobot/backend
```

Default local database:

```text
apps/backend/data/agent_os.db
```

Default desktop backend URL:

```text
http://127.0.0.1:8000
```

If needed:

```bash
cp apps/desktop/.env.example apps/desktop/.env
```

## Enable memory flags

Memory V1 is seeded disabled by default. Enable the feature flags before validating CRUD, recall, or Studio flows.

Run from `apps/backend`:

```bash
uv run python - <<'PY'
from sqlmodel import select

from app.db.session import get_db_session
from app.models.entities import Setting

flags = {
    "memory_v1_enabled": "true",
    "memory_manual_crud_enabled": "true",
    "memory_hard_delete_enabled": "false",
}

with get_db_session() as session:
    items = session.exec(
        select(Setting).where(Setting.scope == "features", Setting.key.in_(tuple(flags)))
    ).all()
    by_key = {item.key: item for item in items}
    for key, value in flags.items():
        setting = by_key[key]
        setting.value_text = value
        session.add(setting)
    session.commit()
PY
```

Confirm:

```bash
curl -s http://127.0.0.1:8000/settings | jq '.items[] | select(.scope=="features" and (.key | startswith("memory_"))) | {key, value_text}'
```

## Run locally

Backend only:

```bash
npm run dev:backend
```

Desktop only:

```bash
npm run dev:desktop
```

Both:

```bash
npm run dev
```

## Validate migrations

For a clean local migration pass, remove the local SQLite file and rebuild it:

```bash
rm -f apps/backend/data/agent_os.db
npm run migrate --workspace @nanobot/backend
npm run seed --workspace @nanobot/backend
```

Then run the focused migration contract tests:

```bash
npm run test --workspace @nanobot/backend -- \
  tests/test_schema_and_migrations.py \
  tests/test_memory_integration_contracts.py
```

What to check:

- canonical tables exist: `memory_entries`, `session_summaries`, `memory_recall_log`, `memory_relations`, `memory_change_log`
- runtime additions exist: `sessions.conversation_id`, `messages.conversation_id`
- FTS tables and triggers exist for `memory_entries` and `session_summaries`
- legacy compatibility tables still migrate cleanly

## Validate runtime memory injection

1. Start the backend and enable the memory flags.
2. Create a session:

```bash
curl -s -X POST http://127.0.0.1:8000/sessions \
  -H 'content-type: application/json' \
  -d '{"title":"Memory Runtime Demo"}'
```

3. Create a manual memory:

```bash
curl -s -X POST http://127.0.0.1:8000/memory/items \
  -H 'content-type: application/json' \
  -d '{
    "kind":"stable",
    "title":"Tea preference",
    "content":"The user prefers oolong tea in the afternoon.",
    "scope":"profile",
    "importance":"high"
  }'
```

4. Send a message that should recall the memory:

```bash
curl -s -X POST http://127.0.0.1:8000/agent/execute \
  -H 'content-type: application/json' \
  -d '{
    "title":"Recall demo",
    "message":"Please use the oolong tea preference."
  }'
```

5. Inspect the recall disclosure:

```bash
curl -s http://127.0.0.1:8000/memory/recall/messages/<assistant_message_id>
```

Expected result:

- the response contains `reason_summary`
- at least one recalled item is present
- the recalled item matches the created memory

## Validate conversation reset

Create a session, capture its `conversation_id`, then rotate it:

```bash
curl -s -X POST http://127.0.0.1:8000/sessions \
  -H 'content-type: application/json' \
  -d '{"title":"Conversation Reset Demo"}'

curl -s -X POST http://127.0.0.1:8000/sessions/<session_id>/reset
```

Expected result:

- `conversation_id` is present on create and reset
- the reset response returns a different `conversation_id`
- the session id stays the same

## Validate search and recall preview

Search:

```bash
curl -s "http://127.0.0.1:8000/memory/search?q=oolong"
```

Recall preview:

```bash
curl -s "http://127.0.0.1:8000/memory/recall/preview?q=oolong&limit=5"
```

Expected result:

- manual memory ranks ahead of equivalent autosaved memory
- hidden and soft-deleted items do not appear
- manual overrides replace the automatic base item in recall preview

## Validate Memory Studio

1. Start backend and desktop.
2. Open `Memory Studio` from the desktop navigation.
3. Confirm the main tabs render:
   - `All Memories`
   - `Stable Memory`
   - `Episodic Memory`
   - `Session Summaries`
   - `Recall Log`
4. Create a manual memory and verify it appears in the list.
5. Open the detail sheet and confirm metadata and history render.
6. Hide and restore the memory.
7. Trigger a chat response that uses memory and open the recall sheet.
8. Use `Open in Memory Studio` from the recall sheet and confirm it focuses the matching item.

## Focused regression commands

Backend memory coverage:

```bash
npm run test --workspace @nanobot/backend -- \
  tests/test_schema_and_migrations.py \
  tests/test_memory_integration_contracts.py \
  tests/test_prompt_context_service.py \
  tests/test_memory_recall.py \
  tests/test_memory_endpoints.py \
  tests/test_subagent_delegation.py
```

Desktop memory coverage:

```bash
npm run test --workspace @nanobot/desktop -- \
  src/components/ChatTimeline.test.tsx \
  src/components/MemoryRecallSheet.test.tsx \
  src/App.test.tsx
```

## Current limitations

- Memory feature flags are still opt-in in seeded local environments.
- `memories` remains as a compatibility surface; canonical Memory V1 state lives in `memory_entries` and `session_summaries`.
- Hard delete remains gated by `memory_hard_delete_enabled`.
- This runbook validates local SQLite flows only; it does not cover any external memory provider.
