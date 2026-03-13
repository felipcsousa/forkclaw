import type { LucideIcon } from 'lucide-react';
import {
  Activity,
  Brain,
  Bot,
  CheckCheck,
  Clock3,
  Settings2,
  Sparkles,
  Wrench,
} from 'lucide-react';

export type AppView =
  | 'chat'
  | 'profile'
  | 'settings'
  | 'tools'
  | 'memory'
  | 'approvals'
  | 'jobs'
  | 'activity';

export interface AppViewDetail {
  label: string;
  eyebrow: string;
  title: string;
  description: string;
  hint: string;
  icon: LucideIcon;
}

export const APP_VIEW_DETAILS: Record<AppView, AppViewDetail> = {
  chat: {
    label: 'New chat',
    eyebrow: 'Conversation',
    title: 'Talk to your local agent',
    description:
      'Sessions keep the conversation durable, local, and easy to resume after restarts.',
    hint: 'Sessions and replies',
    icon: Sparkles,
  },
  profile: {
    label: 'Profile',
    eyebrow: 'Behavior',
    title: 'Canonical agent profile',
    description:
      'Edit the identity, soul, policy, and user context that shape new executions.',
    hint: 'Identity and policy',
    icon: Bot,
  },
  settings: {
    label: 'Settings',
    eyebrow: 'Runtime',
    title: 'Operational defaults and local limits',
    description:
      'Adjust provider, workspace, budgets, and app preferences without touching files.',
    hint: 'Provider and workspace',
    icon: Settings2,
  },
  tools: {
    label: 'Tools',
    eyebrow: 'Security',
    title: 'Local tool permissions and audit trail',
    description:
      'Control which tools are denied, require approval, or run automatically inside the workspace boundary.',
    hint: 'Permissions and calls',
    icon: Wrench,
  },
  memory: {
    label: 'Memory',
    eyebrow: 'Recall',
    title: 'Memory Studio',
    description:
      'Browse, search, edit, and control what the agent remembers and when those memories are used.',
    hint: 'Manual memory control',
    icon: Brain,
  },
  approvals: {
    label: 'Approvals',
    eyebrow: 'Review',
    title: 'Paused sensitive actions',
    description:
      'Inspect the exact action, parameters, and session before deciding whether a tool may continue.',
    hint: 'Pending actions',
    icon: CheckCheck,
  },
  jobs: {
    label: 'Jobs',
    eyebrow: 'Automation',
    title: 'Scheduled jobs and heartbeat',
    description:
      'Keep background work running locally with durable schedules, heartbeat checks, and execution history.',
    hint: 'Cron and heartbeat',
    icon: Clock3,
  },
  activity: {
    label: 'Activity',
    eyebrow: 'Observability',
    title: 'Recent execution timeline',
    description:
      'Understand what the agent did, how long it took, which tools it touched, and where failures happened.',
    hint: 'Execution trace',
    icon: Activity,
  },
};

export const APP_NAVIGATION_GROUPS: Array<{ title: string; items: AppView[] }> = [
  { title: 'Navigate', items: ['chat', 'activity', 'approvals'] },
  { title: 'Operate', items: ['jobs', 'memory', 'tools'] },
  { title: 'Configure', items: ['profile', 'settings'] },
];

export const DESKTOP_SIDEBAR_PANEL_SIZE = 22;
export const DESKTOP_MAIN_PANEL_SIZE = 78;
export const DESKTOP_SIDEBAR_MIN_SIZE = 18;
export const DESKTOP_SIDEBAR_MAX_SIZE = 32;
