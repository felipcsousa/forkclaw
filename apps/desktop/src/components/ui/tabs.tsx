import * as React from 'react';

import { cn } from '@/lib/utils';

type TabsContextValue = {
  value: string;
  setValue: (value: string) => void;
};

const TabsContext = React.createContext<TabsContextValue | null>(null);

function useTabsContext() {
  const context = React.useContext(TabsContext);

  if (!context) {
    throw new Error('Tabs components must be used within Tabs.');
  }

  return context;
}

const Tabs = ({
  className,
  defaultValue,
  value,
  onValueChange,
  children,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & {
  defaultValue: string;
  value?: string;
  onValueChange?: (value: string) => void;
}) => {
  const [internalValue, setInternalValue] = React.useState(defaultValue);
  const currentValue = value ?? internalValue;

  const handleValueChange = React.useCallback(
    (nextValue: string) => {
      if (value === undefined) {
        setInternalValue(nextValue);
      }

      onValueChange?.(nextValue);
    },
    [onValueChange, value],
  );

  return (
    <TabsContext.Provider value={{ value: currentValue, setValue: handleValueChange }}>
      <div className={cn('space-y-5', className)} {...props}>
        {children}
      </div>
    </TabsContext.Provider>
  );
};

const TabsList = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      role="tablist"
      className={cn(
        'inline-flex h-10 items-center rounded-2xl border border-border/80 bg-muted/55 p-1 text-muted-foreground',
        className,
      )}
      {...props}
    />
  ),
);

TabsList.displayName = 'TabsList';

const TabsTrigger = React.forwardRef<
  HTMLButtonElement,
  React.ButtonHTMLAttributes<HTMLButtonElement> & { value: string }
>(({ className, value, ...props }, ref) => {
  const context = useTabsContext();
  const isActive = context.value === value;

  return (
    <button
      ref={ref}
      type="button"
      role="tab"
      aria-selected={isActive}
      data-state={isActive ? 'active' : 'inactive'}
      className={cn(
        'inline-flex items-center justify-center rounded-xl px-3.5 py-2 text-sm font-medium transition-all outline-none',
        'hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/30',
        isActive
          ? 'bg-background text-foreground shadow-[0_1px_2px_rgba(15,23,42,0.08)]'
          : 'text-muted-foreground',
        className,
      )}
      onClick={() => context.setValue(value)}
      {...props}
    />
  );
});

TabsTrigger.displayName = 'TabsTrigger';

const TabsContent = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement> & { value: string }
>(({ className, value, ...props }, ref) => {
  const context = useTabsContext();
  const isActive = context.value === value;

  if (!isActive) {
    return null;
  }

  return (
    <div
      ref={ref}
      role="tabpanel"
      data-state="active"
      className={cn('mt-5 outline-none', className)}
      {...props}
    />
  );
});

TabsContent.displayName = 'TabsContent';

export { Tabs, TabsContent, TabsList, TabsTrigger };
