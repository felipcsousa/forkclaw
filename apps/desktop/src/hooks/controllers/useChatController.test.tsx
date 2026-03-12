import { act, renderHook, waitFor } from '@testing-library/react';
import type { Dispatch, SetStateAction } from 'react';
import { vi } from 'vitest';

import type { SessionExecutionStreamOptions } from '../../lib/backend/sessionExecutionStream';
import { useChatController } from './useChatController';

const mockCancelSessionSubagent = vi.fn();
const mockCreateSession = vi.fn();
const mockFetchSessionMessages = vi.fn();
const mockFetchSessions = vi.fn();
const mockFetchSessionSubagent = vi.fn();
const mockFetchSessionSubagentMessages = vi.fn();
const mockFetchSessionSubagents = vi.fn();
const mockSendSessionMessageAsync = vi.fn();
const mockConnectSessionExecutionStream = vi.fn();
let capturedStreamOptions: SessionExecutionStreamOptions | null = null;

vi.mock('../../lib/backend/sessions', () => ({
  cancelSessionSubagent: (sessionId: string, childSessionId: string) =>
    mockCancelSessionSubagent(sessionId, childSessionId),
  createSession: (title?: string) => mockCreateSession(title),
  fetchSessionMessages: (sessionId: string) => mockFetchSessionMessages(sessionId),
  fetchSessions: () => mockFetchSessions(),
  fetchSessionSubagent: (sessionId: string, childSessionId: string) =>
    mockFetchSessionSubagent(sessionId, childSessionId),
  fetchSessionSubagentMessages: (sessionId: string, childSessionId: string) =>
    mockFetchSessionSubagentMessages(sessionId, childSessionId),
  fetchSessionSubagents: (sessionId: string) =>
    mockFetchSessionSubagents(sessionId),
  sendSessionMessageAsync: (sessionId: string, content: string) =>
    mockSendSessionMessageAsync(sessionId, content),
}));

vi.mock('../../lib/backend/sessionExecutionStream', () => ({
  connectSessionExecutionStream: (options: SessionExecutionStreamOptions) => {
    capturedStreamOptions = options;
    mockConnectSessionExecutionStream(options);
    return {
      close: vi.fn(),
    };
  },
}));

function createRunAsyncAction() {
  return async <T,>(
    action: () => Promise<T>,
    options: { setPending?: Dispatch<SetStateAction<boolean>> },
  ): Promise<T | null> => {
    options.setPending?.(true);
    try {
      return await action();
    } finally {
      options.setPending?.(false);
    }
  };
}

