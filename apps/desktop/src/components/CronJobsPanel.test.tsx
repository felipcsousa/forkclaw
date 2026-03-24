import { render, fireEvent } from '@testing-library/react';
import { vi } from 'vitest';
import { CronJobsPanel } from './CronJobsPanel';

describe('CronJobsPanel', () => {
  it('does not call onCreateJob when submitted while creating or mutating', () => {
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

    const form = container.querySelector('form');
    if (form) {
      fireEvent.submit(form);
    }

    expect(onCreateJob).not.toHaveBeenCalled();
  });
});
