import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Activity, TrendingUp, TrendingDown, Minus } from 'lucide-react'
import { cn } from '../lib/utils'
import { getTechnicalAnalysis, type TechnicalIndicator, type TechnicalSummary } from '../lib/api'
import { PageLoader, ErrorState } from '../components/ui/Spinner'
import StockSearchInput from '../components/ui/StockSearchInput'

// ── constants ─────────────────────────────────────────────────────

const PERIODS = ['6mo', '1y', '2y'] as const
type Period = typeof PERIODS[number]

const VERDICT_CONFIG: Record<string, { bg: string; border: string; text: string; label: string }> = {
  'STRONG BUY':  { bg: 'bg-gain/15',      border: 'border-gain/40',  text: 'text-gain',           label: 'STRONG BUY'  },
  'BUY':         { bg: 'bg-gain/8',       border: 'border-gain/25',  text: 'text-gain',           label: 'BUY'         },
  'NEUTRAL':     { bg: 'bg-bg-elevated',  border: 'border-border',   text: 'text-ink-secondary',  label: 'NEUTRAL'     },
  'SELL':        { bg: 'bg-loss/8',       border: 'border-loss/25',  text: 'text-loss',           label: 'SELL'        },
  'STRONG SELL': { bg: 'bg-loss/15',      border: 'border-loss/40',  text: 'text-loss',           label: 'STRONG SELL' },
}

const CATEGORY_ORDER = ['Trend', 'Trend Strength', 'Momentum', 'Volume', 'Volatility']

// ── sub-components ────────────────────────────────────────────────

function VerdictBanner({ summary, ticker }: { summary: TechnicalSummary; ticker: string }) {
  const cfg   = VERDICT_CONFIG[summary.verdict] ?? VERDICT_CONFIG['NEUTRAL']
  const total = summary.bullish + summary.bearish + summary.neutral
  const bullPct = total > 0 ? (summary.bullish / total) * 100 : 0
  const bearPct = total > 0 ? (summary.bearish / total) * 100 : 0
  const neutPct = 100 - bullPct - bearPct

  return (
    <div className={cn('rounded-lg border p-5', cfg.bg, cfg.border)}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-ink-disabled">
            {ticker} — Technical Verdict
          </p>
          <p className={cn('text-3xl font-bold tracking-tight', cfg.text)}>
            {cfg.label}
          </p>
          <div className="mt-2 flex items-center gap-3 text-sm">
            <span className="flex items-center gap-1 text-gain">
              <TrendingUp size={13} />
              {summary.bullish} bullish
            </span>
            <span className="text-ink-disabled">·</span>
            <span className="flex items-center gap-1 text-loss">
              <TrendingDown size={13} />
              {summary.bearish} bearish
            </span>
            {summary.neutral > 0 && (
              <>
                <span className="text-ink-disabled">·</span>
                <span className="flex items-center gap-1 text-ink-muted">
                  <Minus size={13} />
                  {summary.neutral} neutral
                </span>
              </>
            )}
          </div>
        </div>

        <div className="min-w-[200px] flex-1 max-w-xs">
          <p className="mb-1.5 text-right text-xs text-ink-muted">
            {summary.bullish}/{summary.bullish + summary.bearish} decisive indicators bullish
          </p>
          <div className="flex h-2.5 overflow-hidden rounded-full bg-bg-overlay">
            <div
              className="h-full bg-gain transition-all duration-700"
              style={{ width: `${bullPct}%` }}
            />
            <div
              className="h-full bg-bg-elevated transition-all duration-700"
              style={{ width: `${neutPct}%` }}
            />
            <div
              className="h-full bg-loss transition-all duration-700"
              style={{ width: `${bearPct}%` }}
            />
          </div>
          <div className="mt-1 flex justify-between text-2xs text-ink-disabled">
            <span>Bull</span>
            <span>Bear</span>
          </div>
        </div>
      </div>
    </div>
  )
}

function IndicatorCard({ indicator }: { indicator: TechnicalIndicator }) {
  const isBull = indicator.signal === 'Bullish'
  const isBear = indicator.signal === 'Bearish'

  return (
    <div
      className={cn(
        'rounded-md border bg-bg-surface p-3.5 transition-all',
        isBull ? 'border-gain/30' : isBear ? 'border-loss/30' : 'border-border',
      )}
      style={{
        borderLeftWidth: '3px',
        borderLeftColor: isBull ? '#3FB950' : isBear ? '#F85149' : '#484F58',
      }}
    >
      <div className="mb-2 flex items-start justify-between gap-2">
        <div>
          <p className="text-xs font-semibold text-ink-primary">{indicator.name}</p>
          <span className="text-2xs text-ink-disabled">{indicator.category}</span>
        </div>
        <div className={cn(
          'flex shrink-0 items-center gap-1 rounded px-1.5 py-0.5 text-2xs font-semibold',
          isBull ? 'bg-gain/10 text-gain' : isBear ? 'bg-loss/10 text-loss' : 'bg-bg-elevated text-ink-muted',
        )}>
          {isBull ? <TrendingUp size={9} /> : isBear ? <TrendingDown size={9} /> : <Minus size={9} />}
          {indicator.signal}
        </div>
      </div>
      <p className="font-mono text-xs font-medium text-ink-secondary">{indicator.value}</p>
      <p className="mt-1 text-xs leading-relaxed text-ink-muted">{indicator.description}</p>
    </div>
  )
}

