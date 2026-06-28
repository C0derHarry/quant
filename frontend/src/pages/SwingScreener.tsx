import { useState, lazy, Suspense } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Play, RefreshCw, TrendingUp, X, AlertTriangle } from 'lucide-react'
import DataTable, { type Column } from '../components/ui/DataTable'
import Badge from '../components/ui/Badge'
import { PageLoader } from '../components/ui/Spinner'
import {
  runScan, getRunStatus, getScreenerResults, getStockDetail,
  type ScreenerResult, type StockDetail,
} from '../lib/api'
import { fmt } from '../lib/utils'

const SwingChart = lazy(() => import('../components/SwingChart'))

// ── Setup type display ────────────────────────────────────────────────────────

const SETUP_LABELS: Record<string, { label: string; variant: 'accent' | 'gain' | 'loss' | 'neutral' }> = {
  breakout:             { label: 'Breakout',      variant: 'accent'  },
  pullback:             { label: 'Pullback',       variant: 'gain'    },
  trend_continuation:   { label: 'Trend',          variant: 'neutral' },
}

function SetupBadge({ type }: { type: string | null }) {
  if (!type) return <span className="text-ink-muted text-xs">—</span>
  const cfg = SETUP_LABELS[type] ?? { label: type, variant: 'neutral' as const }
  return (
    <Badge variant={cfg.variant} className="text-2xs px-1.5 py-0.5 capitalize">
      {cfg.label}
    </Badge>
  )
}

// ── Score bar (1–10) ──────────────────────────────────────────────────────────

function ScoreBar({ score }: { score: number }) {
  const pct = Math.round((score / 10) * 100)
  const color = score >= 8 ? 'bg-accent' : score >= 6 ? 'bg-gain' : score >= 4 ? 'bg-amber-400' : 'bg-border'
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-1.5 bg-border rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-semibold text-ink-primary tabular-nums">{score}</span>
    </div>
  )
}

// ── RS rank pill ──────────────────────────────────────────────────────────────

function RSPill({ rank }: { rank: number | null }) {
  if (rank == null) return <span className="text-ink-muted text-xs">—</span>
  const color = rank >= 80 ? 'text-gain' : rank >= 60 ? 'text-ink-primary' : 'text-ink-muted'
  return <span className={`font-mono text-xs font-semibold ${color}`}>{Math.round(rank)}</span>
}

// ── R:R display ───────────────────────────────────────────────────────────────

function RRCell({ r }: { r: ScreenerResult }) {
  if (r.rr == null || r.stop == null || r.target == null) {
    return <span className="text-ink-muted text-xs">—</span>
  }
  const color = r.rr >= 2 ? 'text-gain' : r.rr >= 1.5 ? 'text-ink-secondary' : 'text-loss'
  return (
    <div className="text-right">
      <div className={`text-xs font-semibold ${color}`}>{fmt(r.rr, 1)}:1</div>
      <div className="text-2xs text-ink-muted font-mono">
        ₹{fmt(r.stop, 0)}→₹{fmt(r.target, 0)}
      </div>
    </div>
  )
}

// ── Column definitions ────────────────────────────────────────────────────────

