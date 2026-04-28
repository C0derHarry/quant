import { useState, useMemo, useRef } from 'react'
import { createPortal } from 'react-dom'
import { useSearchParams } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import {
  optimizePortfolio, getRiskParity, getEfficientFrontier, runWalkForward,
  runSensitivity, getRegimes,
  type OptimizeResult, type StopRow, type RegimeWarning, type DCARow,
  type RiskParityResult, type FrontierResult, type WalkForwardResult,
  type SensitivityResult, type RegimeBar, type RegimeStat,
} from '../lib/api'
import Spinner, { ErrorState } from '../components/ui/Spinner'
import MetricCard from '../components/ui/MetricCard'
import Badge, { regimeBadge } from '../components/ui/Badge'
import DataTable, { Column } from '../components/ui/DataTable'
import StockBrowser from '../components/ui/StockBrowser'
import {
  X, AlertTriangle, Play, Layers, ChevronDown, Brain,
  TrendingUp, TrendingDown, Activity, BarChart2,
} from 'lucide-react'
import { cn, fmt, fmtPct, fmtCurrency } from '../lib/utils'
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  Cell, ScatterChart, Scatter, ZAxis, ComposedChart, Area, Line,
  ReferenceLine, ReferenceArea,
} from 'recharts'

const PALETTE = ['#388BFD', '#3FB950', '#F85149', '#D29922', '#BC8CFF', '#56D364', '#E3B341', '#79C0FF']
const REGIME_FILL: Record<string, string> = { Bull: '#3FB950', Bear: '#F85149', Sideways: '#D29922' }

// ── colour helpers ────────────────────────────────────────────────────────────

function lerpColor(a: string, b: string, t: number): string {
  const ah = parseInt(a.slice(1), 16), bh = parseInt(b.slice(1), 16)
  const [ar, ag, ab2] = [(ah >> 16) & 0xFF, (ah >> 8) & 0xFF, ah & 0xFF]
  const [br, bg, bb]  = [(bh >> 16) & 0xFF, (bh >> 8) & 0xFF, bh & 0xFF]
  const r = Math.round(ar + (br - ar) * t)
  const g = Math.round(ag + (bg - ag) * t)
  const b2 = Math.round(ab2 + (bb - ab2) * t)
  return `#${r.toString(16).padStart(2,'0')}${g.toString(16).padStart(2,'0')}${b2.toString(16).padStart(2,'0')}`
}

function sharpeColor(s: number): string {
  const c = Math.max(0, Math.min(1.5, s))
  return c <= 1.0
    ? lerpColor('#F85149', '#D29922', c)
    : lerpColor('#D29922', '#3FB950', (c - 1.0) / 0.5)
}

function groupRegimeSpans(series: RegimeBar[]) {
  if (!series.length) return []
  const spans: { start: string; end: string; regime: string }[] = []
  let cur = series[0].regime, start = series[0].date
  for (let i = 1; i < series.length; i++) {
    if (series[i].regime !== cur) {
      spans.push({ start, end: series[i - 1].date, regime: cur })
      cur = series[i].regime; start = series[i].date
    }
  }
  spans.push({ start, end: series[series.length - 1].date, regime: cur })
  return spans
}

// ── field-quality helpers ─────────────────────────────────────────────────────

type Accent = 'neutral' | 'warn' | 'loss'

function fieldAccent(v: number, good: [number, number], warn: [number, number]): Accent {
  if (v >= good[0] && v <= good[1]) return 'neutral'
  if (v >= warn[0] && v <= warn[1]) return 'warn'
  return 'loss'
}

const ACCENT_BORDER: Record<Accent, string> = {
  neutral: 'border-border',
  warn:    'border-warn/50',
  loss:    'border-loss/60',
}
const ACCENT_LABEL: Record<Accent, string> = {
  neutral: 'text-ink-secondary',
  warn:    'text-warn',
  loss:    'text-loss',
}

// ── help tooltip ──────────────────────────────────────────────────────────────

function HelpTooltip({ text }: { text: string }) {
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null)
  const ref = useRef<HTMLButtonElement>(null)

  function show() {
    if (!ref.current) return
    const r = ref.current.getBoundingClientRect()
    const flipLeft = r.right + 272 > window.innerWidth
    setPos({ x: flipLeft ? r.left - 272 : r.right + 8, y: r.top - 4 })
  }

  return (
    <>
      <button ref={ref} type="button" tabIndex={-1}
        onMouseEnter={show} onMouseLeave={() => setPos(null)}
        className="inline-flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-full border border-ink-disabled/40 text-[9px] font-bold text-ink-disabled transition-colors hover:border-ink-secondary hover:text-ink-secondary focus:outline-none">
        ?
      </button>
      {pos && createPortal(
        <div style={{ position: 'fixed', left: pos.x, top: pos.y, zIndex: 9999, maxWidth: 264 }}
          className="pointer-events-none rounded-md border border-border bg-bg-elevated px-3 py-2 text-xs leading-relaxed text-ink-secondary shadow-xl">
          {text}
        </div>,
        document.body,
      )}
    </>
  )
}

// ── shared sub-components ─────────────────────────────────────────────────────

function WeightBar({ label, value, color }: { label: string; value: number; color: string }) {
  const pct = Math.max(0, Math.min(100, value * 100))
  return (
    <div className="flex items-center gap-3">
      <span className="w-32 shrink-0 font-mono text-xs font-semibold text-ink-primary">{label}</span>
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-bg-overlay">
        <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="num w-12 shrink-0 text-right font-mono text-xs text-ink-secondary">{fmtPct(value * 100, 1)}</span>
    </div>
  )
}

function NumberInput({ label, value, onChange, min, max, step, suffix, accent = 'neutral', hint }: {
  label: string; value: number; onChange: (v: number) => void
  min?: number; max?: number; step?: number; suffix?: string
  accent?: Accent; hint?: string
}) {
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center gap-1.5">
        <label className={cn('text-2xs font-semibold uppercase tracking-widest transition-colors', ACCENT_LABEL[accent])}>
          {label}
        </label>
        {hint && <HelpTooltip text={hint} />}
      </div>
      <div className={cn('flex items-center gap-1 rounded border bg-bg-elevated px-3 py-1.5 transition-colors', ACCENT_BORDER[accent])}>
        <input type="number" value={value} min={min} max={max} step={step ?? 1}
          onChange={e => onChange(+e.target.value)}
          className="w-full bg-transparent num font-mono text-sm text-ink-primary focus:outline-none" />
        {suffix && <span className="shrink-0 text-xs text-ink-disabled">{suffix}</span>}
      </div>
    </div>
  )
}

// ── Efficient Frontier chart ──────────────────────────────────────────────────

