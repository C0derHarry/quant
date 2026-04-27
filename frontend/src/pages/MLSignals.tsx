import { useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import {
  analyzeSignals,
  type SignalResult, type TickerSignal, type SignalHistoryRow,
} from '../lib/api'
import StockBrowser from '../components/ui/StockBrowser'
import Spinner, { ErrorState } from '../components/ui/Spinner'
import { Play, ArrowRight, Brain, Info, HelpCircle } from 'lucide-react'
import { cn, fmtPct } from '../lib/utils'
import {
  ResponsiveContainer, AreaChart, Area, BarChart, Bar,
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ReferenceLine, Cell,
} from 'recharts'

// ── helpers ──────────────────────────────────────────────────────────────────

function signalColor(regime: string) {
  if (regime === 'Long')  return 'text-gain'
  if (regime === 'Short') return 'text-loss'
  return 'text-warn'
}

function gaugeColor(regime: string) {
  if (regime === 'Long')  return '#3FB950'
  if (regime === 'Short') return '#F85149'
  return '#D29922'
}

function confidenceBadgeVariant(bin: string) {
  if (bin.includes('Long'))  return 'bg-gain/10 text-gain border-gain/20'
  if (bin.includes('Short')) return 'bg-loss/10 text-loss border-loss/20'
  return 'bg-warn/10 text-warn border-warn/20'
}

const DARK_TOOLTIP_STYLE = {
  contentStyle: { background: '#161b22', border: '1px solid #30363d', borderRadius: 6, fontSize: 12 },
  itemStyle:    { color: '#c9d1d9' },
  labelStyle:   { color: '#8b949e', marginBottom: 4 },
}

// ── sub-components ───────────────────────────────────────────────────────────

function SignalCard({
  ticker, signal, active, onClick,
}: { ticker: string; signal: TickerSignal; active: boolean; onClick: () => void }) {
  const pct  = Math.round(signal.p_up * 100)
  const col  = gaugeColor(signal.regime)

  return (
    <button
      onClick={onClick}
      className={cn(
        'w-full rounded-lg border p-4 text-left transition-all',
        active
          ? 'border-accent bg-[rgba(56,139,253,.08)]'
          : 'border-border bg-bg-surface hover:bg-bg-elevated',
      )}
    >
      <div className="flex items-start justify-between">
        <p className="font-mono text-sm font-semibold text-ink-primary">{ticker}</p>
        <span className={cn('text-xs font-semibold', signalColor(signal.regime))}>
          {signal.regime === 'Long' ? '▲ Long' : signal.regime === 'Short' ? '▼ Short' : '→ Flat'}
        </span>
      </div>

      <div className="mt-3">
        <div className="mb-1 flex items-center justify-between">
          <span className="text-xs text-ink-muted">P(5d-up)</span>
          <span className="font-mono text-xs font-semibold text-ink-primary">{pct}%</span>
        </div>
        <div className="h-2 w-full overflow-hidden rounded-full bg-bg-elevated">
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{ width: `${pct}%`, background: col }}
          />
        </div>
      </div>

      <div className="mt-2.5">
        <span className={cn(
          'inline-block rounded border px-1.5 py-0.5 text-2xs font-medium',
          confidenceBadgeVariant(signal.confidence_bin),
        )}>
          {signal.confidence_bin}
        </span>
      </div>

      {signal.metrics && (
        <div className="mt-3 grid grid-cols-3 gap-1 border-t border-border/40 pt-3">
          {[
            { label: 'AUC',   val: signal.metrics.roc_auc.toFixed(3), tip: 'ROC-AUC on test set. Above 0.55 indicates the model discriminates up-days from down-days better than random.' },
            { label: 'Brier', val: signal.metrics.brier.toFixed(3),   tip: 'Probability MSE. Below 0.25 means the model beats random guessing on calibration quality.' },
            { label: 'Acc',   val: fmtPct(signal.metrics.accuracy * 100), tip: 'Directional accuracy at 0.5 threshold. Only meaningful if clearly above the base rate (% of up-days).' },
          ].map(({ label, val, tip }) => (
            <div key={label} className="text-center">
              <p className="font-mono text-xs font-semibold text-ink-primary">{val}</p>
              <p className="text-2xs text-ink-disabled" title={tip}>{label}</p>
            </div>
          ))}
        </div>
      )}
    </button>
  )
}

// ── chart panels ─────────────────────────────────────────────────────────────

