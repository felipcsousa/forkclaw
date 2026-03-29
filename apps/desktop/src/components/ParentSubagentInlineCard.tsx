import { ArrowUpRight, Square, StopCircle } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  canCancelSubagent,
  formatDuration,
  formatEstimatedCost,
  formatTimestamp,
  subagentStatusCopy,
  subagentStatusVariant,
} from '@/lib/subagents';
import type { SubagentSessionRecord } from '../lib/backend';

interface ParentSubagentInlineCardProps {
  subagent: SubagentSessionRecord;
  isCancelling: boolean;
  onOpen: (parentSessionId: string, childSessionId: string) => void;
  onCancel: (parentSessionId: string, childSessionId: string) => void;
}

export function ParentSubagentInlineCard({
  subagent,
  isCancelling,
  onOpen,
  onCancel,
}: ParentSubagentInlineCardProps) {
  const canCancel = canCancelSubagent(subagent.run.lifecycle_status);

  return (
    <div className="ml-11 rounded-2xl border border-border/70 bg-[color-mix(in_srgb,white_86%,var(--color-muted)_14%)] px-4 py-3 shadow-sm">
      <div className="flex flex-col gap-3">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <Badge variant={subagentStatusVariant(subagent.run.lifecycle_status)}>
                {subagent.run.lifecycle_status}
              </Badge>
              <span className="text-[11px] font-medium uppercase tracking-[0.16em] text-muted-foreground">
                Child session
              </span>
            </div>
            <p className="mt-2 text-sm font-medium text-foreground">
              {subagent.delegated_goal || subagent.title}
            </p>
            <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
              {subagentStatusCopy(subagent.run.lifecycle_status)}
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Button
              type="button"
              size="sm"
              variant="secondary"
              className="h-8 gap-1.5 text-xs"
              onClick={() => onOpen(subagent.parent_session_id || '', subagent.id)}
              aria-label={`Open child session: ${subagent.delegated_goal || subagent.title}`}
            >
              <ArrowUpRight className="h-3.5 w-3.5" />
              Open child session
            </Button>
            {canCancel ? (
              <Button
                type="button"
                size="sm"
                variant="ghost"
                className="h-8 gap-1.5 text-xs text-destructive hover:bg-destructive/10 hover:text-destructive"
                onClick={() => onCancel(subagent.parent_session_id || '', subagent.id)}
                disabled={isCancelling}
                aria-label={`Cancel child session: ${subagent.delegated_goal || subagent.title}`}
              >
                <StopCircle className="h-3.5 w-3.5" />
                {isCancelling ? 'Cancelling...' : 'Cancel'}
              </Button>
            ) : null}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
          <span>Created {formatTimestamp(subagent.created_at)}</span>
          <span>Duration {formatDuration(subagent.run)}</span>
          <span>Cost {formatEstimatedCost(subagent.run.estimated_cost_usd)}</span>
          {subagent.run.task_run_id ? (
            <span className="inline-flex items-center gap-1">
              <Square className="h-3 w-3" />
              {subagent.run.task_run_id.slice(0, 8)}
            </span>
          ) : null}
        </div>
      </div>
    </div>
  );
}
