import { useCallback, useState } from 'react';

import {
  fetchSkills,
  fetchToolCalls,
  fetchToolCatalog,
  fetchToolPermissions,
  fetchToolPolicy,
  type SkillRecord,
  type ToolCatalogEntryRecord,
  type ToolCallRecord,
  type ToolPermissionLevel,
  type ToolPermissionRecord,
  type ToolPolicyProfileId,
  type ToolPolicyRecord,
  updateSkill,
  updateToolPermission,
  updateToolPolicy,
} from '../../lib/backend/tools';
import type { RunAsyncAction } from './shared';

type ToolingSnapshot = {
  policyResponse: ToolPolicyRecord;
  permissionsResponse: {
    workspace_root: string;
    items: ToolPermissionRecord[];
  };
  skillsResponse: {
    strategy: string;
    items: SkillRecord[];
  };
};

export function useToolingController({
  runAsyncAction,
}: {
  runAsyncAction: RunAsyncAction;
}) {
  const [workspaceRoot, setWorkspaceRoot] = useState('');
  const [toolCatalog, setToolCatalog] = useState<ToolCatalogEntryRecord[]>([]);
  const [toolPolicy, setToolPolicy] = useState<ToolPolicyRecord | null>(null);
  const [toolPermissions, setToolPermissions] = useState<ToolPermissionRecord[]>([]);
  const [toolCalls, setToolCalls] = useState<ToolCallRecord[]>([]);
  const [skillsStrategy, setSkillsStrategy] = useState('all_eligible');
  const [skills, setSkills] = useState<SkillRecord[]>([]);
  const [isLoadingTools, setIsLoadingTools] = useState(false);
  const [isUpdatingToolPermission, setIsUpdatingToolPermission] =
    useState(false);

  const applyToolingSnapshot = useCallback((response: ToolingSnapshot) => {
    setToolPolicy(response.policyResponse);
    setWorkspaceRoot(response.permissionsResponse.workspace_root);
    setToolPermissions(response.permissionsResponse.items);
    setSkillsStrategy(response.skillsResponse.strategy);
    setSkills(response.skillsResponse.items);
  }, []);

  const loadTools = useCallback(async () => {
    const response = await runAsyncAction(
      async () => {
        const [
          catalogResponse,
          policyResponse,
          permissionsResponse,
          callsResponse,
          skillsResponse,
        ] = await Promise.all([
          fetchToolCatalog(),
          fetchToolPolicy(),
          fetchToolPermissions(),
          fetchToolCalls(),
          fetchSkills(),
        ]);
        return {
          callsResponse,
          catalogResponse,
          permissionsResponse,
          policyResponse,
          skillsResponse,
        };
      },
      {
        setPending: setIsLoadingTools,
        errorMessage: 'Failed to load tool permissions.',
      },
    );
    if (!response) {
      return null;
    }

    setToolCatalog(response.catalogResponse.items);
    setToolCalls(response.callsResponse.items);
    applyToolingSnapshot(response);
    return response;
  }, [applyToolingSnapshot, runAsyncAction]);

  const loadToolingSnapshot = useCallback(async () => {
    const response = await runAsyncAction(
      async () => {
        const [
          catalogResponse,
          policyResponse,
          permissionsResponse,
          skillsResponse,
        ] = await Promise.all([
          fetchToolCatalog(),
          fetchToolPolicy(),
          fetchToolPermissions(),
          fetchSkills(),
        ]);
        return {
          catalogResponse,
          permissionsResponse,
          policyResponse,
          skillsResponse,
        };
      },
      {
        setPending: setIsLoadingTools,
        errorMessage: 'Failed to load tool permissions.',
      },
    );
    if (!response) {
      return null;
    }

    setToolCatalog(response.catalogResponse.items);
    applyToolingSnapshot(response);
    return response;
  }, [applyToolingSnapshot, runAsyncAction]);

  const handleChangeToolPermission = useCallback(
    async (toolName: string, permissionLevel: ToolPermissionLevel) => {
      const updated = await runAsyncAction(
        async () => {
          await updateToolPermission(toolName, permissionLevel);
          const [policyResponse, permissionsResponse, skillsResponse] =
            await Promise.all([
              fetchToolPolicy(),
              fetchToolPermissions(),
              fetchSkills(),
            ]);
          return { permissionsResponse, policyResponse, skillsResponse };
        },
        {
          setPending: setIsUpdatingToolPermission,
          errorMessage: 'Failed to update tool permission.',
        },
      );
      if (!updated) {
        return null;
      }

      applyToolingSnapshot(updated);
      return updated;
    },
    [applyToolingSnapshot, runAsyncAction],
  );

  const handleChangeToolPolicyProfile = useCallback(
    async (profileId: ToolPolicyProfileId) => {
      const updated = await runAsyncAction(
        async () => {
          await updateToolPolicy(profileId);
          const [policyResponse, permissionsResponse, skillsResponse] =
            await Promise.all([
              fetchToolPolicy(),
              fetchToolPermissions(),
              fetchSkills(),
            ]);
          return { permissionsResponse, policyResponse, skillsResponse };
        },
        {
          setPending: setIsUpdatingToolPermission,
          errorMessage: 'Failed to update tool policy profile.',
        },
      );
      if (!updated) {
        return null;
      }

      applyToolingSnapshot(updated);
      return updated;
    },
    [applyToolingSnapshot, runAsyncAction],
  );

  const handleToggleSkill = useCallback(
    async (skillKey: string, enabled: boolean) => {
      const updated = await runAsyncAction(
        () => updateSkill(skillKey, { enabled }),
        {
          setPending: setIsUpdatingToolPermission,
          errorMessage: 'Failed to update skill settings.',
        },
      );
      if (!updated) {
        return null;
      }

      setSkills((current) =>
        current.map((item) => (item.key === updated.key ? updated : item)),
      );
      return updated;
    },
    [runAsyncAction],
  );

  return {
    handleChangeToolPermission,
    handleChangeToolPolicyProfile,
    handleToggleSkill,
    isLoadingTools,
    isUpdatingToolPermission,
    loadTools,
    loadToolingSnapshot,
    skills,
    skillsStrategy,
    toolCalls,
    toolCatalog,
    toolPermissions,
    toolPolicy,
    workspaceRoot,
  };
}
