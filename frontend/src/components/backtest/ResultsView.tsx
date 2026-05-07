import { useState } from 'react'
import { type BacktestResult, exportStrategy } from '../../lib/api'
import { cn } from '../../lib/utils'
import { fmtLargeNum } from '../../lib/utils'
import {
  ResponsiveContainer, AreaChart, Area, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
} from 'recharts'
import DataTable, { Column } from '../ui/DataTable'
import { Download, AlertTriangle, RefreshCw } from 'lucide-react'

type Tab = 'equity' | 'drawdown' | 'kpis' | 'trades' | 'export'

interface Props {
  result:   BacktestResult
  onRerun:  () => void
}

function KpiCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded border border-border bg-bg-elevated p-4">
      <p className="text-2xs font-semibold uppercase tracking-widest text-ink-disabled">{label}</p>
      <p className="mt-1.5 font-mono text-xl font-bold text-ink-primary">{value}</p>
      {sub && <p className="mt-0.5 text-2xs text-ink-muted">{sub}</p>}
    </div>
  )
}

function EquityChart({ result }: { result: BacktestResult }) {
  const data = result.equity_curve.map((r, i) => ({
    date:      r.date.slice(0, 7),  // YYYY-MM
    strategy:  Math.round(r.value),
    benchmark: Math.round(result.benchmark_curve[i]?.value ?? r.value),
  }))

  // Thin out for performance: keep 1 per month
  const seen = new Set<string>()
  const chart = data.filter(d => {
    if (seen.has(d.date)) return false
    seen.add(d.date)
    return true
  })

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={chart} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,.04)" />
        <XAxis dataKey="date" tick={{ fill: '#7D8590', fontSize: 10 }} tickLine={false} axisLine={false} interval={11} />
        <YAxis tick={{ fill: '#7D8590', fontSize: 10 }} tickLine={false} axisLine={false} width={72}
          tickFormatter={v => `₹${(v/1000).toFixed(0)}k`} />
        <Tooltip formatter={(v: number, name: string) => [`₹${v.toLocaleString('en-IN')}`, name]} />
        <Legend wrapperStyle={{ fontSize: 11 }} />
        <Line type="monotone" dataKey="strategy"  name="Strategy"    stroke="#3FB950" strokeWidth={1.8} dot={false} />
        <Line type="monotone" dataKey="benchmark" name="NIFTY 50"    stroke="#388BFD" strokeWidth={1.4} dot={false} strokeDasharray="4 2" />
      </LineChart>
    </ResponsiveContainer>
  )
}

function DrawdownChart({ result }: { result: BacktestResult }) {
  const seen = new Set<string>()
  const chart = result.drawdown_curve
    .map(r => ({ date: r.date.slice(0, 7), dd: r.dd_pct }))
    .filter(d => { if (seen.has(d.date)) return false; seen.add(d.date); return true })

  return (
    <ResponsiveContainer width="100%" height={200}>
      <AreaChart data={chart} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="dd-grad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  stopColor="#F85149" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#F85149" stopOpacity={0}   />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,.04)" />
        <XAxis dataKey="date" tick={{ fill: '#7D8590', fontSize: 10 }} tickLine={false} axisLine={false} interval={11} />
        <YAxis tick={{ fill: '#7D8590', fontSize: 10 }} tickLine={false} axisLine={false} width={45}
          tickFormatter={v => `${v}%`} />
        <Tooltip formatter={(v: number) => [`${v.toFixed(2)}%`, 'Drawdown']} />
        <Area type="monotone" dataKey="dd" stroke="#F85149" strokeWidth={1.5} fill="url(#dd-grad)" dot={false} />
      </AreaChart>
    </ResponsiveContainer>
  )
}

const TRADE_COLS: Column<BacktestResult['trade_log'][0]>[] = [
  { key: 'date',   header: 'Date',   cell: r => <span className="font-mono text-xs text-ink-muted">{r.date}</span>,   sort: r => r.date, width: '100px' },
  { key: 'ticker', header: 'Symbol', cell: r => <span className="font-mono text-xs font-semibold text-accent">{r.ticker.replace('.NS','')}</span>, sort: r => r.ticker },
  { key: 'side',   header: 'Side',   cell: r => (
    <span className={cn('rounded px-2 py-0.5 text-2xs font-semibold', r.side === 'buy' ? 'bg-gain/10 text-gain' : 'bg-loss/10 text-loss')}>
      {r.side.toUpperCase()}
    </span>
  ), width: '70px' },
  { key: 'value',  header: 'Value',  cell: r => <span className="num font-mono text-xs text-ink-primary">₹{fmtLargeNum(r.value)}</span>, sort: r => r.value, align: 'right' },
  { key: 'cost',   header: 'Total Cost', cell: r => <span className="num font-mono text-xs text-ink-secondary">₹{(r.cost_breakdown?.total ?? 0).toFixed(2)}</span>, sort: r => r.cost_breakdown?.total ?? 0, align: 'right' },
]

