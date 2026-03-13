import { act, renderHook, waitFor } from '@testing-library/react';
import type { Dispatch, SetStateAction } from 'react';
import { vi } from 'vitest';

import type { SessionExecutionStreamOptions } from '../../lib/backend/sessionExecutionStream';
import { useChatController } from './useChatController';

const mockCancelSessionSubagent = vi.fn();
const mockCreateSession = vi.fn();
const mockFetchMemoryRecallDetail = vi.fn();
const mockFetchSessionMessages = vi.fn();
const mockFetchSessionRecallSummaries = vi.fn();
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
  fetchSessionSubagents: (sessionId: string) => mockFetchSessionSubagents(sessionId),
  sendSessionMessageAsync: (sessionId: string, content: string) =>
    mockSendSessionMessageAsync(sessionId, content),
}));

vi.mock('../../lib/backend/memory', () => ({
  fetchMemoryRecallDetail: (messageId: string) => mockFetchMemoryRecallDetail(messageId),
  fetchSessionRecallSummaries: (sessionId: string) =>
    mockFetchSessionRecallSummaries(sessionId),
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
    } catch {
      return null;
    } finally {
      options.setPending?.(false);
    }
  };
}

describe('useChatController', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    capturedStreamOptions = null;
    mockFetchSessionRecallSummaries.mockResolvedValue({ items: [] });
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
      expect(mockFetchSessionRecallSummaries).toHaveBeenCalledWith('session-1');
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

  it('opens recall detail for an assistant message', async () => {
    const runAsyncAction = createRunAsyncAction();
    const setErrorMessage = vi.fn();

    mockFetchMemoryRecallDetail.mockResolvedValue({
      assistant_message_id: 'message-2',
      session_id: 'session-1',
      created_at: '2026-03-08T12:01:00Z',
      reason_summary: '1 memory item injected for recall.',
      items: [],
    });

    const { result } = renderHook(() =>
      useChatController({
        runAsyncAction,
        setErrorMessage,
      }),
    );

    await act(async () => {
      await result.current.handleOpenRecall('message-2');
    });

    await waitFor(() => {
      expect(mockFetchMemoryRecallDetail).toHaveBeenCalledWith('message-2');
      expect(result.current.isRecallSheetOpen).toBe(true);
      expect(result.current.activeRecall?.assistant_message_id).toBe('message-2');
    });
  });
});
