import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { runMagicFormula, runQARP } from '../lib/api'
import Spinner from '../components/ui/Spinner'
import DataTable, { Column } from '../components/ui/DataTable'
import StockBrowser from '../components/ui/StockBrowser'
import { X, Wand2, Sparkles } from 'lucide-react'
import { cn } from '../lib/utils'

function ScoreBar({ rank, total }: { rank: number; total: number }) {
  const pct = Math.round((1 - rank / total) * 100)
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-bg-overlay">
        <div
          className="h-full rounded-full bg-accent transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="num font-mono text-xs text-ink-muted">#{rank}</span>
    </div>
  )
}

type Verdict = 'BUY' | 'WATCH' | 'AVOID'

function VerdictBadge({ v }: { v: Verdict }) {
  const cfg: Record<Verdict, { label: string; cls: string }> = {
    BUY:   { label: 'Buy',   cls: 'bg-[rgba(63,185,80,.12)] text-gain border-[rgba(63,185,80,.3)]' },
    WATCH: { label: 'Watch', cls: 'bg-[rgba(210,153,34,.12)] text-warn border-[rgba(210,153,34,.3)]' },
    AVOID: { label: 'Avoid', cls: 'bg-[rgba(248,81,73,.12)] text-loss border-[rgba(248,81,73,.3)]' },
  }
  const { label, cls } = cfg[v] ?? cfg.AVOID
  return (
    <span className={cn('inline-block rounded border px-2 py-0.5 text-xs font-semibold', cls)}>
      {label}
    </span>
  )
}

