import type {
  AgentExecutionAcceptedResponse,
  AgentExecutionResponse,
  MessageRecord,
  SubagentSessionRecord,
} from '../../lib/backend';
import type {
  SessionExecutionEvent,
  SessionExecutionEventApprovalData,
  SessionExecutionEventRunData,
  SessionExecutionEventSubagentData,
  SessionExecutionEventToolData,
} from '../../lib/backend/sessionExecutionStream';

export type ChatExecutionRunStatus =
  | 'connecting'
  | 'running'
  | 'awaiting_approval'
  | 'failed'
  | 'completed'
  | 'disconnected';

export interface ChatExecutionStep {
  id: string;
  eventId: string;
  kind: 'tool' | 'approval' | 'subagent' | 'status';
  eventType: string;
  title: string;
  status: string;
  createdAt: string;
  startedAt: string | null;
  finishedAt: string | null;
  durationMs: number | null;
  summary: string;
  details: string | null;
}

export interface ChatExecutionRun {
  id: string;
  taskRunId: string | null;
  sessionId: string;
  prompt: string | null;
  userMessageId: string | null;
  assistantMessageId: string | null;
  createdAt: string;
  startedAt: string | null;
  finishedAt: string | null;
  status: ChatExecutionRunStatus;
  finalText: string | null;
  errorMessage: string | null;
  steps: ChatExecutionStep[];
}

export interface ChatExecutionState {
  runsById: Record<string, ChatExecutionRun>;
  sessionRunIds: Record<string, string[]>;
  runIdByTaskRunId: Record<string, string>;
}

type RunResponse = Partial<AgentExecutionAcceptedResponse & AgentExecutionResponse>;

export type ChatExecutionAction =
  | {
      type: 'run/optimistic-created';
      sessionId: string;
      localRunId: string;
      prompt: string;
      createdAt: string;
    }
  | {
      type: 'run/response-bound';
      sessionId: string;
      localRunId: string;
      response: RunResponse;
    }
  | {
      type: 'run/optimistic-discarded';
      sessionId: string;
      localRunId: string;
    }
  | {
      type: 'run/event-received';
      sessionId: string;
      event: SessionExecutionEvent;
    };

export interface ChatTimelineMessageItem {
  kind: 'message';
  message: MessageRecord;
}

export interface ChatTimelineRunItem {
  kind: 'run';
  run: ChatExecutionRun;
  subagents: SubagentSessionRecord[];
}

export type ChatTimelineItem = ChatTimelineMessageItem | ChatTimelineRunItem;

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function parseJsonString(value: string | null | undefined) {
  if (!value) {
    return null;
  }

  try {
    return JSON.parse(value) as unknown;
  } catch {
    return null;
  }
}

