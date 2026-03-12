import type { Dispatch, SetStateAction } from 'react';

export type PendingSetter = Dispatch<SetStateAction<boolean>>;

export interface AsyncActionOptions {
  errorMessage: string;
  setPending?: PendingSetter;
  clearError?: boolean;
}

export type RunAsyncAction = <T>(
  action: () => Promise<T>,
  options: AsyncActionOptions,
) => Promise<T | null>;

export function toErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}
