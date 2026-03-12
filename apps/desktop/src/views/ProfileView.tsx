import type { useAppController } from '../hooks/useAppController';
import { AgentSettingsPanel } from '../components/AgentSettingsPanel';

type AppController = ReturnType<typeof useAppController>;

export interface ProfileViewProps {
  profile: AppController['agentProfile'];
}

export function ProfileView({ profile }: ProfileViewProps) {
  return (
    <AgentSettingsPanel
      agent={profile.agent}
      draft={profile.agentDraft}
      isLoading={profile.isLoadingAgent}
      isSaving={profile.isSavingAgent}
      isResetting={profile.isResettingAgent}
      onDraftChange={profile.handleAgentDraftChange}
      onSave={profile.handleSaveAgentConfig}
      onReset={profile.handleResetAgentConfig}
    />
  );
}
