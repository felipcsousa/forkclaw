import { FormEvent, useId } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Field, SelectInput } from '@/components/ui/form-field';
import { Input } from '@/components/ui/input';
import { Separator } from '@/components/ui/separator';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import type {
  OperationalDefaultView,
  OperationalProvider,
  OperationalSettingsRecord,
  OperationalSettingsUpdate,
} from '../lib/backend';

interface OperationalSettingsPanelProps {
  settings: OperationalSettingsRecord | null;
  draft: OperationalSettingsUpdate;
  isLoading: boolean;
  isSaving: boolean;
  onDraftChange: <K extends keyof OperationalSettingsUpdate>(
    field: K,
    value: OperationalSettingsUpdate[K],
  ) => void;
  onSave: () => void;
}

const providerOptions: Array<{ value: OperationalProvider; label: string }> = [
  { value: 'product_echo', label: 'Product Echo (local fallback)' },
  { value: 'openai', label: 'OpenAI' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'openrouter', label: 'OpenRouter' },
  { value: 'deepseek', label: 'DeepSeek' },
  { value: 'gemini', label: 'Gemini' },
];

const defaultViewOptions: Array<{ value: OperationalDefaultView; label: string }> = [
  { value: 'chat', label: 'Chat' },
  { value: 'profile', label: 'Profile' },
  { value: 'settings', label: 'Settings' },
  { value: 'tools', label: 'Tools' },
  { value: 'approvals', label: 'Approvals' },
  { value: 'jobs', label: 'Jobs' },
  { value: 'activity', label: 'Activity' },
];

