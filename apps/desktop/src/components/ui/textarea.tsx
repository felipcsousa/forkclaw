import * as React from 'react';
import { cn } from '@/lib/utils';

const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(
    ({ className, ...props }, ref) => {
        return (
            <textarea
                className={cn(
                    'flex min-h-[96px] w-full resize-vertical rounded-[1rem] border border-border/70 bg-background px-3.5 py-3 text-sm leading-relaxed text-foreground shadow-[inset_0_1px_0_rgba(255,255,255,0.6)] transition-all',
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
Textarea.displayName = 'Textarea';

export { Textarea };