const COLUMNS: Column<ScreenerResult>[] = [
  {
    key: 'symbol',
    header: 'Symbol',
    sort: r => r.symbol,
    cell: r => (
      <div className="flex items-center gap-1.5">
        <div>
          <div className="font-semibold text-ink-primary flex items-center gap-1">
            {r.symbol}
            {r.earnings_flag && (
              <AlertTriangle size={11} className="text-amber-400" aria-label="Earnings within 10 days" />
            )}
          </div>
          <div className="text-2xs text-ink-muted truncate max-w-[140px]">{r.name}</div>
        </div>
      </div>
    ),
  },
  {
    key: 'score',
    header: 'Score',
    sort: r => r.score,
    align: 'left',
    cell: r => <ScoreBar score={r.score} />,
  },
  {
    key: 'setup',
    header: 'Setup',
    cell: r => <SetupBadge type={r.setup_type} />,
  },
  {
    key: 'rs_rank',
    header: 'RS Rank',
    sort: r => r.rs_rank ?? 0,
    align: 'center',
    cell: r => <RSPill rank={r.rs_rank} />,
  },
  {
    key: 'last_close',
    header: 'Last Close',
    sort: r => r.last_close ?? 0,
    align: 'right',
    cell: r => <span className="font-mono text-xs">₹{fmt(r.last_close, 2)}</span>,
  },
  {
    key: 'pivot',
    header: 'Pivot / ATR',
    align: 'right',
    sort: r => r.entry_pivot ?? 0,
    cell: r => (
      <div className="text-right">
        <div className="text-xs font-mono text-ink-primary">₹{fmt(r.entry_pivot, 2)}</div>
        <div className="text-2xs text-ink-muted">ATR {fmt(r.atr, 1)}</div>
      </div>
    ),
  },
  {
    key: 'rr',
    header: 'R:R',
    sort: r => r.rr ?? 0,
    align: 'right',
    cell: r => <RRCell r={r} />,
  },
  {
    key: 'adx',
    header: 'ADX',
    sort: r => r.adx ?? 0,
    align: 'right',
    cell: r => (
      <span className={`text-xs font-mono ${r.adx != null && r.adx > 25 ? 'text-gain' : 'text-ink-secondary'}`}>
        {fmt(r.adx, 0)}
      </span>
    ),
  },
  {
    key: 'week52',
    header: '52W Range',
    cell: r => (
      <div className="text-xs text-ink-secondary font-mono whitespace-nowrap">
        {fmt(r.week52_low, 0)} — {fmt(r.week52_high, 0)}
      </div>
    ),
  },
]

// ── Stock detail panel ────────────────────────────────────────────────────────

