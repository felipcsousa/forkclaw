import { useCallback, useState } from 'react';

import {
  cancelSessionSubagent,
  createSession,
  fetchSessionMessages,
  fetchSessions,
  fetchSessionSubagent,
  fetchSessionSubagentMessages,
  fetchSessionSubagents,
  sendSessionMessage,
  type MessageRecord,
  type SessionRecord,
  type SessionSubagentsListResponse,
  type SubagentSessionRecord,
} from '../../lib/backend/sessions';
import type { PendingSetter, RunAsyncAction } from './shared';
import { toErrorMessage } from './shared';

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

  const clearActiveSessionState = useCallback(() => {
    setActiveSession(null);
    setMessages([]);
    setSubagents([]);
    setActiveSubagent(null);
    setActiveSubagentMessages([]);
    setActiveSubagentParentSessionId(null);
    setSubagentsErrorMessage(null);
    setSubagentDetailErrorMessage(null);
    setIsSubagentSheetOpen(false);
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

  const loadSession = useCallback(
    async (
      session: SessionRecord,
      { silent = false }: { silent?: boolean } = {},
    ) => {
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
        await loadSubagents(response.session.id, { silent });
      } else {
        setSubagents([]);
        setSubagentsErrorMessage(null);
      }
      return response;
    },
    [loadSubagents, runAsyncAction],
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
    async (preferredSessionId?: string): Promise<SessionRecord | null> => {
      const nextSession = await refreshSessionsAndSelection(preferredSessionId);
      if (!nextSession) {
        return null;
      }

      await loadSession(nextSession, { silent: true });
      return nextSession;
    },
    [loadSession, refreshSessionsAndSelection],
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

      const sent = await runAsyncAction(
        async () => {
          setDraft('');
          await sendSessionMessage(session.id, trimmed);
          await refreshSessionContext(session.id);
          if (afterSend) {
            await afterSend(session.id);
          }
          return session;
        },
        {
          setPending: setIsSending,
          errorMessage: 'Failed to send message.',
        },
      );

      if (sent === null) {
        setDraft(trimmed);
        return null;
      }

      return sent;
    },
    [draft, ensureSessionForSend, refreshSessionContext, runAsyncAction, setErrorMessage],
  );

  const activeSubagentIndex = activeSubagent
    ? subagents.findIndex((item) => item.id === activeSubagent.id)
    : -1;

  return {
    activeSession,
    activeSubagent,
    activeSubagentHasNext:
      activeSubagentIndex >= 0 && activeSubagentIndex < subagents.length - 1,
    activeSubagentHasPrevious: activeSubagentIndex > 0,
    activeSubagentMessages,
    activeSubagentParentSessionId,
    bootstrap,
    cancellingSubagentId,
    clearActiveSessionState,
    draft,
    handleCancelSubagent,
    handleCloseSubagent,
    handleCreateSession,
    handleOpenNextSubagent,
    handleOpenPreviousSubagent,
    handleOpenSubagent,
    handleReturnToParentSession,
    handleSelectSession,
    handleSendMessage,
    isBootstrapping,
    isCreatingSession,
    isLoadingMessages,
    isLoadingSubagentDetail,
    isLoadingSubagentMessages,
    isLoadingSubagents,
    isSending,
    isSubagentSheetOpen,
    loadSession,
    loadSubagentDetail,
    loadSubagentMessages,
    loadSubagents,
    messages,
    refreshSessionContext,
    refreshSessionsAndSelection,
    sessions,
    setDraft,
    setIsSubagentSheetOpen,
    subagentDetailErrorMessage,
    subagents,
    subagentsErrorMessage,
  };
}
