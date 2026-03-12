import type { useAppController } from '../hooks/useAppController';
import { ToolPermissionsPanel } from '../components/ToolPermissionsPanel';

type AppController = ReturnType<typeof useAppController>;

export interface ToolsViewProps {
  tooling: AppController['tooling'];
}

export function ToolsView({ tooling }: ToolsViewProps) {
  return (
    <ToolPermissionsPanel
      catalog={tooling.toolCatalog}
      policy={tooling.toolPolicy}
      workspaceRoot={tooling.workspaceRoot}
      permissions={tooling.toolPermissions}
      calls={tooling.toolCalls}
      skills={tooling.skills}
      skillsStrategy={tooling.skillsStrategy}
      isLoading={tooling.isLoadingTools}
      isUpdating={tooling.isUpdatingToolPermission}
      onChangeProfile={tooling.handleChangeToolPolicyProfile}
      onChangePermission={tooling.handleChangeToolPermission}
      onToggleSkill={tooling.handleToggleSkill}
    />
  );
}
