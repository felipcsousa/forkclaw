# ADR-0002: Memory V1 Canonical Backend Model

## Status

Accepted

## Context

Forkclaw is SQLite-first and already persists sessions, tasks, tool calls, approvals, settings, and subagent lineage in the local database. Memory needed a canonical backend model that supports both automatic capture and direct user management without turning memory into a thin autosave layer.

The existing `memories` table is too simple for that goal. It stores key/value pairs but cannot represent lifecycle, provenance, subagent isolation, change history, security state, or anti-resurrection behavior.

## Decision

Adopt Memory V1 as a new canonical memory layer with these rules:

- `memory_entries` becomes the primary store for memory content
- `memory_change_log` is append-only and records before/after snapshots
- `session_summaries` persists memory-facing execution summaries
- `memory_relations` stores provenance and promotion links
- `memory_recall_log` is created now for future recall tracing
- legacy `memories` rows are backfilled once into `memory_entries`
- new code stops reading and writing `memories`
- memory identity keeps `session_key` separate from `conversation_id` inside the memory domain only
- editing automatic memory updates the same row id and converts it to `user_override`

## Consequences

Positive:

- manual memory becomes a real product surface, not debug state
- automatic capture and manual memory share one canonical schema
- change history survives destructive actions
- anti-resurrection becomes enforceable at the persistence layer
- subagent memory lineage stays explicit

Tradeoffs:

- Forkclaw temporarily carries both legacy `memories` and canonical V1 tables
- memory identity is richer than the rest of the runtime core for now
- hard delete needs extra guarding because history must survive it

## Rejected alternatives

### Dual-write with legacy `memories`

Rejected because it preserves ambiguity about the source of truth and complicates rollout and dedupe.

### Retrofitting `sessions` with a new global conversation identity now

Rejected because it would widen the blast radius beyond backend memory and violate the no-broad-refactor constraint.

### Creating override rows instead of in-place user overrides

Rejected for V1 because it would complicate admin UX, CRUD, and history lookup for limited product value.
