import type { useAppController } from '../hooks/useAppController';
import { ChatComposer } from '../components/ChatComposer';
import { ChatTimeline } from '../components/ChatTimeline';
import { SessionSubagentIndex } from '../components/SessionSubagentIndex';

type AppController = ReturnType<typeof useAppController>;

export interface ChatWorkspaceProps {
  app: AppController['app'];
  chat: AppController['chat'];
  onRefresh: () => void;
}

export function ChatWorkspace({
  app,
  chat,
  onRefresh,
}: ChatWorkspaceProps) {
  return (
    <div className="min-h-0 flex flex-1 flex-col rounded-[1.4rem] border border-border/80 bg-[color-mix(in_srgb,white_92%,var(--color-muted)_8%)] shadow-[0_14px_32px_rgba(15,23,42,0.04)]">
      <div className="min-h-0 flex-1 px-6 py-5">
        <ChatTimeline
          session={chat.activeSession}
          messages={chat.messages}
          subagents={chat.subagents}
          isLoading={chat.isBootstrapping || chat.isLoadingMessages}
          isSending={chat.isSending}
          cancellingSubagentId={chat.cancellingSubagentId}
          onOpenSubagent={chat.handleOpenSubagent}
          onCancelSubagent={chat.handleCancelSubagent}
        />
      </div>
      <ChatComposer
        draft={chat.draft}
        disabled={app.isComposerDisabled}
        isSending={chat.isSending}
        sessionTitle={chat.activeSession?.title || null}
        onDraftChange={chat.setDraft}
        onSubmit={chat.handleSendMessage}
      />
      <SessionSubagentIndex
        session={chat.activeSession}
        items={chat.subagents}
        isLoading={chat.isLoadingSubagents}
        errorMessage={chat.subagentsErrorMessage}
        cancellingSubagentId={chat.cancellingSubagentId}
        onOpen={chat.handleOpenSubagent}
        onCancel={chat.handleCancelSubagent}
        onRefresh={onRefresh}
      />
    </div>
  );
}
