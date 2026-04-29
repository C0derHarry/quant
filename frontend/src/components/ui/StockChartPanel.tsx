import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { getOHLCV, type SectorStock } from '../../lib/api'
import Spinner from './Spinner'
import { X, ExternalLink, TrendingUp, TrendingDown } from 'lucide-react'
import { cn } from '../../lib/utils'
import {
  ResponsiveContainer, AreaChart, Area,
  XAxis, YAxis, CartesianGrid, Tooltip,
} from 'recharts'

type ChartPeriod = '1D' | '5D' | '1M' | '3M' | '6M' | '1Y'

const PERIODS: ChartPeriod[] = ['1D', '5D', '1M', '3M', '6M', '1Y']

const PERIOD_CONFIG: Record<ChartPeriod, { period: string; interval: string }> = {
  '1D': { period: '5d',  interval: '5m'  },
  '5D': { period: '5d',  interval: '60m' },
  '1M': { period: '1mo', interval: '1d'  },
  '3M': { period: '3mo', interval: '1d'  },
  '6M': { period: '6mo', interval: '1d'  },
  '1Y': { period: '1y',  interval: '1d'  },
}

function formatLabel(dateStr: string, period: ChartPeriod): string {
  const d = new Date(dateStr)
  if (period === '1D' || period === '5D') {
    return d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false })
  }
  return d.toLocaleDateString('en-IN', { month: 'short', day: 'numeric' })
}

function PriceTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded border border-border bg-bg-elevated p-2.5 shadow-lg">
      <p className="mb-1 text-xs text-ink-muted">{label}</p>
      <p className="num font-mono text-sm font-semibold text-ink-primary">
        ₹{Number(payload[0]?.value).toLocaleString('en-IN', { maximumFractionDigits: 2 })}
      </p>
    </div>
  )
}

interface Props {
  stock: SectorStock
  onClose: () => void
}

