import * as React from 'react';

import { cn } from '@/lib/utils';

const Sidebar = ({
  className,
  ...props
}: React.HTMLAttributes<HTMLElement>) => (
  <aside
    className={cn(
      'flex h-full min-h-0 w-full min-w-0 flex-col overflow-hidden bg-sidebar text-sidebar-foreground',
      className,
    )}
    {...props}
  />
);

const SidebarHeader = ({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) => (
  <div
    className={cn(
      'px-4 py-3',
      className,
    )}
    {...props}
  />
);

const SidebarContent = ({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn('flex min-h-0 min-w-0 flex-1 flex-col px-3 py-3', className)} {...props} />
);

const SidebarFooter = ({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) => (
  <div
    className={cn(
      'border-t border-sidebar-border/80 bg-sidebar-muted/35 px-4 py-3',
      className,
    )}
    {...props}
  />
);

const SidebarGroup = ({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn('space-y-1', className)} {...props} />
);

const SidebarGroupLabel = ({
  className,
  ...props
}: React.HTMLAttributes<HTMLParagraphElement>) => (
  <p
    className={cn(
      'px-2 text-[11px] font-semibold text-sidebar-muted-foreground/80',
      className,
    )}
    {...props}
  />
);

const SidebarMenu = ({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn('space-y-0.5', className)} {...props} />
);

const SidebarMenuButton = ({
  className,
  isActive,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { isActive?: boolean }) => (
  <button
    data-active={isActive ? 'true' : 'false'}
    className={cn(
      'group/sidebar flex w-full items-center justify-between rounded-lg border border-transparent px-3 py-2 text-left text-sm transition-all duration-200 outline-none focus-visible:ring-2 focus-visible:ring-ring',
      isActive
        ? 'bg-foreground/[0.04] text-foreground font-medium'
        : 'text-sidebar-muted-foreground hover:bg-foreground/[0.03] hover:text-sidebar-foreground',
      className,
    )}
    {...props}
  />
);

export {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
};
