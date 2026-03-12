import { ArrowLeft, ChevronLeft, ChevronRight, Loader2 } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { SheetContent, SheetDescription, SheetTitle } from '@/components/ui/sheet';
import {
  formatDuration,
  formatEstimatedCost,
  formatTimestamp,
  parseSubagentSummary,
  subagentStatusCopy,
  subagentStatusVariant,
} from '@/lib/subagents';
import type { MessageRecord, SessionRecord, SubagentSessionRecord } from '../lib/backend';
import { SubagentTimelineMini } from './SubagentTimelineMini';

interface SubagentSessionSheetProps {
  parentSession: SessionRecord | null;
  subagent: SubagentSessionRecord | null;
  messages: MessageRecord[];
  isLoadingDetail: boolean;
  isLoadingMessages: boolean;
  errorMessage: string | null;
  hasPrevious: boolean;
  hasNext: boolean;
  onBackToParent: (parentSessionId: string) => void;
  onPrevious: () => void;
  onNext: () => void;
}

export function SubagentSessionSheet({
  parentSession,
  subagent,
  messages,
  isLoadingDetail,
  isLoadingMessages,
  errorMessage,
  hasPrevious,
  hasNext,
  onBackToParent,
  onPrevious,
  onNext,
}: SubagentSessionSheetProps) {
  const summary = parseSubagentSummary(subagent);

  return (
    <SheetContent
      side="right"
      className="w-full border-l border-border/80 p-0 sm:w-[min(88vw,42rem)]"
      data-testid="subagent-session-sheet"
    >
      <div className="border-b border-border/70 px-6 py-5">
        <div className="flex items-start justify-between gap-4 pr-8">
          <div className="min-w-0">
            <SheetTitle>Sessão filha</SheetTitle>
            <SheetDescription className="mt-1 leading-relaxed">
              Visualizador read-only da execução delegada.
            </SheetDescription>
          </div>
          {subagent ? (
            <Badge variant={subagentStatusVariant(subagent.run.lifecycle_status)}>
              {subagent.run.lifecycle_status}
            </Badge>
          ) : null}
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <Button
            type="button"
            size="sm"
            variant="secondary"
            className="h-8 gap-1.5 text-xs"
            onClick={() => subagent && onBackToParent(subagent.parent_session_id || '')}
            disabled={!subagent}
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Voltar ao pai
          </Button>
          <Button
            type="button"
            size="sm"
            variant="ghost"
            className="h-8 gap-1.5 text-xs"
            onClick={onPrevious}
            disabled={!hasPrevious}
          >
            <ChevronLeft className="h-3.5 w-3.5" />
            Anterior
          </Button>
          <Button
            type="button"
            size="sm"
            variant="ghost"
            className="h-8 gap-1.5 text-xs"
            onClick={onNext}
            disabled={!hasNext}
          >
            Próximo
            <ChevronRight className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      <ScrollArea className="min-h-0 flex-1">
        <div className="space-y-6 px-6 py-5">
          {isLoadingDetail && !subagent ? (
            <div className="rounded-2xl border border-dashed border-border px-4 py-6 text-sm text-muted-foreground">
              <span className="inline-flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                Loading child session...
              </span>
            </div>
          ) : errorMessage ? (
            <div className="rounded-2xl border border-destructive/20 bg-destructive/5 px-4 py-5 text-sm text-destructive">
              <p className="font-medium">Não foi possível abrir a sessão filha.</p>
              <p className="mt-1 opacity-90">{errorMessage}</p>
            </div>
          ) : subagent ? (
            <>
              <section className="rounded-3xl border border-border/70 bg-[color-mix(in_srgb,white_90%,var(--color-muted)_10%)] px-5 py-4 shadow-sm">
                <p className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">
                  Objetivo delegado
                </p>
                <h3 className="mt-2 text-lg font-semibold tracking-tight text-foreground">
                  {subagent.delegated_goal || subagent.title}
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                  {subagentStatusCopy(subagent.run.lifecycle_status)}
                </p>
                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  <MetaTile label="Sessão pai" value={parentSession?.title || 'Unknown'} />
                  <MetaTile label="Criado em" value={formatTimestamp(subagent.created_at)} />
                  <MetaTile label="Duração" value={formatDuration(subagent.run)} />
                  <MetaTile
                    label="Custo estimado"
                    value={formatEstimatedCost(subagent.run.estimated_cost_usd)}
                  />
                </div>
              </section>

              <section className="space-y-3">
                <SectionHeading title="Resumo final" />
                <div className="rounded-2xl border border-border/70 bg-background px-4 py-4">
                  <p className="text-sm leading-relaxed text-foreground">
                    {summary?.summary || subagent.run.final_summary || 'Ainda sem resumo final.'}
                  </p>
                  {summary?.key_findings?.length ? (
                    <div className="mt-4 space-y-2">
                      {summary.key_findings.map((finding) => (
                        <div
                          key={finding}
                          className="rounded-xl bg-muted/40 px-3 py-2 text-sm text-muted-foreground"
                        >
                          {finding}
                        </div>
                      ))}
                    </div>
                  ) : null}
                </div>
              </section>

              <section className="space-y-3">
                <SectionHeading title="Timeline resumida" />
                <SubagentTimelineMini events={subagent.timeline_events} />
              </section>

              <section className="space-y-3">
                <SectionHeading title="Tools usadas" />
                {summary?.tools_used?.length ? (
                  <div className="flex flex-wrap gap-2">
                    {summary.tools_used.map((tool) => (
                      <Badge key={tool} variant="outline" className="px-2 py-0 text-[10px]">
                        {tool}
                      </Badge>
                    ))}
                  </div>
                ) : (
                  <div className="rounded-2xl border border-dashed border-border px-4 py-4 text-sm text-muted-foreground">
                    Nenhuma tool registrada até agora.
                  </div>
                )}
              </section>

              <section className="space-y-3">
                <SectionHeading title="Transcript da sessão filha" />
                {isLoadingMessages && messages.length === 0 ? (
                  <div className="rounded-2xl border border-dashed border-border px-4 py-5 text-sm text-muted-foreground">
                    Loading child transcript...
                  </div>
                ) : messages.length === 0 ? (
                  <div className="rounded-2xl border border-dashed border-border px-4 py-5 text-sm text-muted-foreground">
                    Nenhuma mensagem persistida ainda para esta sessão filha.
                  </div>
                ) : (
                  <div className="rounded-2xl border border-border/70 bg-background">
                    {messages.map((message, index) => (
                      <div key={message.id}>
                        {index > 0 ? <Separator /> : null}
                        <div className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <Badge variant={message.role === 'assistant' ? 'default' : 'outline'}>
                              {message.role}
                            </Badge>
                            <span className="text-xs text-muted-foreground">
                              {formatTimestamp(message.created_at)}
                            </span>
                          </div>
                          <p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-foreground">
                            {message.content_text}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </section>
            </>
          ) : null}
        </div>
      </ScrollArea>
    </SheetContent>
  );
}

function SectionHeading({ title }: { title: string }) {
  return (
    <div className="flex items-center justify-between">
      <h3 className="text-sm font-semibold tracking-tight text-foreground">{title}</h3>
    </div>
  );
}

function MetaTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-border/70 bg-background px-3 py-3">
      <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
        {label}
      </p>
      <p className="mt-1 text-sm text-foreground">{value}</p>
    </div>
  );
}
