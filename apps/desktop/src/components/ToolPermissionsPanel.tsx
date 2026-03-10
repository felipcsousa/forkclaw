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
import type {
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
  isLoading: boolean;
  isUpdating: boolean;
  onChangeProfile: (profileId: ToolPolicyProfileId) => void;
  onChangePermission: (toolName: string, permissionLevel: ToolPermissionLevel) => void;
}

const toolModeDescriptions: Record<ToolPermissionLevel, string> = {
  deny: 'Block every attempt immediately.',
  ask: 'Pause the run and require explicit approval.',
  allow: 'Execute automatically inside the configured boundary.',
};

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
  isLoading,
  isUpdating,
  onChangeProfile,
  onChangePermission,
}: ToolPermissionsPanelProps) {
  const catalogMap = new Map(catalog.map((item) => [item.id, item]));
  const catalogOrder = new Map(catalog.map((item, index) => [item.id, index]));
  const overrideToolNames = new Set(policy?.overrides.map((item) => item.tool_name) || []);
  const activeProfile =
    policy?.profiles.find((item) => item.id === policy.profile_id) || null;

  const sortedPermissions = [...permissions].sort((left, right) => {
    const leftIndex = catalogOrder.get(left.tool_name) ?? Number.MAX_SAFE_INTEGER;
    const rightIndex = catalogOrder.get(right.tool_name) ?? Number.MAX_SAFE_INTEGER;
    if (leftIndex !== rightIndex) {
      return leftIndex - rightIndex;
    }
    return left.tool_name.localeCompare(right.tool_name);
  });

  const groupedPermissions = sortedPermissions.reduce<
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

  return (
    <div className="space-y-5 animate-fade-in">
      <Tabs defaultValue="policy">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <TabsList>
            <TabsTrigger value="policy">Permission policy</TabsTrigger>
            <TabsTrigger value="calls">Recent calls</TabsTrigger>
          </TabsList>
          <p className="max-w-xs truncate text-xs text-muted-foreground" title={workspaceRoot}>
            Root: {workspaceRoot}
          </p>
        </div>

        <TabsContent value="policy" className="space-y-4">
          <Separator />
          <div className="grid gap-4 rounded-[1.2rem] border border-border/80 bg-muted/12 p-4 lg:grid-cols-[minmax(0,1fr)_16rem]">
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-sm font-medium text-foreground">Policy profile</p>
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
                className="text-xs font-medium uppercase tracking-[0.12em] text-muted-foreground"
              >
                Policy profile
              </label>
              <select
                id="tool-policy-profile"
                aria-label="Policy profile"
                className="flex h-10 w-full rounded-xl border border-border/70 bg-background px-3 py-2 text-sm text-foreground shadow-[inset_0_1px_0_rgba(255,255,255,0.6)] transition-all hover:border-border hover:bg-muted/35 focus:border-ring/25 focus:outline-none focus:ring-2 focus:ring-ring/15"
                value={policy?.profile_id || 'minimal'}
                onChange={(event) =>
                  onChangeProfile(event.target.value as ToolPolicyProfileId)
                }
                disabled={isUpdating || !policy}
              >
                {(policy?.profiles || []).map((profile) => (
                  <option key={profile.id} value={profile.id}>
                    {profile.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {isLoading && permissions.length === 0 ? (
            <p className="empty-dashed rounded-[1rem] px-4 py-6 text-sm text-muted-foreground animate-pulse">
              Loading tool policies...
            </p>
          ) : permissions.length === 0 ? (
            <p className="empty-dashed rounded-[1rem] px-4 py-6 text-sm text-muted-foreground">
              No tool policies found. The agent cannot execute local tools until
              permissions are seeded.
            </p>
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
                        {group.groupLabel}
                      </h3>
                      <p className="text-xs text-muted-foreground">
                        {activeProfile?.defaults[group.group as ToolGroup]
                          ? `Default: ${activeProfile.defaults[group.group as ToolGroup]}`
                          : 'No default policy registered for this group.'}
                      </p>
                    </div>
                    <Badge variant="secondary">{group.items.length} tool(s)</Badge>
                  </div>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Tool</TableHead>
                        <TableHead>Details</TableHead>
                        <TableHead>Workspace</TableHead>
                        <TableHead>Policy</TableHead>
                        <TableHead className="w-32">Mode</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {group.items.map((permission) => {
                        const descriptor = catalogMap.get(permission.tool_name);
                        return (
                          <TableRow key={permission.id}>
                            <TableCell>
                              <div className="space-y-1">
                                <p className="font-medium text-foreground">
                                  {descriptor?.label || permission.tool_name}
                                </p>
                                <p className="text-sm text-muted-foreground">
                                  {toolModeDescriptions[permission.permission_level]}
                                </p>
                              </div>
                            </TableCell>
                            <TableCell>
                              <div className="space-y-2">
                                <p className="text-sm text-muted-foreground">
                                  {descriptor?.description ||
                                    'No catalog description is available for this tool.'}
                                </p>
                                <div className="flex flex-wrap gap-2">
                                  <Badge
                                    variant={riskVariant(descriptor?.risk || 'low')}
                                  >
                                    {descriptor?.risk || 'low'}
                                  </Badge>
                                  <Badge
                                    variant={toolStatusVariant(
                                      descriptor?.status || 'disabled',
                                    )}
                                  >
                                    {descriptor?.status || 'disabled'}
                                  </Badge>
                                  {overrideToolNames.has(permission.tool_name) ? (
                                    <Badge variant="outline">override</Badge>
                                  ) : null}
                                </div>
                              </div>
                            </TableCell>
                            <TableCell className="text-sm text-muted-foreground">
                              {permission.workspace_path ||
                                (descriptor?.requires_workspace
                                  ? workspaceRoot
                                  : 'No filesystem workspace required.')}
                            </TableCell>
                            <TableCell>
                              <Badge variant={permissionStatusVariant(permission.status)}>
                                {permission.status}
                              </Badge>
                            </TableCell>
                            <TableCell>
                              <select
                                className="flex h-9 w-full rounded-xl border border-border/70 bg-background px-3 py-2 text-sm text-foreground shadow-[inset_0_1px_0_rgba(255,255,255,0.6)] transition-all hover:border-border hover:bg-muted/35 focus:border-ring/25 focus:outline-none focus:ring-2 focus:ring-ring/15"
                                aria-label={`Mode for ${permission.tool_name}`}
                                value={permission.permission_level}
                                onChange={(event) =>
                                  onChangePermission(
                                    permission.tool_name,
                                    event.target.value as ToolPermissionLevel,
                                  )
                                }
                                disabled={isUpdating}
                              >
                                <option value="deny">deny</option>
                                <option value="ask">ask</option>
                                <option value="allow">allow</option>
                              </select>
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </section>
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="calls" className="space-y-4">
          <Separator />
          {calls.length === 0 ? (
            <p className="empty-dashed rounded-[1rem] px-4 py-6 text-sm text-muted-foreground">
              No tool calls recorded yet.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Tool</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Input</TableHead>
                  <TableHead className="w-36 text-right">Inspect</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {calls.map((call) => {
                  const descriptor = catalogMap.get(call.tool_name);
                  return (
                    <TableRow key={call.id}>
                      <TableCell className="font-medium text-foreground">
                        {descriptor?.label || call.tool_name}
                      </TableCell>
                      <TableCell>
                        <Badge variant={permissionStatusVariant(call.status)}>
                          {call.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="max-w-[28rem] truncate text-sm text-muted-foreground">
                        {call.input_json || '{}'}
                      </TableCell>
                      <TableCell className="text-right">
                        <PayloadDialog
                          title={descriptor?.label || call.tool_name}
                          description="Recorded tool input from the audit trail."
                          payload={call.input_json || '{}'}
                        />
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
