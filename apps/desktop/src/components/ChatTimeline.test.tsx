import { fireEvent, render, screen } from '@testing-library/react';
import { vi } from 'vitest';

import { ChatTimeline } from './ChatTimeline';

function makeSession(overrides: Record<string, unknown> = {}) {
  return {
    id: 'session-1',
    agent_id: 'agent-1',
    kind: 'main',
    parent_session_id: null,
    root_session_id: 'session-1',
    spawn_depth: 0,
    title: 'Persistent Chat',
    summary: null,
    status: 'active',
    delegated_goal: null,
    delegated_context_snapshot: null,
    tool_profile: null,
    model_override: null,
    max_iterations: null,
    started_at: '2026-03-08T12:00:00Z',
    last_message_at: null,
    created_at: '2026-03-08T12:00:00Z',
    updated_at: '2026-03-08T12:00:00Z',
    ...overrides,
  };
}

function makeMessage(overrides: Record<string, unknown> = {}) {
  return {
    id: 'message-2',
    session_id: 'session-1',
    role: 'assistant',
    status: 'committed',
    sequence_number: 2,
    content_text: 'Reply with recalled context.',
    created_at: '2026-03-08T12:01:00Z',
    updated_at: '2026-03-08T12:01:00Z',
    ...overrides,
  };
}

describe('ChatTimeline', () => {
  it('renders a subtle recall pill for assistant messages with recalled memories', () => {
    const onOpenRecall = vi.fn();

    render(
      <ChatTimeline
        session={makeSession() as never}
        timelineItems={[
          {
            kind: 'message',
            message: makeMessage(),
          } as never,
        ]}
        recallSummaries={[
          {
            assistant_message_id: 'message-2',
            created_at: '2026-03-08T12:01:00Z',
            recalled_count: 1,
            reason_summary: '1 memory item injected for recall.',
            items: [],
          },
        ]}
        subagents={[]}
        executionStreamStatus="idle"
        executionStreamReconnectAttempt={0}
        executionStreamErrorMessage={null}
        isLoading={false}
        isSending={false}
        cancellingSubagentId={null}
        onOpenRecall={onOpenRecall}
        onOpenSubagent={vi.fn()}
        onCancelSubagent={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: '1 memory used' }));

    expect(onOpenRecall).toHaveBeenCalledWith('message-2');
  });
});
