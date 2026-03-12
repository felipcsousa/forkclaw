import { resolveBackendConnectionInfo } from '../desktopRuntime';

export interface SessionExecutionEventMessagePayload {
  id: string;
  role: string;
  content_text: string;
  sequence_number: number;
}

export interface SessionExecutionEventMessageUserAcceptedData {
  message: SessionExecutionEventMessagePayload;
}

export interface SessionExecutionEventAssistantRunCreatedData {
  user_message_id?: string | null;
  status?: string | null;
}

export interface SessionExecutionEventToolData {
  tool_call_id?: string | null;
  tool_name?: string | null;
  status?: string | null;
  input_json?: string | null;
  output_json?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  output_text?: string | null;
  error_message?: string | null;
}

export interface SessionExecutionEventApprovalData {
  approval_id?: string | null;
  tool_call_id?: string | null;
  tool_name?: string | null;
  requested_action?: string | null;
  reason?: string | null;
  status?: string | null;
}

export interface SessionExecutionEventSubagentData {
  parent_session_id?: string | null;
  child_session_id?: string | null;
  status?: string | null;
  goal_summary?: string | null;
}

export interface SessionExecutionEventMessageCompletedData {
  message: SessionExecutionEventMessagePayload;
}

export interface SessionExecutionEventRunData {
  status?: string | null;
  error_message?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
}

interface SessionExecutionEventBase<TType extends string, TData> {
  id: string;
  type: TType;
  session_id: string;
  task_id: string | null;
  task_run_id: string | null;
  created_at: string;
  data: TData;
  raw: Record<string, unknown>;
}

export type SessionExecutionEvent =
  | SessionExecutionEventBase<
      'message.user.accepted',
      SessionExecutionEventMessageUserAcceptedData
    >
  | SessionExecutionEventBase<
      'assistant.run.created',
      SessionExecutionEventAssistantRunCreatedData
    >
  | SessionExecutionEventBase<'tool.started', SessionExecutionEventToolData>
  | SessionExecutionEventBase<'tool.completed', SessionExecutionEventToolData>
  | SessionExecutionEventBase<'tool.failed', SessionExecutionEventToolData>
  | SessionExecutionEventBase<'approval.requested', SessionExecutionEventApprovalData>
  | SessionExecutionEventBase<'subagent.spawned', SessionExecutionEventSubagentData>
  | SessionExecutionEventBase<'message.completed', SessionExecutionEventMessageCompletedData>
  | SessionExecutionEventBase<'execution.started', SessionExecutionEventRunData>
  | SessionExecutionEventBase<'execution.completed', SessionExecutionEventRunData>
  | SessionExecutionEventBase<'execution.failed', SessionExecutionEventRunData>;

export interface SessionExecutionStreamOptions {
  sessionId: string;
  onOpen?: () => void;
  onEvent: (event: SessionExecutionEvent) => void;
  onError?: (error: Error) => void;
  onDisconnect?: (error?: Error) => void;
  onReconnect?: (attempt: number, delayMs: number) => void;
}

export interface SessionExecutionStreamConnection {
  close: () => void;
}

const SESSION_EXECUTION_EVENT_TYPES = [
  'message.user.accepted',
  'assistant.run.created',
  'tool.started',
  'tool.completed',
  'tool.failed',
  'approval.requested',
  'subagent.spawned',
  'message.completed',
  'execution.started',
  'execution.completed',
  'execution.failed',
] as const satisfies readonly SessionExecutionEvent['type'][];

const BASE_RECONNECT_DELAY_MS = 1_000;
const MAX_RECONNECT_DELAY_MS = 5_000;

type EventFrame = {
  eventId: string;
  eventName: string;
  data: string;
};

