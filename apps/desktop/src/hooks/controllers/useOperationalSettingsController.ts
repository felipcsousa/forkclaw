import { useCallback, useRef, useState } from 'react';

import {
  fetchOperationalSettings,
  type OperationalSettingsRecord,
  type OperationalSettingsUpdate,
  updateOperationalSettings,
} from '../../lib/backend/settings';
import type { RunAsyncAction } from './shared';

const emptyOperationalDraft: OperationalSettingsUpdate = {
  provider: 'product_echo',
  model_name: 'product-echo/simple',
  workspace_root: '',
  max_iterations_per_execution: 2,
  daily_budget_usd: 10,
  monthly_budget_usd: 200,
  default_view: 'chat',
  activity_poll_seconds: 3,
  heartbeat_interval_seconds: 1800,
  api_key: '',
  clear_api_key: false,
};

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
    heartbeat_interval_seconds: settings.heartbeat_interval_seconds,
    api_key: '',
    clear_api_key: false,
  };
}

export function useOperationalSettingsController({
  runAsyncAction,
  setErrorMessage,
}: {
  runAsyncAction: RunAsyncAction;
  setErrorMessage: (value: string | null) => void;
}) {
  const [operationalSettings, setOperationalSettings] =
    useState<OperationalSettingsRecord | null>(null);
  const [operationalDraft, setOperationalDraft] =
    useState<OperationalSettingsUpdate>(emptyOperationalDraft);
  const [isLoadingOperationalSettings, setIsLoadingOperationalSettings] =
    useState(false);
  const [isSavingOperationalSettings, setIsSavingOperationalSettings] =
    useState(false);
  const isSavingOperationalSettingsRef = useRef(false);

  const loadOperationalSettings = useCallback(async () => {
    const response = await runAsyncAction(() => fetchOperationalSettings(), {
      setPending: setIsLoadingOperationalSettings,
      errorMessage: 'Failed to load operational settings.',
    });
    if (!response) {
      return null;
    }

    setOperationalSettings(response);
    setOperationalDraft(toOperationalDraft(response));
    return response;
  }, [runAsyncAction]);

  const handleOperationalDraftChange = useCallback(
    <K extends keyof OperationalSettingsUpdate>(
      field: K,
      value: OperationalSettingsUpdate[K],
    ) => {
      setOperationalDraft((current) => ({ ...current, [field]: value }));
    },
    [],
  );

  const handleSaveOperationalSettings = useCallback(async () => {
    if (isSavingOperationalSettingsRef.current) return null;

    if (
      !operationalDraft.model_name.trim() ||
      !operationalDraft.workspace_root.trim()
    ) {
      setErrorMessage('Provider model and workspace root are required.');
      return null;
    }

    isSavingOperationalSettingsRef.current = true;
    try {
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
        return null;
      }

      setOperationalSettings(saved);
      setOperationalDraft(toOperationalDraft(saved));
      return saved;
    } finally {
      isSavingOperationalSettingsRef.current = false;
    }
  }, [operationalDraft, runAsyncAction, setErrorMessage]);

  return {
    handleOperationalDraftChange,
    handleSaveOperationalSettings,
    isLoadingOperationalSettings,
    isSavingOperationalSettings,
    loadOperationalSettings,
    operationalDraft,
    operationalSettings,
  };
}
