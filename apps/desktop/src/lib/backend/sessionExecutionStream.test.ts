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

  it('opens the canonical SSE endpoint and parses canonical event envelopes', async () => {
    const events: SessionExecutionEvent[] = [];

    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(
        createEventStreamBody([
          'id: evt-1\n',
          'event: tool.completed\n',
          'data: {"id":"evt-1","type":"tool.completed","session_id":"session-1","task_run_id":"run-1","created_at":"2026-03-12T13:00:00Z","data":{"tool_call_id":"call-1","tool_name":"shell_exec","status":"completed","input_json":"{\\"command\\":\\"pwd\\"}","output_json":"{\\"exit_code\\":0}","started_at":"2026-03-12T12:59:58Z","finished_at":"2026-03-12T13:00:00Z"}}\n\n',
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
      'http://127.0.0.1:8000/sessions/session-1/events',
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
        id: 'evt-1',
        type: 'tool.completed',
        session_id: 'session-1',
        task_run_id: 'run-1',
        data: expect.objectContaining({
          tool_name: 'shell_exec',
          status: 'completed',
        }),
      }),
    ]);

    connection.close();
  });

  it('reconnects with Last-Event-ID and suppresses replayed events', async () => {
    const reconnects: number[] = [];
    const events: SessionExecutionEvent[] = [];
    const readyCalls: number[] = [];

    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          createEventStreamBody([
            'id: evt-1\n',
            'event: execution.started\n',
            'data: {"id":"evt-1","type":"execution.started","session_id":"session-1","task_run_id":"run-2","created_at":"2026-03-12T13:00:01Z","data":{"status":"running","started_at":"2026-03-12T13:00:01Z","finished_at":null}}\n\n',
            'event: stream.ready\n',
            'data: {"type":"stream.ready","session_id":"session-1","data":{"phase":"live"}}\n\n',
          ]),
          {
            status: 200,
            headers: {
              'Content-Type': 'text/event-stream',
            },
          },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          createEventStreamBody([
            'id: evt-1\n',
            'event: execution.started\n',
            'data: {"id":"evt-1","type":"execution.started","session_id":"session-1","task_run_id":"run-2","created_at":"2026-03-12T13:00:01Z","data":{"status":"running","started_at":"2026-03-12T13:00:01Z","finished_at":null}}\n\n',
            'id: evt-2\n',
            'event: execution.completed\n',
            'data: {"id":"evt-2","type":"execution.completed","session_id":"session-1","task_run_id":"run-2","created_at":"2026-03-12T13:00:02Z","data":{"status":"completed","started_at":"2026-03-12T13:00:01Z","finished_at":"2026-03-12T13:00:02Z"}}\n\n',
            'event: stream.ready\n',
            'data: {"type":"stream.ready","session_id":"session-1","data":{"phase":"live"}}\n\n',
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
      },
      onReconnect: (attempt) => {
        reconnects.push(attempt);
      },
      onReady: () => {
        readyCalls.push(events.length);
        if (readyCalls.length === 2) {
          connection.close();
        }
      },
    });

    await vi.advanceTimersByTimeAsync(1_000);
    await vi.advanceTimersByTimeAsync(0);

    expect(reconnects).toEqual([1]);
    expect(readyCalls).toEqual([1, 2]);
    const secondHeaders = (vi.mocked(globalThis.fetch).mock.calls[1]?.[1]?.headers ??
      new Headers()) as Headers;
    expect(secondHeaders.get('Last-Event-ID')).toBe('evt-1');
    expect(events).toEqual([
      expect.objectContaining({
        id: 'evt-1',
        task_run_id: 'run-2',
      }),
      expect.objectContaining({
        id: 'evt-2',
        task_run_id: 'run-2',
      }),
    ]);
  });
});
