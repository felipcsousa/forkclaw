import type {
  SubagentLifecycleStatus,
  SubagentRunRecord,
  SubagentSessionRecord,
} from './backend';

export interface ParsedSubagentSummary {
  status: string;
  goal: string;
  summary: string;
  key_findings: string[];
  files_touched: string[];
  tools_used: string[];
  estimated_cost_usd: number;
  started_at: string | null;
  finished_at: string | null;
}

export function parseSubagentSummary(
  subagent: SubagentSessionRecord | null,
): ParsedSubagentSummary | null {
  if (!subagent?.run.final_output_json) {
    return null;
  }

  try {
    const payload = JSON.parse(subagent.run.final_output_json) as Partial<ParsedSubagentSummary>;
    return {
      status: typeof payload.status === 'string' ? payload.status : subagent.run.lifecycle_status,
      goal:
        typeof payload.goal === 'string' && payload.goal
          ? payload.goal
          : subagent.delegated_goal || subagent.title,
      summary:
        typeof payload.summary === 'string' && payload.summary
          ? payload.summary
          : subagent.run.final_summary || '',
      key_findings: Array.isArray(payload.key_findings)
        ? payload.key_findings.filter((item): item is string => typeof item === 'string')
        : [],
      files_touched: Array.isArray(payload.files_touched)
        ? payload.files_touched.filter((item): item is string => typeof item === 'string')
        : [],
      tools_used: Array.isArray(payload.tools_used)
        ? payload.tools_used.filter((item): item is string => typeof item === 'string')
        : [],
      estimated_cost_usd:
        typeof payload.estimated_cost_usd === 'number'
          ? payload.estimated_cost_usd
          : subagent.run.estimated_cost_usd || 0,
      started_at: typeof payload.started_at === 'string' ? payload.started_at : null,
      finished_at: typeof payload.finished_at === 'string' ? payload.finished_at : null,
    };
  } catch {
    return null;
  }
}

export function subagentStatusVariant(status: string) {
  if (status === 'completed') {
    return 'success' as const;
  }

  if (status === 'failed' || status === 'timed_out') {
    return 'destructive' as const;
  }

  if (status === 'queued' || status === 'running') {
    return 'warning' as const;
  }

  return 'secondary' as const;
}

export function subagentStatusCopy(status: string) {
  if (status === 'cancelled') {
    return 'Interrupted before a normal finish.';
  }

  if (status === 'failed') {
    return 'Ended with an execution error.';
  }

  if (status === 'timed_out') {
    return 'Stopped after reaching the execution timeout.';
  }

  if (status === 'queued') {
    return 'Waiting for a local worker slot.';
  }

  if (status === 'running') {
    return 'Running as a separate child session.';
  }

  return 'Completed and posted a summary back to the parent.';
}

export function canCancelSubagent(status: SubagentLifecycleStatus) {
  return status === 'queued' || status === 'running';
}

export function formatTimestamp(value: string | null | undefined) {
  if (!value) {
    return 'Unknown';
  }

  try {
    return new Date(value).toLocaleString([], {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return value;
  }
}

export function formatDuration(run: SubagentRunRecord) {
  if (!run.started_at) {
    return 'Not started';
  }

  const startedAt = new Date(run.started_at).getTime();
  const finishedAt = run.finished_at ? new Date(run.finished_at).getTime() : Date.now();
  if (Number.isNaN(startedAt) || Number.isNaN(finishedAt)) {
    return 'Unknown';
  }

  const seconds = Math.max(Math.round((finishedAt - startedAt) / 1000), 0);
  if (seconds < 60) {
    return `${seconds}s`;
  }

  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  return remainingSeconds > 0 ? `${minutes}m ${remainingSeconds}s` : `${minutes}m`;
}

export function formatEstimatedCost(value: number | null | undefined) {
  if (typeof value !== 'number' || value <= 0) {
    return 'N/A';
  }

  return `$${value.toFixed(4)}`;
}

export function anchoredSubagentsForMessage(
  subagents: SubagentSessionRecord[],
  messageId: string,
) {
  return subagents.filter((item) => item.run.launcher_message_id === messageId);
}
