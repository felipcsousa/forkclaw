import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from 'react';

import {
  cancelSessionSubagent,
  createSession,
  fetchSessionMessages,
  fetchSessions,
  fetchSessionSubagent,
  fetchSessionSubagentMessages,
  fetchSessionSubagents,
  sendSessionMessageAsync,
  type AgentExecutionAcceptedResponse,
  type MessageRecord,
  type SessionRecord,
  type SessionMessagesResponse,
  type SessionSubagentsListResponse,
  type SubagentSessionRecord,
} from '../../lib/backend/sessions';
import {
  connectSessionExecutionStream,
  type SessionExecutionEvent,
  fetchMemoryRecallDetail,
  fetchSessionRecallSummaries,
  type MemoryRecallDetailRecord,
  type SessionRecallSummaryRecord,
} from '../../lib/backend/memory';
import {
  type SessionExecutionEvent,
  connectSessionExecutionStream,
} from '../../lib/backend/sessionExecutionStream';
import type { PendingSetter, RunAsyncAction } from './shared';
import {
  buildChatTimelineItems,
  chatExecutionStateReducer,
  createInitialChatExecutionState,
} from './chatExecutionState';
import { toErrorMessage } from './shared';

type ExecutionStreamStatus =
  | 'idle'
  | 'connecting'
  | 'connected'
  | 'reconnecting'
  | 'disconnected';

