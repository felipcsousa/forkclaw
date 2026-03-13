import { Bot, User } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import type { SessionRecallSummaryRecord } from '@/lib/backend/memory';
import { anchoredSubagentsForMessage } from '@/lib/subagents';
import { cn } from '@/lib/utils';
import type { SessionRecord, SubagentSessionRecord } from '../lib/backend';
import type { ChatTimelineItem } from '../hooks/controllers/chatExecutionState';
import { AssistantRunCard } from './AssistantRunCard';
import { ParentSubagentInlineCard } from './ParentSubagentInlineCard';

interface ChatTimelineProps {
  session: SessionRecord | null;
  timelineItems: ChatTimelineItem[];
  recallSummaries: SessionRecallSummaryRecord[];
  subagents: SubagentSessionRecord[];
  executionStreamStatus:
    | 'idle'
    | 'connecting'
    | 'connected'
    | 'reconnecting'
    | 'disconnected';
  executionStreamReconnectAttempt: number;
  executionStreamErrorMessage: string | null;
  isLoading: boolean;
  isSending: boolean;
  cancellingSubagentId: string | null;
  onOpenRecall: (assistantMessageId: string) => void;
  onOpenSubagent: (parentSessionId: string, childSessionId: string) => void;
  onCancelSubagent: (parentSessionId: string, childSessionId: string) => void;
}

export function ChatTimeline({
  session,
  timelineItems,
  recallSummaries,
  subagents,
  executionStreamStatus,
  executionStreamReconnectAttempt,
  executionStreamErrorMessage,
  isLoading,
  isSending,
  cancellingSubagentId,
  onOpenRecall,
  onOpenSubagent,
  onCancelSubagent,
}: ChatTimelineProps) {
  if (!session) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <div className="animate-appear w-full max-w-md text-center">
          <div className="mx-auto mb-4 flex h-10 w-10 items-center justify-center rounded-full bg-muted/60">
            <Bot className="h-5 w-5 text-muted-foreground" />
          </div>
          <p className="text-base font-medium text-foreground">No active session</p>
          <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
            Open a thread from the sidebar or start a new conversation.
          </p>
        </div>
      </div>
    );
  }

  return (
    <section className="flex min-h-0 flex-1 flex-col">
      <ScrollArea className="min-h-0 flex-1 py-4">
        <div className="mx-auto w-full max-w-[58rem]">
          {isLoading && timelineItems.length === 0 ? (
            <div className="flex items-center justify-center py-12">
              <p className="animate-pulse text-sm text-muted-foreground">Loading messages...</p>
            </div>
          ) : timelineItems.length === 0 ? (
            <div className="flex min-h-[24rem] items-center justify-center py-6">
              <div className="animate-appear w-full max-w-md text-center">
                <div className="mx-auto mb-4 flex h-10 w-10 items-center justify-center rounded-full bg-muted/60">
                  <Bot className="h-5 w-5 text-muted-foreground" />
                </div>
                <p className="text-base font-medium text-foreground">No messages yet</p>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                  Start the conversation below to build context in this session.
                </p>
              </div>
            </div>
          ) : (
            <div className="space-y-5 pb-2">
              {timelineItems.map((item, index) => {
                if (item.kind === 'run') {
                  return (
                    <AssistantRunCard
                      key={item.run.id}
                      run={item.run}
                      subagents={item.subagents}
                      streamStatus={executionStreamStatus}
                      streamReconnectAttempt={executionStreamReconnectAttempt}
                      streamErrorMessage={executionStreamErrorMessage}
                      cancellingSubagentId={cancellingSubagentId}
                      onOpenSubagent={onOpenSubagent}
                      onCancelSubagent={onCancelSubagent}
                    />
                  );
                }

                const { message } = item;
                const isUser = message.role === 'user';
                const anchoredSubagents = anchoredSubagentsForMessage(subagents, message.id);
                const recallSummary = recallSummaries.find(
                  (candidate) => candidate.assistant_message_id === message.id,
                );
                const recallLabel =
                  recallSummary?.recalled_count === 1
                    ? '1 memory used'
                    : `${recallSummary?.recalled_count || 0} memories used`;

                return (
                  <div key={message.id} className="space-y-3">
                    <article
                      className={cn(
                        'animate-fade-in flex gap-3.5',
                        isUser ? 'justify-end' : 'justify-start',
                        isSending &&
                          index === timelineItems.length - 1 &&
                          'opacity-60',
                      )}
                    >
                      {!isUser ? (
                        <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-border/80 bg-muted/40 text-muted-foreground">
                          <Bot className="h-3.5 w-3.5" />
                        </div>
                      ) : null}

                      <div
                        className={cn(
                          'max-w-[min(68ch,76%)] rounded-2xl px-4 py-3',
                          isUser
                            ? 'bg-primary text-primary-foreground shadow-sm'
                            : 'border border-border/70 bg-muted/15 text-foreground',
                        )}
                      >
                        <div className="mb-1.5 flex items-center gap-2">
                          <span
                            className={cn(
                              'text-xs font-medium',
                              isUser ? 'text-primary-foreground/70' : 'text-muted-foreground',
                            )}
                          >
                            {isUser ? 'You' : 'Agent'}
                          </span>
                          <span
                            className={cn(
                              'text-xs',
                              isUser ? 'text-primary-foreground/55' : 'text-muted-foreground/70',
                            )}
                          >
                            {message.created_at
                              ? new Date(message.created_at).toLocaleTimeString([], {
                                  hour: '2-digit',
                                  minute: '2-digit',
                                })
                              : ''}
                          </span>
                        </div>
                        <div className="whitespace-pre-wrap text-[15px] leading-7">
                          {message.content_text}
                        </div>
                        {!isUser && recallSummary && recallSummary.recalled_count > 0 ? (
                          <div className="mt-3 flex justify-start">
                            <Button
                              type="button"
                              variant="ghost"
                              size="sm"
                              className="h-7 rounded-full border border-border/70 px-3 text-xs font-medium text-muted-foreground hover:text-foreground"
                              onClick={() => onOpenRecall(message.id)}
                            >
                              {recallLabel}
                            </Button>
                          </div>
                        ) : null}
                      </div>

                      {isUser ? (
                        <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
                          <User className="h-3.5 w-3.5" />
                        </div>
                      ) : null}
                    </article>

                    {anchoredSubagents.map((subagent) => (
                      <ParentSubagentInlineCard
                        key={subagent.id}
                        subagent={subagent}
                        isCancelling={cancellingSubagentId === subagent.id}
                        onOpen={onOpenSubagent}
                        onCancel={onCancelSubagent}
                      />
                    ))}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </ScrollArea>
    </section>
  );
}
