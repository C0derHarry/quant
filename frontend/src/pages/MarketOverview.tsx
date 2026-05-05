import { useState, useRef, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer,
} from 'recharts'
import {
  getIndices, getSectors, getIndexList, getIndexStocks, getAssetCompare,
  type TickerSnapshot, type SectorStock,
} from '../lib/api'
import { fmtPct, fmtLargeNum, isMarketOpen } from '../lib/utils'
import { PageLoader, ErrorState } from '../components/ui/Spinner'
import Spinner from '../components/ui/Spinner'
import StockChartPanel from '../components/ui/StockChartPanel'
import { TrendingUp, TrendingDown, ArrowRight, Search, ChevronDown } from 'lucide-react'
import { cn } from '../lib/utils'

const REFRESH = isMarketOpen() ? 1_000 : 0

const MOVER_INDICES = [
  'NIFTY 50', 'NIFTY NEXT 50', 'NIFTY 100',
  'NIFTY MIDCAP 50', 'NIFTY SMALLCAP 100', 'NIFTY 500',
]

const ASSET_COLORS: Record<string, string> = {
  'NIFTY 50':  '#388BFD',
  'Gold':      '#D29922',
  'IT Sector': '#BC8CFF',
  'Banking':   '#39D353',
  'Midcap':    '#3FB950',
  'USD/INR':   '#F85149',
}

const PERIODS = ['1m', '3m', '6m', '1y', '3y'] as const

// ── shared sub-components ─────────────────────────────────────────

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

// ── main page ─────────────────────────────────────────────────────

