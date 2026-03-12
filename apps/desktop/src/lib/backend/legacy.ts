import { resolveBackendConnectionInfo } from '../desktopRuntime';

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
}

export type SessionKind = 'main' | 'subagent';
export type SubagentLifecycleStatus =
  | 'queued'
  | 'running'
  | 'completed'
  | 'failed'
  | 'cancelled'
  | 'timed_out';

export interface SubagentCountsRecord {
  total: number;
  queued: number;
  running: number;
  completed: number;
  failed: number;
  cancelled: number;
  timed_out: number;
}

export interface SessionRecord {
  id: string;
  agent_id: string;
  kind: SessionKind;
  parent_session_id: string | null;
  root_session_id: string | null;
  spawn_depth: number;
  title: string;
  summary: string | null;
  status: string;
  delegated_goal: string | null;
  delegated_context_snapshot: string | null;
  tool_profile: string | null;
  model_override: string | null;
  max_iterations: number | null;
  started_at: string;
  last_message_at: string | null;
  created_at: string;
  updated_at: string;
  subagent_counts?: SubagentCountsRecord | null;
}

export interface SessionsListResponse {
  items: SessionRecord[];
}

export interface MessageRecord {
  id: string;
  session_id: string;
  role: string;
  status: string;
  sequence_number: number;
  content_text: string;
  created_at: string;
  updated_at: string;
}

export interface SessionMessagesResponse {
  session: SessionRecord;
  items: MessageRecord[];
  has_more?: boolean;
  next_before_sequence?: number | null;
}

export interface SubagentRunRecord {
  id: string;
  launcher_session_id: string;
  child_session_id: string;
  launcher_message_id: string | null;
  launcher_task_run_id: string | null;
  task_id: string | null;
  task_run_id: string | null;
  lifecycle_status: SubagentLifecycleStatus;
  started_at: string | null;
  finished_at: string | null;
  cancellation_requested_at: string | null;
  final_summary: string | null;
  final_output_json: string | null;
  estimated_cost_usd: number | null;
  error_code: string | null;
  error_summary: string | null;
  created_at: string;
  updated_at: string;
}

export interface SubagentTimelineEventRecord {
  id: string;
  event_type: string;
  created_at: string;
  status?: SubagentLifecycleStatus | null;
  summary: string;
  task_run_id?: string | null;
  estimated_cost_usd?: number | null;
}

export interface SubagentSessionRecord extends SessionRecord {
  run: SubagentRunRecord;
  timeline_events: SubagentTimelineEventRecord[];
}

export interface SessionSubagentsListResponse {
  parent_session_id: string;
  items: SubagentSessionRecord[];
}

export interface SubagentCancelResponse {
  parent_session_id: string;
  child_session_id: string;
  lifecycle_status: SubagentLifecycleStatus;
  cancellation_requested_at: string | null;
  finished_at: string | null;
}

export interface AgentExecutionResponse {
  task_id: string;
  task_run_id: string;
  session_id: string;
  user_message_id: string;
  assistant_message_id: string;
  status: string;
  output_text: string;
  kernel_name: string;
  model_name: string | null;
  tools_used: string[];
  finished_at: string | null;
}

export interface AgentExecutionAcceptedResponse {
  task_id: string;
  task_run_id: string;
  session_id: string;
  user_message_id: string;
  status: string;
  events_url: string;
}

