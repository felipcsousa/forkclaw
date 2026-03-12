import { ArrowUpRight, Loader2, StopCircle } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  canCancelSubagent,
  formatDuration,
  formatEstimatedCost,
  formatTimestamp,
  subagentStatusCopy,
  subagentStatusVariant,
} from '@/lib/subagents';
import type { SessionRecord, SubagentSessionRecord } from '../lib/backend';

interface SessionSubagentIndexProps {
  session: SessionRecord | null;
  items: SubagentSessionRecord[];
  isLoading: boolean;
  errorMessage: string | null;
  cancellingSubagentId: string | null;
  onOpen: (parentSessionId: string, childSessionId: string) => void;
  onCancel: (parentSessionId: string, childSessionId: string) => void;
  onRefresh: () => void;
}

export function SessionSubagentIndex({
  session,
  items,
  isLoading,
  errorMessage,
  cancellingSubagentId,
  onOpen,
  onCancel,
  onRefresh,
}: SessionSubagentIndexProps) {
  if (!session) {
    return null;
  }

  return (
    <section className="border-t border-border/70 px-6 py-5">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold tracking-tight text-foreground">
              Subagentes
            </h3>
            {session.subagent_counts?.total ? (
              <Badge variant="outline" className="px-2 py-0 text-[10px]">
                {session.subagent_counts.total} child sessions
              </Badge>
            ) : null}
          </div>
          <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
            Sessões filhas nativas desta conversa. Elas não aparecem na navegação global.
          </p>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-8 text-xs"
          onClick={onRefresh}
        >
          Atualizar
        </Button>
      </div>

      <div className="mt-4">
        {isLoading && items.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border px-4 py-6 text-sm text-muted-foreground">
            <span className="inline-flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading child sessions...
            </span>
          </div>
        ) : errorMessage ? (
          <div className="rounded-2xl border border-destructive/20 bg-destructive/5 px-4 py-5 text-sm text-destructive">
            <p className="font-medium">Não foi possível carregar os subagentes.</p>
            <p className="mt-1 opacity-90">{errorMessage}</p>
          </div>
        ) : items.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border px-4 py-6">
            <p className="text-sm font-medium text-foreground">Nenhuma sessão filha ainda.</p>
            <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
              Quando a sessão pai delegar nativamente uma tarefa, o resultado aparece aqui.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {items.map((item) => {
              const canCancel = canCancelSubagent(item.run.lifecycle_status);

              return (
                <article
                  key={item.id}
                  className="rounded-2xl border border-border/70 bg-background px-4 py-3 shadow-sm"
                >
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant={subagentStatusVariant(item.run.lifecycle_status)}>
                          {item.run.lifecycle_status}
                        </Badge>
                        <span className="text-xs font-medium text-foreground">
                          {item.delegated_goal || item.title}
                        </span>
                      </div>
                      <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                        {subagentStatusCopy(item.run.lifecycle_status)}
                      </p>
                      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
                        <span>Criado em {formatTimestamp(item.created_at)}</span>
                        <span>Duração {formatDuration(item.run)}</span>
                        <span>Custo {formatEstimatedCost(item.run.estimated_cost_usd)}</span>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <Button
                        type="button"
                        size="sm"
                        variant="secondary"
                        className="h-8 gap-1.5 text-xs"
                        onClick={() => onOpen(item.parent_session_id || '', item.id)}
                      >
                        <ArrowUpRight className="h-3.5 w-3.5" />
                        Abrir sessão filha
                      </Button>
                      {canCancel ? (
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          className="h-8 gap-1.5 text-xs text-destructive hover:bg-destructive/10 hover:text-destructive"
                          onClick={() => onCancel(item.parent_session_id || '', item.id)}
                          disabled={cancellingSubagentId === item.id}
                        >
                          <StopCircle className="h-3.5 w-3.5" />
                          {cancellingSubagentId === item.id ? 'Cancelando...' : 'Cancelar'}
                        </Button>
                      ) : null}
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}
