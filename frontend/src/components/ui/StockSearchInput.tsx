import { useState, useEffect, useRef, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Search, X } from 'lucide-react'
import { getAllSymbols } from '../../lib/api'
import Spinner from './Spinner'

interface Props {
  selected:  string
  onSelect:  (symbol: string) => void
  onClear:   () => void
  placeholder?: string
}

export default function StockSearchInput({
  selected,
  onSelect,
  onClear,
  placeholder = 'Search stocks (e.g. TCS, Reliance…)',
}: Props) {
  const [query, setQuery] = useState('')
  const [open,  setOpen]  = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  const { data: allSymbols, isLoading: loadingSymbols } = useQuery({
    queryKey:  ['symbols'],
    queryFn:   () => getAllSymbols('NSE'),
    staleTime: Infinity,
  })

  const filtered = useMemo(() => {
    if (!query.trim() || !allSymbols) return []
    const q = query.toUpperCase()
    return allSymbols
      .filter(s => s.symbol.toUpperCase().includes(q) || s.name.toUpperCase().includes(q))
      .slice(0, 8)
  }, [query, allSymbols])

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  if (selected) return (
    <div className="flex items-center gap-1.5 rounded border border-accent/50 bg-accent/5 px-2.5 py-1.5">
      <span className="font-mono text-xs font-semibold text-accent">{selected}</span>
      <button onClick={onClear} className="text-ink-disabled hover:text-ink-primary">
        <X size={11} />
      </button>
    </div>
  )

  const showDropdown = open && query.trim().length > 0

  return (
    <div ref={ref} className="relative max-w-xs flex-1">
      <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-disabled" />
      <input
        value={query}
        onChange={e => { setQuery(e.target.value); setOpen(true) }}
        onFocus={() => setOpen(true)}
        placeholder={placeholder}
        className="w-full rounded border border-border bg-bg-elevated py-2 pl-7 pr-3 text-xs text-ink-primary placeholder:text-ink-disabled focus:border-accent focus:outline-none"
      />
      {query && (
        <button
          onClick={() => { setQuery(''); setOpen(false) }}
          className="absolute right-2 top-1/2 -translate-y-1/2 text-ink-disabled hover:text-ink-primary"
        >
          <X size={11} />
        </button>
      )}
      {showDropdown && (
        <div className="absolute left-0 right-0 top-full z-50 mt-1 overflow-hidden rounded-md border border-border bg-bg-surface shadow-card-lg">
          {loadingSymbols ? (
            <div className="flex items-center gap-2 px-3 py-2.5 text-xs text-ink-muted">
              <Spinner size={12} />
              Loading NSE stocks…
            </div>
          ) : filtered.length === 0 ? (
            <div className="px-3 py-2.5 text-xs text-ink-muted">
              No matches for "{query}"
            </div>
          ) : (
            filtered.map(s => (
              <button
                key={s.symbol}
                onMouseDown={e => {
                  e.preventDefault()
                  onSelect(s.symbol)
                  setQuery('')
                  setOpen(false)
                }}
                className="flex w-full items-center gap-3 px-3 py-2 text-left transition-colors hover:bg-bg-elevated"
              >
                <span className="w-20 shrink-0 font-mono text-xs font-semibold text-ink-primary">
                  {s.symbol}
                </span>
                <span className="truncate text-xs text-ink-muted">{s.name}</span>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  )
}
