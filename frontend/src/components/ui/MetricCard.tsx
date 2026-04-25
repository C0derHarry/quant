import { cn } from '../../lib/utils'
import { ReactNode } from 'react'

interface MetricCardProps {
  label:    string
  value:    string | ReactNode
  sub?:     string | ReactNode
  accent?:  'gain' | 'loss' | 'warn' | 'accent' | 'neutral'
  className?: string
  size?:    'sm' | 'md' | 'lg'
}

const ACCENT_VALUE: Record<string, string> = {
  gain:    'text-gain',
  loss:    'text-loss',
  warn:    'text-warn',
  accent:  'text-accent',
  neutral: 'text-ink-primary',
}

export default function MetricCard({
  label, value, sub, accent = 'neutral', className, size = 'md',
}: MetricCardProps) {
  return (
    <div
      className={cn(
        'rounded-md border border-border bg-bg-surface shadow-card transition-shadow hover:shadow-card-lg',
        size === 'sm' && 'px-4 py-3',
        size === 'md' && 'px-5 py-4',
        size === 'lg' && 'px-6 py-5',
        className,
      )}
    >
      <p className="mb-1 text-2xs font-semibold uppercase tracking-[0.08em] text-ink-secondary">
        {label}
      </p>
      <div className={cn(
        'num font-mono font-semibold',
        size === 'sm' && 'text-xl',
        size === 'md' && 'text-2xl',
        size === 'lg' && 'text-3xl',
        ACCENT_VALUE[accent],
      )}>
        {value}
      </div>
      {sub != null && (
        <p className="mt-1 text-xs text-ink-muted">{sub}</p>
      )}
    </div>
  )
}
