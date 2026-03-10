export interface HealthResponse {
  status: string;
  service: string;
  version: string;
}

export interface SessionRecord {
  id: string;
  agent_id: string;
  title: string;
  summary: string | null;
  status: string;
  started_at: string;
  last_message_at: string | null;
  created_at: string;
  updated_at: string;
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
  | 'gemini';

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
  api_key?: string | null;
  clear_api_key: boolean;
}

export type ToolPermissionLevel = 'deny' | 'ask' | 'allow';

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
  entries: ActivityTimelineEntryRecord[];
  audit_log: ActivityAuditEventRecord[];
}

export interface ActivityTimelineResponse {
  items: ActivityTimelineItemRecord[];
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

const backendUrl =
  import.meta.env.VITE_BACKEND_URL?.trim() || 'http://127.0.0.1:8000';

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

async function requestJson<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${backendUrl}${path}`, {
      headers: {
        'Content-Type': 'application/json',
        ...(init?.headers || {}),
      },
      ...init,
    });
  } catch (error: unknown) {
    const message =
      error instanceof Error ? error.message : 'Unknown network failure.';
    throw new Error(`Could not reach the local backend at ${backendUrl}. ${message}`);
  }

  if (!response.ok) {
    throw new Error(await parseErrorResponse(response));
  }

  return (await response.json()) as T;
}

export function fetchHealth(): Promise<HealthResponse> {
  return requestJson<HealthResponse>('/health', { method: 'GET' });
}

export function fetchAgentConfig(): Promise<AgentRecord> {
  return requestJson<AgentRecord>('/agent/config', { method: 'GET' });
}

export function updateAgentConfig(
  payload: AgentConfigUpdate,
): Promise<AgentRecord> {
  return requestJson<AgentRecord>('/agent/config', {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export function resetAgentConfig(): Promise<AgentRecord> {
  return requestJson<AgentRecord>('/agent/config/reset', {
    method: 'POST',
  });
}

export function fetchSessions(): Promise<SessionsListResponse> {
  return requestJson<SessionsListResponse>('/sessions', { method: 'GET' });
}

export function fetchOperationalSettings(): Promise<OperationalSettingsRecord> {
  return requestJson<OperationalSettingsRecord>('/settings/operational', {
    method: 'GET',
  });
}

export function updateOperationalSettings(
  payload: OperationalSettingsUpdate,
): Promise<OperationalSettingsRecord> {
  return requestJson<OperationalSettingsRecord>('/settings/operational', {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export function fetchToolPermissions(): Promise<ToolPermissionsResponse> {
  return requestJson<ToolPermissionsResponse>('/tools/permissions', {
    method: 'GET',
  });
}

export function updateToolPermission(
  toolName: string,
  permissionLevel: ToolPermissionLevel,
): Promise<ToolPermissionRecord> {
  return requestJson<ToolPermissionRecord>(`/tools/permissions/${toolName}`, {
    method: 'PUT',
    body: JSON.stringify({ permission_level: permissionLevel }),
  });
}

export function fetchToolCalls(): Promise<ToolCallsResponse> {
  return requestJson<ToolCallsResponse>('/tools/calls', {
    method: 'GET',
  });
}

export function fetchApprovals(): Promise<ApprovalsResponse> {
  return requestJson<ApprovalsResponse>('/approvals', {
    method: 'GET',
  });
}

export function fetchActivityTimeline(): Promise<ActivityTimelineResponse> {
  return requestJson<ActivityTimelineResponse>('/activity/timeline', {
    method: 'GET',
  });
}

export function fetchCronJobsDashboard(): Promise<CronJobsDashboardResponse> {
  return requestJson<CronJobsDashboardResponse>('/cron-jobs', {
    method: 'GET',
  });
}

export function createCronJob(
  payload: CronJobCreateInput,
): Promise<CronJobRecord> {
  return requestJson<CronJobRecord>('/cron-jobs', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function pauseCronJob(jobId: string): Promise<CronJobRecord> {
  return requestJson<CronJobRecord>(`/cron-jobs/${jobId}/pause`, {
    method: 'POST',
  });
}

export function activateCronJob(jobId: string): Promise<CronJobRecord> {
  return requestJson<CronJobRecord>(`/cron-jobs/${jobId}/activate`, {
    method: 'POST',
  });
}

export async function deleteCronJob(jobId: string): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${backendUrl}/cron-jobs/${jobId}`, {
      headers: {
        'Content-Type': 'application/json',
      },
      method: 'DELETE',
    });
  } catch (error: unknown) {
    const message =
      error instanceof Error ? error.message : 'Unknown network failure.';
    throw new Error(`Could not reach the local backend at ${backendUrl}. ${message}`);
  }

  if (!response.ok) {
    throw new Error(await parseErrorResponse(response));
  }
}

export function approveApproval(
  approvalId: string,
): Promise<ApprovalActionResponse> {
  return requestJson<ApprovalActionResponse>(`/approvals/${approvalId}/approve`, {
    method: 'POST',
  });
}

export function denyApproval(
  approvalId: string,
): Promise<ApprovalActionResponse> {
  return requestJson<ApprovalActionResponse>(`/approvals/${approvalId}/deny`, {
    method: 'POST',
  });
}

export function createSession(title?: string): Promise<SessionRecord> {
  return requestJson<SessionRecord>('/sessions', {
    method: 'POST',
    body: JSON.stringify({ title: title || null }),
  });
}

export function fetchSessionMessages(
  sessionId: string,
): Promise<SessionMessagesResponse> {
  return requestJson<SessionMessagesResponse>(`/sessions/${sessionId}/messages`, {
    method: 'GET',
  });
}

export function sendSessionMessage(
  sessionId: string,
  content: string,
): Promise<AgentExecutionResponse> {
  return requestJson<AgentExecutionResponse>(`/sessions/${sessionId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ content }),
  });
}
