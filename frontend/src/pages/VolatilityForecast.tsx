import { useState, useMemo } from 'react'
import { useMutation } from '@tanstack/react-query'
import {
  analyzeVol, forecastVol,
  type VolAnalysis, type VolForecast,
} from '../lib/api'
import Spinner, { ErrorState } from '../components/ui/Spinner'
import MetricCard from '../components/ui/MetricCard'
import Badge from '../components/ui/Badge'
import DataTable, { Column } from '../components/ui/DataTable'
import StockBrowser from '../components/ui/StockBrowser'
import { X, Activity, BarChart2, Table2, Play, Zap } from 'lucide-react'
import { cn, fmtPct } from '../lib/utils'
import {
  ResponsiveContainer, AreaChart, Area, LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ReferenceLine,
} from 'recharts'

const PERIODS = ['6mo', '1y', '2y', '5y']
type VolTab   = 'ewma' | 'lambda' | 'decay'

function VolTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded border border-border bg-bg-elevated p-3 shadow-lg">
      <p className="mb-1.5 text-xs font-semibold text-ink-secondary">{label}</p>
      {payload.map((p: any) => (
        <div key={p.dataKey} className="flex items-center gap-2 text-xs">
          <span className="h-1.5 w-1.5 rounded-full" style={{ background: p.color }} />
          <span className="text-ink-muted">{p.name}:</span>
          <span className="num font-mono text-ink-primary">
            {typeof p.value === 'number' ? p.value.toFixed(3) + '%' : p.value}
          </span>
        </div>
      ))}
    </div>
  )
}

type DecayRow = { 'λ': number; 'Half-life (days)': number; '95%-weight window (days)': number }

const DECAY_COLS: Column<DecayRow>[] = [
  {
    key: 'lambda', header: 'λ',
    cell: r => <span className="num font-mono text-ink-primary">{r['λ'].toFixed(2)}</span>,
    sort: r => r['λ'], align: 'right',
  },
  {
    key: 'hl', header: 'Half-life (days)',
    cell: r => <span className="num font-mono text-ink-secondary">{r['Half-life (days)'].toFixed(1)}</span>,
    sort: r => r['Half-life (days)'], align: 'right',
  },
  {
    key: 'w95', header: '95%-Weight Window',
    cell: r => <span className="num font-mono text-ink-secondary">{r['95%-weight window (days)'].toFixed(1)}</span>,
    sort: r => r['95%-weight window (days)'], align: 'right',
  },
]

