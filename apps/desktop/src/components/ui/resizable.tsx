import * as React from 'react';
import {
  Group,
  Panel,
  Separator,
  type GroupProps,
  type PanelProps,
  type SeparatorProps,
} from 'react-resizable-panels';

import { cn } from '@/lib/utils';

const ResizablePanelGroup = ({
  className,
  ...props
}: GroupProps & { className?: string }) => (
  <Group
    className={cn(
      'flex h-full w-full data-[orientation=vertical]:flex-col',
      className,
    )}
    {...props}
  />
);

const ResizablePanel = (props: PanelProps) => <Panel {...props} />;

const ResizableHandle = ({
  className,
  withHandle,
  ...props
}: SeparatorProps & { withHandle?: boolean }) => (
  <Separator
    className={cn(
      'relative flex w-3 items-center justify-center bg-transparent transition-colors hover:bg-muted/60 data-[orientation=vertical]:h-3 data-[orientation=vertical]:w-full',
      className,
    )}
    {...props}
  >
    {withHandle ? (
      <div className="h-10 w-1 rounded-full bg-border/90 data-[orientation=vertical]:h-1 data-[orientation=vertical]:w-10" />
    ) : null}
  </Separator>
);

export { ResizableHandle, ResizablePanel, ResizablePanelGroup };
