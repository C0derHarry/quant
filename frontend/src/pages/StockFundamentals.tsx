import { useState, useCallback, useMemo } from 'react'
import { useLocation } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import {
  getOHLCV, getKPIs, getRollingKPIs,
  type FundamentalsReq, type OHLCVRow, type KPISet, type RollingRow,
} from '../lib/api'
import Spinner from '../components/ui/Spinner'
import MetricCard from '../components/ui/MetricCard'
import Badge from '../components/ui/Badge'
import StockBrowser from '../components/ui/StockBrowser'
import { X, Play, BarChart3, TrendingUp, Activity } from 'lucide-react'
import { cn, fmt, fmtPct, fmtLargeNum } from '../lib/utils'
import {
  ResponsiveContainer, LineChart, Line, AreaChart, Area,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, BarChart, Bar,
} from 'recharts'

const PALETTE = ['#388BFD', '#3FB950', '#F85149', '#D29922', '#BC8CFF']
const PERIODS = ['1mo', '3mo', '6mo', '1y', '2y', '5y', '10y']

const PERIOD_INTERVAL_MAP: Record<string, string[]> = {
  '1mo': ['30m', '60m', '90m', '1d', '5d', '1wk'],
  '3mo': ['30m', '1h',  '1d', '5d', '1wk', '1mo'],
  '6mo': ['1d',  '5d',  '1wk', '1mo'],
  '1y':  ['1d',  '5d',  '1wk', '1mo'],
  '2y':  ['1d',  '5d',  '1wk', '1mo'],
  '5y':  ['1d',  '5d',  '1wk', '1mo'],
  '10y': ['1d',  '5d',  '1wk', '1mo'],
}

const MIN_WINDOW_BARS: Record<string, number> = {
  '1mo_1d':   5,  '1mo_1wk':  2,
  '3mo_1d':  10,  '3mo_1wk':  4,  '3mo_1mo':  2,
  '6mo_1d':  21,  '6mo_1wk':  8,  '6mo_1mo':  3,
  '1y_1d':   63,  '1y_5d':   13,  '1y_1wk':  12,  '1y_1mo':  4,
  '2y_1d':  126,  '2y_5d':   26,  '2y_1wk':  26,  '2y_1mo':  6,
  '5y_1d':  252,  '5y_5d':   52,  '5y_1wk':  52,  '5y_1mo': 12,
  '10y_1d': 252, '10y_5d':  104, '10y_1wk': 104, '10y_1mo': 24,
}

const INTERVAL_LABEL: Record<string, string> = {
  '30m': '30m', '60m': '60m', '90m': '90m', '1h': '1h',
  '1d': '1D', '5d': '5D', '1wk': '1W', '1mo': '1M',
}

type ResultTab    = 'price' | 'kpis' | 'rolling'
type RollingMetric = 'rolling_cagr' | 'rolling_sharpe' | 'rolling_calmar' | 'drawdown'

const ROLLING_LABELS: Record<RollingMetric, string> = {
  rolling_cagr:   'Rolling CAGR',
  rolling_sharpe: 'Rolling Sharpe',
  rolling_calmar: 'Rolling Calmar',
  drawdown:       'Drawdown',
}

function DarkTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded border border-border bg-bg-elevated p-3 shadow-lg">
      <p className="mb-2 text-xs font-semibold text-ink-secondary">{label}</p>
      {payload.map((p: any) => (
        <div key={p.dataKey} className="flex items-center gap-2 text-xs">
          <span className="h-1.5 w-1.5 rounded-full" style={{ background: p.color }} />
          <span className="text-ink-muted">{p.name}:</span>
          <span className="num font-mono text-ink-primary">
            {typeof p.value === 'number' ? p.value.toFixed(2) : p.value}
          </span>
        </div>
      ))}
    </div>
  )
}

function VolumeTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded border border-border bg-bg-elevated p-3 shadow-lg">
      <p className="mb-1 text-xs font-semibold text-ink-secondary">{label}</p>
      <span className="num font-mono text-xs text-ink-primary">{fmtLargeNum(payload[0]?.value ?? 0)}</span>
    </div>
  )
}

