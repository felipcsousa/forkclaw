import { Eye } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Separator } from '@/components/ui/separator';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import type {
  SkillRecord,
  ToolCallRecord,
  ToolCatalogEntryRecord,
  ToolGroup,
  ToolPermissionLevel,
  ToolPermissionRecord,
  ToolPolicyProfileId,
  ToolPolicyRecord,
} from '../lib/backend';

interface ToolPermissionsPanelProps {
  catalog: ToolCatalogEntryRecord[];
  policy: ToolPolicyRecord | null;
  workspaceRoot: string;
  permissions: ToolPermissionRecord[];
  calls: ToolCallRecord[];
  skills: SkillRecord[];
  skillsStrategy: string;
  isLoading: boolean;
  isUpdating: boolean;
  onChangeProfile: (profileId: ToolPolicyProfileId) => void;
  onChangePermission: (toolName: string, permissionLevel: ToolPermissionLevel) => void;
  onToggleSkill: (skillKey: string, enabled: boolean) => void;
}

const toolGroupLabels: Record<ToolGroup, string> = {
  'group:fs': 'Filesystem',
  'group:runtime': 'Runtime',
  'group:web': 'Web',
  'group:sessions': 'Sessions',
  'group:memory': 'Memory',
  'group:automation': 'Automation',
};

function permissionStatusVariant(status: string) {
  if (status === 'completed' || status === 'active' || status === 'running') {
    return 'success' as const;
  }

  if (status === 'denied' || status === 'failed') {
    return 'destructive' as const;
  }

  return 'secondary' as const;
}

function toolStatusVariant(status: string) {
  if (status === 'enabled') {
    return 'success' as const;
  }
  if (status === 'experimental') {
    return 'warning' as const;
  }
  return 'secondary' as const;
}

function riskVariant(risk: string) {
  if (risk === 'high') {
    return 'destructive' as const;
  }
  if (risk === 'medium') {
    return 'warning' as const;
  }
  return 'outline' as const;
}

function eligibilityVariant(skill: SkillRecord) {
  if (skill.selected) {
    return 'success' as const;
  }
  if (!skill.enabled || skill.blocked_reasons.length > 0) {
    return 'warning' as const;
  }
  return 'secondary' as const;
}

function formatSkillState(skill: SkillRecord) {
  if (skill.selected) {
    return 'eligible';
  }
  if (!skill.enabled) {
    return 'disabled';
  }
  if (skill.blocked_reasons.length > 0) {
    return skill.blocked_reasons.join(', ');
  }
  return 'blocked';
}

function formatBlockedReasons(skill: SkillRecord) {
  if (skill.blocked_reasons.length === 0) {
    return 'Ready for prompt injection.';
  }

  return skill.blocked_reasons
    .map((reason) => (reason === 'disabled' ? 'Blocked by setting' : reason))
    .join(', ');
}

function PayloadDialog({
  title,
  description,
  payload,
}: {
  title: string;
  description: string;
  payload: string;
}) {
  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="ghost" size="sm">
          <Eye className="h-4 w-4" />
          View payload
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        <pre className="max-h-[60vh] overflow-auto rounded-[1.2rem] border border-border/80 bg-muted/18 p-4 text-xs leading-6 text-foreground">
          {payload || '{}'}
        </pre>
      </DialogContent>
    </Dialog>
  );
}

