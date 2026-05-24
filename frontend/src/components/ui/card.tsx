import { cn } from '../../lib/utils';

export function Card({ className, children }: { className?: string; children: React.ReactNode }) {
  return <div className={cn('panel-surface overflow-hidden transition-shadow duration-200 hover:shadow-[0_14px_36px_rgba(15,23,42,0.09)]', className)}>{children}</div>;
}

export function CardHeader({ className, children }: { className?: string; children: React.ReactNode }) {
  return <div className={cn('border-b border-[hsl(var(--line))] bg-[linear-gradient(180deg,hsl(var(--panel-soft))_0%,hsl(var(--panel))_100%)] px-4 py-4', className)}>{children}</div>;
}

export function CardContent({ className, children }: { className?: string; children: React.ReactNode }) {
  return <div className={cn('px-4 py-4', className)}>{children}</div>;
}
