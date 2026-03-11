import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';

import App from './App';
import {
  DESKTOP_MAIN_PANEL_SIZE,
  DESKTOP_SIDEBAR_MAX_SIZE,
  DESKTOP_SIDEBAR_MIN_SIZE,
  DESKTOP_SIDEBAR_PANEL_SIZE,
} from './components/app-shell-layout';
import { TooltipProvider } from './components/ui/tooltip';

const baseTimestamp = '2026-03-08T12:00:00Z';

const mockFetchSessions = vi.fn();
const mockCreateSession = vi.fn();
const mockFetchSessionMessages = vi.fn();
const mockSendSessionMessage = vi.fn();
const mockFetchAgentConfig = vi.fn();
const mockUpdateAgentConfig = vi.fn();
const mockResetAgentConfig = vi.fn();
const mockFetchOperationalSettings = vi.fn();
const mockUpdateOperationalSettings = vi.fn();
const mockFetchToolCatalog = vi.fn();
const mockFetchToolPolicy = vi.fn();
const mockUpdateToolPolicy = vi.fn();
const mockFetchToolPermissions = vi.fn();
const mockFetchToolCalls = vi.fn();
const mockUpdateToolPermission = vi.fn();
const mockFetchSkills = vi.fn();
const mockUpdateSkill = vi.fn();
const mockFetchApprovals = vi.fn();
const mockApproveApproval = vi.fn();
const mockDenyApproval = vi.fn();
const mockFetchActivityTimeline = vi.fn();
const mockFetchCronJobsDashboard = vi.fn();
const mockCreateCronJob = vi.fn();
const mockPauseCronJob = vi.fn();
const mockActivateCronJob = vi.fn();
const mockDeleteCronJob = vi.fn();
const defaultMatchMedia = window.matchMedia;
const providerLabelMap: Record<string, string> = {
  product_echo: 'Product Echo (local fallback)',
  openai: 'OpenAI',
  anthropic: 'Anthropic',
  openrouter: 'OpenRouter',
  deepseek: 'DeepSeek',
  gemini: 'Gemini',
  'kimi-coding': 'Kimi for Coding',
};

const defaultHeartbeat = {
  last_run_at: null,
  task_run_id: null,
  cleaned_stale_runs: 0,
  pending_approvals: 0,
  recent_task_runs: 0,
  summary_text: 'Heartbeat has not run yet.',
};

function makeSession(overrides: Record<string, unknown> = {}) {
  return {
    id: 'session-1',
    agent_id: 'agent-1',
    title: 'Persistent Chat',
    summary: null,
    status: 'active',
    started_at: baseTimestamp,
    last_message_at: null,
    created_at: baseTimestamp,
    updated_at: baseTimestamp,
    ...overrides,
  };
}

function makeMessage(overrides: Record<string, unknown> = {}) {
  return {
    id: 'message-1',
    session_id: 'session-1',
    role: 'user',
    status: 'committed',
    sequence_number: 1,
    content_text: 'hello kernel',
    created_at: baseTimestamp,
    updated_at: baseTimestamp,
    ...overrides,
  };
}

function makeToolPermission(overrides: Record<string, unknown> = {}) {
  return {
    id: 'perm-1',
    agent_id: 'agent-1',
    tool_name: 'list_files',
    workspace_path: '/workspace',
    permission_level: 'ask',
    approval_required: true,
    status: 'active',
    created_at: baseTimestamp,
    updated_at: baseTimestamp,
    ...overrides,
  };
}

function makeToolCatalogEntry(overrides: Record<string, unknown> = {}) {
  return {
    id: 'list_files',
    label: 'List files',
    description: 'List files and directories inside the configured workspace.',
    group: 'group:fs',
    group_label: 'Filesystem',
    risk: 'low',
    status: 'enabled',
    input_schema: {
      type: 'object',
      properties: {
        path: { type: 'string' },
      },
    },
    output_schema: {
      type: 'object',
      properties: {
        count: { type: 'integer' },
      },
    },
    requires_workspace: true,
    ...overrides,
  };
}

function makeToolPolicy(overrides: Record<string, unknown> = {}) {
  return {
    profile_id: 'minimal',
    profiles: [
      {
        id: 'minimal',
        label: 'Minimal',
        description: 'Deny web access and require approval elsewhere.',
        defaults: {
          'group:fs': 'ask',
          'group:runtime': 'ask',
          'group:web': 'deny',
          'group:sessions': 'ask',
          'group:memory': 'ask',
          'group:automation': 'ask',
        },
      },
      {
        id: 'research',
        label: 'Research',
        description: 'Allow web and memory tools by default.',
        defaults: {
          'group:fs': 'ask',
          'group:runtime': 'ask',
          'group:web': 'allow',
          'group:sessions': 'ask',
          'group:memory': 'allow',
          'group:automation': 'ask',
        },
      },
    ],
    overrides: [],
    ...overrides,
  };
}

