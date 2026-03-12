import { useCallback, useEffect, useRef, useState } from 'react';

import { type AppView } from '../components/app-shell-layout';
import { getOperationalProviderLabel } from '../lib/backend/settings';
import { useActivityController } from './controllers/useActivityController';
import { useAgentProfileController } from './controllers/useAgentProfileController';
import { useApprovalsController } from './controllers/useApprovalsController';
import { useChatController } from './controllers/useChatController';
import { useJobsController } from './controllers/useJobsController';
import { useOperationalSettingsController } from './controllers/useOperationalSettingsController';
import { useShellController } from './controllers/useShellController';
import {
  type AsyncActionOptions,
  toErrorMessage,
} from './controllers/shared';
import { useToolingController } from './controllers/useToolingController';

export function useAppController() {
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const hasAppliedDefaultViewRef = useRef(false);

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

  const chat = useChatController({ runAsyncAction, setErrorMessage });
  const shell = useShellController({
    onNavigateToChat: chat.clearActiveSessionState,
  });
  const activity = useActivityController({ runAsyncAction });
  const agentProfile = useAgentProfileController({
    runAsyncAction,
    setErrorMessage,
  });
  const operationalSettings = useOperationalSettingsController({
    runAsyncAction,
    setErrorMessage,
  });
  const tooling = useToolingController({ runAsyncAction });
  const approvals = useApprovalsController({ runAsyncAction });
  const jobs = useJobsController({ runAsyncAction, setErrorMessage });
  const { setMobileNavOpen, setView, view } = shell;
  const {
    activeSession,
    activeSubagent,
    activeSubagentParentSessionId,
    bootstrap,
    handleCancelSubagent: cancelSubagent,
    handleCreateSession: createChatSession,
    handleOpenSubagent: openSubagent,
    handleReturnToParentSession: returnToParentSession,
    handleSelectSession: selectSession,
    handleSendMessage: sendMessage,
    isSubagentSheetOpen,
    loadSession,
    loadSubagentDetail,
    loadSubagentMessages,
    refreshSessionContext,
    refreshSessionsAndSelection,
  } = chat;
  const { loadActivity } = activity;
  const { loadAgentConfig } = agentProfile;
  const {
    handleApproveApproval: approvePendingApproval,
    handleDenyApproval: denyPendingApproval,
    loadApprovals,
  } = approvals;
  const {
    handleCreateJob: createJob,
    handlePauseJob: pauseJob,
    handleActivateJob: activateJob,
    handleRemoveJob: removeJob,
    loadJobs,
  } = jobs;
  const {
    handleSaveOperationalSettings: saveOperationalSettings,
    loadOperationalSettings,
  } = operationalSettings;
  const { loadToolingSnapshot, loadTools } = tooling;

  const focusChatView = useCallback(() => {
    setView('chat');
    setMobileNavOpen(false);
  }, [setMobileNavOpen, setView]);

  const loadOperationalSettingsWithDefaultView = useCallback(async () => {
    const response = await loadOperationalSettings();
    if (!response) {
      return null;
    }

    setView((current) =>
      !hasAppliedDefaultViewRef.current && current === 'chat'
        ? response.default_view
        : current,
    );
    hasAppliedDefaultViewRef.current = true;
    return response;
  }, [loadOperationalSettings, setView]);

  const refreshJobsAndActivity = useCallback(async () => {
    await Promise.all([loadJobs(), loadActivity()]);
  }, [loadActivity, loadJobs]);

  const handleCreateSession = useCallback(async () => {
    const created = await createChatSession();
    if (!created) {
      return null;
    }

    focusChatView();
    return created;
  }, [createChatSession, focusChatView]);

  const handleSelectSession = useCallback(
    async (sessionId: string) => {
      focusChatView();
      return selectSession(sessionId);
    },
    [focusChatView, selectSession],
  );

  const handleOpenSubagent = useCallback(
    async (parentSessionId: string, childSessionId: string) => {
      focusChatView();
      return openSubagent(parentSessionId, childSessionId);
    },
    [focusChatView, openSubagent],
  );

  const handleCancelSubagent = useCallback(
    async (parentSessionId: string, childSessionId: string) =>
      cancelSubagent(parentSessionId, childSessionId, async () => {
        await loadActivity();
      }),
    [cancelSubagent, loadActivity],
  );

  const handleReturnToParentSession = useCallback(
    async (parentSessionId: string) => {
      focusChatView();
      return returnToParentSession(parentSessionId);
    },
    [focusChatView, returnToParentSession],
  );

  const handleSendMessage = useCallback(
    async () =>
      sendMessage(async () => {
        await Promise.all([loadApprovals(), loadActivity()]);
      }),
    [loadActivity, loadApprovals, sendMessage],
  );

  const handleSaveOperationalSettings = useCallback(async () => {
    const saved = await saveOperationalSettings();
    if (!saved) {
      return null;
    }

    await loadToolingSnapshot();
    return saved;
  }, [loadToolingSnapshot, saveOperationalSettings]);

  const handleApproveApproval = useCallback(
    async (approvalId: string) => {
      const response = await approvePendingApproval(approvalId);
      if (!response) {
        return null;
      }

      focusChatView();
      const preferredSessionId = response.approval.session_id || undefined;
      await Promise.all([
        preferredSessionId
          ? refreshSessionContext(preferredSessionId)
          : refreshSessionsAndSelection(),
        loadApprovals(),
        loadActivity(),
      ]);
      return response;
    },
    [
      approvePendingApproval,
      focusChatView,
      loadActivity,
      loadApprovals,
      refreshSessionContext,
      refreshSessionsAndSelection,
    ],
  );

  const handleDenyApproval = useCallback(
    async (approvalId: string) => {
      const response = await denyPendingApproval(approvalId);
      if (!response) {
        return null;
      }

      focusChatView();
      const preferredSessionId = response.approval.session_id || undefined;
      await Promise.all([
        preferredSessionId
          ? refreshSessionContext(preferredSessionId)
          : refreshSessionsAndSelection(),
        loadApprovals(),
        loadActivity(),
      ]);
      return response;
    },
    [
      denyPendingApproval,
      focusChatView,
      loadActivity,
      loadApprovals,
      refreshSessionContext,
      refreshSessionsAndSelection,
    ],
  );

  const handleCreateJob = useCallback(
    async (payload: Parameters<typeof createJob>[0]) => {
      const created = await createJob(payload);
      if (!created) {
        return null;
      }

      setView('jobs');
      setMobileNavOpen(false);
      await refreshJobsAndActivity();
      return created;
    },
    [createJob, refreshJobsAndActivity, setMobileNavOpen, setView],
  );

  const handlePauseJob = useCallback(
    async (jobId: string) => {
      const paused = await pauseJob(jobId);
      if (!paused) {
        return null;
      }

      await refreshJobsAndActivity();
      return paused;
    },
    [pauseJob, refreshJobsAndActivity],
  );

  const handleActivateJob = useCallback(
    async (jobId: string) => {
      const activated = await activateJob(jobId);
      if (!activated) {
        return null;
      }

      await refreshJobsAndActivity();
      return activated;
    },
    [activateJob, refreshJobsAndActivity],
  );

  const handleRemoveJob = useCallback(
    async (jobId: string) => {
      const removed = await removeJob(jobId);
      if (!removed) {
        return null;
      }

      await refreshJobsAndActivity();
      return removed;
    },
    [refreshJobsAndActivity, removeJob],
  );

  const handleRefreshCurrentView = useCallback(async () => {
    setErrorMessage(null);

    switch (view) {
      case 'chat':
        await bootstrap(activeSession?.id);
        return;
      case 'profile':
        await loadAgentConfig();
        return;
      case 'settings':
        await loadOperationalSettingsWithDefaultView();
        return;
      case 'tools':
        await loadTools();
        return;
      case 'approvals':
        await loadApprovals();
        return;
      case 'jobs':
        await refreshJobsAndActivity();
        return;
      case 'activity':
        await loadActivity();
        return;
      default:
        return;
    }
  }, [
    activeSession?.id,
    bootstrap,
    loadActivity,
    loadAgentConfig,
    loadApprovals,
    loadOperationalSettingsWithDefaultView,
    loadTools,
    refreshJobsAndActivity,
    view,
  ]);

  useEffect(() => {
    void bootstrap();
    void loadAgentConfig();
    void loadOperationalSettingsWithDefaultView();
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
    loadOperationalSettingsWithDefaultView,
    loadTools,
  ]);

  useEffect(() => {
    if (view !== 'jobs' && view !== 'activity') {
      return undefined;
    }

    const intervalMs = Math.max(
      (operationalSettings.operationalSettings?.activity_poll_seconds || 3) *
        1000,
      1000,
    );
    const intervalId = window.setInterval(() => {
      void refreshJobsAndActivity();
    }, intervalMs);

    return () => window.clearInterval(intervalId);
  }, [
    operationalSettings.operationalSettings?.activity_poll_seconds,
    refreshJobsAndActivity,
    view,
  ]);

  useEffect(() => {
    if (view !== 'chat' || !activeSession) {
      return undefined;
    }

    const intervalMs = Math.max(
      (operationalSettings.operationalSettings?.activity_poll_seconds || 3) *
        1000,
      1000,
    );
    const intervalId = window.setInterval(() => {
      void loadSession(activeSession, { silent: true });
      if (isSubagentSheetOpen && activeSubagent && activeSubagentParentSessionId) {
        void loadSubagentDetail(activeSubagentParentSessionId, activeSubagent.id, {
          silent: true,
        });
        void loadSubagentMessages(
          activeSubagentParentSessionId,
          activeSubagent.id,
          { silent: true },
        );
      }
    }, intervalMs);

    return () => window.clearInterval(intervalId);
  }, [
    activeSession,
    activeSubagent,
    activeSubagentParentSessionId,
    isSubagentSheetOpen,
    loadSession,
    loadSubagentDetail,
    loadSubagentMessages,
    operationalSettings.operationalSettings?.activity_poll_seconds,
    view,
  ]);

  const pendingApprovalsCount = approvals.approvals.filter(
    (approval) => approval.status === 'pending',
  ).length;
  const activeJobsCount = jobs.cronJobs.filter(
    (job) => job.status === 'active',
  ).length;
  const providerLabel = getOperationalProviderLabel(
    operationalSettings.operationalSettings?.provider ||
      agentProfile.agent?.profile?.model_provider ||
      'product_echo',
  );
  const agentTitle = agentProfile.agent?.name || 'Nanobot Agent';
  const isComposerDisabled =
    chat.isBootstrapping ||
    chat.isLoadingMessages ||
    chat.isCreatingSession ||
    chat.isSending;
  const isWorkspaceSyncing =
    chat.isBootstrapping ||
    agentProfile.isLoadingAgent ||
    tooling.isLoadingTools ||
    approvals.isLoadingApprovals ||
    jobs.isLoadingJobs ||
    activity.isLoadingActivity ||
    operationalSettings.isLoadingOperationalSettings;

  const getViewCount = useCallback(
    (targetView: AppView): string | null => {
      switch (targetView) {
        case 'chat':
          return chat.sessions.length ? String(chat.sessions.length) : null;
        case 'approvals':
          return pendingApprovalsCount ? String(pendingApprovalsCount) : null;
        case 'tools':
          return tooling.toolPermissions.length
            ? String(tooling.toolPermissions.length)
            : null;
        case 'jobs':
          return jobs.cronJobs.length ? String(jobs.cronJobs.length) : null;
        case 'activity':
          return activity.activityItems.length
            ? String(activity.activityItems.length)
            : null;
        default:
          return null;
      }
    },
    [
      activity.activityItems.length,
      chat.sessions.length,
      jobs.cronJobs.length,
      pendingApprovalsCount,
      tooling.toolPermissions.length,
    ],
  );

  return {
    activity,
    agentProfile,
    app: {
      activeJobsCount,
      agentTitle,
      errorMessage,
      getViewCount,
      handleRefreshCurrentView,
      isComposerDisabled,
      isWorkspaceSyncing,
      pendingApprovalsCount,
      providerLabel,
      setErrorMessage,
    },
    approvals: {
      ...approvals,
      handleApproveApproval,
      handleDenyApproval,
    },
    chat: {
      ...chat,
      handleCancelSubagent,
      handleCreateSession,
      handleOpenSubagent,
      handleReturnToParentSession,
      handleSelectSession,
      handleSendMessage,
    },
    jobs: {
      ...jobs,
      handleActivateJob,
      handleCreateJob,
      handlePauseJob,
      handleRemoveJob,
    },
    operationalSettings: {
      ...operationalSettings,
      handleSaveOperationalSettings,
    },
    shell,
    tooling,
  };
}
