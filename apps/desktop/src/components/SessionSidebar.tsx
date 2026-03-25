import { Fragment } from 'react';
import { MessageSquarePlus } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import type { SessionRecord } from '../lib/backend';

interface SessionSidebarProps {
  sessions: SessionRecord[];
  activeSessionId: string | null;
  isCreating: boolean;
  isLoading: boolean;
  onCreateSession: () => void;
  onSelectSession: (sessionId: string) => void;
}

function sessionTimestamp(session: SessionRecord) {
  const candidate = session.last_message_at || session.updated_at || session.created_at;
  const parsed = new Date(candidate);

  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function groupLabel(createdAt: string | null) {
  if (!createdAt) {
    return 'Unsorted';
  }

  const now = new Date();
  const created = new Date(createdAt);
  const sameDay = now.toDateString() === created.toDateString();

  if (sameDay) {
    return 'Today';
  }

  const yesterday = new Date();
  yesterday.setDate(now.getDate() - 1);

  if (yesterday.toDateString() === created.toDateString()) {
    return 'Yesterday';
  }

  return 'Earlier';
}

export function SessionSidebar({
  sessions,
  activeSessionId,
  isCreating,
  isLoading,
  onCreateSession,
  onSelectSession,
}: SessionSidebarProps) {
  let lastGroup: string | null = null;
  const orderedSessions = [...sessions].sort((left, right) => {
    const leftTime = sessionTimestamp(left)?.getTime() || 0;
    const rightTime = sessionTimestamp(right)?.getTime() || 0;

    return rightTime - leftTime;
  });

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-2.5">
      <div className="flex items-center justify-between gap-2 px-2 mb-1">
        <p className="text-[11px] font-semibold text-sidebar-muted-foreground/80">
          Sessions
        </p>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="h-9 w-9 shrink-0 rounded-xl bg-background/70 hover:bg-background"
              onClick={onCreateSession}
              disabled={isCreating}
              aria-label="New session"
            >
              <MessageSquarePlus className="h-4 w-4" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>New session</TooltipContent>
        </Tooltip>
      </div>

      <ScrollArea className="min-h-0 flex-1 px-1">
        {isLoading && sessions.length === 0 ? (
          <div className="empty-dashed rounded-lg px-3 py-3 text-sm text-muted-foreground animate-pulse">
            Loading sessions...
          </div>
        ) : sessions.length === 0 ? (
          <div className="empty-dashed rounded-lg px-3 py-3">
            <p className="text-sm font-medium text-foreground">No persistent sessions yet.</p>
            <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
              Create a new session to start a durable conversation with the agent.
            </p>
          </div>
        ) : (
          <div className="space-y-1 pb-2">
            {orderedSessions.map((session) => {
              const referenceTime = sessionTimestamp(session);
              const currentGroup = groupLabel(referenceTime?.toISOString() || null);
              const showGroup = currentGroup !== lastGroup;
              lastGroup = currentGroup;

              return (
                <Fragment key={session.id}>
                  {showGroup ? (
                    <p className="px-2 mt-2 mb-1 text-[10px] font-medium tracking-wide text-sidebar-muted-foreground/60">
                      {currentGroup}
                    </p>
                  ) : null}
                  <button
                    type="button"
                    onClick={() => onSelectSession(session.id)}
                    data-testid={`session-item-${session.id}`}
                    data-active={session.id === activeSessionId ? 'true' : 'false'}
                    className={cn(
                      'group relative w-full rounded-lg border border-transparent px-3 py-1.5 text-left transition-all duration-200 outline-none focus-visible:ring-2 focus-visible:ring-ring',
                      session.id === activeSessionId
                        ? 'bg-foreground/[0.04] text-foreground font-medium'
                        : 'text-sidebar-muted-foreground hover:bg-foreground/[0.03] hover:text-sidebar-foreground',
                    )}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p
                          className={cn(
                            'truncate text-sm font-medium tracking-[-0.01em]',
                            session.id === activeSessionId
                              ? 'text-foreground'
                              : 'text-sidebar-foreground',
                          )}
                        >
                          {session.title}
                        </p>
                        <p className="mt-1 truncate text-xs text-muted-foreground">
                          {referenceTime
                            ? referenceTime.toLocaleString([], {
                              month: 'short',
                              day: 'numeric',
                              hour: '2-digit',
                              minute: '2-digit',
                            })
                            : 'Time unavailable'}
                        </p>
                      </div>
                    </div>
                  </button>
                </Fragment>
              );
            })}
          </div>
        )}
      </ScrollArea>
    </div>
  );
}
