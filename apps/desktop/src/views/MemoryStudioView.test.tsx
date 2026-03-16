import { fireEvent, render, screen } from '@testing-library/react';
import { vi } from 'vitest';

import { TooltipProvider } from '@/components/ui/tooltip';
import { MemoryStudioView } from './MemoryStudioView';

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
    origin_session_id: null,
    origin_subagent_session_id: null,
    original_memory_id: null,
    created_at: '2026-03-08T12:00:00Z',
    updated_at: '2026-03-08T12:00:00Z',
    ...overrides,
  };
}

function makeRecall(overrides: Record<string, unknown> = {}) {
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

function makeMemoryController(overrides: Record<string, unknown> = {}) {
  return {
    activeTab: 'all',
    handleCreateMemory: vi.fn(),
    handleDeleteMemory: vi.fn(),
    handleDemoteMemory: vi.fn(),
    handleHideMemory: vi.fn(),
    handleOpenDetail: vi.fn(),
    handlePromoteMemory: vi.fn(),
    handleRestoreMemory: vi.fn(),
    handleUpdateMemory: vi.fn(),
    isLoadingMemory: false,
    isLoadingMemoryDetail: false,
    isUpdatingMemory: false,
    loadMemoryStudio: vi.fn(),
    memoryItems: [makeMemory()],
    modeFilter: 'all',
    recallLog: [],
    scopeFilter: '',
    searchText: '',
    selectedMemory: null,
    selectedMemoryHistory: [],
    setActiveTab: vi.fn(),
    setModeFilter: vi.fn(),
    setScopeFilter: vi.fn(),
    setSearchText: vi.fn(),
    setSelectedMemory: vi.fn(),
    setSourceKindFilter: vi.fn(),
    setStateFilter: vi.fn(),
    sourceKindFilter: '',
    stateFilter: 'active',
    ...overrides,
  };
}

describe('MemoryStudioView', () => {
  it('renders tabs, memory rows, and row actions for the studio', () => {
    const memory = makeMemoryController();

    render(
      <TooltipProvider>
        <MemoryStudioView memory={memory as never} />
      </TooltipProvider>
    );

    expect(screen.getByRole('tab', { name: 'All Memories' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Stable Memory' })).toBeInTheDocument();
    expect(screen.getByText('Tea preference')).toBeInTheDocument();
    expect(screen.getByText('Manual')).toBeInTheDocument();

    fireEvent.pointerDown(
      screen.getByRole('button', { name: 'Actions for Tea preference' }),
    );
    fireEvent.click(screen.getByRole('menuitem', { name: 'Hide from recall' }));

    expect(memory.handleHideMemory).toHaveBeenCalledWith('memory-1');
  });

  it('shows tailored empty states for manual-only filters and recall log', () => {
    const memory = makeMemoryController({
      activeTab: 'recall_log',
      memoryItems: [],
      modeFilter: 'manual',
      recallLog: [makeRecall()],
    });

    const { rerender } = render(
      <TooltipProvider>
        <MemoryStudioView memory={memory as never} />
      </TooltipProvider>
    );

    expect(screen.getByText('Memory recall log')).toBeInTheDocument();
    expect(screen.getByText('Tea preference')).toBeInTheDocument();

    rerender(
      <TooltipProvider>
        <MemoryStudioView
          memory={
            makeMemoryController({
              activeTab: 'all',
              memoryItems: [],
              modeFilter: 'manual',
              recallLog: [],
            }) as never
          }
        />
      </TooltipProvider>,
    );

    expect(screen.getByText('No manual memories yet')).toBeInTheDocument();
  });
});