function safeStringify(value: unknown) {
  if (value === null || value === undefined) {
    return null;
  }

  if (typeof value === 'string') {
    return value;
  }

  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function truncateSummary(value: string | null | undefined, maxLength = 72) {
  if (!value) {
    return '';
  }

  const trimmed = value.replace(/\s+/g, ' ').trim();
  if (trimmed.length <= maxLength) {
    return trimmed;
  }

  return `${trimmed.slice(0, maxLength - 1)}…`;
}

function summarizeToolInput(inputJson: string | null | undefined) {
  const parsed = parseJsonString(inputJson);
  if (!parsed) {
    return '';
  }

  const record = asRecord(parsed);
  if (!record) {
    return truncateSummary(String(parsed));
  }

  const summaryParts = Object.entries(record)
    .slice(0, 2)
    .map(
      ([key, value]) =>
        `${key}=${truncateSummary(typeof value === 'string' ? value : safeStringify(value), 24)}`,
    );
  return summaryParts.join(' · ');
}

function unwrapToolOutput(outputJson: string | null | undefined) {
  const parsed = parseJsonString(outputJson);
  const record = asRecord(parsed);
  if (!record) {
    return null;
  }

  const nested = asRecord(record.data);
  return {
    raw: record,
    data: nested ?? record,
  };
}

function summarizeShellOutput(outputJson: string | null | undefined) {
  const unwrapped = unwrapToolOutput(outputJson);
  const record = unwrapped?.data;
  if (!record) {
    return truncateSummary(outputJson || 'No output');
  }

  const exitCode = typeof record.exit_code === 'number' ? `Exit ${record.exit_code}` : null;
  const stdout = typeof record.stdout === 'string' ? record.stdout.trim() : '';
  const stderr = typeof record.stderr === 'string' ? record.stderr.trim() : '';
  const preview = stdout || stderr || (typeof record.message === 'string' ? record.message : '');
  const firstLine = preview.split(/\r?\n/).find((line) => line.trim()) || 'No output';
  return [exitCode, truncateSummary(firstLine, 48)].filter(Boolean).join(' · ');
}

function summarizeToolOutput(toolName: string, outputJson: string | null | undefined) {
  if (toolName === 'shell_exec') {
    return summarizeShellOutput(outputJson);
  }

  const unwrapped = unwrapToolOutput(outputJson);
  const record = unwrapped?.data;
  if (record) {
    for (const candidate of ['summary', 'message', 'text', 'result']) {
      if (typeof record[candidate] === 'string') {
        return truncateSummary(record[candidate] as string, 72);
      }
    }
  }

  const raw = unwrapped?.raw;
  if (raw && typeof raw.text === 'string') {
    return truncateSummary(raw.text, 72);
  }

  return truncateSummary(outputJson || 'No output');
}

function calculateDurationMs(startedAt: string | null, finishedAt: string | null) {
  if (!startedAt || !finishedAt) {
    return null;
  }

  const startedMs = new Date(startedAt).getTime();
  const finishedMs = new Date(finishedAt).getTime();
  if (Number.isNaN(startedMs) || Number.isNaN(finishedMs)) {
    return null;
  }

  return Math.max(finishedMs - startedMs, 0);
}

function createEmptyRun({
  id,
  taskRunId,
  sessionId,
  createdAt,
}: {
  id: string;
  taskRunId: string | null;
  sessionId: string;
  createdAt: string;
}): ChatExecutionRun {
  return {
    id,
    taskRunId,
    sessionId,
    prompt: null,
    userMessageId: null,
    assistantMessageId: null,
    createdAt,
    startedAt: null,
    finishedAt: null,
    status: 'running',
    finalText: null,
    errorMessage: null,
    steps: [],
  };
}

function upsertRun(state: ChatExecutionState, run: ChatExecutionRun) {
  const runsById = {
    ...state.runsById,
    [run.id]: run,
  };
  const existingSessionRunIds = state.sessionRunIds[run.sessionId] || [];
  const sessionRunIds = existingSessionRunIds.includes(run.id)
    ? state.sessionRunIds
    : {
        ...state.sessionRunIds,
        [run.sessionId]: [...existingSessionRunIds, run.id],
      };
  const runIdByTaskRunId =
    run.taskRunId && state.runIdByTaskRunId[run.taskRunId] !== run.id
      ? {
          ...state.runIdByTaskRunId,
          [run.taskRunId]: run.id,
        }
      : state.runIdByTaskRunId;

  return {
    runsById,
    sessionRunIds,
    runIdByTaskRunId,
  };
}

function updateRunStep(steps: ChatExecutionStep[], nextStep: ChatExecutionStep) {
  const existingIndex = steps.findIndex((step) => step.id === nextStep.id);
  if (existingIndex < 0) {
    return [...steps, nextStep].sort((left, right) =>
      left.createdAt.localeCompare(right.createdAt),
    );
  }

  const updated = [...steps];
  updated[existingIndex] = {
    ...updated[existingIndex],
    ...nextStep,
  };
  return updated;
}

function deriveRunStatus(event: SessionExecutionEvent): ChatExecutionRunStatus {
  switch (event.type) {
    case 'approval.requested':
      return 'awaiting_approval';
    case 'tool.failed':
    case 'execution.failed':
      return 'failed';
    case 'execution.completed':
      return 'completed';
    case 'message.user.accepted':
    case 'assistant.run.created':
    case 'execution.started':
    case 'tool.started':
    case 'tool.completed':
    case 'subagent.spawned':
    case 'message.completed':
      return 'running';
  }
}

function toolStepStatus(eventType: SessionExecutionEvent['type'], tool: SessionExecutionEventToolData) {
  if (eventType === 'tool.started') {
    return 'running';
  }
  if (eventType === 'tool.failed') {
    return 'failed';
  }
  return tool.status || 'completed';
}

function createToolStep(event: Extract<SessionExecutionEvent, { type: 'tool.started' | 'tool.completed' | 'tool.failed' }>): ChatExecutionStep {
  const tool = event.data;
  const toolName = tool.tool_name || 'tool';
  const summary =
    event.type === 'tool.failed'
      ? truncateSummary(tool.error_message || summarizeToolOutput(toolName, tool.output_json) || 'Tool failed')
      : summarizeToolOutput(toolName, tool.output_json) ||
        summarizeToolInput(tool.input_json) ||
        truncateSummary(event.type);

  return {
    id: tool.tool_call_id || event.id,
    eventId: event.id,
    kind: 'tool',
    eventType: event.type,
    title: toolName,
    status: toolStepStatus(event.type, tool),
    createdAt: event.created_at,
    startedAt: tool.started_at || null,
    finishedAt: tool.finished_at || null,
    durationMs: calculateDurationMs(tool.started_at || null, tool.finished_at || null),
    summary,
    details:
      safeStringify({
        input_json: parseJsonString(tool.input_json) ?? tool.input_json ?? null,
        output_json: parseJsonString(tool.output_json) ?? tool.output_json ?? null,
        output_text: tool.output_text ?? null,
        error_message: tool.error_message ?? null,
      }) || null,
  };
}

function createApprovalStep(event: Extract<SessionExecutionEvent, { type: 'approval.requested' }>): ChatExecutionStep {
  const approval = event.data;
  return {
    id: approval.approval_id || event.id,
    eventId: event.id,
    kind: 'approval',
    eventType: event.type,
    title: 'Approval requested',
    status: approval.status || 'pending',
    createdAt: event.created_at,
    startedAt: null,
    finishedAt: null,
    durationMs: null,
    summary: truncateSummary(approval.reason || approval.requested_action || 'Awaiting approval'),
    details: safeStringify(approval),
  };
}

function createSubagentStep(event: Extract<SessionExecutionEvent, { type: 'subagent.spawned' }>): ChatExecutionStep {
  const subagent = event.data;
  return {
    id: subagent.child_session_id || event.id,
    eventId: event.id,
    kind: 'subagent',
    eventType: event.type,
    title: 'Subagent',
    status: subagent.status || 'running',
    createdAt: event.created_at,
    startedAt: null,
    finishedAt: null,
    durationMs: null,
    summary: truncateSummary(subagent.goal_summary || event.type),
    details: safeStringify(subagent),
  };
}

function createStatusStep(
  event: Extract<SessionExecutionEvent, { type: 'execution.started' | 'execution.completed' | 'execution.failed' }>,
) {
  const run = event.data;
  const title =
    event.type === 'execution.started'
      ? 'Execution started'
      : event.type === 'execution.completed'
        ? 'Execution completed'
        : 'Execution failed';
  const summary =
    event.type === 'execution.failed'
      ? truncateSummary(run.error_message || 'Execution ended with an error.')
      : title;

  return {
    id: event.id,
    eventId: event.id,
    kind: 'status' as const,
    eventType: event.type,
    title,
    status: deriveRunStatus(event),
    createdAt: event.created_at,
    startedAt: run.started_at || null,
    finishedAt: run.finished_at || null,
    durationMs: calculateDurationMs(run.started_at || null, run.finished_at || null),
    summary,
    details: safeStringify(event.raw),
  };
}

function stepFromEvent(event: SessionExecutionEvent): ChatExecutionStep | null {
  switch (event.type) {
    case 'tool.started':
    case 'tool.completed':
    case 'tool.failed':
      return createToolStep(event);
    case 'approval.requested':
      return createApprovalStep(event);
    case 'subagent.spawned':
      return createSubagentStep(event);
    case 'execution.started':
    case 'execution.completed':
    case 'execution.failed':
      return createStatusStep(event);
    default:
      return null;
  }
}

function nextRunStatusFromResponse(response: RunResponse, previousStatus: ChatExecutionRunStatus) {
  if (response.status === 'completed') {
    return 'completed';
  }
  if (response.status === 'failed') {
    return 'failed';
  }
  if (previousStatus === 'connecting' && response.status === 'queued') {
    return 'connecting';
  }
  return 'running';
}

function runDataFromEvent(event: SessionExecutionEvent): SessionExecutionEventRunData | null {
  switch (event.type) {
    case 'execution.started':
    case 'execution.completed':
    case 'execution.failed':
      return event.data;
    default:
      return null;
  }
}

function toolDataFromEvent(event: SessionExecutionEvent): SessionExecutionEventToolData | null {
  switch (event.type) {
    case 'tool.started':
    case 'tool.completed':
    case 'tool.failed':
      return event.data;
    default:
      return null;
  }
}

function approvalDataFromEvent(event: SessionExecutionEvent): SessionExecutionEventApprovalData | null {
  return event.type === 'approval.requested' ? event.data : null;
}

function subagentDataFromEvent(event: SessionExecutionEvent): SessionExecutionEventSubagentData | null {
  return event.type === 'subagent.spawned' ? event.data : null;
}

export function createInitialChatExecutionState(): ChatExecutionState {
  return {
    runsById: {},
    sessionRunIds: {},
    runIdByTaskRunId: {},
  };
}

export function chatExecutionStateReducer(
  state: ChatExecutionState,
  action: ChatExecutionAction,
): ChatExecutionState {
  switch (action.type) {
    case 'run/optimistic-created': {
      const run = createEmptyRun({
        id: action.localRunId,
        taskRunId: null,
        sessionId: action.sessionId,
        createdAt: action.createdAt,
      });
      run.prompt = action.prompt;
      run.status = 'connecting';
      return upsertRun(state, run);
    }
    case 'run/response-bound': {
      const runIdForTaskRun =
        action.response.task_run_id
          ? state.runIdByTaskRunId[action.response.task_run_id] ||
            action.response.task_run_id
          : null;
      const existingRun =
        (runIdForTaskRun ? state.runsById[runIdForTaskRun] : null) ||
        state.runsById[action.localRunId] ||
        createEmptyRun({
          id: action.localRunId,
          taskRunId: null,
          sessionId: action.sessionId,
          createdAt: new Date().toISOString(),
        });
      const nextTaskRunId = action.response.task_run_id || existingRun.taskRunId;
      const nextRunId = nextTaskRunId || existingRun.id;
      const run: ChatExecutionRun = {
        ...existingRun,
        id: nextRunId,
        taskRunId: nextTaskRunId,
        userMessageId: action.response.user_message_id || existingRun.userMessageId,
        assistantMessageId:
          action.response.assistant_message_id || existingRun.assistantMessageId,
        finalText: action.response.output_text || existingRun.finalText,
        status: nextRunStatusFromResponse(action.response, existingRun.status),
      };

      const nextState = upsertRun(state, run);
      if (existingRun.id !== nextRunId || action.localRunId !== nextRunId) {
        const runIdsToRemove = new Set<string>();
        if (existingRun.id !== nextRunId) {
          runIdsToRemove.add(existingRun.id);
        }
        if (action.localRunId !== nextRunId) {
          runIdsToRemove.add(action.localRunId);
        }
        const runsById = Object.fromEntries(
          Object.entries(nextState.runsById).filter(([runId]) => !runIdsToRemove.has(runId)),
        );
        const sessionRunIds = {
          ...nextState.sessionRunIds,
          [run.sessionId]: (nextState.sessionRunIds[run.sessionId] || [])
            .map((id) => (runIdsToRemove.has(id) ? nextRunId : id))
            .filter((id, index, items) => items.indexOf(id) === index),
        };
        return {
          runsById,
          sessionRunIds,
          runIdByTaskRunId: nextTaskRunId
            ? {
                ...nextState.runIdByTaskRunId,
                [nextTaskRunId]: nextRunId,
              }
            : nextState.runIdByTaskRunId,
        };
      }

      return nextState;
    }
    case 'run/optimistic-discarded': {
      const existingRun = state.runsById[action.localRunId];
      if (!existingRun) {
        return state;
      }

      const runsById = Object.fromEntries(
        Object.entries(state.runsById).filter(([runId]) => runId !== action.localRunId),
      );
      const sessionRunIds = {
        ...state.sessionRunIds,
        [action.sessionId]: (state.sessionRunIds[action.sessionId] || []).filter(
          (runId) => runId !== action.localRunId,
        ),
      };
      const runIdByTaskRunId = Object.fromEntries(
        Object.entries(state.runIdByTaskRunId).filter(
          ([, runId]) => runId !== action.localRunId,
        ),
      );

      return {
        runsById,
        sessionRunIds,
        runIdByTaskRunId,
      };
    }
    case 'run/event-received': {
      const existingRunId = action.event.task_run_id
        ? state.runIdByTaskRunId[action.event.task_run_id]
        : undefined;
      const runId = existingRunId || action.event.task_run_id || action.event.id;
      const existingRun =
        state.runsById[runId] ||
        createEmptyRun({
          id: runId,
          taskRunId: action.event.task_run_id,
          sessionId: action.sessionId,
          createdAt: action.event.created_at,
        });

      const runData = runDataFromEvent(action.event);
      const toolData = toolDataFromEvent(action.event);
      const approvalData = approvalDataFromEvent(action.event);
      const nextStatus = deriveRunStatus(action.event);
      const run: ChatExecutionRun = {
        ...existingRun,
        taskRunId: action.event.task_run_id || existingRun.taskRunId,
        status: nextStatus,
        startedAt:
          runData?.started_at ||
          toolData?.started_at ||
          existingRun.startedAt,
        finishedAt:
          runData?.finished_at ||
          toolData?.finished_at ||
          (nextStatus === 'completed' || nextStatus === 'failed'
            ? action.event.created_at
            : existingRun.finishedAt),
        errorMessage:
          runData?.error_message ||
          toolData?.error_message ||
          existingRun.errorMessage,
      };

      if (action.event.type === 'assistant.run.created') {
        run.userMessageId = action.event.data.user_message_id || run.userMessageId;
      }
      if (action.event.type === 'message.user.accepted') {
        run.userMessageId = action.event.data.message.id || run.userMessageId;
      }
      if (action.event.type === 'message.completed') {
        run.assistantMessageId = action.event.data.message.id || run.assistantMessageId;
        run.finalText = action.event.data.message.content_text || run.finalText;
      }
      if (approvalData?.status === 'pending') {
        run.status = 'awaiting_approval';
      }
      if (subagentDataFromEvent(action.event)) {
        run.status = existingRun.status === 'disconnected' ? 'disconnected' : run.status;
      }

      const nextStep = stepFromEvent(action.event);
      if (nextStep) {
        run.steps = updateRunStep(existingRun.steps, nextStep);
      }

      return upsertRun(state, run);
    }
    default:
      return state;
  }
}

export function buildChatTimelineItems({
  activeSessionId,
  messages,
  runsState,
  subagents,
}: {
  activeSessionId: string | null;
  messages: MessageRecord[];
  runsState: ChatExecutionState;
  subagents: SubagentSessionRecord[];
}): ChatTimelineItem[] {
  if (!activeSessionId) {
    return messages.map((message) => ({ kind: 'message', message }));
  }

  const runIds = runsState.sessionRunIds[activeSessionId] || [];
  const runs = runIds
    .map((runId) => runsState.runsById[runId])
    .filter((run): run is ChatExecutionRun => Boolean(run))
    .sort((left, right) => left.createdAt.localeCompare(right.createdAt));
  const assistantMessageIds = new Set(
    runs.map((run) => run.assistantMessageId).filter((value): value is string => Boolean(value)),
  );
  const runIdsByUserMessageId = new Map<string, ChatExecutionRun[]>();

  for (const run of runs) {
    if (run.userMessageId) {
      const items = runIdsByUserMessageId.get(run.userMessageId) || [];
      items.push(run);
      runIdsByUserMessageId.set(run.userMessageId, items);
    }
  }

  const subagentsByRunId = new Map<string | null, SubagentSessionRecord[]>();
  for (const subagent of subagents) {
    const launcherId = subagent.run.launcher_task_run_id;
    const list = subagentsByRunId.get(launcherId) || [];
    list.push(subagent);
    subagentsByRunId.set(launcherId, list);
  }

  const renderedRunIds = new Set<string>();
  const items: ChatTimelineItem[] = [];

  for (const message of messages) {
    if (message.role === 'assistant' && assistantMessageIds.has(message.id)) {
      continue;
    }

    items.push({
      kind: 'message',
      message,
    });

    const anchoredRuns = runIdsByUserMessageId.get(message.id) || [];
    for (const run of anchoredRuns) {
      renderedRunIds.add(run.id);
      items.push({
        kind: 'run',
        run,
        subagents: subagentsByRunId.get(run.taskRunId) || [],
      });
    }
  }

  for (const run of runs) {
    if (renderedRunIds.has(run.id)) {
      continue;
    }

    items.push({
      kind: 'run',
      run,
      subagents: subagentsByRunId.get(run.taskRunId) || [],
    });
  }

  return items;
}
