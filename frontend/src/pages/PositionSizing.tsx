import { useState, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import {
  optimizePortfolio,
  type OptimizeResult, type StopRow, type RegimeWarning, type DCARow,
} from '../lib/api'
import Spinner, { ErrorState } from '../components/ui/Spinner'
import MetricCard from '../components/ui/MetricCard'
import Badge, { regimeBadge } from '../components/ui/Badge'
import DataTable, { Column } from '../components/ui/DataTable'
import StockBrowser from '../components/ui/StockBrowser'
import { X, AlertTriangle, Play, Layers, ChevronDown, Brain } from 'lucide-react'
import { cn, fmt, fmtPct, fmtCurrency } from '../lib/utils'
import { REGIME_COLOR } from '../lib/utils'
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Cell,
} from 'recharts'

const PALETTE = ['#388BFD', '#3FB950', '#F85149', '#D29922', '#BC8CFF', '#56D364', '#E3B341', '#79C0FF']

const STOP_COLS: Column<StopRow>[] = [
  {
    key: 'ticker', header: 'Ticker',
    cell: r => (
      <div className="flex items-center gap-2">
        <span className="font-mono text-sm font-semibold text-accent">{r.ticker}</span>
        {r.is_short && <Badge variant="loss" className="text-2xs py-0">SHORT</Badge>}
      </div>
    ),
    sort: r => r.ticker,
  },
  {
    key: 'regime', header: 'Regime',
    cell: r => <Badge variant={regimeBadge(r.regime)}>{r.regime}</Badge>,
    sort: r => r.regime,
  },
  {
    key: 'bl_return', header: 'BL Return',
    cell: r => (
      <span className={cn('num font-mono', r.bl_return >= 0 ? 'text-gain' : 'text-loss')}>
        {fmtPct(r.bl_return)}
      </span>
    ),
    sort: r => r.bl_return, align: 'right',
  },
  {
    key: 'weight', header: 'Weight',
    cell: r => <span className="num font-mono text-ink-primary">{fmtPct(r.weight)}</span>,
    sort: r => r.weight, align: 'right',
  },
  {
    key: 'allocation', header: 'Allocated',
    cell: r => <span className="num font-mono text-ink-secondary">{fmtCurrency(r.allocation)}</span>,
    sort: r => r.allocation, align: 'right',
  },
  {
    key: 'shares', header: 'Shares',
    cell: r => <span className="num font-mono text-ink-secondary">{r.shares}</span>,
    sort: r => r.shares, align: 'right',
  },
  {
    key: 'entry_price', header: 'Entry ₹',
    cell: r => <span className="num font-mono text-ink-primary">₹{fmt(r.entry_price)}</span>,
    sort: r => r.entry_price, align: 'right',
  },
  {
    key: 'stop_price', header: 'Stop ₹',
    cell: r => <span className="num font-mono text-loss">₹{fmt(r.stop_price)}</span>,
    sort: r => r.stop_price, align: 'right',
  },
  {
    key: 'stop_pct', header: 'Stop %',
    cell: r => <span className="num font-mono text-loss">{fmtPct(r.stop_pct)}</span>,
    sort: r => r.stop_pct, align: 'right',
  },
  {
    key: 'at_risk', header: 'At Risk',
    cell: r => <span className="num font-mono text-warn">{fmtCurrency(r.at_risk)}</span>,
    sort: r => r.at_risk, align: 'right',
  },
]

function WeightBar({ label, value, color }: { label: string; value: number; color: string }) {
  const pct = Math.max(0, Math.min(100, value * 100))
  return (
    <div className="flex items-center gap-3">
      <span className="w-32 shrink-0 font-mono text-xs font-semibold text-ink-primary">{label}</span>
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-bg-overlay">
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
      <span className="num w-12 shrink-0 text-right font-mono text-xs text-ink-secondary">
        {fmtPct(value * 100, 1)}
      </span>
    </div>
  )
}