function FrontierChart({ data, rpWeights }: { data: FrontierResult; rpWeights: Record<string, number> | null }) {
  const frontierDots = data.frontier.map(p => ({ x: p.vol, y: p.ret, sharpe: p.sharpe }))
  const maxS   = [{ x: data.max_sharpe.vol, y: data.max_sharpe.ret, label: 'Max Sharpe' }]
  const minV   = [{ x: data.min_var.vol,    y: data.min_var.ret,    label: 'Min Variance' }]

  const CustomTooltip = ({ active, payload }: any) => {
    if (!active || !payload?.length) return null
    const d = payload[0].payload
    return (
      <div className="rounded border border-border bg-bg-elevated p-2 text-xs shadow-lg">
        {d.label && <p className="mb-1 font-semibold text-ink-primary">{d.label}</p>}
        <p className="text-ink-muted">Vol: <span className="font-mono text-ink-primary">{d.x?.toFixed(1)}%</span></p>
        <p className="text-ink-muted">Return: <span className="font-mono text-ink-primary">{d.y?.toFixed(1)}%</span></p>
        {d.sharpe != null && <p className="text-ink-muted">Sharpe: <span className="font-mono text-ink-primary">{d.sharpe?.toFixed(2)}</span></p>}
      </div>
    )
  }

  return (
    <div className="rounded-md border border-border bg-bg-surface p-5 shadow-card">
      <p className="mb-3 text-2xs font-semibold uppercase tracking-[0.12em] text-ink-disabled">
        Efficient Frontier (Markowitz Bullet)
      </p>
      <ResponsiveContainer width="100%" height={220}>
        <ScatterChart margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#30363D" />
          <XAxis dataKey="x" type="number" name="Vol" unit="%" tick={{ fontSize: 10 }} domain={['auto', 'auto']} label={{ value: 'Annual Vol %', position: 'insideBottom', offset: -4, style: { fontSize: 10, fill: '#6E7681' } }} />
          <YAxis dataKey="y" type="number" name="Return" unit="%" tick={{ fontSize: 10 }} domain={['auto', 'auto']} label={{ value: 'Annual Return %', angle: -90, position: 'insideLeft', style: { fontSize: 10, fill: '#6E7681' } }} />
          <ZAxis range={[28, 28]} />
          <Tooltip content={<CustomTooltip />} cursor={{ strokeDasharray: '3 3' }} />
          <Scatter name="Frontier" data={frontierDots} fill="#484F58" fillOpacity={0.5} />
          <Scatter name="Max Sharpe" data={maxS} fill="#388BFD" shape="star" />
          <Scatter name="Min Variance" data={minV} fill="#3FB950" />
        </ScatterChart>
      </ResponsiveContainer>
      <div className="mt-2 flex flex-wrap gap-4 justify-center text-2xs">
        <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-[#484F58]" />Frontier</span>
        <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-accent" />Max Sharpe ({data.max_sharpe.sharpe.toFixed(2)})</span>
        <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-gain" />Min Variance ({data.min_var.sharpe.toFixed(2)})</span>
      </div>
    </div>
  )
}

// ── Equity curve chart ────────────────────────────────────────────────────────

function EquityCurveChart({ data }: { data: WalkForwardResult }) {
  const thinned = data.equity_curve.filter((_, i) => i % 3 === 0 || i === data.equity_curve.length - 1)

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (!active || !payload?.length) return null
    return (
      <div className="rounded border border-border bg-bg-elevated p-2 text-xs shadow-lg">
        <p className="mb-1 font-mono text-ink-primary">{label}</p>
        {payload.map((p: any) => (
          <p key={p.dataKey} style={{ color: p.color }} className="font-mono">
            {p.name}: {p.value?.toFixed(1)}
          </p>
        ))}
      </div>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={260}>
      <ComposedChart data={thinned} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
        <defs>
          <linearGradient id="equityFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#388BFD" stopOpacity={0.2} />
            <stop offset="95%" stopColor="#388BFD" stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#30363D" />
        <XAxis dataKey="date" tick={{ fontSize: 9 }} interval={Math.floor(thinned.length / 8)} />
        <YAxis tick={{ fontSize: 10 }} domain={['auto', 'auto']} />
        <Tooltip content={<CustomTooltip />} />
        <ReferenceLine y={100} stroke="#484F58" strokeDasharray="3 3" />
        <Area type="monotone" dataKey="value" name="Portfolio" stroke="#388BFD" fill="url(#equityFill)" strokeWidth={1.5} dot={false} />
        <Line type="monotone" dataKey="benchmark" name="Nifty 50" stroke="#484F58" strokeDasharray="4 2" strokeWidth={1} dot={false} />
      </ComposedChart>
    </ResponsiveContainer>
  )
}

// ── Regime chart ──────────────────────────────────────────────────────────────

function RegimeChart({ series, ticker }: { series: RegimeBar[]; ticker: string }) {
  // Do NOT thin — ReferenceArea x1/x2 must exactly match dates in the chart data.
  // 2 years of daily points (~500) is fine for Recharts performance.
  const spans = groupRegimeSpans(series)

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (!active || !payload?.length) return null
    const d = payload[0]?.payload
    return (
      <div className="rounded border border-border bg-bg-elevated p-2 text-xs shadow-lg">
        <p className="mb-1 font-mono text-ink-primary">{label}</p>
        <p className="text-ink-muted">Price: <span className="font-mono text-ink-primary">₹{d?.price?.toFixed(2)}</span></p>
        <p className="text-ink-muted">Regime: <span style={{ color: REGIME_FILL[d?.regime] ?? '#888' }} className="font-semibold">{d?.regime}</span></p>
      </div>
    )
  }

  return (
    <div className="rounded-md border border-border bg-bg-surface p-5 shadow-card">
      <p className="mb-3 text-2xs font-semibold uppercase tracking-[0.12em] text-ink-disabled">
        {ticker} — HMM Regime History
      </p>
      <ResponsiveContainer width="100%" height={260}>
        <ComposedChart data={series} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#30363D" />
          <XAxis dataKey="date" tick={{ fontSize: 9 }} interval={Math.floor(series.length / 8)} />
          <YAxis tick={{ fontSize: 10 }} domain={['auto', 'auto']} />
          <Tooltip content={<CustomTooltip />} />
          {spans.map((sp, i) => (
            <ReferenceArea key={i} x1={sp.start} x2={sp.end}
              fill={REGIME_FILL[sp.regime] ?? '#888'} fillOpacity={0.08} />
          ))}
          <Line type="monotone" dataKey="price" name="Price" stroke="#388BFD" strokeWidth={1.5} dot={false} />
        </ComposedChart>
      </ResponsiveContainer>
      <div className="mt-2 flex flex-wrap gap-4 justify-center text-2xs text-ink-muted">
        {Object.entries(REGIME_FILL).map(([label, color]) => (
          <span key={label} className="flex items-center gap-1.5">
            <span className="h-2 w-4 rounded" style={{ background: color, opacity: 0.5 }} />{label}
          </span>
        ))}
      </div>
    </div>
  )
}

// ── Sensitivity heatmap ───────────────────────────────────────────────────────

function SensitivityHeatmap({ data }: { data: SensitivityResult }) {
  const allSharpes = data.sharpe_grid.flat()
  const maxS = Math.max(...allSharpes)
  const hasVariance = maxS - Math.min(...allSharpes) > 0.1
  const interpretation = hasVariance
    ? maxS > 1.2
      ? allSharpes.filter(s => s > maxS * 0.85).length > allSharpes.length * 0.4
        ? 'Broad plateau — strategy appears robust across parameter variations.'
        : 'Sharp peak — strategy may be fragile, only works in a narrow parameter band.'
      : 'Low Sharpe across all parameters — consider revising the strategy.'
    : 'Sharpe is uniform — parameters have little impact on this strategy.'

  return (
    <div className="rounded-md border border-border bg-bg-surface p-5 shadow-card">
      <p className="mb-3 text-2xs font-semibold uppercase tracking-[0.12em] text-ink-disabled">
        Parameter Sensitivity (Sharpe Ratio)
      </p>
      {/* Col headers */}
      <div className="mb-1 ml-16 grid text-center text-2xs text-ink-muted" style={{ gridTemplateColumns: `repeat(${data.x_values.length}, 1fr)` }}>
        {data.x_values.map(v => <span key={v}>{v}</span>)}
      </div>
      <p className="mb-1 ml-16 text-2xs text-center text-ink-disabled">{data.x_param}</p>
      {data.sharpe_grid.map((row, ri) => (
        <div key={ri} className="flex items-center gap-1 mb-1">
          <span className="w-14 shrink-0 text-right font-mono text-2xs text-ink-muted pr-2">
            {data.y_values[ri]}
          </span>
          <div className="grid flex-1 gap-1" style={{ gridTemplateColumns: `repeat(${data.x_values.length}, 1fr)` }}>
            {row.map((s, ci) => (
              <div key={ci} className="rounded px-1 py-2 text-center font-mono text-2xs font-semibold transition-all"
                style={{ background: sharpeColor(s) + '33', border: `1px solid ${sharpeColor(s)}44`, color: sharpeColor(s) }}>
                {s.toFixed(2)}
              </div>
            ))}
          </div>
        </div>
      ))}
      <p className="mt-2 ml-16 text-2xs text-ink-disabled">{data.y_param}</p>
      <p className="mt-3 rounded border border-border bg-bg-elevated px-3 py-2 text-xs text-ink-secondary">
        {interpretation}
      </p>
    </div>
  )
}

