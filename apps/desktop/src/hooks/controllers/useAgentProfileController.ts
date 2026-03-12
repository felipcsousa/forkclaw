import { useCallback, useState } from 'react';

import {
  fetchAgentConfig,
  resetAgentConfig,
  updateAgentConfig,
  type AgentConfigUpdate,
  type AgentRecord,
} from '../../lib/backend/agent';
import type { RunAsyncAction } from './shared';

const emptyAgentDraft: AgentConfigUpdate = {
  name: '',
  description: '',
  identity_text: '',
  soul_text: '',
  user_context_text: '',
  policy_base_text: '',
  model_name: '',
};

function toAgentDraft(agent: AgentRecord): AgentConfigUpdate {
  return {
    name: agent.name,
    description: agent.description || '',
    identity_text: agent.profile?.identity_text || '',
    soul_text: agent.profile?.soul_text || '',
    user_context_text: agent.profile?.user_context_text || '',
    policy_base_text: agent.profile?.policy_base_text || '',
    model_name: agent.profile?.model_name || '',
  };
}

export function useAgentProfileController({
  runAsyncAction,
  setErrorMessage,
}: {
  runAsyncAction: RunAsyncAction;
  setErrorMessage: (value: string | null) => void;
}) {
  const [agent, setAgent] = useState<AgentRecord | null>(null);
  const [agentDraft, setAgentDraft] = useState<AgentConfigUpdate>(emptyAgentDraft);
  const [isLoadingAgent, setIsLoadingAgent] = useState(false);
  const [isSavingAgent, setIsSavingAgent] = useState(false);
  const [isResettingAgent, setIsResettingAgent] = useState(false);

  const loadAgentConfig = useCallback(async () => {
    const response = await runAsyncAction(() => fetchAgentConfig(), {
      setPending: setIsLoadingAgent,
      errorMessage: 'Failed to load agent profile.',
    });
    if (!response) {
      return null;
    }

    setAgent(response);
    setAgentDraft(toAgentDraft(response));
    return response;
  }, [runAsyncAction]);

  const handleAgentDraftChange = useCallback(
    (field: keyof AgentConfigUpdate, value: string) => {
      setAgentDraft((current) => ({ ...current, [field]: value }));
    },
    [],
  );

  const handleSaveAgentConfig = useCallback(async () => {
    if (
      !agentDraft.name.trim() ||
      !agentDraft.identity_text.trim() ||
      !agentDraft.soul_text.trim() ||
      !agentDraft.policy_base_text.trim() ||
      !agentDraft.model_name.trim()
    ) {
      setErrorMessage(
        'Name, identity, soul, policy base, and default model are required.',
      );
      return null;
    }

    const saved = await runAsyncAction(
      () =>
        updateAgentConfig({
          name: agentDraft.name.trim(),
          description: agentDraft.description.trim(),
          identity_text: agentDraft.identity_text.trim(),
          soul_text: agentDraft.soul_text.trim(),
          user_context_text: agentDraft.user_context_text.trim(),
          policy_base_text: agentDraft.policy_base_text.trim(),
          model_name: agentDraft.model_name.trim(),
        }),
      {
        setPending: setIsSavingAgent,
        errorMessage: 'Failed to save agent profile.',
      },
    );
    if (!saved) {
      return null;
    }

    setAgent(saved);
    setAgentDraft(toAgentDraft(saved));
    return saved;
  }, [agentDraft, runAsyncAction, setErrorMessage]);

  const handleResetAgentConfig = useCallback(async () => {
    const reset = await runAsyncAction(() => resetAgentConfig(), {
      setPending: setIsResettingAgent,
      errorMessage: 'Failed to restore agent defaults.',
    });
    if (!reset) {
      return null;
    }

    setAgent(reset);
    setAgentDraft(toAgentDraft(reset));
    return reset;
  }, [runAsyncAction]);

  return {
    agent,
    agentDraft,
    handleAgentDraftChange,
    handleResetAgentConfig,
    handleSaveAgentConfig,
    isLoadingAgent,
    isResettingAgent,
    isSavingAgent,
    loadAgentConfig,
    setAgentDraft,
  };
}
