import { useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { ActivityTimelineItemRecord } from '../lib/backend';

interface ActivityTimelinePanelProps {
  items: ActivityTimelineItemRecord[];
  isLoading: boolean;
  onOpenSubagent?: (parentSessionId: string, childSessionId: string) => void;
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
    return (
      d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) +
      ', ' +
      d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    );
  } catch {
    return raw;
  }
}

function statusVariant(status: string) {
  if (status === 'completed' || status === 'active' || status === 'running') {
    return 'success' as const;
  }

  if (status === 'failed' || status === 'timed_out') {
    return 'destructive' as const;
  }

  if (status === 'queued') {
    return 'warning' as const;
  }

  return 'secondary' as const;
}

export function ActivityTimelinePanel({
  items,
  isLoading,
  onOpenSubagent,
}: ActivityTimelinePanelProps) {
  const [filter, setFilter] = useState<'all' | 'subagents'>('all');
  const visibleItems =
    filter === 'subagents' ? items.filter((item) => item.lineage) : items;

  return (
    <div className="space-y-5 animate-fade-in">
      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          size="sm"
          variant={filter === 'all' ? 'secondary' : 'ghost'}
          className="h-8 text-xs"
          onClick={() => setFilter('all')}
        >
          All
        </Button>
        <Button
          type="button"
          size="sm"
          variant={filter === 'subagents' ? 'secondary' : 'ghost'}
          className="h-8 text-xs"
          onClick={() => setFilter('subagents')}
        >
          Subagents only
        </Button>
      </div>

      {isLoading && visibleItems.length === 0 ? (
        <p className="empty-dashed rounded-[1rem] px-4 py-6 text-sm text-muted-foreground animate-pulse">
          Loading recent activity...
        </p>
      ) : visibleItems.length === 0 ? (
        <div className="empty-dashed rounded-xl px-5 py-7">
          <p className="text-sm font-medium text-foreground">No activity recorded yet.</p>
          <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
            Run the agent, use tools, or trigger a scheduled job to populate the timeline.
          </p>
        </div>
      ) : (
        <div className="divide-y divide-border/60 overflow-hidden rounded-xl border border-border bg-card shadow-sm">
          {visibleItems.map((item) => (
            <div
              key={item.task_run_id}
              className="animate-appear flex flex-col p-4 transition-colors hover:bg-muted/30 sm:px-5"
            >
              {item.lineage ? (
                <div className="mb-3 rounded-2xl border border-border/70 bg-[color-mix(in_srgb,white_90%,var(--color-muted)_10%)] px-4 py-3">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant={statusVariant(item.lineage.status)}>
                          {item.lineage.status}
                        </Badge>
                        <span className="text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
                          Parent -&gt; Child
                        </span>
                      </div>
                      <p className="mt-2 text-sm font-semibold tracking-tight text-foreground">
                        {item.lineage.parent_session_title || 'Parent session'} -&gt;{' '}
                        {item.lineage.child_session_title || item.session_title || item.task_title}
                      </p>
                      <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                        {item.lineage.goal_summary}
                      </p>
                    </div>
                    {onOpenSubagent ? (
                      <Button
                        type="button"
                        size="sm"
                        variant="secondary"
                        className="h-8 text-xs"
                        onClick={() =>
                          onOpenSubagent(
                            item.lineage!.parent_session_id,
                            item.lineage!.child_session_id,
                          )
                        }
                      >
                        Open child session
                      </Button>
                    ) : null}
                  </div>
                </div>
              ) : null}

              <div className="flex min-w-0 flex-col justify-between gap-3 sm:flex-row sm:items-center">
                <div className="flex min-w-0 items-center gap-2.5">
                  <h3 className="truncate text-[13px] font-semibold tracking-tight text-foreground">
                    {item.session_title || item.task_title}
                  </h3>
                  <Badge variant="secondary" className="min-h-[1.125rem] px-1.5 py-0 text-[9px]">
                    {item.task_kind}
                  </Badge>
                </div>
                <div className="flex shrink-0 items-center gap-3">
                  <span className="text-[11px] font-medium text-muted-foreground">
                    {formatMetric(item.duration_ms, item.estimated_cost_usd) ||
                      `${item.entries.length} entries`}
                  </span>
                  <Badge variant={statusVariant(item.status)} className="px-2 py-0 text-[10px] font-medium">
                    {item.status}
                  </Badge>
                </div>
              </div>

              {item.error_message ? (
                <div className="mt-3 rounded-md border border-destructive/20 bg-destructive/5 px-3 py-2 text-[12px] text-destructive">
                  <span className="font-semibold">Error: </span>
                  {item.error_message}
                </div>
              ) : null}

              {item.resolved_skills.length > 0 ? (
                <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
                  <Badge variant="outline" className="px-2 py-0 text-[10px]">
                    Guided by: {item.resolved_skills.map((skill) => skill.name).join(', ')}
                  </Badge>
                  {item.skill_strategy ? <span>Strategy: {item.skill_strategy}</span> : null}
                </div>
              ) : null}

              {item.entries.length > 0 ? (
                <div className="mt-3">
                  <details className="group/details">
                    <summary className="flex cursor-pointer list-none items-center gap-1.5 text-[11px] font-medium text-muted-foreground/80 hover:text-foreground">
                      <span className="text-[10px] opacity-70 transition-transform group-open/details:rotate-90">
                        ▶
                      </span>
                      View {item.entries.length} detailed entries
                    </summary>
                    <div className="mt-3 ml-[5px] space-y-3 border-l border-border/80 pl-2">
                      {item.entries.map((entry) => (
                        <div key={entry.id} className="relative space-y-0.5 pl-4">
                          <span
                            className={cn(
                              'absolute -left-[5px] top-1.5 h-2 w-2 rounded-full border shadow-xs',
                              entry.status === 'completed' || entry.status === 'active'
                                ? 'border-emerald-300 bg-emerald-100'
                                : entry.status === 'failed'
                                  ? 'border-destructive/30 bg-destructive/10'
                                  : 'border-border bg-background',
                            )}
                          />
                          <div className="flex flex-wrap items-center gap-1.5 text-[10px] font-medium text-muted-foreground">
                            <span>{entry.type}</span>
                            <span>&middot;</span>
                            <span>{formatTimestamp(entry.created_at)}</span>
                          </div>
                          <p className="text-[12px] font-medium tracking-tight text-foreground">
                            {entry.title}
                          </p>
                          {entry.summary ? (
                            <p className="text-[11px] leading-relaxed text-muted-foreground opacity-90">
                              {entry.summary}
                            </p>
                          ) : null}
                          {entry.error_message ? (
                            <p className="mt-0.5 text-[11px] text-destructive">
                              {entry.error_message}
                            </p>
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
