import {
  useCallback,
  useEffect,
  useState,
  type Dispatch,
  type SetStateAction,
} from 'react';

import { APP_VIEW_DETAILS, type AppView } from '../components/app-shell-layout';
import {
  approveApproval,
  activateCronJob,
  createCronJob,
  createSession,
  deleteCronJob,
  denyApproval,
  fetchActivityTimeline,
  fetchApprovals,
  fetchAgentConfig,
  fetchCronJobsDashboard,
  fetchOperationalSettings,
  fetchSessionMessages,
  fetchSessions,
  fetchToolCalls,
  fetchToolPermissions,
  getOperationalProviderLabel,
  pauseCronJob,
  resetAgentConfig,
  sendSessionMessage,
  updateAgentConfig,
  updateOperationalSettings,
  updateToolPermission,
  type ActivityTimelineItemRecord,
  type AgentConfigUpdate,
  type AgentRecord,
  type ApprovalRecord,
  type CronJobCreateInput,
  type CronJobRecord,
  type HeartbeatStatusRecord,
  type MessageRecord,
  type OperationalSettingsRecord,
  type OperationalSettingsUpdate,
  type SessionRecord,
  type TaskRunHistoryRecord,
  type ToolCallRecord,
  type ToolPermissionLevel,
  type ToolPermissionRecord,
} from '../lib/backend';

const emptyAgentDraft: AgentConfigUpdate = {
  name: '',
  description: '',
  identity_text: '',
  soul_text: '',
  user_context_text: '',
  policy_base_text: '',
  model_name: '',
};

const emptyOperationalDraft: OperationalSettingsUpdate = {
  provider: 'product_echo',
  model_name: 'product-echo/simple',
  workspace_root: '',
  max_iterations_per_execution: 2,
  daily_budget_usd: 10,
  monthly_budget_usd: 200,
  default_view: 'chat',
  activity_poll_seconds: 3,
  api_key: '',
  clear_api_key: false,
};

type PendingSetter = Dispatch<SetStateAction<boolean>>;

interface AsyncActionOptions {
  errorMessage: string;
  setPending?: PendingSetter;
  clearError?: boolean;
}

function toAgentDraft(agent: AgentRecord): AgentConfigUpdate {
  return {
    name: agent.name,
    description: agent.description || '',
    identity_text: agent.profile?.identity_text || '',
    soul_text: agent.profile?.soul_text || '',
    user_context_text: agent.profile?.user_context_text || '',
    policy_base_text: agent.profile?.policy_base_text || '',
    model_name: agent.profile?.model_name || '',
  };
}

function toOperationalDraft(
  settings: OperationalSettingsRecord,
): OperationalSettingsUpdate {
  return {
    provider: settings.provider,
    model_name: settings.model_name,
    workspace_root: settings.workspace_root,
    max_iterations_per_execution: settings.max_iterations_per_execution,
    daily_budget_usd: settings.daily_budget_usd,
    monthly_budget_usd: settings.monthly_budget_usd,
    default_view: settings.default_view,
    activity_poll_seconds: settings.activity_poll_seconds,
    api_key: '',
    clear_api_key: false,
  };
}

function toErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

