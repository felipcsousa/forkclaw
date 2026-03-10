import { Menu, MoreHorizontal, RefreshCw } from 'lucide-react';

import { AppSidebar } from './components/AppSidebar';
import { ActivityTimelinePanel } from './components/ActivityTimelinePanel';
import { AgentSettingsPanel } from './components/AgentSettingsPanel';
import { ApprovalsInbox } from './components/ApprovalsInbox';
import { ChatComposer } from './components/ChatComposer';
import { ChatTimeline } from './components/ChatTimeline';
import { CronJobsPanel } from './components/CronJobsPanel';
import { OperationalSettingsPanel } from './components/OperationalSettingsPanel';
import { ToolPermissionsPanel } from './components/ToolPermissionsPanel';
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
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from './components/ui/tooltip';
import { useAppController } from './hooks/useAppController';

function App() {
  const {
    activeApprovalId,
    activeJobsCount,
    activeSession,
    activeView,
    activityItems,
    agent,
    agentDraft,
    agentTitle,
    approvals,
    cronJobs,
    draft,
    errorMessage,
    getViewCount,
    handleActivateJob,
    handleAgentDraftChange,
    handleApproveApproval,
    handleChangeToolPolicyProfile,
    handleChangeToolPermission,
    handleCreateJob,
    handleCreateSession,
    handleDenyApproval,
    handleOperationalDraftChange,
    handlePauseJob,
    handleRefreshCurrentView,
    handleRemoveJob,
    handleResetAgentConfig,
    handleSaveAgentConfig,
    handleSaveOperationalSettings,
    handleSelectSession,
    handleSendMessage,
    handleToggleSkill,
    heartbeat,
    isActingOnApproval,
    isBootstrapping,
    isComposerDisabled,
    isCreatingJob,
    isCreatingSession,
    isDesktop,
    isLoadingActivity,
    isLoadingAgent,
    isLoadingApprovals,
    isLoadingJobs,
    isLoadingMessages,
    isLoadingOperationalSettings,
    isLoadingTools,
    isMutatingJob,
    isResettingAgent,
    isSavingAgent,
    isSavingOperationalSettings,
    isSending,
    isUpdatingToolPermission,
    isWorkspaceSyncing,
    jobHistory,
    messages,
    mobileNavOpen,
    navigateTo,
    operationalDraft,
    operationalSettings,
    pendingApprovalsCount,
    providerLabel,
    sessions,
    setActiveApprovalId,
    setDraft,
    setErrorMessage,
    setMobileNavOpen,
    skills,
    skillsStrategy,
    toolCalls,
    toolCatalog,
    toolPolicy,
    toolPermissions,
    view,
    workspaceRoot,
  } = useAppController();

  function renderViewContent() {
    if (view === 'chat') {
      return (
        <div className="min-h-0 flex flex-1 flex-col rounded-[1.4rem] border border-border/80 bg-[color-mix(in_srgb,white_92%,var(--color-muted)_8%)] shadow-[0_14px_32px_rgba(15,23,42,0.04)]">
          <div className="min-h-0 flex-1 px-6 py-5">
            <ChatTimeline
              session={activeSession}
              messages={messages}
              isLoading={isBootstrapping || isLoadingMessages}
              isSending={isSending}
            />
          </div>
          <ChatComposer
            draft={draft}
            disabled={isComposerDisabled}
            isSending={isSending}
            sessionTitle={activeSession?.title || null}
            onDraftChange={setDraft}
            onSubmit={handleSendMessage}
          />
        </div>
      );
    }

    if (view === 'profile') {
      return (
        <AgentSettingsPanel
          agent={agent}
          draft={agentDraft}
          isLoading={isLoadingAgent}
          isSaving={isSavingAgent}
          isResetting={isResettingAgent}
          onDraftChange={handleAgentDraftChange}
          onSave={handleSaveAgentConfig}
          onReset={handleResetAgentConfig}
        />
      );
    }

    if (view === 'settings') {
      return (
        <OperationalSettingsPanel
          settings={operationalSettings}
          draft={operationalDraft}
          isLoading={isLoadingOperationalSettings}
          isSaving={isSavingOperationalSettings}
          onDraftChange={handleOperationalDraftChange}
          onSave={handleSaveOperationalSettings}
        />
      );
    }

    if (view === 'tools') {
      return (
        <ToolPermissionsPanel
          catalog={toolCatalog}
          policy={toolPolicy}
          workspaceRoot={workspaceRoot}
          permissions={toolPermissions}
          calls={toolCalls}
          skills={skills}
          skillsStrategy={skillsStrategy}
          isLoading={isLoadingTools}
          isUpdating={isUpdatingToolPermission}
          onChangeProfile={handleChangeToolPolicyProfile}
          onChangePermission={handleChangeToolPermission}
          onToggleSkill={handleToggleSkill}
        />
      );
    }

    if (view === 'approvals') {
      return (
        <ApprovalsInbox
          approvals={approvals}
          activeApprovalId={activeApprovalId}
          isLoading={isLoadingApprovals}
          isActing={isActingOnApproval}
          onSelectApproval={setActiveApprovalId}
          onApprove={handleApproveApproval}
          onDeny={handleDenyApproval}
        />
      );
    }

    if (view === 'jobs') {
      return (
        <CronJobsPanel
          jobs={cronJobs}
          history={jobHistory}
          heartbeat={heartbeat}
          isLoading={isLoadingJobs}
          isCreating={isCreatingJob}
          isMutating={isMutatingJob}
          onCreateJob={handleCreateJob}
          onPauseJob={handlePauseJob}
          onActivateJob={handleActivateJob}
          onRemoveJob={handleRemoveJob}
        />
      );
    }

    return (
      <ActivityTimelinePanel
        items={activityItems}
        isLoading={isLoadingActivity}
      />
    );
  }

  const sidebar = (
    <AppSidebar
      view={view}
      agentTitle={agentTitle}
      providerLabel={providerLabel}
      pendingApprovalsCount={pendingApprovalsCount}
      activeJobsCount={activeJobsCount}
      isWorkspaceSyncing={isWorkspaceSyncing}
      sessions={sessions}
      activeSessionId={activeSession?.id || null}
      isCreatingSession={isCreatingSession}
      isLoadingSessions={isBootstrapping}
      getViewCount={getViewCount}
      onNavigate={navigateTo}
      onCreateSession={handleCreateSession}
      onSelectSession={handleSelectSession}
    />
  );

  return (
    <div className="flex h-screen w-full bg-background text-foreground overflow-hidden">
      {/* Desktop Sidebar */}
      {isDesktop ? (
        <div className="w-[260px] shrink-0 bg-sidebar z-20 shadow-sm relative">
          {sidebar}
        </div>
      ) : null}

      {/* Main Content Area */}
      <div className="flex min-w-0 flex-1 flex-col bg-background">
        {/* Global Header */}
        <header className="sticky top-0 z-10 flex h-14 shrink-0 items-center justify-between border-b border-border bg-background/95 px-5 md:px-6 backdrop-blur supports-[backdrop-filter]:bg-background/60">
          <div className="flex items-center gap-4">
            {!isDesktop ? (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={() => setMobileNavOpen(true)}
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
                  {!isDesktop && <BreadcrumbItem>{agentTitle}</BreadcrumbItem>}
                  {!isDesktop && <BreadcrumbSeparator />}
                  <BreadcrumbItem>
                    <BreadcrumbPage className="font-semibold text-foreground">
                      {activeView.label}
                    </BreadcrumbPage>
                  </BreadcrumbItem>
                </BreadcrumbList>
              </Breadcrumb>
              {isDesktop && (
                <>
                  <Separator orientation="vertical" className="h-4" />
                  <p className="truncate text-sm text-muted-foreground">
                    {activeView.hint}
                  </p>
                </>
              )}
            </div>
          </div>

          <div className="flex shrink-0 items-center gap-2">
            <Badge
              variant={isWorkspaceSyncing ? 'warning' : 'outline'}
              className="hidden sm:inline-flex rounded-md font-medium"
            >
              {isWorkspaceSyncing ? 'Syncing' : 'Ready'}
            </Badge>
            <Badge
              variant="outline"
              className="hidden sm:inline-flex rounded-md font-medium"
            >
              {providerLabel}
            </Badge>
            {pendingApprovalsCount > 0 ? (
              <Badge variant="warning" className="rounded-md font-medium">
                {pendingApprovalsCount} pending
              </Badge>
            ) : null}

            <Separator
              orientation="vertical"
              className="mx-1 h-4 hidden sm:block"
            />

            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 text-muted-foreground hover:text-foreground"
                  onClick={() => void handleRefreshCurrentView()}
                  disabled={isWorkspaceSyncing}
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
                  onClick={() => void handleRefreshCurrentView()}
                >
                  Refresh view
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>

        {/* Scrollable Main Area */}
        <main
          className="flex-1 overflow-auto"
          data-testid={isDesktop ? 'desktop-shell' : undefined}
        >
          <div className="mx-auto w-full max-w-5xl p-5 md:p-8 lg:p-10">
            <div className="space-y-1.5 pb-4">
              <h2 className="text-2xl font-semibold tracking-tight text-foreground">
                {view === 'chat'
                  ? activeSession?.title || 'New Session'
                  : activeView.title}
              </h2>
              <p className="text-sm leading-relaxed text-muted-foreground">
                {activeView.description}
              </p>
            </div>

            {errorMessage ? (
              <div
                className="mb-6 rounded-[0.5rem] border border-destructive/20 bg-destructive/10 px-4 py-3 text-sm text-destructive"
                role="alert"
              >
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <strong className="font-semibold">
                      Something needs attention
                    </strong>
                    <p className="mt-0.5 opacity-90">{errorMessage}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="secondary"
                      size="sm"
                      className="h-7 text-xs"
                      type="button"
                      onClick={() => void handleRefreshCurrentView()}
                    >
                      Reload
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 text-xs hover:bg-destructive/20"
                      type="button"
                      onClick={() => setErrorMessage(null)}
                    >
                      Dismiss
                    </Button>
                  </div>
                </div>
              </div>
            ) : null}

            <div className="min-h-0">{renderViewContent()}</div>
          </div>
        </main>
      </div>

      <Sheet open={mobileNavOpen} onOpenChange={setMobileNavOpen}>
        <SheetContent
          side="left"
          className="w-[min(88vw,260px)] p-0 border-r-0"
          data-testid="app-sidebar-sheet"
        >
          <SheetTitle className="sr-only">Navigation</SheetTitle>
          <SheetDescription className="sr-only">
            Navigate between chats, approvals, jobs, tools, and settings.
          </SheetDescription>
          <div className="h-full bg-sidebar">{sidebar}</div>
        </SheetContent>
      </Sheet>
    </div>
  );
}

export default App;
