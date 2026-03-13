import { fireEvent, render, screen } from '@testing-library/react';
import { vi } from 'vitest';

import { MemoryRecallSheet } from './MemoryRecallSheet';

describe('MemoryRecallSheet', () => {
  it('shows recalled memories, reasons, and a link back to Memory Studio', () => {
    const onOpenMemory = vi.fn();
    const onOpenChange = vi.fn();

    render(
      <MemoryRecallSheet
        activeRecall={{
          assistant_message_id: 'message-2',
          session_id: 'session-1',
          created_at: '2026-03-08T12:01:00Z',
          reason_summary: '1 memory item injected for recall.',
          items: [
            {
              memory_id: 'memory-1',
              title: 'Tea preference',
              kind: 'stable',
              scope: 'profile',
              source_kind: 'manual',
              source_label: 'Manual',
              importance: 'high',
              reason: 'Matched terms: oolong',
              origin_session_id: null,
              origin_subagent_session_id: null,
            },
          ],
        }}
        errorMessage={null}
        isLoading={false}
        open
        onOpenChange={onOpenChange}
        onOpenMemory={onOpenMemory}
      />,
    );

    expect(screen.getByText('Tea preference')).toBeInTheDocument();
    expect(screen.getByText('Matched terms: oolong')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Open in Memory Studio' }));

    expect(onOpenMemory).toHaveBeenCalledWith('memory-1');
  });
});
