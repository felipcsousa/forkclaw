import * as React from 'react';
import { cn } from '@/lib/utils';

const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
    ({ className, type, ...props }, ref) => {
        return (
            <input
                type={type}
                className={cn(
                    'flex h-10 w-full rounded-xl border border-border/70 bg-background px-3.5 py-2 text-sm text-foreground shadow-[inset_0_1px_0_rgba(255,255,255,0.6)] transition-all',
                    'placeholder:text-muted-foreground',
                    'hover:border-border hover:bg-muted/35',
                    'focus:border-ring/25 focus:outline-none focus:ring-2 focus:ring-ring/15',
                    'disabled:cursor-not-allowed disabled:opacity-50',
                    className,
                )}
                ref={ref}
                {...props}
            />
        );
    },
);
Input.displayName = 'Input';

export { Input };
