import { Menu, MoreHorizontal, RefreshCw } from 'lucide-react';

import { AppSidebar } from './components/AppSidebar';
import { Badge } from './components/ui/badge';
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from './components/ui/breadcrumb';
import { Button } from './components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from './components/ui/dropdown-menu';
import { Separator } from './components/ui/separator';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetTitle,
} from './components/ui/sheet';
import { SubagentSessionSheet } from './components/SubagentSessionSheet';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from './components/ui/tooltip';
import { useAppController } from './hooks/useAppController';
import { ActivityView } from './views/ActivityView';
import { ApprovalsView } from './views/ApprovalsView';
import { ChatWorkspace } from './views/ChatWorkspace';
import { JobsView } from './views/JobsView';
import { MemoryStudioView } from './views/MemoryStudioView';
import { ProfileView } from './views/ProfileView';
import { SettingsView } from './views/SettingsView';
import { ToolsView } from './views/ToolsView';

function App() {
  const {
    activity,
    agentProfile,
    app,
    approvals,
    chat,
    jobs,
    memory,
    operationalSettings,
    shell,
    tooling,
  } = useAppController();

  function renderCurrentView() {
    switch (shell.view) {
      case 'chat':
        return (
          <ChatWorkspace
            app={app}
            chat={chat}
            onOpenMemory={(memoryId) => {
              void memory.handleOpenMemoryStudioItem(memoryId);
            }}
            onRefresh={() => {
              void app.handleRefreshCurrentView();
            }}
          />
        );
      case 'profile':
        return <ProfileView profile={agentProfile} />;
      case 'settings':
        return <SettingsView settings={operationalSettings} />;
      case 'tools':
        return <ToolsView tooling={tooling} />;
      case 'memory':
        return <MemoryStudioView memory={memory} />;
      case 'approvals':
        return <ApprovalsView approvals={approvals} />;
      case 'jobs':
        return <JobsView jobs={jobs} />;
      case 'activity':
        return (
          <ActivityView
            activity={activity}
            onOpenSubagent={chat.handleOpenSubagent}
          />
        );
      default:
        return null;
    }
  }

  const sidebar = (
    <AppSidebar
      view={shell.view}
      agentTitle={app.agentTitle}
      providerLabel={app.providerLabel}
      pendingApprovalsCount={app.pendingApprovalsCount}
      activeJobsCount={app.activeJobsCount}
      isWorkspaceSyncing={app.isWorkspaceSyncing}
      sessions={chat.sessions}
      activeSessionId={chat.activeSession?.id || null}
      isCreatingSession={chat.isCreatingSession}
      isLoadingSessions={chat.isBootstrapping}
      getViewCount={app.getViewCount}
      onNavigate={shell.navigateTo}
      onCreateSession={() => {
        void chat.handleCreateSession();
      }}
      onSelectSession={(sessionId) => {
        void chat.handleSelectSession(sessionId);
      }}
    />
  );

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background text-foreground">
      {shell.isDesktop ? (
        <div className="relative z-20 w-[260px] shrink-0 bg-sidebar shadow-sm">
          {sidebar}
        </div>
      ) : null}

      <div className="flex min-w-0 flex-1 flex-col bg-background">
        <header className="sticky top-0 z-10 flex h-14 shrink-0 items-center justify-between border-b border-border bg-background/95 px-5 backdrop-blur supports-[backdrop-filter]:bg-background/60 md:px-6">
          <div className="flex items-center gap-4">
            {!shell.isDesktop ? (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={() => shell.setMobileNavOpen(true)}
                    aria-label="Open navigation"
                  >
                    <Menu className="h-4 w-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Open navigation</TooltipContent>
              </Tooltip>
            ) : null}

            <div className="flex items-center gap-3">
              <Breadcrumb>
                <BreadcrumbList>
                  {!shell.isDesktop && <BreadcrumbItem>{app.agentTitle}</BreadcrumbItem>}
                  {!shell.isDesktop && <BreadcrumbSeparator />}
                  <BreadcrumbItem>
                    <BreadcrumbPage className="font-semibold text-foreground">
                      {shell.activeView.label}
                    </BreadcrumbPage>
                  </BreadcrumbItem>
                </BreadcrumbList>
              </Breadcrumb>
              {shell.isDesktop ? (
                <>
                  <Separator orientation="vertical" className="h-4" />
                  <p className="truncate text-sm text-muted-foreground">
                    {shell.activeView.hint}
                  </p>
                </>
              ) : null}
            </div>
          </div>

          <div className="flex shrink-0 items-center gap-2">
            <Badge
              variant={app.isWorkspaceSyncing ? 'warning' : 'outline'}
              className="hidden rounded-md font-medium sm:inline-flex"
            >
              {app.isWorkspaceSyncing ? 'Syncing' : 'Ready'}
            </Badge>
            <Badge
              variant="outline"
              className="hidden rounded-md font-medium sm:inline-flex"
            >
              {app.providerLabel}
            </Badge>
            {app.pendingApprovalsCount > 0 ? (
              <Badge variant="warning" className="rounded-md font-medium">
                {app.pendingApprovalsCount} pending
              </Badge>
            ) : null}

            <Separator orientation="vertical" className="mx-1 hidden h-4 sm:block" />

            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 text-muted-foreground hover:text-foreground"
                  onClick={() => {
                    void app.handleRefreshCurrentView();
                  }}
                  disabled={app.isWorkspaceSyncing}
                  aria-label="Refresh view"
                >
                  <RefreshCw className="h-3.5 w-3.5" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Refresh view</TooltipContent>
            </Tooltip>

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 text-muted-foreground hover:text-foreground"
                  aria-label="More actions"
                >
                  <MoreHorizontal className="h-3.5 w-3.5" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuLabel>Workspace</DropdownMenuLabel>
                <DropdownMenuItem
                  onClick={() => {
                    void app.handleRefreshCurrentView();
                  }}
                >
                  Refresh view
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>

        <main
          className="flex-1 overflow-auto"
          data-testid={shell.isDesktop ? 'desktop-shell' : undefined}
        >
          <div className="mx-auto w-full max-w-5xl p-5 md:p-8 lg:p-10">
            <div className="space-y-1.5 pb-4">
              <h2 className="text-2xl font-semibold tracking-tight text-foreground">
                {shell.view === 'chat'
                  ? chat.activeSession?.title || 'New Session'
                  : shell.activeView.title}
              </h2>
              <p className="text-sm leading-relaxed text-muted-foreground">
                {shell.activeView.description}
              </p>
            </div>

            {app.errorMessage ? (
              <div
                className="mb-6 rounded-[0.5rem] border border-destructive/20 bg-destructive/10 px-4 py-3 text-sm text-destructive"
                role="alert"
              >
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <strong className="font-semibold">
                      Something needs attention
                    </strong>
                    <p className="mt-0.5 opacity-90">{app.errorMessage}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="secondary"
                      size="sm"
                      className="h-7 text-xs"
                      type="button"
                      onClick={() => {
                        void app.handleRefreshCurrentView();
                      }}
                    >
                      Reload
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 text-xs hover:bg-destructive/20"
                      type="button"
                      onClick={() => app.setErrorMessage(null)}
                    >
                      Dismiss
                    </Button>
                  </div>
                </div>
              </div>
            ) : null}

            <div className="min-h-0">{renderCurrentView()}</div>
          </div>
        </main>
      </div>

      <Sheet open={shell.mobileNavOpen} onOpenChange={shell.setMobileNavOpen}>
        <SheetContent
          side="left"
          className="w-[min(88vw,260px)] border-r-0 p-0"
          data-testid="app-sidebar-sheet"
        >
          <SheetTitle className="sr-only">Navigation</SheetTitle>
          <SheetDescription className="sr-only">
            Navigate between chats, approvals, jobs, tools, and settings.
          </SheetDescription>
          <div className="h-full bg-sidebar">{sidebar}</div>
        </SheetContent>
      </Sheet>

      <Sheet
        open={chat.isSubagentSheetOpen}
        onOpenChange={chat.handleCloseSubagent}
      >
        <SubagentSessionSheet
          parentSession={chat.activeSession}
          subagent={chat.activeSubagent}
          messages={chat.activeSubagentMessages}
          isLoadingDetail={chat.isLoadingSubagentDetail}
          isLoadingMessages={chat.isLoadingSubagentMessages}
          errorMessage={chat.subagentDetailErrorMessage}
          hasPrevious={chat.activeSubagentHasPrevious}
          hasNext={chat.activeSubagentHasNext}
          onBackToParent={chat.handleReturnToParentSession}
          onPrevious={() => {
            void chat.handleOpenPreviousSubagent();
          }}
          onNext={() => {
            void chat.handleOpenNextSubagent();
          }}
        />
      </Sheet>
    </div>
  );
}

export default App;
