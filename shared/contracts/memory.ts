export type MemoryScope = 'operational' | 'stable' | 'episodic' | 'manual';

export type MemorySourceKind =
  | 'manual'
  | 'autosaved'
  | 'summary'
  | 'promoted_from_session'
  | 'promoted_from_subagent'
  | 'user_override';

export type MemoryLifecycleState = 'active' | 'superseded' | 'soft_deleted';

export type MemoryRecallReason =
  | 'runtime_context'
  | 'explicit_search'
  | 'session_summary'
  | 'promotion_review'
  | 'subagent_context'
  | 'manual_inspection';

export interface ConversationIdentity {
  session_key: string;
  conversation_id: string;
  session_id: string | null;
  run_id: string | null;
  parent_session_id: string | null;
}
