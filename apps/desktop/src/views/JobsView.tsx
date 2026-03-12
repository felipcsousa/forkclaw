import type { useAppController } from '../hooks/useAppController';
import { CronJobsPanel } from '../components/CronJobsPanel';

type AppController = ReturnType<typeof useAppController>;

export interface JobsViewProps {
  jobs: AppController['jobs'];
}

export function JobsView({ jobs }: JobsViewProps) {
  return (
    <CronJobsPanel
      jobs={jobs.cronJobs}
      history={jobs.jobHistory}
      heartbeat={jobs.heartbeat}
      isLoading={jobs.isLoadingJobs}
      isCreating={jobs.isCreatingJob}
      isMutating={jobs.isMutatingJob}
      onCreateJob={jobs.handleCreateJob}
      onPauseJob={jobs.handlePauseJob}
      onActivateJob={jobs.handleActivateJob}
      onRemoveJob={jobs.handleRemoveJob}
    />
  );
}
