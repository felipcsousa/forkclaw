import { ArrowUpRight, Loader2 } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Sheet, SheetContent, SheetDescription, SheetTitle } from '@/components/ui/sheet';
import type { MemoryRecallDetailRecord } from '../lib/backend/memory';

interface MemoryRecallSheetProps {
  activeRecall: MemoryRecallDetailRecord | null;
  errorMessage: string | null;
  isLoading: boolean;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onOpenMemory: (memoryId: string) => void;
}

export function MemoryRecallSheet({
  activeRecall,
  errorMessage,
  isLoading,
  open,
  onOpenChange,
  onOpenMemory,
}: MemoryRecallSheetProps) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="w-full border-l border-border/80 p-0 sm:w-[min(92vw,34rem)]"
      >
        <div className="border-b border-border/70 px-6 py-5">
          <SheetTitle>Memories used for this reply</SheetTitle>
          <SheetDescription className="mt-1">
            See what was injected, why it matched, and where it came from.
          </SheetDescription>
        </div>

        <ScrollArea className="min-h-0 flex-1">
          <div className="space-y-4 px-6 py-5">
            {isLoading ? (
              <div className="rounded-2xl border border-dashed border-border px-4 py-6 text-sm text-muted-foreground">
                <span className="inline-flex items-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Loading recalled memories...
                </span>
              </div>
            ) : errorMessage ? (
              <div className="rounded-2xl border border-destructive/20 bg-destructive/5 px-4 py-5 text-sm text-destructive">
                <p className="font-medium">Could not load memory recall detail.</p>
                <p className="mt-1 opacity-90">{errorMessage}</p>
              </div>
            ) : activeRecall?.items.length ? (
              <>
                <section className="rounded-3xl border border-border/70 bg-[color-mix(in_srgb,white_92%,var(--color-muted)_8%)] px-5 py-4">
                  <p className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">
                    Recall summary
                  </p>
                  <p className="mt-2 text-sm leading-relaxed text-foreground">
                    {activeRecall.reason_summary || 'Relevant memories were injected for this reply.'}
                  </p>
                </section>

                {activeRecall.items.map((item) => (
                  <article
                    key={item.memory_id}
                    className="rounded-3xl border border-border/70 bg-background px-5 py-4 shadow-sm"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0">
                        <h3 className="text-base font-semibold tracking-tight text-foreground">
                          {item.title}
                        </h3>
                        <div className="mt-2 flex flex-wrap gap-2">
                          <Badge variant="outline">{item.kind.replace('_', ' ')}</Badge>
                          <Badge variant="secondary">{item.source_label}</Badge>
                          <Badge variant="outline">{item.scope}</Badge>
                          <Badge variant="warning">{item.importance}</Badge>
                        </div>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="gap-1.5"
                        onClick={() => onOpenMemory(item.memory_id)}
                      >
                        Open in Memory Studio
                        <ArrowUpRight className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                    <div className="mt-4 space-y-3 text-sm">
                      <div>
                        <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
                          Recall reason
                        </p>
                        <p className="mt-1 text-foreground">{item.reason}</p>
                      </div>
                      <div>
                        <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
                          Origin
                        </p>
                        <p className="mt-1 text-muted-foreground">
                          {item.origin_subagent_session_id
                            ? `Subagent session ${item.origin_subagent_session_id}`
                            : item.origin_session_id
                              ? `Session ${item.origin_session_id}`
                              : 'Manual memory'}
                        </p>
                      </div>
                    </div>
                  </article>
                ))}
              </>
            ) : (
              <div className="rounded-2xl border border-dashed border-border px-4 py-6 text-sm text-muted-foreground">
                No recalled memories were recorded for this reply.
              </div>
            )}
          </div>
        </ScrollArea>
      </SheetContent>
    </Sheet>
  );
}
