import { fireEvent, render, screen } from '@testing-library/react';
import { vi } from 'vitest';

import { CronJobsPanel } from './CronJobsPanel';

describe('CronJobsPanel', () => {
  it('prevents double-submissions when creating is in progress', () => {
    const onCreateJob = vi.fn();
    const { container } = render(
      <CronJobsPanel
        jobs={[]}
        history={[]}
        heartbeat={null}
        isLoading={false}
        isCreating={true}
        isMutating={false}
        onCreateJob={onCreateJob}
        onPauseJob={vi.fn()}
        onActivateJob={vi.fn()}
        onRemoveJob={vi.fn()}
      />
    );

    fireEvent.click(screen.getByRole('tab', { name: 'Create' }));

    const form = container.querySelector('form');
    fireEvent.submit(form!);

    expect(onCreateJob).not.toHaveBeenCalled();
  });
});
