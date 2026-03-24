import { render, fireEvent } from '@testing-library/react';
import { vi } from 'vitest';
import { AgentSettingsPanel } from './AgentSettingsPanel';

describe('AgentSettingsPanel', () => {
  it('does not call onSave when submitted while disabled', () => {
    const onSave = vi.fn();
    const { container } = render(
      <AgentSettingsPanel
        agent={null}
        draft={{
          name: '',
          description: '',
          identity_text: '',
          soul_text: '',
          user_context_text: '',
          policy_base_text: '',
          model_name: ''
        }}
        isLoading={false}
        isSaving={true}
        isResetting={false}
        onDraftChange={vi.fn()}
        onSave={onSave}
        onReset={vi.fn()}
      />
    );

    const form = container.querySelector('form');
    if (form) {
      fireEvent.submit(form);
    }

    expect(onSave).not.toHaveBeenCalled();
  });
});