export default function StockChartPanel({ stock, onClose }: Props) {
  const navigate = useNavigate()
  const [period, setPeriod] = useState<ChartPeriod>('1D')
  const config = PERIOD_CONFIG[period]

  const { data: ohlcvRaw, isLoading } = useQuery({
    queryKey: ['stockChart', stock.symbol, period],
    queryFn:  () => getOHLCV({
      symbols:  [stock.symbol],
      period:   config.period,
      interval: config.interval,
      window:   1,
    }),
    staleTime: 60_000,
  })

  const chartData = useMemo(() => {
    const rows = ohlcvRaw?.[stock.symbol] ?? []
    if (period === '1D') {
      // find the last trading date and filter to only that day's bars
      if (rows.length === 0) return []
      const lastDate = rows[rows.length - 1].date.slice(0, 10)
      const dayRows = rows.filter(r => r.date.startsWith(lastDate))
      return dayRows.map(r => ({ t: formatLabel(r.date, period), close: r.close }))
    }
    return rows.map(r => ({ t: formatLabel(r.date, period), close: r.close }))
  }, [ohlcvRaw, stock.symbol, period])

  // displayPrice is always stock.price (live market value) so it never flashes
  // or shifts when switching periods. Change is computed from chartData[0] → stock.price
  // so the delta correctly reflects the selected period window.
  const { displayChange, displayPct, displayPrice } = useMemo(() => {
    const last = stock.price
    if (chartData.length === 0) {
      return { displayChange: stock.change, displayPct: stock.pct_change, displayPrice: last }
    }
    const first  = chartData[0].close
    const change = last - first
    const pct    = first !== 0 ? (change / first) * 100 : 0
    return { displayChange: change, displayPct: pct, displayPrice: last }
  }, [chartData, stock])

  const up    = displayPct >= 0
  const color = up ? '#3FB950' : '#F85149'
  const gradId = `grad-${stock.symbol}`

  const xInterval = (period === '1D' || period === '5D') ? 13 : 'preserveStartEnd'

  const rangeWidth =
    stock.year_high > stock.year_low
      ? Math.max(0, Math.min(100,
          (displayPrice - stock.year_low) / (stock.year_high - stock.year_low) * 100))
      : 50

  function goDeepDive() {
    navigate('/fundamentals', { state: { preselect: stock.symbol } })
    onClose()
  }

  return (
    /* Backdrop */
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-[2px] p-4"
      onClick={onClose}>

      {/* Modal - 16:9, max ~960×540 */}
      <div
        className="relative w-full max-w-[960px] rounded-lg border border-border bg-bg-surface shadow-2xl"
        style={{ aspectRatio: '16/9' }}
        onClick={e => e.stopPropagation()}
      >
        <div className="flex h-full">

          {/* ── Left column: metadata ── */}
          <div className="flex w-[260px] shrink-0 flex-col border-r border-border p-5">
            {/* Header */}
            <div className="flex items-start justify-between">
              <div>
                <p className="font-mono text-lg font-bold text-ink-primary">{stock.symbol}</p>
                <p className="mt-0.5 max-w-[200px] truncate text-xs text-ink-muted">{stock.name}</p>
              </div>
              <button onClick={onClose}
                className="text-ink-disabled transition-colors hover:text-ink-primary">
                <X size={16} />
              </button>
            </div>

            {/* Price */}
            <div className="mt-4">
              <p className="num font-mono text-3xl font-semibold text-ink-primary">
                ₹{displayPrice.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
              </p>
              <div className="mt-1.5 flex items-center gap-2">
                <span className={cn('num flex items-center gap-1 font-mono text-sm font-semibold',
                  up ? 'text-gain' : 'text-loss')}>
                  {up ? <TrendingUp size={13} /> : <TrendingDown size={13} />}
                  {up ? '+' : ''}{displayChange.toFixed(2)}
                </span>
                <span className={cn('num font-mono text-sm', up ? 'text-gain' : 'text-loss')}>
                  ({up ? '+' : ''}{displayPct.toFixed(2)}%)
                </span>
              </div>
              <p className="mt-1 text-2xs text-ink-disabled">{period} change</p>
            </div>

            {/* 52-week range */}
            {stock.year_high > stock.year_low && (
              <div className="mt-auto">
                <p className="mb-2 text-2xs font-semibold uppercase tracking-widest text-ink-disabled">
                  52-Week Range
                </p>
                <div className="flex items-center gap-2">
                  <span className="num shrink-0 font-mono text-xs text-loss">
                    ₹{stock.year_low.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                  </span>
                  <div className="relative h-1.5 flex-1 overflow-hidden rounded-full bg-bg-overlay">
                    <div className="absolute left-0 h-full rounded-full bg-accent"
                      style={{ width: `${rangeWidth}%` }} />
                  </div>
                  <span className="num shrink-0 font-mono text-xs text-gain">
                    ₹{stock.year_high.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                  </span>
                </div>
              </div>
            )}

            {/* Deep dive CTA */}
            <button onClick={goDeepDive}
              className="mt-4 flex w-full items-center justify-center gap-2 rounded border border-accent bg-accent py-2 text-sm font-semibold text-white transition-all hover:bg-accent/90">
              <ExternalLink size={13} /> Deep Dive
            </button>
          </div>

          {/* ── Right column: chart ── */}
          <div className="flex flex-1 flex-col overflow-hidden">
            {/* Period tabs */}
            <div className="flex border-b border-border px-4">
              {PERIODS.map(p => (
                <button key={p} onClick={() => setPeriod(p)}
                  className={cn(
                    'border-b-2 px-3 py-2.5 text-xs font-semibold transition-colors',
                    period === p
                      ? 'border-accent text-accent'
                      : 'border-transparent text-ink-muted hover:text-ink-primary',
                  )}>
                  {p}
                </button>
              ))}
            </div>

            {/* Chart area */}
            <div className="flex flex-1 flex-col overflow-hidden px-2 py-3">
              {isLoading ? (
                <div className="flex flex-1 items-center justify-center">
                  <Spinner size={24} />
                </div>
              ) : chartData.length === 0 ? (
                <div className="flex flex-1 items-center justify-center">
                  <p className="text-sm text-ink-disabled">No data for this period.</p>
                </div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={chartData} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%"  stopColor={color} stopOpacity={0.22} />
                        <stop offset="95%" stopColor={color} stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,.04)" />
                    <XAxis dataKey="t"
                      tick={{ fill: '#7D8590', fontSize: 10 }} tickLine={false} axisLine={false}
                      interval={xInterval as any} />
                    <YAxis
                      tick={{ fill: '#7D8590', fontSize: 10 }} tickLine={false} axisLine={false}
                      width={68} domain={['auto', 'auto']}
                      tickFormatter={v =>
                        `₹${Number(v).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`}
                    />
                    <Tooltip content={<PriceTooltip />} />
                    <Area type="monotone" dataKey="close"
                      stroke={color} strokeWidth={1.8}
                      fill={`url(#${gradId})`} dot={false} connectNulls />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