export function OperationalSettingsPanel({
  settings,
  draft,
  isLoading,
  isSaving,
  onDraftChange,
  onSave,
}: OperationalSettingsPanelProps) {
  const disabled = isLoading || isSaving;
  const idBase = useId();

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSave();
  }

  return (
    <div className="space-y-5 animate-fade-in">
      <form className="space-y-6" onSubmit={handleSubmit}>
        <Tabs defaultValue="provider">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <TabsList>
              <TabsTrigger value="provider">Provider</TabsTrigger>
              <TabsTrigger value="workspace">Workspace</TabsTrigger>
              <TabsTrigger value="budgets">Budgets</TabsTrigger>
              <TabsTrigger value="preferences">Preferences</TabsTrigger>
            </TabsList>
            <Badge variant={settings?.provider_api_key_configured ? 'success' : 'outline'}>
              {settings?.provider_api_key_configured ? 'Key configured' : 'No API key'}
            </Badge>
          </div>

          <TabsContent value="provider" className="space-y-6">
            <div className="field-grid two">
              <Field
                label="Provider"
                htmlFor={`${idBase}-provider`}
                hint="Choose the runtime provider and keep secrets in the system keychain."
              >
                <SelectInput
                  id={`${idBase}-provider`}
                  value={draft.provider}
                  onChange={(e) =>
                    onDraftChange('provider', e.target.value as OperationalProvider)
                  }
                  disabled={disabled}
                >
                  {providerOptions.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </SelectInput>
              </Field>
              <Field label="Default model" htmlFor={`${idBase}-model`}>
                <Input
                  id={`${idBase}-model`}
                  value={draft.model_name}
                  onChange={(e) => onDraftChange('model_name', e.target.value)}
                  disabled={disabled}
                  required
                />
              </Field>
            </div>
            <Field
              label="Provider API key"
              htmlFor={`${idBase}-api-key`}
              hint="Leave blank to keep the stored secret."
            >
              <Input
                id={`${idBase}-api-key`}
                type="password"
                value={draft.api_key || ''}
                onChange={(e) => onDraftChange('api_key', e.target.value)}
                disabled={disabled}
                placeholder={
                  settings?.provider_api_key_configured
                    ? 'Stored in keychain. Leave blank to keep it.'
                    : 'Paste a new API key'
                }
              />
            </Field>
            <label className="flex items-center gap-3 rounded-[1.1rem] border border-border/80 bg-background/70 px-4 py-3 text-sm">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-border"
                checked={draft.clear_api_key}
                onChange={(e) => onDraftChange('clear_api_key', e.target.checked)}
                disabled={disabled || draft.provider === 'product_echo'}
              />
              <span className="text-muted-foreground">
                Clear the stored API key for the selected provider
              </span>
            </label>
          </TabsContent>

          <TabsContent value="workspace" className="space-y-6">
            <Field
              label="Workspace root"
              htmlFor={`${idBase}-workspace-root`}
              hint="Control where local tools can run."
            >
              <Input
                id={`${idBase}-workspace-root`}
                value={draft.workspace_root}
                onChange={(e) => onDraftChange('workspace_root', e.target.value)}
                disabled={disabled}
                required
              />
            </Field>
            <div className="field-grid two">
              <Field
                label="Max iterations per execution"
                htmlFor={`${idBase}-iterations`}
                hint="How much work one execution may do before stopping."
              >
                <Input
                  id={`${idBase}-iterations`}
                  type="number"
                  min={1}
                  max={10}
                  value={draft.max_iterations_per_execution}
                  onChange={(e) =>
                    onDraftChange(
                      'max_iterations_per_execution',
                      Number(e.target.value) || 1,
                    )
                  }
                  disabled={disabled}
                  required
                />
              </Field>
              <Field
                label="Activity poll seconds"
                htmlFor={`${idBase}-poll-seconds`}
                hint="How often the local UI refreshes jobs and activity."
              >
                <Input
                  id={`${idBase}-poll-seconds`}
                  type="number"
                  min={1}
                  max={300}
                  value={draft.activity_poll_seconds}
                  onChange={(e) =>
                    onDraftChange(
                      'activity_poll_seconds',
                      Number(e.target.value) || 1,
                    )
                  }
                  disabled={disabled}
                  required
                />
              </Field>
            </div>
          </TabsContent>

          <TabsContent value="budgets" className="space-y-6">
            <div className="field-grid two">
              <Field
                label="Daily budget (USD, approx)"
                htmlFor={`${idBase}-daily-budget`}
                hint="Use approximate daily guardrails for the MVP."
              >
                <Input
                  id={`${idBase}-daily-budget`}
                  type="number"
                  min={0.000001}
                  step={0.000001}
                  value={draft.daily_budget_usd}
                  onChange={(e) =>
                    onDraftChange('daily_budget_usd', Number(e.target.value) || 0.000001)
                  }
                  disabled={disabled}
                  required
                />
              </Field>
              <Field
                label="Monthly budget (USD, approx)"
                htmlFor={`${idBase}-monthly-budget`}
                hint="Approximate monthly guardrails for the MVP."
              >
                <Input
                  id={`${idBase}-monthly-budget`}
                  type="number"
                  min={0.000001}
                  step={0.000001}
                  value={draft.monthly_budget_usd}
                  onChange={(e) =>
                    onDraftChange(
                      'monthly_budget_usd',
                      Number(e.target.value) || 0.000001,
                    )
                  }
                  disabled={disabled}
                  required
                />
              </Field>
            </div>
          </TabsContent>

          <TabsContent value="preferences" className="space-y-6">
            <Field
              label="Default app view"
              htmlFor={`${idBase}-default-view`}
              hint="Pick the most useful starting view for this local console."
            >
              <SelectInput
                id={`${idBase}-default-view`}
                value={draft.default_view}
                onChange={(e) =>
                  onDraftChange('default_view', e.target.value as OperationalDefaultView)
                }
                disabled={disabled}
              >
                {defaultViewOptions.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </SelectInput>
            </Field>
          </TabsContent>
        </Tabs>

        <Separator />

        <div className="flex flex-wrap items-center justify-between gap-4 rounded-[1rem] bg-muted/16 px-4 py-3">
          <p className="max-w-xl text-sm leading-relaxed text-muted-foreground">
            Budget limits are approximate guardrails for the MVP. They help stop new
            runs before costs drift too far.
          </p>
          <Button type="submit" disabled={disabled}>
            {isSaving ? 'Saving...' : 'Save settings'}
          </Button>
        </div>
      </form>
    </div>
  );
}
