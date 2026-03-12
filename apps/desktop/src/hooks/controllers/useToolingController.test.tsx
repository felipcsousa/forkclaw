import { act, renderHook, waitFor } from '@testing-library/react';
import type { Dispatch, SetStateAction } from 'react';
import { vi } from 'vitest';

import { useToolingController } from './useToolingController';

const mockFetchSkills = vi.fn();
const mockFetchToolCalls = vi.fn();
const mockFetchToolCatalog = vi.fn();
const mockFetchToolPermissions = vi.fn();
const mockFetchToolPolicy = vi.fn();
const mockUpdateSkill = vi.fn();
const mockUpdateToolPermission = vi.fn();
const mockUpdateToolPolicy = vi.fn();

vi.mock('../../lib/backend/tools', () => ({
  fetchSkills: () => mockFetchSkills(),
  fetchToolCalls: () => mockFetchToolCalls(),
  fetchToolCatalog: () => mockFetchToolCatalog(),
  fetchToolPermissions: () => mockFetchToolPermissions(),
  fetchToolPolicy: () => mockFetchToolPolicy(),
  updateSkill: (skillKey: string, payload: unknown) =>
    mockUpdateSkill(skillKey, payload),
  updateToolPermission: (toolName: string, level: string) =>
    mockUpdateToolPermission(toolName, level),
  updateToolPolicy: (profileId: string) => mockUpdateToolPolicy(profileId),
}));

function createRunAsyncAction() {
  return async <T,>(
    action: () => Promise<T>,
    options: { setPending?: Dispatch<SetStateAction<boolean>> },
  ): Promise<T | null> => {
    options.setPending?.(true);
    try {
      return await action();
    } finally {
      options.setPending?.(false);
    }
  };
}

describe('useToolingController', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('refreshes the tooling snapshot after a permission change', async () => {
    mockUpdateToolPermission.mockResolvedValue(undefined);
    mockFetchToolPolicy.mockResolvedValue({ profile_id: 'minimal' });
    mockFetchToolPermissions.mockResolvedValue({
      workspace_root: '/workspace',
      items: [{ id: 'perm-1', tool_name: 'list_files', permission_level: 'allow' }],
    });
    mockFetchSkills.mockResolvedValue({
      strategy: 'all_eligible',
      items: [{ key: 'skill-1', enabled: true }],
    });

    const { result } = renderHook(() =>
      useToolingController({
        runAsyncAction: createRunAsyncAction(),
      }),
    );

    await act(async () => {
      await result.current.handleChangeToolPermission('list_files', 'allow');
    });

    await waitFor(() => {
      expect(mockUpdateToolPermission).toHaveBeenCalledWith(
        'list_files',
        'allow',
      );
      expect(mockFetchToolPolicy).toHaveBeenCalledTimes(1);
      expect(mockFetchToolPermissions).toHaveBeenCalledTimes(1);
      expect(mockFetchSkills).toHaveBeenCalledTimes(1);
      expect(result.current.workspaceRoot).toBe('/workspace');
      expect(result.current.toolPermissions).toEqual([
        { id: 'perm-1', tool_name: 'list_files', permission_level: 'allow' },
      ]);
    });
  });
});
