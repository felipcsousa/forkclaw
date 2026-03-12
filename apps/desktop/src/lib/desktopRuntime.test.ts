import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { invoke, isTauri } from '@tauri-apps/api/core';

import {
  resetDesktopRuntimeConnectionCache,
  resolveBackendConnectionInfo,
} from './desktopRuntime';

vi.mock('@tauri-apps/api/core', () => ({
  invoke: vi.fn(),
  isTauri: vi.fn(),
}));

describe('desktopRuntime', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resetDesktopRuntimeConnectionCache();
  });

  afterEach(() => {
    resetDesktopRuntimeConnectionCache();
  });

  it('falls back to the localhost backend outside tauri', async () => {
    vi.mocked(isTauri).mockReturnValue(false);

    await expect(resolveBackendConnectionInfo()).resolves.toEqual({
      baseUrl: 'http://127.0.0.1:8000',
      bootstrapToken: null,
      managedByShell: false,
    });
    expect(invoke).not.toHaveBeenCalled();
  });

  it('loads and caches the managed backend connection info in tauri', async () => {
    vi.mocked(isTauri).mockReturnValue(true);
    vi.mocked(invoke).mockResolvedValue({
      baseUrl: 'http://127.0.0.1:43123',
      bootstrapToken: 'desktop-token',
      managedByShell: true,
    });

    const first = await resolveBackendConnectionInfo();
    const second = await resolveBackendConnectionInfo();

    expect(first).toEqual({
      baseUrl: 'http://127.0.0.1:43123',
      bootstrapToken: 'desktop-token',
      managedByShell: true,
    });
    expect(second).toEqual(first);
    expect(invoke).toHaveBeenCalledTimes(1);
    expect(invoke).toHaveBeenCalledWith('get_backend_connection_info');
  });
});