export default function ValueScreen() {
  const [selected, setSelected] = useState<string[]>([])
  const [screener, setScreener] = useState<'magic' | 'qarp'>('magic')
  const [results, setResults]   = useState<Record<string, unknown>[] | null>(null)

  const magicMut = useMutation({
    mutationFn: () => runMagicFormula(selected),
    onSuccess:  d => setResults(d.results),
  })
  const qarpMut = useMutation({
    mutationFn: () => runQARP(selected),
    onSuccess:  d => setResults(d.results),
  })

  function toggle(sym: string) {
    setSelected(prev =>
      prev.includes(sym) ? prev.filter(s => s !== sym) : [...prev, sym]
    )
    setResults(null)
  }

  const running = magicMut.isPending || qarpMut.isPending

  const resultCols = results && results.length > 0
    ? Object.keys(results[0]).map<Column<Record<string, unknown>>>(k => {
        if (k === 'Verdict') {
          return {
            key: k, header: 'Verdict', align: 'center',
            cell: r => <VerdictBadge v={String(r[k]) as Verdict} />,
            sort: r => ({ BUY: 0, WATCH: 1, AVOID: 2 }[String(r[k])] ?? 3),
          }
        }
        return {
          key:    k,
          header: k.replace(/_/g, ' '),
          cell:   r => {
            const v = r[k]
            if (typeof v === 'number') {
              return <span className="num font-mono text-ink-primary">{Number(v).toFixed(2)}</span>
            }
            return <span className="text-ink-primary">{String(v)}</span>
          },
          sort: r => typeof r[k] === 'number' ? Number(r[k]) : String(r[k]),
          align: typeof results[0][k] === 'number' ? 'right' : 'left',
        }
      })
    : []

  return (
    <div className="flex h-[calc(100vh-104px)] gap-5 animate-fade-up">
      {/* Left: Stock browser */}
      <StockBrowser
        className="w-[340px] shrink-0"
        selected={selected}
        onToggle={toggle}
      />

      {/* Right: Selected + results */}
      <div className="flex flex-1 flex-col gap-4 overflow-hidden">

        {/* Selected chips */}
        <div className="rounded-md border border-border bg-bg-surface p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-xs font-semibold uppercase tracking-widest text-ink-secondary">
              Selected ({selected.length})
            </h3>
            {selected.length > 0 && (
              <button
                onClick={() => { setSelected([]); setResults(null) }}
                className="text-xs text-ink-muted hover:text-loss transition-colors"
              >
                Clear all
              </button>
            )}
          </div>

          {selected.length === 0 ? (
            <p className="text-xs text-ink-disabled">Add stocks from the panel on the left.</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {selected.map(sym => (
                <button
                  key={sym}
                  onClick={() => toggle(sym)}
                  className="flex items-center gap-1.5 rounded-sm border border-accent/30 bg-[rgba(56,139,253,.08)] px-2.5 py-1 font-mono text-xs font-semibold text-accent hover:border-loss/50 hover:bg-[rgba(248,81,73,.08)] hover:text-loss transition-colors"
                >
                  {sym} <X size={10} />
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Screener controls */}
        <div className="flex items-center gap-3">
          <button
            onClick={() => setScreener('magic')}
            className={cn(
              'flex items-center gap-2 rounded border px-4 py-2 text-sm font-medium transition-all',
              screener === 'magic'
                ? 'border-accent bg-[rgba(56,139,253,.1)] text-accent'
                : 'border-border bg-bg-surface text-ink-secondary hover:bg-bg-elevated',
            )}
          >
            <Wand2 size={14} /> Magic Formula
          </button>
          <button
            onClick={() => setScreener('qarp')}
            className={cn(
              'flex items-center gap-2 rounded border px-4 py-2 text-sm font-medium transition-all',
              screener === 'qarp'
                ? 'border-accent bg-[rgba(56,139,253,.1)] text-accent'
                : 'border-border bg-bg-surface text-ink-secondary hover:bg-bg-elevated',
            )}
          >
            <Sparkles size={14} /> QARP
          </button>
          <button
            disabled={selected.length === 0 || running}
            onClick={() => screener === 'magic' ? magicMut.mutate() : qarpMut.mutate()}
            className={cn(
              'ml-auto flex items-center gap-2 rounded border px-5 py-2 text-sm font-semibold transition-all',
              selected.length === 0 || running
                ? 'border-border text-ink-disabled cursor-not-allowed'
                : 'border-accent bg-accent text-white hover:bg-accent/90',
            )}
          >
            {running ? <><Spinner size={14} /> Running…</> : 'Run Screener'}
          </button>
        </div>

        {/* QARP criteria legend */}
        {screener === 'qarp' && (
          <div className="flex flex-wrap items-center gap-4 rounded-md border border-border bg-bg-surface px-4 py-3 text-xs text-ink-muted">
            <span className="font-semibold text-ink-secondary">Verdict criteria:</span>
            <span><span className="font-semibold text-gain">Buy</span> - ROE &gt; 20%, D/E &lt; 0.5, Forward P/E &lt; 15 (all three met)</span>
            <span><span className="font-semibold text-warn">Watch</span> - two of three criteria met</span>
            <span><span className="font-semibold text-loss">Avoid</span> - fewer than two criteria met</span>
          </div>
        )}

        {/* Results */}
        <div className="flex-1 overflow-auto rounded-md border border-border bg-bg-surface shadow-card">
          {!results && !running && (
            <div className="flex h-full items-center justify-center">
              <p className="text-sm text-ink-disabled">
                Select stocks and run a screener to see results.
              </p>
            </div>
          )}
          {running && (
            <div className="flex h-full flex-col items-center justify-center gap-3">
              <Spinner size={24} />
              <p className="text-sm text-ink-muted">Fetching financials and running screener…</p>
            </div>
          )}
          {results && (
            <div className="p-4">
              <p className="mb-3 text-xs text-ink-muted">
                {results.length} results - {screener === 'magic' ? 'ranked by Earnings Yield + ROC' : 'ROE, D/E & P/E screened'}
              </p>
              <DataTable
                columns={resultCols}
                data={results}
                keyFn={r => String(r['Ticker'] ?? r['ticker'] ?? r['Symbol'] ?? JSON.stringify(r))}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