function makeSkill(overrides: Record<string, unknown> = {}) {
  return {
    key: 'list-files-coach',
    name: 'List Files Coach',
    description: 'Guide filesystem listing.',
    origin: 'workspace',
    enabled: true,
    eligible: true,
    selected: true,
    blocked_reasons: [],
    config: null,
    configured_env_keys: [],
    primary_env: null,
    ...overrides,
  };
}

function makeSkillSummary(overrides: Record<string, unknown> = {}) {
  return {
    key: 'list-files-coach',
    name: 'List Files Coach',
    origin: 'workspace',
    source_path: '/workspace/skills/list-files-coach/SKILL.md',
    selected: true,
    eligible: true,
    blocked_reasons: [],
    ...overrides,
  };
}

function makeCronJob(overrides: Record<string, unknown> = {}) {
  return {
    id: 'job-1',
    agent_id: 'agent-1',
    name: 'Morning Digest',
    schedule: 'every:60s',
    timezone: 'UTC',
    status: 'active',
    task_payload_json:
      '{"job_type":"summarize_recent_activity","message":"Daily summary","stale_after_seconds":null}',
    last_run_at: null,
    next_run_at: '2026-03-08T12:01:00Z',
    created_at: baseTimestamp,
    updated_at: baseTimestamp,
    payload: {
      job_type: 'summarize_recent_activity',
      message: 'Daily summary',
      stale_after_seconds: null,
    },
    ...overrides,
  };
}

function makeApproval(overrides: Record<string, unknown> = {}) {
  return {
    id: 'approval-1',
    agent_id: 'agent-1',
    task_id: 'task-1',
    tool_call_id: 'call-1',
    kind: 'tool_permission',
    requested_action: 'write_file({"path":"todo.txt","content":"secret plan"})',
    reason: 'Tool permission is configured as ask.',
    status: 'pending',
    decided_at: null,
    expires_at: null,
    created_at: '2026-03-08T12:02:00Z',
    updated_at: '2026-03-08T12:02:00Z',
    tool_name: 'write_file',
    tool_input_json: '{"path":"todo.txt","content":"secret plan"}',
    session_id: 'session-approval',
    session_title: 'Approval Session',
    task_run_id: 'run-1',
    ...overrides,
  };
}

vi.mock('@/components/ui/select', () => ({
  Select: ({ value, onValueChange, children, disabled }: any) => {
    return (
      <select
        value={value}
        onChange={(e) => onValueChange(e.target.value)}
        disabled={disabled}
        data-testid="mock-select"
        aria-label="mock select"
      >
        {children}
      </select>
    );
  },
  SelectTrigger: ({ id, 'aria-label': ariaLabel, children }: any) => null,
  SelectContent: ({ children }: any) => <>{children}</>,
  SelectItem: ({ value, children }: any) => <option value={value}>{children}</option>,
  SelectValue: () => null,
}));

vi.mock('./lib/backend', () => ({
  fetchSessions: () => mockFetchSessions(),
  createSession: (title?: string) => mockCreateSession(title),
  fetchSessionMessages: (sessionId: string) => mockFetchSessionMessages(sessionId),
  sendSessionMessage: (sessionId: string, content: string) =>
    mockSendSessionMessage(sessionId, content),
  fetchAgentConfig: () => mockFetchAgentConfig(),
  updateAgentConfig: (payload: unknown) => mockUpdateAgentConfig(payload),
  resetAgentConfig: () => mockResetAgentConfig(),
  fetchOperationalSettings: () => mockFetchOperationalSettings(),
  updateOperationalSettings: (payload: unknown) => mockUpdateOperationalSettings(payload),
  fetchToolCatalog: () => mockFetchToolCatalog(),
  fetchToolPolicy: () => mockFetchToolPolicy(),
  updateToolPolicy: (profileId: string) => mockUpdateToolPolicy(profileId),
  fetchToolPermissions: () => mockFetchToolPermissions(),
  fetchToolCalls: () => mockFetchToolCalls(),
  updateToolPermission: (toolName: string, level: string) =>
    mockUpdateToolPermission(toolName, level),
  fetchSkills: () => mockFetchSkills(),
  updateSkill: (skillKey: string, payload: unknown) => mockUpdateSkill(skillKey, payload),
  fetchApprovals: () => mockFetchApprovals(),
  approveApproval: (approvalId: string) => mockApproveApproval(approvalId),
  denyApproval: (approvalId: string) => mockDenyApproval(approvalId),
  fetchActivityTimeline: () => mockFetchActivityTimeline(),
  fetchCronJobsDashboard: () => mockFetchCronJobsDashboard(),
  createCronJob: (payload: unknown) => mockCreateCronJob(payload),
  pauseCronJob: (jobId: string) => mockPauseCronJob(jobId),
  activateCronJob: (jobId: string) => mockActivateCronJob(jobId),
  deleteCronJob: (jobId: string) => mockDeleteCronJob(jobId),
  getOperationalProviderLabel: (provider: string) =>
    providerLabelMap[provider] || provider,
  getOperationalProviderSuggestedModel: (provider: string) =>
    provider === 'kimi-coding'
      ? 'k2p5'
      : provider === 'product_echo'
        ? 'product-echo/simple'
        : null,
}));

