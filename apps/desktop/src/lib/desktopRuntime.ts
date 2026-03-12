import { invoke, isTauri } from '@tauri-apps/api/core';

export interface BackendConnectionInfo {
  baseUrl: string;
  bootstrapToken: string | null;
  managedByShell: boolean;
}

const defaultBackendUrl =
  import.meta.env.VITE_BACKEND_URL?.trim() || 'http://127.0.0.1:8000';

let connectionInfoPromise: Promise<BackendConnectionInfo> | null = null;

export async function resolveBackendConnectionInfo(): Promise<BackendConnectionInfo> {
  if (connectionInfoPromise) {
    return connectionInfoPromise;
  }

  if (!isTauri()) {
    connectionInfoPromise = Promise.resolve({
      baseUrl: defaultBackendUrl,
      bootstrapToken: null,
      managedByShell: false,
    });
    return connectionInfoPromise;
  }

  connectionInfoPromise = invoke<BackendConnectionInfo>('get_backend_connection_info');
  return connectionInfoPromise;
}

export function resetDesktopRuntimeConnectionCache(): void {
  connectionInfoPromise = null;
}