export interface AgentProfileRecord {
  id: string;
  display_name: string;
  persona: string;
  system_prompt: string | null;
  identity_text: string;
  soul_text: string;
  user_context_text: string;
  policy_base_text: string;
  model_provider: string | null;
  model_name: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface AgentRecord {
  id: string;
  slug: string;
  name: string;
  description: string | null;
  status: string;
  is_default: boolean;
  created_at: string;
  updated_at: string;
  profile: AgentProfileRecord | null;
}

export interface AgentConfigUpdate {
  name: string;
  description: string;
  identity_text: string;
  soul_text: string;
  user_context_text: string;
  policy_base_text: string;
  model_name: string;
}

export type OperationalProvider =
  | 'product_echo'
  | 'openai'
  | 'anthropic'
  | 'openrouter'
  | 'deepseek'
  | 'gemini'
  | 'kimi-coding';

const OPERATIONAL_PROVIDER_LABELS: Record<OperationalProvider, string> = {
  product_echo: 'Product Echo (local fallback)',
  openai: 'OpenAI',
  anthropic: 'Anthropic',
  openrouter: 'OpenRouter',
  deepseek: 'DeepSeek',
  gemini: 'Gemini',
  'kimi-coding': 'Kimi for Coding',
};

const OPERATIONAL_PROVIDER_SUGGESTED_MODELS: Partial<Record<OperationalProvider, string>> = {
  product_echo: 'product-echo/simple',
  'kimi-coding': 'k2p5',
};

export function getOperationalProviderLabel(
  provider: OperationalProvider | string | null | undefined,
): string {
  if (!provider) {
    return 'product_echo';
  }
  return OPERATIONAL_PROVIDER_LABELS[provider as OperationalProvider] || provider;
}

export function getOperationalProviderSuggestedModel(
  provider: OperationalProvider,
): string | null {
  return OPERATIONAL_PROVIDER_SUGGESTED_MODELS[provider] || null;
}

export type OperationalDefaultView =
  | 'chat'
  | 'profile'
  | 'settings'
  | 'tools'
  | 'approvals'
  | 'jobs'
  | 'activity';

export interface OperationalSettingsRecord {
  provider: OperationalProvider;
  model_name: string;
  workspace_root: string;
  max_iterations_per_execution: number;
  daily_budget_usd: number;
  monthly_budget_usd: number;
  default_view: OperationalDefaultView;
  activity_poll_seconds: number;
  heartbeat_interval_seconds: number;
  provider_api_key_configured: boolean;
}

export interface OperationalSettingsUpdate {
  provider: OperationalProvider;
  model_name: string;
  workspace_root: string;
  max_iterations_per_execution: number;
  daily_budget_usd: number;
  monthly_budget_usd: number;
  default_view: OperationalDefaultView;
  activity_poll_seconds: number;
  heartbeat_interval_seconds: number;
  api_key?: string | null;
  clear_api_key: boolean;
}

export type ToolPermissionLevel = 'deny' | 'ask' | 'allow';
export type ToolGroup =
  | 'group:fs'
  | 'group:runtime'
  | 'group:web'
  | 'group:sessions'
  | 'group:memory'
  | 'group:automation';
export type ToolRisk = 'low' | 'medium' | 'high';
export type ToolStatus = 'enabled' | 'experimental' | 'disabled';
export type ToolPolicyProfileId = 'minimal' | 'coding' | 'research' | 'full';

export interface ToolPermissionRecord {
  id: string;
  agent_id: string;
  tool_name: string;
  workspace_path: string | null;
  permission_level: ToolPermissionLevel;
  approval_required: boolean;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface ToolPermissionsResponse {
  workspace_root: string;
  items: ToolPermissionRecord[];
}

export interface ToolCatalogEntryRecord {
  id: string;
  label: string;
  description: string;
  group: ToolGroup;
  group_label: string;
  risk: ToolRisk;
  status: ToolStatus;
  input_schema: Record<string, unknown>;
  output_schema: Record<string, unknown> | null;
  requires_workspace: boolean;
}

export interface ToolCatalogResponse {
  items: ToolCatalogEntryRecord[];
}

export interface ToolPolicyProfileRecord {
  id: ToolPolicyProfileId;
  label: string;
  description: string;
  defaults: Partial<Record<ToolGroup, ToolPermissionLevel>>;
}

export interface ToolPolicyOverrideRecord {
  id: string;
  agent_id: string;
  tool_name: string;
  permission_level: ToolPermissionLevel;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface ToolPolicyRecord {
  profile_id: ToolPolicyProfileId;
  profiles: ToolPolicyProfileRecord[];
  overrides: ToolPolicyOverrideRecord[];
}

export interface ToolCallRecord {
  id: string;
  session_id: string | null;
  message_id: string | null;
  task_run_id: string | null;
  tool_name: string;
  status: string;
  input_json: string | null;
  output_json: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
  guided_by_skills: SkillSummaryRecord[];
}

export interface ToolCallsResponse {
  items: ToolCallRecord[];
}

export interface ApprovalRecord {
  id: string;
  agent_id: string;
  task_id: string | null;
  tool_call_id: string | null;
  kind: string;
  requested_action: string;
  reason: string | null;
  status: string;
  decided_at: string | null;
  expires_at: string | null;
  created_at: string;
  updated_at: string;
  tool_name: string | null;
  tool_input_json: string | null;
  session_id: string | null;
  session_title: string | null;
  task_run_id: string | null;
}

export interface ApprovalsResponse {
  items: ApprovalRecord[];
}

export interface ApprovalActionResponse {
  approval: ApprovalRecord;
  task_run_status: string;
  tool_call_status: string;
  output_text: string;
  assistant_message_id: string | null;
}

export interface ActivityAuditEventRecord {
  id: string;
  level: string;
  event_type: string;
  entity_type: string;
  entity_id: string | null;
  summary_text: string | null;
  payload_json: string | null;
  created_at: string;
}

export type ActivityTimelineEntryType =
  | 'message'
  | 'task'
  | 'tool_call'
  | 'approval'
  | 'status'
  | 'audit';

export interface ActivityTimelineEntryRecord {
  id: string;
  type: ActivityTimelineEntryType;
  created_at: string;
  status: string | null;
  title: string;
  summary: string;
  error_message: string | null;
  duration_ms: number | null;
  estimated_cost_usd: number | null;
  metadata: Record<string, unknown> | null;
}

export interface ActivityTimelineLineageRecord {
  parent_session_id: string;
  parent_session_title: string | null;
  child_session_id: string;
  child_session_title: string | null;
  goal_summary: string;
  status: string;
  task_run_id: string | null;
  estimated_cost_usd: number | null;
}

export interface ActivityTimelineItemRecord {
  task_run_id: string;
  task_id: string;
  task_kind: string;
  task_title: string;
  session_id: string | null;
  session_title: string | null;
  started_at: string | null;
  finished_at: string | null;
  status: string;
  error_message: string | null;
  duration_ms: number | null;
  estimated_cost_usd: number | null;
  skill_strategy: string | null;
  resolved_skills: SkillSummaryRecord[];
  lineage?: ActivityTimelineLineageRecord | null;
  entries: ActivityTimelineEntryRecord[];
  audit_log: ActivityAuditEventRecord[];
}

export interface ActivityTimelineResponse {
  items: ActivityTimelineItemRecord[];
  next_cursor?: string | null;
}

export type SkillOrigin = 'bundled' | 'user-local' | 'workspace';

export interface SkillRecord {
  key: string;
  name: string;
  description: string;
  origin: SkillOrigin;
  enabled: boolean;
  eligible: boolean;
  selected: boolean;
  blocked_reasons: string[];
  config: Record<string, unknown> | null;
  configured_env_keys: string[];
  primary_env: string | null;
}

export interface SkillsResponse {
  strategy: string;
  items: SkillRecord[];
}

export interface SkillSummaryRecord {
  key: string;
  name: string;
  origin: SkillOrigin;
  source_path: string;
  selected: boolean;
  eligible: boolean;
  blocked_reasons: string[];
}

export interface SkillUpdateInput {
  enabled?: boolean;
  config?: Record<string, unknown> | null;
  env?: Record<string, string> | null;
  clear_env?: string[];
  api_key?: string | null;
  clear_api_key?: boolean;
}

export type CronJobType =
  | 'review_pending_approvals'
  | 'summarize_recent_activity'
  | 'cleanup_stale_runs';

export interface CronJobPayloadRecord {
  job_type: CronJobType;
  message: string | null;
  stale_after_seconds: number | null;
}

export interface CronJobRecord {
  id: string;
  agent_id: string;
  name: string;
  schedule: string;
  timezone: string;
  status: string;
  task_payload_json: string | null;
  last_run_at: string | null;
  next_run_at: string | null;
  created_at: string;
  updated_at: string;
  payload: CronJobPayloadRecord;
}

export interface TaskRunHistoryRecord {
  task_run_id: string;
  task_id: string;
  cron_job_id: string | null;
  task_title: string;
  task_kind: string;
  task_status: string;
  job_name: string | null;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  error_message: string | null;
  output_summary: string | null;
  created_at: string;
}

export interface HeartbeatStatusRecord {
  last_run_at: string | null;
  task_run_id: string | null;
  cleaned_stale_runs: number;
  pending_approvals: number;
  recent_task_runs: number;
  summary_text: string;
}

export interface CronJobsDashboardResponse {
  items: CronJobRecord[];
  history: TaskRunHistoryRecord[];
  heartbeat: HeartbeatStatusRecord;
}

export interface CronJobCreateInput {
  name: string;
  schedule: string;
  timezone?: string | null;
  payload: CronJobPayloadRecord;
}

interface BackendErrorBody {
  detail?: unknown;
  request_id?: unknown;
}

function detailToMessage(detail: unknown): string | null {
  if (typeof detail === 'string' && detail.trim()) {
    return detail.trim();
  }

  if (Array.isArray(detail) && detail.length > 0) {
    return detail
      .map((item) => {
        if (
          item &&
          typeof item === 'object' &&
          'msg' in item &&
          typeof item.msg === 'string'
        ) {
          return item.msg;
        }
        return JSON.stringify(item);
      })
      .join('; ');
  }

  return null;
}

async function parseErrorResponse(response: Response): Promise<string> {
  const requestId = response.headers.get('X-Request-ID');
  const fallback = `Backend responded with ${response.status}`;
  const contentType = response.headers.get('content-type') || '';

  if (contentType.includes('application/json')) {
    const payload = (await response.json()) as BackendErrorBody;
    const detail = detailToMessage(payload.detail);
    const responseRequestId =
      typeof payload.request_id === 'string' ? payload.request_id : requestId;
    return `${detail || fallback}${
      responseRequestId ? ` (request ${responseRequestId})` : ''
    }`;
  }

  const text = (await response.text()).trim();
  return `${text || fallback}${requestId ? ` (request ${requestId})` : ''}`;
}

export async function requestJson<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  let response: Response;
  const connection = await resolveBackendConnectionInfo();
  const headers = new Headers(init?.headers);
  headers.set('Content-Type', 'application/json');
  if (connection.bootstrapToken) {
    headers.set('X-Backend-Bootstrap-Token', connection.bootstrapToken);
  }

