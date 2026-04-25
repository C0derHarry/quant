import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { getIndices, getSectors, TickerSnapshot } from '../lib/api'
import { fmtPct, isMarketOpen } from '../lib/utils'
import { PageLoader, ErrorState } from '../components/ui/Spinner'
import { TrendingUp, TrendingDown, ArrowRight } from 'lucide-react'
import { cn } from '../lib/utils'

const REFRESH = isMarketOpen() ? 10_000 : 0

function DeltaChip({ pct }: { pct: number }) {
  const up = pct >= 0
  return (
    <span className={cn(
      'inline-flex items-center gap-1 rounded-sm px-1.5 py-0.5 text-xs font-mono font-medium',
      up ? 'bg-[rgba(63,185,80,.1)] text-gain' : 'bg-[rgba(248,81,73,.1)] text-loss',
    )}>
      {up ? <TrendingUp size={10} /> : <TrendingDown size={10} />}
      {fmtPct(pct)}
    </span>
  )
}

function IndexTile({ name, snap }: { name: string; snap: TickerSnapshot }) {
  return (
    <div className="rounded-md border border-border bg-bg-surface p-4 shadow-card">
      <p className="mb-2 text-2xs font-semibold uppercase tracking-widest text-ink-muted">{name}</p>
      <p className="num font-mono text-2xl font-semibold text-ink-primary">
        {snap.price.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
      </p>
      <div className="mt-2 flex items-center gap-2">
        <DeltaChip pct={snap.pct_change} />
        <span className={cn('num text-xs font-mono', snap.change >= 0 ? 'text-gain' : 'text-loss')}>
          {snap.change >= 0 ? '+' : ''}{snap.change.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
        </span>
      </div>
    </div>
  )
}

function SectorCard({ name, snap }: { name: string; snap: TickerSnapshot }) {
  const navigate = useNavigate()
  const up       = snap.pct_change >= 0

  return (
    <button
      onClick={() => navigate(`/sector/${encodeURIComponent(name)}`)}
      className={cn(
        'group w-full rounded-md border bg-bg-surface p-5 text-left shadow-card',
        'transition-all duration-200 hover:shadow-card-lg hover:-translate-y-0.5',
        up ? 'border-[rgba(63,185,80,.18)] hover:border-[rgba(63,185,80,.35)]'
           : 'border-[rgba(248,81,73,.18)] hover:border-[rgba(248,81,73,.35)]',
      )}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-2xs font-semibold uppercase tracking-widest text-ink-muted">{name}</p>
          <p className="num mt-1.5 font-mono text-2xl font-semibold text-ink-primary">
            {snap.price.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
          </p>
        </div>
        <div className={cn(
          'flex h-8 w-8 items-center justify-center rounded-sm transition-colors',
          up ? 'bg-[rgba(63,185,80,.1)] text-gain' : 'bg-[rgba(248,81,73,.1)] text-loss',
        )}>
          {up ? <TrendingUp size={16} /> : <TrendingDown size={16} />}
        </div>
      </div>

      <div className="mt-3 flex items-center justify-between">
        <DeltaChip pct={snap.pct_change} />
        <span className={cn('num text-xs font-mono', up ? 'text-gain' : 'text-loss')}>
          {snap.change >= 0 ? '+' : ''}{snap.change.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
        </span>
      </div>

      <div className={cn(
        'mt-3 flex items-center gap-1 text-xs font-medium opacity-0 transition-opacity',
        'group-hover:opacity-100',
        up ? 'text-gain' : 'text-loss',
      )}>
        View stocks <ArrowRight size={12} />
      </div>
    </button>
  )
}

export default function MarketOverview() {
  const { data: indices, isLoading: iL, error: iE } =
    useQuery({ queryKey: ['indices'], queryFn: getIndices, refetchInterval: REFRESH })

  const { data: sectors, isLoading: sL, error: sE } =
    useQuery({ queryKey: ['sectors'], queryFn: getSectors, refetchInterval: REFRESH })

  if (iL || sL) return <PageLoader label="Fetching market data…" />
  if (iE || sE) return <ErrorState message={String((iE || sE)?.message)} />

  return (
    <div className="space-y-8 animate-fade-up">
      {/* Index strip */}
      <section>
        <h2 className="mb-3 text-2xs font-semibold uppercase tracking-[0.12em] text-ink-disabled">
          Indices
        </h2>
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {Object.entries(indices ?? {}).map(([name, snap]) => (
            <IndexTile key={name} name={name} snap={snap} />
          ))}
        </div>
      </section>

      {/* Sector grid */}
      <section>
        <h2 className="mb-3 text-2xs font-semibold uppercase tracking-[0.12em] text-ink-disabled">
          Sector Performance — click to drill down
        </h2>
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-4">
          {Object.entries(sectors ?? {}).map(([name, snap]) => (
            <SectorCard key={name} name={name} snap={snap} />
          ))}
        </div>
      </section>
    </div>
  )
}
