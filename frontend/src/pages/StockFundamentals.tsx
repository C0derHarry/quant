import { useState, useCallback, useMemo } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import {
  getAllSymbols, getOHLCV, getKPIs, getRollingKPIs,
  type FundamentalsReq, type OHLCVRow, type KPISet, type RollingRow,
} from '../lib/api'
import { PageLoader, ErrorState } from '../components/ui/Spinner'
import Spinner from '../components/ui/Spinner'
import MetricCard from '../components/ui/MetricCard'
import Badge from '../components/ui/Badge'
import { Search, X, Plus, CheckCircle2, Play, BarChart3, TrendingUp, Activity } from 'lucide-react'
import { cn, fmt, fmtPct, fmtLargeNum } from '../lib/utils'
import {
  ResponsiveContainer, LineChart, Line, AreaChart, Area,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, BarChart, Bar,
} from 'recharts'

const PAGE     = 15
const PALETTE  = ['#388BFD', '#3FB950', '#F85149', '#D29922', '#BC8CFF']
const PERIODS  = ['1mo', '3mo', '6mo', '1y', '2y', '5y']
const INTERVALS = ['1d', '1wk']
const WINDOWS  = [30, 60, 90, 180, 252]

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
          value={fmtPct(kpi.cagr * 100, 1)}
          accent={kpi.cagr >= 0 ? 'gain' : 'loss'} />
        <MetricCard size="sm" label="Ann. Volatility"
          value={fmtPct(kpi.volatility * 100, 1)} />
        <MetricCard size="sm" label="Sharpe Ratio"
          value={fmt(kpi.sharpe)}
          accent={kpi.sharpe >= 1 ? 'gain' : kpi.sharpe >= 0.5 ? 'warn' : 'loss'} />
        <MetricCard size="sm" label="Max Drawdown"
          value={fmtPct(kpi.max_drawdown * 100, 1)} accent="loss" />
        <MetricCard size="sm" label="Calmar Ratio"
          value={fmt(kpi.calmar)}
          accent={kpi.calmar >= 0.5 ? 'gain' : 'neutral'} />
        <MetricCard size="sm" label="Skewness"
          value={fmt(kpi.skewness)} />
        <MetricCard size="sm" label="Excess Kurtosis"
          value={fmt(kpi.excess_kurtosis)} />
        <MetricCard size="sm" label="% Positive Days"
          value={`${kpi.pct_positive.toFixed(0)}%`}
          accent={kpi.pct_positive >= 52 ? 'gain' : 'neutral'} />
      </div>
    </div>
  )
}

