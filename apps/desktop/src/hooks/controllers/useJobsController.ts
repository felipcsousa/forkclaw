import { useCallback, useRef, useState } from 'react';

import {
  activateCronJob,
  createCronJob,
  deleteCronJob,
  fetchCronJobsDashboard,
  pauseCronJob,
  type CronJobCreateInput,
  type CronJobRecord,
  type HeartbeatStatusRecord,
  type TaskRunHistoryRecord,
} from '../../lib/backend/jobs';
import type { RunAsyncAction } from './shared';

export function useJobsController({
  runAsyncAction,
  setErrorMessage,
}: {
  runAsyncAction: RunAsyncAction;
  setErrorMessage: (value: string | null) => void;
}) {
  const [cronJobs, setCronJobs] = useState<CronJobRecord[]>([]);
  const [jobHistory, setJobHistory] = useState<TaskRunHistoryRecord[]>([]);
  const [heartbeat, setHeartbeat] = useState<HeartbeatStatusRecord | null>(null);
  const [isLoadingJobs, setIsLoadingJobs] = useState(false);
  const [isCreatingJob, setIsCreatingJob] = useState(false);
  const [isMutatingJob, setIsMutatingJob] = useState(false);
  const isCreatingJobRef = useRef(false);
  const isMutatingJobRef = useRef(false);

  const loadJobs = useCallback(async () => {
    const response = await runAsyncAction(() => fetchCronJobsDashboard(), {
      setPending: setIsLoadingJobs,
      errorMessage: 'Failed to load scheduler state.',
    });
    if (!response) {
      return null;
    }

    setCronJobs(response.items);
    setJobHistory(response.history);
    setHeartbeat(response.heartbeat);
    return response;
  }, [runAsyncAction]);

  const handleCreateJob = useCallback(
    async (payload: CronJobCreateInput) => {
      if (isCreatingJobRef.current) return null;

      if (!payload.name.trim() || !payload.schedule.trim()) {
        setErrorMessage('Job name and schedule are required.');
        return null;
      }

      isCreatingJobRef.current = true;
      try {
        return await runAsyncAction(() => createCronJob(payload), {
          setPending: setIsCreatingJob,
          errorMessage: 'Failed to create scheduled job.',
        });
      } finally {
        isCreatingJobRef.current = false;
      }
    },
    [runAsyncAction, setErrorMessage],
  );

  const handlePauseJob = useCallback(
    async (jobId: string) => {
      if (isMutatingJobRef.current) return null;
      isMutatingJobRef.current = true;
      try {
        return await runAsyncAction(() => pauseCronJob(jobId), {
          setPending: setIsMutatingJob,
          errorMessage: 'Failed to pause scheduled job.',
        });
      } finally {
        isMutatingJobRef.current = false;
      }
    },
    [runAsyncAction],
  );

  const handleActivateJob = useCallback(
    async (jobId: string) => {
      if (isMutatingJobRef.current) return null;
      isMutatingJobRef.current = true;
      try {
        return await runAsyncAction(() => activateCronJob(jobId), {
          setPending: setIsMutatingJob,
          errorMessage: 'Failed to activate scheduled job.',
        });
      } finally {
        isMutatingJobRef.current = false;
      }
    },
    [runAsyncAction],
  );

  const handleRemoveJob = useCallback(
    async (jobId: string) => {
      if (isMutatingJobRef.current) return null;
      isMutatingJobRef.current = true;
      try {
        return await runAsyncAction(async () => {
          await deleteCronJob(jobId);
          return { ok: true };
        }, {
          setPending: setIsMutatingJob,
          errorMessage: 'Failed to remove scheduled job.',
        });
      } finally {
        isMutatingJobRef.current = false;
      }
    },
    [runAsyncAction],
  );

  return {
    cronJobs,
    handleActivateJob,
    handleCreateJob,
    handlePauseJob,
    handleRemoveJob,
    heartbeat,
    isCreatingJob,
    isLoadingJobs,
    isMutatingJob,
    jobHistory,
    loadJobs,
  };
}
