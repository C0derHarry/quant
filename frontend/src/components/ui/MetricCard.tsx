import { cn } from '../../lib/utils'
import { ReactNode } from 'react'
import { HelpCircle } from 'lucide-react'

interface MetricCardProps {
  label:    string
  value:    string | ReactNode
  sub?:     string | ReactNode
  accent?:  'gain' | 'loss' | 'warn' | 'accent' | 'neutral'
  className?: string
  size?:    'sm' | 'md' | 'lg'
  tooltip?: string
}

const ACCENT_VALUE: Record<string, string> = {
  gain:    'text-gain',
  loss:    'text-loss',
  warn:    'text-warn',
  accent:  'text-accent',
  neutral: 'text-ink-primary',
}

export default function MetricCard({
  label, value, sub, accent = 'neutral', className, size = 'md', tooltip,
}: MetricCardProps) {
  return (
    <div
      className={cn(
        'relative rounded-md border border-border bg-bg-surface shadow-card transition-shadow hover:shadow-card-lg',
        size === 'sm' && 'px-4 py-3',
        size === 'md' && 'px-5 py-4',
        size === 'lg' && 'px-6 py-5',
        className,
      )}
    >
      {tooltip && (
        <div className="group absolute right-2.5 top-2.5 z-10">
          <HelpCircle size={12} className="cursor-help text-ink-disabled transition-colors hover:text-ink-muted" />
          <div className="pointer-events-none invisible absolute right-0 top-5 z-20 w-56 rounded border border-border bg-bg-elevated p-2.5 text-xs leading-relaxed text-ink-secondary shadow-lg group-hover:visible">
            {tooltip}
          </div>
        </div>
      )}
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
