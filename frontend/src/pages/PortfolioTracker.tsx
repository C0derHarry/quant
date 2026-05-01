import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Trash2, TrendingUp, TrendingDown, BarChart2, Minus, ExternalLink } from 'lucide-react'
import {
  listPortfolios, deletePortfolio, getTrackerData, getPortfolioNews,
  type SavedPortfolio, type TrackerResult, type NewsArticle,
  type PortfolioNewsTickerSentiment,
} from '../lib/api'
import Spinner, { ErrorState } from '../components/ui/Spinner'
import MetricCard from '../components/ui/MetricCard'
import { cn, fmtPct, fmt } from '../lib/utils'
import {
  ResponsiveContainer, ComposedChart, Area, XAxis, YAxis,
  CartesianGrid, Tooltip, Legend,
} from 'recharts'

// ── Portfolio news sub-components ─────────────────────────────────────────────

function ptTimeAgo(pub: string): string {
  const diff = Date.now() - new Date(pub).getTime()
  const mins = Math.floor(diff / 60_000)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

function TickerSentimentChip({ ts }: { ts: PortfolioNewsTickerSentiment }) {
  const isBull = ts.label.includes('Bullish')
  const isBear = ts.label.includes('Bearish')
  return (
    <div className={cn(
      'flex items-center gap-1.5 rounded border px-2 py-1',
      isBull ? 'border-gain/30 bg-gain/5'
             : isBear ? 'border-loss/30 bg-loss/5'
                      : 'border-border bg-bg-elevated',
    )}>
      <span className="font-mono text-xs font-semibold text-ink-primary">{ts.ticker}</span>
      {isBull
        ? <TrendingUp  size={10} className="text-gain" />
        : isBear
        ? <TrendingDown size={10} className="text-loss" />
        : <Minus size={10} className="text-ink-disabled" />}
      <span className={cn(
        'text-2xs font-medium',
        isBull ? 'text-gain' : isBear ? 'text-loss' : 'text-ink-disabled',
      )}>{ts.label}</span>
    </div>
  )
}

function PortfolioNewsCard({ article }: { article: NewsArticle }) {
  const isBull     = article.sentiment_label.includes('Bullish')
  const isBear     = article.sentiment_label.includes('Bearish')
  const borderColor = isBull ? '#3FB950' : isBear ? '#F85149' : '#21262D'
  return (
    <div
      className="flex flex-col gap-2 rounded-md border border-border bg-bg-elevated p-3"
      style={{ borderLeftColor: borderColor, borderLeftWidth: '2px' }}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="truncate text-2xs font-semibold uppercase tracking-wide text-ink-disabled">
          {article.source}
        </span>
        <span className="shrink-0 text-2xs text-ink-disabled">{ptTimeAgo(article.published_at)}</span>
      </div>
      <p className="line-clamp-2 text-xs font-medium leading-snug text-ink-primary">
        {article.title}
      </p>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap gap-1">
          {article.tickers.slice(0, 3).map(t => (
            <span key={t.ticker} className={cn(
              'rounded px-1.5 py-0.5 font-mono text-2xs font-medium',
              t.sentiment_label.includes('Bullish') ? 'bg-gain/10 text-gain'
                : t.sentiment_label.includes('Bearish') ? 'bg-loss/10 text-loss'
                : 'bg-bg-overlay text-ink-secondary',
            )}>
              {t.ticker}
            </span>
          ))}
        </div>
        <a
          href={article.url}
          target="_blank"
          rel="noopener noreferrer"
          onClick={e => e.stopPropagation()}
          className="flex items-center gap-1 text-2xs text-ink-disabled hover:text-accent"
        >
          Read <ExternalLink size={9} />
        </a>
      </div>
    </div>
  )
}

function PortfolioNewsSection({ tickers }: { tickers: string[] }) {
  const { data, isLoading, error } = useQuery({
    queryKey:  ['portfolio-news', tickers.slice().sort().join(',')],
    queryFn:   () => getPortfolioNews(tickers, 10),
    staleTime: 15 * 60_000,
    enabled:   tickers.length > 0,
  })

  return (
    <div className="rounded-lg border border-border bg-bg-surface">
      <p className="border-b border-border px-4 py-3 text-xs font-semibold uppercase tracking-widest text-ink-disabled">
        Portfolio News
      </p>
      <div className="space-y-3 p-4">
        {isLoading && (
          <div className="flex items-center justify-center py-6">
            <Spinner size={18} />
          </div>
        )}
        {error && (
          <p className="text-xs text-loss">{(error as Error).message}</p>
        )}
        {data && !isLoading && (
          <>
            {data.ticker_sentiment.filter(ts => ts.article_count > 0).length > 0 && (
              <div className="flex flex-wrap gap-2 pb-1">
                {data.ticker_sentiment
                  .filter(ts => ts.article_count > 0)
                  .map(ts => <TickerSentimentChip key={ts.ticker} ts={ts} />)}
              </div>
            )}
            {data.articles.length === 0 ? (
              <p className="py-4 text-center text-xs text-ink-disabled">
                No recent news found for this portfolio.
              </p>
            ) : (
              <div className="space-y-2">
                {data.articles.map(a => <PortfolioNewsCard key={a.id} article={a} />)}
              </div>
            )}
            {data.cached && (
              <p className="text-2xs text-ink-disabled">
                Cached results — refreshes hourly to preserve API quota
              </p>
            )}
          </>
        )}
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────

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
    <div className="flex h-[calc(100vh-104px)] gap-5 overflow-hidden">

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

      {/* Portfolio News */}
      <PortfolioNewsSection tickers={t.tickers} />
    </>
  )
}
