# Subagents Hardening V1

## Scope

This pass hardens the existing subagent MVP for reliability. It does not add new orchestration features.

## Failure Modes Covered

- Concurrent spawn attempts can no longer exceed `3` active children per parent session.
- Two workers racing on the same queued child can no longer claim the same run.
- A child can now carry its own normalized `timeout_seconds`, clamped by backend policy.
- Running children that exceed their timeout window are cleaned up as `timed_out`.
- Running children with a pending cancellation request are cleaned up as `cancelled`.
- Cooperative cancellation is checked before provider calls, before each tool call, before provider follow-up, and before persisting the final child message.
- Terminalization is idempotent: the parent summary message is stored once and linked through `parent_summary_message_id`.
- SQLite `busy/locked` failures during spawn, claim, and cleanup are retried with a short bounded backoff.

## Deliberate V2 Deferrals

- Provider or tool preemption while work is already in flight.
- Distributed spawn deduplication or idempotency keys.
- Semantic retries based on provider-specific failure classes.
- Explicit leasing or heartbeat-based ownership for worker claims.
- Nested subagents, `sessions_send`, durable named children, thread binding, multichannel routing, realtime transport, and richer orchestration topologies.