function StatBadge({ diffs }: { diffs: number }) {
  if (diffs === 0) return <Badge variant="gain">Stationary I(0)</Badge>
  if (diffs === 1) return <Badge variant="warn">Integrated I(1)</Badge>
  return <Badge variant="loss">Integrated I({diffs})</Badge>
}

function KPIGrid({ ticker, kpi, color }: { ticker: string; kpi: KPISet; color: string }) {
  return (
    <div className="rounded-md border bg-bg-surface p-4" style={{ borderColor: color + '40' }}>
      <div className="mb-3 flex items-center justify-between">
        <p className="font-mono text-sm font-bold" style={{ color }}>{ticker}</p>
        <StatBadge diffs={kpi.stationarity_diffs} />
      </div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <MetricCard size="sm" label="CAGR"
          value={fmtPct(kpi.cagr, 1)}
          accent={kpi.cagr >= 0 ? 'gain' : 'loss'}
          tooltip="Compound Annual Growth Rate — total return expressed as an equivalent annual rate over the selected period." />
        <MetricCard size="sm" label="Ann. Volatility"
          value={fmtPct(kpi.volatility, 1)}
          tooltip="Annualised standard deviation of daily log returns — measures the magnitude of price swings. Higher = more uncertain." />
        <MetricCard size="sm" label="Sharpe Ratio"
          value={fmt(kpi.sharpe)}
          accent={kpi.sharpe >= 1 ? 'gain' : kpi.sharpe >= 0.5 ? 'warn' : 'loss'}
          tooltip="Risk-adjusted return: CAGR ÷ volatility. Above 1 is good, above 2 is excellent. Negative means returns lagged the risk taken." />
        <MetricCard size="sm" label="Max Drawdown"
          value={fmtPct(kpi.max_drawdown, 1)} accent="loss"
          tooltip="Largest peak-to-trough decline over the period. Represents the worst loss an investor would have experienced." />
        <MetricCard size="sm" label="Calmar Ratio"
          value={fmt(kpi.calmar)}
          accent={kpi.calmar >= 0.5 ? 'gain' : 'neutral'}
          tooltip="CAGR divided by Max Drawdown. Higher values indicate better return per unit of drawdown risk taken." />
        <MetricCard size="sm" label="Skewness"
          value={fmt(kpi.skewness)}
          tooltip="Asymmetry of the return distribution. Positive = more frequent large gains; Negative = more frequent large losses (fat left tail)." />
        <MetricCard size="sm" label="Excess Kurtosis"
          value={fmt(kpi.excess_kurtosis)}
          tooltip="Fat-tail risk beyond a normal distribution. High positive values mean extreme moves (crashes or surges) happen more often than expected." />
        <MetricCard size="sm" label="% Positive Days"
          value={`${kpi.pct_positive.toFixed(0)}%`}
          accent={kpi.pct_positive >= 52 ? 'gain' : 'neutral'}
          tooltip="Percentage of trading days with a positive return. A consistent edge above 50% is generally favourable." />
      </div>
    </div>
  )
}