function IndicatorTable({ indicators }: { indicators: TechnicalIndicator[] }) {
  const sorted = [...indicators].sort(
    (a, b) => CATEGORY_ORDER.indexOf(a.category) - CATEGORY_ORDER.indexOf(b.category)
  )

  return (
    <div className="rounded-lg border border-border bg-bg-surface overflow-hidden">
      <div className="border-b border-border px-4 py-3">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-ink-secondary">
          All Indicators
        </h3>
      </div>
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-border/50 bg-bg-elevated/50">
            <th className="px-4 py-2 text-left font-medium text-ink-disabled">Indicator</th>
            <th className="px-4 py-2 text-left font-medium text-ink-disabled">Category</th>
            <th className="px-4 py-2 text-left font-medium text-ink-disabled">Value</th>
            <th className="px-4 py-2 text-left font-medium text-ink-disabled">Signal</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((ind, i) => {
            const isBull = ind.signal === 'Bullish'
            const isBear = ind.signal === 'Bearish'
            return (
              <tr key={ind.name} className={cn(
                'border-b border-border/30 last:border-0',
                i % 2 === 0 ? 'bg-transparent' : 'bg-bg-elevated/30',
              )}>
                <td className="px-4 py-2.5 font-medium text-ink-primary">{ind.name}</td>
                <td className="px-4 py-2.5 text-ink-muted">{ind.category}</td>
                <td className="px-4 py-2.5 font-mono text-ink-secondary">{ind.value}</td>
                <td className="px-4 py-2.5">
                  <span className={cn(
                    'inline-flex items-center gap-1 rounded px-1.5 py-0.5 font-semibold',
                    isBull ? 'bg-gain/10 text-gain' : isBear ? 'bg-loss/10 text-loss' : 'bg-bg-overlay text-ink-muted',
                  )}>
                    {isBull ? <TrendingUp size={9} /> : isBear ? <TrendingDown size={9} /> : <Minus size={9} />}
                    {ind.signal}
                  </span>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

// ── main page ─────────────────────────────────────────────────────

export default function TechnicalAnalysis() {
  const [ticker, setTicker] = useState('')
  const [period, setPeriod] = useState<Period>('1y')

  const { data, isLoading, error } = useQuery({
    queryKey:  ['technical', ticker, period],
    queryFn:   () => getTechnicalAnalysis(`${ticker}.NS`, period),
    enabled:   !!ticker,
    staleTime: 15 * 60_000,
  })

  const bullish = data?.indicators.filter(i => i.signal === 'Bullish') ?? []
  const bearish = data?.indicators.filter(i => i.signal === 'Bearish') ?? []
  const neutral = data?.indicators.filter(i => i.signal === 'Neutral') ?? []

  return (
    <div className="animate-fade-up space-y-6">
      {/* header */}
      <div className="flex items-start gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-border bg-bg-elevated">
          <Activity size={16} className="text-accent" />
        </div>
        <div>
          <h1 className="text-xl font-semibold text-ink-primary">Technical Analysis</h1>
          <p className="mt-0.5 text-sm text-ink-muted">
            12 curated indicators · Classical rules · BUY / SELL verdict
          </p>
        </div>
      </div>

      {/* controls */}
      <div className="flex flex-wrap items-center gap-3">
        <StockSearchInput
          selected={ticker}
          onSelect={setTicker}
          onClear={() => setTicker('')}
          placeholder="Search NSE stock (e.g. TCS, Reliance…)"
        />

        {/* period toggle */}
        <div className="flex rounded-md border border-border bg-bg-elevated p-0.5">
          {PERIODS.map(p => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={cn(
                'rounded px-3 py-1.5 text-xs font-medium transition-all',
                period === p
                  ? 'bg-accent/10 text-accent'
                  : 'text-ink-muted hover:text-ink-secondary',
              )}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {/* states */}
      {!ticker && (
        <div className="flex flex-col items-center justify-center py-24 text-center">
          <Activity size={32} className="mb-3 text-ink-disabled" />
          <p className="text-sm font-medium text-ink-secondary">Select a stock to run analysis</p>
          <p className="mt-1 text-xs text-ink-muted">
            12 technical indicators evaluated in real-time
          </p>
        </div>
      )}

      {ticker && isLoading && <PageLoader label={`Running technical analysis for ${ticker}…`} />}
      {ticker && error    && <ErrorState message={(error as Error).message} />}

      {/* results */}
      {data && (
        <div className="space-y-6">
          <VerdictBanner summary={data.summary} ticker={ticker} />

          {/* bullish / bearish columns */}
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {/* bullish */}
            <div className="space-y-3">
              <h2 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-gain">
                <TrendingUp size={13} />
                Bullish Signals ({bullish.length})
              </h2>
              {bullish.length > 0 ? (
                bullish.map(ind => <IndicatorCard key={ind.name} indicator={ind} />)
              ) : (
                <p className="text-xs text-ink-disabled">No bullish signals.</p>
              )}
            </div>

            {/* bearish */}
            <div className="space-y-3">
              <h2 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-loss">
                <TrendingDown size={13} />
                Bearish Signals ({bearish.length})
              </h2>
              {bearish.length > 0 ? (
                bearish.map(ind => <IndicatorCard key={ind.name} indicator={ind} />)
              ) : (
                <p className="text-xs text-ink-disabled">No bearish signals.</p>
              )}
            </div>
          </div>

          {/* neutral pills */}
          {neutral.length > 0 && (
            <div>
              <h2 className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-ink-disabled">
                <Minus size={13} />
                Neutral / Inconclusive ({neutral.length})
              </h2>
              <div className="flex flex-wrap gap-2">
                {neutral.map(ind => (
                  <div
                    key={ind.name}
                    className="rounded border border-border bg-bg-elevated px-3 py-1.5"
                    title={ind.description}
                  >
                    <span className="text-xs font-medium text-ink-muted">{ind.name}</span>
                    <span className="ml-2 font-mono text-2xs text-ink-disabled">{ind.value}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* full table */}
          <IndicatorTable indicators={data.indicators} />
        </div>
      )}
    </div>
  )
}
