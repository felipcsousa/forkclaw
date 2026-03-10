import { FormEvent, useId } from 'react';

import { Button } from '@/components/ui/button';
import { Field } from '@/components/ui/form-field';
import { Input } from '@/components/ui/input';
import { Separator } from '@/components/ui/separator';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import type { AgentConfigUpdate, AgentRecord } from '../lib/backend';

interface AgentSettingsPanelProps {
  agent: AgentRecord | null;
  draft: AgentConfigUpdate;
  isLoading: boolean;
  isSaving: boolean;
  isResetting: boolean;
  onDraftChange: (field: keyof AgentConfigUpdate, value: string) => void;
  onSave: () => void;
  onReset: () => void;
}

export function AgentSettingsPanel({
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  agent,
  draft,
  isLoading,
  isSaving,
  isResetting,
  onDraftChange,
  onSave,
  onReset,
}: AgentSettingsPanelProps) {
  const disabled = isLoading || isSaving || isResetting;
  const idBase = useId();

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSave();
  }

  return (
    <div className="space-y-5 animate-fade-in">
      <form className="space-y-6" onSubmit={handleSubmit}>
        <Tabs defaultValue="identity">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <TabsList>
              <TabsTrigger value="identity">Identity</TabsTrigger>
              <TabsTrigger value="behavior">Behavior</TabsTrigger>
              <TabsTrigger value="policy">Policy</TabsTrigger>
            </TabsList>
            <p className="text-sm text-muted-foreground">
              Save here to change the next agent run.
            </p>
          </div>

          <TabsContent value="identity" className="space-y-6">
            <div className="field-grid two">
              <Field label="Agent name" htmlFor={`${idBase}-name`}>
                <Input
                  id={`${idBase}-name`}
                  value={draft.name}
                  onChange={(e) => onDraftChange('name', e.target.value)}
                  disabled={disabled}
                  required
                  maxLength={200}
                />
              </Field>
              <Field label="Default model" htmlFor={`${idBase}-model`}>
                <Input
                  id={`${idBase}-model`}
                  value={draft.model_name}
                  onChange={(e) => onDraftChange('model_name', e.target.value)}
                  disabled={disabled}
                  required
                  maxLength={100}
                />
              </Field>
            </div>
            <Field
              label="Description"
              htmlFor={`${idBase}-description`}
              hint="Short summary used to anchor the role of this agent."
            >
              <Textarea
                id={`${idBase}-description`}
                value={draft.description}
                onChange={(e) => onDraftChange('description', e.target.value)}
                disabled={disabled}
                maxLength={4000}
              />
            </Field>
          </TabsContent>

          <TabsContent value="behavior" className="space-y-6">
            <Field
              label="Identity"
              htmlFor={`${idBase}-identity`}
              hint="Stable guidance for how the agent should present itself."
            >
              <Textarea
                id={`${idBase}-identity`}
                value={draft.identity_text}
                onChange={(e) => onDraftChange('identity_text', e.target.value)}
                disabled={disabled}
                required
                maxLength={8000}
              />
            </Field>
            <Field
              label="Soul"
              htmlFor={`${idBase}-soul`}
              hint="The default tone, judgment, and decision posture."
            >
              <Textarea
                id={`${idBase}-soul`}
                value={draft.soul_text}
                onChange={(e) => onDraftChange('soul_text', e.target.value)}
                disabled={disabled}
                required
                maxLength={8000}
              />
            </Field>
            <Field
              label="User context"
              htmlFor={`${idBase}-user-context`}
              hint="User-specific context that should inform new runs."
            >
              <Textarea
                id={`${idBase}-user-context`}
                value={draft.user_context_text}
                onChange={(e) => onDraftChange('user_context_text', e.target.value)}
                disabled={disabled}
                maxLength={8000}
              />
            </Field>
          </TabsContent>

          <TabsContent value="policy" className="space-y-6">
            <Field
              label="Policy base"
              htmlFor={`${idBase}-policy`}
              hint="Canonical guidance that the runtime reads from SQLite before every execution."
            >
              <Textarea
                id={`${idBase}-policy`}
                value={draft.policy_base_text}
                onChange={(e) => onDraftChange('policy_base_text', e.target.value)}
                disabled={disabled}
                required
                maxLength={8000}
                className="min-h-[220px]"
              />
            </Field>
          </TabsContent>
        </Tabs>

        <Separator />

        <div className="flex flex-wrap items-center justify-between gap-4 rounded-[1rem] bg-muted/16 px-4 py-3">
          <p className="max-w-xl text-sm leading-relaxed text-muted-foreground">
            Restore defaults to return to the seeded baseline profile.
          </p>
          <div className="flex items-center gap-2">
            <Button variant="secondary" type="button" onClick={onReset} disabled={disabled}>
              {isResetting ? 'Restoring...' : 'Restore defaults'}
            </Button>
            <Button type="submit" disabled={disabled}>
              {isSaving ? 'Saving...' : 'Save profile'}
            </Button>
          </div>
        </div>
      </form>
    </div>
  );
}
