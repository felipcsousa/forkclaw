import { Eye, ShieldAlert } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from '@/components/ui/resizable';
import { ScrollArea } from '@/components/ui/scroll-area';
import { cn } from '@/lib/utils';
import type { ApprovalRecord } from '../lib/backend';

interface ApprovalsInboxProps {
  approvals: ApprovalRecord[];
  activeApprovalId: string | null;
  isLoading: boolean;
  isActing: boolean;
  onSelectApproval: (approvalId: string) => void;
  onApprove: (approvalId: string) => void;
  onDeny: (approvalId: string) => void;
}

function statusVariant(status: string) {
  if (status === 'approved' || status === 'completed') return 'success' as const;
  if (status === 'denied' || status === 'failed') return 'destructive' as const;
  return 'warning' as const;
}

export function ApprovalsInbox({
  approvals,
  activeApprovalId,
  isLoading,
  isActing,
  onSelectApproval,
  onApprove,
  onDeny,
}: ApprovalsInboxProps) {
  const activeApproval =
    approvals.find((approval) => approval.id === activeApprovalId) || approvals[0] || null;

  return (
    <div className="animate-fade-in h-auto bg-card rounded-xl border border-border shadow-sm overflow-hidden flex flex-col min-h-[42rem]">
      <ResizablePanelGroup orientation="horizontal" className="flex-1">
        <ResizablePanel defaultSize={32} minSize={25} className="bg-muted/10">
          <div className="flex h-full flex-col border-r border-border/60">
            <div className="border-b border-border/60 bg-background/50 px-4 py-3.5 flex items-center justify-between shrink-0">
              <span className="text-[13px] font-semibold tracking-tight text-foreground">Inbox queue</span>
              <Badge variant="secondary" className="px-1.5 h-5 text-[10px] rounded-md shadow-xs bg-background border-border/60 font-medium">{approvals.length}</Badge>
            </div>

            <ScrollArea className="min-h-0 flex-1">
              {isLoading && approvals.length === 0 ? (
                <div className="flex flex-col items-center justify-center p-8 gap-2 opacity-60">
                  <p className="text-[13px] font-semibold tracking-tight text-foreground animate-pulse">Loading approvals...</p>
                </div>
              ) : approvals.length === 0 ? (
                <div className="flex flex-col items-center justify-center p-12 gap-2 text-center">
                  <p className="text-[14px] font-semibold tracking-tight text-foreground">Inbox zero</p>
                  <p className="text-[13px] text-muted-foreground/80">No pending approvals require your attention at the moment.</p>
                </div>
              ) : (
                <div className="flex flex-col divide-y divide-border/40">
                  {approvals.map((approval) => (
                    <button
                      key={approval.id}
                      type="button"
                      onClick={() => onSelectApproval(approval.id)}
                      className={cn(
                        'w-full px-4 py-2.5 text-left transition-colors relative outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset group/approval',
                        approval.id === activeApproval?.id
                          ? 'bg-foreground/[0.04] shadow-[inset_3px_0_0_var(--color-foreground)]'
                          : 'hover:bg-foreground/[0.03]',
                      )}
                    >
                      <div className="flex items-center justify-between gap-3 mb-1">
                        <span className={cn(
                          "truncate text-[13px] tracking-tight",
                          approval.id === activeApproval?.id ? "font-semibold text-foreground" : "font-medium text-foreground/90"
                        )}>
                          {approval.tool_name || approval.kind}
                        </span>
                        <Badge variant={statusVariant(approval.status)} className="px-1.5 py-0 min-h-[1.125rem] text-[9px] font-semibold shrink-0">
                          {approval.status}
                        </Badge>
                      </div>
                      <p className="truncate text-[11px] font-medium text-muted-foreground">
                        {approval.session_title || 'No session title'}
                      </p>
                    </button>
                  ))}
                </div>
              )}
            </ScrollArea>
          </div>
        </ResizablePanel>

        <ResizableHandle withHandle className="bg-border/60 w-1 hover:w-1.5 hover:bg-border transition-all" />

        <ResizablePanel defaultSize={68} minSize={40} className="bg-background">
          <div className="flex h-full flex-col">
            {activeApproval ? (
              <>
                <div className="border-b border-border/60 bg-card px-6 py-5 shrink-0 shadow-xs z-10">
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="space-y-2.5">
                      <div className="flex items-center gap-2">
                        <ShieldAlert className="h-4 w-4 text-amber-500" strokeWidth={2.5} />
                        <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground/80">
                          Decision Summary
                        </p>
                      </div>
                      <h3 className="text-xl font-semibold tracking-tight text-foreground">
                        {activeApproval.tool_name || activeApproval.kind}
                      </h3>
                      <p className="max-w-xl text-[13px] leading-relaxed text-muted-foreground/90">
                        Approve to resume the paused run with these parameters, or deny to record a traced failure.
                      </p>
                    </div>
                    <Badge variant={statusVariant(activeApproval.status)} className="font-medium shadow-xs px-2.5 py-0.5 text-[11px] uppercase tracking-wider">
                      {activeApproval.status}
                    </Badge>
                  </div>
                </div>

                <ScrollArea className="min-h-0 flex-1 px-6 py-6 bg-muted/5">
                  <div className="max-w-3xl space-y-8 pb-8">
                    <div className="grid gap-6 sm:grid-cols-2 rounded-xl border border-border/60 bg-card p-5 shadow-xs">
                      <div>
                        <p className="mb-2 text-[10px] font-bold uppercase tracking-widest text-muted-foreground/80">
                          Requested Action
                        </p>
                        <p className="text-[14px] font-medium text-foreground">
                          {activeApproval.requested_action}
                        </p>
                      </div>
                      <div>
                        <p className="mb-2 text-[10px] font-bold uppercase tracking-widest text-muted-foreground/80">
                          Session
                        </p>
                        <p className="text-[14px] font-medium text-foreground">
                          {activeApproval.session_title || activeApproval.session_id || '(none)'}
                        </p>
                      </div>
                    </div>

                    <div className="space-y-3">
                      <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground/80">
                        Reason
                      </p>
                      <div className="rounded-xl border border-border/60 bg-card p-4 shadow-xs">
                        <p className="text-[13px] leading-relaxed text-foreground/90">
                          {activeApproval.reason || 'No additional reason provided.'}
                        </p>
                      </div>
                    </div>

                    <div className="space-y-3">
                      <div className="flex items-center justify-between gap-4">
                        <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground/80">
                          Parameters
                        </p>
                        <Dialog>
                          <DialogTrigger asChild>
                            <Button variant="secondary" size="sm" className="h-7 px-3 text-xs shadow-none border-border">
                              <Eye className="mr-1.5 h-3.5 w-3.5" />
                              Raw JSON
                            </Button>
                          </DialogTrigger>
                          <DialogContent className="sm:max-w-xl">
                            <DialogHeader>
                              <DialogTitle className="text-lg">Approval payload</DialogTitle>
                              <DialogDescription className="text-[13px]">
                                Exact JSON stored with this paused action.
                              </DialogDescription>
                            </DialogHeader>
                            <div className="relative rounded-lg bg-zinc-950 p-4 shadow-inner mt-2">
                              <pre className="max-h-[50vh] overflow-auto text-[12px] leading-relaxed text-zinc-50 font-mono scrollbar-thin scrollbar-thumb-zinc-700 scrollbar-track-transparent">
                                {activeApproval.tool_input_json || '{}'}
                              </pre>
                            </div>
                          </DialogContent>
                        </Dialog>
                      </div>
                      <div className="rounded-xl border border-border/60 bg-zinc-950 p-4 shadow-inner">
                        <pre className="overflow-auto text-[12px] leading-relaxed text-zinc-50 font-mono scrollbar-thin scrollbar-thumb-zinc-700 scrollbar-track-transparent">
                          {activeApproval.tool_input_json || '{}'}
                        </pre>
                      </div>
                    </div>
                  </div>
                </ScrollArea>

                <div className="border-t border-border/60 bg-card px-6 py-4 shrink-0 shadow-[0_-4px_12px_rgba(0,0,0,0.02)] z-10">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <p className="text-[12px] font-medium text-muted-foreground/80 hidden sm:block">
                      Decisions remain durable across restarts.
                    </p>
                    <div className="flex items-center gap-3 w-full sm:w-auto">
                      <Button
                        variant="secondary"
                        onClick={() => onDeny(activeApproval.id)}
                        disabled={isActing || activeApproval.status !== 'pending'}
                        className="flex-1 sm:flex-none shadow-sm"
                      >
                        Deny
                      </Button>
                      <Button
                        onClick={() => onApprove(activeApproval.id)}
                        disabled={isActing || activeApproval.status !== 'pending'}
                        className="flex-1 sm:flex-none shadow-sm bg-primary text-primary-foreground hover:bg-primary/90"
                      >
                        Approve Action
                      </Button>
                    </div>
                  </div>
                </div>
              </>
            ) : (
              <div className="flex h-full flex-col items-center justify-center p-8 gap-3 bg-muted/5">
                <div className="h-12 w-12 rounded-full bg-muted/50 flex items-center justify-center mb-2">
                  <ShieldAlert className="h-6 w-6 text-muted-foreground/30" />
                </div>
                <p className="text-[14px] font-semibold tracking-tight text-foreground">
                  Select an approval
                </p>
                <p className="text-[13px] text-muted-foreground/80 max-w-sm text-center">
                  Review the parameters and reason before authorizing the agent payload to resume execution.
                </p>
              </div>
            )}
          </div>
        </ResizablePanel>
      </ResizablePanelGroup>
    </div>
  );
}
