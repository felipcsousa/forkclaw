import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  connectSessionExecutionStream,
  type SessionExecutionEvent,
} from './sessionExecutionStream';

const mockResolveBackendConnectionInfo = vi.fn();

vi.mock('../desktopRuntime', () => ({
  resolveBackendConnectionInfo: () => mockResolveBackendConnectionInfo(),
}));

function createEventStreamBody(chunks: string[]) {
  const encoder = new TextEncoder();

  return new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk));
      }
      controller.close();
    },
  });
}

describe('connectSessionExecutionStream', () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.useFakeTimers();
    mockResolveBackendConnectionInfo.mockResolvedValue({
      baseUrl: 'http://127.0.0.1:8000',
      bootstrapToken: 'bootstrap-token',
      managedByShell: false,
    });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    globalThis.fetch = originalFetch;
  });

  it('opens the session SSE endpoint with the bootstrap token and parses typed events', async () => {
    const events: SessionExecutionEvent[] = [];

    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(
        createEventStreamBody([
          'id: evt-1\n',
          'event: tool_call.completed\n',
          'data: {"session_id":"session-1","task_run_id":"run-1","created_at":"2026-03-12T13:00:00Z","tool":{"tool_name":"shell","status":"completed"}}\n\n',
        ]),
        {
          status: 200,
          headers: {
            'Content-Type': 'text/event-stream',
          },
        },
      ),
    ) as typeof fetch;

    const connection = connectSessionExecutionStream({
      sessionId: 'session-1',
      onEvent: (event) => {
        events.push(event);
        connection.close();
      },
    });

    await vi.advanceTimersByTimeAsync(0);

    expect(globalThis.fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/sessions/session-1/events/stream',
      expect.objectContaining({
        headers: expect.any(Headers),
        method: 'GET',
      }),
    );
    const headers = (vi.mocked(globalThis.fetch).mock.calls[0]?.[1]?.headers ??
      new Headers()) as Headers;
    expect(headers.get('Accept')).toBe('text/event-stream');
    expect(headers.get('X-Backend-Bootstrap-Token')).toBe('bootstrap-token');
    expect(events).toEqual([
      expect.objectContaining({
        event_id: 'evt-1',
        event_type: 'tool_call.completed',
        session_id: 'session-1',
        task_run_id: 'run-1',
      }),
    ]);

    connection.close();
  });

  it('signals reconnect attempts after a transient fetch failure', async () => {
    const reconnects: number[] = [];
    const events: SessionExecutionEvent[] = [];

    globalThis.fetch = vi
      .fn()
      .mockRejectedValueOnce(new Error('socket closed'))
      .mockResolvedValueOnce(
        new Response(
          createEventStreamBody([
            'event: kernel.execution.completed\n',
            'data: {"event_id":"evt-2","session_id":"session-1","task_run_id":"run-2","created_at":"2026-03-12T13:00:01Z"}\n\n',
          ]),
          {
            status: 200,
            headers: {
              'Content-Type': 'text/event-stream',
            },
          },
        ),
      ) as typeof fetch;

    const connection = connectSessionExecutionStream({
      sessionId: 'session-1',
      onEvent: (event) => {
        events.push(event);
        connection.close();
      },
      onReconnect: (attempt) => {
        reconnects.push(attempt);
      },
    });

    await vi.advanceTimersByTimeAsync(1_000);
    await vi.advanceTimersByTimeAsync(0);

    expect(reconnects).toEqual([1]);
    expect(events).toEqual([
      expect.objectContaining({
        event_id: 'evt-2',
        task_run_id: 'run-2',
      }),
    ]);
  });
});
