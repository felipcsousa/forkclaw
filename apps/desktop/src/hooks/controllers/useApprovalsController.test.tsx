import { act, renderHook, waitFor } from '@testing-library/react';
import type { Dispatch, SetStateAction } from 'react';
import { vi } from 'vitest';

import { useApprovalsController } from './useApprovalsController';

const mockApproveApproval = vi.fn();
const mockDenyApproval = vi.fn();
const mockFetchApprovals = vi.fn();

vi.mock('../../lib/backend/approvals', () => ({
  approveApproval: (approvalId: string) => mockApproveApproval(approvalId),
  denyApproval: (approvalId: string) => mockDenyApproval(approvalId),
  fetchApprovals: () => mockFetchApprovals(),
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

describe('useApprovalsController', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('preserves the selected approval when it still exists and clears it when empty', async () => {
    const first = { id: 'approval-1', status: 'pending' };
    const second = { id: 'approval-2', status: 'pending' };

    mockFetchApprovals
      .mockResolvedValueOnce({ items: [first, second] })
      .mockResolvedValueOnce({ items: [second] })
      .mockResolvedValueOnce({ items: [] });

    const { result } = renderHook(() =>
      useApprovalsController({
        runAsyncAction: createRunAsyncAction(),
      }),
    );

    await act(async () => {
      await result.current.loadApprovals();
    });

    expect(result.current.activeApprovalId).toBe('approval-1');

    act(() => {
      result.current.setActiveApprovalId('approval-2');
    });

    await act(async () => {
      await result.current.loadApprovals();
    });

    expect(result.current.activeApprovalId).toBe('approval-2');

    await act(async () => {
      await result.current.loadApprovals();
    });

    await waitFor(() => {
      expect(result.current.activeApprovalId).toBeNull();
      expect(result.current.approvals).toEqual([]);
    });
  });
});