export function useAppController() {
  const [view, setView] = useState<AppView>('chat');
  const [sessions, setSessions] = useState<SessionRecord[]>([]);
  const [activeSession, setActiveSession] = useState<SessionRecord | null>(
    null,
  );
  const [messages, setMessages] = useState<MessageRecord[]>([]);
  const [draft, setDraft] = useState('');
  const [agent, setAgent] = useState<AgentRecord | null>(null);
  const [agentDraft, setAgentDraft] =
    useState<AgentConfigUpdate>(emptyAgentDraft);
  const [operationalSettings, setOperationalSettings] =
    useState<OperationalSettingsRecord | null>(null);
  const [operationalDraft, setOperationalDraft] =
    useState<OperationalSettingsUpdate>(emptyOperationalDraft);
  const [isBootstrapping, setIsBootstrapping] = useState(true);
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);
  const [isCreatingSession, setIsCreatingSession] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [isLoadingAgent, setIsLoadingAgent] = useState(false);
  const [isSavingAgent, setIsSavingAgent] = useState(false);
  const [isResettingAgent, setIsResettingAgent] = useState(false);
  const [isLoadingOperationalSettings, setIsLoadingOperationalSettings] =
    useState(false);
  const [isSavingOperationalSettings, setIsSavingOperationalSettings] =
    useState(false);
  const [workspaceRoot, setWorkspaceRoot] = useState('');
  const [toolPermissions, setToolPermissions] = useState<
    ToolPermissionRecord[]
  >([]);
  const [toolCalls, setToolCalls] = useState<ToolCallRecord[]>([]);
  const [approvals, setApprovals] = useState<ApprovalRecord[]>([]);
  const [cronJobs, setCronJobs] = useState<CronJobRecord[]>([]);
  const [jobHistory, setJobHistory] = useState<TaskRunHistoryRecord[]>([]);
  const [heartbeat, setHeartbeat] = useState<HeartbeatStatusRecord | null>(
    null,
  );
  const [activityItems, setActivityItems] = useState<
    ActivityTimelineItemRecord[]
  >([]);
  const [activeApprovalId, setActiveApprovalId] = useState<string | null>(null);
  const [isLoadingTools, setIsLoadingTools] = useState(false);
  const [isLoadingApprovals, setIsLoadingApprovals] = useState(false);
  const [isLoadingJobs, setIsLoadingJobs] = useState(false);
  const [isLoadingActivity, setIsLoadingActivity] = useState(false);
  const [isUpdatingToolPermission, setIsUpdatingToolPermission] =
    useState(false);
  const [isActingOnApproval, setIsActingOnApproval] = useState(false);
  const [isCreatingJob, setIsCreatingJob] = useState(false);
  const [isMutatingJob, setIsMutatingJob] = useState(false);
  const [hasAppliedDefaultView, setHasAppliedDefaultView] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [isDesktop, setIsDesktop] = useState(() => {
    if (
      typeof window === 'undefined' ||
      typeof window.matchMedia !== 'function'
    ) {
      return true;
    }

    return window.matchMedia('(min-width: 1024px)').matches;
  });

  const runAsyncAction = useCallback(
    async <T>(
      action: () => Promise<T>,
      { clearError = true, setPending, errorMessage }: AsyncActionOptions,
    ): Promise<T | null> => {
      if (clearError) {
        setErrorMessage(null);
      }
      setPending?.(true);

      try {
        return await action();
      } catch (error: unknown) {
        setErrorMessage(toErrorMessage(error, errorMessage));
        return null;
      } finally {
        setPending?.(false);
      }
    },
    [],
  );

  const loadAgentConfig = useCallback(async () => {
    const response = await runAsyncAction(() => fetchAgentConfig(), {
      setPending: setIsLoadingAgent,
      errorMessage: 'Failed to load agent profile.',
    });
    if (!response) {
      return;
    }

    setAgent(response);
    setAgentDraft(toAgentDraft(response));
  }, [runAsyncAction]);

  const loadOperationalSettings = useCallback(async () => {
    const response = await runAsyncAction(() => fetchOperationalSettings(), {
      setPending: setIsLoadingOperationalSettings,
      errorMessage: 'Failed to load operational settings.',
    });
    if (!response) {
      return;
    }

    setOperationalSettings(response);
    setOperationalDraft(toOperationalDraft(response));
    setView((current) =>
      !hasAppliedDefaultView && current === 'chat'
        ? response.default_view
        : current,
    );
    setHasAppliedDefaultView(true);
  }, [hasAppliedDefaultView, runAsyncAction]);

  const loadSession = useCallback(
    async (session: SessionRecord) => {
      const response = await runAsyncAction(
        () => fetchSessionMessages(session.id),
        {
          setPending: setIsLoadingMessages,
          errorMessage: 'Failed to load session messages.',
        },
      );
      if (!response) {
        return;
      }

      setActiveSession(response.session);
      setMessages(response.items);
    },
    [runAsyncAction],
  );

  const loadTools = useCallback(async () => {
    const response = await runAsyncAction(
      async () => {
        const [permissionsResponse, callsResponse] = await Promise.all([
          fetchToolPermissions(),
          fetchToolCalls(),
        ]);
        return { permissionsResponse, callsResponse };
      },
      {
        setPending: setIsLoadingTools,
        errorMessage: 'Failed to load tool permissions.',
      },
    );
    if (!response) {
      return;
    }

    setWorkspaceRoot(response.permissionsResponse.workspace_root);
    setToolPermissions(response.permissionsResponse.items);
    setToolCalls(response.callsResponse.items);
  }, [runAsyncAction]);

  const loadApprovals = useCallback(async () => {
    const response = await runAsyncAction(() => fetchApprovals(), {
      setPending: setIsLoadingApprovals,
      errorMessage: 'Failed to load approvals inbox.',
    });
    if (!response) {
      return;
    }

    setApprovals(response.items);
    setActiveApprovalId((current) => {
      if (response.items.length === 0) {
        return null;
      }

      const stillExists = response.items.some((item) => item.id === current);
      return stillExists ? current : response.items[0].id;
    });
  }, [runAsyncAction]);

  const loadJobs = useCallback(async () => {
    const response = await runAsyncAction(() => fetchCronJobsDashboard(), {
      setPending: setIsLoadingJobs,
      errorMessage: 'Failed to load scheduler state.',
    });
    if (!response) {
      return;
    }

    setCronJobs(response.items);
    setJobHistory(response.history);
    setHeartbeat(response.heartbeat);
  }, [runAsyncAction]);

  const loadActivity = useCallback(async () => {
    const response = await runAsyncAction(() => fetchActivityTimeline(), {
      setPending: setIsLoadingActivity,
      errorMessage: 'Failed to load activity timeline.',
    });
    if (!response) {
      return;
    }

    setActivityItems(response.items);
  }, [runAsyncAction]);

  const bootstrap = useCallback(
    async (preferredSessionId?: string) => {
      const response = await runAsyncAction(() => fetchSessions(), {
        setPending: setIsBootstrapping,
        errorMessage: 'Failed to load chat sessions.',
      });
      if (!response) {
        return;
      }

      setSessions(response.items);

      const nextSession =
        response.items.find((item) => item.id === preferredSessionId) ||
        response.items[0] ||
        null;

      if (!nextSession) {
        setActiveSession(null);
        setMessages([]);
        return;
      }

      await loadSession(nextSession);
    },
    [loadSession, runAsyncAction],
  );

  const refreshJobsAndActivity = useCallback(async () => {
    await Promise.all([loadJobs(), loadActivity()]);
  }, [loadActivity, loadJobs]);

  const refreshExecutionContext = useCallback(
    async ({
      preferredSessionId,
      includeJobs = false,
    }: {
      preferredSessionId?: string;
      includeJobs?: boolean;
    } = {}) => {
      await bootstrap(preferredSessionId);
      await loadTools();
      await loadApprovals();

      if (includeJobs) {
        await refreshJobsAndActivity();
        return;
      }

      await loadActivity();
    },
    [bootstrap, loadActivity, loadApprovals, loadTools, refreshJobsAndActivity],
  );

  const adoptNewSession = useCallback((session: SessionRecord) => {
    setSessions((current) => [session, ...current]);
    setActiveSession(session);
    setMessages([]);
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

  useEffect(() => {
    void bootstrap();
    void loadAgentConfig();
    void loadOperationalSettings();
    void loadTools();
    void loadApprovals();
    void loadJobs();
    void loadActivity();
  }, [
    bootstrap,
    loadActivity,
    loadAgentConfig,
    loadApprovals,
    loadJobs,
    loadOperationalSettings,
    loadTools,
  ]);

  useEffect(() => {
    if (
      typeof window === 'undefined' ||
      typeof window.matchMedia !== 'function'
    ) {
      return undefined;
    }

    const media = window.matchMedia('(min-width: 1024px)');
    const sync = () => setIsDesktop(media.matches);

    sync();
    media.addEventListener('change', sync);

    return () => media.removeEventListener('change', sync);
  }, []);

  useEffect(() => {
    if (view !== 'jobs' && view !== 'activity') {
      return undefined;
    }

    const intervalMs = Math.max(
      (operationalSettings?.activity_poll_seconds || 3) * 1000,
      1000,
    );
    const intervalId = window.setInterval(() => {
      void refreshJobsAndActivity();
    }, intervalMs);

    return () => window.clearInterval(intervalId);
  }, [
    operationalSettings?.activity_poll_seconds,
    refreshJobsAndActivity,
    view,
  ]);

  async function handleCreateSession() {
    const created = await runAsyncAction(() => createSession('New Session'), {
      setPending: setIsCreatingSession,
      errorMessage: 'Failed to create session.',
    });
    if (!created) {
      return;
    }

    adoptNewSession(created);
    setDraft('');
    setView('chat');
    setMobileNavOpen(false);
  }

  async function handleSelectSession(sessionId: string) {
    if (sessionId === activeSession?.id) {
      setView('chat');
      setMobileNavOpen(false);
      return;
    }

    const session = sessions.find((item) => item.id === sessionId);
    if (!session) {
      return;
    }

    setView('chat');
    setMobileNavOpen(false);
    await loadSession(session);
  }

  async function handleSendMessage() {
    const trimmed = draft.trim();
    if (!trimmed) {
      setErrorMessage('Write a message before sending it to the agent.');
      return;
    }

    const session = await ensureSessionForSend();
    if (!session) {
      return;
    }

    const sent = await runAsyncAction(
      async () => {
        setDraft('');
        await sendSessionMessage(session.id, trimmed);
        await refreshExecutionContext({
          preferredSessionId: session.id,
          includeJobs: true,
        });
      },
      {
        setPending: setIsSending,
        errorMessage: 'Failed to send message.',
      },
    );

    if (sent === null) {
      setDraft(trimmed);
    }
  }

  function handleAgentDraftChange(
    field: keyof AgentConfigUpdate,
    value: string,
  ) {
    setAgentDraft((current) => ({ ...current, [field]: value }));
  }

  function handleOperationalDraftChange<
    K extends keyof OperationalSettingsUpdate,
  >(field: K, value: OperationalSettingsUpdate[K]) {
    setOperationalDraft((current) => ({ ...current, [field]: value }));
  }

  async function handleSaveAgentConfig() {
    if (
      !agentDraft.name.trim() ||
      !agentDraft.identity_text.trim() ||
      !agentDraft.soul_text.trim() ||
      !agentDraft.policy_base_text.trim() ||
      !agentDraft.model_name.trim()
    ) {
      setErrorMessage(
        'Name, identity, soul, policy base, and default model are required.',
      );
      return;
    }

    const saved = await runAsyncAction(
      () =>
        updateAgentConfig({
          name: agentDraft.name.trim(),
          description: agentDraft.description.trim(),
          identity_text: agentDraft.identity_text.trim(),
          soul_text: agentDraft.soul_text.trim(),
          user_context_text: agentDraft.user_context_text.trim(),
          policy_base_text: agentDraft.policy_base_text.trim(),
          model_name: agentDraft.model_name.trim(),
        }),
      {
        setPending: setIsSavingAgent,
        errorMessage: 'Failed to save agent profile.',
      },
    );
    if (!saved) {
      return;
    }

    setAgent(saved);
    setAgentDraft(toAgentDraft(saved));
  }

  async function handleResetAgentConfig() {
    const reset = await runAsyncAction(() => resetAgentConfig(), {
      setPending: setIsResettingAgent,
      errorMessage: 'Failed to restore agent defaults.',
    });
    if (!reset) {
      return;
    }

    setAgent(reset);
    setAgentDraft(toAgentDraft(reset));
  }

  async function handleSaveOperationalSettings() {
    if (
      !operationalDraft.model_name.trim() ||
      !operationalDraft.workspace_root.trim()
    ) {
      setErrorMessage('Provider model and workspace root are required.');
      return;
    }

    const saved = await runAsyncAction(
      () =>
        updateOperationalSettings({
          ...operationalDraft,
          model_name: operationalDraft.model_name.trim(),
          workspace_root: operationalDraft.workspace_root.trim(),
          api_key: operationalDraft.api_key?.trim() || null,
        }),
      {
        setPending: setIsSavingOperationalSettings,
        errorMessage: 'Failed to save operational settings.',
      },
    );
    if (!saved) {
      return;
    }

    setOperationalSettings(saved);
    setOperationalDraft(toOperationalDraft(saved));
    await Promise.all([loadAgentConfig(), loadTools()]);
  }

  async function handleChangeToolPermission(
    toolName: string,
    permissionLevel: ToolPermissionLevel,
  ) {
    const updated = await runAsyncAction(
      () => updateToolPermission(toolName, permissionLevel),
      {
        setPending: setIsUpdatingToolPermission,
        errorMessage: 'Failed to update tool permission.',
      },
    );
    if (!updated) {
      return;
    }

    setToolPermissions((current) =>
      current.map((item) => (item.id === updated.id ? updated : item)),
    );
  }

  async function handleApproveApproval(approvalId: string) {
    const response = await runAsyncAction(() => approveApproval(approvalId), {
      setPending: setIsActingOnApproval,
      errorMessage: 'Failed to approve action.',
    });
    if (!response) {
      return;
    }

    setView('chat');
    await refreshExecutionContext({
      preferredSessionId: response.approval.session_id || undefined,
    });
  }

  async function handleDenyApproval(approvalId: string) {
    const response = await runAsyncAction(() => denyApproval(approvalId), {
      setPending: setIsActingOnApproval,
      errorMessage: 'Failed to deny action.',
    });
    if (!response) {
      return;
    }

    setView('chat');
    await refreshExecutionContext({
      preferredSessionId: response.approval.session_id || undefined,
    });
  }

  async function handleCreateJob(payload: CronJobCreateInput) {
    if (!payload.name.trim() || !payload.schedule.trim()) {
      setErrorMessage('Job name and schedule are required.');
      return;
    }

    const created = await runAsyncAction(() => createCronJob(payload), {
      setPending: setIsCreatingJob,
      errorMessage: 'Failed to create scheduled job.',
    });
    if (!created) {
      return;
    }

    setView('jobs');
    await refreshJobsAndActivity();
  }

  async function handlePauseJob(jobId: string) {
    const paused = await runAsyncAction(() => pauseCronJob(jobId), {
      setPending: setIsMutatingJob,
      errorMessage: 'Failed to pause scheduled job.',
    });
    if (!paused) {
      return;
    }

    await refreshJobsAndActivity();
  }

  async function handleActivateJob(jobId: string) {
    const activated = await runAsyncAction(() => activateCronJob(jobId), {
      setPending: setIsMutatingJob,
      errorMessage: 'Failed to activate scheduled job.',
    });
    if (!activated) {
      return;
    }

    await refreshJobsAndActivity();
  }

  async function handleRemoveJob(jobId: string) {
    const removed = await runAsyncAction(() => deleteCronJob(jobId), {
      setPending: setIsMutatingJob,
      errorMessage: 'Failed to remove scheduled job.',
    });
    if (removed === null) {
      return;
    }

    await refreshJobsAndActivity();
  }

  async function handleRefreshCurrentView() {
    setErrorMessage(null);

    if (view === 'chat') {
      await bootstrap(activeSession?.id);
      return;
    }

    if (view === 'profile') {
      await loadAgentConfig();
      return;
    }

    if (view === 'settings') {
      await loadOperationalSettings();
      return;
    }

    if (view === 'tools') {
      await loadTools();
      return;
    }

    if (view === 'approvals') {
      await loadApprovals();
      return;
    }

    if (view === 'jobs') {
      await refreshJobsAndActivity();
      return;
    }

    await loadActivity();
  }

  const isComposerDisabled =
    isBootstrapping || isLoadingMessages || isCreatingSession || isSending;
  const isWorkspaceSyncing =
    isBootstrapping ||
    isLoadingAgent ||
    isLoadingTools ||
    isLoadingApprovals ||
    isLoadingJobs ||
    isLoadingActivity ||
    isLoadingOperationalSettings;
  const activeView = APP_VIEW_DETAILS[view];
  const pendingApprovalsCount = approvals.filter(
    (approval) => approval.status === 'pending',
  ).length;
  const activeJobsCount = cronJobs.filter(
    (job) => job.status === 'active',
  ).length;
  const providerLabel = getOperationalProviderLabel(
    operationalSettings?.provider || agent?.profile?.model_provider || 'product_echo',
  );
  const agentTitle = agent?.name || 'Nanobot Agent';

  const getViewCount = useCallback(
    (targetView: AppView): string | null => {
      if (targetView === 'chat') {
        return sessions.length ? String(sessions.length) : null;
      }

      if (targetView === 'approvals') {
        return pendingApprovalsCount ? String(pendingApprovalsCount) : null;
      }

      if (targetView === 'tools') {
        return toolPermissions.length ? String(toolPermissions.length) : null;
      }

      if (targetView === 'jobs') {
        return cronJobs.length ? String(cronJobs.length) : null;
      }

      if (targetView === 'activity') {
        return activityItems.length ? String(activityItems.length) : null;
      }

      return null;
    },
    [
      activityItems.length,
      cronJobs.length,
      pendingApprovalsCount,
      sessions.length,
      toolPermissions.length,
    ],
  );

  const navigateTo = useCallback((nextView: AppView) => {
    if (nextView === 'chat') {
      setActiveSession(null);
    }
    setView(nextView);
    setMobileNavOpen(false);
  }, []);

  return {
    activeApprovalId,
    activeJobsCount,
    activeSession,
    activeView,
    activityItems,
    agent,
    agentDraft,
    agentTitle,
    approvals,
    cronJobs,
    draft,
    errorMessage,
    getViewCount,
    handleActivateJob,
    handleAgentDraftChange,
    handleApproveApproval,
    handleChangeToolPermission,
    handleCreateJob,
    handleCreateSession,
    handleDenyApproval,
    handleOperationalDraftChange,
    handlePauseJob,
    handleRefreshCurrentView,
    handleRemoveJob,
    handleResetAgentConfig,
    handleSaveAgentConfig,
    handleSaveOperationalSettings,
    handleSelectSession,
    handleSendMessage,
    heartbeat,
    isActingOnApproval,
    isBootstrapping,
    isComposerDisabled,
    isCreatingJob,
    isCreatingSession,
    isDesktop,
    isLoadingActivity,
    isLoadingAgent,
    isLoadingApprovals,
    isLoadingJobs,
    isLoadingMessages,
    isLoadingOperationalSettings,
    isLoadingTools,
    isMutatingJob,
    isResettingAgent,
    isSavingAgent,
    isSavingOperationalSettings,
    isSending,
    isUpdatingToolPermission,
    isWorkspaceSyncing,
    jobHistory,
    messages,
    mobileNavOpen,
    navigateTo,
    operationalDraft,
    operationalSettings,
    pendingApprovalsCount,
    providerLabel,
    sessions,
    setActiveApprovalId,
    setDraft,
    setErrorMessage,
    setMobileNavOpen,
    toolCalls,
    toolPermissions,
    view,
    workspaceRoot,
  };
}
