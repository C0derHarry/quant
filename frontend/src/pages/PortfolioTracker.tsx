import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Trash2, TrendingUp, TrendingDown, BarChart2 } from 'lucide-react'
import {
  listPortfolios, deletePortfolio, getTrackerData,
  type SavedPortfolio, type TrackerResult,
} from '../lib/api'
import Spinner, { ErrorState } from '../components/ui/Spinner'
import MetricCard from '../components/ui/MetricCard'
import { cn, fmtPct, fmt } from '../lib/utils'
import {
  ResponsiveContainer, ComposedChart, Area, XAxis, YAxis,
  CartesianGrid, Tooltip, Legend,
} from 'recharts'

export default function PortfolioTracker() {
  const qc = useQueryClient()
  const [selected, setSelected] = useState<string | null>(null)

  const { data: portfolios, isLoading: listLoading, error: listError } =
    useQuery({ queryKey: ['savedPortfolios'], queryFn: listPortfolios })

  const { data: tracker, isLoading: trackLoading, error: trackError } =
    useQuery({
      queryKey:  ['tracker', selected],
      queryFn:   () => getTrackerData(selected!),
      enabled:   !!selected,
      staleTime: 5 * 60_000,
    })

  const delMut = useMutation({
    mutationFn: deletePortfolio,
    onSuccess:  () => {
      qc.invalidateQueries({ queryKey: ['savedPortfolios'] })
      setSelected(null)
    },
  })

  if (listLoading) return (
    <div className="flex flex-1 items-center justify-center">
      <Spinner size={28} />
    </div>
  )
  if (listError) return <ErrorState message={(listError as Error).message} />

  const list = portfolios ?? []

  return (
    <div className="flex h-full gap-5 overflow-hidden p-5">

      {/* ── Left: portfolio list ── */}
      <div className="flex w-[260px] shrink-0 flex-col gap-3">
        <h2 className="text-xs font-semibold uppercase tracking-widest text-ink-disabled">
          Saved Portfolios
        </h2>

        {list.length === 0 ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-border py-12 text-center">
            <BarChart2 size={28} className="text-ink-disabled" />
            <p className="text-xs text-ink-muted">No saved portfolios yet.</p>
            <p className="text-xs text-ink-disabled">Build one in the Portfolio tab.</p>
          </div>
        ) : (
          <div className="space-y-2 overflow-y-auto">
            {list.map(p => (
              <PortfolioCard
                key={p.id}
                portfolio={p}
                active={selected === p.id}
                onSelect={() => setSelected(p.id)}
                onDelete={() => delMut.mutate(p.id)}
              />
            ))}
          </div>
        )}
      </div>

      {/* ── Right: tracker detail ── */}
      <div className="flex flex-1 flex-col gap-4 overflow-y-auto">
        {!selected ? (
          <div className="flex flex-1 items-center justify-center">
            <p className="text-sm text-ink-muted">Select a portfolio to view performance</p>
          </div>
        ) : trackLoading ? (
          <div className="flex flex-1 items-center justify-center">
            <Spinner size={28} />
          </div>
        ) : trackError ? (
          <ErrorState message={(trackError as Error).message} />
        ) : tracker ? (
          <TrackerDetail tracker={tracker} />
        ) : null}
      </div>
    </div>
  )
}

// ── Portfolio card ─────────────────────────────────────────────────────────

