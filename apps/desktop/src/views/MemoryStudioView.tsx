import { useEffect, useState } from 'react';
import { Archive, EyeOff, History, MoreHorizontal, Plus, RotateCcw, Search, Sparkles, Trash2 } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Sheet, SheetContent, SheetDescription, SheetTitle } from '@/components/ui/sheet';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import type { useAppController } from '../hooks/useAppController';
import type { MemoryItemCreateInput, MemoryItemRecord } from '../lib/backend/memory';

type AppController = ReturnType<typeof useAppController>;

export interface MemoryStudioViewProps {
  memory: AppController['memory'];
}

type EditorState =
  | { mode: 'create'; seedKind: MemoryItemCreateInput['kind'] }
  | { mode: 'edit'; item: MemoryItemRecord }
  | null;

const TAB_LABELS = [
  { value: 'all', label: 'All Memories' },
  { value: 'stable', label: 'Stable Memory' },
  { value: 'episodic', label: 'Episodic Memory' },
  { value: 'session_summaries', label: 'Session Summaries' },
  { value: 'recall_log', label: 'Recall Log' },
] as const;

export function MemoryStudioView({ memory }: MemoryStudioViewProps) {
  const [editorState, setEditorState] = useState<EditorState>(null);
  const [draft, setDraft] = useState<MemoryItemCreateInput>({
    kind: 'stable',
    title: '',
    content: '',
    scope: 'global',
    importance: 'medium',
  });
  const {
    activeTab,
    loadMemoryStudio,
    modeFilter,
    scopeFilter,
    searchText,
    sourceKindFilter,
    stateFilter,
  } = memory;

  useEffect(() => {
    void loadMemoryStudio();
  }, [
    activeTab,
    loadMemoryStudio,
    modeFilter,
    scopeFilter,
    searchText,
    sourceKindFilter,
    stateFilter,
  ]);

  function openCreateDialog(seedKind: MemoryItemCreateInput['kind']) {
    setDraft({
      kind: seedKind,
      title: '',
      content: '',
      scope: 'global',
      importance: 'medium',
    });
    setEditorState({ mode: 'create', seedKind });
  }

  function openEditDialog(item: MemoryItemRecord) {
    setDraft({
      kind: item.kind,
      title: item.title,
      content: item.content,
      scope: item.scope,
      importance: item.importance,
    });
    setEditorState({ mode: 'edit', item });
  }

  async function handleSubmitEditor() {
    if (!draft.title.trim() || !draft.content.trim()) {
      return;
    }

    if (editorState?.mode === 'edit') {
      await memory.handleUpdateMemory(editorState.item.id, {
        title: draft.title,
        content: draft.content,
        scope: draft.scope,
        importance: draft.importance,
      });
    } else {
      await memory.handleCreateMemory(draft);
    }
    setEditorState(null);
  }

  const isRecallLogTab = memory.activeTab === 'recall_log';
  const hasActiveFilters =
    !!memory.searchText.trim() ||
    !!memory.scopeFilter ||
    !!memory.sourceKindFilter ||
    memory.stateFilter !== 'active' ||
    memory.modeFilter !== 'all';

  return (
    <div className="space-y-5 animate-fade-in">
      <section className="overflow-hidden rounded-[1.75rem] border border-border/80 bg-[linear-gradient(135deg,color-mix(in_srgb,var(--color-muted)_24%,white_76%)_0%,color-mix(in_srgb,var(--color-background)_94%,#d1b483_6%)_100%)] shadow-[0_24px_60px_rgba(15,23,42,0.08)]">
        <div className="grid gap-5 px-6 py-6 lg:grid-cols-[minmax(0,1.15fr)_minmax(20rem,0.85fr)]">
          <div className="space-y-3">
            <Badge variant="outline" className="rounded-full px-3 py-1 text-[10px] uppercase tracking-[0.18em]">
              Memory Studio
            </Badge>
            <h3 className="max-w-xl text-2xl font-semibold tracking-tight text-foreground">
              Make recall legible, editable, and reversible.
            </h3>
            <p className="max-w-2xl text-sm leading-7 text-muted-foreground">
              Stable facts, episodic traces, session summaries, and the recall log all live in one
              workspace so memory stops feeling like hidden machinery.
            </p>
          </div>

          <div className="grid gap-3 rounded-[1.4rem] border border-border/70 bg-background/80 p-4">
            <div className="grid gap-3 md:grid-cols-[minmax(0,1.3fr)_repeat(3,minmax(0,1fr))]">
              <div className="relative md:col-span-1">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  value={memory.searchText}
                  onChange={(event) => memory.setSearchText(event.target.value)}
                  className="pl-9"
                  placeholder="Search titles, content, or source"
                />
              </div>

              <Select
                value={memory.scopeFilter || 'all'}
                onValueChange={(value) =>
                  memory.setScopeFilter(value === 'all' ? '' : value)
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="Scope" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All scopes</SelectItem>
                  <SelectItem value="global">Global</SelectItem>
                  <SelectItem value="profile">Profile</SelectItem>
                  <SelectItem value="workspace">Workspace</SelectItem>
                </SelectContent>
              </Select>

              <Select
                value={memory.sourceKindFilter || 'all'}
                onValueChange={(value) =>
                  memory.setSourceKindFilter(value === 'all' ? '' : value)
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="Source kind" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All sources</SelectItem>
                  <SelectItem value="manual">Manual</SelectItem>
                  <SelectItem value="autosaved">Auto-saved</SelectItem>
                </SelectContent>
              </Select>

              <Select
                value={memory.modeFilter}
                onValueChange={(value) =>
                  memory.setModeFilter(value as AppController['memory']['modeFilter'])
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="Mode" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Manual + automatic</SelectItem>
                  <SelectItem value="manual">Manual only</SelectItem>
                  <SelectItem value="automatic">Automatic only</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3">
              <Select
                value={memory.stateFilter}
                onValueChange={(value) =>
                  memory.setStateFilter(value as AppController['memory']['stateFilter'])
                }
              >
                <SelectTrigger className="w-[13rem]">
                  <SelectValue placeholder="State" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="active">Active</SelectItem>
                  <SelectItem value="hidden">Hidden from recall</SelectItem>
                  <SelectItem value="deleted">Deleted</SelectItem>
                </SelectContent>
              </Select>

              <Button
                type="button"
                className="gap-2 rounded-xl"
                onClick={() =>
                  openCreateDialog(
                    memory.activeTab === 'episodic'
                      ? 'episodic'
                      : memory.activeTab === 'session_summaries'
                        ? 'session_summary'
                        : 'stable',
                  )
                }
              >
                <Plus className="h-4 w-4" />
                Create memory
              </Button>
            </div>
          </div>
        </div>
      </section>

      <Tabs
        defaultValue={memory.activeTab}
        value={memory.activeTab}
        onValueChange={(value) =>
          memory.setActiveTab(value as AppController['memory']['activeTab'])
        }
      >
        <TabsList className="flex h-auto w-full flex-wrap justify-start gap-2 rounded-[1.2rem] bg-muted/35 p-1.5">
          {TAB_LABELS.map((tab) => (
            <TabsTrigger
              key={tab.value}
              value={tab.value}
              className="rounded-[0.95rem] px-3.5 py-2 text-xs font-medium tracking-[0.06em]"
            >
              {tab.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {isRecallLogTab ? (
        <section className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h3 className="text-sm font-semibold tracking-[0.12em] text-foreground">
                Memory recall log
              </h3>
              <p className="mt-1 text-sm text-muted-foreground">
                Every assistant reply that used recalled memory is listed here.
              </p>
            </div>
            <Badge variant="outline">{memory.recallLog.length} event(s)</Badge>
          </div>

          {memory.recallLog.length === 0 ? (
            <EmptyState
              title="No recall events yet"
              description="Once the agent injects memory into replies, the reasons and sources will appear here."
              icon={Sparkles}
            />
          ) : (
            <div className="space-y-3">
              {memory.recallLog.map((event) => (
                <article
                  key={event.id}
                  className="rounded-[1.4rem] border border-border/70 bg-background px-5 py-4 shadow-sm"
                >
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold tracking-tight text-foreground">
                        {event.reason_summary || 'Memory used for this reply'}
                      </p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        Session {event.session_id} · {new Date(event.created_at).toLocaleString()}
                      </p>
                    </div>
                    <Badge variant="secondary">{event.items.length} recalled</Badge>
                  </div>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {event.items.map((item) => (
                      <Button
                        key={item.memory_id}
                        type="button"
                        variant="secondary"
                        size="sm"
                        className="h-8 rounded-full border border-border/80 bg-background"
                        onClick={() => void memory.handleOpenDetail(item.memory_id)}
                      >
                        {item.title}
                      </Button>
                    ))}
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      ) : memory.memoryItems.length === 0 ? (
        <EmptyState
          title={
            memory.modeFilter === 'manual'
              ? 'No manual memories yet'
              : hasActiveFilters
                ? 'No results'
                : 'No memories yet'
          }
          description={
            memory.modeFilter === 'manual'
              ? 'Manual memories will appear here after you add your first note or override.'
              : hasActiveFilters
                ? 'Try widening the filters or using a broader search phrase.'
                : 'Start by adding a manual memory or let the agent build recall history over time.'
          }
          icon={memory.modeFilter === 'manual' ? Plus : Archive}
        />
      ) : (
        <section className="overflow-hidden rounded-[1.5rem] border border-border/70 bg-background shadow-sm">
          <Table>
            <TableHeader className="bg-muted/30">
              <TableRow className="hover:bg-transparent">
                <TableHead>Title</TableHead>
                <TableHead>Source</TableHead>
                <TableHead>Scope</TableHead>
                <TableHead>Updated</TableHead>
                <TableHead>Recall status</TableHead>
                <TableHead>Importance</TableHead>
                <TableHead className="w-[3.5rem]" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {memory.memoryItems.map((item) => (
                <TableRow key={item.id} className="group">
                  <TableCell>
                    <button
                      type="button"
                      className="space-y-1 text-left"
                      onClick={() => void memory.handleOpenDetail(item.id)}
                    >
                      <p className="font-medium tracking-tight text-foreground">{item.title}</p>
                      <div className="flex flex-wrap gap-1.5">
                        <MemoryBadge item={item} />
                      </div>
                    </button>
                  </TableCell>
                  <TableCell>{item.source_label}</TableCell>
                  <TableCell>{item.scope}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {new Date(item.updated_at).toLocaleString()}
                  </TableCell>
                  <TableCell>
                    <Badge variant={item.recall_status === 'hidden' ? 'warning' : 'success'}>
                      {item.recall_status}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">{item.importance}</Badge>
                  </TableCell>
                  <TableCell className="text-right">
                    <DropdownMenu>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <DropdownMenuTrigger asChild>
                            <Button
                              variant="ghost"
                              size="icon"
                              aria-label={`Actions for ${item.title}`}
                              className="h-8 w-8"
                            >
                              <MoreHorizontal className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                        </TooltipTrigger>
                        <TooltipContent>Actions</TooltipContent>
                      </Tooltip>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => openEditDialog(item)}>
                          Edit memory
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => void memory.handleOpenDetail(item.id)}>
                          <History className="mr-2 h-4 w-4" />
                          View history
                        </DropdownMenuItem>
                        {item.recall_status === 'hidden' || item.state === 'deleted' ? (
                          <DropdownMenuItem onClick={() => void memory.handleRestoreMemory(item.id)}>
                            <RotateCcw className="mr-2 h-4 w-4" />
                            Restore
                          </DropdownMenuItem>
                        ) : (
                          <DropdownMenuItem onClick={() => void memory.handleHideMemory(item.id)}>
                            <EyeOff className="mr-2 h-4 w-4" />
                            Hide from recall
                          </DropdownMenuItem>
                        )}
                        <DropdownMenuItem onClick={() => void memory.handlePromoteMemory(item.id)}>
                          Promote
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => void memory.handleDemoteMemory(item.id)}>
                          Demote
                        </DropdownMenuItem>
                        {item.state === 'deleted' ? (
                          <DropdownMenuItem
                            onClick={() => {
                              if (window.confirm('Delete this memory permanently?')) {
                                void memory.handleDeleteMemory(item.id, true);
                              }
                            }}
                            className="text-destructive"
                          >
                            <Trash2 className="mr-2 h-4 w-4" />
                            Delete permanently
                          </DropdownMenuItem>
                        ) : (
                          <DropdownMenuItem
                            onClick={() => void memory.handleDeleteMemory(item.id)}
                          >
                            <Archive className="mr-2 h-4 w-4" />
                            Delete
                          </DropdownMenuItem>
                        )}
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </section>
      )}

      <Dialog open={editorState !== null} onOpenChange={(open) => !open && setEditorState(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {editorState?.mode === 'edit' ? 'Edit memory' : 'Create manual memory'}
            </DialogTitle>
            <DialogDescription>
              Use manual notes and overrides to keep recall understandable and under your control.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4">
            <div className="grid gap-2">
              <Label htmlFor="memory-kind">Kind</Label>
              <Select
                value={draft.kind}
                onValueChange={(value) =>
                  setDraft((current) => ({
                    ...current,
                    kind: value as MemoryItemCreateInput['kind'],
                  }))
                }
                disabled={editorState?.mode === 'edit'}
              >
                <SelectTrigger id="memory-kind">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="stable">Stable memory</SelectItem>
                  <SelectItem value="episodic">Episodic memory</SelectItem>
                  <SelectItem value="session_summary">Session summary</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="grid gap-2">
              <Label htmlFor="memory-title">Title</Label>
              <Input
                id="memory-title"
                value={draft.title}
                onChange={(event) =>
                  setDraft((current) => ({ ...current, title: event.target.value }))
                }
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="memory-content">Content</Label>
              <Textarea
                id="memory-content"
                rows={7}
                value={draft.content}
                onChange={(event) =>
                  setDraft((current) => ({ ...current, content: event.target.value }))
                }
              />
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label htmlFor="memory-scope">Scope</Label>
                <Input
                  id="memory-scope"
                  value={draft.scope}
                  onChange={(event) =>
                    setDraft((current) => ({ ...current, scope: event.target.value }))
                  }
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="memory-importance">Importance</Label>
                <Select
                  value={draft.importance}
                  onValueChange={(value) =>
                    setDraft((current) => ({
                      ...current,
                      importance: value as MemoryItemCreateInput['importance'],
                    }))
                  }
                >
                  <SelectTrigger id="memory-importance">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="low">Low</SelectItem>
                    <SelectItem value="medium">Medium</SelectItem>
                    <SelectItem value="high">High</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="flex justify-end gap-2">
              <Button type="button" variant="ghost" onClick={() => setEditorState(null)}>
                Cancel
              </Button>
              <Button type="button" onClick={() => void handleSubmitEditor()}>
                {editorState?.mode === 'edit' ? 'Save changes' : 'Create memory'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Sheet
        open={Boolean(memory.selectedMemory)}
        onOpenChange={(open) => {
          if (!open) {
            memory.setSelectedMemory(null);
          }
        }}
      >
        <SheetContent
          side="right"
          className="w-full border-l border-border/80 p-0 sm:w-[min(92vw,36rem)]"
        >
          {memory.selectedMemory ? (
            <>
              <div className="border-b border-border/70 px-6 py-5">
                <SheetTitle>{memory.selectedMemory.title}</SheetTitle>
                <SheetDescription className="mt-1">
                  Full content, origin, and change history for this memory item.
                </SheetDescription>
              </div>
              <ScrollArea className="min-h-0 flex-1">
                <div className="space-y-5 px-6 py-5">
                  <section className="rounded-3xl border border-border/70 bg-[color-mix(in_srgb,white_92%,var(--color-muted)_8%)] px-5 py-4">
                    <div className="flex flex-wrap gap-2">
                      <MemoryBadge item={memory.selectedMemory} />
                    </div>
                    <p className="mt-4 whitespace-pre-wrap text-sm leading-7 text-foreground">
                      {memory.selectedMemory.content}
                    </p>
                  </section>

                  <section className="grid gap-3 sm:grid-cols-2">
                    <MetaBlock label="Source" value={memory.selectedMemory.source_label} />
                    <MetaBlock label="Scope" value={memory.selectedMemory.scope} />
                    <MetaBlock
                      label="Origin session"
                      value={memory.selectedMemory.origin_session_id || 'None'}
                    />
                    <MetaBlock
                      label="Origin subagent"
                      value={memory.selectedMemory.origin_subagent_session_id || 'None'}
                    />
                  </section>

                  <section className="space-y-3">
                    <div>
                      <h4 className="text-sm font-semibold tracking-tight text-foreground">
                        Change history
                      </h4>
                      <p className="mt-1 text-sm text-muted-foreground">
                        Every override, state change, and recall-control adjustment stays visible.
                      </p>
                    </div>
                    {memory.selectedMemoryHistory.length === 0 ? (
                      <div className="rounded-2xl border border-dashed border-border px-4 py-5 text-sm text-muted-foreground">
                        No history recorded yet.
                      </div>
                    ) : (
                      <div className="space-y-3">
                        {memory.selectedMemoryHistory.map((entry) => (
                          <article
                            key={entry.id}
                            className="rounded-2xl border border-border/70 bg-background px-4 py-4"
                          >
                            <div className="flex items-center justify-between gap-3">
                              <Badge variant="outline">{entry.action.replace('_', ' ')}</Badge>
                              <span className="text-xs text-muted-foreground">
                                {new Date(entry.created_at).toLocaleString()}
                              </span>
                            </div>
                            {entry.summary ? (
                              <p className="mt-2 text-sm text-foreground">{entry.summary}</p>
                            ) : null}
                          </article>
                        ))}
                      </div>
                    )}
                  </section>
                </div>
              </ScrollArea>
            </>
          ) : null}
        </SheetContent>
      </Sheet>
    </div>
  );
}

function MemoryBadge({ item }: { item: MemoryItemRecord }) {
  return (
    <>
      <Badge variant="outline">{item.kind.replace('_', ' ')}</Badge>
      <Badge variant={item.is_manual ? 'secondary' : 'outline'}>
        {item.is_manual ? 'manual' : 'auto-saved'}
      </Badge>
      {item.is_override ? <Badge variant="warning">override</Badge> : null}
      {item.recall_status === 'hidden' ? <Badge variant="warning">hidden</Badge> : null}
      {item.state === 'deleted' ? <Badge variant="destructive">deleted</Badge> : null}
    </>
  );
}

function MetaBlock({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-border/70 bg-background px-4 py-4">
      <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
        {label}
      </p>
      <p className="mt-1 text-sm text-foreground">{value}</p>
    </div>
  );
}

function EmptyState({
  description,
  icon: Icon,
  title,
}: {
  description: string;
  icon: typeof Plus;
  title: string;
}) {
  return (
    <div className="rounded-[1.5rem] border border-dashed border-border bg-muted/15 px-6 py-14 text-center">
      <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-background text-muted-foreground shadow-sm">
        <Icon className="h-5 w-5" />
      </div>
      <p className="mt-4 text-base font-semibold tracking-tight text-foreground">{title}</p>
      <p className="mx-auto mt-2 max-w-md text-sm leading-7 text-muted-foreground">
        {description}
      </p>
    </div>
  );
}