export default function VolatilityForecast() {
  const [selected, setSelected]     = useState<string[]>([])
  const [period, setPeriod]         = useState('1y')
  const [activeTab, setTab]         = useState<VolTab>('ewma')
  const [horizon, setHorizon]       = useState(10)
  const [analysis, setAnalysis]     = useState<VolAnalysis | null>(null)
  const [forecast, setForecast]     = useState<VolForecast | null>(null)

  const ticker = selected[0] ?? ''

  function toggle(sym: string) {
    setSelected(prev => prev.includes(sym) ? [] : [sym])
    setAnalysis(null)
    setForecast(null)
  }

  const analyzeMut = useMutation({
    mutationFn: analyzeVol,
    onSuccess: d => { setAnalysis(d); setForecast(null) },
  })
  const forecastMut = useMutation({
    mutationFn: forecastVol,
    onSuccess: d => setForecast(d),
  })

  const analyzing   = analyzeMut.isPending
  const forecasting = forecastMut.isPending

  const xFmt = (d: string) =>
    d.startsWith('Day')
      ? d
      : new Date(d).toLocaleDateString('en-US', { month: 'short', year: '2-digit' })

  const forecastChartData = useMemo(() => {
    if (!forecast) return []
    const hist = forecast.hist_vol.map(r => ({
      label:  r.date,
      hist:   r.vol,
      fc:     undefined as number | undefined,
    }))
    const lastHist = hist[hist.length - 1]?.hist
    const fcPoints = forecast.forecast.map((r, i) => ({
      label: `Day +${r.day}`,
      hist:  i === 0 ? lastHist : undefined,
      fc:    r.ann_vol,
    }))
    return [...hist.slice(-60), ...fcPoints]
  }, [forecast])

  const fmtRupee = (n: number) =>
    `₹${Math.round(n).toLocaleString('en-IN')}`

  return (
    <div className="flex h-[calc(100vh-104px)] gap-5 animate-fade-up">
      {/* Left: Stock browser (single select, no sector dropdown) */}
      <StockBrowser
        className="w-[340px] shrink-0"
        selected={selected}
        onToggle={toggle}
        maxSelected={1}
        hideSector
      />

      {/* Right: controls + results */}
      <div className="flex flex-1 flex-col gap-4 min-w-0 overflow-y-auto">

        {/* Selected + period + analyze */}
        <div className="rounded-md border border-border bg-bg-surface p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-xs font-semibold uppercase tracking-widest text-ink-secondary">
              Selected Stock
            </h3>
            {ticker && (
              <button
                onClick={() => toggle(ticker)}
                className="text-xs text-ink-muted hover:text-loss transition-colors"
              >
                Clear
              </button>
            )}
          </div>

          {!ticker ? (
            <p className="text-xs text-ink-disabled">Pick a stock from the panel on the left.</p>
          ) : (
            <div className="flex items-center gap-1.5 rounded-sm border border-accent/30 bg-[rgba(56,139,253,.08)] px-2.5 py-1 font-mono text-xs font-semibold text-accent w-fit">
              {ticker} <button onClick={() => toggle(ticker)}><X size={10} /></button>
            </div>
          )}

          <div className="mt-4 flex flex-wrap items-end gap-4">
            <div className="flex flex-col gap-1.5">
              <label className="text-2xs font-semibold uppercase tracking-widest text-ink-secondary">Data Period</label>
              <div className="flex gap-1 rounded border border-border bg-bg-elevated p-1">
                {PERIODS.map(p => (
                  <button key={p} onClick={() => setPeriod(p)}
                    className={cn('rounded px-3 py-1 font-mono text-xs transition-colors',
                      period === p ? 'bg-accent text-white' : 'text-ink-secondary hover:text-ink-primary'
                    )}>{p}</button>
                ))}
              </div>
            </div>

            <button
              disabled={!ticker || analyzing}
              onClick={() => analyzeMut.mutate({ tickers: [ticker], period })}
              className={cn(
                'flex items-center gap-2 rounded border px-5 py-2 text-sm font-semibold transition-all',
                !ticker || analyzing
                  ? 'cursor-not-allowed border-border text-ink-disabled'
                  : 'border-accent bg-accent text-white hover:bg-accent/90',
              )}
            >
              {analyzing ? <><Spinner size={14} /> Analyzing…</> : <><Zap size={14} /> Analyze</>}
            </button>
          </div>
        </div>

        {analyzeMut.isError && (
          <ErrorState message={(analyzeMut.error as Error).message} />
        )}

        {analyzing && (
          <div className="flex items-center justify-center gap-3 py-16">
            <Spinner size={24} />
            <p className="text-sm text-ink-muted">Computing EWMA & fitting GARCH grid…</p>
          </div>
        )}

        {analysis && !analyzing && (
          <>
            {/* Metrics strip — row 1: vol metrics */}
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
              <MetricCard size="sm" label="Opt. Lambda"
                value={analysis.opt_lambda.toFixed(4)} accent="accent"
                tooltip="Optimal EWMA decay factor (λ) found by MLE. Controls how quickly old data loses influence. Closer to 1 = longer memory, slower decay." />
              <MetricCard size="sm" label="Half-life"
                value={`${analysis.half_life.toFixed(1)} d`}
                tooltip="Number of trading days for a volatility shock to decay to half its initial weight under the optimal λ." />
              <MetricCard size="sm" label="Current Vol"
                value={fmtPct(analysis.current_vol, 2)}
                accent={analysis.current_vol > analysis.mean_vol ? 'loss' : 'gain'}
                tooltip="Most recent EWMA annualised volatility — the market's current risk estimate for this stock." />
              <MetricCard size="sm" label="Peak Vol"
                value={fmtPct(analysis.peak_vol, 2)} accent="loss"
                sub={analysis.peak_date}
                tooltip="Highest annualised EWMA volatility recorded over the selected data period, and the date it occurred." />
              <MetricCard size="sm" label="Mean Vol"
                value={fmtPct(analysis.mean_vol, 2)}
                tooltip="Average annualised EWMA volatility over the selected data period — the stock's long-run volatility baseline." />
              <MetricCard size="sm" label="1D 1% VaR (₹1M)"
                value={fmtRupee(analysis.var_1d_1m)} accent="warn"
                tooltip="Value at Risk: the maximum expected 1-day loss on a ₹10L position at 99% confidence (1% chance of exceeding this loss)." />
            </div>

            {/* Metrics strip — row 2: best GARCH */}
            <div className="grid grid-cols-3 gap-3">
              <MetricCard size="sm" label="Best GARCH"
                value={`GARCH(${analysis.best_p},${analysis.best_q})`} accent="accent"
                tooltip="Best-fit GARCH(p,q) model selected by lowest joint AIC and BIC from the candidate grid. p = ARCH lags, q = GARCH lags." />
              <MetricCard size="sm" label="AIC"
                value={analysis.best_aic.toFixed(2)}
                tooltip="Akaike Information Criterion — measures model fit quality while penalising complexity. Lower is better." />
              <MetricCard size="sm" label="BIC"
                value={analysis.best_bic.toFixed(2)}
                tooltip="Bayesian Information Criterion — similar to AIC but with a stronger complexity penalty. Lower is better. Used alongside AIC to select the best model." />
            </div>

            {/* EWMA tabs */}
            <div className="rounded-md border border-border bg-bg-surface shadow-card">
              <div className="flex gap-1 border-b border-border px-4 pt-3">
                {([
                  { id: 'ewma',   label: 'EWMA History',      Icon: Activity },
                  { id: 'lambda', label: 'Lambda Sensitivity', Icon: BarChart2 },
                  { id: 'decay',  label: 'Decay Table',        Icon: Table2 },
                ] as const).map(({ id, label, Icon }) => (
                  <button key={id} onClick={() => setTab(id)}
                    className={cn(
                      'flex items-center gap-1.5 border-b-2 px-4 pb-2.5 text-xs font-semibold transition-colors',
                      activeTab === id
                        ? 'border-accent text-accent'
                        : 'border-transparent text-ink-secondary hover:text-ink-primary',
                    )}>
                    <Icon size={13} /> {label}
                  </button>
                ))}
              </div>

              <div className="p-5">
                {activeTab === 'ewma' && (
                  <ResponsiveContainer width="100%" height={280}>
                    <AreaChart data={analysis.vol_history} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                      <defs>
                        <linearGradient id="ewmaFill" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%"  stopColor="#388BFD" stopOpacity={0.3} />
                          <stop offset="95%" stopColor="#388BFD" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,.05)" />
                      <XAxis dataKey="date" tickFormatter={xFmt}
                        tick={{ fill: '#7D8590', fontSize: 11 }} tickLine={false} axisLine={false} />
                      <YAxis tick={{ fill: '#7D8590', fontSize: 11 }} tickLine={false} axisLine={false}
                        width={58} tickFormatter={v => v.toFixed(1) + '%'} />
                      <Tooltip content={<VolTooltip />} />
                      <Legend wrapperStyle={{ fontSize: 11, paddingTop: 8 }} />
                      <Area type="monotone" dataKey="ewma_vol" name="EWMA Vol"
                        stroke="#388BFD" fill="url(#ewmaFill)" strokeWidth={1.5} dot={false} />
                      <Line type="monotone" dataKey="rolling_vol" name="Rolling Vol"
                        stroke="#3FB950" strokeWidth={1} dot={false} strokeDasharray="4 2" connectNulls />
                    </AreaChart>
                  </ResponsiveContainer>
                )}

                {activeTab === 'lambda' && (
                  <div className="space-y-3">
                    <p className="text-xs text-ink-muted">
                      Half-life in trading days as a function of the EWMA decay parameter λ.
                      Red dashed line = optimal λ = {analysis.opt_lambda.toFixed(4)}.
                    </p>
                    <ResponsiveContainer width="100%" height={250}>
                      <BarChart data={analysis.decay_table} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,.05)" vertical={false} />
                        <XAxis dataKey="λ" tick={{ fill: '#7D8590', fontSize: 11 }}
                          tickLine={false} axisLine={false} tickFormatter={v => (+v).toFixed(2)} />
                        <YAxis tick={{ fill: '#7D8590', fontSize: 11 }} tickLine={false} axisLine={false}
                          width={40} tickFormatter={v => `${v}d`} />
                        <Tooltip
                          formatter={(v: number) => [`${v.toFixed(1)} days`, 'Half-life']}
                          contentStyle={{ background: '#0D1117', border: '1px solid #21262D', borderRadius: 4, fontSize: 12 }}
                          labelStyle={{ color: '#7D8590' }}
                          labelFormatter={v => `λ = ${v}`}
                        />
                        <Bar dataKey="Half-life (days)" fill="#388BFD" radius={[2, 2, 0, 0]} />
                        <ReferenceLine
                          y={analysis.half_life}
                          stroke="#F85149"
                          strokeDasharray="4 2"
                          label={{ value: `HL=${analysis.half_life.toFixed(1)}d`, fill: '#F85149', fontSize: 10 }}
                        />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                )}

                {activeTab === 'decay' && (
                  <DataTable
                    columns={DECAY_COLS}
                    data={analysis.decay_table as DecayRow[]}
                    keyFn={r => String(r['λ'])}
                  />
                )}
              </div>
            </div>

            {/* Forecast */}
            <div className="rounded-md border border-border bg-bg-surface shadow-card">
              <div className="flex flex-wrap items-center gap-4 border-b border-border px-5 py-3">
                <h3 className="text-xs font-semibold uppercase tracking-widest text-ink-secondary">
                  Volatility Forecast
                </h3>
                <Badge variant="accent">GARCH({analysis.best_p},{analysis.best_q})</Badge>
                <div className="ml-auto flex flex-wrap items-center gap-3">
                  <span className="text-xs text-ink-muted">
                    Horizon:&nbsp;
                    <span className="num font-mono font-semibold text-ink-primary">{horizon}d</span>
                  </span>
                  <input
                    type="range" min={1} max={30} value={horizon}
                    onChange={e => setHorizon(+e.target.value)}
                    className="w-28 accent-accent"
                  />
                  <button
                    disabled={forecasting}
                    onClick={() => forecastMut.mutate({
                      tickers: [ticker], period,
                      best_p: analysis.best_p,
                      best_q: analysis.best_q,
                      horizon,
                    })}
                    className={cn(
                      'flex items-center gap-2 rounded border px-4 py-1.5 text-xs font-semibold transition-all',
                      forecasting
                        ? 'cursor-not-allowed border-border text-ink-disabled'
                        : 'border-accent bg-[rgba(56,139,253,.12)] text-accent hover:bg-[rgba(56,139,253,.2)]',
                    )}
                  >
                    {forecasting ? <><Spinner size={12} /> Forecasting…</> : <><Play size={12} /> Run</>}
                  </button>
                </div>
              </div>

              <div className="p-5">
                {!forecast && !forecasting && (
                  <p className="py-8 text-center text-sm text-ink-disabled">
                    Set the horizon and click Run to generate a&nbsp;
                    GARCH({analysis.best_p},{analysis.best_q}) forecast.
                  </p>
                )}
                {forecasting && (
                  <div className="flex items-center justify-center gap-3 py-10">
                    <Spinner size={20} />
                    <p className="text-sm text-ink-muted">
                      Running GARCH({analysis.best_p},{analysis.best_q})…
                    </p>
                  </div>
                )}
                {forecast && !forecasting && (
                  <div className="space-y-5">
                    <ResponsiveContainer width="100%" height={260}>
                      <AreaChart data={forecastChartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                        <defs>
                          <linearGradient id="histFill" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%"  stopColor="#388BFD" stopOpacity={0.2} />
                            <stop offset="95%" stopColor="#388BFD" stopOpacity={0} />
                          </linearGradient>
                          <linearGradient id="fcFill" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%"  stopColor="#D29922" stopOpacity={0.35} />
                            <stop offset="95%" stopColor="#D29922" stopOpacity={0} />
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,.05)" />
                        <XAxis dataKey="label" tickFormatter={xFmt}
                          tick={{ fill: '#7D8590', fontSize: 10 }} tickLine={false} axisLine={false} />
                        <YAxis tick={{ fill: '#7D8590', fontSize: 11 }} tickLine={false} axisLine={false}
                          width={58} tickFormatter={v => v.toFixed(1) + '%'} />
                        <Tooltip content={<VolTooltip />} />
                        <Legend wrapperStyle={{ fontSize: 11, paddingTop: 8 }} />
                        <Area type="monotone" dataKey="hist" name="Historical Vol"
                          stroke="#388BFD" fill="url(#histFill)" strokeWidth={1.5} dot={false} connectNulls />
                        <Area type="monotone" dataKey="fc" name="Forecast Vol"
                          stroke="#D29922" fill="url(#fcFill)" strokeWidth={2}
                          dot={{ r: 3, fill: '#D29922' }} connectNulls />
                      </AreaChart>
                    </ResponsiveContainer>

                    <div className="overflow-x-auto rounded-md border border-border">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-border bg-bg-elevated">
                            {['Day', 'Ann. Vol', 'Daily Vol', '1D 1% VaR (₹1M)'].map(h => (
                              <th key={h}
                                className="px-4 py-2.5 text-right text-2xs font-semibold uppercase tracking-[.08em] text-ink-secondary first:text-left">
                                {h}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {forecast.forecast.map(r => (
                            <tr key={r.day}
                              className="border-b border-border/40 transition-colors last:border-0 hover:bg-bg-elevated">
                              <td className="px-4 py-2.5 num font-mono text-ink-primary">+{r.day}</td>
                              <td className="px-4 py-2.5 text-right num font-mono text-ink-secondary">
                                {fmtPct(r.ann_vol, 2)}
                              </td>
                              <td className="px-4 py-2.5 text-right num font-mono text-ink-secondary">
                                {fmtPct(r.daily_vol, 3)}
                              </td>
                              <td className="px-4 py-2.5 text-right num font-mono text-loss">
                                {fmtRupee(r.var_1d_1m)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