export default function MarketOverview() {
  const [view, setView] = useState<'overview' | 'movers' | 'assets'>('overview')

  // Overview state
  const [indexSearch,   setIndexSearch]   = useState('')
  const [selectedIndex, setSelectedIndex] = useState<string | null>(null)
  const [showDrop,      setShowDrop]      = useState(false)
  const [selectedStock, setSelectedStock] = useState<SectorStock | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Movers state
  const [moverIndex, setMoverIndex] = useState('NIFTY 50')
  const [moverTab,   setMoverTab]   = useState<'gainers' | 'losers' | 'volume'>('gainers')

  // Assets state
  const [assetPeriod, setAssetPeriod] = useState('1y')

  // Queries
  const { data: indices, isLoading: iL, error: iE } = useQuery({
    queryKey: ['indices'], queryFn: getIndices, refetchInterval: REFRESH,
  })
  const { data: sectors, isLoading: sL, error: sE } = useQuery({
    queryKey: ['sectors'], queryFn: getSectors, refetchInterval: REFRESH,
  })
  const { data: indexList } = useQuery({
    queryKey: ['indexList'], queryFn: getIndexList, staleTime: Infinity,
  })
  const { data: indexStocks, isLoading: loadingStocks } = useQuery({
    queryKey: ['indexStocks', selectedIndex],
    queryFn:  () => getIndexStocks(selectedIndex!),
    enabled:  !!selectedIndex,
    staleTime: 30_000,
  })
  const { data: moverStocks, isLoading: loadingMovers } = useQuery({
    queryKey: ['moverStocks', moverIndex],
    queryFn:  () => getIndexStocks(moverIndex),
    staleTime: 30_000,
  })
  const { data: assetData, isLoading: loadingAssets } = useQuery({
    queryKey: ['assetCompare', assetPeriod],
    queryFn:  () => getAssetCompare(assetPeriod),
    enabled:  view === 'assets',
    staleTime: 60 * 60_000,
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

  const sortedMovers = useMemo(() => {
    if (!moverStocks) return []
    const copy = [...moverStocks]
    if (moverTab === 'gainers') return copy.sort((a, b) => b.pct_change - a.pct_change).slice(0, 15)
    if (moverTab === 'losers')  return copy.sort((a, b) => a.pct_change - b.pct_change).slice(0, 15)
    return copy.sort((a, b) => b.volume - a.volume).slice(0, 15)
  }, [moverStocks, moverTab])

  const assetChartData = useMemo(() => {
    if (!assetData) return []
    const dateMap = new Map<string, Record<string, number>>()
    Object.entries(assetData).forEach(([label, series]) => {
      series.forEach(({ date, value }) => {
        if (!dateMap.has(date)) dateMap.set(date, {})
        dateMap.get(date)![label] = value
      })
    })
    return Array.from(dateMap.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([date, vals]) => ({ date, ...vals }))
  }, [assetData])

  const assetReturns = useMemo(() => {
    if (!assetData) return {} as Record<string, number>
    return Object.fromEntries(
      Object.entries(assetData).map(([label, series]) => [
        label,
        series.length ? parseFloat((series[series.length - 1].value - 100).toFixed(2)) : 0,
      ])
    )
  }, [assetData])

  if (iL || sL) return <PageLoader label="Fetching market data..." />
  if (iE || sE) return <ErrorState message={String((iE || sE)?.message)} />

  return (
    <div className="space-y-6 animate-fade-up">

      {/* View toggle */}
      <div className="flex w-fit items-center gap-0.5 rounded-md border border-border bg-bg-elevated p-0.5">
        {([
          { key: 'overview', label: 'Overview'      },
          { key: 'movers',   label: 'Top Movers'    },
          { key: 'assets',   label: 'Asset Classes' },
        ] as const).map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setView(key)}
            className={cn(
              'rounded px-4 py-1.5 text-sm font-medium transition-all',
              view === key
                ? 'bg-accent/10 text-accent'
                : 'text-ink-muted hover:text-ink-secondary',
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {/* ── OVERVIEW ── */}
      {view === 'overview' && (
        <div className="space-y-8">
          {/* Indices */}
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

          {/* Index Explorer - moved above sector grid */}
          <section>
            <h2 className="mb-3 text-2xs font-semibold uppercase tracking-[0.12em] text-ink-disabled">
              Index Explorer - search any NSE index
            </h2>
            <div className="relative max-w-sm">
              <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted" />
              <input
                ref={inputRef}
                type="text"
                value={indexSearch}
                placeholder="Search index (e.g. NIFTY IT, MIDCAP 50)..."
                onChange={e => { setIndexSearch(e.target.value); setShowDrop(true) }}
                onFocus={() => setShowDrop(true)}
                onBlur={() => setTimeout(() => setShowDrop(false), 150)}
                className="w-full rounded border border-border bg-bg-surface py-2 pl-9 pr-8 text-sm text-ink-primary placeholder:text-ink-disabled focus:border-accent focus:outline-none"
              />
              <ChevronDown size={13} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-ink-muted" />
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
            {selectedIndex && (
              <div className="mt-4 rounded-md border border-border bg-bg-surface shadow-card">
                <div className="flex items-center gap-4 border-b border-border px-4 py-2.5">
                  <span className="w-28 shrink-0 text-2xs font-semibold uppercase tracking-wider text-ink-disabled">Symbol</span>
                  <div className="flex-1" />
                  <span className="w-28 shrink-0 text-right text-2xs font-semibold uppercase tracking-wider text-ink-disabled">Price</span>
                  <span className="w-20 shrink-0 text-right text-2xs font-semibold uppercase tracking-wider text-ink-disabled">Change %</span>
                  <span className="w-20 shrink-0 text-right text-2xs font-semibold uppercase tracking-wider text-ink-disabled">Volume</span>
                </div>
                {loadingStocks ? (
                  <div className="flex items-center justify-center py-12"><Spinner size={24} /></div>
                ) : (indexStocks ?? []).length === 0 ? (
                  <p className="py-8 text-center text-sm text-ink-disabled">No stocks found.</p>
                ) : (
                  <div className="max-h-[420px] overflow-y-auto">
                    {(indexStocks ?? []).map(s => (
                      <IndexStockRow key={s.symbol} stock={s} onClick={() => setSelectedStock(s)} />
                    ))}
                  </div>
                )}
              </div>
            )}
          </section>

          {/* Sector grid */}
          <section>
            <h2 className="mb-3 text-2xs font-semibold uppercase tracking-[0.12em] text-ink-disabled">
              Sector Performance - click to drill down
            </h2>
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-4">
              {Object.entries(sectors ?? {}).map(([name, snap]) => (
                <SectorCard key={name} name={name} snap={snap} />
              ))}
            </div>
          </section>
        </div>
      )}

      {/* ── TOP MOVERS ── */}
      {view === 'movers' && (
        <div className="space-y-5">
          {/* Index pills */}
          <div className="flex flex-wrap gap-2">
            {MOVER_INDICES.map(idx => (
              <button
                key={idx}
                onClick={() => setMoverIndex(idx)}
                className={cn(
                  'rounded px-3 py-1 text-xs font-medium transition-all',
                  moverIndex === idx
                    ? 'bg-accent text-white'
                    : 'border border-border bg-bg-elevated text-ink-secondary hover:border-accent/50 hover:text-ink-primary',
                )}
              >
                {idx}
              </button>
            ))}
          </div>

          {/* Sub-tabs */}
          <div className="flex gap-0 border-b border-border">
            {([
              { key: 'gainers', label: 'Gainers'          },
              { key: 'losers',  label: 'Losers'           },
              { key: 'volume',  label: 'Volume Shockers'  },
            ] as const).map(({ key, label }) => (
              <button
                key={key}
                onClick={() => setMoverTab(key)}
                className={cn(
                  '-mb-px border-b-2 px-5 py-2.5 text-sm font-medium transition-all',
                  moverTab === key
                    ? 'border-accent text-accent'
                    : 'border-transparent text-ink-muted hover:text-ink-secondary',
                )}
              >
                {label}
              </button>
            ))}
          </div>

          {/* Movers list */}
          {loadingMovers ? (
            <div className="flex justify-center py-16"><Spinner size={24} /></div>
          ) : sortedMovers.length === 0 ? (
            <p className="py-12 text-center text-sm text-ink-muted">No data for {moverIndex}.</p>
          ) : (
            <div className="overflow-hidden rounded-md border border-border bg-bg-surface shadow-card">
              {sortedMovers.map((stock, i) => {
                const up = stock.pct_change >= 0
                return (
                  <button
                    key={stock.symbol}
                    onClick={() => setSelectedStock(stock)}
                    className="flex w-full items-center gap-4 border-b border-border/50 px-4 py-3 text-left transition-colors hover:bg-bg-elevated last:border-0"
                  >
                    <span className="w-5 shrink-0 text-right font-mono text-xs text-ink-disabled">{i + 1}</span>
                    <div className="min-w-0 flex-1">
                      <p className="font-mono text-sm font-semibold text-accent">{stock.symbol}</p>
                      <p className="truncate text-xs text-ink-muted">{stock.name}</p>
                    </div>
                    <span className="num shrink-0 font-mono text-sm text-ink-primary">
                      ₹{stock.price.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
                    </span>
                    <DeltaChip pct={stock.pct_change} />
                    <span className={cn(
                      'num w-20 shrink-0 text-right font-mono text-xs',
                      moverTab === 'volume' ? 'text-ink-secondary' : (up ? 'text-gain' : 'text-loss'),
                    )}>
                      {moverTab === 'volume'
                        ? fmtLargeNum(stock.volume)
                        : `${up ? '+' : ''}${stock.change.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`}
                    </span>
                  </button>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* ── ASSET CLASSES ── */}
      {view === 'assets' && (
        <div className="space-y-5">
          {/* Period selector */}
          <div className="flex gap-1">
            {PERIODS.map(p => (
              <button
                key={p}
                onClick={() => setAssetPeriod(p)}
                className={cn(
                  'rounded px-3 py-1.5 font-mono text-xs font-medium uppercase transition-all',
                  assetPeriod === p
                    ? 'bg-accent/10 text-accent'
                    : 'text-ink-muted hover:text-ink-secondary',
                )}
              >
                {p}
              </button>
            ))}
          </div>

          {/* Legend with current returns */}
          {assetData && (
            <div className="flex flex-wrap gap-5">
              {Object.entries(assetReturns)
                .sort(([, a], [, b]) => b - a)
                .map(([label, ret]) => (
                <div key={label} className="flex items-center gap-2">
                  <div className="h-2 w-5 rounded-full" style={{ backgroundColor: ASSET_COLORS[label] }} />
                  <span className="text-xs text-ink-secondary">{label}</span>
                  <span className={cn('font-mono text-xs font-semibold', ret >= 0 ? 'text-gain' : 'text-loss')}>
                    {ret >= 0 ? '+' : ''}{ret}%
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* Chart */}
          {loadingAssets ? (
            <div className="flex h-96 items-center justify-center">
              <Spinner size={28} />
            </div>
          ) : assetChartData.length > 0 ? (
            <div className="rounded-md border border-border bg-bg-surface p-5 shadow-card">
              <ResponsiveContainer width="100%" height={380}>
                <LineChart data={assetChartData} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="date"
                    tickFormatter={d => {
                      const dt = new Date(d)
                      return dt.toLocaleDateString('en-IN', { month: 'short', year: '2-digit' })
                    }}
                    interval="preserveStartEnd"
                    minTickGap={60}
                  />
                  <YAxis
                    tickFormatter={v => `${v}`}
                    domain={['auto', 'auto']}
                    width={48}
                  />
                  <Tooltip
                    formatter={(v: number, name: string) => [`${v.toFixed(1)}`, name]}
                    labelFormatter={l => new Date(l).toLocaleDateString('en-IN', {
                      day: 'numeric', month: 'short', year: 'numeric',
                    })}
                    contentStyle={{ backgroundColor: '#161B22', border: '1px solid #21262D', borderRadius: 5 }}
                    labelStyle={{ color: '#8B949E', fontSize: 11 }}
                    itemStyle={{ color: '#E6EDF3', fontSize: 11 }}
                  />
                  {Object.keys(ASSET_COLORS).map(label => (
                    <Line
                      key={label}
                      type="monotone"
                      dataKey={label}
                      stroke={ASSET_COLORS[label]}
                      strokeWidth={1.5}
                      dot={false}
                      connectNulls
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
              <p className="mt-2 text-center text-2xs text-ink-disabled">
                All assets normalized to 100 at period start - shows relative performance, not absolute price
              </p>
            </div>
          ) : !loadingAssets && (
            <div className="flex h-48 items-center justify-center text-sm text-ink-muted">
              Failed to load asset data. Check backend connection.
            </div>
          )}
        </div>
      )}

      {/* Stock chart panel (available across all views) */}
      {selectedStock && (
        <StockChartPanel stock={selectedStock} onClose={() => setSelectedStock(null)} />
      )}
    </div>
  )
}
