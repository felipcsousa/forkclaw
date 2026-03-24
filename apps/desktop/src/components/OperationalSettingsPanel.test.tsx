import { render, fireEvent } from '@testing-library/react';
import { vi } from 'vitest';
import { OperationalSettingsPanel } from './OperationalSettingsPanel';

describe('OperationalSettingsPanel', () => {
  it('does not call onSave when submitted while disabled', () => {
    const onSave = vi.fn();
    const { container } = render(
      <OperationalSettingsPanel
        settings={null}
        draft={{
          provider: 'openai',
          model_name: '',
          workspace_root: '',
          max_iterations_per_execution: 1,
          activity_poll_seconds: 1,
          heartbeat_interval_seconds: 60,
          daily_budget_usd: 1,
          monthly_budget_usd: 1,
          default_view: 'chat',
        }}
        isLoading={false}
        isSaving={true}
        onDraftChange={vi.fn()}
        onSave={onSave}
      />
    );

    const form = container.querySelector('form');
    if (form) {
      fireEvent.submit(form);
    }

    expect(onSave).not.toHaveBeenCalled();
  });
});
