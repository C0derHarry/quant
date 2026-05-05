import { useQuery } from '@tanstack/react-query'
import { getStrategyCatalog, type StrategySpec } from '../../lib/api'
import { PageLoader, ErrorState } from '../ui/Spinner'
import { TrendingUp, BarChart2, ChevronRight, type LucideIcon } from 'lucide-react'
import { cn } from '../../lib/utils'

const STRATEGY_ICONS: Record<string, LucideIcon> = {
  cross_sectional_mom: TrendingUp,
  ivy_gtaa:            BarChart2,
}

interface Props {
  selectedId: string | null
  onChange:   (id: string) => void
  onNext:     () => void
  onBack:     () => void
}

export default function StrategyCatalog({ selectedId, onChange, onNext, onBack }: Props) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['strategy-catalog'],
    queryFn:  getStrategyCatalog,
    staleTime: Infinity,
  })

  if (isLoading) return <PageLoader label="Loading strategy catalog…" />
  if (error)     return <ErrorState message={(error as Error).message} />

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <button onClick={onBack} className="text-xs text-ink-muted hover:text-ink-secondary">← Back</button>
        <div>
          <h2 className="text-sm font-semibold text-ink-primary">Choose a Strategy</h2>
          <p className="text-xs text-ink-muted">Academic-grade strategies with real-world validation.</p>
        </div>
      </div>

      <div className="grid gap-3">
        {(data ?? []).map((s: StrategySpec) => {
          const Icon = STRATEGY_ICONS[s.id] ?? TrendingUp
          const active = selectedId === s.id
          return (
            <button
              key={s.id}
              onClick={() => onChange(s.id)}
              className={cn(
                'flex w-full items-start gap-4 rounded border p-4 text-left transition-all',
                active
                  ? 'border-accent bg-[rgba(56,139,253,.08)]'
                  : 'border-border bg-bg-elevated hover:border-ink-disabled hover:bg-bg-overlay',
              )}
            >
              <div className={cn(
                'mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded',
                active ? 'bg-accent text-white' : 'bg-bg-overlay text-ink-muted',
              )}>
                <Icon size={15} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <p className={cn('text-sm font-semibold', active ? 'text-accent' : 'text-ink-primary')}>
                    {s.label}
                  </p>
                  {s.requires_fundamentals && (
                    <span className="rounded-sm bg-bg-overlay px-1.5 py-0.5 text-2xs font-medium text-ink-muted">
                      Needs fundamentals
                    </span>
                  )}
                </div>
                <p className="mt-1 text-xs text-ink-muted leading-relaxed line-clamp-2">{s.description}</p>
                <p className="mt-1.5 text-2xs text-ink-disabled">{s.reference}</p>
              </div>
              {active && <ChevronRight size={14} className="text-accent shrink-0 mt-1" />}
            </button>
          )
        })}
      </div>

      <button
        onClick={onNext}
        disabled={!selectedId}
        className="mt-2 w-full rounded bg-accent py-2.5 text-sm font-semibold text-white transition-opacity disabled:opacity-40 hover:bg-accent/90"
      >
        Configure Strategy
      </button>
    </div>
  )
}
