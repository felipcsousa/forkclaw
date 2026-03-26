import { fireEvent, render } from '@testing-library/react';
import { vi } from 'vitest';

import { AgentSettingsPanel } from './AgentSettingsPanel';

describe('AgentSettingsPanel', () => {
  it('prevents double-submissions when saving is in progress', () => {
    const onSave = vi.fn();
    const { container } = render(
      <AgentSettingsPanel
        agent={null}
        draft={{ name: 'Test Agent', model_name: 'gpt-4o', system_message: 'Test message', allow_core_memory: true, tool_permission_policy: 'ask' }}
        isLoading={false}
        isSaving={true}
        isResetting={false}
        onDraftChange={vi.fn()}
        onSave={onSave}
        onReset={vi.fn()}
      />
    );

    const form = container.querySelector('form');
    fireEvent.submit(form!);

    expect(onSave).not.toHaveBeenCalled();
  });
});
