import { act, renderHook, waitFor } from '@testing-library/react';
import type { Dispatch, SetStateAction } from 'react';
import { vi } from 'vitest';

import { useMemoryController } from './useMemoryController';

const mockCreateMemoryItem = vi.fn();
const mockDeleteMemoryItem = vi.fn();
const mockDemoteMemoryItem = vi.fn();
const mockFetchMemoryItem = vi.fn();
const mockFetchMemoryItemHistory = vi.fn();
const mockFetchMemoryItems = vi.fn();
const mockFetchMemoryRecallLog = vi.fn();
const mockHideMemoryItem = vi.fn();
const mockPromoteMemoryItem = vi.fn();
const mockRestoreMemoryItem = vi.fn();
const mockUpdateMemoryItem = vi.fn();

vi.mock('../../lib/backend/memory', () => ({
  createMemoryItem: (payload: unknown) => mockCreateMemoryItem(payload),
  deleteMemoryItem: (memoryId: string, hard?: boolean) =>
    mockDeleteMemoryItem(memoryId, hard),
  demoteMemoryItem: (memoryId: string) => mockDemoteMemoryItem(memoryId),
  fetchMemoryItem: (memoryId: string) => mockFetchMemoryItem(memoryId),
  fetchMemoryItemHistory: (memoryId: string) => mockFetchMemoryItemHistory(memoryId),
  fetchMemoryItems: (filters: unknown) => mockFetchMemoryItems(filters),
  fetchMemoryRecallLog: () => mockFetchMemoryRecallLog(),
  hideMemoryItem: (memoryId: string) => mockHideMemoryItem(memoryId),
  promoteMemoryItem: (memoryId: string) => mockPromoteMemoryItem(memoryId),
  restoreMemoryItem: (memoryId: string) => mockRestoreMemoryItem(memoryId),
  updateMemoryItem: (memoryId: string, payload: unknown) =>
    mockUpdateMemoryItem(memoryId, payload),
}));

function createRunAsyncAction() {
  return async <T,>(
    action: () => Promise<T>,
    options: {
      clearError?: boolean;
      errorMessage: string;
      setPending?: Dispatch<SetStateAction<boolean>>;
    },
  ): Promise<T | null> => {
    if (options.clearError !== false) {
      // noop, just match the production signature
    }
    options.setPending?.(true);
    try {
      return await action();
    } finally {
      options.setPending?.(false);
    }
  };
}

function makeMemory(overrides: Record<string, unknown> = {}) {
  return {
    id: 'memory-1',
    kind: 'stable',
    title: 'Tea preference',
    content: 'Prefers oolong tea.',
    scope: 'profile',
    source_kind: 'manual',
    source_label: 'Manual',
    importance: 'high',
    state: 'active',
    recall_status: 'active',
    is_manual: true,
    is_override: false,
    original_memory_id: null,
    origin_session_id: null,
    origin_subagent_session_id: null,
    created_at: '2026-03-08T12:00:00Z',
    updated_at: '2026-03-08T12:00:00Z',
    ...overrides,
  };
}

function makeRecallLogEntry(overrides: Record<string, unknown> = {}) {
  return {
    id: 'recall-1',
    assistant_message_id: 'message-2',
    session_id: 'session-1',
    task_run_id: 'run-1',
    created_at: '2026-03-08T12:01:00Z',
    reason_summary: '1 memory item injected for recall.',
    items: [
      {
        memory_id: 'memory-1',
        title: 'Tea preference',
        kind: 'stable',
        scope: 'profile',
        source_kind: 'manual',
        source_label: 'Manual',
        importance: 'high',
        reason: 'Matched terms: oolong',
        origin_session_id: null,
        origin_subagent_session_id: null,
      },
    ],
    ...overrides,
  };
}

describe('useMemoryController', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('loads the studio with the active filters and tab mapping', async () => {
    mockFetchMemoryItems.mockResolvedValue({ items: [makeMemory()] });
    mockFetchMemoryRecallLog.mockResolvedValue({ items: [makeRecallLogEntry()] });

    const { result } = renderHook(() =>
      useMemoryController({
        runAsyncAction: createRunAsyncAction(),
      }),
    );

    act(() => {
      result.current.setActiveTab('stable');
      result.current.setSearchText('oolong');
      result.current.setScopeFilter('profile');
      result.current.setSourceKindFilter('manual');
      result.current.setStateFilter('hidden');
      result.current.setModeFilter('manual');
    });

    await act(async () => {
      await result.current.loadMemoryStudio();
    });

    expect(mockFetchMemoryItems).toHaveBeenCalledWith({
      kind: 'stable',
      mode: 'manual',
      query: 'oolong',
      recallStatus: undefined,
      scope: 'profile',
      sourceKind: 'manual',
      state: 'hidden',
    });
    expect(mockFetchMemoryRecallLog).toHaveBeenCalledTimes(1);
    expect(result.current.memoryItems).toEqual([makeMemory()]);
    expect(result.current.recallLog).toEqual([makeRecallLogEntry()]);
  });

  it('refreshes the index and detail after a mutating action', async () => {
    const memory = makeMemory();
    mockFetchMemoryItems.mockResolvedValue({ items: [memory] });
    mockFetchMemoryRecallLog.mockResolvedValue({ items: [] });
    mockFetchMemoryItem.mockResolvedValue(memory);
    mockFetchMemoryItemHistory.mockResolvedValue({
      items: [
        {
          id: 'hist-1',
          memory_id: memory.id,
          action: 'created',
          summary: 'Memory created.',
          snapshot: null,
          created_at: '2026-03-08T12:00:00Z',
        },
      ],
    });
    mockHideMemoryItem.mockResolvedValue(
      makeMemory({ recall_status: 'hidden', updated_at: '2026-03-08T12:05:00Z' }),
    );

    const { result } = renderHook(() =>
      useMemoryController({
        runAsyncAction: createRunAsyncAction(),
      }),
    );

    await act(async () => {
      await result.current.loadMemoryStudio();
      await result.current.handleOpenDetail(memory.id);
      await result.current.handleHideMemory(memory.id);
    });

    await waitFor(() => {
      expect(mockHideMemoryItem).toHaveBeenCalledWith(memory.id);
      expect(mockFetchMemoryItems).toHaveBeenCalledTimes(2);
      expect(mockFetchMemoryItem).toHaveBeenCalledTimes(2);
      expect(mockFetchMemoryItemHistory).toHaveBeenCalledTimes(2);
      expect(result.current.selectedMemory?.id).toBe(memory.id);
    });
  });
});
