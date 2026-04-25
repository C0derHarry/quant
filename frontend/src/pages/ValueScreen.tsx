import { useState, useCallback } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { getAllSymbols, runMagicFormula, runQARP } from '../lib/api'
import { PageLoader, ErrorState } from '../components/ui/Spinner'
import Spinner from '../components/ui/Spinner'
import DataTable, { Column } from '../components/ui/DataTable'
import { Search, X, Plus, CheckCircle2, Wand2, Sparkles } from 'lucide-react'
import { cn } from '../lib/utils'

const PAGE = 15

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

export default function ValueScreen() {
  const [search, setSearch]     = useState('')
  const [page, setPage]         = useState(0)
  const [selected, setSelected] = useState<string[]>([])
  const [screener, setScreener] = useState<'magic' | 'qarp'>('magic')
  const [results, setResults]   = useState<Record<string, unknown>[] | null>(null)

  const { data: symbols, isLoading, error } = useQuery({
    queryKey: ['symbols'],
    queryFn:  () => getAllSymbols('NSE'),
    staleTime: Infinity,
  })

  const magicMut = useMutation({
    mutationFn: () => runMagicFormula(selected),
    onSuccess:  d => setResults(d.results),
  })
  const qarpMut = useMutation({
    mutationFn: () => runQARP(selected),
    onSuccess:  d => setResults(d.results),
  })

  const filtered = (symbols ?? []).filter(s =>
    search ? s.symbol.includes(search.toUpperCase()) || s.name.toUpperCase().includes(search.toUpperCase()) : true
  )
  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE))
  const pageItems  = filtered.slice(page * PAGE, (page + 1) * PAGE)

  function toggle(sym: string) {
    setSelected(prev =>
      prev.includes(sym) ? prev.filter(s => s !== sym) : [...prev, sym]
    )
    setResults(null)
  }

  const running = magicMut.isPending || qarpMut.isPending

  const resultCols = results && results.length > 0
    ? Object.keys(results[0]).map<Column<Record<string, unknown>>>(k => ({
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
      }))
    : []

  if (isLoading) return <PageLoader label="Loading symbols…" />
  if (error)     return <ErrorState message={error.message} />

  return (
    <div className="flex h-[calc(100vh-104px)] gap-5 animate-fade-up">
      {/* Left: Stock browser */}
      <div className="flex w-[340px] shrink-0 flex-col rounded-md border border-border bg-bg-surface shadow-card">
        <div className="border-b border-border p-4">
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-widest text-ink-secondary">
            NSE Universe
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
            const sel = selected.includes(s.symbol)
            return (
              <button
                key={s.symbol}
                onClick={() => toggle(s.symbol)}
                className={cn(
                  'flex w-full items-center justify-between px-4 py-2.5 text-left transition-colors',
                  'border-b border-border/40 last:border-0',
                  sel ? 'bg-[rgba(56,139,253,.06)]' : 'hover:bg-bg-elevated',
                )}
              >
                <div>
                  <p className={cn('font-mono text-sm font-semibold', sel ? 'text-accent' : 'text-ink-primary')}>
                    {s.symbol}
                  </p>
                  <p className="mt-0.5 max-w-[200px] truncate text-xs text-ink-muted">{s.name}</p>
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
          <button
            onClick={() => setPage(p => Math.max(0, p - 1))}
            disabled={page === 0}
            className="text-xs text-ink-secondary hover:text-ink-primary disabled:text-ink-disabled"
          >
            ← Prev
          </button>
          <span className="text-xs text-ink-muted">
            {page + 1} / {totalPages}
          </span>
          <button
            onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
            disabled={page >= totalPages - 1}
            className="text-xs text-ink-secondary hover:text-ink-primary disabled:text-ink-disabled"
          >
            Next →
          </button>
        </div>
      </div>

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
                {results.length} results — {screener === 'magic' ? 'ranked by Earnings Yield + ROC' : 'filtered by ROE, D/E, P/E'}
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
