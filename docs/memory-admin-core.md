# Memory Admin Core

## Scope

This document describes the backend-only administrative surface for Memory V1. It is intended to support a real memory panel later, not just internal debugging.

## Feature flags

Seeded in `settings` as disabled by default:

- `features.memory_v1_enabled=false`
- `features.memory_manual_crud_enabled=false`
- `features.memory_hard_delete_enabled=false`

Behavior:

- read routes return `404` when Memory V1 is disabled
- mutation routes return `403` when V1 is enabled but manual CRUD is disabled
- hard delete returns `403` unless the hard-delete flag is enabled

## Routes

### Read

- `GET /memory/entries`
- `GET /memory/entries/{id}`
- `GET /memory/entries/{id}/history`

`GET /memory/entries` supports:

- `limit`
- `offset`
- `scope_type`
- `source_kind`
- `lifecycle_state`
- `hidden`
- `deleted`
- `session_id`
- `conversation_id`
- `search`

### Mutation

- `POST /memory/entries`
- `PATCH /memory/entries/{id}`
- `DELETE /memory/entries/{id}`
- `POST /memory/entries/{id}/hide`
- `POST /memory/entries/{id}/unhide`
- `POST /memory/entries/{id}/promote`
- `POST /memory/entries/{id}/demote`
- `POST /memory/entries/{id}/restore`

## Mutation rules

- manual create: `source_kind=manual`
- manual edit: same row id
- automatic edit: same row id, changes to `user_override`
- promote: `episodic -> stable`
- demote: `stable -> episodic`
- hide/unhide: toggle `hidden_from_recall`
- soft delete: set `deleted_at`, preserve tombstone
- restore: clear `deleted_at`
- hard delete: physical delete after final history write

## Dedupe and conflicts

Dedupe uses normalized text hashing:

- NFKC normalize
- lowercase
- collapse whitespace
- concatenate `title`, `body`, `summary`
- SHA-256 hash

Manual create or edit returns `409` when the hash collides with another active memory. The response detail includes:

- `message`
- `existing_memory_id`
- `reason`

## Security rules

- raw secrets are rejected for manual memory
- prompt-injection content is rejected for curated/manual memory
- automatic capture redacts secrets before persistence
- automatic capture may flag but still store episodic content when the output is suspicious but not user-curated

## Capture notes

Automatic capture runs after successful execution persistence and also after subagent terminalization when needed. It creates:

- a `session_summaries` row
- an episodic `memory_entries` row when dedupe and anti-resurrection allow it

If capture is blocked by a user tombstone, the backend records `memory.capture.suppressed` in `audit_events`.