function NumberInput({
  label, value, onChange, min, max, step, suffix,
}: {
  label: string; value: number; onChange: (v: number) => void
  min?: number; max?: number; step?: number; suffix?: string
}) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-2xs font-semibold uppercase tracking-widest text-ink-secondary">{label}</label>
      <div className="flex items-center gap-1 rounded border border-border bg-bg-elevated px-3 py-1.5">
        <input
          type="number"
          value={value}
          min={min}
          max={max}
          step={step ?? 1}
          onChange={e => onChange(+e.target.value)}
          className="w-full bg-transparent num font-mono text-sm text-ink-primary focus:outline-none"
        />
        {suffix && <span className="shrink-0 text-xs text-ink-disabled">{suffix}</span>}
      </div>
    </div>
  )
}

export default function PositionSizing() {
  const [searchParams] = useSearchParams()

  const urlTickers = useMemo(
    () => searchParams.get('tickers')?.split(',').filter(Boolean) ?? [],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  )
  const urlML = searchParams.get('ml') === '1'

  const [selected, setSelected]     = useState<string[]>(urlTickers)
  const [result, setResult]         = useState<OptimizeResult | null>(null)
  const [useMLSignals, setUseML]    = useState(urlML)

  // Form state
  const [capital, setCapital]     = useState(100000)
  const [targetRet, setTarget]    = useState(12)
  const [riskApt, setRisk]        = useState(5)
  const [allowShort, setShort]    = useState(false)
  const [investMode, setMode]     = useState<'lump' | 'dca'>('lump')
  const [dcaMonths, setDca]       = useState(6)
  const [stopK, setStopK]         = useState(2.0)

  const optMut = useMutation({
    mutationFn: optimizePortfolio,
    onSuccess:  d => setResult(d),
  })

  const running = optMut.isPending

  function toggle(sym: string) {
    setSelected(prev =>
      prev.includes(sym) ? prev.filter(s => s !== sym) : [...prev, sym]
    )
    setResult(null)
  }

  function runOptimize() {
    optMut.mutate({
      tickers:               selected,
      capital,
      user_target_annual:    targetRet / 100,
      risk_appetite_monthly: riskApt / 100,
      allow_short:           allowShort,
      invest_mode:           investMode,
      dca_months:            dcaMonths,
      stop_loss_k:           stopK,
      use_ml_signals:        useMLSignals,
    })
  }

  const weightData = useMemo(() => {
    if (!result) return []
    return Object.entries(result.weights)
      .sort(([, a], [, b]) => b - a)
      .map(([ticker, w], i) => ({ ticker, weight: w, color: PALETTE[i % PALETTE.length] }))
  }, [result])

  const dcaCols = useMemo((): Column<DCARow>[] => {
    if (!result?.dca_schedule.length) return []
    return Object.keys(result.dca_schedule[0]).map(k => ({
      key: k,
      header: k,
      cell: r => {
        const v = r[k]
        if (k === 'Month') return <span className="font-mono text-xs text-ink-primary">{String(v)}</span>
        return <span className="num font-mono text-xs text-ink-secondary">{fmtCurrency(v as number)}</span>
      },
      sort: r => typeof r[k] === 'number' ? r[k] as number : String(r[k]),
      align: k === 'Month' ? 'left' : 'right',
    }))
  }, [result])

  return (
    <div className="flex h-[calc(100vh-104px)] gap-5 animate-fade-up">
      {/* ── Left: Stock browser ─────────────────────────────────── */}
      <StockBrowser
        className="w-[300px] shrink-0"
        selected={selected}
        onToggle={toggle}
      />

      {/* ── Right panel ─────────────────────────────────────────── */}
      <div className="flex flex-1 flex-col gap-4 overflow-hidden">
        {/* Selected + config */}
        <div className="rounded-md border border-border bg-bg-surface p-4">
          {/* Selected chips */}
          <div className="mb-4">
            <div className="mb-2 flex items-center justify-between">
              <h3 className="text-xs font-semibold uppercase tracking-widest text-ink-secondary">
                Selected ({selected.length})
              </h3>
              {selected.length > 0 && (
                <button onClick={() => { setSelected([]); setResult(null) }}
                  className="text-xs text-ink-muted hover:text-loss transition-colors">
                  Clear all
                </button>
              )}
            </div>
            {selected.length === 0 ? (
              <p className="text-xs text-ink-disabled">Add stocks from the panel on the left.</p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {selected.map((sym, i) => (
                  <button key={sym} onClick={() => toggle(sym)}
                    className="flex items-center gap-1.5 rounded-sm border px-2.5 py-1 font-mono text-xs font-semibold transition-colors hover:opacity-70"
                    style={{ borderColor: PALETTE[i % PALETTE.length] + '60', background: PALETTE[i % PALETTE.length] + '18', color: PALETTE[i % PALETTE.length] }}
                  >
                    {sym} <X size={10} />
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Config grid */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-7">
            <NumberInput label="Capital" value={capital} onChange={setCapital} min={1000} step={10000} suffix="₹" />
            <NumberInput label="Target Return" value={targetRet} onChange={setTarget} min={0} max={100} step={0.5} suffix="% / yr" />
            <NumberInput label="Risk Appetite" value={riskApt} onChange={setRisk} min={0} max={50} step={0.5} suffix="% / mo" />
            <NumberInput label="Stop Loss K" value={stopK} onChange={setStopK} min={0.5} max={5} step={0.1} suffix="σ" />

            {/* Allow short toggle */}
            <div className="flex flex-col gap-1">
              <label className="text-2xs font-semibold uppercase tracking-widest text-ink-secondary">Allow Short</label>
              <button
                onClick={() => setShort(p => !p)}
                className={cn(
                  'flex h-[34px] items-center gap-2 rounded border px-3 text-xs font-semibold transition-colors',
                  allowShort
                    ? 'border-loss/40 bg-[rgba(248,81,73,.1)] text-loss'
                    : 'border-border bg-bg-elevated text-ink-secondary hover:bg-bg-overlay',
                )}
              >
                <span className={cn('h-3.5 w-3.5 rounded-full border-2 transition-colors',
                  allowShort ? 'border-loss bg-loss' : 'border-ink-disabled')} />
                {allowShort ? 'Yes' : 'No'}
              </button>
            </div>

            {/* Invest mode */}
            <div className="flex flex-col gap-1">
              <label className="text-2xs font-semibold uppercase tracking-widest text-ink-secondary">Mode</label>
              <div className="flex gap-1 rounded border border-border bg-bg-elevated p-0.5">
                {(['lump', 'dca'] as const).map(m => (
                  <button key={m} onClick={() => setMode(m)}
                    className={cn('flex-1 rounded py-1 text-xs font-semibold transition-colors',
                      investMode === m ? 'bg-accent text-white' : 'text-ink-secondary hover:text-ink-primary'
                    )}>
                    {m === 'lump' ? 'Lump' : 'DCA'}
                  </button>
                ))}
              </div>
            </div>

            {investMode === 'dca' && (
              <NumberInput label="DCA Months" value={dcaMonths} onChange={setDca} min={1} max={36} />
            )}

            {/* ML signals toggle */}
            <div className="flex flex-col gap-1">
              <label className="text-2xs font-semibold uppercase tracking-widest text-ink-secondary">
                ML Signals
              </label>
              <button
                onClick={() => setUseML(p => !p)}
                className={cn(
                  'flex h-[34px] items-center gap-2 rounded border px-3 text-xs font-semibold transition-colors',
                  useMLSignals
                    ? 'border-accent/40 bg-[rgba(56,139,253,.1)] text-accent'
                    : 'border-border bg-bg-elevated text-ink-secondary hover:bg-bg-overlay',
                )}
              >
                <Brain size={12} className={useMLSignals ? 'text-accent' : 'text-ink-disabled'} />
                {useMLSignals ? 'On' : 'Off'}
              </button>
            </div>
          </div>

          {useMLSignals && (
            <p className="mt-2 text-2xs text-ink-muted">
              ML signal views will be fetched / loaded from cache and blended as a 4th signal
              (45% regime + 30% momentum + 20% ML) before Black-Litterman optimization.
            </p>
          )}
        </div>

        {/* Run button */}
        <div className="flex justify-end">
          <button
            disabled={selected.length < 2 || running}
            onClick={runOptimize}
            className={cn(
              'flex items-center gap-2 rounded border px-6 py-2.5 text-sm font-semibold transition-all',
              selected.length < 2 || running
                ? 'cursor-not-allowed border-border text-ink-disabled'
                : 'border-accent bg-accent text-white hover:bg-accent/90',
            )}
          >
            {running
              ? <><Spinner size={14} /> Optimizing…</>
              : <><Layers size={14} /> Optimize Portfolio</>}
          </button>
          {selected.length < 2 && selected.length > 0 && (
            <p className="ml-3 self-center text-xs text-ink-muted">Select at least 2 stocks</p>
          )}
        </div>

        {optMut.isError && (
          <ErrorState message={(optMut.error as Error).message} />
        )}

        {running && (
          <div className="flex flex-1 flex-col items-center justify-center gap-3">
            <Spinner size={28} />
            <p className="text-sm text-ink-muted">
              Running HMM regime detection, Black-Litterman MVO, Monte Carlo VaR…
            </p>
          </div>
        )}

        {/* Results */}
        {result && !running && (
          <div className="flex-1 space-y-4 overflow-y-auto">
            {/* ML adjusted banner */}
            {result.ml_adjusted && (
              <div className="flex items-center gap-2.5 rounded-md border border-accent/30 bg-[rgba(56,139,253,.07)] px-4 py-2.5">
                <Brain size={14} className="shrink-0 text-accent" />
                <p className="text-xs text-ink-secondary">
                  ML signal views applied — return estimates blended{' '}
                  <span className="font-semibold text-ink-primary">
                    45% regime + 30% momentum + 20% ML
                  </span>{' '}
                  before Black-Litterman optimization.
                </p>
              </div>
            )}

            {/* Regime warnings */}
            {result.warnings.length > 0 && (
              <div className="rounded-md border border-warn/30 bg-[rgba(210,153,34,.08)] p-4">
                <div className="mb-3 flex items-center gap-2">
                  <AlertTriangle size={14} className="text-warn" />
                  <span className="text-xs font-semibold uppercase tracking-widest text-warn">
                    Regime Shift Warnings
                  </span>
                </div>
                <div className="flex flex-wrap gap-2">
                  {result.warnings.map((w: RegimeWarning) => (
                    <div key={w.ticker}
                      className="flex items-center gap-2 rounded border border-warn/25 bg-[rgba(210,153,34,.1)] px-3 py-1.5">
                      <span className="font-mono text-xs font-semibold text-accent">{w.ticker}</span>
                      <span className="text-xs text-ink-muted">
                        {w.current} → {w.shift_to}
                      </span>
                      <span className="num font-mono text-xs font-semibold text-warn">
                        {fmtPct(w.probability * 100, 0)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Metrics grid */}
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
              <MetricCard size="sm" label="Annual Return"
                value={fmtPct(result.metrics.annual_return)}
                accent={result.metrics.annual_return >= 0 ? 'gain' : 'loss'}
                tooltip="Expected portfolio return over a full year, blended from HMM regime signal (55%), momentum (35%), and your target return — then shrunk via James-Stein and blended with market equilibrium through Black-Litterman." />
              <MetricCard size="sm" label="Annual Vol"
                value={fmtPct(result.metrics.annual_vol)}
                tooltip="Annualised standard deviation of portfolio returns, derived from DCC-GARCH one-step-ahead variance forecasts. Measures how much the portfolio value swings year-to-year." />
              <MetricCard size="sm" label="Sharpe Ratio"
                value={fmt(result.metrics.sharpe)}
                accent={result.metrics.sharpe >= 1 ? 'gain' : result.metrics.sharpe >= 0.5 ? 'warn' : 'loss'}
                tooltip="Return above the risk-free rate (7%) per unit of annual volatility. Above 1.0 is strong; 0.5–1.0 is acceptable; below 0.5 means you are not being adequately compensated for the risk taken." />
              <MetricCard size="sm" label="Monthly VaR 95%"
                value={fmtPct(result.metrics.monthly_var_95)} accent="warn"
                tooltip="Parametric Value-at-Risk: the maximum monthly loss you would expect in 19 out of 20 months (95th percentile), computed from GARCH-forecasted volatility scaled to a 21-day horizon." />
              <MetricCard size="sm" label="MC VaR"
                value={fmtPct(result.metrics.mc_var)} accent="loss"
                tooltip="Monte Carlo Value-at-Risk at 95% confidence over 21 days. Uses block-bootstrap resampling and a Student-t fit — whichever gives the more conservative (larger loss) estimate is reported." />
              <MetricCard size="sm" label="MC CVaR"
                value={fmtPct(result.metrics.mc_cvar)} accent="loss"
                tooltip="Conditional VaR (Expected Shortfall): the average loss across the worst 5% of 21-day Monte Carlo scenarios. More conservative than VaR because it captures how bad the tail actually is, not just the threshold." />
            </div>

            {/* Weight distribution */}
            <div className="rounded-md border border-border bg-bg-surface p-5 shadow-card">
              <h3 className="mb-4 text-xs font-semibold uppercase tracking-widest text-ink-secondary">
                Portfolio Weights
              </h3>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                {weightData.map(w => (
                  <WeightBar key={w.ticker} label={w.ticker} value={w.weight} color={w.color} />
                ))}
              </div>
            </div>

            {/* Stop-loss & allocation table */}
            <div className="rounded-md border border-border bg-bg-surface shadow-card">
              <div className="flex items-center justify-between border-b border-border px-5 py-3">
                <h3 className="text-xs font-semibold uppercase tracking-widest text-ink-secondary">
                  Allocation & Stop-Loss
                </h3>
                <span className="num font-mono text-xs text-ink-muted">
                  Capital: {fmtCurrency(capital)}
                </span>
              </div>
              <div className="p-4">
                <DataTable
                  columns={STOP_COLS}
                  data={result.stop_table}
                  keyFn={r => r.ticker}
                />
              </div>
            </div>

            {/* DCA schedule */}
            {investMode === 'dca' && result.dca_schedule.length > 0 && (
              <div className="rounded-md border border-border bg-bg-surface shadow-card">
                <div className="border-b border-border px-5 py-3">
                  <h3 className="text-xs font-semibold uppercase tracking-widest text-ink-secondary">
                    DCA Deployment Schedule
                  </h3>
                </div>
                <div className="p-4">
                  <DataTable
                    columns={dcaCols}
                    data={result.dca_schedule}
                    keyFn={r => String(r['Month'])}
                  />
                </div>
              </div>
            )}

            {/* DCC params footer */}
            <div className="flex gap-4 rounded-md border border-border bg-bg-surface px-5 py-3">
              <span className="text-xs text-ink-muted">DCC-GARCH params:</span>
              <span className="num font-mono text-xs text-ink-secondary">
                α = {result.dcc_a.toFixed(4)}
              </span>
              <span className="num font-mono text-xs text-ink-secondary">
                β = {result.dcc_b.toFixed(4)}
              </span>
            </div>
          </div>
        )}

        {!result && !running && selected.length === 0 && (
          <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center">
            <Layers size={36} className="text-ink-disabled" />
            <p className="text-sm text-ink-disabled">
              Select stocks, configure your parameters, and run the optimizer.
            </p>
            <p className="max-w-sm text-xs text-ink-disabled">
              Uses Black-Litterman MVO, HMM regime detection, DCC-GARCH correlations,
              and Monte Carlo VaR.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
