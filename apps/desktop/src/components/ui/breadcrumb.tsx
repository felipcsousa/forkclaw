import * as React from 'react';
import { ChevronRight } from 'lucide-react';

import { cn } from '@/lib/utils';

const Breadcrumb = React.forwardRef<HTMLElement, React.ComponentPropsWithoutRef<'nav'>>(
  ({ className, ...props }, ref) => (
    <nav ref={ref} aria-label="breadcrumb" className={cn('', className)} {...props} />
  ),
);
Breadcrumb.displayName = 'Breadcrumb';

const BreadcrumbList = React.forwardRef<HTMLOListElement, React.ComponentPropsWithoutRef<'ol'>>(
  ({ className, ...props }, ref) => (
    <ol
      ref={ref}
      className={cn(
        'flex flex-wrap items-center gap-1.5 text-sm text-muted-foreground',
        className,
      )}
      {...props}
    />
  ),
);
BreadcrumbList.displayName = 'BreadcrumbList';

const BreadcrumbItem = React.forwardRef<HTMLLIElement, React.ComponentPropsWithoutRef<'li'>>(
  ({ className, ...props }, ref) => (
    <li ref={ref} className={cn('inline-flex items-center gap-1.5', className)} {...props} />
  ),
);
BreadcrumbItem.displayName = 'BreadcrumbItem';

const BreadcrumbPage = React.forwardRef<HTMLSpanElement, React.ComponentPropsWithoutRef<'span'>>(
  ({ className, ...props }, ref) => (
    <span ref={ref} aria-current="page" className={cn('font-medium text-foreground', className)} {...props} />
  ),
);
BreadcrumbPage.displayName = 'BreadcrumbPage';

const BreadcrumbSeparator = ({
  className,
  children,
  ...props
}: React.ComponentPropsWithoutRef<'li'>) => (
  <li
    role="presentation"
    aria-hidden="true"
    className={cn('text-muted-foreground/65', className)}
    {...props}
  >
    {children ?? <ChevronRight className="h-3.5 w-3.5" />}
  </li>
);
BreadcrumbSeparator.displayName = 'BreadcrumbSeparator';

export {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
};