export function ToolPermissionsPanel({
  catalog,
  policy,
  workspaceRoot,
  permissions,
  calls,
  skills,
  skillsStrategy,
  isLoading,
  isUpdating,
  onChangeProfile,
  onChangePermission,
  onToggleSkill,
}: ToolPermissionsPanelProps) {
  const catalogMap = new Map(catalog.map((item) => [item.id, item]));
  const overrideMap = new Map(
    (policy?.overrides || []).map((item) => [item.tool_name, item.permission_level]),
  );
  const activeProfile =
    policy?.profiles.find((item) => item.id === policy.profile_id) || null;

  const groupedPermissions = permissions.reduce<
    Array<{
      group: string;
      groupLabel: string;
      items: ToolPermissionRecord[];
    }>
  >((groups, permission) => {
    const descriptor = catalogMap.get(permission.tool_name);
    const group = descriptor?.group || 'group:runtime';
    const groupLabel = descriptor?.group_label || toolGroupLabels[group];
    const existing = groups.find((item) => item.group === group);
    if (existing) {
      existing.items.push(permission);
      return groups;
    }
    groups.push({ group, groupLabel, items: [permission] });
    return groups;
  }, []);

  const sortedSkills = [...skills].sort((left, right) =>
    left.name.localeCompare(right.name),
  );

  return (
    <div className="space-y-5 animate-fade-in">
      <Tabs defaultValue="catalog">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <TabsList>
            <TabsTrigger value="catalog">Catalog</TabsTrigger>
            <TabsTrigger value="skills">Skills</TabsTrigger>
            <TabsTrigger value="calls">Recent calls</TabsTrigger>
          </TabsList>
          <p className="max-w-xs truncate text-xs text-muted-foreground" title={workspaceRoot}>
            Root: {workspaceRoot}
          </p>
        </div>

        <TabsContent value="catalog" className="space-y-4">
          <Separator />
          <div className="grid gap-4 rounded-[1.2rem] border border-border/80 bg-muted/12 p-4 lg:grid-cols-[minmax(0,1fr)_16rem]">
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-sm font-medium text-foreground">Tool policy profile</p>
                <Badge variant="outline">
                  {policy?.overrides.length || 0} override
                  {(policy?.overrides.length || 0) === 1 ? '' : 's'}
                </Badge>
              </div>
              <p className="text-sm text-muted-foreground">
                {activeProfile?.description ||
                  'The backend controls default tool access by profile and per-tool overrides.'}
              </p>
            </div>
            <div className="space-y-2">
              <label
                htmlFor="tool-policy-profile"
                className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground"
              >
                Policy profile
              </label>
              <Select
                value={policy?.profile_id || 'minimal'}
                onValueChange={(value) => onChangeProfile(value as ToolPolicyProfileId)}
                disabled={isUpdating || !policy}
              >
                <SelectTrigger id="tool-policy-profile" className="w-full h-9 shadow-sm rounded-lg">
                  <SelectValue placeholder="Select a profile" />
                </SelectTrigger>
                <SelectContent>
                  {(policy?.profiles || []).map((profile) => (
                    <SelectItem key={profile.id} value={profile.id}>
                      {profile.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {isLoading && permissions.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-border py-12 px-4 bg-muted/10 shadow-sm">
              <div className="h-4 w-32 animate-pulse rounded bg-muted-foreground/20" />
            </div>
          ) : permissions.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-border py-12 px-4 bg-muted/10 shadow-sm">
              <p className="text-[14px] font-semibold tracking-tight text-foreground">No tool policies mapped</p>
              <p className="text-[13px] text-muted-foreground text-center max-w-sm">The agent cannot execute local tools until permissions are seeded.</p>
            </div>
          ) : (
            <div className="space-y-4">
              {groupedPermissions.map((group) => (
                <section
                  key={group.group}
                  className="overflow-hidden rounded-[1.2rem] border border-border/80"
                >
                  <div className="flex items-center justify-between gap-3 border-b border-border/80 bg-muted/16 px-4 py-3">
                    <div>
                      <h3 className="text-sm font-semibold text-foreground">
                        {group.groupLabel} tools
                      </h3>
                      <p className="text-xs text-muted-foreground">
                        {activeProfile?.defaults[group.group as ToolGroup]
                          ? `Default: ${activeProfile.defaults[group.group as ToolGroup]}`
                          : 'No default policy registered for this group.'}
                      </p>
                    </div>
                    <Badge variant="secondary">{group.items.length} tool(s)</Badge>
                  </div>
                  <div className="rounded-b-[1.2rem] overflow-hidden">
                    <Table className="table-fixed w-full">
                      <TableHeader className="bg-muted/30">
                        <TableRow className="hover:bg-transparent">
                          <TableHead className="text-[11px] font-medium capitalize text-muted-foreground h-9 w-[55%]">Tool</TableHead>
                          <TableHead className="text-[11px] font-medium capitalize text-muted-foreground h-9 w-[25%]">Health & Status</TableHead>
                          <TableHead className="text-[11px] font-medium capitalize text-muted-foreground h-9 w-[20%]">Mode</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {group.items.map((permission) => {
                          const descriptor = catalogMap.get(permission.tool_name);
                          return (
                            <TableRow key={permission.id} className="group border-b border-border/60 last:border-0 hover:bg-muted/30 transition-colors duration-200">
                              <TableCell className="py-2">
                                <div className="space-y-0.5">
                                  <p className="font-semibold text-[13px] tracking-tight text-foreground leading-tight">
                                    {descriptor?.label || permission.tool_name}
                                  </p>
                                  <div className="flex items-center gap-1.5 text-[11px] font-medium text-muted-foreground">
                                    <span className="opacity-80">{descriptor?.group_label || 'Runtime'}</span>
                                    <span className="opacity-40">&bull;</span>
                                    <span className="truncate max-w-[28rem]" title={descriptor?.description || 'No catalog description is available for this tool.'}>
                                      {descriptor?.description || 'No catalog description is available for this tool.'}
                                    </span>
                                  </div>
                                </div>
                              </TableCell>
                              <TableCell className="py-2 align-top pt-2.5">
                                <div className="flex flex-wrap items-center gap-1.5">
                                  {(descriptor?.risk === 'high' || descriptor?.risk === 'medium') && (
                                    <Badge variant={riskVariant(descriptor?.risk)} className="px-1.5 py-0 text-[10px] uppercase tracking-wider">
                                      {descriptor?.risk} risk
                                    </Badge>
                                  )}
                                  {descriptor?.status === 'experimental' && (
                                    <Badge variant={toolStatusVariant(descriptor?.status)} className="px-1.5 py-0 text-[10px] uppercase tracking-wider">
                                      {descriptor?.status} tool
                                    </Badge>
                                  )}
                                  {permission.status !== 'active' && (
                                    <Badge variant={permissionStatusVariant(permission.status)} className="px-1.5 py-0 text-[10px] uppercase tracking-wider">
                                      Plugin {permission.status}
                                    </Badge>
                                  )}
                                  {(() => {
                                    const overrideLevel = overrideMap.get(permission.tool_name);
                                    const groupKey = (descriptor?.group || 'group:runtime') as ToolGroup;
                                    const profileDefault = activeProfile?.defaults[groupKey];
                                    const isEffectiveOverride = overrideLevel != null && overrideLevel !== profileDefault;
                                    return isEffectiveOverride ? (
                                      <span className="text-[10px] font-medium text-muted-foreground opacity-80 italic flex items-center gap-1">
                                        policy override
                                      </span>
                                    ) : null;
                                  })()}
                                </div>
                              </TableCell>
                              <TableCell className="py-2">
                                <Select
                                  value={permission.permission_level}
                                  onValueChange={(value) => onChangePermission(permission.tool_name, value as ToolPermissionLevel)}
                                  disabled={isUpdating}
                                >
                                  <SelectTrigger aria-label={`Mode for ${permission.tool_name}`} className="h-7 text-xs rounded-lg shadow-none">
                                    <SelectValue />
                                  </SelectTrigger>
                                  <SelectContent>
                                    <SelectItem value="allow">Allow</SelectItem>
                                    <SelectItem value="ask">Ask</SelectItem>
                                    <SelectItem value="deny">Deny</SelectItem>
                                  </SelectContent>
                                </Select>
                              </TableCell>
                            </TableRow>
                          );
                        })}
                      </TableBody>
                    </Table>
                  </div>
                </section>
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="skills" className="space-y-4">
          <Separator />
          <div className="rounded-[1.2rem] border border-border/80 bg-muted/12 p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-sm font-medium text-foreground">Eligible skills</p>
                <p className="text-sm text-muted-foreground">
                  Selection strategy: <span className="font-medium">{skillsStrategy}</span>
                </p>
              </div>
              <Badge variant="outline">{skills.length} resolved</Badge>
            </div>
          </div>

          {skills.length === 0 ? (
           <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-border py-12 px-4 bg-muted/10 shadow-sm">
              <p className="text-[14px] font-semibold tracking-tight text-foreground">No skills resolved</p>
              <p className="text-[13px] text-muted-foreground text-center max-w-sm">No bundled, workspace, or user-local skills were resolved for this workspace.</p>
            </div>
          ) : (
            <div className="rounded-xl border border-border bg-card overflow-hidden shadow-sm">
              <Table className="table-fixed w-full">
                <TableHeader className="bg-muted/30">
                  <TableRow className="hover:bg-transparent">
                    <TableHead className="text-[11px] font-medium capitalize text-muted-foreground h-9 w-[55%]">Skill</TableHead>
                    <TableHead className="text-[11px] font-medium capitalize text-muted-foreground h-9 w-[25%]">Status</TableHead>
                    <TableHead className="text-[11px] font-medium capitalize text-muted-foreground h-9 w-[20%] text-right">Enable</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {sortedSkills.map((skill) => (
                    <TableRow key={skill.key} className="group border-b border-border/60 last:border-0 hover:bg-muted/30 transition-colors duration-200">
                      <TableCell className="py-2">
                        <div className="space-y-0.5">
                          <p className="font-semibold text-[13px] tracking-tight text-foreground leading-tight">{skill.name}</p>
                          <div className="flex items-center gap-1.5 text-[11px] font-medium text-muted-foreground">
                            <span className="opacity-80">{skill.origin}</span>
                            <span className="opacity-40">&bull;</span>
                            <span className="truncate max-w-[28rem]">{skill.description}</span>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell className="py-2">
                        <div className="flex flex-col gap-1 items-start">
                          <Badge variant={eligibilityVariant(skill)} className="px-1.5 py-0 text-[10px] uppercase tracking-wider">
                            {formatSkillState(skill)}
                          </Badge>
                          {skill.blocked_reasons.length > 0 && (
                            <span className="text-[10px] font-medium text-muted-foreground opacity-80">
                              {formatBlockedReasons(skill)}
                            </span>
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="text-right py-2">
                        <label className="inline-flex items-center justify-end gap-2 cursor-pointer">
                          <span className="sr-only">Enable {skill.name}</span>
                          <input
                            type="checkbox"
                            aria-label={`Enable ${skill.name}`}
                            className="h-4 w-4 rounded border-border/80 text-foreground focus:ring-ring/25 focus:ring-offset-background"
                            checked={skill.enabled}
                            disabled={isUpdating}
                            onChange={(event) =>
                              onToggleSkill(skill.key, event.target.checked)
                            }
                          />
                        </label>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </TabsContent>

        <TabsContent value="calls" className="space-y-4">
          <Separator />
          {calls.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-border py-12 px-4 bg-muted/10 shadow-sm">
              <p className="text-[14px] font-semibold tracking-tight text-foreground">No tool calls</p>
              <p className="text-[13px] text-muted-foreground text-center max-w-sm">No tool executions have been recorded in this workspace yet.</p>
            </div>
          ) : (
            <div className="rounded-xl border border-border bg-card overflow-hidden shadow-sm">
              <Table>
                <TableHeader className="bg-muted/30">
                  <TableRow className="hover:bg-transparent">
                    <TableHead className="text-[11px] font-medium capitalize text-muted-foreground h-9">Execution</TableHead>
                    <TableHead className="text-[11px] font-medium capitalize text-muted-foreground h-9">Status</TableHead>
                    <TableHead className="text-[11px] font-medium capitalize text-muted-foreground h-9 w-36 text-right">Inspect</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {calls.map((call) => {
                    const toolLabel =
                      catalogMap.get(call.tool_name)?.label || call.tool_name;
                    return (
                      <TableRow key={call.id} className="group border-b border-border/60 last:border-0 hover:bg-muted/30 transition-colors duration-200">
                        <TableCell className="py-2.5">
                          <div className="space-y-0.5">
                           <p className="font-semibold text-[13px] tracking-tight text-foreground leading-tight">{toolLabel}</p>
                           <p className="text-[11px] font-medium text-muted-foreground flex gap-1.5 items-center">
                             {call.guided_by_skills.length > 0
                               ? <span className="text-amber-500/90 font-semibold">{call.guided_by_skills.map((s) => s.name).join(', ')}</span>
                               : <span className="opacity-80">Manual</span>}
                             <span className="opacity-40">&bull;</span>
                             <span className="truncate max-w-[16rem]">{call.input_json || '{}'}</span>
                           </p>
                          </div>
                        </TableCell>
                        <TableCell className="py-2.5 align-top pt-3">
                          <Badge variant={permissionStatusVariant(call.status)} className="px-1.5 py-0 text-[10px] uppercase tracking-wider">
                            {call.status}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right py-2.5">
                          <PayloadDialog
                            title={toolLabel}
                            description="Recorded tool input from the audit trail."
                            payload={call.input_json || '{}'}
                          />
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
