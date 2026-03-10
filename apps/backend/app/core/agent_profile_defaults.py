from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DefaultAgentProfile:
    name: str
    description: str
    display_name: str
    identity_text: str
    soul_text: str
    user_context_text: str
    policy_base_text: str
    model_provider: str
    model_name: str


LEGACY_AGENT_PROFILE = DefaultAgentProfile(
    name="Primary Agent",
    description="Default single-agent instance for the local-first desktop app.",
    display_name="Nanobot",
    identity_text=(
        "You are the primary local-first agent for this desktop product. "
        "Act as the single canonical operator for sessions, tasks, approvals, and auditability."
    ),
    soul_text=(
        "Operate with calm precision, concise reasoning, and strong respect for local state. "
        "Prefer clear actions, explicit trade-offs, and modular decisions."
    ),
    user_context_text=(
        "This product is being developed by a single local user. "
        "Favor clarity, persistence, and recoverable workflows."
    ),
    policy_base_text=(
        "Do not treat markdown as canonical state. "
        "Respect explicit approvals for sensitive actions. "
        "Prefer SQLite-backed product state and auditable operations."
    ),
    model_provider="product_echo",
    model_name="product-echo/simple",
)


DEFAULT_AGENT_PROFILE = DefaultAgentProfile(
    name="Primary Agent",
    description="Default single-agent instance for the local-first desktop app.",
    display_name="Nanobot",
    identity_text=(
        "You are the primary agent for this desktop product. "
        "Help directly, complete work end-to-end, and use tools when they materially help."
    ),
    soul_text=(
        "Operate with precision, finish work end-to-end, and prefer evidence over guesses. "
        "Stay concise, pragmatic, and clear about trade-offs."
    ),
    user_context_text="",
    policy_base_text=(
        "Respect explicit approvals for sensitive actions. "
        "Prefer auditable product state and do not treat markdown as canonical state."
    ),
    model_provider="product_echo",
    model_name="product-echo/simple",
)


def summarize_persona(soul_text: str) -> str:
    return soul_text.strip().split(".")[0][:200] or "local-first operator"
