import type { useAppController } from '../hooks/useAppController';
import { ApprovalsInbox } from '../components/ApprovalsInbox';

type AppController = ReturnType<typeof useAppController>;

export interface ApprovalsViewProps {
  approvals: AppController['approvals'];
}

export function ApprovalsView({ approvals }: ApprovalsViewProps) {
  return (
    <ApprovalsInbox
      approvals={approvals.approvals}
      activeApprovalId={approvals.activeApprovalId}
      isLoading={approvals.isLoadingApprovals}
      isActing={approvals.isActingOnApproval}
      onSelectApproval={approvals.setActiveApprovalId}
      onApprove={approvals.handleApproveApproval}
      onDeny={approvals.handleDenyApproval}
    />
  );
}
