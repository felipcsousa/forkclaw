import { requestJson, sendJson } from './client';

export type MemoryKind = 'stable' | 'episodic' | 'session_summary';
export type MemoryImportance = 'low' | 'medium' | 'high';
export type MemoryState = 'active' | 'deleted';
export type MemoryRecallStatus = 'active' | 'hidden';
export type MemoryStateFilter = 'active' | 'hidden' | 'deleted';
export type MemoryMode = 'all' | 'manual' | 'automatic';

export interface MemoryItemRecord {
  id: string;
  kind: MemoryKind;
  title: string;
  content: string;
  scope: string;
  source_kind: string;
  source_label: string;
  importance: MemoryImportance;
  state: MemoryState;
  recall_status: MemoryRecallStatus;
  is_manual: boolean;
  is_override: boolean;
  origin_session_id: string | null;
  origin_subagent_session_id: string | null;
  original_memory_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface MemoryItemsResponse {
  items: MemoryItemRecord[];
}

export interface MemoryHistoryEntryRecord {
  id: string;
  memory_id: string;
  action: string;
  summary: string | null;
  snapshot: Record<string, unknown> | null;
  created_at: string;
}

export interface MemoryHistoryResponse {
  items: MemoryHistoryEntryRecord[];
}

export interface MemoryRecallItemRecord {
  memory_id: string;
  title: string;
  kind: MemoryKind;
  scope: string;
  source_kind: string;
  source_label: string;
  importance: MemoryImportance;
  reason: string;
  origin_session_id: string | null;
  origin_subagent_session_id: string | null;
}

export interface MemoryRecallDetailRecord {
  assistant_message_id: string;
  session_id: string;
  created_at: string;
  reason_summary: string | null;
  items: MemoryRecallItemRecord[];
}

export interface MemoryRecallLogEntryRecord extends MemoryRecallDetailRecord {
  id: string;
  task_run_id: string | null;
}

export interface MemoryRecallLogResponse {
  items: MemoryRecallLogEntryRecord[];
}

export interface SessionRecallSummaryRecord {
  assistant_message_id: string;
  created_at: string;
  recalled_count: number;
  reason_summary: string | null;
  items: MemoryRecallItemRecord[];
}

export interface SessionRecallSummariesResponse {
  items: SessionRecallSummaryRecord[];
}

export interface MemoryItemCreateInput {
  kind: MemoryKind;
  title: string;
  content: string;
  scope: string;
  importance: MemoryImportance;
}

export interface MemoryItemUpdateInput {
  title?: string;
  content?: string;
  scope?: string;
  importance?: MemoryImportance;
}

export interface MemoryItemsQuery {
  kind?: MemoryKind;
  query?: string;
  scope?: string;
  sourceKind?: string;
  state?: MemoryStateFilter;
  recallStatus?: MemoryRecallStatus;
  mode?: MemoryMode;
}

function queryString(filters: MemoryItemsQuery = {}) {
  const params = new URLSearchParams();
  if (filters.kind) {
    params.set('kind', filters.kind);
  }
  if (filters.query) {
    params.set('query', filters.query);
  }
  if (filters.scope) {
    params.set('scope', filters.scope);
  }
  if (filters.sourceKind) {
    params.set('source_kind', filters.sourceKind);
  }
  if (filters.state) {
    params.set('state', filters.state);
  }
  if (filters.mode) {
    params.set('mode', filters.mode);
  }
  if (filters.recallStatus) {
    params.set('recall_status', filters.recallStatus);
  }
  const serialized = params.toString();
  return serialized ? `?${serialized}` : '';
}

export function fetchMemoryItems(
  filters: MemoryItemsQuery = {},
): Promise<MemoryItemsResponse> {
  return requestJson<MemoryItemsResponse>(`/memory/items${queryString(filters)}`, {
    method: 'GET',
  });
}

export function fetchMemoryItem(memoryId: string): Promise<MemoryItemRecord> {
  return requestJson<MemoryItemRecord>(`/memory/items/${memoryId}`, {
    method: 'GET',
  });
}

export function fetchMemoryItemHistory(
  memoryId: string,
): Promise<MemoryHistoryResponse> {
  return requestJson<MemoryHistoryResponse>(`/memory/items/${memoryId}/history`, {
    method: 'GET',
  });
}

export function createMemoryItem(
  payload: MemoryItemCreateInput,
): Promise<MemoryItemRecord> {
  return sendJson<MemoryItemRecord>('POST', '/memory/items', payload);
}

export function updateMemoryItem(
  memoryId: string,
  payload: MemoryItemUpdateInput,
): Promise<MemoryItemRecord> {
  return sendJson<MemoryItemRecord>('PUT', `/memory/items/${memoryId}`, payload);
}

export function hideMemoryItem(memoryId: string): Promise<MemoryItemRecord> {
  return sendJson<MemoryItemRecord>('POST', `/memory/items/${memoryId}/hide`);
}

export function restoreMemoryItem(memoryId: string): Promise<MemoryItemRecord> {
  return sendJson<MemoryItemRecord>('POST', `/memory/items/${memoryId}/restore`);
}

export function promoteMemoryItem(memoryId: string): Promise<MemoryItemRecord> {
  return sendJson<MemoryItemRecord>('POST', `/memory/items/${memoryId}/promote`);
}

export function demoteMemoryItem(memoryId: string): Promise<MemoryItemRecord> {
  return sendJson<MemoryItemRecord>('POST', `/memory/items/${memoryId}/demote`);
}

export function deleteMemoryItem(
  memoryId: string,
  hard = false,
): Promise<MemoryItemRecord | null> {
  return requestJson<MemoryItemRecord | null>(
    `/memory/items/${memoryId}${hard ? '?hard=true' : ''}`,
    {
      method: 'DELETE',
    },
  );
}

export function fetchMemoryRecallLog(): Promise<MemoryRecallLogResponse> {
  return requestJson<MemoryRecallLogResponse>('/memory/recall', {
    method: 'GET',
  });
}

export function fetchMemoryRecallDetail(
  messageId: string,
): Promise<MemoryRecallDetailRecord> {
  return requestJson<MemoryRecallDetailRecord>(
    `/memory/recall/messages/${messageId}`,
    { method: 'GET' },
  );
}

export function fetchSessionRecallSummaries(
  sessionId: string,
): Promise<SessionRecallSummariesResponse> {
  return requestJson<SessionRecallSummariesResponse>(
    `/memory/recall/sessions/${sessionId}`,
    { method: 'GET' },
  );
}
