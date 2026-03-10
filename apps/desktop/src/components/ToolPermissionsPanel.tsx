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
import type { ToolCallRecord, ToolPermissionLevel, ToolPermissionRecord } from '../lib/backend';

interface ToolPermissionsPanelProps {
  workspaceRoot: string;
  permissions: ToolPermissionRecord[];
  calls: ToolCallRecord[];
  isLoading: boolean;
  isUpdating: boolean;
  onChangePermission: (toolName: string, permissionLevel: ToolPermissionLevel) => void;
}

const toolLabels: Record<string, string> = {
  list_files: 'List files',
  read_file: 'Read file',
  write_file: 'Write file',
  edit_file: 'Edit file',
  clipboard_read: 'Clipboard read',
  clipboard_write: 'Clipboard write',
};

const toolModeDescriptions: Record<ToolPermissionLevel, string> = {
  deny: 'Block every attempt immediately.',
  ask: 'Pause the run and require explicit approval.',
  allow: 'Execute automatically inside the workspace boundary.',
};

function statusVariant(status: string) {
  if (status === 'completed' || status === 'active' || status === 'running') {
    return 'success' as const;
  }

  if (status === 'denied' || status === 'failed') {
    return 'destructive' as const;
  }

  return 'secondary' as const;
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
  workspaceRoot,
  permissions,
  calls,
  isLoading,
  isUpdating,
  onChangePermission,
}: ToolPermissionsPanelProps) {
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
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Tool</TableHead>
                  <TableHead>Workspace</TableHead>
                  <TableHead>Policy</TableHead>
                  <TableHead className="w-32">Mode</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {permissions.map((perm) => (
                  <TableRow key={perm.id}>
                    <TableCell>
                      <div className="space-y-1">
                        <p className="font-medium text-foreground">
                          {toolLabels[perm.tool_name] || perm.tool_name}
                        </p>
                        <p className="text-sm text-muted-foreground">
                          {toolModeDescriptions[perm.permission_level]}
                        </p>
                      </div>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {perm.workspace_path || 'No filesystem workspace required.'}
                    </TableCell>
                    <TableCell>
                      <Badge variant={statusVariant(perm.status)}>{perm.status}</Badge>
                    </TableCell>
                    <TableCell>
                      <select
                        className="flex h-9 w-full rounded-xl border border-border/70 bg-background px-3 py-2 text-sm text-foreground shadow-[inset_0_1px_0_rgba(255,255,255,0.6)] transition-all hover:border-border hover:bg-muted/35 focus:border-ring/25 focus:outline-none focus:ring-2 focus:ring-ring/15"
                        aria-label={`Mode for ${perm.tool_name}`}
                        value={perm.permission_level}
                        onChange={(e) =>
                          onChangePermission(
                            perm.tool_name,
                            e.target.value as ToolPermissionLevel,
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
                ))}
              </TableBody>
            </Table>
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
                {calls.map((call) => (
                  <TableRow key={call.id}>
                    <TableCell className="font-medium text-foreground">
                      {toolLabels[call.tool_name] || call.tool_name}
                    </TableCell>
                    <TableCell>
                      <Badge variant={statusVariant(call.status)}>{call.status}</Badge>
                    </TableCell>
                    <TableCell className="max-w-[28rem] truncate text-sm text-muted-foreground">
                      {call.input_json || '{}'}
                    </TableCell>
                    <TableCell className="text-right">
                      <PayloadDialog
                        title={toolLabels[call.tool_name] || call.tool_name}
                        description="Recorded tool input from the audit trail."
                        payload={call.input_json || '{}'}
                      />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