export function useChatController({
  runAsyncAction,
  setErrorMessage,
}: {
  runAsyncAction: RunAsyncAction;
  setErrorMessage: (value: string | null) => void;
}) {
  const [sessions, setSessions] = useState<SessionRecord[]>([]);
  const [activeSession, setActiveSession] = useState<SessionRecord | null>(null);
  const [messages, setMessages] = useState<MessageRecord[]>([]);
  const [subagents, setSubagents] = useState<SubagentSessionRecord[]>([]);
  const [activeSubagent, setActiveSubagent] =
    useState<SubagentSessionRecord | null>(null);
  const [activeSubagentMessages, setActiveSubagentMessages] = useState<
    MessageRecord[]
  >([]);
  const [activeSubagentParentSessionId, setActiveSubagentParentSessionId] =
    useState<string | null>(null);
  const [isSubagentSheetOpen, setIsSubagentSheetOpen] = useState(false);
  const [draft, setDraft] = useState('');
  const [isBootstrapping, setIsBootstrapping] = useState(true);
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);
  const [isLoadingSubagents, setIsLoadingSubagents] = useState(false);
  const [isLoadingSubagentDetail, setIsLoadingSubagentDetail] = useState(false);
  const [isLoadingSubagentMessages, setIsLoadingSubagentMessages] =
    useState(false);
  const [isCreatingSession, setIsCreatingSession] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [cancellingSubagentId, setCancellingSubagentId] = useState<
    string | null
  >(null);
  const [subagentsErrorMessage, setSubagentsErrorMessage] = useState<
    string | null
  >(null);
  const [subagentDetailErrorMessage, setSubagentDetailErrorMessage] =
    useState<string | null>(null);
  const [executionStreamStatus, setExecutionStreamStatus] =
    useState<ExecutionStreamStatus>('idle');
  const [executionStreamErrorMessage, setExecutionStreamErrorMessage] =
    useState<string | null>(null);
  const [executionStreamReconnectAttempt, setExecutionStreamReconnectAttempt] =
    useState(0);
  const [runsState, dispatchRuns] = useReducer(
    chatExecutionStateReducer,
    undefined,
    createInitialChatExecutionState,
  );
  const executionStreamReadyRef = useRef(false);
  const activeSessionId = activeSession?.id || null;
  const activeSessionKind = activeSession?.kind || null;
  const [sessionRecallSummaries, setSessionRecallSummaries] = useState<
    SessionRecallSummaryRecord[]
  >([]);
  const [activeRecall, setActiveRecall] = useState<MemoryRecallDetailRecord | null>(
    null,
  );
  const [isRecallSheetOpen, setIsRecallSheetOpen] = useState(false);
  const [isLoadingSessionRecallSummaries, setIsLoadingSessionRecallSummaries] =
    useState(false);
  const [isLoadingRecallDetail, setIsLoadingRecallDetail] = useState(false);
  const [recallDetailErrorMessage, setRecallDetailErrorMessage] = useState<
    string | null
  >(null);

  const clearActiveSessionState = useCallback(() => {
    setActiveSession(null);
    setMessages([]);
    setSubagents([]);
    setActiveSubagent(null);
    setActiveSubagentMessages([]);
    setActiveSubagentParentSessionId(null);
    setSubagentsErrorMessage(null);
    setSubagentDetailErrorMessage(null);
    setSessionRecallSummaries([]);
    setActiveRecall(null);
    setRecallDetailErrorMessage(null);
    setIsRecallSheetOpen(false);
    setIsSubagentSheetOpen(false);
    setExecutionStreamStatus('idle');
    setExecutionStreamErrorMessage(null);
    setExecutionStreamReconnectAttempt(0);
    executionStreamReadyRef.current = false;
  }, []);

  const loadSessionsIndex = useCallback(
    async ({
      setPending,
    }: {
      setPending?: PendingSetter;
    } = {}): Promise<SessionRecord[] | null> => {
      const response = await runAsyncAction(() => fetchSessions(true), {
        setPending,
        errorMessage: 'Failed to load chat sessions.',
      });
      if (!response) {
        return null;
      }

      setSessions(response.items);
      return response.items;
    },
    [runAsyncAction],
  );

  const loadSubagents = useCallback(
    async (
      sessionId: string,
      { silent = false }: { silent?: boolean } = {},
    ): Promise<SessionSubagentsListResponse | null> => {
      if (!silent) {
        setIsLoadingSubagents(true);
      }
      setSubagentsErrorMessage(null);

      try {
        const response = await fetchSessionSubagents(sessionId);
        setSubagents(response.items);
        return response;
      } catch (error: unknown) {
        setSubagents([]);
        setSubagentsErrorMessage(
          toErrorMessage(error, 'Failed to load child sessions.'),
        );
        return null;
      } finally {
        if (!silent) {
          setIsLoadingSubagents(false);
        }
      }
    },
    [],
  );

  const loadSessionRecallSummaries = useCallback(
    async (
      sessionId: string,
      { silent = false }: { silent?: boolean } = {},
    ) => {
      if (!silent) {
        setIsLoadingSessionRecallSummaries(true);
      }
      setRecallDetailErrorMessage(null);

      try {
        const response = await fetchSessionRecallSummaries(sessionId);
        setSessionRecallSummaries(response.items);
        return response;
      } catch (error: unknown) {
        setSessionRecallSummaries([]);
        setRecallDetailErrorMessage(
          toErrorMessage(error, 'Failed to load memory recall summaries.'),
        );
        return null;
      } finally {
        if (!silent) {
          setIsLoadingSessionRecallSummaries(false);
        }
      }
    },
    [],
  );

  const loadSession = useCallback(
    async (
      session: SessionRecord,
      { silent = false }: { silent?: boolean } = {},
    ): Promise<SessionMessagesResponse | null> => {
      const response = await runAsyncAction(
        () => fetchSessionMessages(session.id),
        {
          setPending: silent ? undefined : setIsLoadingMessages,
          errorMessage: 'Failed to load session messages.',
        },
      );
      if (!response) {
        return null;
      }

      setActiveSession(response.session);
      setMessages(response.items);

      if (response.session.kind === 'main') {
        await Promise.all([
          loadSubagents(response.session.id, { silent }),
          loadSessionRecallSummaries(response.session.id, { silent }),
        ]);
      } else {
        setSubagents([]);
        setSubagentsErrorMessage(null);
        setSessionRecallSummaries([]);
      }
      return response;
    },
    [loadSessionRecallSummaries, loadSubagents, runAsyncAction],
  );

  const loadSubagentDetail = useCallback(
    async (
      parentSessionId: string,
      childSessionId: string,
      { silent = false }: { silent?: boolean } = {},
    ) => {
      if (!silent) {
        setIsLoadingSubagentDetail(true);
      }
      setSubagentDetailErrorMessage(null);

      try {
        const response = await fetchSessionSubagent(parentSessionId, childSessionId);
        setActiveSubagent(response);
        setActiveSubagentParentSessionId(parentSessionId);
        return response;
      } catch (error: unknown) {
        setSubagentDetailErrorMessage(
          toErrorMessage(error, 'Failed to load child session details.'),
        );
        return null;
      } finally {
        if (!silent) {
          setIsLoadingSubagentDetail(false);
        }
      }
    },
    [],
  );

  const loadSubagentMessages = useCallback(
    async (
      parentSessionId: string,
      childSessionId: string,
      { silent = false }: { silent?: boolean } = {},
    ) => {
      if (!silent) {
        setIsLoadingSubagentMessages(true);
      }
      setSubagentDetailErrorMessage(null);

      try {
        const response = await fetchSessionSubagentMessages(
          parentSessionId,
          childSessionId,
        );
        setActiveSubagentMessages(response.items);
        return response;
      } catch (error: unknown) {
        setSubagentDetailErrorMessage(
          toErrorMessage(error, 'Failed to load child session transcript.'),
        );
        return null;
      } finally {
        if (!silent) {
          setIsLoadingSubagentMessages(false);
        }
      }
    },
    [],
  );

  const resolveNextSession = useCallback(
    (
      items: SessionRecord[],
      preferredSessionId?: string,
    ): SessionRecord | null =>
      items.find((item) => item.id === preferredSessionId) ||
      items.find((item) => item.id === activeSession?.id) ||
      items[0] ||
      null,
    [activeSession?.id],
  );

  const bootstrap = useCallback(
    async (preferredSessionId?: string) => {
      const items = await loadSessionsIndex({ setPending: setIsBootstrapping });
      if (!items) {
        return null;
      }

      const nextSession = resolveNextSession(items, preferredSessionId);
      if (!nextSession) {
        clearActiveSessionState();
        return null;
      }

      await loadSession(nextSession);
      return nextSession;
    },
    [clearActiveSessionState, loadSession, loadSessionsIndex, resolveNextSession],
  );

  const refreshSessionsAndSelection = useCallback(
    async (preferredSessionId?: string): Promise<SessionRecord | null> => {
      const items = await loadSessionsIndex();
      if (!items) {
        return null;
      }

      const nextSession = resolveNextSession(items, preferredSessionId);
      if (!nextSession) {
        clearActiveSessionState();
        return null;
      }

      return nextSession;
    },
    [clearActiveSessionState, loadSessionsIndex, resolveNextSession],
  );

  const refreshSessionContext = useCallback(
    async (preferredSessionId?: string): Promise<SessionMessagesResponse | null> => {
      const nextSession = await refreshSessionsAndSelection(preferredSessionId);
      if (!nextSession) {
        return null;
      }

      return loadSession(nextSession, { silent: true });
    },
    [loadSession, refreshSessionsAndSelection],
  );

  const refreshSessionIndexOnly = useCallback(
    async (preferredSessionId?: string) => {
      await refreshSessionsAndSelection(preferredSessionId);
    },
    [refreshSessionsAndSelection],
  );

  const adoptNewSession = useCallback((session: SessionRecord) => {
    setSessions((current) => [session, ...current]);
    setActiveSession(session);
    setMessages([]);
    setSubagents([]);
    setActiveSubagent(null);
    setActiveSubagentMessages([]);
    setActiveSubagentParentSessionId(null);
    setSubagentsErrorMessage(null);
    setSubagentDetailErrorMessage(null);
    setIsSubagentSheetOpen(false);
  }, []);

  const ensureSessionForSend = useCallback(async () => {
    if (activeSession) {
      return activeSession;
    }

    const created = await runAsyncAction(() => createSession('New Session'), {
      setPending: setIsCreatingSession,
      errorMessage: 'Failed to create session.',
    });
    if (!created) {
      return null;
    }

    adoptNewSession(created);
    return created;
  }, [activeSession, adoptNewSession, runAsyncAction]);

  const handleCreateSession = useCallback(async () => {
    const created = await runAsyncAction(() => createSession('New Session'), {
      setPending: setIsCreatingSession,
      errorMessage: 'Failed to create session.',
    });
    if (!created) {
      return null;
    }

    adoptNewSession(created);
    setDraft('');
    return created;
  }, [adoptNewSession, runAsyncAction]);

  const handleSelectSession = useCallback(
    async (sessionId: string) => {
      if (sessionId === activeSession?.id) {
        return activeSession;
      }

      const session = sessions.find((item) => item.id === sessionId);
      if (!session) {
        return null;
      }

      setActiveSubagent(null);
      setActiveSubagentMessages([]);
      setActiveSubagentParentSessionId(null);
      setSubagentDetailErrorMessage(null);
      setActiveRecall(null);
      setRecallDetailErrorMessage(null);
      setIsRecallSheetOpen(false);
      setIsSubagentSheetOpen(false);
      await loadSession(session);
      return session;
    },
    [activeSession, loadSession, sessions],
  );

  const handleOpenSubagent = useCallback(
    async (parentSessionId: string, childSessionId: string) => {
      if (!parentSessionId) {
        setSubagentDetailErrorMessage(
          'Parent session is missing for this child session.',
        );
        return null;
      }

      const parentSession = sessions.find((item) => item.id === parentSessionId);
      if (parentSession && parentSession.id !== activeSession?.id) {
        await loadSession(parentSession, { silent: true });
      }

      setIsSubagentSheetOpen(true);
      await Promise.all([
        loadSubagentDetail(parentSessionId, childSessionId),
        loadSubagentMessages(parentSessionId, childSessionId),
      ]);
      return childSessionId;
    },
    [
      activeSession?.id,
      loadSession,
      loadSubagentDetail,
      loadSubagentMessages,
      sessions,
    ],
  );

  const handleCloseSubagent = useCallback(() => {
    setIsSubagentSheetOpen(false);
    setSubagentDetailErrorMessage(null);
  }, []);

  const handleOpenRecall = useCallback(async (assistantMessageId: string) => {
    setRecallDetailErrorMessage(null);
    setIsRecallSheetOpen(true);
    try {
      setIsLoadingRecallDetail(true);
      const response = await fetchMemoryRecallDetail(assistantMessageId);
      setActiveRecall(response);
      return response;
    } catch (error: unknown) {
      setActiveRecall(null);
      setRecallDetailErrorMessage(
        toErrorMessage(error, 'Failed to load memory recall detail.'),
      );
      return null;
    } finally {
      setIsLoadingRecallDetail(false);
    }
  }, []);

  const handleCloseRecall = useCallback(() => {
    setIsRecallSheetOpen(false);
    setRecallDetailErrorMessage(null);
  }, []);

  const handleCancelSubagent = useCallback(
    async (
      parentSessionId: string,
      childSessionId: string,
      afterCancel?: () => Promise<void>,
    ) => {
      setCancellingSubagentId(childSessionId);
      setSubagentDetailErrorMessage(null);

      try {
        await cancelSessionSubagent(parentSessionId, childSessionId);
        await loadSubagents(parentSessionId, { silent: true });
        if (isSubagentSheetOpen && activeSubagent?.id === childSessionId) {
          await Promise.all([
            loadSubagentDetail(parentSessionId, childSessionId, { silent: true }),
            loadSubagentMessages(parentSessionId, childSessionId, { silent: true }),
          ]);
        }
        if (afterCancel) {
          await afterCancel();
        }
        return true;
      } catch (error: unknown) {
        setSubagentDetailErrorMessage(
          toErrorMessage(error, 'Failed to cancel child session.'),
        );
        return false;
      } finally {
        setCancellingSubagentId(null);
      }
    },
    [
      activeSubagent?.id,
      isSubagentSheetOpen,
      loadSubagentDetail,
      loadSubagentMessages,
      loadSubagents,
    ],
  );

  const handleReturnToParentSession = useCallback(
    async (parentSessionId: string) => {
      handleCloseSubagent();
      if (parentSessionId && parentSessionId !== activeSession?.id) {
        const parentSession = sessions.find((item) => item.id === parentSessionId);
        if (parentSession) {
          await loadSession(parentSession, { silent: true });
        }
      }
    },
    [activeSession?.id, handleCloseSubagent, loadSession, sessions],
  );

  const handleOpenPreviousSubagent = useCallback(async () => {
    if (!activeSubagent || !activeSubagentParentSessionId) {
      return null;
    }
    const currentIndex = subagents.findIndex((item) => item.id === activeSubagent.id);
    if (currentIndex <= 0) {
      return null;
    }
    const previous = subagents[currentIndex - 1];
    await handleOpenSubagent(activeSubagentParentSessionId, previous.id);
    return previous.id;
  }, [
    activeSubagent,
    activeSubagentParentSessionId,
    handleOpenSubagent,
    subagents,
  ]);

  const handleOpenNextSubagent = useCallback(async () => {
    if (!activeSubagent || !activeSubagentParentSessionId) {
      return null;
    }
    const currentIndex = subagents.findIndex((item) => item.id === activeSubagent.id);
    if (currentIndex < 0 || currentIndex >= subagents.length - 1) {
      return null;
    }
    const next = subagents[currentIndex + 1];
    await handleOpenSubagent(activeSubagentParentSessionId, next.id);
    return next.id;
  }, [activeSubagent, activeSubagentParentSessionId, handleOpenSubagent, subagents]);

  const handleExecutionEvent = useCallback(
    (event: SessionExecutionEvent) => {
      dispatchRuns({
        type: 'run/event-received',
        sessionId: event.session_id,
        event,
      });

      if (event.type.startsWith('subagent.')) {
        void loadSubagents(event.session_id, { silent: true });
      }

      const isTerminalEvent =
        event.type === 'message.completed' ||
        event.type === 'execution.completed' ||
        event.type === 'execution.failed';
      if (!isTerminalEvent || !executionStreamReadyRef.current) {
        return;
      }

      void refreshSessionIndexOnly(event.session_id);

      if (event.type === 'message.completed' && event.data.message.content_text) {
        return;
      }

      void refreshSessionContext(event.session_id);
    },
    [
      loadSubagents,
      refreshSessionContext,
      refreshSessionIndexOnly,
    ],
  );

  useEffect(() => {
    if (!activeSessionId || activeSessionKind !== 'main') {
      setExecutionStreamStatus('idle');
      setExecutionStreamErrorMessage(null);
      setExecutionStreamReconnectAttempt(0);
      executionStreamReadyRef.current = false;
      return undefined;
    }

    executionStreamReadyRef.current = false;
    setExecutionStreamStatus('connecting');
    setExecutionStreamErrorMessage(null);
    setExecutionStreamReconnectAttempt(0);

    const connection = connectSessionExecutionStream({
      sessionId: activeSessionId,
      onOpen: () => {
        setExecutionStreamStatus('connected');
        setExecutionStreamErrorMessage(null);
        setExecutionStreamReconnectAttempt(0);
      },
      onEvent: handleExecutionEvent,
      onReady: () => {
        executionStreamReadyRef.current = true;
      },
      onError: (error) => {
        executionStreamReadyRef.current = false;
        setExecutionStreamStatus('disconnected');
        setExecutionStreamErrorMessage(error.message);
      },
      onDisconnect: () => {
        executionStreamReadyRef.current = false;
        setExecutionStreamStatus('disconnected');
      },
      onReconnect: (attempt) => {
        executionStreamReadyRef.current = false;
        setExecutionStreamStatus('reconnecting');
        setExecutionStreamReconnectAttempt(attempt);
      },
    });

    return () => {
      connection.close();
    };
  }, [activeSessionId, activeSessionKind, handleExecutionEvent]);

  const handleSendMessage = useCallback(
    async (afterSend?: (sessionId: string) => Promise<void>) => {
      const trimmed = draft.trim();
      if (!trimmed) {
        setErrorMessage('Write a message before sending it to the agent.');
        return null;
      }

      const session = await ensureSessionForSend();
      if (!session) {
        return null;
      }

      const localRunId = `optimistic:${session.id}:${Date.now()}`;
      dispatchRuns({
        type: 'run/optimistic-created',
        sessionId: session.id,
        localRunId,
        prompt: trimmed,
        createdAt: new Date().toISOString(),
      });

      setDraft('');
      const response = (await runAsyncAction(
        async (): Promise<Partial<AgentExecutionAcceptedResponse> | undefined> =>
          (await sendSessionMessageAsync(
            session.id,
            trimmed,
          )) as Partial<AgentExecutionAcceptedResponse> | undefined,
        {
          setPending: setIsSending,
          errorMessage: 'Failed to send message.',
        },
      )) as Partial<AgentExecutionAcceptedResponse> | null;

      if (response === null) {
        dispatchRuns({
          type: 'run/optimistic-discarded',
          sessionId: session.id,
          localRunId,
        });
        setDraft(trimmed);
        return null;
      }

      dispatchRuns({
        type: 'run/response-bound',
        sessionId: session.id,
        localRunId,
        response,
      });

      try {
        const refreshed = await refreshSessionContext(session.id);
        if (refreshed === null) {
          setErrorMessage('Message sent, but failed to refresh session context.');
        }
      } catch (error) {
        setErrorMessage(
          toErrorMessage(error, 'Message sent, but failed to refresh session context.'),
        );
      }

      if (afterSend) {
        try {
          await afterSend(session.id);
        } catch (error) {
          setErrorMessage(
            toErrorMessage(error, 'Message sent, but failed to refresh related views.'),
          );
        }
      }

      return session;
    },
    [draft, ensureSessionForSend, refreshSessionContext, runAsyncAction, setErrorMessage],
  );

  const activeSubagentIndex = activeSubagent
    ? subagents.findIndex((item) => item.id === activeSubagent.id)
    : -1;
  const timelineItems = useMemo(
    () =>
      buildChatTimelineItems({
        activeSessionId: activeSession?.id || null,
        messages,
        runsState,
        subagents,
      }),
    [activeSession?.id, messages, runsState, subagents],
  );
  const liveRuns = useMemo(() => {
    if (!activeSession) {
      return [];
    }

    const runIds = runsState.sessionRunIds[activeSession.id] || [];
    return runIds
      .map((runId) => runsState.runsById[runId])
      .filter((run): run is NonNullable<typeof run> => Boolean(run));
  }, [activeSession, runsState.runsById, runsState.sessionRunIds]);
  const hasActiveLiveRuns = liveRuns.some(
    (run) =>
      run.status === 'connecting' ||
      run.status === 'running' ||
      run.status === 'awaiting_approval' ||
      run.status === 'disconnected',
  );

  return {
    activeSession,
    activeSubagent,
    activeSubagentHasNext:
      activeSubagentIndex >= 0 && activeSubagentIndex < subagents.length - 1,
    activeSubagentHasPrevious: activeSubagentIndex > 0,
    activeSubagentMessages,
    activeSubagentParentSessionId,
    activeRecall,
    bootstrap,
    cancellingSubagentId,
    clearActiveSessionState,
    draft,
    executionStreamErrorMessage,
    executionStreamReconnectAttempt,
    executionStreamStatus,
    hasActiveLiveRuns,
    handleCancelSubagent,
    handleCloseRecall,
    handleCloseSubagent,
    handleCreateSession,
    handleOpenNextSubagent,
    handleOpenRecall,
    handleOpenPreviousSubagent,
    handleOpenSubagent,
    handleReturnToParentSession,
    handleSelectSession,
    handleSendMessage,
    isBootstrapping,
    isCreatingSession,
    isLoadingMessages,
    isLoadingRecallDetail,
    isLoadingSessionRecallSummaries,
    isLoadingSubagentDetail,
    isLoadingSubagentMessages,
    isLoadingSubagents,
    isRecallSheetOpen,
    isSending,
    isSubagentSheetOpen,
    liveRuns,
    loadSession,
    loadSessionRecallSummaries,
    loadSubagentDetail,
    loadSubagentMessages,
    loadSubagents,
    messages,
    recallDetailErrorMessage,
    refreshSessionContext,
    refreshSessionsAndSelection,
    sessions,
    sessionRecallSummaries,
    setDraft,
    setIsRecallSheetOpen,
    setIsSubagentSheetOpen,
    shouldPollActiveSession:
      Boolean(activeSession) &&
      hasActiveLiveRuns &&
      executionStreamStatus !== 'connected',
    subagentDetailErrorMessage,
    subagents,
    subagentsErrorMessage,
    timelineItems,
  };
}
