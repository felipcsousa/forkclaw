import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import type { ChatExecutionRun } from '../hooks/controllers/chatExecutionState';
import { AssistantRunCard } from './AssistantRunCard';

vi.mock('./ParentSubagentInlineCard', () => ({
  ParentSubagentInlineCard: () => null,
}));

const baseRun: ChatExecutionRun = {
  id: 'run-1',
  taskRunId: 'run-1',
  sessionId: 'session-1',
  prompt: 'Run a guarded shell command.',
  userMessageId: 'message-1',
  assistantMessageId: null,
  createdAt: '2026-03-12T13:00:00Z',
  startedAt: '2026-03-12T13:00:00Z',
  finishedAt: null,
  status: 'running',
  finalText: null,
  errorMessage: null,
  steps: [],
};

describe('AssistantRunCard', () => {
  it('renders reconnecting stream copy with the current attempt count', () => {
    render(
      <AssistantRunCard
        run={baseRun}
        subagents={[]}
        streamStatus="reconnecting"
        streamReconnectAttempt={2}
        streamErrorMessage={null}
        cancellingSubagentId={null}
        onOpenSubagent={() => undefined}
        onCancelSubagent={() => undefined}
      />,
    );

    expect(screen.getByText('Reconnecting (2)')).toBeInTheDocument();
    expect(screen.getByText('Execution in progress.')).toBeInTheDocument();
  });

  it('renders disconnected and approval-pending copy for paused runs', () => {
    render(
      <AssistantRunCard
        run={{
          ...baseRun,
          status: 'awaiting_approval',
        }}
        subagents={[]}
        streamStatus="disconnected"
        streamReconnectAttempt={0}
        streamErrorMessage="Live stream disconnected. Falling back to session refresh."
        cancellingSubagentId={null}
        onOpenSubagent={() => undefined}
        onCancelSubagent={() => undefined}
      />,
    );

    expect(screen.getByText('Live updates unavailable')).toBeInTheDocument();
    expect(
      screen.getByText('Execution paused while an approval is pending.'),
    ).toBeInTheDocument();
    expect(
      screen.getByText('Live stream disconnected. Falling back to session refresh.'),
    ).toBeInTheDocument();
  });
});