function HistoryChart({
  history, longThr, shortThr,
}: { history: SignalHistoryRow[]; longThr: number; shortThr: number }) {
  const data = history.map(r => ({
    date:   r.date.slice(5),
    p_up:   +(r.p_up * 100).toFixed(1),
    regime: r.regime,
  }))

  return (
    <ResponsiveContainer width="100%" height={260}>
      <AreaChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="histGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  stopColor="#388BFD" stopOpacity={0.25} />
            <stop offset="95%" stopColor="#388BFD" stopOpacity={0}    />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#21262d" vertical={false} />
        <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#8b949e' }} tickLine={false} axisLine={false} />
        <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: '#8b949e' }} tickLine={false} axisLine={false}
               tickFormatter={v => `${v}%`} width={38} />
        <Tooltip
          {...DARK_TOOLTIP_STYLE}
          formatter={(v: number) => [`${v}%`, 'P(up)']}
        />
        <ReferenceLine y={longThr * 100}  stroke="#3FB950" strokeDasharray="4 3" strokeWidth={1.2}
                       label={{ value: 'Long', position: 'right', fontSize: 10, fill: '#3FB950' }} />
        <ReferenceLine y={shortThr * 100} stroke="#F85149" strokeDasharray="4 3" strokeWidth={1.2}
                       label={{ value: 'Short', position: 'right', fontSize: 10, fill: '#F85149' }} />
        <Area type="monotone" dataKey="p_up" stroke="#388BFD" strokeWidth={1.5}
              fill="url(#histGrad)" dot={false} />
      </AreaChart>
    </ResponsiveContainer>
  )
}

