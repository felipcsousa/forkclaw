import { useCallback, useState } from 'react';

import {
  createMemoryItem,
  deleteMemoryItem,
  demoteMemoryItem,
  fetchMemoryItem,
  fetchMemoryItemHistory,
  fetchMemoryItems,
  fetchMemoryRecallLog,
  hideMemoryItem,
  promoteMemoryItem,
  restoreMemoryItem,
  updateMemoryItem,
  type MemoryHistoryEntryRecord,
  type MemoryItemCreateInput,
  type MemoryItemRecord,
  type MemoryItemUpdateInput,
  type MemoryMode,
  type MemoryRecallLogEntryRecord,
  type MemoryStateFilter,
} from '../../lib/backend/memory';
import type { RunAsyncAction } from './shared';

export type MemoryStudioTab =
  | 'all'
  | 'stable'
  | 'episodic'
  | 'session_summaries'
  | 'recall_log';

function kindForTab(tab: MemoryStudioTab) {
  if (tab === 'stable') {
    return 'stable' as const;
  }
  if (tab === 'episodic') {
    return 'episodic' as const;
  }
  if (tab === 'session_summaries') {
    return 'session_summary' as const;
  }
  return undefined;
}

export function useMemoryController({
  runAsyncAction,
}: {
  runAsyncAction: RunAsyncAction;
}) {
  const [memoryItems, setMemoryItems] = useState<MemoryItemRecord[]>([]);
  const [recallLog, setRecallLog] = useState<MemoryRecallLogEntryRecord[]>([]);
  const [selectedMemory, setSelectedMemory] = useState<MemoryItemRecord | null>(null);
  const [selectedMemoryHistory, setSelectedMemoryHistory] = useState<
    MemoryHistoryEntryRecord[]
  >([]);
  const [activeTab, setActiveTab] = useState<MemoryStudioTab>('all');
  const [searchText, setSearchText] = useState('');
  const [scopeFilter, setScopeFilter] = useState('');
  const [sourceKindFilter, setSourceKindFilter] = useState('');
  const [stateFilter, setStateFilter] = useState<MemoryStateFilter>('active');
  const [modeFilter, setModeFilter] = useState<MemoryMode>('all');
  const [isLoadingMemory, setIsLoadingMemory] = useState(false);
  const [isUpdatingMemory, setIsUpdatingMemory] = useState(false);
  const [isLoadingMemoryDetail, setIsLoadingMemoryDetail] = useState(false);

  const buildFilters = useCallback(() => {
    const kind = kindForTab(activeTab);
    return {
      kind,
      mode: modeFilter,
      query: searchText.trim() || undefined,
      recallStatus: undefined,
      scope: scopeFilter || undefined,
      sourceKind: sourceKindFilter || undefined,
      state: stateFilter,
    };
  }, [activeTab, modeFilter, scopeFilter, searchText, sourceKindFilter, stateFilter]);

  const loadMemoryStudio = useCallback(async () => {
    const response = await runAsyncAction(
      async () => {
        const [itemsResponse, recallResponse] = await Promise.all([
          fetchMemoryItems(buildFilters()),
          fetchMemoryRecallLog(),
        ]);
        return { itemsResponse, recallResponse };
      },
      {
        setPending: setIsLoadingMemory,
        errorMessage: 'Failed to load memory studio.',
      },
    );
    if (!response) {
      return null;
    }

    setMemoryItems(response.itemsResponse.items);
    setRecallLog(response.recallResponse.items);
    return response;
  }, [buildFilters, runAsyncAction]);

  const handleOpenDetail = useCallback(
    async (memoryId: string) => {
      const response = await runAsyncAction(
        async () => {
          const [itemResponse, historyResponse] = await Promise.all([
            fetchMemoryItem(memoryId),
            fetchMemoryItemHistory(memoryId),
          ]);
          return { historyResponse, itemResponse };
        },
        {
          setPending: setIsLoadingMemoryDetail,
          errorMessage: 'Failed to load memory detail.',
        },
      );
      if (!response) {
        return null;
      }

      setSelectedMemory(response.itemResponse);
      setSelectedMemoryHistory(response.historyResponse.items);
      return response.itemResponse;
    },
    [runAsyncAction],
  );

  const refreshAfterMutation = useCallback(
    async (memoryId?: string | null) => {
      await loadMemoryStudio();
      if (memoryId) {
        await handleOpenDetail(memoryId);
      }
    },
    [handleOpenDetail, loadMemoryStudio],
  );

  const handleCreateMemory = useCallback(
    async (payload: MemoryItemCreateInput) => {
      const created = await runAsyncAction(
        () => createMemoryItem(payload),
        {
          setPending: setIsUpdatingMemory,
          errorMessage: 'Failed to create memory.',
        },
      );
      if (!created) {
        return null;
      }

      await refreshAfterMutation(created.id);
      return created;
    },
    [refreshAfterMutation, runAsyncAction],
  );

  const handleUpdateMemory = useCallback(
    async (memoryId: string, payload: MemoryItemUpdateInput) => {
      const updated = await runAsyncAction(
        () => updateMemoryItem(memoryId, payload),
        {
          setPending: setIsUpdatingMemory,
          errorMessage: 'Failed to update memory.',
        },
      );
      if (!updated) {
        return null;
      }

      await refreshAfterMutation(updated.id);
      return updated;
    },
    [refreshAfterMutation, runAsyncAction],
  );

  const handleHideMemory = useCallback(
    async (memoryId: string) => {
      const hidden = await runAsyncAction(
        () => hideMemoryItem(memoryId),
        {
          setPending: setIsUpdatingMemory,
          errorMessage: 'Failed to hide memory from recall.',
        },
      );
      if (!hidden) {
        return null;
      }

      await refreshAfterMutation(memoryId);
      return hidden;
    },
    [refreshAfterMutation, runAsyncAction],
  );

  const handleRestoreMemory = useCallback(
    async (memoryId: string) => {
      const restored = await runAsyncAction(
        () => restoreMemoryItem(memoryId),
        {
          setPending: setIsUpdatingMemory,
          errorMessage: 'Failed to restore memory.',
        },
      );
      if (!restored) {
        return null;
      }

      await refreshAfterMutation(memoryId);
      return restored;
    },
    [refreshAfterMutation, runAsyncAction],
  );

  const handlePromoteMemory = useCallback(
    async (memoryId: string) => {
      const promoted = await runAsyncAction(
        () => promoteMemoryItem(memoryId),
        {
          setPending: setIsUpdatingMemory,
          errorMessage: 'Failed to promote memory.',
        },
      );
      if (!promoted) {
        return null;
      }

      await refreshAfterMutation(memoryId);
      return promoted;
    },
    [refreshAfterMutation, runAsyncAction],
  );

  const handleDemoteMemory = useCallback(
    async (memoryId: string) => {
      const demoted = await runAsyncAction(
        () => demoteMemoryItem(memoryId),
        {
          setPending: setIsUpdatingMemory,
          errorMessage: 'Failed to demote memory.',
        },
      );
      if (!demoted) {
        return null;
      }

      await refreshAfterMutation(memoryId);
      return demoted;
    },
    [refreshAfterMutation, runAsyncAction],
  );

  const handleDeleteMemory = useCallback(
    async (memoryId: string, hard = false) => {
      const deleted = await runAsyncAction(
        () => deleteMemoryItem(memoryId, hard),
        {
          setPending: setIsUpdatingMemory,
          errorMessage: hard
            ? 'Failed to permanently delete memory.'
            : 'Failed to delete memory.',
        },
      );
      if (deleted === null && hard) {
        setSelectedMemory((current) => (current?.id === memoryId ? null : current));
        setSelectedMemoryHistory((current) =>
          selectedMemory?.id === memoryId ? [] : current,
        );
        await loadMemoryStudio();
        return null;
      }
      if (!deleted) {
        return null;
      }

      await refreshAfterMutation(memoryId);
      return deleted;
    },
    [loadMemoryStudio, refreshAfterMutation, runAsyncAction, selectedMemory?.id],
  );

  return {
    activeTab,
    handleCreateMemory,
    handleDeleteMemory,
    handleDemoteMemory,
    handleHideMemory,
    handleOpenDetail,
    handlePromoteMemory,
    handleRestoreMemory,
    handleUpdateMemory,
    isLoadingMemory,
    isLoadingMemoryDetail,
    isUpdatingMemory,
    loadMemoryStudio,
    memoryItems,
    modeFilter,
    recallLog,
    scopeFilter,
    searchText,
    selectedMemory,
    selectedMemoryHistory,
    setActiveTab,
    setModeFilter,
    setScopeFilter,
    setSearchText,
    setSelectedMemory,
    setSourceKindFilter,
    setStateFilter,
    sourceKindFilter,
    stateFilter,
  };
}
