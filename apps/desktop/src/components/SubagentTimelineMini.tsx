import { Badge } from '@/components/ui/badge';
import {
  formatEstimatedCost,
  formatTimestamp,
  subagentStatusVariant,
} from '@/lib/subagents';
import type { SubagentTimelineEventRecord } from '../lib/backend';

interface SubagentTimelineMiniProps {
  events: SubagentTimelineEventRecord[];
}

export function SubagentTimelineMini({ events }: SubagentTimelineMiniProps) {
  if (events.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-border px-4 py-4 text-sm text-muted-foreground">
        No timeline entries yet.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {events.map((event) => (
        <div
          key={event.id}
          className="relative rounded-2xl border border-border/70 bg-background px-4 py-3"
        >
          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant={subagentStatusVariant(event.status || 'queued')}>
                  {event.event_type.replace('subagent.', '')}
                </Badge>
                <span className="text-xs text-muted-foreground">
                  {formatTimestamp(event.created_at)}
                </span>
              </div>
              <p className="mt-2 text-sm leading-relaxed text-foreground">
                {event.summary}
              </p>
            </div>

            <div className="flex flex-col items-start gap-1 text-[11px] text-muted-foreground sm:items-end">
              {event.task_run_id ? <span>run {event.task_run_id.slice(0, 8)}</span> : null}
              {typeof event.estimated_cost_usd === 'number' ? (
                <span>{formatEstimatedCost(event.estimated_cost_usd)}</span>
              ) : null}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
