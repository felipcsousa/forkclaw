import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { fetchHealth } from './backend';
import { resolveBackendConnectionInfo } from './desktopRuntime';

vi.mock('./desktopRuntime', () => ({
  resolveBackendConnectionInfo: vi.fn(),
}));

describe('backend client', () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.clearAllMocks();
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: 'ok', service: 'backend', version: '0.1.0' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it('includes the bootstrap token header when the shell manages the backend', async () => {
    vi.mocked(resolveBackendConnectionInfo).mockResolvedValue({
      baseUrl: 'http://127.0.0.1:43123',
      bootstrapToken: 'desktop-token',
      managedByShell: true,
    });

    await fetchHealth();

    expect(globalThis.fetch).toHaveBeenCalledTimes(1);
    const [url, init] = vi.mocked(globalThis.fetch).mock.calls[0];

    expect(url).toBe('http://127.0.0.1:43123/health');
    expect(init?.method).toBe('GET');
    expect(init?.headers).toBeInstanceOf(Headers);
    expect((init?.headers as Headers).get('Content-Type')).toBe('application/json');
    expect((init?.headers as Headers).get('X-Backend-Bootstrap-Token')).toBe(
      'desktop-token',
    );
  });
});
