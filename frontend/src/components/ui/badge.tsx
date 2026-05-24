import { cn } from '../../lib/utils';

export function Badge({ className, tone = 'neutral', children }: { className?: string; tone?: 'neutral' | 'success' | 'warning' | 'danger' | 'primary'; children: React.ReactNode }) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold',
        tone === 'neutral' && 'bg-[hsl(var(--panel-soft))] text-[hsl(var(--muted))]',
        tone === 'success' && 'bg-[rgba(22,163,74,0.12)] text-[hsl(var(--success))]',
        tone === 'warning' && 'bg-[rgba(245,158,11,0.14)] text-[#B45309]',
        tone === 'danger' && 'bg-[rgba(220,38,38,0.12)] text-[hsl(var(--danger))]',
        tone === 'primary' && 'bg-[rgba(37,99,235,0.12)] text-[hsl(var(--primary-dark))]',
        className,
      )}
    >
      {children}
    </span>
  );
}