const agentConfig = {
  id: 'agent-1',
  slug: 'main',
  name: 'Primary Agent',
  description: 'Default single-agent instance.',
  status: 'active',
  is_default: true,
  created_at: baseTimestamp,
  updated_at: baseTimestamp,
  profile: {
    id: 'profile-1',
    display_name: 'Nanobot',
    persona: 'Operate with precision, finish work end-to-end, and prefer evidence over guesses',
    system_prompt:
      'Operate with precision, finish work end-to-end, and prefer evidence over guesses.',
    identity_text:
      'You are the primary agent for this desktop product. Help directly, complete work end-to-end, and use tools when they materially help.',
    soul_text:
      'Operate with precision, finish work end-to-end, and prefer evidence over guesses.',
    user_context_text: '',
    policy_base_text:
      'Respect explicit approvals for sensitive actions. Prefer auditable product state and do not treat markdown as canonical state.',
    model_provider: 'product_echo',
    model_name: 'product-echo/simple',
    status: 'active',
    created_at: baseTimestamp,
    updated_at: baseTimestamp,
  },
};

function renderApp() {
  return render(
    <TooltipProvider delayDuration={0}>
      <App />
    </TooltipProvider>,
  );
}

describe('App', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.matchMedia = defaultMatchMedia;
    mockFetchAgentConfig.mockResolvedValue(agentConfig);
    mockFetchToolCatalog.mockResolvedValue({
      items: [makeToolCatalogEntry()],
    });
    mockFetchToolPolicy.mockResolvedValue(makeToolPolicy());
    mockFetchToolPermissions.mockResolvedValue({
      workspace_root: '/workspace',
      items: [makeToolPermission()],
    });
    mockFetchToolCalls.mockResolvedValue({ items: [] });
    mockFetchSkills.mockResolvedValue({
      strategy: 'all_eligible',
      items: [makeSkill()],
    });
    mockFetchApprovals.mockResolvedValue({ items: [] });
    mockFetchOperationalSettings.mockResolvedValue({
      provider: 'product_echo',
      model_name: 'product-echo/simple',
      workspace_root: '/workspace',
      max_iterations_per_execution: 2,
      daily_budget_usd: 10,
      monthly_budget_usd: 200,
      default_view: 'chat',
      activity_poll_seconds: 3,
      heartbeat_interval_seconds: 1800,
      provider_api_key_configured: false,
    });
    mockFetchActivityTimeline.mockResolvedValue({ items: [] });
    mockFetchCronJobsDashboard.mockResolvedValue({
      items: [],
      history: [],
      heartbeat: defaultHeartbeat,
    });
  });

  afterEach(() => {
    window.matchMedia = defaultMatchMedia;
  });

  it('loads a persisted session and sends a new message through the backend', async () => {
    const session = makeSession({
      last_message_at: '2026-03-08T12:01:00Z',
      updated_at: '2026-03-08T12:01:00Z',
    });

    mockFetchSessions
      .mockResolvedValueOnce({ items: [session] })
      .mockResolvedValueOnce({ items: [session] });
    mockFetchSessionMessages
      .mockResolvedValueOnce({ session, items: [] })
      .mockResolvedValueOnce({
        session,
        items: [
          makeMessage({
            session_id: session.id,
            created_at: '2026-03-08T12:02:00Z',
            updated_at: '2026-03-08T12:02:00Z',
          }),
          makeMessage({
            id: 'message-2',
            session_id: session.id,
            role: 'assistant',
            sequence_number: 2,
            content_text: 'Reply: hello kernel',
            created_at: '2026-03-08T12:02:01Z',
            updated_at: '2026-03-08T12:02:01Z',
          }),
        ],
      });
    mockSendSessionMessage.mockResolvedValueOnce({
      status: 'completed',
    });

    renderApp();

    await waitFor(() =>
      expect(screen.getByRole('heading', { name: 'Persistent Chat' })).toBeInTheDocument(),
    );

    fireEvent.change(screen.getByLabelText(/message/i), {
      target: { value: 'hello kernel' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    await waitFor(() =>
      expect(mockSendSessionMessage).toHaveBeenCalledWith('session-1', 'hello kernel'),
    );

    await waitFor(() =>
      expect(screen.getByText('Reply: hello kernel')).toBeInTheDocument(),
    );
  });

  it('creates a new session from the empty state', async () => {
    const createdSession = makeSession({
      id: 'session-new',
      title: 'New Session',
      started_at: '2026-03-08T12:05:00Z',
      created_at: '2026-03-08T12:05:00Z',
      updated_at: '2026-03-08T12:05:00Z',
    });

    mockFetchSessions.mockResolvedValueOnce({ items: [] });
    mockCreateSession.mockResolvedValueOnce(createdSession);

    renderApp();

    await waitFor(() =>
      expect(screen.getByText(/no persistent sessions yet/i)).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole('button', { name: /new session/i }));

    await waitFor(() =>
      expect(mockCreateSession).toHaveBeenCalledWith('New Session'),
    );

    expect(screen.getByRole('heading', { name: 'New Session' })).toBeInTheDocument();
  });

  it('uses a valid desktop shell width contract for the sidebar rail', () => {
    expect(DESKTOP_SIDEBAR_PANEL_SIZE + DESKTOP_MAIN_PANEL_SIZE).toBe(100);
    expect(DESKTOP_SIDEBAR_MIN_SIZE).toBeLessThan(DESKTOP_SIDEBAR_PANEL_SIZE);
    expect(DESKTOP_SIDEBAR_MAX_SIZE).toBeGreaterThan(DESKTOP_SIDEBAR_PANEL_SIZE);
  });

  it('renders a stable desktop sidebar with explicit active navigation and session states', async () => {
    const session = makeSession({
      last_message_at: '2026-03-08T12:01:00Z',
      updated_at: '2026-03-08T12:01:00Z',
    });

    mockFetchSessions.mockResolvedValueOnce({ items: [session] });
    mockFetchSessionMessages.mockResolvedValueOnce({ session, items: [] });

    renderApp();

    await waitFor(() =>
      expect(screen.getByTestId('app-sidebar')).toBeInTheDocument(),
    );

    expect(screen.getByTestId('desktop-shell')).toBeInTheDocument();
    expect(screen.getByTestId('app-sidebar')).not.toHaveClass('min-w-[21.5rem]');
    expect(screen.getByTestId('app-sidebar-nav-chat')).toHaveAttribute(
      'data-active',
      'false',
    );
    expect(screen.getByTestId('session-item-session-1')).toHaveAttribute(
      'data-active',
      'true',
    );
  });

  it('keeps the same sheet navigation trigger on narrow layouts', async () => {
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: () => { },
      removeEventListener: () => { },
      addListener: () => { },
      removeListener: () => { },
      dispatchEvent: () => false,
    }));

    mockFetchSessions.mockResolvedValueOnce({ items: [] });

    renderApp();

    fireEvent.click(screen.getByRole('button', { name: /open navigation/i }));

    await waitFor(() =>
      expect(screen.getByTestId('app-sidebar-sheet')).toBeInTheDocument(),
    );

    expect(screen.getByTestId('app-sidebar-sheet')).toHaveClass('w-[min(88vw,260px)]');
    expect(screen.getByTestId('app-sidebar-sheet')).not.toHaveClass('w-[260px]');
  });

  it('keeps the app shell height fully viewport-bound', async () => {
    mockFetchSessions.mockResolvedValueOnce({ items: [] });

    renderApp();

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Profile' })).toBeInTheDocument(),
    );

    const shellFrame = screen.getByRole('main');

    expect(shellFrame).toHaveClass('overflow-auto');
    expect(shellFrame).not.toHaveClass('min-h-[48rem]');
  });

  it('sorts and groups sessions in the sidebar by most recent activity', async () => {
    const recentSession = makeSession({
      id: 'session-recent',
      title: 'Recent Follow-up',
      started_at: '2026-03-07T08:00:00Z',
      last_message_at: '2026-03-09T09:15:00Z',
      created_at: '2026-03-07T08:00:00Z',
      updated_at: '2026-03-09T09:15:00Z',
    });
    const staleSession = makeSession({
      id: 'session-stale',
      title: 'Older Thread',
      started_at: '2026-03-08T10:00:00Z',
      created_at: '2026-03-08T10:00:00Z',
      updated_at: '2026-03-08T10:00:00Z',
    });

    mockFetchSessions.mockResolvedValueOnce({ items: [staleSession, recentSession] });
    mockFetchSessionMessages.mockResolvedValueOnce({ session: recentSession, items: [] });

    renderApp();

    await waitFor(() =>
      expect(screen.getByTestId('session-item-session-recent')).toBeInTheDocument(),
    );

    const sessionItems = screen.getAllByTestId(/session-item-/);

    expect(sessionItems[0]).toHaveAttribute('data-testid', 'session-item-session-recent');
    expect(sessionItems[1]).toHaveAttribute('data-testid', 'session-item-session-stale');
  });

  it('shows a useful error banner when the local backend is unavailable', async () => {
    mockFetchSessions.mockRejectedValue(
      new Error('Could not reach the local backend at http://127.0.0.1:8000. Connection refused'),
    );

    renderApp();

    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent(
        /could not reach the local backend/i,
      ),
    );
  });

  it('updates and resets the agent profile from the settings panel', async () => {
    mockFetchSessions.mockResolvedValueOnce({ items: [] });
    mockUpdateAgentConfig.mockResolvedValueOnce({
      ...agentConfig,
      name: 'Desk Operator',
      profile: {
        ...agentConfig.profile,
        identity_text: 'Act as a meticulous operator.',
        soul_text: 'Respond with exact calm.',
        user_context_text: 'The user prefers operational summaries.',
        policy_base_text: 'Always require explicit approval.',
        model_name: 'product-echo/tuned',
      },
    });
    mockResetAgentConfig.mockResolvedValueOnce(agentConfig);

    renderApp();

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Profile' })).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole('button', { name: 'Profile' }));

    await waitFor(() =>
      expect(screen.getByDisplayValue('Primary Agent')).toBeInTheDocument(),
    );

    fireEvent.change(screen.getByLabelText(/agent name/i), {
      target: { value: 'Desk Operator' },
    });
    fireEvent.change(screen.getByLabelText(/default model/i), {
      target: { value: 'product-echo/tuned' },
    });
    fireEvent.click(screen.getByRole('tab', { name: 'Behavior' }));
    await waitFor(() =>
      expect(screen.getByRole('tab', { name: 'Behavior' })).toHaveAttribute(
        'data-state',
        'active',
      ),
    );
    fireEvent.change(
      screen.getAllByLabelText(/identity/i, { selector: 'textarea' })[0],
      {
        target: { value: 'Act as a meticulous operator.' },
      },
    );
    fireEvent.change(screen.getByLabelText(/^soul$/i), {
      target: { value: 'Respond with exact calm.' },
    });
    fireEvent.click(screen.getByRole('tab', { name: 'Policy' }));
    fireEvent.change(screen.getByLabelText(/policy base/i), {
      target: { value: 'Always require explicit approval.' },
    });

    fireEvent.click(screen.getByRole('button', { name: /save profile/i }));

    await waitFor(() =>
      expect(mockUpdateAgentConfig).toHaveBeenCalledWith({
        name: 'Desk Operator',
        description: 'Default single-agent instance.',
        identity_text: 'Act as a meticulous operator.',
        soul_text: 'Respond with exact calm.',
        user_context_text: '',
        policy_base_text: 'Always require explicit approval.',
        model_name: 'product-echo/tuned',
      }),
    );

    fireEvent.click(screen.getByRole('button', { name: /restore defaults/i }));

    await waitFor(() => expect(mockResetAgentConfig).toHaveBeenCalled());
    fireEvent.click(screen.getByRole('tab', { name: 'Identity' }));
    expect(screen.getByDisplayValue('Primary Agent')).toBeInTheDocument();
  });

  it('updates a tool permission from the tools panel', async () => {
    mockFetchSessions.mockResolvedValueOnce({ items: [] });
    mockUpdateToolPermission.mockResolvedValueOnce({
      ...makeToolPermission(),
      permission_level: 'allow',
      approval_required: false,
      updated_at: '2026-03-08T12:10:00Z',
    });
    mockFetchToolPolicy
      .mockResolvedValueOnce(makeToolPolicy())
      .mockResolvedValueOnce(makeToolPolicy());
    mockFetchToolPermissions
      .mockResolvedValueOnce({
        workspace_root: '/workspace',
        items: [makeToolPermission()],
      })
      .mockResolvedValueOnce({
        workspace_root: '/workspace',
        items: [
          makeToolPermission({
            permission_level: 'allow',
            approval_required: false,
            updated_at: '2026-03-08T12:10:00Z',
          }),
        ],
      });
    mockFetchSkills
      .mockResolvedValueOnce({
        strategy: 'all_eligible',
        items: [makeSkill()],
      })
      .mockResolvedValueOnce({
        strategy: 'all_eligible',
        items: [
          makeSkill({
            eligible: false,
            selected: false,
            blocked_reasons: ['missing_tools'],
          }),
        ],
      });

    renderApp();

    await waitFor(() =>
      expect(screen.getByTestId('app-sidebar-nav-tools')).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByTestId('app-sidebar-nav-tools'));

    await waitFor(() => {
      expect(screen.getByText('Ask')).toBeInTheDocument();
    });

    expect(screen.getByText('Filesystem')).toBeInTheDocument();

    const selects = screen.getAllByTestId('mock-select');
    // The second select is the tool mode, the first is the tool profile
    fireEvent.change(selects[1], {
      target: { value: 'allow' },
    });

    await waitFor(() =>
      expect(mockUpdateToolPermission).toHaveBeenCalledWith('list_files', 'allow'),
    );

    await waitFor(() =>
      expect(mockFetchSkills).toHaveBeenCalledTimes(2),
    );

    fireEvent.click(screen.getByRole('tab', { name: 'Skills' }));

    await waitFor(() =>
      expect(screen.getAllByText('missing_tools').length).toBeGreaterThan(0),
    );

    expect(screen.getByText(/Root:/i)).toBeInTheDocument();
  });

  it('updates the active tool policy profile from the tools panel', async () => {
    mockFetchSessions.mockResolvedValueOnce({ items: [] });
    mockUpdateToolPolicy.mockResolvedValueOnce(
      makeToolPolicy({ profile_id: 'research' }),
    );
    mockFetchToolPolicy
      .mockResolvedValueOnce(makeToolPolicy())
      .mockResolvedValueOnce(makeToolPolicy({ profile_id: 'research' }));
    mockFetchToolPermissions
      .mockResolvedValueOnce({
        workspace_root: '/workspace',
        items: [makeToolPermission()],
      })
      .mockResolvedValueOnce({
        workspace_root: '/workspace',
        items: [makeToolPermission({ permission_level: 'allow', approval_required: false })],
      });
    mockFetchSkills
      .mockResolvedValueOnce({
        strategy: 'all_eligible',
        items: [makeSkill()],
      })
      .mockResolvedValueOnce({
        strategy: 'all_eligible',
        items: [
          makeSkill({
            eligible: false,
            selected: false,
            blocked_reasons: ['missing_tools'],
          }),
        ],
      });

    renderApp();

    await waitFor(() =>
      expect(screen.getByTestId('app-sidebar-nav-tools')).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByTestId('app-sidebar-nav-tools'));

    await waitFor(() =>
      expect(screen.getAllByTestId('mock-select')[0]).toBeInTheDocument(),
    );

    fireEvent.change(screen.getAllByTestId('mock-select')[0], {
      target: { value: 'research' },
    });

    await waitFor(() =>
      expect(mockUpdateToolPolicy).toHaveBeenCalledWith('research'),
    );

    await waitFor(() =>
      expect(mockFetchSkills).toHaveBeenCalledTimes(2),
    );

    fireEvent.click(screen.getByRole('tab', { name: 'Skills' }));

    await waitFor(() =>
      expect(screen.getAllByText('missing_tools').length).toBeGreaterThan(0),
    );
  });

  it('shows the skills tab and toggles a skill enablement', async () => {
    mockFetchSessions.mockResolvedValueOnce({ items: [] });
    mockFetchSkills.mockResolvedValueOnce({
      strategy: 'all_eligible',
      items: [
        makeSkill({
          key: 'special-helper',
          name: 'Special Helper',
          origin: 'user-local',
          enabled: false,
          eligible: false,
          selected: false,
          blocked_reasons: ['disabled'],
        }),
      ],
    });
    mockUpdateSkill.mockResolvedValueOnce(
      makeSkill({
        key: 'special-helper',
        name: 'Special Helper',
        origin: 'user-local',
        enabled: true,
        eligible: true,
        selected: true,
        blocked_reasons: [],
      }),
    );

    renderApp();

    await waitFor(() =>
      expect(screen.getByTestId('app-sidebar-nav-tools')).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByTestId('app-sidebar-nav-tools'));

    await waitFor(() =>
      expect(screen.getByRole('tab', { name: 'Skills' })).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole('tab', { name: 'Skills' }));

    await waitFor(() =>
      expect(screen.getByText('Special Helper')).toBeInTheDocument(),
    );

    expect(screen.getByText('user-local')).toBeInTheDocument();
    expect(screen.getByText('disabled')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('checkbox', { name: /enable special helper/i }));

    await waitFor(() =>
      expect(mockUpdateSkill).toHaveBeenCalledWith('special-helper', {
        enabled: true,
      }),
    );
  });

  it('updates operational settings and keeps secrets out of the UI response', async () => {
    mockFetchSessions.mockResolvedValueOnce({ items: [] });
    mockUpdateOperationalSettings.mockResolvedValueOnce({
      provider: 'openai',
      model_name: 'gpt-4o-mini',
      workspace_root: '/secure-workspace',
      max_iterations_per_execution: 1,
      daily_budget_usd: 0.5,
      monthly_budget_usd: 10,
      default_view: 'activity',
      activity_poll_seconds: 5,
      heartbeat_interval_seconds: 1800,
      provider_api_key_configured: true,
    });

    renderApp();

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Settings' })).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole('button', { name: 'Settings' }));

    await waitFor(() =>
      expect(
        screen.getByLabelText(/^provider$/i, { selector: 'select' }),
      ).toBeInTheDocument(),
    );

    fireEvent.change(screen.getByLabelText(/^provider$/i, { selector: 'select' }), {
      target: { value: 'openai' },
    });
    fireEvent.change(screen.getByLabelText(/default model/i), {
      target: { value: 'gpt-4o-mini' },
    });
    fireEvent.change(screen.getByLabelText(/provider api key/i), {
      target: { value: 'sk-secret' },
    });
    fireEvent.click(screen.getByRole('tab', { name: 'Workspace' }));
    await waitFor(() =>
      expect(screen.getByRole('tab', { name: 'Workspace' })).toHaveAttribute(
        'data-state',
        'active',
      ),
    );
    fireEvent.change(screen.getAllByLabelText(/workspace root/i)[0], {
      target: { value: '/secure-workspace' },
    });
    fireEvent.change(screen.getByLabelText(/max iterations per execution/i), {
      target: { value: '1' },
    });
    fireEvent.change(screen.getByLabelText(/heartbeat interval/i), {
      target: { value: '1800' },
    });
    fireEvent.click(screen.getByRole('tab', { name: 'Budgets' }));
    fireEvent.change(screen.getByLabelText(/daily budget/i), {
      target: { value: '0.5' },
    });
    fireEvent.change(screen.getByLabelText(/monthly budget/i), {
      target: { value: '10' },
    });
    fireEvent.click(screen.getByRole('tab', { name: 'Preferences' }));
    fireEvent.change(screen.getByLabelText(/default app view/i), {
      target: { value: 'activity' },
    });
    fireEvent.click(screen.getByRole('button', { name: /save settings/i }));

    await waitFor(() =>
      expect(mockUpdateOperationalSettings).toHaveBeenCalledWith({
        provider: 'openai',
        model_name: 'gpt-4o-mini',
        workspace_root: '/secure-workspace',
        max_iterations_per_execution: 1,
        daily_budget_usd: 0.5,
        monthly_budget_usd: 10,
        default_view: 'activity',
        activity_poll_seconds: 3,
        heartbeat_interval_seconds: 1800,
        api_key: 'sk-secret',
        clear_api_key: false,
      }),
    );

    expect(screen.getByText(/Key configured/i)).toBeInTheDocument();
  });

  it('exposes Kimi for Coding in settings and preserves the rest of the draft', async () => {
    mockFetchSessions.mockResolvedValueOnce({ items: [] });
    mockUpdateOperationalSettings.mockResolvedValueOnce({
      provider: 'kimi-coding',
      model_name: 'k2p5',
      workspace_root: '/kimi-workspace',
      max_iterations_per_execution: 2,
      daily_budget_usd: 10,
      monthly_budget_usd: 200,
      default_view: 'chat',
      activity_poll_seconds: 3,
      heartbeat_interval_seconds: 1800,
      provider_api_key_configured: false,
    });

    renderApp();

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Settings' })).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole('button', { name: 'Settings' }));

    await waitFor(() =>
      expect(
        screen.getByLabelText(/^provider$/i, { selector: 'select' }),
      ).toBeInTheDocument(),
    );

    expect(
      screen.getByRole('option', { name: 'Kimi for Coding' }),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: 'Workspace' }));
    fireEvent.change(screen.getAllByLabelText(/workspace root/i)[0], {
      target: { value: '/kimi-workspace' },
    });
    fireEvent.click(screen.getByRole('tab', { name: 'Provider' }));
    fireEvent.change(screen.getByLabelText(/^provider$/i, { selector: 'select' }), {
      target: { value: 'kimi-coding' },
    });

    const modelInput = screen.getByLabelText(/default model/i);
    expect(modelInput).toHaveAttribute('placeholder', 'k2p5');
    fireEvent.change(modelInput, {
      target: { value: 'k2p5' },
    });
    fireEvent.click(screen.getByRole('button', { name: /save settings/i }));

    await waitFor(() =>
      expect(mockUpdateOperationalSettings).toHaveBeenCalledWith({
        provider: 'kimi-coding',
        model_name: 'k2p5',
        workspace_root: '/kimi-workspace',
        max_iterations_per_execution: 2,
        daily_budget_usd: 10,
        monthly_budget_usd: 200,
        default_view: 'chat',
        activity_poll_seconds: 3,
        heartbeat_interval_seconds: 1800,
        api_key: null,
        clear_api_key: false,
      }),
    );

    expect(screen.getAllByText('Kimi for Coding').length).toBeGreaterThan(0);
  });

  it('approves a pending tool request from the approvals inbox', async () => {
    const session = makeSession({
      id: 'session-approval',
      title: 'Approval Session',
      last_message_at: '2026-03-08T12:01:00Z',
      updated_at: '2026-03-08T12:01:00Z',
    });

    const approval = makeApproval({
      session_id: session.id,
      session_title: session.title,
    });

    mockFetchSessions.mockResolvedValue({ items: [session] });
    mockFetchSessionMessages.mockResolvedValue({
      session,
      items: [
        makeMessage({
          session_id: session.id,
          content_text: 'tool:write_file path=todo.txt content="secret plan"',
          created_at: '2026-03-08T12:02:00Z',
          updated_at: '2026-03-08T12:02:00Z',
        }),
        makeMessage({
          id: 'message-2',
          session_id: session.id,
          role: 'assistant',
          sequence_number: 2,
          content_text: 'Tool `write_file` requires approval and was not executed.',
          created_at: '2026-03-08T12:02:01Z',
          updated_at: '2026-03-08T12:02:01Z',
        }),
      ],
    });
    mockFetchApprovals.mockResolvedValue({ items: [approval] });
    mockApproveApproval.mockResolvedValue({
      approval: { ...approval, status: 'approved' },
      task_run_status: 'completed',
      tool_call_status: 'completed',
      output_text: 'Tool result from write_file:\nWrote todo.txt',
      assistant_message_id: 'message-3',
    });

    renderApp();

    await waitFor(() =>
      expect(screen.getByTestId('app-sidebar-nav-approvals')).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByTestId('app-sidebar-nav-approvals'));

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Approve Action' })).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole('button', { name: 'Approve Action' }));

    await waitFor(() =>
      expect(mockApproveApproval).toHaveBeenCalledWith('approval-1'),
    );
  });

  it('creates a scheduled job from the jobs panel', async () => {
    mockFetchSessions.mockResolvedValueOnce({ items: [] });
    mockCreateCronJob.mockResolvedValue({
      ...makeCronJob(),
    });
    mockFetchCronJobsDashboard
      .mockResolvedValueOnce({
        items: [],
        history: [],
        heartbeat: defaultHeartbeat,
      })
      .mockResolvedValueOnce({
        items: [makeCronJob()],
        history: [],
        heartbeat: {
          last_run_at: '2026-03-08T12:00:30Z',
          task_run_id: 'heartbeat-1',
          cleaned_stale_runs: 0,
          pending_approvals: 0,
          recent_task_runs: 1,
          summary_text: 'Heartbeat reviewed 1 recent task runs.',
        },
      });

    renderApp();

    await waitFor(() =>
      expect(screen.getByTestId('app-sidebar-nav-jobs')).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByTestId('app-sidebar-nav-jobs'));

    await waitFor(() => {
      expect(screen.getByRole('tab', { name: 'Create' })).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('tab', { name: 'Create' }));

    await waitFor(() => {
      expect(screen.getByLabelText(/job name/i)).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText(/job name/i), {
      target: { value: 'Morning Digest' },
    });
    fireEvent.change(screen.getByLabelText(/schedule/i), {
      target: { value: 'every:60s' },
    });
    fireEvent.change(screen.getByLabelText(/job note/i), {
      target: { value: 'Daily summary' },
    });
    fireEvent.click(screen.getByRole('button', { name: /create job/i }));

    await waitFor(() =>
      expect(mockCreateCronJob).toHaveBeenCalledWith({
        name: 'Morning Digest',
        schedule: 'every:60s',
        payload: {
          job_type: 'summarize_recent_activity',
          message: 'Daily summary',
          stale_after_seconds: null,
        },
      }),
    );
  });

  it('renders activity timeline entries from the aggregated endpoint', async () => {
    mockFetchSessions.mockResolvedValueOnce({ items: [] });
    mockFetchToolCalls.mockResolvedValue({
      items: [
        {
          id: 'call-1',
          session_id: 'session-1',
          message_id: 'message-1',
          task_run_id: 'run-1',
          tool_name: 'list_files',
          status: 'completed',
          input_json: '{"path":"."}',
          output_json: '{"text":"file: notes.txt"}',
          started_at: '2026-03-08T12:00:01Z',
          finished_at: '2026-03-08T12:00:01Z',
          created_at: '2026-03-08T12:00:01Z',
          updated_at: '2026-03-08T12:00:01Z',
          guided_by_skills: [makeSkillSummary()],
        },
      ],
    });
    mockFetchActivityTimeline.mockResolvedValue({
      items: [
        {
          task_run_id: 'run-1',
          task_id: 'task-1',
          task_kind: 'agent_execution',
          task_title: 'Agent simple execution',
          session_id: 'session-1',
          session_title: 'Debug Session',
          started_at: '2026-03-08T12:00:00Z',
          finished_at: '2026-03-08T12:00:02Z',
          status: 'completed',
          error_message: null,
          duration_ms: 2000,
          estimated_cost_usd: null,
          skill_strategy: 'all_eligible',
          resolved_skills: [makeSkillSummary()],
          entries: [
            {
              id: 'message:1',
              type: 'message',
              created_at: '2026-03-08T12:00:00Z',
              status: 'committed',
              title: 'User message',
              summary: 'hello timeline',
              error_message: null,
              duration_ms: null,
              estimated_cost_usd: null,
              metadata: null,
            },
            {
              id: 'tool:1',
              type: 'tool_call',
              created_at: '2026-03-08T12:00:01Z',
              status: 'completed',
              title: 'Tool call: list_files',
              summary: 'file: notes.txt',
              error_message: null,
              duration_ms: null,
              estimated_cost_usd: null,
              metadata: null,
            },
            {
              id: 'status:1',
              type: 'status',
              created_at: '2026-03-08T12:00:02Z',
              status: 'completed',
              title: 'Execution status',
              summary: 'Execution completed.',
              error_message: null,
              duration_ms: 2000,
              estimated_cost_usd: null,
              metadata: null,
            },
          ],
          audit_log: [],
        },
      ],
    });

    renderApp();

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Activity' })).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole('button', { name: 'Activity' }));

    await waitFor(() =>
      expect(screen.getByText('hello timeline')).toBeInTheDocument(),
    );
    expect(screen.getByText('Tool call: list_files')).toBeInTheDocument();
    expect(screen.getByText(/Guided by: List Files Coach/i)).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('app-sidebar-nav-tools'));

    await waitFor(() =>
      expect(screen.getByRole('tab', { name: 'Recent calls' })).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole('tab', { name: 'Recent calls' }));

    await waitFor(() =>
      expect(screen.getByText(/List Files Coach/i)).toBeInTheDocument(),
    );
  });
});
