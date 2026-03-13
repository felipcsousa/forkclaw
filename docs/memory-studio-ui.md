# Memory Studio UI

## Overview

Memory Studio is the desktop surface for inspecting and controlling Nanobot memory without turning chat into a technical console.

The feature is split into two layers:

- `Memory Studio`: dedicated workspace for browsing, filtering, editing, deleting, and understanding memory records.
- `Chat recall disclosure`: a lightweight per-response indicator that shows which memories were used and why.

## Information Architecture

Memory Studio is a first-class app view in the desktop shell under the `Operate` section.

The view exposes five top-level tabs:

- `All Memories`
- `Stable Memory`
- `Episodic Memory`
- `Session Summaries`
- `Recall Log`

The first four tabs operate on the same `MemoryItem` domain and differ only by filter preset:

- `Stable Memory`: durable user or system knowledge intended for repeated recall.
- `Episodic Memory`: event-like memory derived from work performed in sessions.
- `Session Summaries`: condensed summaries associated with a session lifecycle.
- `All Memories`: combined view across all memory kinds.

`Recall Log` is read-only and shows recall events rather than editable memory records.

## Main List

Memory tabs share one table with these columns:

- `title`
- `source`
- `scope`
- `updated_at`
- `recall status`
- `importance`

Selecting a row opens a detail surface that shows:

- full content
- origin metadata
- change history
- session reference when available
- subagent reference when available

## Search And Filters

The list supports:

- free-text search across title and content
- `scope` filter
- `source kind` filter
- state filter: `active`, `hidden`, `deleted`
- mode filter: `manual`, `automatic`, `all`

Filter combinations are intended to answer practical questions quickly, such as:

- "show only manual stable memories"
- "show hidden episodic memories"
- "find deleted summaries from a session"

## Actions

Supported memory actions:

- `Create`
- `Edit`
- `Soft delete`
- `Hard delete`
- `Hide from recall`
- `Restore`
- `Promote`
- `Demote`
- `View history`

Behavior rules:

- `Create` always creates a manual memory record.
- `Edit` uses a robust form dialog rather than fragile inline editing.
- Editing an auto-saved memory creates a manual override revision instead of mutating the original record in place.
- `Soft delete` is reversible and does not ask for confirmation.
- `Hard delete` requires confirmation.
- `Hide from recall` removes the memory from recall without deleting it.
- `Restore` reactivates a hidden or soft-deleted memory.
- `Promote` raises importance.
- `Demote` lowers importance.
- `View history` exposes the audit trail and prior snapshots in the detail surface.

## Badges

The UI uses plain, explicit badges so memory state is understandable at a glance.

- `Manual`: created directly by the user.
- `Auto-saved`: generated automatically by the system.
- `Override`: manual revision layered on top of an automatic memory.
- `Hidden`: excluded from recall but still stored.
- `Deleted`: soft-deleted and recoverable until hard deletion.

These badges are meant to answer two questions immediately:

- where the memory came from
- whether the agent can still use it

## Empty States

The feature distinguishes between different empty outcomes instead of showing a generic blank table.

- `No memories`: there are no memory records for the selected tab.
- `No manual memories`: the current view contains memory, but none created manually.
- `No results`: filters or search terms produced no matches.

Each state should explain what the user can do next, usually by clearing filters or creating a memory.

## Detail And History

The desktop detail experience uses a right-side sheet. On smaller layouts it falls back to a drawer/dialog pattern.

The detail surface includes:

- memory title and status
- complete content
- source label and source kind
- scope and importance
- session identifier when available
- subagent/session origin when available
- change history with prior snapshots and action summaries

## Chat Recall Disclosure

Chat remains intentionally light.

Assistant responses only show a subtle `memories used` indicator when recall metadata exists for that response. When absent, chat rendering is unchanged.

Opening the recall drawer shows:

- memories injected into the response
- recall reason
- origin/source
- a link/action to open the memory in Memory Studio when the record still exists

This gives users visibility into recall behavior without turning every chat message into a diagnostic panel.

## Product Intent

Memory Studio V1 is designed to make memory legible and controllable:

- users can inspect what exists
- users can correct or override what the system saved
- users can hide or restore memory without destructive workflows
- users can understand when memory influenced a response

The goal is a memory system that feels operable rather than opaque.
