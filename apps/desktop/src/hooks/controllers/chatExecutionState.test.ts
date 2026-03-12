import { describe, expect, it } from 'vitest';

import type { MessageRecord } from '../../lib/backend';
import {
  buildChatTimelineItems,
  chatExecutionStateReducer,
  createInitialChatExecutionState,
} from './chatExecutionState';

const baseMessage: MessageRecord = {
  id: 'message-1',
  session_id: 'session-1',
  role: 'user',
  status: 'committed',
  sequence_number: 1,
  content_text: 'Run the workspace checks.',
  created_at: '2026-03-12T13:00:00Z',
  updated_at: '2026-03-12T13:00:00Z',
};

describe('chatExecutionStateReducer', () => {
  it('tracks a run by task_run_id from optimistic start through final assistant message', () => {
    let state = createInitialChatExecutionState();

    state = chatExecutionStateReducer(state, {
      type: 'run/optimistic-created',
      sessionId: 'session-1',
      localRunId: 'optimistic:1',
      prompt: 'Run the workspace checks.',
      createdAt: '2026-03-12T13:00:00Z',
    });
    state = chatExecutionStateReducer(state, {
      type: 'run/response-bound',
      sessionId: 'session-1',
      localRunId: 'optimistic:1',
      response: {
        task_run_id: 'run-1',
        user_message_id: 'message-1',
      },
    });
    state = chatExecutionStateReducer(state, {
      type: 'run/event-received',
      sessionId: 'session-1',
      event: {
        event_id: 'evt-tool-1',
        event_type: 'tool_call.requested',
        session_id: 'session-1',
        task_run_id: 'run-1',
        created_at: '2026-03-12T13:00:01Z',
        raw: {},
        tool: {
          tool_call_id: 'call-1',
          tool_name: 'read_file',
          status: 'running',
          input_json: '{"path":"README.md"}',
        },
      },
    });
    state = chatExecutionStateReducer(state, {
      type: 'run/event-received',
      sessionId: 'session-1',
      event: {
        event_id: 'evt-finished-1',
        event_type: 'assistant.message.completed',
        session_id: 'session-1',
        task_run_id: 'run-1',
        created_at: '2026-03-12T13:00:02Z',
        raw: {},
        assistant_message: {
          assistant_message_id: 'message-2',
          user_message_id: 'message-1',
          content_text: 'Workspace checks finished successfully.',
        },
      },
    });

    const run = state.runsById['run-1'];
    expect(run).toBeDefined();
    expect(run?.userMessageId).toBe('message-1');
    expect(run?.assistantMessageId).toBe('message-2');
    expect(run?.status).toBe('completed');
    expect(run?.finalText).toBe('Workspace checks finished successfully.');
    expect(run?.steps).toEqual([
      expect.objectContaining({
        id: 'call-1',
        kind: 'tool',
        title: 'read_file',
        status: 'running',
      }),
    ]);
  });

  it('summarizes shell output without exposing stdout or stderr by default', () => {
    const state = chatExecutionStateReducer(createInitialChatExecutionState(), {
      type: 'run/event-received',
      sessionId: 'session-1',
      event: {
        event_id: 'evt-shell-1',
        event_type: 'tool_call.completed',
        session_id: 'session-1',
        task_run_id: 'run-shell-1',
        created_at: '2026-03-12T13:10:00Z',
        raw: {},
        tool: {
          tool_call_id: 'call-shell-1',
          tool_name: 'shell',
          status: 'completed',
          started_at: '2026-03-12T13:09:58Z',
          finished_at: '2026-03-12T13:10:00Z',
          input_json: '{"cmd":"npm test"}',
          output_json:
            '{"exit_code":0,"stdout":"PASS src/app.test.ts\\n8 passed","stderr":""}',
        },
      },
    });

    const run = state.runsById['run-shell-1'];
    expect(run?.steps).toEqual([
      expect.objectContaining({
        title: 'shell',
        status: 'completed',
        durationMs: 2000,
        summary: 'Exit 0 · PASS src/app.test.ts',
      }),
    ]);
    expect(run?.steps[0]?.details).toContain('stdout');
  });
});

describe('buildChatTimelineItems', () => {
  it('inserts runs after the triggering user message and hides duplicate persisted assistant messages', () => {
    const state = chatExecutionStateReducer(createInitialChatExecutionState(), {
      type: 'run/event-received',
      sessionId: 'session-1',
      event: {
        event_id: 'evt-final-1',
        event_type: 'assistant.message.completed',
        session_id: 'session-1',
        task_run_id: 'run-1',
        created_at: '2026-03-12T13:00:02Z',
        raw: {},
        assistant_message: {
          assistant_message_id: 'message-2',
          user_message_id: 'message-1',
          content_text: 'Workspace checks finished successfully.',
        },
      },
    });

    const items = buildChatTimelineItems({
      activeSessionId: 'session-1',
      messages: [
        baseMessage,
        {
          ...baseMessage,
          id: 'message-2',
          role: 'assistant',
          sequence_number: 2,
          content_text: 'Workspace checks finished successfully.',
        },
      ],
      runsState: state,
      subagents: [],
    });

    expect(items.map((item) => item.kind)).toEqual(['message', 'run']);
    expect(items[1]).toEqual(
      expect.objectContaining({
        kind: 'run',
        run: expect.objectContaining({
          taskRunId: 'run-1',
          assistantMessageId: 'message-2',
        }),
      }),
    );
  });
});
