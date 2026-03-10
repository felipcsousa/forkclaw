import { ArrowUp } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';

interface ChatComposerProps {
  draft: string;
  disabled: boolean;
  isSending: boolean;
  sessionTitle: string | null;
  onDraftChange: (value: string) => void;
  onSubmit: () => void;
}

export function ChatComposer({
  draft,
  disabled,
  isSending,
  sessionTitle,
  onDraftChange,
  onSubmit,
}: ChatComposerProps) {
  return (
    <div className="border-t border-border/60 px-6 py-3.5">
      <div className="mx-auto w-full max-w-[58rem] space-y-3">
        <Textarea
          id="chat-message"
          aria-label="Message"
          value={draft}
          onChange={(e) => onDraftChange(e.target.value)}
          placeholder={
            sessionTitle
              ? `Message ${sessionTitle}…`
              : 'Select or create a session first…'
          }
          disabled={disabled}
          rows={3}
          className="min-h-[80px] resize-none bg-background/80"
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              onSubmit();
            }
          }}
        />

        <div className="flex items-center justify-between gap-4">
          <p className="text-xs text-muted-foreground">
            ↵ Enter to send · Shift+Enter for new line
          </p>
          <Button
            onClick={onSubmit}
            disabled={disabled}
            size="sm"
          >
            <ArrowUp className="h-3.5 w-3.5" />
            {isSending ? 'Sending…' : 'Send'}
          </Button>
        </div>
      </div>
    </div>
  );
}
