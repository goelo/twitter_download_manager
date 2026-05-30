import * as React from 'react';
import { cn } from '../../lib/utils';

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        'h-10 w-full rounded-md border border-[hsl(var(--line))] bg-[rgba(15,23,42,0.82)] px-3 text-sm text-[hsl(var(--text))] outline-none transition-colors duration-200 ease-out placeholder:text-[hsl(var(--muted))] focus:border-[hsl(var(--primary))] focus:bg-[rgba(15,23,42,0.96)] focus:ring-2 focus:ring-[rgba(14,165,233,0.22)] disabled:cursor-not-allowed disabled:opacity-55',
        className,
      )}
      {...props}
    />
  ),
);
Input.displayName = 'Input';
