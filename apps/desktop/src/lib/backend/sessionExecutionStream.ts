import { resolveBackendConnectionInfo } from '../desktopRuntime';

export interface SessionExecutionEventToolPayload {
  tool_call_id?: string | null;
  tool_name?: string | null;
  status?: string | null;
  input_json?: string | null;
  output_json?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface SessionExecutionEventApprovalPayload {
  approval_id?: string | null;
  status?: string | null;
  reason?: string | null;
}

export interface SessionExecutionEventSubagentPayload {
  child_session_id?: string | null;
  title?: string | null;
  status?: string | null;
  summary?: string | null;
}

export interface SessionExecutionEventAssistantMessagePayload {
  assistant_message_id?: string | null;
  user_message_id?: string | null;
  content_text?: string | null;
  status?: string | null;
}

export interface SessionExecutionEventRunPayload {
  status?: string | null;
  error_message?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface SessionExecutionEvent {
  event_id: string;
  event_type: string;
  session_id: string;
  task_run_id: string | null;
  created_at: string;
  run?: SessionExecutionEventRunPayload;
  tool?: SessionExecutionEventToolPayload;
  approval?: SessionExecutionEventApprovalPayload;
  subagent?: SessionExecutionEventSubagentPayload;
  assistant_message?: SessionExecutionEventAssistantMessagePayload;
  raw: Record<string, unknown>;
}

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

const BASE_RECONNECT_DELAY_MS = 1_000;
const MAX_RECONNECT_DELAY_MS = 5_000;

function buildEventFrame(block: string) {
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

function normalizeSessionExecutionEvent(
  frame: { eventId: string; eventName: string; data: string },
): SessionExecutionEvent | null {
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

  const rawEventId = asString(record.event_id) || frame.eventId || crypto.randomUUID();
  const rawEventType = asString(record.event_type) || frame.eventName;
  const sessionId = asString(record.session_id);
  const createdAt = asString(record.created_at) || new Date().toISOString();

  if (!sessionId || !rawEventType) {
    return null;
  }

  return {
    event_id: rawEventId,
    event_type: rawEventType,
    session_id: sessionId,
    task_run_id: asString(record.task_run_id),
    created_at: createdAt,
    run: asRecord(record.run) || undefined,
    tool: asRecord(record.tool) || undefined,
    approval: asRecord(record.approval) || undefined,
    subagent: asRecord(record.subagent) || undefined,
    assistant_message: asRecord(record.assistant_message) || undefined,
    raw: record,
  };
}

async function consumeEventStream(
  response: Response,
  options: SessionExecutionStreamOptions,
  isClosed: () => boolean,
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
        options.onEvent(event);
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

        const response = await fetch(
          `${connection.baseUrl}/sessions/${encodeURIComponent(options.sessionId)}/events/stream`,
          {
            method: 'GET',
            headers,
            signal: activeAbortController.signal,
          },
        );

        reconnectAttempt = 0;
        await consumeEventStream(response, options, isClosed);
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
