import { render, screen } from '@testing-library/react';
import { vi } from 'vitest';

import { ChatComposer } from './ChatComposer';

describe('ChatComposer', () => {
  it('renders the idle send action by default', () => {
    const onSubmit = vi.fn();

    const { container } = render(
      <ChatComposer
        draft=""
        disabled={false}
        isSending={false}
        sessionTitle="Persistent Chat"
        onDraftChange={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    expect(screen.getByRole('button', { name: 'Send' })).toBeInTheDocument();
    expect(container.querySelector('svg.animate-spin')).toBeNull();
  });

  it('shows a spinner and sending label while a message is sending', () => {
    const onSubmit = vi.fn();

    const { container } = render(
      <ChatComposer
        draft=""
        disabled={false}
        isSending
        sessionTitle="Persistent Chat"
        onDraftChange={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    expect(screen.getByRole('button', { name: 'Sending…' })).toBeInTheDocument();
    expect(container.querySelector('svg.animate-spin')).not.toBeNull();
  });
});