function PortfolioCard({ portfolio: p, active, onSelect, onDelete }: {
  portfolio: SavedPortfolio
  active:    boolean
  onSelect:  () => void
  onDelete:  () => void
}) {
  const date = new Date(p.invested_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
  return (
    <div
      onClick={onSelect}
      className={cn(
        'group relative cursor-pointer rounded-lg border p-3.5 transition-all',
        active
          ? 'border-accent bg-[rgba(56,139,253,.08)]'
          : 'border-border bg-bg-surface hover:border-border/80 hover:bg-bg-elevated',
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-ink-primary">{p.name}</p>
          <p className="mt-0.5 text-xs text-ink-disabled">Invested {date}</p>
        </div>
        <button
          onClick={e => { e.stopPropagation(); onDelete() }}
          className="shrink-0 text-ink-disabled opacity-0 transition-opacity group-hover:opacity-100 hover:text-loss"
        >
          <Trash2 size={13} />
        </button>
      </div>
      <div className="mt-2 flex flex-wrap gap-1">
        {p.tickers.slice(0, 4).map(t => (
          <span key={t} className="rounded bg-bg-overlay px-1.5 py-0.5 font-mono text-2xs text-ink-muted">
            {t.replace('.NS', '').replace('.BO', '')}
          </span>
        ))}
        {p.tickers.length > 4 && (
          <span className="rounded bg-bg-overlay px-1.5 py-0.5 font-mono text-2xs text-ink-disabled">
            +{p.tickers.length - 4}
          </span>
        )}
      </div>
    </div>
  )
}

// ── Tracker detail ─────────────────────────────────────────────────────────

function TrackerDetail({ tracker: t }: { tracker: TrackerResult }) {
  const m    = t.metrics
  const up   = m.total_return >= 0
  const date = new Date(t.invested_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })

  return (
    <>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-ink-primary">{t.portfolio_name}</h2>
          <p className="text-xs text-ink-muted">Invested since {date} · {m.days_held} days</p>
        </div>
        <div className={cn('flex items-center gap-1.5 font-mono text-2xl font-semibold',
          up ? 'text-gain' : 'text-loss')}>
          {up ? <TrendingUp size={20} /> : <TrendingDown size={20} />}
          {up ? '+' : ''}{m.total_return.toFixed(2)}%
        </div>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-5 gap-3">
        <MetricCard size="sm" label="Total Return"
          value={`${m.total_return >= 0 ? '+' : ''}${fmtPct(m.total_return)}`}
          accent={up ? 'gain' : 'loss'}
          tooltip="Cumulative portfolio return since investment date." />
        <MetricCard size="sm" label="CAGR"
          value={fmtPct(m.cagr)}
          accent={m.cagr >= 0 ? 'gain' : 'loss'}
          tooltip="Annualised compound growth rate." />
        <MetricCard size="sm" label="Annual Vol"
          value={fmtPct(m.annual_vol)}
          tooltip="Annualised standard deviation of daily returns." />
        <MetricCard size="sm" label="Sharpe"
          value={fmt(m.sharpe)}
          tooltip="Risk-adjusted return (CAGR / annual volatility)." />
        <MetricCard size="sm" label="Max Drawdown"
          value={fmtPct(m.max_drawdown)}
          accent="loss"
          tooltip="Largest peak-to-trough decline since investment." />
      </div>

      {/* Chart */}
      <div className="rounded-lg border border-border bg-bg-surface p-4">
        <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-ink-disabled">
          Portfolio vs NIFTY 50
        </p>
        <ResponsiveContainer width="100%" height={240}>
          <ComposedChart data={t.series} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="portGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor="#388BFD" stopOpacity={0.2} />
                <stop offset="95%" stopColor="#388BFD" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,.04)" />
            <XAxis dataKey="date"
              tick={{ fill: '#7D8590', fontSize: 10 }} tickLine={false} axisLine={false}
              interval="preserveStartEnd" />
            <YAxis
              tick={{ fill: '#7D8590', fontSize: 10 }} tickLine={false} axisLine={false}
              width={52} tickFormatter={v => `${((v - 1) * 100).toFixed(0)}%`} />
            <Tooltip
              formatter={(v: number, name: string) =>
                [`${((v - 1) * 100).toFixed(2)}%`, name === 'portfolio' ? 'Portfolio' : 'NIFTY 50']}
              contentStyle={{ background: '#1c2128', border: '1px solid #30363d', borderRadius: 6, fontSize: 12 }}
              labelStyle={{ color: '#7D8590' }}
            />
            <Legend formatter={v => v === 'portfolio' ? 'Portfolio' : 'NIFTY 50'} />
            <Area type="monotone" dataKey="portfolio"
              stroke="#388BFD" strokeWidth={1.8}
              fill="url(#portGrad)" dot={false} />
            <Area type="monotone" dataKey="benchmark"
              stroke="#7D8590" strokeWidth={1.2} strokeDasharray="4 3"
              fill="none" dot={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Per-ticker breakdown */}
      <div className="rounded-lg border border-border bg-bg-surface">
        <p className="border-b border-border px-4 py-3 text-xs font-semibold uppercase tracking-widest text-ink-disabled">
          Stock Breakdown
        </p>
        <div className="divide-y divide-border">
          {t.ticker_performance.map(tp => (
            <div key={tp.ticker} className="flex items-center justify-between px-4 py-3">
              <div className="flex items-center gap-3">
                <span className="font-mono text-sm font-semibold text-ink-primary">
                  {tp.ticker.replace('.NS', '').replace('.BO', '')}
                </span>
                <span className="text-xs text-ink-disabled">{tp.weight.toFixed(1)}% weight</span>
              </div>
              <span className={cn('num font-mono text-sm font-semibold',
                tp.return >= 0 ? 'text-gain' : 'text-loss')}>
                {tp.return >= 0 ? '+' : ''}{tp.return.toFixed(2)}%
              </span>
            </div>
          ))}
        </div>
      </div>
    </>
  )
}