export default function StockFundamentals() {
  const location = useLocation()
  const [selected, setSelected] = useState<string[]>(() => {
    const pre = (location.state as { preselect?: string } | null)?.preselect
    return pre ? [pre] : []
  })
  const [period, setPeriod]       = useState('1y')
  const [interval, setInterval]   = useState('1d')
  const [rollingWindow, setWin]   = useState(63)   // MIN_WINDOW_BARS['1y_1d']
  const [resultTab, setResultTab] = useState<ResultTab>('price')
  const [rollingMetric, setRM]    = useState<RollingMetric>('rolling_sharpe')

  const validIntervals = PERIOD_INTERVAL_MAP[period] ?? ['1d']
  const minWindow      = MIN_WINDOW_BARS[`${period}_${interval}`] ?? 5
  const maxWindow      = Math.max(minWindow * 6, minWindow + 10)

  function handlePeriodChange(p: string) {
    const valid = PERIOD_INTERVAL_MAP[p] ?? ['1d']
    const newIv = valid.includes(interval) ? interval : (valid.includes('1d') ? '1d' : valid[0])
    const minW  = MIN_WINDOW_BARS[`${p}_${newIv}`] ?? 5
    setPeriod(p)
    setInterval(newIv)
    setWin(minW)
  }

  function handleIntervalChange(iv: string) {
    const minW = MIN_WINDOW_BARS[`${period}_${iv}`] ?? 5
    setInterval(iv)
    setWin(minW)
  }

  const ohlcvMut   = useMutation({ mutationFn: getOHLCV })
  const kpiMut     = useMutation({ mutationFn: getKPIs })
  const rollingMut = useMutation({ mutationFn: getRollingKPIs })

  const running    = ohlcvMut.isPending || kpiMut.isPending || rollingMut.isPending
  const hasResults = !!ohlcvMut.data

  const runAll = useCallback(() => {
    const req: FundamentalsReq = { symbols: selected, period, interval, window: rollingWindow }
    ohlcvMut.mutate(req)
    kpiMut.mutate(req)
    rollingMut.mutate(req)
  }, [selected, period, interval, rollingWindow])

  function toggle(sym: string) {
    if (selected.includes(sym)) setSelected(p => p.filter(s => s !== sym))
    else if (selected.length < 5) setSelected(p => [...p, sym])
  }

  const ohlcvData   = ohlcvMut.data
  const kpiData     = kpiMut.data
  const rollingData = rollingMut.data

  const normalizedData = useMemo(() => {
    if (!ohlcvData) return []
    const entries = Object.entries(ohlcvData)
    if (!entries.length) return []
    const bases: Record<string, number>                      = {}
    const lookup: Record<string, Record<string, OHLCVRow>>   = {}
    entries.forEach(([t, rows]) => {
      bases[t]  = rows[0]?.close ?? 1
      lookup[t] = Object.fromEntries(rows.map(r => [r.date, r]))
    })
    const allDates = [...new Set(entries.flatMap(([, rows]) => rows.map(r => r.date)))].sort()
    return allDates.map(date => {
      const pt: Record<string, number | string> = { date }
      entries.forEach(([t]) => {
        const r = lookup[t][date]
        if (r) pt[t] = +((r.close / bases[t]) * 100).toFixed(2)
      })
      return pt
    })
  }, [ohlcvData])

  const volumeData = useMemo(() => {
    if (!ohlcvData || !selected.length) return []
    return (ohlcvData[selected[0]] ?? []).map(r => ({ date: r.date, volume: r.volume }))
  }, [ohlcvData, selected])

  const rollingChartData = useMemo(() => {
    if (!rollingData) return []
    const entries = Object.entries(rollingData)
    if (!entries.length) return []
    const lookup: Record<string, Record<string, RollingRow>> = {}
    entries.forEach(([t, rows]) => {
      lookup[t] = Object.fromEntries(rows.map(r => [r.date, r]))
    })
    const allDates = [...new Set(entries.flatMap(([, rows]) => rows.map(r => r.date)))].sort()
    return allDates.map(date => {
      const pt: Record<string, number | string> = { date }
      entries.forEach(([t]) => {
        const r = lookup[t][date]
        if (r) pt[t] = +(r[rollingMetric] ?? 0).toFixed(4)
      })
      return pt
    })
  }, [rollingData, rollingMetric])

  const xFmt = (d: string) =>
    new Date(d).toLocaleDateString('en-US', { month: 'short', year: '2-digit' })

  return (
    <div className="flex h-[calc(100vh-104px)] gap-5 animate-fade-up">
      {/* ── Left: Stock browser ─────────────────────────────────── */}
      <StockBrowser
        className="w-[320px] shrink-0"
        selected={selected}
        onToggle={toggle}
        maxSelected={5}
      />

      {/* ── Right panel ─────────────────────────────────────────── */}
      <div className="flex flex-1 flex-col gap-4 overflow-hidden">
        {/* Selected chips */}
        <div className="rounded-md border border-border bg-bg-surface p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-xs font-semibold uppercase tracking-widest text-ink-secondary">
              Selected ({selected.length}/5)
            </h3>
            {selected.length > 0 && (
              <button onClick={() => setSelected([])}
                className="text-xs text-ink-muted hover:text-loss transition-colors">
                Clear all
              </button>
            )}
          </div>
          {selected.length === 0 ? (
            <p className="text-xs text-ink-disabled">Select up to 5 stocks from the panel on the left.</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {selected.map((sym, i) => (
                <button key={sym} onClick={() => toggle(sym)}
                  className="flex items-center gap-1.5 rounded-sm border px-2.5 py-1 font-mono text-xs font-semibold transition-colors hover:opacity-70"
                  style={{ borderColor: PALETTE[i] + '60', background: PALETTE[i] + '18', color: PALETTE[i] }}
                >
                  {sym} <X size={10} />
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Config bar */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Period */}
          <div className="flex items-center gap-2 rounded border border-border bg-bg-surface px-3 py-2">
            <span className="text-2xs font-semibold uppercase tracking-widest text-ink-disabled">Period</span>
            <div className="flex gap-0.5">
              {PERIODS.map(p => (
                <button key={p} onClick={() => handlePeriodChange(p)}
                  className={cn('rounded px-2 py-0.5 font-mono text-xs transition-colors',
                    period === p ? 'bg-accent text-white' : 'text-ink-secondary hover:text-ink-primary'
                  )}>{p}</button>
              ))}
            </div>
          </div>

          {/* Interval — filtered by period */}
          <div className="flex items-center gap-2 rounded border border-border bg-bg-surface px-3 py-2">
            <span className="text-2xs font-semibold uppercase tracking-widest text-ink-disabled">Interval</span>
            <div className="flex gap-0.5">
              {validIntervals.map(iv => (
                <button key={iv} onClick={() => handleIntervalChange(iv)}
                  className={cn('rounded px-2 py-0.5 font-mono text-xs transition-colors',
                    interval === iv ? 'bg-accent text-white' : 'text-ink-secondary hover:text-ink-primary'
                  )}>{INTERVAL_LABEL[iv] ?? iv}</button>
              ))}
            </div>
          </div>

          {/* Window — number input clamped to [minWindow, maxWindow] */}
          <div className="flex items-center gap-2 rounded border border-border bg-bg-surface px-3 py-2">
            <span className="text-2xs font-semibold uppercase tracking-widest text-ink-disabled">Window</span>
            <input
              type="number"
              value={rollingWindow}
              min={minWindow}
              max={maxWindow}
              onChange={e => setWin(Math.max(minWindow, Math.min(maxWindow, +e.target.value)))}
              className="w-14 bg-transparent num font-mono text-xs text-ink-primary focus:outline-none"
            />
            <span className="text-2xs text-ink-disabled">bars · min&nbsp;{minWindow}</span>
          </div>

          <button
            onClick={runAll}
            disabled={selected.length === 0 || running}
            className={cn(
              'ml-auto flex items-center gap-2 rounded border px-5 py-2 text-sm font-semibold transition-all',
              selected.length === 0 || running
                ? 'cursor-not-allowed border-border text-ink-disabled'
                : 'border-accent bg-accent text-white hover:bg-accent/90',
            )}
          >
            {running
              ? <><Spinner size={14} /> Analyzing…</>
              : <><Play size={14} /> Run Analysis</>}
          </button>
        </div>

        {/* Results */}
        <div className="flex-1 overflow-hidden rounded-md border border-border bg-bg-surface shadow-card">
          {!hasResults && !running && (
            <div className="flex h-full flex-col items-center justify-center gap-3">
              <TrendingUp size={32} className="text-ink-disabled" />
              <p className="text-sm text-ink-disabled">Select stocks and run analysis to see results.</p>
            </div>
          )}
          {running && (
            <div className="flex h-full flex-col items-center justify-center gap-3">
              <Spinner size={24} />
              <p className="text-sm text-ink-muted">Downloading data and computing metrics…</p>
            </div>
          )}
          {hasResults && !running && (
            <div className="flex h-full flex-col">
              {/* Tab bar */}
              <div className="flex gap-1 border-b border-border px-4 pt-3">
                {([
                  { id: 'price',   label: 'Price Chart',       Icon: TrendingUp },
                  { id: 'kpis',    label: 'KPIs',              Icon: BarChart3 },
                  { id: 'rolling', label: 'Rolling Analytics', Icon: Activity },
                ] as const).map(({ id, label, Icon }) => (
                  <button key={id} onClick={() => setResultTab(id)}
                    className={cn(
                      'flex items-center gap-1.5 border-b-2 px-4 pb-2.5 text-xs font-semibold transition-colors',
                      resultTab === id
                        ? 'border-accent text-accent'
                        : 'border-transparent text-ink-secondary hover:text-ink-primary',
                    )}>
                    <Icon size={13} /> {label}
                  </button>
                ))}
              </div>

              <div className="flex-1 overflow-auto p-5">
                {/* Price Chart */}
                {resultTab === 'price' && (
                  <div className="space-y-6">
                    <div>
                      <p className="mb-3 text-2xs font-semibold uppercase tracking-[.08em] text-ink-disabled">
                        Normalised Performance — rebased to 100
                      </p>
                      <ResponsiveContainer width="100%" height={280}>
                        <LineChart data={normalizedData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,.05)" />
                          <XAxis dataKey="date" tickFormatter={xFmt}
                            tick={{ fill: '#7D8590', fontSize: 11 }} tickLine={false} axisLine={false} />
                          <YAxis tick={{ fill: '#7D8590', fontSize: 11 }} tickLine={false} axisLine={false}
                            width={48} tickFormatter={v => v.toFixed(0)} />
                          <Tooltip content={<DarkTooltip />} />
                          <Legend wrapperStyle={{ fontSize: 11, paddingTop: 8 }} />
                          {selected.map((t, i) => (
                            <Line key={t} type="monotone" dataKey={t} stroke={PALETTE[i]}
                              strokeWidth={1.5} dot={false} connectNulls />
                          ))}
                        </LineChart>
                      </ResponsiveContainer>
                    </div>

                    {volumeData.length > 0 && (
                      <div>
                        <p className="mb-3 text-2xs font-semibold uppercase tracking-[.08em] text-ink-disabled">
                          Volume — {selected[0]}
                        </p>
                        <ResponsiveContainer width="100%" height={110}>
                          <BarChart data={volumeData} margin={{ top: 0, right: 20, left: 0, bottom: 0 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,.05)" vertical={false} />
                            <XAxis dataKey="date" tickFormatter={xFmt}
                              tick={{ fill: '#7D8590', fontSize: 10 }} tickLine={false} axisLine={false} />
                            <YAxis tick={{ fill: '#7D8590', fontSize: 10 }} tickLine={false} axisLine={false}
                              width={48} tickFormatter={fmtLargeNum} />
                            <Tooltip content={<VolumeTooltip />} />
                            <Bar dataKey="volume" fill="rgba(56,139,253,.35)" radius={[1, 1, 0, 0]} />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    )}
                  </div>
                )}

                {/* KPIs */}
                {resultTab === 'kpis' && kpiData && (
                  <div className="space-y-4">
                    {selected.map((t, i) => kpiData[t] && (
                      <KPIGrid key={t} ticker={t} kpi={kpiData[t]} color={PALETTE[i]} />
                    ))}
                  </div>
                )}

                {/* Rolling Analytics */}
                {resultTab === 'rolling' && rollingData && (
                  <div className="space-y-4">
                    <div className="flex flex-wrap gap-2">
                      {(Object.entries(ROLLING_LABELS) as [RollingMetric, string][]).map(([k, v]) => (
                        <button key={k} onClick={() => setRM(k)}
                          className={cn(
                            'rounded border px-3 py-1 text-xs font-medium transition-colors',
                            rollingMetric === k
                              ? 'border-accent bg-[rgba(56,139,253,.12)] text-accent'
                              : 'border-border text-ink-secondary hover:bg-bg-elevated',
                          )}>{v}</button>
                      ))}
                    </div>
                    <ResponsiveContainer width="100%" height={300}>
                      <LineChart data={rollingChartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,.05)" />
                        <XAxis dataKey="date" tickFormatter={xFmt}
                          tick={{ fill: '#7D8590', fontSize: 11 }} tickLine={false} axisLine={false} />
                        <YAxis tick={{ fill: '#7D8590', fontSize: 11 }} tickLine={false} axisLine={false}
                          width={55} tickFormatter={v => v.toFixed(2)} />
                        <Tooltip content={<DarkTooltip />} />
                        <Legend wrapperStyle={{ fontSize: 11, paddingTop: 8 }} />
                        {selected.map((t, i) => (
                          <Line key={t} type="monotone" dataKey={t} stroke={PALETTE[i]}
                            strokeWidth={1.5} dot={false} connectNulls />
                        ))}
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
