import { cn } from '../../lib/utils'

type Variant = 'gain' | 'loss' | 'warn' | 'accent' | 'neutral' | 'violet'

const VARIANTS: Record<Variant, string> = {
  gain:    'bg-[rgba(63,185,80,.14)] text-gain   border-[rgba(63,185,80,.25)]',
  loss:    'bg-[rgba(248,81,73,.14)] text-loss   border-[rgba(248,81,73,.25)]',
  warn:    'bg-[rgba(210,153,34,.14)] text-warn  border-[rgba(210,153,34,.25)]',
  accent:  'bg-[rgba(56,139,253,.14)] text-accent border-[rgba(56,139,253,.25)]',
  violet:  'bg-[rgba(188,140,255,.14)] text-violet border-[rgba(188,140,255,.25)]',
  neutral: 'bg-bg-elevated text-ink-secondary border-border',
}

export function regimeBadge(regime: string) {
  const map: Record<string, Variant> = { Bull: 'gain', Bear: 'loss', Sideways: 'warn' }
  return map[regime] ?? 'neutral'
}

interface BadgeProps {
  children: React.ReactNode
  variant?: Variant
  className?: string
}

export default function Badge({ children, variant = 'neutral', className }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-sm border px-1.5 py-0.5 font-mono text-xs font-semibold uppercase tracking-wide',
        VARIANTS[variant],
        className,
      )}
    >
      {children}
    </span>
  )
}
