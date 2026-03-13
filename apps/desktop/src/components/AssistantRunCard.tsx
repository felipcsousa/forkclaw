import { Activity, Bot, WifiOff } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import type {
  ChatExecutionRun,
  ChatExecutionRunStatus,
} from '../hooks/controllers/chatExecutionState';
import type { SubagentSessionRecord } from '../lib/backend';
import { ParentSubagentInlineCard } from './ParentSubagentInlineCard';
import { RunStepRow } from './RunStepRow';

type StreamStatus =
  | 'idle'
  | 'connecting'
  | 'connected'
  | 'reconnecting'
  | 'disconnected';

function runStatusVariant(status: ChatExecutionRunStatus) {
  if (status === 'completed' || status === 'running') {
    return 'success' as const;
  }

  if (status === 'failed') {
    return 'destructive' as const;
  }

  if (status === 'awaiting_approval') {
    return 'warning' as const;
  }

  return 'secondary' as const;
}

function formatElapsed(run: ChatExecutionRun) {
  const startedAt = run.startedAt || run.createdAt;
  const finishedAt = run.finishedAt;
  const startMs = new Date(startedAt).getTime();
  const endMs = new Date(finishedAt || Date.now()).getTime();
  if (Number.isNaN(startMs) || Number.isNaN(endMs)) {
    return null;
  }

  const durationMs = Math.max(endMs - startMs, 0);
  if (durationMs < 1000) {
    return `${durationMs}ms`;
  }

  const seconds = Math.round(durationMs / 1000);
  if (seconds < 60) {
    return `${seconds}s`;
  }

  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  return remainingSeconds ? `${minutes}m ${remainingSeconds}s` : `${minutes}m`;
}

function streamCopy(streamStatus: StreamStatus, reconnectAttempt: number) {
  if (streamStatus === 'reconnecting') {
    return reconnectAttempt > 0 ? `Reconnecting (${reconnectAttempt})` : 'Reconnecting';
  }

  if (streamStatus === 'disconnected') {
    return 'Live updates unavailable';
  }

  if (streamStatus === 'connecting') {
    return 'Connecting live updates';
  }

  if (streamStatus === 'connected') {
    return 'Live';
  }

  return null;
}

interface AssistantRunCardProps {
  run: ChatExecutionRun;
  subagents: SubagentSessionRecord[];
  streamStatus: StreamStatus;
  streamReconnectAttempt: number;
  streamErrorMessage: string | null;
  cancellingSubagentId: string | null;
  onOpenSubagent: (parentSessionId: string, childSessionId: string) => void;
  onCancelSubagent: (parentSessionId: string, childSessionId: string) => void;
}

export function AssistantRunCard({
  run,
  subagents,
  streamStatus,
  streamReconnectAttempt,
  streamErrorMessage,
  cancellingSubagentId,
  onOpenSubagent,
  onCancelSubagent,
}: AssistantRunCardProps) {
  const streamLabel = streamCopy(streamStatus, streamReconnectAttempt);
  const isResolved = run.status === 'completed' || run.status === 'failed';
  const summaryText =
    run.finalText ||
    (run.status === 'awaiting_approval'
      ? 'Execution paused while an approval is pending.'
      : run.status === 'failed'
        ? run.errorMessage || 'Execution ended with an error.'
        : 'Execution in progress.');

  return (
    <article className="animate-fade-in flex gap-3.5">
      <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-border/80 bg-muted/40 text-muted-foreground">
        <Bot className="h-3.5 w-3.5" />
      </div>

      <div className="w-full max-w-[min(72ch,86%)] space-y-3">
        <div className="rounded-[1.35rem] border border-border/70 bg-[color-mix(in_srgb,white_90%,var(--color-muted)_10%)] px-4 py-3 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant={runStatusVariant(run.status)}>{run.status}</Badge>
                <span className="text-[11px] font-medium uppercase tracking-[0.16em] text-muted-foreground">
                  Assistant run
                </span>
                {streamLabel ? (
                  <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground">
                    {streamStatus === 'connected' ? (
                      <Activity className="h-3 w-3" />
                    ) : (
                      <WifiOff className="h-3 w-3" />
                    )}
                    {streamLabel}
                  </span>
                ) : null}
              </div>
              <p className="mt-2 whitespace-pre-wrap text-[15px] leading-7 text-foreground">
                {summaryText}
              </p>
            </div>

            <div className="shrink-0 text-[11px] text-muted-foreground">
              {formatElapsed(run)}
            </div>
          </div>

          {streamErrorMessage && streamStatus !== 'connected' ? (
            <p className="mt-2 text-xs text-muted-foreground">{streamErrorMessage}</p>
          ) : null}

          {run.steps.length > 0 ? (
            <details className="group mt-3" open={!isResolved}>
              <summary className="cursor-pointer list-none text-[12px] font-medium text-muted-foreground hover:text-foreground">
                <span className="inline-flex items-center gap-1">
                  <span className="text-[10px] opacity-70 transition-transform group-open:rotate-90">
                    ▶
                  </span>
                  {run.steps.length} step{run.steps.length === 1 ? '' : 's'}
                </span>
              </summary>
              <div className="mt-3 space-y-2.5">
                {run.steps.map((step) => (
                  <RunStepRow key={step.id} step={step} />
                ))}
              </div>
            </details>
          ) : null}
        </div>

        {subagents.map((subagent) => (
          <ParentSubagentInlineCard
            key={subagent.id}
            subagent={subagent}
            isCancelling={cancellingSubagentId === subagent.id}
            onOpen={onOpenSubagent}
            onCancel={onCancelSubagent}
          />
        ))}
      </div>
    </article>
  );
}
