import { useState, useEffect, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Sparkles, Clock, RefreshCw, TrendingUp, TrendingDown,
  Minus, ChevronDown, ChevronUp, AlertTriangle, Eye, Check, KeyRound, Layers,
} from 'lucide-react'
import { cn } from '../lib/utils'
import {
  getMyAIKey, getCachedAIOverview, streamAIOverview,
  type AIOverviewResult, type AIStockAnalysis, type AIKeyInfo,
} from '../lib/api'
import Spinner, { ErrorState } from '../components/ui/Spinner'
import ProviderSetup from '../components/ai/ProviderSetup'
import UniverseSelector from '../components/ai/UniverseSelector'

// ── Verdict config ────────────────────────────────────────────────────────

type QualityVerdict = AIStockAnalysis['quality_verdict']
type Conviction     = AIStockAnalysis['conviction']

const VERDICT_CFG: Record<QualityVerdict, {
  bg: string; border: string; text: string
  icon: React.ElementType; label: string
}> = {
  'Genuinely Discounted': {
    bg: 'bg-gain/10', border: 'border-gain/30', text: 'text-gain',
    icon: TrendingUp, label: 'Genuinely Discounted',
  },
  'Watch': {
    bg: 'bg-warn/10', border: 'border-warn/30', text: 'text-warn',
    icon: Eye, label: 'Watch',
  },
  'Value Trap': {
    bg: 'bg-loss/10', border: 'border-loss/30', text: 'text-loss',
    icon: AlertTriangle, label: 'Value Trap',
  },
  'Overvalued': {
    bg: 'bg-bg-elevated', border: 'border-border', text: 'text-ink-secondary',
    icon: TrendingDown, label: 'Overvalued',
  },
}

const CONVICTION_CFG: Record<Conviction, { dot: string }> = {
  High:   { dot: 'bg-gain' },
  Medium: { dot: 'bg-warn' },
  Low:    { dot: 'bg-ink-disabled' },
}

// ── Small helpers ─────────────────────────────────────────────────────────

function SignalPill({ signal, label }: { signal: string; label: string }) {
  return (
    <div className={cn(
      'flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium',
      signal === 'Bullish' ? 'bg-gain/10 text-gain'
        : signal === 'Bearish' ? 'bg-loss/10 text-loss'
        : 'bg-bg-elevated text-ink-disabled',
    )}>
      {signal === 'Bullish' ? <TrendingUp size={8} />
        : signal === 'Bearish' ? <TrendingDown size={8} />
        : <Minus size={8} />}
      {label}
    </div>
  )
}

// ── StockCard ─────────────────────────────────────────────────────────────