function StockPanel({ symbol, result, onClose }: {
  symbol: string
  result: ScreenerResult | undefined
  onClose: () => void
}) {
  const { data, isLoading, error } = useQuery<StockDetail>({
    queryKey: ['stock-detail', symbol],
    queryFn:  () => getStockDetail(symbol),
    staleTime: 5 * 60 * 1000,
  })

  return (
    <div className="flex flex-col h-full bg-bg-surface">
      <div className="flex items-center justify-between px-4 py-3 border-b border-border flex-shrink-0">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-ink-primary">{symbol}</span>
          {result?.setup_type && <SetupBadge type={result.setup_type} />}
          {result?.earnings_flag && (
            <span className="text-2xs text-amber-400 font-medium">⚠ Earnings soon</span>
          )}
        </div>
        <button onClick={onClose} className="text-ink-muted hover:text-ink-primary transition-colors">
          <X size={16} />
        </button>
      </div>

      {/* Risk summary strip */}
      {result && result.entry_pivot != null && (
        <div className="grid grid-cols-4 gap-px bg-border border-b border-border flex-shrink-0">
          {[
            { label: 'Pivot',  value: `₹${fmt(result.entry_pivot, 2)}` },
            { label: 'Stop',   value: `₹${fmt(result.stop, 2)}`,   cls: 'text-loss' },
            { label: 'Target', value: `₹${fmt(result.target, 2)}`,  cls: 'text-gain' },
            { label: 'R:R',    value: `${fmt(result.rr, 1)}:1`,     cls: result.rr != null && result.rr >= 2 ? 'text-gain' : '' },
          ].map(({ label, value, cls }) => (
            <div key={label} className="bg-bg-surface px-3 py-2 text-center">
              <div className="text-2xs text-ink-muted">{label}</div>
              <div className={`text-xs font-semibold font-mono mt-0.5 ${cls ?? 'text-ink-primary'}`}>{value}</div>
            </div>
          ))}
        </div>
      )}

      <div className="flex-1 overflow-y-auto">
        {isLoading && <PageLoader />}
        {error && <div className="p-4 text-sm text-loss">Failed to load chart data</div>}
        {data && (
          <Suspense fallback={<PageLoader />}>
            <SwingChart data={data} />
          </Suspense>
        )}
      </div>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function SwingScreener() {
  const qc = useQueryClient()
  const [runId, setRunId]               = useState<string | null>(null)
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null)

  const scanMutation = useMutation({
    mutationFn: runScan,
    onSuccess: ({ run_id }) => setRunId(run_id),
  })

  const { data: status } = useQuery({
    queryKey: ['run-status', runId],
    queryFn:  () => getRunStatus(runId!),
    enabled:  !!runId,
    refetchInterval: (q) => {
      const s = q.state.data?.status
      return s === 'running' ? 2000 : false
    },
    select: (d) => {
      if (d.status === 'done' || d.status === 'error') {
        qc.invalidateQueries({ queryKey: ['screener-results'] })
      }
      return d
    },
  })

  const { data: results = [], isLoading: resultsLoading } = useQuery<ScreenerResult[]>({
    queryKey: ['screener-results'],
    queryFn:  getScreenerResults,
    staleTime: 2 * 60 * 1000,
  })

  const isScanning = status?.status === 'running' || scanMutation.isPending
  const selectedResult = results.find(r => r.symbol === selectedSymbol)

  // Summary stats
  const breakouts   = results.filter(r => r.setup_type === 'breakout').length
  const pullbacks   = results.filter(r => r.setup_type === 'pullback').length
  const continuations = results.filter(r => r.setup_type === 'trend_continuation').length

  return (
    <div className="flex h-[calc(100vh-0px)] overflow-hidden bg-bg-base">
      {/* Main panel */}
      <div className={`flex flex-col flex-1 min-w-0 transition-all duration-200 ${selectedSymbol ? 'mr-[520px]' : ''}`}>

        {/* Top bar */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border bg-bg-surface flex-shrink-0">
          <div className="flex items-center gap-3">
            <TrendingUp size={20} className="text-accent" />
            <div>
              <h1 className="font-semibold text-ink-primary">Swing Screener</h1>
              <p className="text-2xs text-ink-muted">NIFTY 500 · Daily · RS-ranked</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {isScanning && status && (
              <div className="text-xs text-ink-secondary">
                Scanning {status.scanned} / {status.total || '…'}
              </div>
            )}
            {status?.status === 'error' && (
              <span className="text-xs text-loss">{status.error ?? 'Scan failed'}</span>
            )}
            <button
              onClick={() => scanMutation.mutate()}
              disabled={isScanning}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-md bg-accent text-white text-sm font-medium
                         hover:bg-accent/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {isScanning ? <RefreshCw size={14} className="animate-spin" /> : <Play size={14} />}
              {isScanning ? 'Scanning…' : 'Run Scan'}
            </button>
          </div>
        </div>

        {/* Results */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {resultsLoading && !results.length && <PageLoader />}

          {!resultsLoading && results.length === 0 && !isScanning && (
            <div className="flex flex-col items-center justify-center h-full gap-3 text-ink-muted">
              <TrendingUp size={40} className="opacity-20" />
              <p className="text-sm">No results yet — run a scan to find swing setups.</p>
            </div>
          )}

          {results.length > 0 && (
            <div className="flex flex-col gap-3">
              {/* Summary pills */}
              <div className="flex items-center gap-3 text-xs text-ink-muted flex-wrap">
                <span>{results.length} setup{results.length !== 1 ? 's' : ''} — click row for chart</span>
                {breakouts > 0     && <span className="text-accent font-medium">{breakouts} breakout{breakouts !== 1 ? 's' : ''}</span>}
                {pullbacks > 0     && <span className="text-gain font-medium">{pullbacks} pullback{pullbacks !== 1 ? 's' : ''}</span>}
                {continuations > 0 && <span className="text-ink-secondary font-medium">{continuations} trend</span>}
              </div>

              <DataTable
                columns={COLUMNS}
                data={results}
                keyFn={r => r.id}
                onRowClick={r => setSelectedSymbol(r.symbol === selectedSymbol ? null : r.symbol)}
                compact
              />
            </div>
          )}
        </div>
      </div>

      {/* Detail panel */}
      {selectedSymbol && (
        <div className="fixed right-0 top-0 bottom-0 w-[520px] border-l border-border shadow-2xl z-10">
          <StockPanel
            symbol={selectedSymbol}
            result={selectedResult}
            onClose={() => setSelectedSymbol(null)}
          />
        </div>
      )}
    </div>
  )
}
