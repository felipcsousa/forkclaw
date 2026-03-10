import { useId, useState, type FormEvent } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Field, SelectInput } from '@/components/ui/form-field';
import { Input } from '@/components/ui/input';
import { Separator } from '@/components/ui/separator';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import type {
  CronJobCreateInput,
  CronJobRecord,
  CronJobType,
  HeartbeatStatusRecord,
  TaskRunHistoryRecord,
} from '../lib/backend';

interface CronJobsPanelProps {
  jobs: CronJobRecord[];
  history: TaskRunHistoryRecord[];
  heartbeat: HeartbeatStatusRecord | null;
  isLoading: boolean;
  isCreating: boolean;
  isMutating: boolean;
  onCreateJob: (payload: CronJobCreateInput) => void;
  onPauseJob: (jobId: string) => void;
  onActivateJob: (jobId: string) => void;
  onRemoveJob: (jobId: string) => void;
}

const jobTypeLabels: Record<CronJobType, string> = {
  review_pending_approvals: 'Review pending approvals',
  summarize_recent_activity: 'Summarize recent activity',
  cleanup_stale_runs: 'Clean stale runs',
};

function statusVariant(status: string) {
  if (status === 'completed' || status === 'active' || status === 'running') {
    return 'success' as const;
  }

  if (status === 'failed') {
    return 'destructive' as const;
  }

  return 'secondary' as const;
}