function StockCard({ stock }: { stock: AIStockAnalysis }) {
  const [expanded, setExpanded] = useState(false)
  const cfg  = VERDICT_CFG[stock.quality_verdict]
  const conv = CONVICTION_CFG[stock.conviction]
  const VIcon = cfg.icon

  return (
    <div className={cn(
      'rounded-lg border p-4 transition-shadow hover:shadow-card',
      cfg.bg, cfg.border,
    )}>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-sm font-bold text-ink-primary">{stock.symbol}</span>
            <span className="truncate max-w-[130px] text-[10px] text-ink-disabled">{stock.company_name}</span>
          </div>
          <p className="mt-0.5 text-[10px] text-ink-disabled">{stock.sector}</p>
        </div>

        <div className="flex shrink-0 flex-col items-end gap-1.5">
          <div className={cn('flex items-center gap-1 text-xs font-semibold', cfg.text)}>
            <VIcon size={11} />
            {cfg.label}
          </div>
          <div className="flex items-center gap-1.5">
            <div className={cn('h-1.5 w-1.5 rounded-full', conv.dot)} />
            <span className="text-[10px] text-ink-muted">{stock.conviction} conviction</span>
          </div>
        </div>
      </div>

      {stock.current_price != null && (
        <p className="mt-2 font-mono text-lg font-semibold text-ink-primary">
          ₹{stock.current_price.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
        </p>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-border/40 pt-3 text-xs">
        {stock.pe != null && (
          <div>
            <span className="text-ink-disabled">P/E </span>
            <span className="num font-semibold text-ink-primary">{stock.pe}</span>
          </div>
        )}
        {stock.roe != null && (
          <div>
            <span className="text-ink-disabled">ROE </span>
            <span className="num font-semibold text-gain">{stock.roe}%</span>
          </div>
        )}
        {stock.de != null && (
          <div>
            <span className="text-ink-disabled">D/E </span>
            <span className="num font-semibold text-ink-primary">{stock.de}</span>
          </div>
        )}
        {stock.rsi != null && (
          <div>
            <span className="text-ink-disabled">RSI </span>
            <span className={cn(
              'num font-semibold',
              stock.rsi > 70 ? 'text-loss' : stock.rsi < 30 ? 'text-gain' : 'text-ink-primary',
            )}>{stock.rsi}</span>
          </div>
        )}
      </div>

      <div className="mt-2 flex flex-wrap gap-1.5">
        <SignalPill signal={stock.macd_signal} label="MACD" />
        <SignalPill signal={stock.ema_signal}  label="EMA"  />
        <SignalPill signal={stock.adx_signal}  label="ADX"  />
        <SignalPill signal={stock.bb_signal}   label="BB"   />
      </div>

      <div className="mt-3 grid grid-cols-3 gap-2">
        {([
          { label: 'Entry',  val: stock.entry_comment,  color: 'text-gain'   },
          { label: 'Stop',   val: stock.stop_comment,   color: 'text-loss'   },
          { label: 'Target', val: stock.target_comment, color: 'text-accent' },
        ] as const).map(({ label, val, color }) => (
          <div key={label} className="rounded bg-bg-elevated/60 p-2">
            <p className="text-[9px] font-semibold uppercase tracking-wider text-ink-disabled">{label}</p>
            <p className={cn('mt-0.5 text-[10px] leading-snug', color)}>{val}</p>
          </div>
        ))}
      </div>

      <button
        onClick={() => setExpanded(e => !e)}
        className="mt-3 flex w-full items-center gap-2 text-left text-xs text-ink-muted transition-colors hover:text-ink-secondary"
      >
        <Sparkles size={10} className="shrink-0 text-accent/70" />
        <span className="flex-1 font-medium">AI Reasoning</span>
        {expanded ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
      </button>
      {expanded && (
        <p className="mt-2 rounded border border-accent/20 bg-accent/5 px-3 py-2 text-[11px] leading-relaxed text-ink-secondary">
          {stock.reasoning}
        </p>
      )}
    </div>
  )
}

// ── Stage progress ────────────────────────────────────────────────────────

const STAGES = [
  { label: 'Loading universe',          est: '~5s'  },
  { label: 'Parallel technical analysis', est: '~20s' },
  { label: 'AI reasoning',              est: '~15s' },
]

type StageStatus = 'pending' | 'running' | 'done'

function StageProgress({
  stageStatus,
  batch,
}: {
  stageStatus: StageStatus[]
  batch: { done: number; total: number } | null
}) {
  const [elapsed, setElapsed] = useState(0)
  const ref = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    ref.current = setInterval(() => setElapsed(e => e + 1), 1000)
    return () => { if (ref.current) clearInterval(ref.current) }
  }, [])

  return (
    <div className="rounded-lg border border-border bg-bg-surface p-6">
      <div className="mb-5 flex items-center gap-3">
        <Spinner size={16} />
        <p className="text-sm font-semibold text-ink-primary">Running AI Analysis Pipeline…</p>
        <span className="ml-auto font-mono text-xs text-ink-muted">{elapsed}s</span>
      </div>
      <div className="space-y-3">
        {STAGES.map((stage, i) => {
          const status = stageStatus[i] ?? 'pending'
          const isAIStage = i === 2
          return (
            <div key={i} className="flex items-center gap-3">
              <div className={cn(
                'flex h-5 w-5 shrink-0 items-center justify-center rounded-full border transition-colors',
                status === 'done'
                  ? 'border-gain/50 bg-gain/15 text-gain'
                  : status === 'running'
                  ? 'border-accent/60 bg-accent/15 text-accent'
                  : 'border-border bg-bg-elevated text-ink-disabled',
              )}>
                {status === 'done'
                  ? <Check size={11} strokeWidth={3} />
                  : status === 'running'
                  ? <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
                  : <span className="font-mono text-[9px]">{i + 1}</span>}
              </div>
              <div className="flex-1">
                <p className={cn(
                  'text-xs transition-colors',
                  status === 'done'      ? 'text-ink-secondary'
                  : status === 'running' ? 'text-ink-primary'
                  : 'text-ink-disabled',
                )}>
                  {stage.label}
                </p>
                {isAIStage && status === 'running' && batch && batch.total > 0 && (
                  <p className="mt-0.5 font-mono text-[10px] text-ink-disabled">
                    Batch {batch.done} of {batch.total}
                  </p>
                )}
              </div>
              <span className="font-mono text-[10px] text-ink-disabled">{stage.est}</span>
            </div>
          )
        })}
      </div>
      <p className="mt-5 text-xs text-ink-muted">
        Result is cached for 4 hours per universe + provider combo
      </p>
    </div>
  )
}

// ── Filter bar ────────────────────────────────────────────────────────────

type Filter = QualityVerdict | 'All'

function FilterBar({
  active, counts, onChange,
}: {
  active: Filter
  counts: Partial<Record<string, number>>
  onChange: (v: Filter) => void
}) {
  const options: { key: Filter; label: string }[] = [
    { key: 'All',                  label: `All (${counts['All'] ?? 0})` },
    { key: 'Genuinely Discounted', label: `Discounted (${counts['Genuinely Discounted'] ?? 0})` },
    { key: 'Watch',                label: `Watch (${counts['Watch'] ?? 0})` },
    { key: 'Value Trap',           label: `Trap (${counts['Value Trap'] ?? 0})` },
    { key: 'Overvalued',           label: `Overvalued (${counts['Overvalued'] ?? 0})` },
  ]
  return (
    <div className="flex flex-wrap gap-2">
      {options.map(({ key, label }) => (
        <button
          key={key}
          onClick={() => onChange(key)}
          className={cn(
            'rounded border px-3 py-1.5 text-xs font-medium transition-all',
            active === key
              ? 'border-accent bg-accent/10 text-accent'
              : 'border-border text-ink-muted hover:text-ink-secondary',
          )}
        >
          {label}
        </button>
      ))}
    </div>
  )
}

// ── Results header ────────────────────────────────────────────────────────

function ResultsHeader({
  result, keyInfo, onChangeUniverse, onChangeProvider, onRefresh, isRefreshing,
}: {
  result:           AIOverviewResult
  keyInfo:          AIKeyInfo | null
  onChangeUniverse: () => void
  onChangeProvider: () => void
  onRefresh:        () => void
  isRefreshing:     boolean
}) {
  const ago = Math.round((Date.now() - new Date(result.generated_at).getTime()) / 60_000)
  const timeStr = ago < 60 ? `${ago}m ago` : `${Math.floor(ago / 60)}h ${ago % 60}m ago`

  return (
    <div className="flex flex-wrap items-center gap-3">
      <div>
        <div className="flex items-center gap-2">
          <Clock size={12} className="text-ink-disabled" />
          <span className="text-xs text-ink-muted">
            Last analyzed {timeStr}
            {result.from_cache && <span className="ml-1.5 text-ink-disabled">(cached)</span>}
          </span>
        </div>
        <p className="mt-0.5 text-[10px] text-ink-disabled">
          {result.candidate_count} stocks · {result.universe}
          {result.extras?.length ? ` + ${result.extras.length} extra` : ''}
          {keyInfo && <span> · via <span className="font-mono text-ink-muted">{result.model}</span></span>}
        </p>
      </div>

      <div className="ml-auto flex items-center gap-2">
        <button
          onClick={onChangeUniverse}
          className="flex items-center gap-1.5 rounded border border-border px-3 py-1.5 text-xs text-ink-muted transition-colors hover:border-ink-muted hover:text-ink-secondary"
        >
          <Layers size={11} />
          Change universe
        </button>
        <button
          onClick={onChangeProvider}
          className="flex items-center gap-1.5 rounded border border-border px-3 py-1.5 text-xs text-ink-muted transition-colors hover:border-ink-muted hover:text-ink-secondary"
        >
          <KeyRound size={11} />
          Change provider
        </button>
        <button
          onClick={onRefresh}
          disabled={isRefreshing}
          className="flex items-center gap-2 rounded border border-border px-3 py-1.5 text-xs text-ink-muted transition-colors hover:border-ink-muted hover:text-ink-secondary disabled:opacity-40"
        >
          <RefreshCw size={12} className={isRefreshing ? 'animate-spin' : ''} />
          Force refresh
        </button>
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────

type Mode = 'setup-key' | 'pick-universe' | 'running' | 'results'

export default function AIOverview() {
  const qc = useQueryClient()
  const [filter, setFilter] = useState<Filter>('All')
  const [mode, setMode]     = useState<Mode | null>(null)
  const [config, setConfig] = useState<{ universe: string; extras: string[] } | null>(null)
  const [stageStatus, setStageStatus] = useState<StageStatus[]>(() => STAGES.map(() => 'pending'))
  const [batch, setBatch] = useState<{ done: number; total: number } | null>(null)
  const [result, setResult] = useState<AIOverviewResult | null>(null)

  const { data: keyInfo, isLoading: isKeyLoading } = useQuery({
    queryKey: ['ai-key'],
    queryFn:  getMyAIKey,
    retry:    false,
  })

  // Resolve initial mode once we know whether a key is saved.
  useEffect(() => {
    if (isKeyLoading || mode) return
    setMode(keyInfo ? 'pick-universe' : 'setup-key')
  }, [isKeyLoading, keyInfo, mode])

  // When user picks a universe, attempt cached fetch first; if hit, skip stream.
  const cachedQuery = useQuery({
    queryKey: ['ai-overview-cached', config?.universe, config?.extras?.join(',')],
    queryFn:  () => getCachedAIOverview(config!.universe, config!.extras),
    enabled:  !!config && mode === 'running',
    retry:    false,
    staleTime: 0,
  })

  const streamMut = useMutation({
    mutationFn: async (force: boolean) => {
      if (!config) throw new Error('No config')
      setStageStatus(STAGES.map(() => 'pending'))
      setBatch(null)
      return streamAIOverview(config.universe, config.extras, force, (ev) => {
        if (ev.type === 'stage') {
          setStageStatus(prev => {
            const next = [...prev]
            next[ev.stage - 1] = ev.status
            return next
          })
        } else if (ev.type === 'batch') {
          setBatch({ done: ev.done, total: ev.total })
        }
      })
    },
    onSuccess: (data) => {
      setResult(data)
      setMode('results')
      setFilter('All')
    },
  })

  // Once a config is set + cache check resolves: hit → results, miss → run stream.
  useEffect(() => {
    if (mode !== 'running' || !config) return
    if (cachedQuery.isLoading) return
    if (cachedQuery.data) {
      setStageStatus(STAGES.map(() => 'done'))
      setResult(cachedQuery.data)
      setMode('results')
    } else if (cachedQuery.isError && !streamMut.isPending && !streamMut.isSuccess) {
      streamMut.mutate(false)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, config, cachedQuery.isLoading, cachedQuery.data, cachedQuery.isError])

  function handleAnalyse(universe: string, extras: string[]) {
    setConfig({ universe, extras })
    setResult(null)
    streamMut.reset()
    setMode('running')
  }

  function handleForceRefresh() {
    if (!config) return
    streamMut.reset()
    setResult(null)
    setMode('running')
    streamMut.mutate(true)
  }

  function handleChangeUniverse() {
    setResult(null)
    streamMut.reset()
    setMode('pick-universe')
  }

  function handleChangeProvider() {
    setResult(null)
    streamMut.reset()
    setMode('setup-key')
  }

  const filtered = result?.stocks.filter(s =>
    filter === 'All' || s.quality_verdict === filter
  ) ?? []

  const counts = result?.stocks.reduce<Record<string, number>>((acc, s) => {
    acc[s.quality_verdict] = (acc[s.quality_verdict] ?? 0) + 1
    acc['All'] = (acc['All'] ?? 0) + 1
    return acc
  }, { All: 0 }) ?? { All: 0 }

  return (
    <div className="animate-fade-up space-y-6">

      {/* Page header */}
      <div className="flex items-start gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-border bg-bg-elevated">
          <Sparkles size={16} className="text-accent" />
        </div>
        <div className="flex-1">
          <h1 className="text-xl font-semibold text-ink-primary">AI Overview</h1>
          <p className="mt-0.5 text-sm text-ink-muted">
            Pick a universe → technical enrichment → AI reasoning · 4h cache
          </p>
        </div>
        {keyInfo && mode !== 'setup-key' && (
          <div className="flex items-center gap-2 rounded border border-border bg-bg-surface px-3 py-1.5">
            <KeyRound size={11} className="text-accent" />
            <span className="text-[11px] text-ink-muted">
              <span className="font-medium text-ink-secondary">{keyInfo.provider}</span>
              <span className="mx-1.5 text-ink-disabled">·</span>
              <span className="font-mono">{keyInfo.model}</span>
              <span className="ml-1.5 text-ink-disabled">…{keyInfo.key_last4}</span>
            </span>
            <button
              onClick={handleChangeProvider}
              className="text-[10px] text-accent hover:underline"
            >
              change
            </button>
          </div>
        )}
      </div>

      {isKeyLoading && (
        <div className="flex items-center justify-center rounded-lg border border-border bg-bg-surface py-16">
          <Spinner size={20} />
        </div>
      )}

      {mode === 'setup-key' && (
        <ProviderSetup
          initialProvider={keyInfo?.provider}
          onSaved={() => {
            qc.invalidateQueries({ queryKey: ['ai-key'] })
            setMode('pick-universe')
          }}
        />
      )}

      {mode === 'pick-universe' && (
        <UniverseSelector onAnalyse={handleAnalyse} />
      )}

      {mode === 'running' && (
        <StageProgress stageStatus={stageStatus} batch={batch} />
      )}

      {streamMut.error && mode === 'running' && (
        <div className="space-y-4">
          <ErrorState message={(streamMut.error as Error).message} />
          <div className="flex justify-center gap-2">
            <button
              onClick={handleChangeUniverse}
              className="flex items-center gap-2 rounded border border-border px-4 py-2 text-sm text-ink-secondary hover:text-ink-primary transition-colors"
            >
              <Layers size={14} />
              Pick a different universe
            </button>
            <button
              onClick={handleForceRefresh}
              className="flex items-center gap-2 rounded border border-border px-4 py-2 text-sm text-ink-secondary hover:text-ink-primary transition-colors"
            >
              <RefreshCw size={14} />
              Try again
            </button>
          </div>
        </div>
      )}

      {mode === 'results' && result && (
        <div className="space-y-4">
          <ResultsHeader
            result={result}
            keyInfo={keyInfo ?? null}
            onChangeUniverse={handleChangeUniverse}
            onChangeProvider={handleChangeProvider}
            onRefresh={handleForceRefresh}
            isRefreshing={streamMut.isPending}
          />

          <FilterBar active={filter} counts={counts} onChange={setFilter} />

          {filtered.length === 0 && (
            <p className="py-12 text-center text-sm text-ink-muted">No stocks match this filter.</p>
          )}

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {filtered.map(stock => (
              <StockCard key={stock.symbol} stock={stock} />
            ))}
          </div>
        </div>
      )}

    </div>
  )
}
