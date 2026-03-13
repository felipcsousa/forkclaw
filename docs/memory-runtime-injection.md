# Memory Runtime Injection V1

## Layer order

The backend runtime builds prompt context in this order:

1. Identity, soul, user context, and base policy.
2. Stable manual memory.
3. Stable autosaved memory.
4. Workspace or project stable memory.
5. Current conversation summary.
6. Top-K episodic recalled memories.
7. Current user input as the terminal `input_text`.

The current user input is not duplicated inside the system prompt. It stays as the final user message in the kernel request.

## Fixed budgets

Prompt context uses fixed character budgets per layer:

- `identity/soul/policy`: `3000`
- `stable_manual`: `2000`
- `stable_autosaved`: `1500`
- `workspace_project`: `1500`
- `conversation_summary`: `1200`
- `episodic`: `1500`
- `episodic_top_k`: `4`

Each layer accepts entries in order until it runs out of space. If the next entry does not fully fit, the runtime truncates that entry with `...` and records a `budget` exclusion diagnostic.

## Precedence and human intervention

For memories sharing the same natural key `(namespace, memory_key, memory_class, scope_kind, scope_ref)`, precedence is:

`manual > user_override > promoted > autosaved > session_summary`

Human interventions are absolute:

- `hidden` memories never enter the prompt.
- `deleted` memories never enter the prompt.
- `user_override` replaces the automatic base memory for the same natural key.

Prompt diagnostics record why each memory was included or excluded.

## Conversation identity

`conversation_id` is distinct from `sessions.id`.

- A new `conversation_id` is created when a main session is created.
- `POST /sessions/{session_id}/reset` rotates `conversation_id` on the same session.
- Existing messages are preserved in the database but default message reads only show the active conversation.
- Subagent sessions get their own `conversation_id`.

## Summaries and episodic memory

Before building prompt history, the runtime recalculates the current conversation summary from prior messages in the active conversation and stores it as:

- `namespace="conversation"`
- `memory_key="summary"`
- `memory_class="summary"`
- `source="session_summary"`

Assistant completions and terminal subagent outcomes write episodic autosaved memories under:

- `namespace="episode"`
- `memory_key="episode:<message_id|task_run_id>"`
- `memory_class="episodic"`
- `source="autosaved"`

Episodic recall uses lowercase token overlap against the current input, then breaks ties by recency. If there is no overlap, the runtime falls back to the most recent episodic memories.

## Subagent scope

Subagents inherit only minimal context:

- Agent identity and policy.
- Stable agent-level memory.
- Matching workspace or project stable memory.
- Explicit delegated context and the current parent conversation snapshot.

Subagents do not inherit the parent's full history, current conversation summary, or episodic recall automatically.

Memories written by subagents include:

- `session_id=<child session id>`
- `conversation_id=<child conversation id>`
- `parent_session_id=<parent session id>`

Automatic promotion to stable memory is disabled in V1. Manual promotion clones the source memory as `memory_class="stable"` with `source="promoted"`.

## Observability

The runtime writes these audit events:

- `prompt_context.resolved`
- `conversation.summary.updated`
- `session.conversation.reset`

`prompt_context.resolved` includes:

- layer usage and budgets
- included memory ids, keys, layers, and reasons
- excluded memory ids, keys, layers, and reasons such as `hidden`, `deleted`, `overridden`, and `budget`
