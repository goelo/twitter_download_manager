import * as React from 'react';
import { cn } from '../../lib/utils';

type Props = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'default' | 'secondary' | 'danger' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
};

export function Button({ className, variant = 'default', size = 'md', ...props }: Props) {
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center rounded-lg border px-3 font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:pointer-events-none disabled:opacity-50',
        size === 'sm' && 'h-8 text-sm',
        size === 'md' && 'h-10 text-sm',
        size === 'lg' && 'h-11 text-base',
        variant === 'default' && 'border-primary bg-primary text-white hover:bg-blue-700',
        variant === 'secondary' && 'border-line bg-white text-text hover:bg-slate-50',
        variant === 'danger' && 'border-danger bg-danger text-white hover:bg-red-700',
        variant === 'ghost' && 'border-transparent bg-transparent text-text hover:bg-slate-100',
        className,
      )}
      {...props}
    />
  );
}
