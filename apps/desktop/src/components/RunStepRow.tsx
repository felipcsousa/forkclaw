import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import type { ChatExecutionStep } from '../hooks/controllers/chatExecutionState';

function statusVariant(status: string) {
  if (status === 'completed' || status === 'running') {
    return 'success' as const;
  }

  if (status === 'failed' || status === 'denied') {
    return 'destructive' as const;
  }

  if (status === 'awaiting_approval' || status === 'pending') {
    return 'warning' as const;
  }

  return 'secondary' as const;
}

function formatDuration(durationMs: number | null) {
  if (durationMs === null) {
    return null;
  }

  if (durationMs < 1000) {
    return `${durationMs}ms`;
  }

  return `${(durationMs / 1000).toFixed(durationMs >= 10_000 ? 0 : 1)}s`;
}

interface RunStepRowProps {
  step: ChatExecutionStep;
}

export function RunStepRow({ step }: RunStepRowProps) {
  const duration = formatDuration(step.durationMs);

  return (
    <div className="rounded-xl border border-border/70 bg-background/80 px-3 py-2.5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-medium text-foreground">{step.title}</p>
            <Badge variant={statusVariant(step.status)} className="px-1.5 py-0 text-[10px]">
              {step.status}
            </Badge>
            {duration ? (
              <span className="text-[11px] text-muted-foreground">{duration}</span>
            ) : null}
          </div>
          <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
            {step.summary}
          </p>
        </div>
      </div>

      {step.details ? (
        <details className="group mt-2">
          <summary className="cursor-pointer list-none text-[11px] font-medium text-muted-foreground hover:text-foreground">
            <span className="inline-flex items-center gap-1">
              <span
                className={cn(
                  'text-[10px] opacity-70 transition-transform group-open:rotate-90',
                )}
              >
                ▶
              </span>
              Details
            </span>
          </summary>
          <pre className="mt-2 overflow-x-auto rounded-lg border border-border/70 bg-muted/20 p-3 text-[11px] leading-relaxed text-muted-foreground">
            {step.details}
          </pre>
        </details>
      ) : null}
    </div>
  );
}
