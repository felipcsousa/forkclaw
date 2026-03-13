import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { fetchMemoryItems } from './memory';
import { resolveBackendConnectionInfo } from '../desktopRuntime';

vi.mock('../desktopRuntime', () => ({
  resolveBackendConnectionInfo: vi.fn(),
}));

describe('memory backend client', () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.clearAllMocks();
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ items: [] }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    vi.mocked(resolveBackendConnectionInfo).mockResolvedValue({
      baseUrl: 'http://127.0.0.1:43123',
      bootstrapToken: 'desktop-token',
      managedByShell: true,
    });
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it('encodes active memory filters into the request query string', async () => {
    await fetchMemoryItems({
      kind: 'stable',
      query: 'oolong',
      scope: 'profile',
      sourceKind: 'manual',
      state: 'hidden',
      mode: 'manual',
      recallStatus: 'hidden',
    });

    expect(globalThis.fetch).toHaveBeenCalledTimes(1);
    const [url, init] = vi.mocked(globalThis.fetch).mock.calls[0];

    expect(url).toBe(
      'http://127.0.0.1:43123/memory/items?kind=stable&query=oolong&scope=profile&source_kind=manual&state=hidden&mode=manual&recall_status=hidden',
    );
    expect(init?.method).toBe('GET');
  });
});
