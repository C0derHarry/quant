import { useState, useMemo } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getSectorStocks, getSectorQuotes } from '../lib/api'
import DataTable, { Column } from '../components/ui/DataTable'
import { PageLoader, ErrorState } from '../components/ui/Spinner'
import { fmtPct, fmtLargeNum } from '../lib/utils'
import { ArrowLeft, TrendingUp, TrendingDown } from 'lucide-react'
import { cn } from '../lib/utils'
import type { SectorStock } from '../lib/api'
import { isMarketOpen } from '../lib/utils'
import StockChartPanel from '../components/ui/StockChartPanel'

const REFRESH = isMarketOpen() ? 1_000 : 0

function PctCell({ pct }: { pct: number }) {
  return (
    <span className={cn('num font-mono font-semibold', pct >= 0 ? 'text-gain' : 'text-loss')}>
      {pct >= 0 && '+'}{pct.toFixed(2)}%
    </span>
  )
}

const COLS: Column<SectorStock>[] = [
  {
    key: 'symbol', header: 'Symbol',
    cell: r => <span className="font-mono text-sm font-semibold text-accent">{r.symbol}</span>,
    sort: r => r.symbol, width: '120px',
  },
  {
    key: 'name', header: 'Company',
    cell: r => <span className="text-ink-primary">{r.name}</span>,
  },
  {
    key: 'price', header: 'Price',
    cell: r => (
      <span className="num font-mono text-ink-primary">
        ₹{r.price.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
      </span>
    ),
    sort: r => r.price, align: 'right',
  },
  {
    key: 'change', header: 'Change',
    cell: r => (
      <span className={cn('num font-mono font-medium', r.change >= 0 ? 'text-gain' : 'text-loss')}>
        {r.change >= 0 ? '+' : ''}{r.change.toFixed(2)}
      </span>
    ),
    sort: r => r.change, align: 'right',
  },
  {
    key: 'pct_change', header: 'Change %',
    cell: r => <PctCell pct={r.pct_change} />,
    sort: r => r.pct_change, align: 'right',
  },
  {
    key: 'volume', header: 'Volume',
    cell: r => <span className="num font-mono text-ink-secondary">{fmtLargeNum(r.volume)}</span>,
    sort: r => r.volume, align: 'right',
  },
  {
    key: 'year_range', header: '52W Range',
    cell: r => (
      <span className="num font-mono text-xs text-ink-muted">
        {r.year_low.toFixed(0)} – {r.year_high.toFixed(0)}
      </span>
    ),
    align: 'right',
  },
]

export default function SectorDetail() {
  const { name } = useParams<{ name: string }>()
  const decoded  = decodeURIComponent(name ?? '')
  // Track only the symbol of the selected row; pick the live merged row by symbol
  // each render so the chart panel reflects every poll tick.
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null)

  // Static fields (symbol, company name, 52W range) — fetched once per session.
  const { data: stocks, isLoading, error } = useQuery({
    queryKey:  ['sector-stocks', decoded],
    queryFn:   () => getSectorStocks(decoded),
    staleTime: Infinity,
  })

  // Live price/change/volume — polled every second during market hours.
  const { data: quotes } = useQuery({
    queryKey:        ['sector-quotes', decoded],
    queryFn:         () => getSectorQuotes(decoded),
    refetchInterval: REFRESH,
    enabled:         !!stocks,
  })

  // Overlay live quotes onto the static rows; re-sort by live pct_change.
  const data = useMemo(() => {
    if (!stocks) return undefined
    const merged = stocks.map(s => {
      const q = quotes?.[s.symbol]
      return q ? { ...s, ...q } : s
    })
    return merged.sort((a, b) => b.pct_change - a.pct_change)
  }, [stocks, quotes])

  const gainers = (data ?? []).filter(s => s.pct_change > 0).length
  const losers  = (data ?? []).filter(s => s.pct_change < 0).length

  return (
    <div className="space-y-5 animate-fade-up">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2">
        <Link to="/" className="flex items-center gap-1.5 text-xs text-ink-muted hover:text-ink-secondary transition-colors">
          <ArrowLeft size={13} /> Market Overview
        </Link>
        <span className="text-ink-disabled">/</span>
        <span className="text-xs font-semibold text-ink-primary">{decoded}</span>
      </div>

      {/* Stats bar */}
      {data && (
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <TrendingUp size={14} className="text-gain" />
            <span className="num font-mono text-sm font-semibold text-gain">{gainers}</span>
            <span className="text-xs text-ink-muted">advancing</span>
          </div>
          <div className="flex items-center gap-2">
            <TrendingDown size={14} className="text-loss" />
            <span className="num font-mono text-sm font-semibold text-loss">{losers}</span>
            <span className="text-xs text-ink-muted">declining</span>
          </div>
          <span className="num ml-auto font-mono text-xs text-ink-muted">
            {data.length} constituents
          </span>
        </div>
      )}

      {isLoading && <PageLoader label={`Loading ${decoded}…`} />}
      {error && <ErrorState message={error.message} />}

      {data && (
        <DataTable
          columns={COLS}
          data={data}
          keyFn={r => r.symbol}
          onRowClick={r => setSelectedSymbol(r.symbol)}
        />
      )}

      {selectedSymbol && data && (() => {
        const live = data.find(r => r.symbol === selectedSymbol)
        if (!live) return null
        return (
          <StockChartPanel
            stock={live}
            onClose={() => setSelectedSymbol(null)}
          />
        )
      })()}
    </div>
  )
}
