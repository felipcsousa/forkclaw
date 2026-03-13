# Memory V1 Architecture

## Purpose

Memory V1 defines a canonical backend memory layer for Forkclaw with two first-class entry paths:

- automatic capture from runtime activity
- manual CRUD controlled by the user

The database is the source of truth. Markdown is allowed only as an export mirror and never as canonical state.

## Core separation

Memory V1 keeps four planes explicit in `memory_entries.scope_type`:

- `operational`: short-lived operational state that exists to support execution, not long-term recall
- `stable`: curated memory worth reusing across future work
- `episodic`: searchable event-like memory captured from sessions and subagents
- `manual`: user-managed memory added or corrected explicitly

This separation prevents memory from collapsing into agent autosave.

## Identity rules

- `session_key`: durable routing identity, stored in `scope_key` for memory-owned records
- `conversation_id`: ephemeral logical thread id, separate from `session_key`
- `run_id`: execution identity, stored in memory metadata and session summaries
- `parent_session_id`: subagent lineage marker

Forkclaw does not retrofit the current session core for V1. Existing `sessions.id` and `task_runs.id` remain intact; the separation is enforced inside memory contracts, memory tables, and memory services.

## Canonical tables

### `memory_entries`

Primary memory store for manual, autosaved, promoted, and overridden memory.

Key fields:

- `scope_type`, `scope_key`
- `conversation_id`, `session_id`, `parent_session_id`
- `source_kind`, `lifecycle_state`
- `title`, `body`, `summary`
- `importance`, `confidence`
- `dedupe_hash`
- `created_by`, `updated_by`
- `redaction_state`, `security_state`
- `hidden_from_recall`, `deleted_at`

### `memory_relations`

Links between entries for provenance and future recall tooling.

Used for relation kinds such as:

- `promoted_from_session`
- `promoted_from_subagent`
- `duplicate_of`
- `override_of`

### `memory_recall_log`

Append-only trace for future recall decisions and ranking inputs.

### `session_summaries`

Memory-facing summaries keyed by session identity and run metadata. This is separate from UI chat summaries.

### `memory_change_log`

Append-only audit trail for every material change, with before/after snapshots.

## Manual memory semantics

- create always writes `source_kind=manual`
- editing a manual memory keeps the same row id
- editing an automatic memory keeps the same row id and flips `source_kind` to `user_override`
- promote changes `scope_type` from `episodic` to `stable`
- demote changes `scope_type` from `stable` to `episodic`
- hide/unhide only toggles `hidden_from_recall`
- soft delete preserves tombstones
- hard delete is disabled by default and requires an explicit feature flag

## Automatic capture semantics

Automatic capture persists two artifacts:

- a `session_summaries` row for execution-level summary metadata
- an `episodic` `memory_entries` row when capture is allowed

Capture is skipped when:

- `features.memory_v1_enabled=false`
- the content is empty
- the same task run already produced a session summary
- dedupe finds an active equivalent memory
- dedupe matches a user tombstone or hidden memory

## Security policy

- redact secrets before persistence
- never persist raw secrets
- block prompt-injection patterns from curated/manual memory
- keep redaction and security outcome in explicit state columns

`redaction_state`:

- `clean`
- `redacted`
- `blocked`

`security_state`:

- `safe`
- `flagged`
- `blocked`

## Anti-resurrection policy

If a user hides or soft-deletes a memory, automatic capture must not recreate it blindly.

The suppression rule is:

1. compute normalized dedupe hash
2. check active duplicates
3. check user tombstones and hidden rows
4. if a tombstone matches, suppress creation and log the suppression

This guarantees that deleted user intent is stronger than autosave.

## Subagent policy

Subagents never share memory implicitly with the parent.

- child captures are attributed to the child lineage
- `parent_session_id` remains explicit
- promotion is the only way to elevate a child memory into stable memory
- parent/child linkage is recorded through metadata and relations, not shared session identity
