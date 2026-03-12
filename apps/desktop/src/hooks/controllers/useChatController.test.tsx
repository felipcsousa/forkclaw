import { act, renderHook, waitFor } from '@testing-library/react';
import type { Dispatch, SetStateAction } from 'react';
import { vi } from 'vitest';

import { useChatController } from './useChatController';

const mockCancelSessionSubagent = vi.fn();
const mockCreateSession = vi.fn();
const mockFetchSessionMessages = vi.fn();
const mockFetchSessions = vi.fn();
const mockFetchSessionSubagent = vi.fn();
const mockFetchSessionSubagentMessages = vi.fn();
const mockFetchSessionSubagents = vi.fn();
const mockSendSessionMessage = vi.fn();

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
  sendSessionMessage: (sessionId: string, content: string) =>
    mockSendSessionMessage(sessionId, content),
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
  });

  it('creates a session on first send and refreshes the active chat context', async () => {
    const session = {
      id: 'session-1',
      title: 'New Session',
      kind: 'main',
    };

    mockCreateSession.mockResolvedValue(session);
    mockSendSessionMessage.mockResolvedValue(undefined);
    mockFetchSessions.mockResolvedValue({ items: [session] });
    mockFetchSessionMessages.mockResolvedValue({ session, items: [] });
    mockFetchSessionSubagents.mockResolvedValue({ items: [] });

    const { result } = renderHook(() =>
      useChatController({
        runAsyncAction: createRunAsyncAction(),
        setErrorMessage: vi.fn(),
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
      expect(mockSendSessionMessage).toHaveBeenCalledWith(
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
});
