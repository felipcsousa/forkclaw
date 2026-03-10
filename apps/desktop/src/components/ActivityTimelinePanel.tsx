import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import type { ActivityTimelineItemRecord } from '../lib/backend';

interface ActivityTimelinePanelProps {
  items: ActivityTimelineItemRecord[];
  isLoading: boolean;
}

function formatMetric(durationMs: number | null, estimatedCostUsd: number | null) {
  const parts: string[] = [];

  if (durationMs !== null) {
    parts.push(`${Math.max(durationMs / 1000, 0).toFixed(2)}s`);
  }

  if (estimatedCostUsd !== null && estimatedCostUsd > 0) {
    parts.push(`$${estimatedCostUsd.toFixed(4)}`);
  }

  return parts.length > 0 ? parts.join(' · ') : null;
}

function formatTimestamp(raw: string) {
  try {
    const d = new Date(raw);
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) +
      ', ' +
      d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch {
    return raw;
  }
}

function statusVariant(status: string) {
  if (status === 'completed' || status === 'active' || status === 'running') {
    return 'success' as const;
  }

  if (status === 'failed') {
    return 'destructive' as const;
  }

  return 'secondary' as const;
}

export function ActivityTimelinePanel({
  items,
  isLoading,
}: ActivityTimelinePanelProps) {
  return (
    <div className="space-y-5 animate-fade-in">

      {isLoading && items.length === 0 ? (
        <p className="empty-dashed rounded-[1rem] px-4 py-6 text-sm text-muted-foreground animate-pulse">
          Loading recent activity...
        </p>
      ) : items.length === 0 ? (
        <div className="empty-dashed rounded-xl px-5 py-7">
          <p className="text-sm font-medium text-foreground">No activity recorded yet.</p>
          <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
            Run the agent, use tools, or trigger a scheduled job to populate the
            timeline.
          </p>
        </div>
      ) : (
        <div className="rounded-xl border border-border bg-card overflow-hidden shadow-sm divide-y divide-border/60">
          {items.map((item) => (
            <div key={item.task_run_id} className="animate-appear hover:bg-muted/30 transition-colors flex flex-col p-4 sm:px-5">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 min-w-0">
                <div className="flex items-center gap-2.5 min-w-0">
                  <h3 className="truncate text-[13px] font-semibold tracking-tight text-foreground">
                    {item.session_title || item.task_title}
                  </h3>
                  <Badge variant="secondary" className="px-1.5 py-0 text-[9px] min-h-[1.125rem]">
                    {item.task_kind}
                  </Badge>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <span className="text-[11px] font-medium text-muted-foreground">
                    {formatMetric(item.duration_ms, item.estimated_cost_usd) || `${item.entries.length} entries`}
                  </span>
                  <Badge variant={statusVariant(item.status)} className="font-medium px-2 py-0 text-[10px]">
                    {item.status}
                  </Badge>
                </div>
              </div>

              {item.error_message ? (
                <div className="mt-3 rounded-md bg-destructive/5 px-3 py-2 text-[12px] text-destructive border border-destructive/20">
                  <span className="font-semibold">Error: </span>
                  {item.error_message}
                </div>
              ) : null}

              {item.resolved_skills.length > 0 ? (
                <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
                  <Badge variant="outline" className="px-2 py-0 text-[10px]">
                    Guided by: {item.resolved_skills.map((skill) => skill.name).join(', ')}
                  </Badge>
                  {item.skill_strategy ? (
                    <span>Strategy: {item.skill_strategy}</span>
                  ) : null}
                </div>
              ) : null}

              {item.entries.length > 0 ? (
                <div className="mt-3">
                  <details className="group/details">
                    <summary className="text-[11px] font-medium text-muted-foreground/80 cursor-pointer list-none flex items-center gap-1.5 hover:text-foreground">
                      <span className="text-[10px] opacity-70 transition-transform group-open/details:rotate-90">▶</span>
                      View {item.entries.length} detailed entries
                    </summary>
                    <div className="mt-3 space-y-3 pl-2 border-l border-border/80 ml-[5px]">
                      {item.entries.map((entry) => (
                        <div key={entry.id} className="relative pl-4 space-y-0.5">
                          <span className={cn(
                            'absolute -left-[5px] top-1.5 h-2 w-2 rounded-full border shadow-xs',
                            entry.status === 'completed' || entry.status === 'active' ? 'border-emerald-300 bg-emerald-100' :
                              entry.status === 'failed' ? 'border-destructive/30 bg-destructive/10' :
                                'border-border bg-background',
                          )} />
                          <div className="flex flex-wrap items-center gap-1.5 text-[10px] font-medium text-muted-foreground">
                            <span>{entry.type}</span>
                            <span>&middot;</span>
                            <span>{formatTimestamp(entry.created_at)}</span>
                          </div>
                          <p className="text-[12px] font-medium text-foreground tracking-tight">{entry.title}</p>
                          {entry.summary ? (
                            <p className="text-[11px] leading-relaxed text-muted-foreground opacity-90">
                              {entry.summary}
                            </p>
                          ) : null}
                          {entry.error_message ? (
                            <p className="text-[11px] text-destructive mt-0.5">{entry.error_message}</p>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  </details>
                </div>
              ) : null}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
