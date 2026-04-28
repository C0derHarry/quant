import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ReferenceLine, ResponsiveContainer, Cell,
} from 'recharts'
import { CheckCircle, XCircle, Minus } from 'lucide-react'
import StockBrowser from '../components/ui/StockBrowser'
import MetricCard from '../components/ui/MetricCard'
import { PageLoader, ErrorState } from '../components/ui/Spinner'
import { getEarningsSurprise, type EarningsQuarter } from '../lib/api'
import { cn } from '../lib/utils'

// ── helpers ───────────────────────────────────────────────────────

function fmt(v: number | null, prefix = '') {
  if (v === null || v === undefined) return '-'
  return `${prefix}${v}`
}

function BeatBadge({ beat }: { beat: boolean | null }) {
  if (beat === null) return <span className="text-xs text-ink-disabled">-</span>
  return beat
    ? <span className="inline-flex items-center gap-1 text-xs font-semibold text-gain"><CheckCircle size={12} /> Beat</span>
    : <span className="inline-flex items-center gap-1 text-xs font-semibold text-loss"><XCircle size={12} /> Miss</span>
}

// ── custom tooltip ────────────────────────────────────────────────

function EarningsTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded border border-border bg-bg-elevated p-2.5 text-xs shadow-lg">
      <p className="mb-1.5 font-semibold text-ink-primary">{label}</p>
      {payload.map((p: any) => (
        <div key={p.name} className="flex items-center gap-2">
          <div className="h-1.5 w-3 rounded-full" style={{ backgroundColor: p.color }} />
          <span className="text-ink-muted">{p.name}:</span>
          <span className="font-mono font-semibold text-ink-primary">
            {typeof p.value === 'number' ? p.value.toFixed(2) : '-'}
          </span>
        </div>
      ))}
    </div>
  )
}

// ── chart ─────────────────────────────────────────────────────────

