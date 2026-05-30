import * as React from 'react';
import { cn } from '../../lib/utils';

type Props = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'default' | 'secondary' | 'danger' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
};

export function Button({ className, variant = 'default', size = 'md', loading = false, disabled, children, ...props }: Props) {
  return (
    <button
      className={cn(
        'inline-flex shrink-0 cursor-pointer items-center justify-center gap-2 rounded-md border px-3 font-semibold outline-none transition-colors duration-200 ease-out focus-visible:ring-2 focus-visible:ring-[rgba(14,165,233,0.38)] focus-visible:ring-offset-2 focus-visible:ring-offset-[hsl(var(--bg))] disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50',
        size === 'sm' && 'h-8 text-xs',
        size === 'md' && 'h-10 text-sm',
        size === 'lg' && 'h-11 text-base',
        variant === 'default' && 'border-[hsl(var(--primary))] bg-[hsl(var(--primary))] text-white shadow-[0_8px_20px_rgba(14,165,233,0.18)] hover:bg-[#2563eb]',
        variant === 'secondary' && 'border-[hsl(var(--line))] bg-[hsl(var(--panel-soft))] text-[hsl(var(--primary-dark))] hover:border-[hsl(var(--primary))] hover:bg-[rgba(14,165,233,0.12)] hover:text-[hsl(var(--text))]',
        variant === 'danger' && 'border-[rgba(248,113,113,0.36)] bg-[rgba(248,113,113,0.14)] text-[hsl(var(--danger))] hover:bg-[rgba(248,113,113,0.2)] hover:text-white',
        variant === 'ghost' && 'border-transparent bg-transparent text-[hsl(var(--muted))] hover:bg-[rgba(148,163,184,0.1)] hover:text-[hsl(var(--text))]',
        className,
      )}
      disabled={disabled || loading}
      {...props}
    >
      {loading && <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent" />}
      {children}
    </button>
  );
}