// ── STOP table columns ────────────────────────────────────────────────────────

const STOP_COLS: Column<StopRow>[] = [
  { key: 'ticker', header: 'Ticker',
    cell: r => (
      <div className="flex items-center gap-2">
        <span className="font-mono text-sm font-semibold text-accent">{r.ticker}</span>
        {r.is_short && <Badge variant="loss" className="text-2xs py-0">SHORT</Badge>}
      </div>
    ), sort: r => r.ticker },
  { key: 'regime', header: 'Regime',
    cell: r => r.regime === '—' ? <span className="text-ink-disabled">—</span> : <Badge variant={regimeBadge(r.regime)}>{r.regime}</Badge>,
    sort: r => r.regime },
  { key: 'weight', header: 'Weight',
    cell: r => <span className="num font-mono text-ink-primary">{fmtPct(r.weight)}</span>,
    sort: r => r.weight, align: 'right' },
  { key: 'allocation', header: 'Allocated',
    cell: r => <span className="num font-mono text-ink-secondary">{fmtCurrency(r.allocation)}</span>,
    sort: r => r.allocation, align: 'right' },
  { key: 'shares', header: 'Shares',
    cell: r => <span className="num font-mono text-ink-secondary">{r.shares}</span>,
    sort: r => r.shares, align: 'right' },
  { key: 'entry_price', header: 'Entry ₹',
    cell: r => <span className="num font-mono text-ink-primary">₹{fmt(r.entry_price)}</span>,
    sort: r => r.entry_price, align: 'right' },
  { key: 'stop_price', header: 'Stop ₹',
    cell: r => <span className="num font-mono text-loss">₹{fmt(r.stop_price)}</span>,
    sort: r => r.stop_price, align: 'right' },
  { key: 'stop_pct', header: 'Stop %',
    cell: r => <span className="num font-mono text-loss">{fmtPct(r.stop_pct)}</span>,
    sort: r => r.stop_pct, align: 'right' },
  { key: 'at_risk', header: 'At Risk',
    cell: r => <span className="num font-mono text-warn">{fmtCurrency(r.at_risk)}</span>,
    sort: r => r.at_risk, align: 'right' },
]

// ── Main component ────────────────────────────────────────────────────────────

type PortfolioType = 'max_sharpe' | 'risk_parity' | 'min_variance'
type TabId = 'build' | 'backtest' | 'regimes' | 'sensitivity'

const TABS: { id: TabId; label: string; icon: React.ElementType; tooltip: string }[] = [
  { id: 'build',       label: 'Build',       icon: Layers,    tooltip: 'Construct a portfolio from your selected stocks. Choose Max Sharpe (best risk-adjusted return), Risk Parity (equal risk per stock), or Min Variance (lowest volatility). Defaults are pre-set to sensible values — labels turn red when a setting is outside the recommended range.' },
  { id: 'backtest',    label: 'Backtest',    icon: TrendingUp, tooltip: 'Walk-forward validation: the model is re-optimised on a training window then evaluated on the next unseen test window. Repeating this across N windows gives an honest, unbiased estimate of real-world performance.' },
  { id: 'regimes',     label: 'Regimes',     icon: Activity,  tooltip: 'A Hidden Markov Model reads price history and classifies each day as Bull, Bear, or Sideways. The transition matrix shows how likely each regime is to persist or flip — useful context before you build or backtest.' },
  { id: 'sensitivity', label: 'Sensitivity', icon: BarChart2, tooltip: 'Sweeps ATR stop multiplier and transaction cost across a 5×4 grid and records the Sharpe ratio at each combination. A broad green plateau means the strategy is robust. A single bright cell surrounded by red means performance is fragile and likely overfitted.' },
]

