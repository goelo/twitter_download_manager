import { cn } from '../../lib/utils';

export function Badge({ className, tone = 'neutral', children }: { className?: string; tone?: 'neutral' | 'success' | 'warning' | 'danger' | 'primary'; children: React.ReactNode }) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold tracking-wide',
        tone === 'neutral' && 'border-[rgba(148,163,184,0.26)] bg-[rgba(148,163,184,0.1)] text-[hsl(var(--muted))]',
        tone === 'success' && 'border-[rgba(34,197,94,0.28)] bg-[rgba(34,197,94,0.12)] text-[hsl(var(--success))]',
        tone === 'warning' && 'border-[rgba(251,191,36,0.28)] bg-[rgba(251,191,36,0.12)] text-[hsl(var(--warning))]',
        tone === 'danger' && 'border-[rgba(248,113,113,0.28)] bg-[rgba(248,113,113,0.12)] text-[hsl(var(--danger))]',
        tone === 'primary' && 'border-[rgba(14,165,233,0.3)] bg-[rgba(14,165,233,0.14)] text-[hsl(var(--primary-dark))]',
        className,
      )}
    >
      {children}
    </span>
  );
}
