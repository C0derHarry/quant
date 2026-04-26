import { useState, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import {
  getIndices, getSectors, getIndexList, getIndexStocks,
  type TickerSnapshot, type SectorStock,
} from '../lib/api'
import { fmtPct, fmtLargeNum, isMarketOpen } from '../lib/utils'
import { PageLoader, ErrorState } from '../components/ui/Spinner'
import Spinner from '../components/ui/Spinner'
import StockChartPanel from '../components/ui/StockChartPanel'
import { TrendingUp, TrendingDown, ArrowRight, Search, ChevronDown } from 'lucide-react'
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

function IndexStockRow({ stock, onClick }: { stock: SectorStock; onClick: () => void }) {
  const up = stock.pct_change >= 0
  return (
    <button
      onClick={onClick}
      className="flex w-full items-center gap-4 border-b border-border/50 px-4 py-3 text-left transition-colors hover:bg-bg-elevated last:border-0"
    >
      <div className="w-28 shrink-0">
        <p className="font-mono text-sm font-semibold text-accent">{stock.symbol}</p>
        <p className="mt-0.5 max-w-[110px] truncate text-xs text-ink-muted">{stock.name}</p>
      </div>

      <div className="flex-1" />

      <span className="num w-28 shrink-0 text-right font-mono text-sm text-ink-primary">
        ₹{stock.price.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
      </span>

      <span className={cn('num w-20 shrink-0 text-right font-mono text-sm font-semibold',
        up ? 'text-gain' : 'text-loss')}>
        {up ? '+' : ''}{stock.pct_change.toFixed(2)}%
      </span>

      <span className="num w-20 shrink-0 text-right font-mono text-xs text-ink-secondary">
        {fmtLargeNum(stock.volume)}
      </span>
    </button>
  )
}

export default function MarketOverview() {
  const { data: indices, isLoading: iL, error: iE } =
    useQuery({ queryKey: ['indices'], queryFn: getIndices, refetchInterval: REFRESH })

  const { data: sectors, isLoading: sL, error: sE } =
    useQuery({ queryKey: ['sectors'], queryFn: getSectors, refetchInterval: REFRESH })

  const { data: indexList } = useQuery({
    queryKey: ['indexList'],
    queryFn:  getIndexList,
    staleTime: Infinity,
  })

  const [indexSearch, setIndexSearch]     = useState('')
  const [selectedIndex, setSelectedIndex] = useState<string | null>(null)
  const [showDrop, setShowDrop]           = useState(false)
  const [selectedStock, setSelectedStock] = useState<SectorStock | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const { data: indexStocks, isLoading: loadingStocks } = useQuery({
    queryKey: ['indexStocks', selectedIndex],
    queryFn:  () => getIndexStocks(selectedIndex!),
    enabled:  !!selectedIndex,
    staleTime: 30_000,
  })

  const filteredIndices = (indexList ?? []).filter(n =>
    indexSearch ? n.toLowerCase().includes(indexSearch.toLowerCase()) : true
  )

  function selectIndex(name: string) {
    setSelectedIndex(name)
    setIndexSearch(name)
    setShowDrop(false)
    setSelectedStock(null)
    inputRef.current?.blur()
  }

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

      {/* Index Explorer */}
      <section>
        <h2 className="mb-3 text-2xs font-semibold uppercase tracking-[0.12em] text-ink-disabled">
          Index Explorer — search any NSE index
        </h2>

        {/* Search combobox */}
        <div className="relative max-w-sm">
          <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted" />
          <input
            ref={inputRef}
            type="text"
            value={indexSearch}
            placeholder="Search index (e.g. NIFTY IT, MIDCAP 50)…"
            onChange={e => { setIndexSearch(e.target.value); setShowDrop(true) }}
            onFocus={() => setShowDrop(true)}
            onBlur={() => setTimeout(() => setShowDrop(false), 150)}
            className="w-full rounded border border-border bg-bg-surface py-2 pl-9 pr-8 text-sm text-ink-primary placeholder:text-ink-disabled focus:border-accent focus:outline-none"
          />
          <ChevronDown size={13} className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-muted pointer-events-none" />

          {showDrop && filteredIndices.length > 0 && (
            <div className="absolute top-full z-30 mt-1 max-h-56 w-full overflow-y-auto rounded border border-border bg-bg-elevated shadow-lg">
              {filteredIndices.map(idx => (
                <button
                  key={idx}
                  onMouseDown={() => selectIndex(idx)}
                  className={cn(
                    'w-full px-3 py-2 text-left text-sm transition-colors hover:bg-bg-surface',
                    selectedIndex === idx ? 'text-accent' : 'text-ink-primary',
                  )}
                >
                  {idx}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Constituent stocks */}
        {selectedIndex && (
          <div className="mt-4 rounded-md border border-border bg-bg-surface shadow-card">
            {/* Table header */}
            <div className="flex items-center gap-4 border-b border-border px-4 py-2.5">
              <span className="w-28 shrink-0 text-2xs font-semibold uppercase tracking-wider text-ink-disabled">
                Symbol
              </span>
              <div className="flex-1" />
              <span className="w-28 shrink-0 text-right text-2xs font-semibold uppercase tracking-wider text-ink-disabled">
                Price
              </span>
              <span className="w-20 shrink-0 text-right text-2xs font-semibold uppercase tracking-wider text-ink-disabled">
                Change %
              </span>
              <span className="w-20 shrink-0 text-right text-2xs font-semibold uppercase tracking-wider text-ink-disabled">
                Volume
              </span>
            </div>

            {loadingStocks ? (
              <div className="flex items-center justify-center py-12">
                <Spinner size={24} />
              </div>
            ) : (indexStocks ?? []).length === 0 ? (
              <p className="py-8 text-center text-sm text-ink-disabled">No stocks found.</p>
            ) : (
              <div className="max-h-[420px] overflow-y-auto">
                {(indexStocks ?? []).map(s => (
                  <IndexStockRow
                    key={s.symbol}
                    stock={s}
                    onClick={() => setSelectedStock(s)}
                  />
                ))}
              </div>
            )}
          </div>
        )}
      </section>

      {/* Stock chart panel */}
      {selectedStock && (
        <StockChartPanel
          stock={selectedStock}
          onClose={() => setSelectedStock(null)}
        />
      )}
    </div>
  )
}