export default function PositionSizing() {
  const [searchParams] = useSearchParams()
  const urlTickers = useMemo(
    () => searchParams.get('tickers')?.split(',').filter(Boolean) ?? [],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  )
  const urlML = searchParams.get('ml') === '1'

  // ── shared state ─────────────────────────────────────────────────
  const [selected, setSelected]   = useState<string[]>(urlTickers)
  const [activeTab, setActiveTab] = useState<TabId>('build')

  // ── Build tab state ───────────────────────────────────────────────
  const [portfolioType, setPortfolioType] = useState<PortfolioType>('max_sharpe')
  const [msResult,  setMsResult]  = useState<OptimizeResult | null>(null)
  const [rpResult,  setRpResult]  = useState<RiskParityResult | null>(null)
  const [frontierResult, setFrontierResult] = useState<FrontierResult | null>(null)
  const [useMLSignals, setUseML]  = useState(urlML)
  const [capital, setCapital]     = useState(100000)
  const [targetRet, setTarget]    = useState(12)
  const [riskApt, setRisk]        = useState(5)
  const [allowShort, setShort]    = useState(false)
  const [investMode, setMode]     = useState<'lump' | 'dca'>('lump')
  const [dcaMonths, setDca]       = useState(6)
  const [stopK, setStopK]         = useState(2.0)

  // ── Backtest tab state ────────────────────────────────────────────
  const [btResult, setBtResult]   = useState<WalkForwardResult | null>(null)
  const [trainMonths, setTrain]   = useState(6)
  const [testMonths, setTest]     = useState(1)
  const [nWindows, setNWindows]   = useState(12)
  const [useMLFilter, setMLFilt]  = useState(false)
  const [useRegFilt, setRegFilt]  = useState(true)

  // ── Regimes tab state ─────────────────────────────────────────────
  const [regimeTicker, setRegimeTicker] = useState<string | null>(null)

  // ── Sensitivity tab state ─────────────────────────────────────────
  const [sensResult, setSensResult] = useState<SensitivityResult | null>(null)

  // ── Current weights (for backtest / sensitivity) ──────────────────
  const currentWeights = useMemo((): Record<string, number> | null => {
    if (portfolioType === 'max_sharpe' && msResult)      return msResult.weights
    if (portfolioType === 'risk_parity' && rpResult)     return rpResult.weights
    if (portfolioType === 'min_variance' && frontierResult) return frontierResult.min_var.weights
    return null
  }, [portfolioType, msResult, rpResult, frontierResult])

  // ── Mutations ─────────────────────────────────────────────────────
  const optMut = useMutation({
    mutationFn: optimizePortfolio,
    onSuccess:  d => { setMsResult(d); triggerFrontier() },
  })
  const rpMut = useMutation({
    mutationFn: getRiskParity,
    onSuccess:  d => { setRpResult(d); triggerFrontier() },
  })
  const feMut = useMutation({
    mutationFn: getEfficientFrontier,
    onSuccess:  d => setFrontierResult(d),
  })
  const btMut = useMutation({
    mutationFn: runWalkForward,
    onSuccess:  d => setBtResult(d),
  })
  const sensMut = useMutation({
    mutationFn: runSensitivity,
    onSuccess:  d => setSensResult(d),
  })

  // ── Regime query ──────────────────────────────────────────────────
  const { data: regimeData, isLoading: regimeLoading, error: regimeError } = useQuery({
    queryKey:  ['regimes', regimeTicker],
    queryFn:   () => getRegimes([regimeTicker!]),
    enabled:   !!regimeTicker,
    staleTime: 30 * 60_000,
  })

  // ── Helpers ───────────────────────────────────────────────────────
  function toggleStock(sym: string) {
    setSelected(prev => prev.includes(sym) ? prev.filter(s => s !== sym) : [...prev, sym])
    setMsResult(null); setRpResult(null); setFrontierResult(null); setBtResult(null); setSensResult(null)
  }

  function triggerFrontier() {
    if (selected.length >= 2) feMut.mutate({ tickers: selected })
  }

  function runBuild() {
    if (portfolioType === 'max_sharpe') {
      optMut.mutate({ tickers: selected, capital, user_target_annual: targetRet / 100,
        risk_appetite_monthly: riskApt / 100, allow_short: allowShort,
        invest_mode: investMode, dca_months: dcaMonths, stop_loss_k: stopK,
        use_ml_signals: useMLSignals })
    } else if (portfolioType === 'risk_parity') {
      rpMut.mutate({ tickers: selected, capital, stop_loss_k: stopK })
    } else {
      feMut.mutate({ tickers: selected })
    }
  }

  function runBacktest() {
    if (!currentWeights) return
    btMut.mutate({
      tickers: selected, weights: currentWeights,
      train_months: trainMonths, test_months: testMonths, n_windows: nWindows,
      use_ml: useMLFilter, use_regimes: useRegFilt,
    })
  }

  function runSens() {
    if (!currentWeights) return
    sensMut.mutate({ tickers: selected, weights: currentWeights })
  }

  const buildRunning = optMut.isPending || rpMut.isPending || feMut.isPending
  const buildError   = optMut.error || rpMut.error || feMut.error

  // ── Weight display data ───────────────────────────────────────────
  const weightData = useMemo(() => {
    const w = portfolioType === 'max_sharpe' ? msResult?.weights
      : portfolioType === 'risk_parity'   ? rpResult?.weights
      : frontierResult?.min_var.weights
    if (!w) return []
    return Object.entries(w).sort(([, a], [, b]) => b - a)
      .map(([ticker, wt], i) => ({ ticker, weight: wt, color: PALETTE[i % PALETTE.length] }))
  }, [portfolioType, msResult, rpResult, frontierResult])

  const displayMetrics = useMemo(() => {
    if (portfolioType === 'max_sharpe' && msResult) return {
      annual_return: msResult.metrics.annual_return,
      annual_vol:    msResult.metrics.annual_vol,
      sharpe:        msResult.metrics.sharpe,
    }
    if (portfolioType === 'risk_parity' && rpResult)  return rpResult.metrics
    if (portfolioType === 'min_variance' && frontierResult) return {
      annual_return: frontierResult.min_var.ret,
      annual_vol:    frontierResult.min_var.vol,
      sharpe:        frontierResult.min_var.sharpe,
    }
    return null
  }, [portfolioType, msResult, rpResult, frontierResult])

  const displayStopTable = useMemo(() => {
    if (portfolioType === 'max_sharpe' && msResult) return msResult.stop_table
    if (portfolioType === 'risk_parity' && rpResult) return rpResult.stop_table
    return null
  }, [portfolioType, msResult, rpResult])

  const hasBuilt = !!(msResult || rpResult || (portfolioType === 'min_variance' && frontierResult))

  const dcaCols = useMemo((): Column<DCARow>[] => {
    if (!msResult?.dca_schedule.length) return []
    return Object.keys(msResult.dca_schedule[0]).map(k => ({
      key: k, header: k,
      cell: r => {
        const v = r[k]
        if (k === 'Month') return <span className="font-mono text-xs text-ink-primary">{String(v)}</span>
        return <span className="num font-mono text-xs text-ink-secondary">{fmtCurrency(v as number)}</span>
      },
      sort: r => typeof r[k] === 'number' ? r[k] as number : String(r[k]),
      align: k === 'Month' ? 'left' : 'right',
    }))
  }, [msResult])

  // ── Tab: Build ────────────────────────────────────────────────────
  function BuildTab() {
    // ── accent computations (live colour feedback) ──────────────────
    const targetAccent = fieldAccent(targetRet, [10, 20], [8, 25])
    const riskAccent   = fieldAccent(riskApt,   [3, 8],   [2, 12])
    const stopAccent   = fieldAccent(stopK,      [1.5, 3], [1, 4])
    const dcaAccent    = fieldAccent(dcaMonths,  [3, 12],  [1, 18])

    const anyOutOfRange = [targetAccent, riskAccent, stopAccent].some(a => a !== 'neutral')

    const METHOD_DESC: Record<string, string> = {
      max_sharpe:   'Best risk-adjusted return. Uses regime detection, GARCH volatility forecasts, and Black-Litterman blending. Recommended for most investors.',
      risk_parity:  'Each stock contributes equal risk to the portfolio. More robust than Max Sharpe when return forecasts are noisy — the Bridgewater All Weather approach.',
      min_variance: 'The lowest-volatility combination of your stocks, regardless of expected returns. Best for capital preservation.',
    }

    return (
      <div className="space-y-4">

        {/* Portfolio type selector */}
        <div className="rounded-md border border-border bg-bg-surface p-4">
          <div className="mb-3">
            <div className="flex items-center gap-1.5 mb-2">
              <p className="text-2xs font-semibold uppercase tracking-widest text-ink-secondary">Portfolio Method</p>
              <HelpTooltip text={METHOD_DESC[portfolioType]} />
            </div>
            <div className="flex gap-2">
              {([
                ['max_sharpe',   'Max Sharpe',   'Best for most investors'],
                ['risk_parity',  'Risk Parity',  'More robust, less tuning'],
                ['min_variance', 'Min Variance', 'Lowest risk'],
              ] as const).map(([id, label, sub]) => (
                <button key={id} onClick={() => setPortfolioType(id)}
                  className={cn('flex flex-col rounded border px-4 py-2.5 text-left transition-all flex-1',
                    portfolioType === id
                      ? 'border-accent/40 bg-[rgba(56,139,253,.1)] text-accent'
                      : 'border-border bg-bg-elevated text-ink-secondary hover:bg-bg-overlay')}>
                  <span className="text-xs font-semibold">{label}</span>
                  <span className="text-2xs text-ink-disabled mt-0.5">{sub}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Selected chips */}
          <div className="mb-4 border-t border-border pt-3">
            <div className="mb-2 flex items-center justify-between">
              <h3 className="text-xs font-semibold uppercase tracking-widest text-ink-secondary">
                Selected ({selected.length})
              </h3>
              {selected.length > 0 && (
                <button onClick={() => { setSelected([]); setMsResult(null); setRpResult(null) }}
                  className="text-xs text-ink-muted hover:text-loss transition-colors">Clear all</button>
              )}
            </div>
            {selected.length === 0
              ? <p className="text-xs text-ink-disabled">Add stocks from the panel on the left.</p>
              : (
                <div className="flex flex-wrap gap-2">
                  {selected.map((sym, i) => (
                    <button key={sym} onClick={() => toggleStock(sym)}
                      className="flex items-center gap-1.5 rounded-sm border px-2.5 py-1 font-mono text-xs font-semibold transition-colors hover:opacity-70"
                      style={{ borderColor: PALETTE[i % PALETTE.length] + '60', background: PALETTE[i % PALETTE.length] + '18', color: PALETTE[i % PALETTE.length] }}>
                      {sym} <X size={10} />
                    </button>
                  ))}
                </div>
              )}
          </div>

          {/* Config (only for max_sharpe) */}
          {portfolioType === 'max_sharpe' && (
            <div className="space-y-3 border-t border-border pt-3">
              {anyOutOfRange && (
                <div className="flex items-center justify-between rounded border border-loss/20 bg-loss/5 px-3 py-2">
                  <span className="text-2xs text-loss">Some settings are outside recommended ranges — results may be unreliable.</span>
                  <button onClick={() => { setTarget(15); setRisk(5); setStopK(2.0) }}
                    className="text-2xs font-semibold text-accent hover:underline ml-3 shrink-0">
                    Reset to recommended
                  </button>
                </div>
              )}
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-7">
                <NumberInput label="Capital" value={capital} onChange={setCapital} min={1000} step={10000} suffix="₹"
                  hint="Total amount to invest" />
                <NumberInput label="Target Return" value={targetRet} onChange={setTarget} min={0} max={100} step={0.5} suffix="% / yr"
                  accent={targetAccent}
                  hint={targetAccent === 'neutral' ? 'Realistic for Indian equities' : targetRet > 20 ? 'Unrealistically high — will over-concentrate' : 'Very conservative — consider 12–18%'} />
                <NumberInput label="Risk Appetite" value={riskApt} onChange={setRisk} min={0} max={50} step={0.5} suffix="% / mo"
                  accent={riskAccent}
                  hint={riskAccent === 'neutral' ? 'Max monthly loss you can tolerate' : riskApt > 8 ? 'Very aggressive allocation' : 'Very tight — may over-constrain'} />
                <NumberInput label="Stop Loss K" value={stopK} onChange={setStopK} min={0.5} max={5} step={0.1} suffix="σ"
                  accent={stopAccent}
                  hint={stopAccent === 'neutral' ? 'Exit if price drops N × daily vol' : stopK < 1.5 ? 'Too tight — expect frequent stops' : 'Too wide — large drawdowns before exit'} />
                <div className="flex flex-col gap-1">
                  <div className="flex items-center gap-1.5">
                    <label className="text-2xs font-semibold uppercase tracking-widest text-ink-secondary">Allow Short</label>
                    <HelpTooltip text="Enables short positions — bet that a stock's price will fall. Increases potential returns but also increases risk. Leave off unless you have a specific bearish thesis." />
                  </div>
                  <button onClick={() => setShort(p => !p)}
                    className={cn('flex h-[34px] items-center gap-2 rounded border px-3 text-xs font-semibold transition-colors',
                      allowShort ? 'border-loss/40 bg-[rgba(248,81,73,.1)] text-loss' : 'border-border bg-bg-elevated text-ink-secondary hover:bg-bg-overlay')}>
                    <span className={cn('h-3.5 w-3.5 rounded-full border-2 transition-colors', allowShort ? 'border-loss bg-loss' : 'border-ink-disabled')} />
                    {allowShort ? 'Yes' : 'No'}
                  </button>
                </div>
                <div className="flex flex-col gap-1">
                  <div className="flex items-center gap-1.5">
                    <label className="text-2xs font-semibold uppercase tracking-widest text-ink-secondary">Mode</label>
                    <HelpTooltip text="Lump Sum deploys all your capital immediately. DCA (Dollar-Cost Averaging) spreads it over equal monthly instalments, reducing the risk of buying at a single bad price point." />
                  </div>
                  <div className="flex gap-1 rounded border border-border bg-bg-elevated p-0.5">
                    {(['lump', 'dca'] as const).map(m => (
                      <button key={m} onClick={() => setMode(m)}
                        className={cn('flex-1 rounded py-1 text-xs font-semibold transition-colors',
                          investMode === m ? 'bg-accent text-white' : 'text-ink-secondary hover:text-ink-primary')}>
                        {m === 'lump' ? 'Lump Sum' : 'DCA'}
                      </button>
                    ))}
                  </div>
                </div>
                {investMode === 'dca' && (
                  <NumberInput label="DCA Months" value={dcaMonths} onChange={setDca} min={1} max={36}
                    accent={dcaAccent}
                    hint={dcaAccent === 'neutral' ? 'Months to spread deployment' : dcaMonths > 12 ? 'Very long — opportunity cost' : 'Short DCA — consider lump sum'} />
                )}
                <div className="flex flex-col gap-1">
                  <div className="flex items-center gap-1.5">
                    <label className="text-2xs font-semibold uppercase tracking-widest text-ink-secondary">ML Signals</label>
                    <HelpTooltip text="Trains a GradientBoosting classifier on RSI, MACD, ATR, and regime features to predict 5-day up probability. Blends its view 20% into Black-Litterman return estimates. Adds ~30 seconds to build time." />
                  </div>
                  <button onClick={() => setUseML(p => !p)}
                    className={cn('flex h-[34px] items-center gap-2 rounded border px-3 text-xs font-semibold transition-colors',
                      useMLSignals ? 'border-accent/40 bg-[rgba(56,139,253,.1)] text-accent' : 'border-border bg-bg-elevated text-ink-secondary hover:bg-bg-overlay')}>
                    <Brain size={12} className={useMLSignals ? 'text-accent' : 'text-ink-disabled'} />
                    {useMLSignals ? 'On' : 'Off'}
                  </button>
                </div>
              </div>
            </div>
          )}

          {portfolioType === 'risk_parity' && (
            <div className="flex gap-3 border-t border-border pt-3">
              <NumberInput label="Capital" value={capital} onChange={setCapital} min={1000} step={10000} suffix="₹"
                hint="Total amount to invest" />
              <NumberInput label="Stop Loss K" value={stopK} onChange={setStopK} min={0.5} max={5} step={0.1} suffix="σ"
                accent={stopAccent}
                hint={stopAccent === 'neutral' ? 'Exit threshold in daily vol units' : stopK < 1.5 ? 'Too tight' : 'Too wide'} />
            </div>
          )}

          {portfolioType === 'min_variance' && (
            <p className="border-t border-border pt-3 text-xs text-ink-disabled">
              No additional parameters — just select stocks and build.
            </p>
          )}
        </div>

        {/* Run button */}
        <div className="flex justify-end">
          <button disabled={selected.length < 2 || buildRunning} onClick={runBuild}
            className={cn('flex items-center gap-2 rounded border px-6 py-2.5 text-sm font-semibold transition-all',
              selected.length < 2 || buildRunning
                ? 'cursor-not-allowed border-border text-ink-disabled'
                : 'border-accent bg-accent text-white hover:bg-accent/90')}>
            {buildRunning ? <><Spinner size={14} /> Building…</> : <><Layers size={14} /> Build Portfolio</>}
          </button>
          {selected.length < 2 && selected.length > 0 &&
            <p className="ml-3 self-center text-xs text-ink-muted">Select at least 2 stocks</p>}
        </div>

        {buildError && <ErrorState message={(buildError as Error).message} />}

        {buildRunning && (
          <div className="flex flex-col items-center gap-3 py-8">
            <Spinner size={28} />
            <p className="text-sm text-ink-muted">
              {portfolioType === 'max_sharpe'  ? 'Running HMM regime detection, Black-Litterman MVO, Monte Carlo VaR…'
               : portfolioType === 'risk_parity' ? 'Computing equal risk contribution weights…'
               : 'Sweeping efficient frontier…'}
            </p>
          </div>
        )}

        {/* Results */}
        {hasBuilt && !buildRunning && (
          <div className="space-y-4">
            {/* ML adjusted banner (max sharpe only) */}
            {msResult?.ml_adjusted && (
              <div className="flex items-center gap-2.5 rounded-md border border-accent/30 bg-[rgba(56,139,253,.07)] px-4 py-2.5">
                <Brain size={14} className="shrink-0 text-accent" />
                <p className="text-xs text-ink-secondary">
                  ML signal views applied — return estimates blended{' '}
                  <span className="font-semibold text-ink-primary">45% regime + 30% momentum + 20% ML</span>{' '}
                  before Black-Litterman optimization.
                </p>
              </div>
            )}

            {/* Regime warnings */}
            {msResult && msResult.warnings.length > 0 && (
              <div className="rounded-md border border-warn/30 bg-[rgba(210,153,34,.08)] p-4">
                <div className="mb-3 flex items-center gap-2">
                  <AlertTriangle size={14} className="text-warn" />
                  <span className="text-xs font-semibold uppercase tracking-widest text-warn">Regime Shift Warnings</span>
                </div>
                <div className="flex flex-wrap gap-2">
                  {msResult.warnings.map((w: RegimeWarning) => (
                    <div key={w.ticker} className="flex items-center gap-2 rounded border border-warn/25 bg-[rgba(210,153,34,.1)] px-3 py-1.5">
                      <span className="font-mono text-xs font-semibold text-accent">{w.ticker}</span>
                      <span className="text-xs text-ink-muted">{w.current} → {w.shift_to}</span>
                      <span className="num font-mono text-xs font-semibold text-warn">{fmtPct(w.probability * 100, 0)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Key metrics */}
            {displayMetrics && (
              <div className="grid grid-cols-3 gap-3">
                <MetricCard size="sm" label="Annual Return"
                  value={fmtPct(displayMetrics.annual_return)}
                  accent={displayMetrics.annual_return >= 0 ? 'gain' : 'loss'}
                  tooltip="Expected portfolio return over a full year." />
                <MetricCard size="sm" label="Annual Vol"
                  value={fmtPct(displayMetrics.annual_vol)}
                  tooltip="Annualised standard deviation of portfolio returns." />
                <MetricCard size="sm" label="Sharpe Ratio"
                  value={fmt(displayMetrics.sharpe)}
                  accent={displayMetrics.sharpe >= 1 ? 'gain' : displayMetrics.sharpe >= 0.5 ? 'warn' : 'loss'}
                  tooltip="Return above risk-free rate per unit of volatility. >1.0 is strong." />
              </div>
            )}

            {/* Max Sharpe extra metrics */}
            {portfolioType === 'max_sharpe' && msResult && (
              <div className="grid grid-cols-3 gap-3">
                <MetricCard size="sm" label="Monthly VaR 95%"
                  value={fmtPct(msResult.metrics.monthly_var_95)} accent="warn"
                  tooltip="Parametric VaR: maximum monthly loss in 19 out of 20 months." />
                <MetricCard size="sm" label="MC VaR"
                  value={fmtPct(msResult.metrics.mc_var)} accent="loss"
                  tooltip="Monte Carlo VaR at 95% confidence (block-bootstrap + Student-t)." />
                <MetricCard size="sm" label="MC CVaR"
                  value={fmtPct(msResult.metrics.mc_cvar)} accent="loss"
                  tooltip="Expected Shortfall: average loss in worst 5% of MC scenarios." />
              </div>
            )}

            {/* Risk contributions (risk parity only) */}
            {portfolioType === 'risk_parity' && rpResult && (
              <div className="rounded-md border border-border bg-bg-surface p-5 shadow-card">
                <h3 className="mb-4 text-xs font-semibold uppercase tracking-widest text-ink-secondary">
                  Risk Contributions (Equal Target)
                </h3>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  {Object.entries(rpResult.risk_contributions)
                    .sort(([, a], [, b]) => b - a)
                    .map(([ticker, rc], i) => (
                      <WeightBar key={ticker} label={ticker} value={rc} color={PALETTE[i % PALETTE.length]} />
                    ))}
                </div>
              </div>
            )}

            {/* Weights */}
            {weightData.length > 0 && (
              <div className="rounded-md border border-border bg-bg-surface p-5 shadow-card">
                <h3 className="mb-4 text-xs font-semibold uppercase tracking-widest text-ink-secondary">
                  Portfolio Weights
                </h3>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  {weightData.map(w => <WeightBar key={w.ticker} label={w.ticker} value={w.weight} color={w.color} />)}
                </div>
              </div>
            )}

            {/* Stop table */}
            {displayStopTable && displayStopTable.length > 0 && (
              <div className="rounded-md border border-border bg-bg-surface shadow-card">
                <div className="flex items-center justify-between border-b border-border px-5 py-3">
                  <h3 className="text-xs font-semibold uppercase tracking-widest text-ink-secondary">
                    Allocation & Stop-Loss
                  </h3>
                  <span className="num font-mono text-xs text-ink-muted">Capital: {fmtCurrency(capital)}</span>
                </div>
                <div className="p-4">
                  <DataTable columns={STOP_COLS} data={displayStopTable} keyFn={r => r.ticker} />
                </div>
              </div>
            )}

            {/* DCA schedule (max sharpe only) */}
            {portfolioType === 'max_sharpe' && investMode === 'dca' && msResult && msResult.dca_schedule.length > 0 && (
              <div className="rounded-md border border-border bg-bg-surface shadow-card">
                <div className="border-b border-border px-5 py-3">
                  <h3 className="text-xs font-semibold uppercase tracking-widest text-ink-secondary">DCA Deployment Schedule</h3>
                </div>
                <div className="p-4">
                  <DataTable columns={dcaCols} data={msResult.dca_schedule} keyFn={r => String(r['Month'])} />
                </div>
              </div>
            )}

            {/* DCC params footer (max sharpe only) */}
            {portfolioType === 'max_sharpe' && msResult && (
              <div className="flex gap-4 rounded-md border border-border bg-bg-surface px-5 py-3">
                <span className="text-xs text-ink-muted">DCC-GARCH params:</span>
                <span className="num font-mono text-xs text-ink-secondary">α = {msResult.dcc_a.toFixed(4)}</span>
                <span className="num font-mono text-xs text-ink-secondary">β = {msResult.dcc_b.toFixed(4)}</span>
              </div>
            )}

            {/* Efficient Frontier chart */}
            {frontierResult && (
              <FrontierChart data={frontierResult} rpWeights={rpResult?.weights ?? null} />
            )}
          </div>
        )}

        {!hasBuilt && !buildRunning && selected.length === 0 && (
          <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
            <Layers size={36} className="text-ink-disabled" />
            <p className="text-sm text-ink-disabled">Select stocks, choose a portfolio method, and build.</p>
            <p className="max-w-sm text-xs text-ink-disabled">
              Max Sharpe uses Black-Litterman + DCC-GARCH + HMM.<br />
              Risk Parity uses equal risk contribution (All Weather approach).<br />
              Min Variance picks the lowest-vol point on the efficient frontier.
            </p>
          </div>
        )}
      </div>
    )
  }

  // ── Tab: Backtest ─────────────────────────────────────────────────
  function BacktestTab() {
    const trainAccent = fieldAccent(trainMonths, [4, 9],  [3, 12])
    const testAccent  = fieldAccent(testMonths,  [1, 3],  [1, 4])
    const winAccent   = fieldAccent(nWindows,    [8, 18], [6, 24])

    return (
      <div className="space-y-4">
        {!currentWeights && (
          <div className="rounded-md border border-warn/30 bg-warn/5 px-4 py-3 text-xs text-warn">
            Build a portfolio first to use walk-forward backtesting.
          </div>
        )}

        <div className="rounded-md border border-border bg-bg-surface p-4">
          <div className="flex items-center gap-1.5 mb-3">
            <p className="text-xs font-semibold uppercase tracking-widest text-ink-secondary">Walk-Forward Settings</p>
            <HelpTooltip text="The model is re-optimised from scratch on the train window, then evaluated on the next unseen test window. Repeating this N times gives an honest out-of-sample performance estimate — much harder to overfit than a simple backtest on all historical data." />
          </div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5 mb-3">
            <NumberInput label="Train Window" value={trainMonths} onChange={setTrain} min={3} max={24} suffix="mo"
              accent={trainAccent}
              hint={trainAccent === 'neutral' ? 'Months of history the model learns from' : trainMonths < 4 ? 'Too short — model won\'t generalise' : 'Very long — stale data lowers relevance'} />
            <NumberInput label="Test Window" value={testMonths} onChange={setTest} min={1} max={6} suffix="mo"
              accent={testAccent}
              hint={testAccent === 'neutral' ? 'Months of fresh data per evaluation window' : testMonths > 3 ? 'Long test windows can mask intra-period variation' : ''} />
            <NumberInput label="Windows" value={nWindows} onChange={setNWindows} min={4} max={24}
              accent={winAccent}
              hint={winAccent === 'neutral' ? 'More windows = more reliable estimate' : nWindows < 6 ? 'Too few windows — result is noisy' : 'Very many — runtime will be long'} />
            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-1.5">
                <label className="text-2xs font-semibold uppercase tracking-widest text-ink-secondary">ML Filter</label>
                <HelpTooltip text="Skips entering a position on days when the ML model's predicted probability of a 5-day gain is below 50%. The ML model is re-trained on each train window. Adds ~1 minute per window to runtime." />
              </div>
              <button onClick={() => setMLFilt(p => !p)}
                className={cn('flex h-[34px] items-center gap-2 rounded border px-3 text-xs font-semibold transition-colors',
                  useMLFilter ? 'border-accent/40 bg-[rgba(56,139,253,.1)] text-accent' : 'border-border bg-bg-elevated text-ink-secondary hover:bg-bg-overlay')}>
                <Brain size={12} /> {useMLFilter ? 'On' : 'Off'}
              </button>
            </div>
            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-1.5">
                <label className="text-2xs font-semibold uppercase tracking-widest text-ink-secondary">Regime Filter</label>
                <HelpTooltip text="Goes fully to cash (zero equity exposure) on any day the HMM classifies as a Bear regime. Reduces drawdowns at the cost of missing early recoveries." />
              </div>
              <button onClick={() => setRegFilt(p => !p)}
                className={cn('flex h-[34px] items-center gap-2 rounded border px-3 text-xs font-semibold transition-colors',
                  useRegFilt ? 'border-gain/40 bg-gain/10 text-gain' : 'border-border bg-bg-elevated text-ink-secondary hover:bg-bg-overlay')}>
                <Activity size={12} /> {useRegFilt ? 'On' : 'Off'}
              </button>
            </div>
          </div>
        </div>

        <div className="flex justify-end gap-3 items-center">
          {btMut.isError && <span className="text-xs text-loss">{(btMut.error as Error).message}</span>}
          <button disabled={!currentWeights || btMut.isPending} onClick={runBacktest}
            className={cn('flex items-center gap-2 rounded border px-6 py-2.5 text-sm font-semibold transition-all',
              !currentWeights || btMut.isPending
                ? 'cursor-not-allowed border-border text-ink-disabled'
                : 'border-accent bg-accent text-white hover:bg-accent/90')}>
            {btMut.isPending ? <><Spinner size={14} /> Running…</> : <><Play size={14} /> Run Walk-Forward</>}
          </button>
        </div>

        {btMut.isPending && (
          <div className="flex flex-col items-center gap-3 py-8">
            <Spinner size={28} />
            <p className="text-sm text-ink-muted">Running walk-forward validation ({nWindows} windows)…</p>
            {useMLFilter && <p className="text-xs text-ink-disabled">ML refit per window — this may take 1–2 minutes.</p>}
          </div>
        )}

        {btResult && !btMut.isPending && (
          <div className="space-y-4">
            {/* Summary cards */}
            <div className="grid grid-cols-4 gap-3">
              <MetricCard size="sm" label="OOS Sharpe"
                value={fmt(btResult.aggregate.sharpe)}
                accent={btResult.aggregate.sharpe >= 1 ? 'gain' : btResult.aggregate.sharpe >= 0.5 ? 'warn' : 'loss'}
                tooltip="Out-of-sample Sharpe ratio across all walk-forward test windows. This is your true unbiased estimate." />
              <MetricCard size="sm" label="Total Return"
                value={fmtPct(btResult.aggregate.annual_return)}
                accent={btResult.aggregate.annual_return >= 0 ? 'gain' : 'loss'}
                tooltip="Stitched out-of-sample return across all test windows." />
              <MetricCard size="sm" label="Max Drawdown"
                value={fmtPct(btResult.aggregate.max_drawdown)} accent="loss"
                tooltip="Worst peak-to-trough decline across all test windows." />
              <MetricCard size="sm" label="Alpha vs Nifty"
                value={fmtPct(btResult.aggregate.alpha)}
                accent={btResult.aggregate.alpha >= 0 ? 'gain' : 'loss'}
                tooltip="Excess return over buy-and-hold Nifty 50 index." />
            </div>

            {/* Equity curve */}
            <div className="rounded-md border border-border bg-bg-surface p-5 shadow-card">
              <p className="mb-3 text-2xs font-semibold uppercase tracking-[0.12em] text-ink-disabled">
                Out-of-Sample Equity Curve
              </p>
              <EquityCurveChart data={btResult} />
              <div className="mt-2 flex gap-4 justify-center text-2xs text-ink-muted">
                <span className="flex items-center gap-1.5"><span className="h-0.5 w-4 rounded bg-accent" />Portfolio</span>
                <span className="flex items-center gap-1.5"><span className="h-0.5 w-4 rounded bg-[#484F58] opacity-70" style={{ borderTop: '2px dashed' }} />Nifty 50</span>
              </div>
            </div>

            {/* Per-window table */}
            <div className="rounded-md border border-border bg-bg-surface shadow-card">
              <div className="flex items-center justify-between border-b border-border px-5 py-3">
                <h3 className="text-xs font-semibold uppercase tracking-widest text-ink-secondary">Per-Window Results</h3>
                <span className={cn('text-xs font-mono font-semibold',
                  btResult.degradation_slope < -0.05 ? 'text-loss' : btResult.degradation_slope > 0.02 ? 'text-gain' : 'text-ink-muted')}>
                  {btResult.degradation_slope < -0.05 ? '↓ Performance degrading' : btResult.degradation_slope > 0.02 ? '↑ Performance improving' : '→ Performance stable'}
                </span>
              </div>
              <div className="p-4">
                <DataTable
                  columns={[
                    { key: 'window', header: '#', cell: r => <span className="font-mono text-xs text-ink-muted">{r.window}</span>, align: 'center' },
                    { key: 'train_start', header: 'Train', cell: r => <span className="font-mono text-2xs text-ink-muted">{r.train_start} → {r.train_end}</span> },
                    { key: 'test_start',  header: 'Test',  cell: r => <span className="font-mono text-2xs text-ink-secondary">{r.test_start} → {r.test_end}</span> },
                    { key: 'sharpe', header: 'Sharpe',
                      cell: r => <span className="num font-mono font-semibold" style={{ color: sharpeColor(r.sharpe) }}>{r.sharpe.toFixed(2)}</span>,
                      sort: r => r.sharpe, align: 'right' },
                    { key: 'return', header: 'Return',
                      cell: r => <span className={cn('num font-mono', r.return >= 0 ? 'text-gain' : 'text-loss')}>{fmtPct(r.return)}</span>,
                      sort: r => r.return, align: 'right' },
                    { key: 'max_drawdown', header: 'Max DD',
                      cell: r => <span className="num font-mono text-loss">{fmtPct(r.max_drawdown)}</span>,
                      sort: r => r.max_drawdown, align: 'right' },
                  ]}
                  data={btResult.window_metrics}
                  keyFn={r => String(r.window)}
                />
              </div>
            </div>
          </div>
        )}
      </div>
    )
  }

  // ── Tab: Regimes ──────────────────────────────────────────────────
  function RegimesTab() {
    // Backend appends .NS so keys are e.g. "INFY.NS" — fall back to first key when lookup misses
    const effectiveKey = regimeTicker && regimeData
      ? (regimeData[regimeTicker] ? regimeTicker
          : Object.keys(regimeData).find(k => k.startsWith(regimeTicker!)) ?? regimeTicker)
      : null
    const tickerData = effectiveKey && regimeData ? regimeData[effectiveKey] : null

    return (
      <div className="space-y-4">
        {selected.length === 0 && (
          <div className="rounded-md border border-border bg-bg-surface px-4 py-3 text-xs text-ink-muted">
            Select stocks first to view their HMM regime history.
          </div>
        )}

        {selected.length > 0 && (
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-1.5 mr-1">
              <span className="text-2xs font-semibold uppercase tracking-widest text-ink-disabled">Select ticker</span>
              <HelpTooltip text="Pick a stock to see its full regime history. The HMM model is fit on 2 years of daily price data, then each day is labelled Bull, Bear, or Sideways based on which of the 3 hidden states was most likely." />
            </div>
            {selected.map((sym, i) => (
              <button key={sym} onClick={() => setRegimeTicker(regimeTicker === sym ? null : sym)}
                className={cn('rounded-sm border px-3 py-1.5 font-mono text-xs font-semibold transition-all',
                  regimeTicker === sym
                    ? 'border-accent bg-[rgba(56,139,253,.15)] text-accent'
                    : 'border-border bg-bg-elevated text-ink-secondary hover:bg-bg-overlay')}>
                {sym}
              </button>
            ))}
          </div>
        )}

        {regimeTicker && regimeLoading && (
          <div className="flex items-center gap-3 py-4">
            <Spinner size={18} />
            <span className="text-sm text-ink-muted">Fitting HMM for {regimeTicker}…</span>
          </div>
        )}

        {regimeTicker && regimeError && (
          <ErrorState message={(regimeError as Error).message} />
        )}

        {tickerData && !regimeLoading && (
          <div className="space-y-4">
            <RegimeChart series={tickerData.series} ticker={regimeTicker!} />

            {/* State stats */}
            <div className="grid grid-cols-3 gap-3">
              {tickerData.state_stats.map(stat => (
                <MetricCard key={stat.regime} label={stat.regime}
                  value={`${stat.mean_return >= 0 ? '+' : ''}${stat.mean_return.toFixed(3)}%`}
                  sub={`Avg ${stat.avg_duration_days}d per stint · Vol ${stat.vol.toFixed(1)}%`}
                  accent={stat.regime === 'Bull' ? 'gain' : stat.regime === 'Bear' ? 'loss' : 'warn'}
                  tooltip={`Average daily return in ${stat.regime} regime. Duration = average number of consecutive days before a transition.`} />
              ))}
            </div>

            {/* Transition matrix */}
            <div className="rounded-md border border-border bg-bg-surface p-5 shadow-card">
              <p className="mb-3 text-2xs font-semibold uppercase tracking-[0.12em] text-ink-disabled">
                Transition Matrix — P(next | current)
              </p>
              <table className="w-full text-xs font-mono">
                <thead>
                  <tr>
                    <th className="px-3 py-1.5 text-left text-ink-disabled">→</th>
                    {['Bull', 'Bear', 'Sideways'].map(h => (
                      <th key={h} className="px-3 py-1.5 text-right" style={{ color: REGIME_FILL[h] }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {tickerData.transition_matrix.map((row, ri) => {
                    const label = ['Bull', 'Bear', 'Sideways'][ri]
                    return (
                      <tr key={ri} className="border-t border-border/40">
                        <td className="px-3 py-1.5 font-semibold" style={{ color: REGIME_FILL[label] }}>{label}</td>
                        {row.map((v, ci) => (
                          <td key={ci} className="px-3 py-1.5 text-right text-ink-secondary">{(v * 100).toFixed(1)}%</td>
                        ))}
                      </tr>
                    )
                  })}
                </tbody>
              </table>
              <p className="mt-3 text-2xs text-ink-muted">
                Expected regime duration = 1 / P(leaving). E.g. P(Bull→Bear) = 2% means ~50 days expected in Bull regime.
              </p>
            </div>
          </div>
        )}
      </div>
    )
  }

  // ── Tab: Sensitivity ──────────────────────────────────────────────
  function SensitivityTab() {
    return (
      <div className="space-y-4">
        {!currentWeights && (
          <div className="rounded-md border border-warn/30 bg-warn/5 px-4 py-3 text-xs text-warn">
            Build a portfolio first to run sensitivity analysis.
          </div>
        )}

        <div className="rounded-md border border-border bg-bg-surface p-4">
          <div className="flex items-center gap-1.5">
            <p className="text-xs font-semibold uppercase tracking-widest text-ink-secondary">Parameter Grid</p>
            <HelpTooltip text="Runs 20 backtests (5 ATR stop multipliers × 4 transaction cost levels) and records the Sharpe ratio for each. ATR multiplier controls how far price must fall before a stop-loss triggers. Transaction cost is charged on every trade. A broad green plateau means results are robust; a single bright cell means performance depends on a very specific setting." />
          </div>
        </div>

        <div className="flex justify-end gap-3 items-center">
          {sensMut.isError && <span className="text-xs text-loss">{(sensMut.error as Error).message}</span>}
          <button disabled={!currentWeights || sensMut.isPending} onClick={runSens}
            className={cn('flex items-center gap-2 rounded border px-6 py-2.5 text-sm font-semibold transition-all',
              !currentWeights || sensMut.isPending
                ? 'cursor-not-allowed border-border text-ink-disabled'
                : 'border-accent bg-accent text-white hover:bg-accent/90')}>
            {sensMut.isPending ? <><Spinner size={14} /> Running…</> : <><BarChart2 size={14} /> Run Sensitivity</>}
          </button>
        </div>

        {sensMut.isPending && (
          <div className="flex flex-col items-center gap-3 py-8">
            <Spinner size={28} />
            <p className="text-sm text-ink-muted">Running 20-combination parameter grid (~15 sec)…</p>
          </div>
        )}

        {sensResult && !sensMut.isPending && (
          <SensitivityHeatmap data={sensResult} />
        )}
      </div>
    )
  }

  // ── Render ────────────────────────────────────────────────────────

  return (
    <div className="flex h-[calc(100vh-104px)] gap-5 animate-fade-up">
      {/* Left: stock browser */}
      <StockBrowser className="w-[300px] shrink-0" selected={selected} onToggle={toggleStock} />

      {/* Right panel */}
      <div className="flex flex-1 flex-col gap-4 overflow-hidden">
        {/* Tab bar */}
        <div className="flex gap-1 rounded-md border border-border bg-bg-surface p-1 shrink-0">
          {TABS.map(({ id, label, icon: Icon, tooltip }) => (
            <button key={id} onClick={() => setActiveTab(id)}
              className={cn('flex flex-1 items-center justify-center gap-2 rounded px-3 py-2 text-xs font-semibold transition-all',
                activeTab === id
                  ? 'bg-accent text-white'
                  : 'text-ink-secondary hover:bg-bg-elevated hover:text-ink-primary')}>
              <Icon size={12} /> {label}
              <span onClick={e => e.stopPropagation()} className={activeTab === id ? 'opacity-70' : ''}>
                <HelpTooltip text={tooltip} />
              </span>
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="flex-1 overflow-y-auto pr-1">
          {activeTab === 'build'       && <BuildTab />}
          {activeTab === 'backtest'    && <BacktestTab />}
          {activeTab === 'regimes'     && <RegimesTab />}
          {activeTab === 'sensitivity' && <SensitivityTab />}
        </div>
      </div>
    </div>
  )
}
