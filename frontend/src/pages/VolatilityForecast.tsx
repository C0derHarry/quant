import { useState, useMemo } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import {
  getAllSymbols, analyzeVol, forecastVol,
  type VolAnalysis, type VolForecast, type GarchModel,
} from '../lib/api'
import Spinner, { ErrorState } from '../components/ui/Spinner'
import MetricCard from '../components/ui/MetricCard'
import Badge from '../components/ui/Badge'
import DataTable, { Column } from '../components/ui/DataTable'
import { Search, Activity, BarChart2, Table2, Play, Zap } from 'lucide-react'
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
            {typeof p.value === 'number' ? (p.value * 100).toFixed(3) + '%' : p.value}
          </span>
        </div>
      ))}
    </div>
  )
}

type DecayRow = { 'λ': number; 'Half-life (days)': number; '95%-weight window (days)': number }

const GARCH_COLS: Column<GarchModel>[] = [
  {
    key: 'model', header: 'Model',
    cell: r => <span className="font-mono text-sm font-semibold text-accent">{r.model}</span>,
    sort: r => r.model,
  },
  {
    key: 'aic', header: 'AIC',
    cell: r => <span className="num font-mono text-ink-primary">{r.aic.toFixed(2)}</span>,
    sort: r => r.aic, align: 'right',
  },
  {
    key: 'bic', header: 'BIC',
    cell: r => <span className="num font-mono text-ink-primary">{r.bic.toFixed(2)}</span>,
    sort: r => r.bic, align: 'right',
  },
  {
    key: 'sig', header: 'Sig.',
    cell: r => r.all_significant
      ? <Badge variant="gain">All sig.</Badge>
      : <Badge variant="neutral">—</Badge>,
    align: 'center',
  },
]

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
  const [tickerQuery, setQuery]     = useState('')
  const [showDrop, setShowDrop]     = useState(false)
  const [ticker, setTicker]         = useState('')
  const [period, setPeriod]         = useState('1y')
  const [activeTab, setTab]         = useState<VolTab>('ewma')
  const [horizon, setHorizon]       = useState(10)
  const [analysis, setAnalysis]     = useState<VolAnalysis | null>(null)
  const [forecast, setForecast]     = useState<VolForecast | null>(null)

  const { data: symbols } = useQuery({
    queryKey: ['symbols'],
    queryFn:  () => getAllSymbols('NSE'),
    staleTime: Infinity,
  })

  const suggestions = useMemo(() =>
    (symbols ?? [])
      .filter(s => tickerQuery.length >= 1 && (
        s.symbol.startsWith(tickerQuery.toUpperCase()) ||
        s.name.toUpperCase().includes(tickerQuery.toUpperCase())
      ))
      .slice(0, 8),
    [symbols, tickerQuery]
  )

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
      fc:    r.daily_vol,
    }))
    return [...hist.slice(-60), ...fcPoints]
  }, [forecast])

  const selectTicker = (sym: string) => {
    setTicker(sym)
    setQuery(sym)
    setShowDrop(false)
  }

  return (
    <div className="space-y-5 animate-fade-up">
      {/* ── Ticker + period config ───────────────────────────────── */}
      <div className="flex flex-wrap items-end gap-4 rounded-md border border-border bg-bg-surface p-4">
        {/* Ticker search */}
        <div className="flex flex-col gap-1.5">
          <label className="text-2xs font-semibold uppercase tracking-widest text-ink-secondary">Ticker</label>
          <div className="relative">
            <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted" />
            <input
              type="text"
              value={tickerQuery}
              placeholder="e.g. RELIANCE.NS"
              onChange={e => { setQuery(e.target.value); setTicker(''); setShowDrop(true) }}
              onFocus={() => setShowDrop(true)}
              onBlur={() => setTimeout(() => setShowDrop(false), 150)}
              className="w-56 rounded border border-border bg-bg-elevated py-1.5 pl-8 pr-3 text-sm text-ink-primary placeholder:text-ink-disabled focus:border-accent focus:outline-none"
            />
            {showDrop && suggestions.length > 0 && (
              <div className="absolute top-full z-20 mt-1 w-full rounded border border-border bg-bg-elevated shadow-lg">
                {suggestions.map(s => (
                  <button
                    key={s.symbol}
                    onMouseDown={() => selectTicker(s.symbol)}
                    className="flex w-full flex-col px-3 py-2 text-left transition-colors hover:bg-bg-overlay"
                  >
                    <span className="font-mono text-xs font-semibold text-accent">{s.symbol}</span>
                    <span className="truncate text-xs text-ink-muted">{s.name}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Period */}
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
            'ml-auto flex items-center gap-2 self-end rounded border px-5 py-2 text-sm font-semibold transition-all',
            !ticker || analyzing
              ? 'cursor-not-allowed border-border text-ink-disabled'
              : 'border-accent bg-accent text-white hover:bg-accent/90',
          )}
        >
          {analyzing ? <><Spinner size={14} /> Analyzing…</> : <><Zap size={14} /> Analyze</>}
        </button>
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
          {/* ── Metrics strip ─────────────────────────────────────── */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            <MetricCard size="sm" label="Opt. Lambda"
              value={analysis.opt_lambda.toFixed(4)} accent="accent" />
            <MetricCard size="sm" label="Half-life"
              value={`${analysis.half_life.toFixed(1)} d`} />
            <MetricCard size="sm" label="Current Vol"
              value={fmtPct(analysis.current_vol * 100, 2)}
              accent={analysis.current_vol > analysis.mean_vol ? 'loss' : 'gain'} />
            <MetricCard size="sm" label="Peak Vol"
              value={fmtPct(analysis.peak_vol * 100, 2)} accent="loss"
              sub={analysis.peak_date} />
            <MetricCard size="sm" label="Mean Vol"
              value={fmtPct(analysis.mean_vol * 100, 2)} />
            <MetricCard size="sm" label="1D 1% VaR"
              value={fmtPct(analysis.var_1d_1m * 100, 2)} accent="warn" />
          </div>

          {/* ── EWMA tabs ─────────────────────────────────────────── */}
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
              {/* EWMA History */}
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
                      width={58} tickFormatter={v => (v * 100).toFixed(1) + '%'} />
                    <Tooltip content={<VolTooltip />} />
                    <Legend wrapperStyle={{ fontSize: 11, paddingTop: 8 }} />
                    <Area type="monotone" dataKey="ewma_vol" name="EWMA Vol"
                      stroke="#388BFD" fill="url(#ewmaFill)" strokeWidth={1.5} dot={false} />
                    <Line type="monotone" dataKey="rolling_vol" name="Rolling Vol"
                      stroke="#3FB950" strokeWidth={1} dot={false} strokeDasharray="4 2" connectNulls />
                  </AreaChart>
                </ResponsiveContainer>
              )}

              {/* Lambda sensitivity */}
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

              {/* Decay table */}
              {activeTab === 'decay' && (
                <DataTable
                  columns={DECAY_COLS}
                  data={analysis.decay_table as DecayRow[]}
                  keyFn={r => String(r['λ'])}
                />
              )}
            </div>
          </div>

          {/* ── GARCH model grid ──────────────────────────────────── */}
          <div className="rounded-md border border-border bg-bg-surface shadow-card">
            <div className="flex items-center justify-between border-b border-border px-5 py-3">
              <h3 className="text-xs font-semibold uppercase tracking-widest text-ink-secondary">
                GARCH Model Grid
              </h3>
              <Badge variant="accent">Best: GARCH({analysis.best_p},{analysis.best_q})</Badge>
            </div>
            <div className="p-4">
              <DataTable
                columns={GARCH_COLS}
                data={analysis.garch_models}
                keyFn={r => r.model}
              />
            </div>
          </div>

          {/* ── Forecast ──────────────────────────────────────────── */}
          <div className="rounded-md border border-border bg-bg-surface shadow-card">
            <div className="flex flex-wrap items-center gap-4 border-b border-border px-5 py-3">
              <h3 className="text-xs font-semibold uppercase tracking-widest text-ink-secondary">
                Volatility Forecast
              </h3>
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
                        width={58} tickFormatter={v => (v * 100).toFixed(1) + '%'} />
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
                          {['Day', 'Ann. Vol', 'Daily Vol', '1D 1% VaR'].map(h => (
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
                              {fmtPct(r.ann_vol * 100, 2)}
                            </td>
                            <td className="px-4 py-2.5 text-right num font-mono text-ink-secondary">
                              {fmtPct(r.daily_vol * 100, 3)}
                            </td>
                            <td className="px-4 py-2.5 text-right num font-mono text-loss">
                              {fmtPct(r.var_1d_1m * 100, 2)}
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
  )
}