function FeatureChart({ data }: { data: { feature: string; importance: number }[] }) {
  const sorted = [...data].sort((a, b) => a.importance - b.importance)

  return (
    <ResponsiveContainer width="100%" height={Math.max(200, sorted.length * 28)}>
      <BarChart data={sorted} layout="vertical" margin={{ top: 4, right: 20, left: 120, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#21262d" horizontal={false} />
        <XAxis type="number" tick={{ fontSize: 11, fill: '#8b949e' }} tickLine={false} axisLine={false}
               tickFormatter={v => v.toFixed(3)} />
        <YAxis type="category" dataKey="feature" tick={{ fontSize: 11, fill: '#8b949e' }}
               tickLine={false} axisLine={false} width={116} />
        <Tooltip
          {...DARK_TOOLTIP_STYLE}
          formatter={(v: number) => [v.toFixed(4), 'Importance']}
        />
        <Bar dataKey="importance" radius={[0, 3, 3, 0]}>
          {sorted.map((_, i) => (
            <Cell key={i} fill="#388BFD" fillOpacity={0.55 + 0.45 * (i / sorted.length)} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

function CalibrationChart({ data }: { data: { predicted: number; actual: number }[] }) {
  const perfect = [{ predicted: 0, actual: 0 }, { predicted: 1, actual: 1 }]

  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart margin={{ top: 8, right: 20, left: 0, bottom: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#21262d" />
        <XAxis
          dataKey="predicted" type="number" domain={[0, 1]}
          tick={{ fontSize: 11, fill: '#8b949e' }} tickLine={false} axisLine={false}
          tickFormatter={v => `${Math.round(v * 100)}%`}
          label={{ value: 'Predicted', position: 'insideBottom', offset: -4, fontSize: 11, fill: '#8b949e' }}
        />
        <YAxis
          type="number" domain={[0, 1]}
          tick={{ fontSize: 11, fill: '#8b949e' }} tickLine={false} axisLine={false}
          tickFormatter={v => `${Math.round(v * 100)}%`} width={38}
          label={{ value: 'Actual', angle: -90, position: 'insideLeft', fontSize: 11, fill: '#8b949e' }}
        />
        <Tooltip
          {...DARK_TOOLTIP_STYLE}
          formatter={(v: number) => [`${(v * 100).toFixed(1)}%`]}
        />
        <Line data={perfect} dataKey="actual" stroke="#30363d" strokeDasharray="5 3"
              dot={false} strokeWidth={1.2} name="Perfect" />
        <Line data={data} dataKey="actual" stroke="#D29922" strokeWidth={2}
              dot={{ r: 3, fill: '#D29922' }} name="Actual" />
        <Line data={data} dataKey="predicted" stroke="#388BFD" strokeWidth={2}
              dot={{ r: 3, fill: '#388BFD' }} name="Predicted" />
      </LineChart>
    </ResponsiveContainer>
  )
}

// ── threshold guidance ────────────────────────────────────────────────────────

const PRESETS = [
  {
    label: 'Conservative',
    long: 0.70, short: 0.30,
    desc: 'Only act on high-conviction signals. Expect fewer positions but stronger edge.',
  },
  {
    label: 'Balanced',
    long: 0.60, short: 0.40,
    desc: 'Default setting. Filters out genuine uncertainty while keeping reasonable signal frequency.',
  },
  {
    label: 'Active',
    long: 0.55, short: 0.45,
    desc: 'More signals with some uncertainty accepted. Suits frequent rebalancers.',
  },
]

function ThresholdGuidance({
  longThr, shortThr, onPreset,
}: { longThr: number; shortThr: number; onPreset: (l: number, s: number) => void }) {
  const flatWidth = Math.round((longThr - shortThr) * 100)

  const activePreset = PRESETS.find(p => p.long === longThr && p.short === shortThr)

  let dynamicDesc: string
  if (flatWidth >= 40) {
    dynamicDesc = `${flatWidth}% flat band - very selective. Only readings below ${Math.round(shortThr * 100)}% or above ${Math.round(longThr * 100)}% generate a signal. Expect infrequent but high-conviction calls.`
  } else if (flatWidth >= 20) {
    dynamicDesc = `${flatWidth}% flat band - balanced filter. Readings between ${Math.round(shortThr * 100)}%–${Math.round(longThr * 100)}% are treated as uncertain and ignored. Good signal-to-noise for most portfolios.`
  } else {
    dynamicDesc = `${flatWidth}% flat band - narrow filter. Most readings will produce a Long or Short signal. Useful for active strategies but expect more false positives.`
  }

  return (
    <div className="border-t border-border/50 px-5 py-3.5 space-y-3">
      {/* Preset chips */}
      <div className="flex items-center gap-2">
        <span className="text-2xs font-semibold uppercase tracking-widest text-ink-disabled w-14 shrink-0">
          Presets
        </span>
        <div className="flex gap-2">
          {PRESETS.map(p => {
            const active = p.long === longThr && p.short === shortThr
            return (
              <button
                key={p.label}
                onClick={() => onPreset(p.long, p.short)}
                className={cn(
                  'rounded border px-3 py-1 text-xs font-medium transition-colors',
                  active
                    ? 'border-accent bg-[rgba(56,139,253,.12)] text-accent'
                    : 'border-border text-ink-secondary hover:border-ink-muted hover:text-ink-primary',
                )}
              >
                {p.label}
              </button>
            )
          })}
        </div>
      </div>

      {/* Zone diagram */}
      <div className="space-y-1.5">
        <div className="flex h-4 w-full overflow-hidden rounded-full text-2xs font-semibold">
          <div
            className="flex items-center justify-center bg-loss/20 text-loss"
            style={{ width: `${Math.round(shortThr * 100)}%` }}
          >
            Short
          </div>
          <div
            className="flex items-center justify-center bg-bg-elevated text-ink-disabled"
            style={{ width: `${flatWidth}%` }}
          >
            Flat
          </div>
          <div
            className="flex items-center justify-center bg-gain/20 text-gain flex-1"
          >
            Long
          </div>
        </div>
        <div className="flex justify-between text-2xs text-ink-disabled font-mono">
          <span>0%</span>
          <span className="text-loss">{Math.round(shortThr * 100)}%</span>
          <span className="text-gain">{Math.round(longThr * 100)}%</span>
          <span>100%</span>
        </div>
      </div>

      {/* Dynamic description */}
      <p className="text-xs text-ink-muted leading-relaxed">
        {activePreset ? <><span className="font-medium text-ink-secondary">{activePreset.label}:</span> {activePreset.desc}</> : dynamicDesc}
      </p>
    </div>
  )
}

// ── main page ─────────────────────────────────────────────────────────────────

type Tab = 'history' | 'fi' | 'calibration'

export default function MLSignals() {
  const navigate = useNavigate()

  const [selected,     setSelected]   = useState<string[]>([])
  const [longThr,      setLongThr]    = useState(0.60)
  const [shortThr,     setShortThr]   = useState(0.40)
  const [activeTicker, setActive]     = useState<string | null>(null)
  const [activeTab,    setActiveTab]  = useState<Tab>('history')

  const { mutate, data, isPending, error } = useMutation({
    mutationFn: analyzeSignals,
    onSuccess: (result) => {
      const first = Object.keys(result)[0] ?? null
      setActive(first)
    },
  })

  function handleRun() {
    if (!selected.length) return
    mutate({ tickers: selected, long_threshold: longThr, short_threshold: shortThr })
  }

  function handleOptimize() {
    const tickers = Object.keys(data ?? {}).filter(t => !(data![t] as TickerSignal).error)
    if (!tickers.length) return
    navigate(`/portfolio?tickers=${tickers.join(',')}&ml=1`)
  }

  const validResults = useMemo(
    () => data ? Object.entries(data).filter(([, v]) => !(v as TickerSignal).error) as [string, TickerSignal][] : [],
    [data],
  )

  const activeSignal = activeTicker ? (data?.[activeTicker] as TickerSignal | undefined) : undefined

  const TABS: { key: Tab; label: string }[] = [
    { key: 'history',     label: 'Signal History' },
    { key: 'fi',          label: 'Feature Importance' },
    { key: 'calibration', label: 'Calibration' },
  ]

  return (
    <div className="flex h-full gap-6">
      {/* Sidebar */}
      <div className="w-[240px] shrink-0">
        <StockBrowser
          selected={selected}
          onToggle={sym => setSelected(prev =>
            prev.includes(sym) ? prev.filter(s => s !== sym) : [...prev, sym]
          )}
          maxSelected={5}
          hideSector
          className="h-full"
        />
      </div>

      {/* Main */}
      <div className="min-w-0 flex-1 space-y-5">

        {/* Header row */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <Brain size={18} className="text-accent" />
            <h1 className="text-base font-semibold text-ink-primary">ML Signals</h1>
            <span className="text-xs text-ink-disabled">GBM · 5-day directional probability</span>
          </div>
          <button
            onClick={handleRun}
            disabled={!selected.length || isPending}
            className={cn(
              'flex items-center gap-2 rounded px-4 py-2 text-sm font-medium transition-colors',
              selected.length && !isPending
                ? 'bg-accent text-white hover:bg-accent/90'
                : 'bg-bg-elevated text-ink-disabled cursor-not-allowed',
            )}
          >
            {isPending ? <Spinner size={14} /> : <Play size={14} />}
            {isPending ? 'Analysing…' : 'Run Signals'}
          </button>
        </div>

        {/* Threshold sliders */}
        <div className="rounded-lg border border-border bg-bg-surface">
          <div className="flex items-center gap-8 px-5 py-3.5">
            {[
              { label: 'Long threshold', value: longThr,  set: setLongThr,  min: 0.50, max: 0.90, color: '#3FB950' },
              { label: 'Short threshold', value: shortThr, set: setShortThr, min: 0.10, max: 0.50, color: '#F85149' },
            ].map(({ label, value, set, min, max, color }) => (
              <div key={label} className="flex flex-1 items-center gap-3">
                <span className="w-32 text-xs text-ink-secondary">{label}</span>
                <input
                  type="range" min={min} max={max} step={0.05} value={value}
                  onChange={e => set(+e.target.value)}
                  className="flex-1 accent-[var(--color-accent)]"
                  style={{ accentColor: color }}
                />
                <span className="w-10 font-mono text-xs font-semibold text-ink-primary text-right">
                  {(value * 100).toFixed(0)}%
                </span>
              </div>
            ))}
          </div>

          {/* Guidance panel */}
          <ThresholdGuidance
            longThr={longThr}
            shortThr={shortThr}
            onPreset={(l, s) => { setLongThr(l); setShortThr(s) }}
          />
        </div>

        {/* Error */}
        {error && <ErrorState message={(error as Error).message} />}

        {/* Empty state */}
        {!isPending && !data && !error && (
          <div className="flex flex-col items-center justify-center rounded-lg border border-border bg-bg-surface py-20 text-center">
            <Brain size={32} className="mb-3 text-ink-disabled" strokeWidth={1.2} />
            <p className="text-sm font-medium text-ink-secondary">Select stocks and click Run Signals</p>
            <p className="mt-1 text-xs text-ink-disabled">
              Trains a calibrated GBM per ticker - P(5-day up move)
            </p>
          </div>
        )}

        {/* Signal cards */}
        {validResults.length > 0 && (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
            {validResults.map(([ticker, sig]) => (
              <SignalCard
                key={ticker}
                ticker={ticker}
                signal={sig}
                active={activeTicker === ticker}
                onClick={() => setActive(ticker)}
              />
            ))}
          </div>
        )}

        {/* Detail charts */}
        {activeSignal && !activeSignal.error && (
          <div className="rounded-lg border border-border bg-bg-surface">
            {/* Tab bar */}
            <div className="flex border-b border-border px-5">
              {TABS.map(({ key, label }) => (
                <button
                  key={key}
                  onClick={() => setActiveTab(key)}
                  className={cn(
                    'border-b-2 px-4 py-3 text-xs font-medium transition-colors',
                    activeTab === key
                      ? 'border-accent text-accent'
                      : 'border-transparent text-ink-muted hover:text-ink-secondary',
                  )}
                >
                  {label}
                </button>
              ))}
              <div className="ml-auto flex items-center pr-1">
                <span className="text-xs font-mono text-ink-disabled">{activeTicker}</span>
              </div>
            </div>

            <div className="p-5">
              {activeTab === 'history' && (
                <>
                  <p className="mb-3 text-xs text-ink-muted">
                    30-day P(5d-up) - green line = long threshold, red line = short threshold
                  </p>
                  <HistoryChart
                    history={activeSignal.signal_history}
                    longThr={longThr}
                    shortThr={shortThr}
                  />
                </>
              )}

              {activeTab === 'fi' && (
                <>
                  <p className="mb-3 text-xs text-ink-muted">
                    Mean impurity-decrease feature importance (averaged across calibration CV folds)
                  </p>
                  <FeatureChart data={activeSignal.feature_importances} />
                </>
              )}

              {activeTab === 'calibration' && (
                <>
                  <div className="mb-3 flex items-center gap-2">
                    <p className="text-xs text-ink-muted">
                      Predicted probability vs observed frequency - dashed grey = perfect calibration
                    </p>
                    <Info size={12} className="shrink-0 text-ink-disabled" />
                  </div>
                  <CalibrationChart data={activeSignal.calibration} />
                </>
              )}
            </div>

            {/* Model metrics footer */}
            <div className="flex flex-wrap gap-6 border-t border-border/40 px-5 py-3">
              {[
                {
                  label: 'Log-Loss',
                  val: activeSignal.metrics.log_loss.toFixed(4),
                  tip: 'Probabilistic cross-entropy loss on the held-out test set. A random coin-flip scores 0.693 (ln 2). Lower is better - beating 0.693 means the model adds real information beyond guessing.',
                },
                {
                  label: 'Brier Score',
                  val: activeSignal.metrics.brier.toFixed(4),
                  tip: 'Mean squared error between the predicted probability and the actual outcome (0 or 1). A random classifier scores ≈ 0.25. Lower is better - the model should score below 0.25 to be considered useful.',
                },
                {
                  label: 'ROC-AUC',
                  val: activeSignal.metrics.roc_auc.toFixed(4),
                  tip: 'Area under the ROC curve: the probability that the model ranks a random up-day above a random down-day. 0.5 = random, 1.0 = perfect. A score above 0.55 indicates meaningful discrimination.',
                },
                {
                  label: 'Accuracy',
                  val: fmtPct(activeSignal.metrics.accuracy * 100),
                  tip: 'Directional accuracy at a 0.5 decision threshold on the test set. Compare to the base rate below - a model is only useful if its accuracy meaningfully exceeds the fraction of up-days.',
                },
                {
                  label: 'Test bars',
                  val: activeSignal.metrics.n_test.toString(),
                  tip: 'Number of trading days in the chronological held-out test set (last 20% of history). A larger test set gives more reliable metric estimates.',
                },
                {
                  label: 'Base rate',
                  val: fmtPct(activeSignal.metrics.pos_rate * 100),
                  tip: 'Fraction of up-days in the test set. This is the score a naïve "always predict up" classifier would achieve. Your model\'s accuracy must meaningfully exceed this to have predictive value.',
                },
              ].map(({ label, val, tip }) => (
                <div key={label} className="text-center">
                  <p className="font-mono text-xs font-semibold text-ink-primary">{val}</p>
                  <div className="mt-0.5 flex items-center justify-center gap-1">
                    <p className="text-2xs text-ink-disabled">{label}</p>
                    <div className="group relative">
                      <HelpCircle size={10} className="cursor-help text-ink-disabled transition-colors hover:text-ink-muted" />
                      <div className="pointer-events-none invisible absolute bottom-4 left-1/2 z-20 w-52 -translate-x-1/2 rounded border border-border bg-bg-elevated p-2.5 text-xs leading-relaxed text-ink-secondary shadow-lg group-hover:visible">
                        {tip}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Optimize CTA */}
        {validResults.length > 0 && (
          <div className="flex items-center justify-between rounded-lg border border-accent/30 bg-[rgba(56,139,253,.05)] px-5 py-3.5">
            <div className="flex items-center gap-2 text-sm text-ink-secondary">
              <Info size={14} className="text-accent" />
              ML signal views can be fed into the Black-Litterman optimizer as an additional
              expected-return signal (20% weight).
            </div>
            <button
              onClick={handleOptimize}
              className="flex items-center gap-2 rounded bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent/90 transition-colors shrink-0 ml-4"
            >
              Optimize with ML Signals
              <ArrowRight size={14} />
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