  try {
    response = await fetch(`${connection.baseUrl}${path}`, {
      ...init,
      headers,
    });
  } catch (error: unknown) {
    const message =
      error instanceof Error ? error.message : 'Unknown network failure.';
    throw new Error(
      `Could not reach the local backend at ${connection.baseUrl}. ${message}`,
    );
  }

  if (!response.ok) {
    throw new Error(await parseErrorResponse(response));
  }

  if (response.status === 204) {
    return null as T;
  }

  return (await response.json()) as T;
}

export function getJson<T>(path: string): Promise<T> {
  return requestJson<T>(path, { method: 'GET' });
}

export function sendJson<T>(
  method: 'POST' | 'PUT',
  path: string,
  body?: unknown,
): Promise<T> {
  return requestJson<T>(path, {
    method,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

export async function requestVoid(path: string, init?: RequestInit): Promise<void> {
  await requestJson<null>(path, init);
}

export function fetchHealth(): Promise<HealthResponse> {
  return getJson<HealthResponse>('/health');
}

export function fetchAgentConfig(): Promise<AgentRecord> {
  return getJson<AgentRecord>('/agent/config');
}

export function updateAgentConfig(
  payload: AgentConfigUpdate,
): Promise<AgentRecord> {
  return sendJson<AgentRecord>('PUT', '/agent/config', payload);
}

export function resetAgentConfig(): Promise<AgentRecord> {
  return sendJson<AgentRecord>('POST', '/agent/config/reset');
}

export function fetchSessions(
  includeSubagentCounts = false,
): Promise<SessionsListResponse> {
  const search = includeSubagentCounts ? '?include_subagent_counts=true' : '';
  return getJson<SessionsListResponse>(`/sessions${search}`);
}

export function fetchOperationalSettings(): Promise<OperationalSettingsRecord> {
  return getJson<OperationalSettingsRecord>('/settings/operational');
}

export function updateOperationalSettings(
  payload: OperationalSettingsUpdate,
): Promise<OperationalSettingsRecord> {
  return sendJson<OperationalSettingsRecord>('PUT', '/settings/operational', payload);
}

export function fetchToolCatalog(): Promise<ToolCatalogResponse> {
  return getJson<ToolCatalogResponse>('/tools/catalog');
}

export function fetchToolPolicy(): Promise<ToolPolicyRecord> {
  return getJson<ToolPolicyRecord>('/tools/policy');
}

export function updateToolPolicy(
  profileId: ToolPolicyProfileId,
): Promise<ToolPolicyRecord> {
  return sendJson<ToolPolicyRecord>('PUT', '/tools/policy', {
    profile_id: profileId,
  });
}

export function fetchToolPermissions(): Promise<ToolPermissionsResponse> {
  return getJson<ToolPermissionsResponse>('/tools/permissions');
}

export function updateToolPermission(
  toolName: string,
  permissionLevel: ToolPermissionLevel,
): Promise<ToolPermissionRecord> {
  return sendJson<ToolPermissionRecord>(
    'PUT',
    `/tools/permissions/${toolName}`,
    { permission_level: permissionLevel },
  );
}

export function fetchToolCalls(): Promise<ToolCallsResponse> {
  return getJson<ToolCallsResponse>('/tools/calls');
}

export function fetchSkills(): Promise<SkillsResponse> {
  return getJson<SkillsResponse>('/skills');
}

export function updateSkill(
  skillKey: string,
  payload: SkillUpdateInput,
): Promise<SkillRecord> {
  return sendJson<SkillRecord>('PUT', `/skills/${skillKey}`, payload);
}

export function fetchApprovals(): Promise<ApprovalsResponse> {
  return getJson<ApprovalsResponse>('/approvals');
}

export function fetchActivityTimeline(params?: {
  limit?: number;
  cursor?: string;
}): Promise<ActivityTimelineResponse> {
  const search = new URLSearchParams();
  if (params?.limit !== undefined) {
    search.set('limit', String(params.limit));
  }
  if (params?.cursor) {
    search.set('cursor', params.cursor);
  }
  const suffix = search.size > 0 ? `?${search.toString()}` : '';
  return getJson<ActivityTimelineResponse>(`/activity/timeline${suffix}`);
}

export function fetchCronJobsDashboard(): Promise<CronJobsDashboardResponse> {
  return getJson<CronJobsDashboardResponse>('/cron-jobs');
}

export function createCronJob(
  payload: CronJobCreateInput,
): Promise<CronJobRecord> {
  return sendJson<CronJobRecord>('POST', '/cron-jobs', payload);
}

export function pauseCronJob(jobId: string): Promise<CronJobRecord> {
  return sendJson<CronJobRecord>('POST', `/cron-jobs/${jobId}/pause`);
}

export function activateCronJob(jobId: string): Promise<CronJobRecord> {
  return sendJson<CronJobRecord>('POST', `/cron-jobs/${jobId}/activate`);
}

export async function deleteCronJob(jobId: string): Promise<void> {
  await requestVoid(`/cron-jobs/${jobId}`, { method: 'DELETE' });
}

export function approveApproval(
  approvalId: string,
): Promise<ApprovalActionResponse> {
  return sendJson<ApprovalActionResponse>('POST', `/approvals/${approvalId}/approve`);
}

export function denyApproval(
  approvalId: string,
): Promise<ApprovalActionResponse> {
  return sendJson<ApprovalActionResponse>('POST', `/approvals/${approvalId}/deny`);
}

export function createSession(title?: string): Promise<SessionRecord> {
  return sendJson<SessionRecord>('POST', '/sessions', { title: title || null });
}

export function fetchSessionMessages(
  sessionId: string,
  params?: {
    limit?: number;
    beforeSequence?: number;
  },
): Promise<SessionMessagesResponse> {
  const search = new URLSearchParams();
  if (params?.limit !== undefined) {
    search.set('limit', String(params.limit));
  }
  if (params?.beforeSequence !== undefined) {
    search.set('before_sequence', String(params.beforeSequence));
  }
  const suffix = search.size > 0 ? `?${search.toString()}` : '';
  return getJson<SessionMessagesResponse>(`/sessions/${sessionId}/messages${suffix}`);
}

export function fetchSessionSubagents(
  sessionId: string,
): Promise<SessionSubagentsListResponse> {
  return getJson<SessionSubagentsListResponse>(`/sessions/${sessionId}/subagents`);
}

export function fetchSessionSubagent(
  sessionId: string,
  childSessionId: string,
): Promise<SubagentSessionRecord> {
  return getJson<SubagentSessionRecord>(
    `/sessions/${sessionId}/subagents/${childSessionId}`,
  );
}

export function fetchSessionSubagentMessages(
  sessionId: string,
  childSessionId: string,
  params?: {
    limit?: number;
    beforeSequence?: number;
  },
): Promise<SessionMessagesResponse> {
  const search = new URLSearchParams();
  if (params?.limit !== undefined) {
    search.set('limit', String(params.limit));
  }
  if (params?.beforeSequence !== undefined) {
    search.set('before_sequence', String(params.beforeSequence));
  }
  const suffix = search.size > 0 ? `?${search.toString()}` : '';
  return getJson<SessionMessagesResponse>(
    `/sessions/${sessionId}/subagents/${childSessionId}/messages${suffix}`,
  );
}

export function cancelSessionSubagent(
  sessionId: string,
  childSessionId: string,
): Promise<SubagentCancelResponse> {
  return sendJson<SubagentCancelResponse>(
    'POST',
    `/sessions/${sessionId}/subagents/${childSessionId}/cancel`,
  );
}

export function sendSessionMessage(
  sessionId: string,
  content: string,
): Promise<AgentExecutionResponse> {
  return sendJson<AgentExecutionResponse>('POST', `/sessions/${sessionId}/messages`, {
    content,
  });
}

export function sendSessionMessageAsync(
  sessionId: string,
  content: string,
): Promise<AgentExecutionAcceptedResponse> {
  return sendJson<AgentExecutionAcceptedResponse>(
    'POST',
    `/sessions/${sessionId}/messages/async`,
    {
      content,
    },
  );
}
