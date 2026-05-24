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
        'inline-flex items-center justify-center gap-2 rounded-lg border px-3 font-semibold outline-none transition-all duration-200 ease-out focus-visible:ring-2 focus-visible:ring-[rgba(37,99,235,0.22)] focus-visible:ring-offset-2 focus-visible:ring-offset-[hsl(var(--bg))] disabled:pointer-events-none disabled:opacity-50 active:translate-y-[1px]',
        size === 'sm' && 'h-8 text-sm',
        size === 'md' && 'h-10 text-sm',
        size === 'lg' && 'h-11 text-base',
        variant === 'default' && 'border-transparent bg-[linear-gradient(180deg,hsl(var(--primary))_0%,hsl(var(--primary-dark))_100%)] text-white shadow-[0_10px_24px_rgba(37,99,235,0.22)] hover:-translate-y-[1px] hover:shadow-[0_14px_30px_rgba(37,99,235,0.26)]',
        variant === 'secondary' && 'border-[hsl(214_24%_68%)] bg-[linear-gradient(180deg,hsl(214_30%_91%)_0%,hsl(214_28%_84%)_100%)] text-[hsl(var(--primary-dark))] shadow-[0_8px_18px_rgba(31,49,74,0.10)] hover:-translate-y-[1px] hover:border-[hsl(var(--primary))] hover:bg-[linear-gradient(180deg,hsl(214_34%_88%)_0%,hsl(214_30%_78%)_100%)] hover:text-[hsl(218_70%_24%)] hover:shadow-[0_12px_24px_rgba(31,49,74,0.14)]',
        variant === 'danger' && 'border-transparent bg-[linear-gradient(180deg,hsl(var(--danger))_0%,#c81e1e_100%)] text-white shadow-[0_10px_24px_rgba(220,38,38,0.18)] hover:-translate-y-[1px] hover:shadow-[0_14px_30px_rgba(220,38,38,0.22)]',
        variant === 'ghost' && 'border-[hsl(214_22%_78%)] bg-[hsl(214_28%_92%)] text-[hsl(var(--primary-dark))] hover:bg-[hsl(214_30%_84%)] hover:text-[hsl(218_70%_24%)]',
        className,
      )}
      {...props}
    />
  );
}