function EarningsChart({ quarters, hasEstimates }: { quarters: EarningsQuarter[]; hasEstimates: boolean }) {
  if (quarters.length === 0) return null

  const chartData = quarters.map(q => ({
    quarter:       q.quarter,
    actual:        q.actual_eps,
    estimate:      q.estimated_eps,
    surprise_pct:  q.surprise_pct,
    beat:          q.beat,
  }))

  return (
    <div className="rounded-md border border-border bg-bg-surface p-5 shadow-card">
      <p className="mb-4 text-2xs font-semibold uppercase tracking-[0.12em] text-ink-disabled">
        {hasEstimates ? 'EPS - Actual vs Estimate' : 'EPS Trend (Quarterly)'}
      </p>
      <ResponsiveContainer width="100%" height={280}>
        <ComposedChart data={chartData} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="quarter" tick={{ fontSize: 10 }} />
          <YAxis
            yAxisId="eps"
            tick={{ fontSize: 10 }}
            tickFormatter={v => v.toFixed(1)}
            label={{ value: 'EPS', angle: -90, position: 'insideLeft', style: { fontSize: 10, fill: '#6E7681' } }}
          />
          {hasEstimates && (
            <YAxis
              yAxisId="surp"
              orientation="right"
              tick={{ fontSize: 10 }}
              tickFormatter={v => `${v}%`}
            />
          )}
          <Tooltip content={<EarningsTooltip />} />
          <ReferenceLine yAxisId="eps" y={0} stroke="#30363D" strokeWidth={1} />

          {hasEstimates && (
            <Bar yAxisId="eps" dataKey="estimate" name="Estimate" fill="#484F58" radius={[2, 2, 0, 0]} maxBarSize={28} />
          )}

          <Bar yAxisId="eps" dataKey="actual" name="Actual EPS" radius={[2, 2, 0, 0]} maxBarSize={28}>
            {chartData.map((entry, i) => (
              <Cell
                key={i}
                fill={
                  entry.beat === null
                    ? '#388BFD'
                    : entry.beat
                      ? '#3FB950'
                      : '#F85149'
                }
              />
            ))}
          </Bar>

          {hasEstimates && (
            <Line
              yAxisId="surp"
              type="monotone"
              dataKey="surprise_pct"
              name="Surprise %"
              stroke="#D29922"
              strokeWidth={1.5}
              dot={{ r: 3, fill: '#D29922' }}
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>

      <div className="mt-3 flex flex-wrap gap-4 justify-center">
        {hasEstimates && (
          <div className="flex items-center gap-1.5">
            <div className="h-2 w-4 rounded bg-[#484F58]" />
            <span className="text-2xs text-ink-muted">Estimate</span>
          </div>
        )}
        <div className="flex items-center gap-1.5">
          <div className="h-2 w-4 rounded bg-gain" />
          <span className="text-2xs text-ink-muted">Beat</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="h-2 w-4 rounded bg-loss" />
          <span className="text-2xs text-ink-muted">Miss</span>
        </div>
        {!hasEstimates && (
          <div className="flex items-center gap-1.5">
            <div className="h-2 w-4 rounded bg-accent" />
            <span className="text-2xs text-ink-muted">Actual EPS</span>
          </div>
        )}
        {hasEstimates && (
          <div className="flex items-center gap-1.5">
            <div className="h-0.5 w-4 rounded bg-warn" />
            <span className="text-2xs text-ink-muted">Surprise %</span>
          </div>
        )}
      </div>
    </div>
  )
}

// ── quarter table ─────────────────────────────────────────────────

function QuarterTable({ quarters, hasEstimates }: { quarters: EarningsQuarter[]; hasEstimates: boolean }) {
  const reversed = [...quarters].reverse()
  return (
    <div className="overflow-hidden rounded-md border border-border bg-bg-surface shadow-card">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-border bg-bg-elevated">
            <th className="px-4 py-2.5 text-left font-semibold uppercase tracking-wider text-ink-disabled">Quarter</th>
            {hasEstimates && (
              <th className="px-4 py-2.5 text-right font-semibold uppercase tracking-wider text-ink-disabled">Estimate</th>
            )}
            <th className="px-4 py-2.5 text-right font-semibold uppercase tracking-wider text-ink-disabled">Actual EPS</th>
            {hasEstimates && (
              <th className="px-4 py-2.5 text-right font-semibold uppercase tracking-wider text-ink-disabled">Surprise</th>
            )}
            {hasEstimates && (
              <th className="px-4 py-2.5 text-center font-semibold uppercase tracking-wider text-ink-disabled">Result</th>
            )}
          </tr>
        </thead>
        <tbody>
          {reversed.map((q, i) => (
            <tr key={i} className="tbl-row border-b border-border/50 last:border-0">
              <td className="px-4 py-2.5 font-medium text-ink-primary">{q.quarter}</td>
              {hasEstimates && (
                <td className="px-4 py-2.5 text-right font-mono text-ink-secondary">
                  {fmt(q.estimated_eps)}
                </td>
              )}
              <td className={cn(
                'px-4 py-2.5 text-right font-mono font-semibold',
                q.beat === null ? 'text-accent' : q.beat ? 'text-gain' : 'text-loss',
              )}>
                {fmt(q.actual_eps)}
              </td>
              {hasEstimates && (
                <td className={cn(
                  'px-4 py-2.5 text-right font-mono',
                  q.surprise_pct === null ? 'text-ink-disabled'
                    : q.surprise_pct >= 0 ? 'text-gain' : 'text-loss',
                )}>
                  {q.surprise_pct !== null
                    ? `${q.surprise_pct >= 0 ? '+' : ''}${q.surprise_pct?.toFixed(2)}%`
                    : '-'}
                </td>
              )}
              {hasEstimates && (
                <td className="px-4 py-2.5 text-center">
                  <BeatBadge beat={q.beat} />
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ── main page ─────────────────────────────────────────────────────

export default function EarningsSurprise() {
  const [selected, setSelected] = useState<string[]>([])

  const ticker = selected[0] ?? null

  const { data, isLoading, error } = useQuery({
    queryKey: ['earnings', ticker],
    queryFn:  () => getEarningsSurprise(ticker!),
    enabled:  !!ticker,
    staleTime: 30 * 60_000,
  })

  function handleToggle(symbol: string) {
    setSelected(prev =>
      prev.includes(symbol) ? prev.filter(s => s !== symbol) : [symbol]
    )
  }

  const latestLabel = data?.latest_beat === null ? null
    : data?.latest_beat ? 'Beat' : 'Miss'

  const latestSurpColor = data?.latest_surprise_pct !== null && data?.latest_surprise_pct !== undefined
    ? (data.latest_surprise_pct >= 0 ? 'gain' : 'loss')
    : 'neutral'

  return (
    <div className="flex h-[calc(100vh-104px)] gap-5 animate-fade-up">
      {/* Left: stock selector */}
      <StockBrowser
        selected={selected}
        onToggle={handleToggle}
        maxSelected={1}
        className="w-[300px] shrink-0"
      />

      {/* Right: content */}
      <div className="flex-1 overflow-y-auto space-y-5 pr-1">
        {!ticker && (
          <div className="flex h-full items-center justify-center">
            <div className="text-center">
              <p className="text-sm font-medium text-ink-secondary">Select a stock to view earnings history</p>
              <p className="mt-1 text-xs text-ink-muted">Best results with large-cap NSE stocks (INFY, RELIANCE, TCS)</p>
            </div>
          </div>
        )}

        {ticker && isLoading && <PageLoader label={`Loading earnings for ${ticker}...`} />}
        {ticker && error    && <ErrorState message={(error as Error).message} />}

        {ticker && data && data.quarters.length === 0 && (
          <div className="flex h-48 items-center justify-center rounded-md border border-border bg-bg-surface">
            <div className="text-center">
              <p className="text-sm font-medium text-ink-secondary">No earnings data found for {ticker}</p>
              <p className="mt-1 text-xs text-ink-muted">Try a major NSE stock like INFY, TCS, or RELIANCE</p>
            </div>
          </div>
        )}

        {ticker && data && data.quarters.length > 0 && (
          <>
            {/* Summary cards */}
            <div className="grid grid-cols-3 gap-4">
              <MetricCard
                label="Latest Result"
                value={latestLabel ?? '-'}
                sub={data.latest_surprise_pct !== null
                  ? `${data.latest_surprise_pct >= 0 ? '+' : ''}${data.latest_surprise_pct?.toFixed(2)}% surprise`
                  : 'No estimate data'}
                accent={data.latest_beat === true ? 'gain' : data.latest_beat === false ? 'loss' : 'neutral'}
                tooltip="Whether the company beat or missed analyst EPS estimates in the most recent reported quarter."
              />
              <MetricCard
                label="Historical Beat Rate"
                value={data.beat_rate !== null ? `${data.beat_rate}%` : '-'}
                sub={`of last ${data.quarters.filter(q => q.beat !== null).length} quarters with estimates`}
                accent={
                  data.beat_rate === null ? 'neutral'
                    : data.beat_rate >= 70 ? 'gain'
                    : data.beat_rate >= 50 ? 'warn'
                    : 'loss'
                }
                tooltip="Percentage of quarters where the company's reported EPS exceeded analyst consensus estimates. Above 70% is considered strong."
              />
              <MetricCard
                label="Avg Surprise"
                value={data.avg_surprise_pct !== null ? `${data.avg_surprise_pct >= 0 ? '+' : ''}${data.avg_surprise_pct}%` : '-'}
                sub="mean EPS surprise over tracked quarters"
                accent={
                  data.avg_surprise_pct === null ? 'neutral'
                    : data.avg_surprise_pct >= 5 ? 'gain'
                    : data.avg_surprise_pct >= 0 ? 'warn'
                    : 'loss'
                }
                tooltip="Average percentage by which the company beat or missed analyst estimates. Consistently positive means the company tends to under-promise and over-deliver."
              />
            </div>

            {!data.has_estimates && (
              <div className="flex items-center gap-2 rounded-md border border-warn/30 bg-warn/5 px-4 py-2.5 text-xs text-warn">
                <Minus size={13} />
                Analyst estimate data not available for this ticker - showing actual EPS trend only
              </div>
            )}

            {/* Chart */}
            <EarningsChart quarters={data.quarters} hasEstimates={data.has_estimates} />

            {/* Table */}
            <QuarterTable quarters={data.quarters} hasEstimates={data.has_estimates} />
          </>
        )}
      </div>
    </div>
  )
}
