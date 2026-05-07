import { useQuery } from '@tanstack/react-query'
import { listPortfolios } from '../../lib/api'
import { PageLoader, ErrorState } from '../ui/Spinner'
import { Briefcase, ChevronRight } from 'lucide-react'
import { cn } from '../../lib/utils'

interface Props {
  selectedId: string | null
  onChange:   (id: string) => void
  onNext:     () => void
}

export default function PortfolioPicker({ selectedId, onChange, onNext }: Props) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['portfolios'],
    queryFn:  listPortfolios,
    staleTime: 60_000,
  })

  if (isLoading) return <PageLoader label="Loading portfolios…" />
  if (error)     return <ErrorState message={(error as Error).message} />

  const portfolios = (data ?? []) as Array<{ id: string; name: string; tickers: string[]; capital?: number }>

  if (portfolios.length === 0) {
    return (
      <div className="flex flex-col items-center gap-3 py-16 text-center">
        <Briefcase size={32} className="text-ink-disabled" />
        <p className="text-sm font-semibold text-ink-primary">No portfolios yet</p>
        <p className="text-xs text-ink-muted">Create a portfolio in the Portfolio section first.</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-sm font-semibold text-ink-primary">Select a Portfolio</h2>
        <p className="mt-0.5 text-xs text-ink-muted">The backtest will use this portfolio's ticker universe.</p>
      </div>

      <div className="grid gap-2">
        {portfolios.map(p => (
          <button
            key={p.id}
            onClick={() => onChange(p.id)}
            className={cn(
              'flex w-full items-center gap-4 rounded border p-4 text-left transition-all',
              selectedId === p.id
                ? 'border-accent bg-[rgba(56,139,253,.08)] text-accent'
                : 'border-border bg-bg-elevated hover:border-ink-disabled hover:bg-bg-overlay',
            )}
          >
            <Briefcase size={16} className={selectedId === p.id ? 'text-accent' : 'text-ink-muted'} />
            <div className="flex-1 min-w-0">
              <p className={cn('text-sm font-semibold', selectedId === p.id ? 'text-accent' : 'text-ink-primary')}>
                {p.name}
              </p>
              <p className="text-xs text-ink-muted mt-0.5">
                {p.tickers?.length ?? 0} tickers
                {p.capital ? ` · ₹${p.capital.toLocaleString('en-IN')}` : ''}
              </p>
            </div>
            {selectedId === p.id && <ChevronRight size={14} className="text-accent shrink-0" />}
          </button>
        ))}
      </div>

      <button
        onClick={onNext}
        disabled={!selectedId}
        className="mt-2 w-full rounded bg-accent py-2.5 text-sm font-semibold text-white transition-opacity disabled:opacity-40 hover:bg-accent/90"
      >
        Continue
      </button>
    </div>
  )
}