export function CronJobsPanel({
  jobs,
  history,
  heartbeat,
  isLoading,
  isCreating,
  isMutating,
  onCreateJob,
  onPauseJob,
  onActivateJob,
  onRemoveJob,
}: CronJobsPanelProps) {
  const [name, setName] = useState('');
  const [schedule, setSchedule] = useState('every:60s');
  const [jobType, setJobType] = useState<CronJobType>('summarize_recent_activity');
  const [message, setMessage] = useState('');
  const [staleAfterSeconds, setStaleAfterSeconds] = useState('900');
  const idBase = useId();

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onCreateJob({
      name: name.trim(),
      schedule: schedule.trim(),
      payload: {
        job_type: jobType,
        message: message.trim() || null,
        stale_after_seconds:
          jobType === 'cleanup_stale_runs' ? Number(staleAfterSeconds) || 900 : null,
      },
    });
    setName('');
    setMessage('');
    setSchedule('every:60s');
    setJobType('summarize_recent_activity');
    setStaleAfterSeconds('900');
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-card px-4 py-2.5 shadow-sm">
        <span className={`inline-block h-2 w-2 shadow-xs rounded-full ${heartbeat?.last_run_at ? 'bg-emerald-500' : 'bg-amber-400'}`} />
        <span className="text-[13px] font-medium tracking-tight text-foreground">
          {heartbeat?.last_run_at ? 'Heartbeat running' : 'Heartbeat starting'}
        </span>
        <span className="text-[11px] font-medium text-muted-foreground">
          {heartbeat?.pending_approvals || 0} pend · {heartbeat?.cleaned_stale_runs || 0} clean · {heartbeat?.recent_task_runs || 0} runs
        </span>
        {heartbeat?.summary_text ? (
          <>
            <Separator orientation="vertical" className="h-4" />
            <span className="truncate text-[11px] font-medium text-muted-foreground/90">{heartbeat.summary_text}</span>
          </>
        ) : null}
      </div>

      <Tabs defaultValue="jobs" className="w-full">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
          <TabsList className="h-9 p-1 bg-muted/50 w-full sm:w-auto overflow-x-auto justify-start border border-border/40">
            <TabsTrigger className="rounded-md px-4 py-1.5 text-xs font-semibold data-[state=active]:shadow-sm" value="create">Create</TabsTrigger>
            <TabsTrigger className="rounded-md px-4 py-1.5 text-xs font-semibold data-[state=active]:shadow-sm" value="jobs">Jobs</TabsTrigger>
            <TabsTrigger className="rounded-md px-4 py-1.5 text-xs font-semibold data-[state=active]:shadow-sm" value="history">History</TabsTrigger>
          </TabsList>
          <p className="text-xs font-medium text-muted-foreground/80">
            Supports: every:30s, every:5m, daily:09:00, weekly:mon@09:00
          </p>
        </div>

        <TabsContent value="create" className="space-y-6 rounded-xl border border-border bg-card p-6 shadow-sm">
          <form className="space-y-6" onSubmit={handleSubmit}>
            <div className="field-grid three">
              <Field label="Job name" htmlFor={`${idBase}-name`}>
                <Input
                  id={`${idBase}-name`}
                  className="rounded-lg shadow-sm"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Morning Digest"
                  required
                />
              </Field>
              <Field label="Schedule" htmlFor={`${idBase}-schedule`}>
                <Input
                  id={`${idBase}-schedule`}
                  className="rounded-lg shadow-sm font-mono text-sm"
                  value={schedule}
                  onChange={(e) => setSchedule(e.target.value)}
                  placeholder="every:60s"
                  required
                />
              </Field>
              <Field
                label="Job type"
                htmlFor={`${idBase}-job-type`}
                hint="Task to run."
              >
                <SelectInput
                  id={`${idBase}-job-type`}
                  className="rounded-lg border-input px-3 py-2 shadow-sm ring-offset-background focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                  value={jobType}
                  onChange={(e) => setJobType(e.target.value as CronJobType)}
                >
                  {Object.entries(jobTypeLabels).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </SelectInput>
              </Field>
            </div>

            {jobType === 'cleanup_stale_runs' ? (
              <Field
                label="Stale timeout (sec)"
                htmlFor={`${idBase}-stale-timeout`}
                hint="Runs older than this may be cleaned up."
              >
                <Input
                  id={`${idBase}-stale-timeout`}
                  className="rounded-lg shadow-sm"
                  type="number"
                  min={30}
                  step={1}
                  value={staleAfterSeconds}
                  onChange={(e) => setStaleAfterSeconds(e.target.value)}
                />
              </Field>
            ) : null}

            <Field
              label="Job note"
              htmlFor={`${idBase}-message`}
              hint="Context stored with the job output."
            >
              <Textarea
                id={`${idBase}-message`}
                className="rounded-lg shadow-sm resize-none"
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="Daily summary"
              />
            </Field>

            <div className="flex flex-wrap items-center justify-between gap-4 pt-4 border-t border-border/60">
              <p className="text-[13px] font-medium text-muted-foreground opacity-90">
                Jobs survive restarts and append history to the local log.
              </p>
              <Button type="submit" disabled={isCreating || isMutating} className="h-9 px-5 rounded-lg shadow-sm font-medium">
                {isCreating ? 'Creating...' : 'Create job'}
              </Button>
            </div>
          </form>
        </TabsContent>

        <TabsContent value="jobs" className="space-y-4">
          {isLoading && jobs.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-border py-12 px-4 bg-card/50">
              <p className="text-[13px] font-semibold tracking-tight text-foreground animate-pulse">Loading scheduled jobs...</p>
            </div>
          ) : jobs.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-border py-12 px-4 bg-sidebar/50">
              <p className="text-[14px] font-semibold tracking-tight text-foreground">No jobs configured</p>
              <p className="text-[13px] text-muted-foreground text-center">Create a scheduled job to automate background tasks.</p>
            </div>
          ) : (
            <div className="rounded-xl border border-border bg-card overflow-hidden shadow-sm">
              <Table>
                <TableHeader className="bg-muted/30">
                  <TableRow className="hover:bg-transparent">
                    <TableHead className="text-[11px] font-medium capitalize text-muted-foreground h-9">Job</TableHead>
                    <TableHead className="text-[11px] font-medium capitalize text-muted-foreground h-9">Status</TableHead>
                    <TableHead className="text-[11px] font-medium capitalize text-muted-foreground h-9">Last run</TableHead>
                    <TableHead className="text-[11px] font-medium capitalize text-muted-foreground h-9">Next run</TableHead>
                    <TableHead className="text-[11px] font-medium capitalize text-muted-foreground h-9 w-48 text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {jobs.map((job) => (
                    <TableRow key={job.id} className="group border-b border-border/60 last:border-0 hover:bg-muted/10 transition-colors">
                      <TableCell className="py-2.5">
                        <div className="space-y-0.5">
                          <p className="font-semibold text-[13px] tracking-tight text-foreground leading-tight">{job.name}</p>
                          <p className="text-[11px] font-medium text-muted-foreground">
                            {jobTypeLabels[job.payload.job_type]} · <span className="font-mono text-foreground/70">{job.schedule}</span>
                          </p>
                        </div>
                      </TableCell>
                      <TableCell className="py-2.5">
                        <Badge variant={statusVariant(job.status)} className="font-medium px-1.5 py-0 text-[10px]">
                          {job.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-[12px] font-medium text-muted-foreground py-2.5">
                        {job.last_run_at || 'Not yet'}
                      </TableCell>
                      <TableCell className="text-[12px] font-medium text-muted-foreground py-2.5">
                        {job.next_run_at || 'Paused'}
                      </TableCell>
                      <TableCell className="text-right py-2.5">
                        <div className="flex justify-end gap-2 opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition-opacity">
                          {job.status === 'active' ? (
                            <Button
                              variant="secondary"
                              size="sm"
                              className="h-7 px-3 text-xs shadow-none border-border"
                              onClick={() => onPauseJob(job.id)}
                              disabled={isMutating}
                            >
                              Pause
                            </Button>
                          ) : (
                            <Button
                              size="sm"
                              className="h-7 px-3 text-xs shadow-none"
                              onClick={() => onActivateJob(job.id)}
                              disabled={isMutating}
                            >
                              Activate
                            </Button>
                          )}
                          <Button
                            variant="destructive"
                            size="sm"
                            className="h-7 px-3 text-xs shadow-none bg-destructive/10 text-destructive hover:bg-destructive hover:text-destructive-foreground focus:bg-destructive focus:text-destructive-foreground transition-colors border-0"
                            onClick={() => onRemoveJob(job.id)}
                            disabled={isMutating}
                          >
                            Remove
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </TabsContent>

        <TabsContent value="history" className="space-y-4">
          {history.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-border py-12 px-4 bg-sidebar/50">
              <p className="text-[14px] font-semibold tracking-tight text-foreground">No history yet</p>
            </div>
          ) : (
            <div className="rounded-xl border border-border bg-card overflow-hidden shadow-sm">
              <Table>
                <TableHeader className="bg-muted/30">
                  <TableRow className="hover:bg-transparent">
                    <TableHead className="text-[11px] font-medium capitalize text-muted-foreground h-9">Execution</TableHead>
                    <TableHead className="text-[11px] font-medium capitalize text-muted-foreground h-9 w-32">Status</TableHead>
                    <TableHead className="text-[11px] font-medium capitalize text-muted-foreground h-9">Summary</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {history.map((item) => (
                    <TableRow key={item.task_run_id} className="border-b border-border/60 last:border-0 hover:bg-muted/10 transition-colors">
                      <TableCell className="py-2.5 font-semibold text-[13px] tracking-tight text-foreground">
                        {item.job_name || item.task_title}
                      </TableCell>
                      <TableCell className="py-2.5">
                        <Badge variant={statusVariant(item.status)} className="font-medium px-1.5 py-0 text-[10px]">
                          {item.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="py-2.5 text-[12px] font-medium leading-relaxed text-muted-foreground">
                        {item.output_summary || item.error_message || 'No summary recorded.'}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
