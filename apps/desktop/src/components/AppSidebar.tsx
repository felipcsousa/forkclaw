import { cn } from '@/lib/utils';

import { SessionSidebar } from './SessionSidebar';
import {
  APP_NAVIGATION_GROUPS,
  APP_VIEW_DETAILS,
  type AppView,
} from './app-shell-layout';
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
} from './ui/sidebar';
import type { SessionRecord } from '../lib/backend';

export interface AppSidebarProps {
  view: AppView;
  agentTitle: string;
  providerLabel: string;
  pendingApprovalsCount: number;
  activeJobsCount: number;
  isWorkspaceSyncing: boolean;
  sessions: SessionRecord[];
  activeSessionId: string | null;
  isCreatingSession: boolean;
  isLoadingSessions: boolean;
  getViewCount: (targetView: AppView) => string | null;
  onNavigate: (nextView: AppView) => void;
  onCreateSession: () => void;
  onSelectSession: (sessionId: string) => void;
  className?: string;
  testId?: string;
}

export function AppSidebar({
  view,
  agentTitle,
  providerLabel,
  pendingApprovalsCount,
  activeJobsCount,
  isWorkspaceSyncing,
  sessions,
  activeSessionId,
  isCreatingSession,
  isLoadingSessions,
  getViewCount,
  onNavigate,
  onCreateSession,
  onSelectSession,
  className,
  testId = 'app-sidebar',
}: AppSidebarProps) {
  return (
    <Sidebar
      className={cn('h-full min-w-0 flex flex-col', className)}
      data-testid={testId}
    >
      <SidebarHeader className="px-5 py-3.5">
        <div className="flex items-center gap-3">
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-foreground text-[10px] font-bold text-background shadow-sm">
            N
          </div>
          <div className="min-w-0">
            <h1 className="truncate text-[13px] font-semibold tracking-tight text-foreground">
              {agentTitle}
            </h1>
            <p className="truncate text-[11px] font-medium text-muted-foreground opacity-90">
              Local agent console
            </p>
          </div>
        </div>
      </SidebarHeader>

      <SidebarContent className="flex-1 gap-3 px-3 pt-1">
        <div className="space-y-4">
          {APP_NAVIGATION_GROUPS.map((group) => (
            <SidebarGroup key={group.title}>
              <SidebarGroupLabel className="mb-1 py-0 h-auto">
                {group.title}
              </SidebarGroupLabel>
              <SidebarMenu>
                {group.items.map((item) => {
                  const details = APP_VIEW_DETAILS[item];
                  const count = getViewCount(item);
                  const Icon = details.icon;
                  const isActive =
                    item === 'chat'
                      ? view === 'chat' && !activeSessionId
                      : view === item;

                  return (
                    <SidebarMenuButton
                      key={item}
                      type="button"
                      aria-label={details.label}
                      isActive={isActive}
                      data-testid={`app-sidebar-nav-${item}`}
                      onClick={() => onNavigate(item)}
                      className={cn(
                        'h-8 rounded-md px-2 transition-colors',
                        isActive
                          ? 'bg-foreground/5 text-foreground font-medium'
                          : 'text-muted-foreground hover:bg-foreground/5 hover:text-foreground',
                      )}
                    >
                      <span className="flex min-w-0 w-full items-center justify-between gap-2.5">
                        <span className="flex items-center gap-2.5 min-w-0">
                          <Icon
                            className={cn(
                              'h-4 w-4 shrink-0',
                              isActive
                                ? 'text-foreground'
                                : 'text-muted-foreground/80',
                            )}
                          />
                          <span
                            className={cn(
                              'truncate text-sm tracking-tight',
                              isActive
                                ? 'text-foreground font-semibold'
                                : 'text-current',
                            )}
                          >
                            {details.label}
                          </span>
                        </span>
                        {count ? (
                          <span className="ml-auto text-[10px] font-mono text-muted-foreground/70">
                            {count}
                          </span>
                        ) : null}
                      </span>
                    </SidebarMenuButton>
                  );
                })}
              </SidebarMenu>
            </SidebarGroup>
          ))}
        </div>

        <SidebarGroup className="mt-auto pb-4">
          <div className="min-h-0 flex-1">
            <SessionSidebar
              sessions={sessions}
              activeSessionId={view === 'chat' ? activeSessionId : null}
              isCreating={isCreatingSession}
              isLoading={isLoadingSessions}
              onCreateSession={onCreateSession}
              onSelectSession={onSelectSession}
            />
          </div>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter className="border-t border-sidebar-border/80 px-4 py-3">
        <div className="flex items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-2 min-w-0">
            <span
              className={cn(
                'inline-block h-2 w-2 shrink-0 rounded-full shadow-xs',
                isWorkspaceSyncing ? 'bg-amber-400' : 'bg-emerald-500',
              )}
            />
            <span className="truncate font-medium text-muted-foreground opacity-90">
              {providerLabel}
            </span>
          </div>
          <span className="shrink-0 font-medium text-muted-foreground/70">
            {pendingApprovalsCount} pend · {activeJobsCount} jobs
          </span>
        </div>
      </SidebarFooter>
    </Sidebar>
  );
}
