import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Layers, X, Sparkles } from 'lucide-react'
import { cn } from '../../lib/utils'
import { getAIUniverses } from '../../lib/api'
import StockSearchInput from '../ui/StockSearchInput'
import Spinner from '../ui/Spinner'

interface Props {
  onAnalyse: (universe: string, extras: string[]) => void
  disabled?: boolean
}

export default function UniverseSelector({ onAnalyse, disabled }: Props) {
  const { data: universes, isLoading } = useQuery({
    queryKey:  ['ai-universes'],
    queryFn:   getAIUniverses,
    staleTime: Infinity,
  })

  const [universe, setUniverse]   = useState<string>('')
  const [extras,   setExtras]     = useState<string[]>([])
  const [searchSel, setSearchSel] = useState<string>('')

  // Pick a sensible default once universes load.
  useEffect(() => {
    if (!universe && universes && universes.length) setUniverse(universes[0])
  }, [universe, universes])

  function addExtra(symbol: string) {
    if (!extras.includes(symbol)) setExtras([...extras, symbol])
    setSearchSel('')
  }

  function removeExtra(symbol: string) {
    setExtras(extras.filter(s => s !== symbol))
  }

  const canRun = !!universe && !disabled

  return (
    <div className="space-y-5 rounded-lg border border-border bg-bg-surface p-6">
      <div className="flex items-start gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-accent/30 bg-accent/10">
          <Layers size={16} className="text-accent" />
        </div>
        <div>
          <h2 className="text-base font-semibold text-ink-primary">Choose what to analyse</h2>
          <p className="mt-0.5 text-xs text-ink-muted">
            Pick a stock universe; optionally add extra tickers via search.
          </p>
        </div>
      </div>

      {/* Universe radios */}
      <div className="space-y-1.5">
        <label className="text-xs font-semibold uppercase tracking-wider text-ink-disabled">
          Stock universe
        </label>
        {isLoading || !universes ? (
          <div className="flex items-center gap-2 px-1 py-3 text-xs text-ink-muted">
            <Spinner size={12} /> Loading universes…
          </div>
        ) : (
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {universes.map(u => {
              const active = u === universe
              return (
                <button
                  key={u}
                  onClick={() => setUniverse(u)}
                  className={cn(
                    'flex items-center justify-between rounded border px-3 py-2 text-left transition-all',
                    active
                      ? 'border-accent bg-accent/10 text-accent'
                      : 'border-border bg-bg-elevated text-ink-secondary hover:border-ink-muted',
                  )}
                >
                  <span className="text-xs font-medium">{u}</span>
                  {active && <span className="text-[10px] font-semibold uppercase">selected</span>}
                </button>
              )
            })}
          </div>
        )}
      </div>

      {/* Extras */}
      <div className="space-y-2">
        <label className="text-xs font-semibold uppercase tracking-wider text-ink-disabled">
          Add specific stocks (optional)
        </label>
        <StockSearchInput
          selected={searchSel}
          onSelect={addExtra}
          onClear={() => setSearchSel('')}
        />
        {extras.length > 0 && (
          <div className="flex flex-wrap gap-1.5 pt-1">
            {extras.map(sym => (
              <span
                key={sym}
                className="flex items-center gap-1 rounded border border-accent/40 bg-accent/10 px-2 py-1 font-mono text-[11px] font-semibold text-accent"
              >
                {sym}
                <button
                  onClick={() => removeExtra(sym)}
                  className="text-accent/70 hover:text-accent"
                >
                  <X size={10} />
                </button>
              </span>
            ))}
          </div>
        )}
      </div>

      <button
        onClick={() => onAnalyse(universe, extras)}
        disabled={!canRun}
        className={cn(
          'flex items-center gap-3 rounded-lg border px-6 py-3 text-sm font-semibold transition-all',
          canRun
            ? 'border-accent/50 bg-accent/10 text-accent hover:bg-accent/20'
            : 'border-border text-ink-disabled cursor-not-allowed',
        )}
      >
        <Sparkles size={16} />
        Let AI Analyse
      </button>
    </div>
  )
}
