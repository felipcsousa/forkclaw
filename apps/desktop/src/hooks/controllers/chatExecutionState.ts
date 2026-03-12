import type { AgentExecutionResponse, MessageRecord, SubagentSessionRecord } from '../../lib/backend';
import type { SessionExecutionEvent } from '../../lib/backend/sessionExecutionStream';

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
      response: Partial<AgentExecutionResponse>;
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

  const record =
    parsed && typeof parsed === 'object' && !Array.isArray(parsed)
      ? (parsed as Record<string, unknown>)
      : null;
  if (!record) {
    return truncateSummary(String(parsed));
  }

  const summaryParts = Object.entries(record)
    .slice(0, 2)
    .map(([key, value]) => `${key}=${truncateSummary(typeof value === 'string' ? value : safeStringify(value), 24)}`);
  return summaryParts.join(' · ');
}

function summarizeShellOutput(outputJson: string | null | undefined) {
  const parsed = parseJsonString(outputJson);
  const record =
    parsed && typeof parsed === 'object' && !Array.isArray(parsed)
      ? (parsed as Record<string, unknown>)
      : null;
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
  if (toolName === 'shell' || toolName === 'exec_command') {
    return summarizeShellOutput(outputJson);
  }

  const parsed = parseJsonString(outputJson);
  if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
    const record = parsed as Record<string, unknown>;
    for (const candidate of ['summary', 'message', 'text', 'result']) {
      if (typeof record[candidate] === 'string') {
        return truncateSummary(record[candidate] as string, 72);
      }
    }
  }

  return truncateSummary(outputJson || 'No output');
}

function deriveRunStatus(event: SessionExecutionEvent) {
  switch (event.event_type) {
    case 'kernel.execution.awaiting_approval':
    case 'tool_call.approval_requested':
      return 'awaiting_approval' as const;
    case 'kernel.execution.failed':
    case 'tool_call.failed':
      return 'failed' as const;
    case 'kernel.execution.completed':
    case 'assistant.message.completed':
      return 'completed' as const;
    default:
      return 'running' as const;
  }
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

function updateRunStep(
  steps: ChatExecutionStep[],
  nextStep: ChatExecutionStep,
) {
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

function stepFromEvent(event: SessionExecutionEvent): ChatExecutionStep | null {
  if (event.tool) {
    const toolName = event.tool.tool_name || 'tool';
    return {
      id: event.tool.tool_call_id || event.event_id,
      eventId: event.event_id,
      kind: 'tool',
      eventType: event.event_type,
      title: toolName,
      status: event.tool.status || deriveRunStatus(event),
      createdAt: event.created_at,
      startedAt: event.tool.started_at || null,
      finishedAt: event.tool.finished_at || null,
      durationMs: calculateDurationMs(
        event.tool.started_at || null,
        event.tool.finished_at || null,
      ),
      summary:
        summarizeToolOutput(toolName, event.tool.output_json) ||
        summarizeToolInput(event.tool.input_json) ||
        truncateSummary(event.event_type),
      details:
        safeStringify({
          input_json: parseJsonString(event.tool.input_json) ?? event.tool.input_json ?? null,
          output_json: parseJsonString(event.tool.output_json) ?? event.tool.output_json ?? null,
        }) || null,
    };
  }

  if (event.approval) {
    return {
      id: event.approval.approval_id || event.event_id,
      eventId: event.event_id,
      kind: 'approval',
      eventType: event.event_type,
      title: 'Approval requested',
      status: event.approval.status || 'pending',
      createdAt: event.created_at,
      startedAt: null,
      finishedAt: null,
      durationMs: null,
      summary: truncateSummary(event.approval.reason || 'Awaiting approval'),
      details: safeStringify(event.approval),
    };
  }

  if (event.subagent) {
    return {
      id: event.subagent.child_session_id || event.event_id,
      eventId: event.event_id,
      kind: 'subagent',
      eventType: event.event_type,
      title: event.subagent.title || 'Subagent',
      status: event.subagent.status || deriveRunStatus(event),
      createdAt: event.created_at,
      startedAt: null,
      finishedAt: null,
      durationMs: null,
      summary: truncateSummary(event.subagent.summary || event.event_type),
      details: safeStringify(event.subagent),
    };
  }

  if (event.event_type === 'assistant.message.completed') {
    return null;
  }

  return {
    id: event.event_id,
    eventId: event.event_id,
    kind: 'status',
    eventType: event.event_type,
    title: event.event_type,
    status: deriveRunStatus(event),
    createdAt: event.created_at,
    startedAt: event.run?.started_at || null,
    finishedAt: event.run?.finished_at || null,
    durationMs: calculateDurationMs(
      event.run?.started_at || null,
      event.run?.finished_at || null,
    ),
    summary: truncateSummary(event.run?.error_message || event.event_type),
    details: safeStringify(event.raw),
  };
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
        status:
          action.response.status === 'completed'
            ? 'completed'
            : action.response.status === 'failed'
              ? 'failed'
              : 'running',
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
          [run.sessionId]: (nextState.sessionRunIds[run.sessionId] || []).map((id) =>
            runIdsToRemove.has(id) ? nextRunId : id,
          ).filter((id, index, items) => items.indexOf(id) === index),
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
    case 'run/event-received': {
      const existingRunId = action.event.task_run_id
        ? state.runIdByTaskRunId[action.event.task_run_id]
        : undefined;
      const runId = existingRunId || action.event.task_run_id || action.event.event_id;
      const existingRun =
        state.runsById[runId] ||
        createEmptyRun({
          id: runId,
          taskRunId: action.event.task_run_id,
          sessionId: action.sessionId,
          createdAt: action.event.created_at,
        });
      const run: ChatExecutionRun = {
        ...existingRun,
        taskRunId: action.event.task_run_id || existingRun.taskRunId,
        status: deriveRunStatus(action.event),
        startedAt: action.event.run?.started_at || existingRun.startedAt,
        finishedAt:
          action.event.run?.finished_at ||
          (deriveRunStatus(action.event) === 'completed' ||
          deriveRunStatus(action.event) === 'failed'
            ? action.event.created_at
            : existingRun.finishedAt),
        errorMessage: action.event.run?.error_message || existingRun.errorMessage,
      };

      if (action.event.assistant_message) {
        run.assistantMessageId =
          action.event.assistant_message.assistant_message_id || run.assistantMessageId;
        run.userMessageId =
          action.event.assistant_message.user_message_id || run.userMessageId;
        run.finalText =
          action.event.assistant_message.content_text || run.finalText;
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
        subagents: subagents.filter(
          (subagent) => subagent.run.launcher_task_run_id === run.taskRunId,
        ),
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
      subagents: subagents.filter(
        (subagent) => subagent.run.launcher_task_run_id === run.taskRunId,
      ),
    });
  }

  return items;
}