describe('useChatController', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    capturedStreamOptions = null;
  });

  it('creates a session on first send and refreshes the active chat context', async () => {
    const runAsyncAction = createRunAsyncAction();
    const setErrorMessage = vi.fn();
    const session = {
      id: 'session-1',
      title: 'New Session',
      kind: 'main',
    };

    mockCreateSession.mockResolvedValue(session);
    mockSendSessionMessageAsync.mockResolvedValue({
      task_id: 'task-1',
      task_run_id: 'run-1',
      session_id: 'session-1',
      user_message_id: 'message-1',
      status: 'queued',
      events_url: '/sessions/session-1/events?task_run_id=run-1',
    });
    mockFetchSessions.mockResolvedValue({ items: [session] });
    mockFetchSessionMessages.mockResolvedValue({ session, items: [] });
    mockFetchSessionSubagents.mockResolvedValue({ items: [] });

    const { result } = renderHook(() =>
      useChatController({
        runAsyncAction,
        setErrorMessage,
      }),
    );

    act(() => {
      result.current.setDraft('hello subagent');
    });

    await act(async () => {
      await result.current.handleSendMessage();
    });

    await waitFor(() => {
      expect(mockCreateSession).toHaveBeenCalledWith('New Session');
      expect(mockSendSessionMessageAsync).toHaveBeenCalledWith(
        'session-1',
        'hello subagent',
      );
      expect(mockFetchSessions).toHaveBeenCalledTimes(1);
      expect(mockFetchSessionMessages).toHaveBeenCalledWith('session-1');
      expect(mockFetchSessionSubagents).toHaveBeenCalledWith('session-1');
      expect(result.current.activeSession).toEqual(session);
      expect(result.current.draft).toBe('');
    });
  });

  it('wires stream lifecycle callbacks and surfaces disconnected state for the active main session', async () => {
    const runAsyncAction = createRunAsyncAction();
    const setErrorMessage = vi.fn();
    const session = {
      id: 'session-1',
      title: 'Persistent Chat',
      kind: 'main',
    };

    mockFetchSessions.mockResolvedValue({ items: [session] });
    mockFetchSessionMessages.mockResolvedValue({ session, items: [] });
    mockFetchSessionSubagents.mockResolvedValue({ items: [] });

    const { result } = renderHook(() =>
      useChatController({
        runAsyncAction,
        setErrorMessage,
      }),
    );

    await act(async () => {
      await result.current.bootstrap();
    });

    await waitFor(() => {
      expect(mockConnectSessionExecutionStream).toHaveBeenCalledWith(
        expect.objectContaining({ sessionId: 'session-1' }),
      );
      expect(capturedStreamOptions).not.toBeNull();
      expect(result.current.executionStreamStatus).toBe('connecting');
      expect(capturedStreamOptions?.onReconnect).toEqual(expect.any(Function));
      expect(capturedStreamOptions?.onError).toEqual(expect.any(Function));
      expect(capturedStreamOptions?.onDisconnect).toEqual(expect.any(Function));
    });

    await act(async () => {
      capturedStreamOptions!.onError!(
        new Error('Live stream disconnected. Falling back to session refresh.'),
      );
    });
    await waitFor(() => {
      expect(result.current.executionStreamStatus).toBe('disconnected');
      expect(result.current.executionStreamErrorMessage).toBe(
        'Live stream disconnected. Falling back to session refresh.',
      );
    });
  });

  it('tracks approval-requested runs through final completion', async () => {
    const runAsyncAction = createRunAsyncAction();
    const setErrorMessage = vi.fn();
    const session = {
      id: 'session-1',
      title: 'Persistent Chat',
      kind: 'main',
    };

    mockFetchSessions.mockResolvedValue({ items: [session] });
    mockFetchSessionMessages.mockResolvedValue({ session, items: [] });
    mockFetchSessionSubagents.mockResolvedValue({ items: [] });
    mockSendSessionMessageAsync.mockResolvedValue({
      task_id: 'task-1',
      task_run_id: 'run-1',
      session_id: 'session-1',
      user_message_id: 'message-1',
      status: 'queued',
      events_url: '/sessions/session-1/events?task_run_id=run-1',
    });

    const { result } = renderHook(() =>
      useChatController({
        runAsyncAction,
        setErrorMessage,
      }),
    );

    await act(async () => {
      await result.current.bootstrap();
    });

    act(() => {
      capturedStreamOptions?.onOpen?.();
      result.current.setDraft('Run a guarded shell command.');
    });

    await act(async () => {
      await result.current.handleSendMessage();
    });

    await waitFor(() => {
      expect(mockSendSessionMessageAsync).toHaveBeenCalledWith(
        'session-1',
        'Run a guarded shell command.',
      );
      expect(result.current.liveRuns).toHaveLength(1);
    });

    act(() => {
      capturedStreamOptions?.onEvent({
        id: 'evt-approval-1',
        type: 'approval.requested',
        session_id: 'session-1',
        task_id: 'task-1',
        task_run_id: 'run-1',
        created_at: '2026-03-12T13:00:01Z',
        data: {
          approval_id: 'approval-1',
          tool_call_id: 'call-1',
          tool_name: 'shell_exec',
          requested_action: "tool:shell_exec command='pwd' cwd=.",
          reason: 'shell_exec requires approval.',
          status: 'pending',
        },
        raw: {},
      });
    });

    await waitFor(() => {
      expect(result.current.liveRuns[0]?.status).toBe('awaiting_approval');
      expect(result.current.liveRuns[0]?.steps[0]?.title).toBe('Approval requested');
    });

    act(() => {
      capturedStreamOptions?.onEvent({
        id: 'evt-message-1',
        type: 'message.completed',
        session_id: 'session-1',
        task_id: 'task-1',
        task_run_id: 'run-1',
        created_at: '2026-03-12T13:00:02Z',
        data: {
          message: {
            id: 'message-2',
            role: 'assistant',
            content_text: 'Shell command approved and completed.',
            sequence_number: 2,
          },
        },
        raw: {},
      });
      capturedStreamOptions?.onEvent({
        id: 'evt-completed-1',
        type: 'execution.completed',
        session_id: 'session-1',
        task_id: 'task-1',
        task_run_id: 'run-1',
        created_at: '2026-03-12T13:00:03Z',
        data: {
          status: 'completed',
          started_at: '2026-03-12T13:00:00Z',
          finished_at: '2026-03-12T13:00:03Z',
        },
        raw: {},
      });
    });

    await waitFor(() => {
      expect(result.current.liveRuns[0]).toEqual(
        expect.objectContaining({
          status: 'completed',
          finalText: 'Shell command approved and completed.',
          assistantMessageId: 'message-2',
        }),
      );
    });
  });
});