function buildEventFrame(block: string): EventFrame | null {
  const lines = block.split(/\r?\n/);
  const dataLines: string[] = [];
  let eventName = 'message';
  let eventId = '';

  for (const line of lines) {
    if (!line || line.startsWith(':')) {
      continue;
    }

    const separatorIndex = line.indexOf(':');
    const field = separatorIndex >= 0 ? line.slice(0, separatorIndex) : line;
    const value = separatorIndex >= 0 ? line.slice(separatorIndex + 1).trimStart() : '';

    if (field === 'event') {
      eventName = value || 'message';
      continue;
    }

    if (field === 'id') {
      eventId = value;
      continue;
    }

    if (field === 'data') {
      dataLines.push(value);
    }
  }

  if (dataLines.length === 0) {
    return null;
  }

  return {
    eventId,
    eventName,
    data: dataLines.join('\n'),
  };
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function asString(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value : null;
}

function isSessionExecutionEventType(value: string): value is SessionExecutionEvent['type'] {
  return (SESSION_EXECUTION_EVENT_TYPES as readonly string[]).includes(value);
}

function normalizeSessionExecutionEvent(frame: EventFrame): SessionExecutionEvent | null {
  let parsed: unknown;

  try {
    parsed = JSON.parse(frame.data);
  } catch {
    return null;
  }

  const record = asRecord(parsed);
  if (!record) {
    return null;
  }

  const id = asString(record.id) || frame.eventId || crypto.randomUUID();
  const type = asString(record.type) || frame.eventName;
  const sessionId = asString(record.session_id);
  const createdAt = asString(record.created_at) || new Date().toISOString();
  const data = asRecord(record.data);

  if (!id || !type || !sessionId || !data || !isSessionExecutionEventType(type)) {
    return null;
  }

  return {
    id,
    type,
    session_id: sessionId,
    task_id: asString(record.task_id),
    task_run_id: asString(record.task_run_id),
    created_at: createdAt,
    data,
    raw: record,
  } as SessionExecutionEvent;
}

async function consumeEventStream(
  response: Response,
  options: SessionExecutionStreamOptions,
  isClosed: () => boolean,
  handleEvent: (event: SessionExecutionEvent) => void,
) {
  if (!response.ok) {
    throw new Error(`Stream request failed with status ${response.status}.`);
  }
  if (!response.body) {
    throw new Error('Stream response did not include a body.');
  }

  options.onOpen?.();

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (!isClosed()) {
    const result = await reader.read();
    if (result.done) {
      break;
    }

    buffer += decoder.decode(result.value, { stream: true });
    const frames = buffer.split(/\r?\n\r?\n/);
    buffer = frames.pop() || '';

    for (const frameText of frames) {
      const frame = buildEventFrame(frameText);
      if (!frame) {
        continue;
      }
      const event = normalizeSessionExecutionEvent(frame);
      if (event) {
        handleEvent(event);
      }
    }
  }
}

export function connectSessionExecutionStream(
  options: SessionExecutionStreamOptions,
): SessionExecutionStreamConnection {
  let closed = false;
  let reconnectAttempt = 0;
  let activeAbortController: AbortController | null = null;
  let lastEventId: string | null = null;
  const seenEventIds = new Set<string>();

  const isClosed = () => closed;

  const run = async () => {
    while (!closed) {
      try {
        const connection = await resolveBackendConnectionInfo();
        activeAbortController = new AbortController();
        const headers = new Headers({
          Accept: 'text/event-stream',
        });
        if (connection.bootstrapToken) {
          headers.set('X-Backend-Bootstrap-Token', connection.bootstrapToken);
        }
        if (lastEventId) {
          headers.set('Last-Event-ID', lastEventId);
        }

        const response = await fetch(
          `${connection.baseUrl}/sessions/${encodeURIComponent(options.sessionId)}/events`,
          {
            method: 'GET',
            headers,
            signal: activeAbortController.signal,
          },
        );

        reconnectAttempt = 0;
        await consumeEventStream(response, options, isClosed, (event) => {
          lastEventId = event.id;
          if (seenEventIds.has(event.id)) {
            return;
          }
          seenEventIds.add(event.id);
          options.onEvent(event);
        });
        if (!closed) {
          options.onDisconnect?.();
        }
      } catch (error) {
        if (closed) {
          return;
        }
        const normalizedError =
          error instanceof Error ? error : new Error('Failed to connect to session stream.');
        options.onError?.(normalizedError);
        options.onDisconnect?.(normalizedError);
      }

      if (closed) {
        return;
      }

      reconnectAttempt += 1;
      const reconnectDelayMs = Math.min(
        BASE_RECONNECT_DELAY_MS * reconnectAttempt,
        MAX_RECONNECT_DELAY_MS,
      );
      options.onReconnect?.(reconnectAttempt, reconnectDelayMs);
      await new Promise((resolve) => globalThis.setTimeout(resolve, reconnectDelayMs));
    }
  };

  void run();

  return {
    close() {
      closed = true;
      activeAbortController?.abort();
    },
  };
}
