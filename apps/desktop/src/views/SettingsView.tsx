import type { useAppController } from '../hooks/useAppController';
import { OperationalSettingsPanel } from '../components/OperationalSettingsPanel';

type AppController = ReturnType<typeof useAppController>;

export interface SettingsViewProps {
  settings: AppController['operationalSettings'];
}

export function SettingsView({ settings }: SettingsViewProps) {
  return (
    <OperationalSettingsPanel
      settings={settings.operationalSettings}
      draft={settings.operationalDraft}
      isLoading={settings.isLoadingOperationalSettings}
      isSaving={settings.isSavingOperationalSettings}
      onDraftChange={settings.handleOperationalDraftChange}
      onSave={settings.handleSaveOperationalSettings}
    />
  );
}
