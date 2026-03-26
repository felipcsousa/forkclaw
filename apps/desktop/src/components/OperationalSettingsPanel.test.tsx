import { fireEvent, render } from '@testing-library/react';
import { vi } from 'vitest';

import { OperationalSettingsPanel } from './OperationalSettingsPanel';
import type { OperationalSettingsUpdate } from '../lib/backend';

describe('OperationalSettingsPanel', () => {
  it('prevents double-submissions when saving is in progress', () => {
    const onSave = vi.fn();
    const draft: OperationalSettingsUpdate = {
      provider: 'openai',
      workspace_root: '',
      max_iterations: 10,
      heartbeat_interval_seconds: 60,
      provider_api_key: '',
      provider_model: 'gpt-4o',
      budget_daily_cents: 100,
      budget_monthly_cents: 1000,
      default_view: 'chat',
    };

    const { container } = render(
      <OperationalSettingsPanel
        settings={null}
        draft={draft}
        isLoading={false}
        isSaving={true}
        onDraftChange={vi.fn()}
        onSave={onSave}
      />
    );

    const form = container.querySelector('form');
    fireEvent.submit(form!);

    expect(onSave).not.toHaveBeenCalled();
  });
});