function ExportSection({ result }: { result: BacktestResult }) {
  const [loading, setLoading] = useState(false)
  const [err, setErr]         = useState<string | null>(null)

  async function handleExport() {
    setLoading(true)
    setErr(null)
    try {
      await exportStrategy({
        strategy_id: result.strategy_id,
        params:      result.params as Record<string, unknown>,
        broker_id:   result.brokerage_id,
        tickers:     result.tickers,
        start_date:  result.start_date,
        end_date:    result.end_date,
        kpis:        result.kpis,
      })
    } catch (e) {
      setErr((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-4 py-4">
      <div className="rounded border border-border bg-bg-elevated p-5">
        <h3 className="text-sm font-semibold text-ink-primary">Export as Python Script</h3>
        <p className="mt-1.5 text-xs text-ink-muted leading-relaxed">
          Downloads a self-contained <code>.py</code> file with your strategy, cost model, and
          a <code>main()</code> function that fetches data via yfinance and prints KPIs.
          Requires only <code>pandas</code>, <code>numpy</code>, and <code>yfinance</code>.
        </p>
        <p className="mt-2 text-xs text-ink-muted leading-relaxed">
          Broker integration stubs are included as commented placeholders — wire up your own
          API credentials to place live orders.
        </p>
        {err && <p className="mt-3 text-xs text-loss">{err}</p>}
        <button
          onClick={handleExport}
          disabled={loading}
          className="mt-4 flex items-center gap-2 rounded bg-accent px-4 py-2 text-sm font-semibold text-white hover:bg-accent/90 disabled:opacity-40 transition-opacity"
        >
          <Download size={14} />
          {loading ? 'Exporting…' : 'Download Python Script'}
        </button>
      </div>
    </div>
  )
}

const TABS: { id: Tab; label: string }[] = [
  { id: 'equity',   label: 'Equity Curve' },
  { id: 'drawdown', label: 'Drawdown' },
  { id: 'kpis',     label: 'KPIs' },
  { id: 'trades',   label: `Trade Log` },
  { id: 'export',   label: 'Export' },
]

export default function ResultsView({ result, onRerun }: Props) {
  const [tab, setTab] = useState<Tab>('equity')
  const k = result.kpis

  return (
    <div className="space-y-4 animate-fade-up">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs text-ink-muted">{result.universe} · {result.start_date} → {result.end_date}</p>
          <p className="mt-0.5 text-xs text-ink-disabled">Broker: {result.brokerage_id}</p>
        </div>
        <button onClick={onRerun}
          className="flex items-center gap-1.5 rounded border border-border px-3 py-1.5 text-xs text-ink-muted hover:border-accent hover:text-accent transition-colors">
          <RefreshCw size={12} /> Reconfigure
        </button>
      </div>

      {/* Survivorship bias notice */}
      {result.survivorship_bias_warning && (
        <div className="flex items-start gap-2 rounded border border-amber-500/20 bg-amber-500/5 px-3 py-2.5">
          <AlertTriangle size={13} className="mt-0.5 shrink-0 text-amber-500" />
          <p className="text-2xs text-amber-400 leading-relaxed">
            Results reflect current index constituents. Delisted stocks are excluded — returns may be
            overstated by ~1–2% CAGR (survivorship bias).
          </p>
        </div>
      )}

      {/* Top KPI strip */}
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <KpiCard label="CAGR" value={`${k.cagr}%`} sub={`Benchmark: ${k.benchmark_cagr}%`} />
        <KpiCard label="Alpha" value={`${k.alpha > 0 ? '+' : ''}${k.alpha}%`} />
        <KpiCard label="Sharpe" value={String(k.sharpe)} />
        <KpiCard label="Max Drawdown" value={`${k.max_drawdown}%`} />
      </div>

      {/* Tabs */}
      <div className="flex border-b border-border">
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={cn(
              'border-b-2 px-4 py-2.5 text-xs font-semibold transition-colors',
              tab === t.id ? 'border-accent text-accent' : 'border-transparent text-ink-muted hover:text-ink-primary',
            )}>
            {t.id === 'trades' ? `Trade Log (${Math.min(result.trade_log.length, 500)})` : t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="min-h-[220px]">
        {tab === 'equity'   && <EquityChart result={result} />}
        {tab === 'drawdown' && <DrawdownChart result={result} />}
        {tab === 'kpis'     && (
          <div className="grid gap-3 sm:grid-cols-3">
            <KpiCard label="CAGR"            value={`${k.cagr}%`}         sub={`Benchmark: ${k.benchmark_cagr}%`} />
            <KpiCard label="Alpha"           value={`${k.alpha > 0 ? '+' : ''}${k.alpha}%`} />
            <KpiCard label="Sharpe Ratio"    value={String(k.sharpe)} />
            <KpiCard label="Sortino Ratio"   value={String(k.sortino)} />
            <KpiCard label="Calmar Ratio"    value={String(k.calmar)} />
            <KpiCard label="Max Drawdown"    value={`${k.max_drawdown}%`} />
            <KpiCard label="Hit Rate"        value={`${k.hit_rate}%`}     sub={`${k.n_trades} trades`} />
            <KpiCard label="Avg Turnover"    value={`${k.avg_turnover}%`} sub="per rebalance" />
            <KpiCard label="Total Cost Paid" value={`₹${k.total_cost_inr.toLocaleString('en-IN')}`} />
          </div>
        )}
        {tab === 'trades' && (
          <DataTable
            columns={TRADE_COLS}
            data={result.trade_log}
            keyFn={r => `${r.date}-${r.ticker}-${r.side}`}
          />
        )}
        {tab === 'export' && <ExportSection result={result} />}
      </div>
    </div>
  )
}
