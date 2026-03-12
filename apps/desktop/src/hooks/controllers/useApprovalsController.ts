import { useCallback, useState } from 'react';

import {
  approveApproval,
  denyApproval,
  fetchApprovals,
  type ApprovalActionResponse,
  type ApprovalRecord,
} from '../../lib/backend/approvals';
import type { RunAsyncAction } from './shared';

export function useApprovalsController({
  runAsyncAction,
}: {
  runAsyncAction: RunAsyncAction;
}) {
  const [approvals, setApprovals] = useState<ApprovalRecord[]>([]);
  const [activeApprovalId, setActiveApprovalId] = useState<string | null>(null);
  const [isLoadingApprovals, setIsLoadingApprovals] = useState(false);
  const [isActingOnApproval, setIsActingOnApproval] = useState(false);

  const loadApprovals = useCallback(async () => {
    const response = await runAsyncAction(() => fetchApprovals(), {
      setPending: setIsLoadingApprovals,
      errorMessage: 'Failed to load approvals inbox.',
    });
    if (!response) {
      return null;
    }

    setApprovals(response.items);
    setActiveApprovalId((current) => {
      if (response.items.length === 0) {
        return null;
      }

      const stillExists = response.items.some((item) => item.id === current);
      return stillExists ? current : response.items[0].id;
    });
    return response;
  }, [runAsyncAction]);

  const handleApproveApproval = useCallback(
    async (approvalId: string): Promise<ApprovalActionResponse | null> =>
      runAsyncAction(() => approveApproval(approvalId), {
        setPending: setIsActingOnApproval,
        errorMessage: 'Failed to approve action.',
      }),
    [runAsyncAction],
  );

  const handleDenyApproval = useCallback(
    async (approvalId: string): Promise<ApprovalActionResponse | null> =>
      runAsyncAction(() => denyApproval(approvalId), {
        setPending: setIsActingOnApproval,
        errorMessage: 'Failed to deny action.',
      }),
    [runAsyncAction],
  );

  return {
    activeApprovalId,
    approvals,
    handleApproveApproval,
    handleDenyApproval,
    isActingOnApproval,
    isLoadingApprovals,
    loadApprovals,
    setActiveApprovalId,
  };
}