export default function StockFundamentals() {
  const [search, setSearch]       = useState('')
  const [page, setPage]           = useState(0)
  const [selected, setSelected]   = useState<string[]>([])
  const [period, setPeriod]       = useState('1y')
  const [interval, setInterval]   = useState('1d')
  const [rollingWindow, setWin]   = useState(90)
  const [resultTab, setResultTab] = useState<ResultTab>('price')
  const [rollingMetric, setRM]    = useState<RollingMetric>('rolling_sharpe')

  const { data: symbols, isLoading, error } = useQuery({
    queryKey: ['symbols'],
    queryFn:  () => getAllSymbols('NSE'),
    staleTime: Infinity,
  })

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

  const filtered   = (symbols ?? []).filter(s =>
    search
      ? s.symbol.startsWith(search.toUpperCase()) ||
        s.name.toUpperCase().includes(search.toUpperCase())
      : true
  )
  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE))
  const pageItems  = filtered.slice(page * PAGE, (page + 1) * PAGE)

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

  if (isLoading) return <PageLoader label="Loading symbols…" />
  if (error)     return <ErrorState message={error.message} />

  return (
    <div className="flex h-[calc(100vh-104px)] gap-5 animate-fade-up">
      {/* ── Left: Stock browser ─────────────────────────────────── */}
      <div className="flex w-[320px] shrink-0 flex-col rounded-md border border-border bg-bg-surface shadow-card">
        <div className="border-b border-border p-4">
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-widest text-ink-secondary">
            NSE Universe <span className="ml-1 text-ink-disabled">(max 5)</span>
          </h3>
          <div className="relative">
            <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted" />
            <input
              type="text"
              placeholder="Search symbol or name…"
              value={search}
              onChange={e => { setSearch(e.target.value); setPage(0) }}
              className="w-full rounded border border-border bg-bg-elevated py-1.5 pl-8 pr-3 text-sm text-ink-primary placeholder:text-ink-disabled focus:border-accent focus:outline-none"
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto">
          {pageItems.map(s => {
            const sel  = selected.includes(s.symbol)
            const full = !sel && selected.length >= 5
            return (
              <button
                key={s.symbol}
                onClick={() => toggle(s.symbol)}
                disabled={full}
                className={cn(
                  'flex w-full items-center justify-between px-4 py-2.5 text-left transition-colors',
                  'border-b border-border/40 last:border-0',
                  sel  ? 'bg-[rgba(56,139,253,.06)]'     : 'hover:bg-bg-elevated',
                  full ? 'cursor-not-allowed opacity-40' : '',
                )}
              >
                <div>
                  <p className={cn('font-mono text-sm font-semibold', sel ? 'text-accent' : 'text-ink-primary')}>
                    {s.symbol}
                  </p>
                  <p className="mt-0.5 max-w-[180px] truncate text-xs text-ink-muted">{s.name}</p>
                </div>
                {sel
                  ? <CheckCircle2 size={15} className="shrink-0 text-accent" />
                  : <Plus size={15} className="shrink-0 text-ink-disabled" />
                }
              </button>
            )
          })}
        </div>

        <div className="flex items-center justify-between border-t border-border px-4 py-2.5">
          <button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0}
            className="text-xs text-ink-secondary hover:text-ink-primary disabled:text-ink-disabled">
            ← Prev
          </button>
          <span className="text-xs text-ink-muted">{page + 1} / {totalPages}</span>
          <button onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))} disabled={page >= totalPages - 1}
            className="text-xs text-ink-secondary hover:text-ink-primary disabled:text-ink-disabled">
            Next →
          </button>
        </div>
      </div>

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
          <div className="flex items-center gap-2 rounded border border-border bg-bg-surface px-3 py-2">
            <span className="text-2xs font-semibold uppercase tracking-widest text-ink-disabled">Period</span>
            <div className="flex gap-0.5">
              {PERIODS.map(p => (
                <button key={p} onClick={() => setPeriod(p)}
                  className={cn('rounded px-2 py-0.5 font-mono text-xs transition-colors',
                    period === p ? 'bg-accent text-white' : 'text-ink-secondary hover:text-ink-primary'
                  )}>{p}</button>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-2 rounded border border-border bg-bg-surface px-3 py-2">
            <span className="text-2xs font-semibold uppercase tracking-widest text-ink-disabled">Interval</span>
            <div className="flex gap-0.5">
              {INTERVALS.map(iv => (
                <button key={iv} onClick={() => setInterval(iv)}
                  className={cn('rounded px-2 py-0.5 font-mono text-xs transition-colors',
                    interval === iv ? 'bg-accent text-white' : 'text-ink-secondary hover:text-ink-primary'
                  )}>{iv}</button>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-2 rounded border border-border bg-bg-surface px-3 py-2">
            <span className="text-2xs font-semibold uppercase tracking-widest text-ink-disabled">Window</span>
            <div className="flex gap-0.5">
              {WINDOWS.map(w => (
                <button key={w} onClick={() => setWin(w)}
                  className={cn('rounded px-2 py-0.5 font-mono text-xs transition-colors',
                    rollingWindow === w ? 'bg-accent text-white' : 'text-ink-secondary hover:text-ink-primary'
                  )}>{w}d</button>
              ))}
            </div>
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
