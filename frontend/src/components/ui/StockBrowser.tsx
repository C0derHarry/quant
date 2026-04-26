import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  getAllSymbols, getSectorNames, getSectorSymbols, getStockNames,
  type SymbolEntry,
} from '../../lib/api'
import { Search, Plus, CheckCircle2 } from 'lucide-react'
import { cn } from '../../lib/utils'
import Spinner from './Spinner'

const PAGE = 15

interface Props {
  selected: string[]
  onToggle: (symbol: string) => void
  maxSelected?: number
  className?: string
  hideSector?: boolean
}

export default function StockBrowser({ selected, onToggle, maxSelected = 5, className, hideSector = false }: Props) {
  const [search, setSearch] = useState('')
  const [page, setPage]     = useState(0)
  const [sector, setSector] = useState('')

  const { data: allSymbols, isLoading: loadingAll } = useQuery({
    queryKey: ['symbols'],
    queryFn:  () => getAllSymbols('NSE'),
    staleTime: Infinity,
  })

  const { data: sectorNames } = useQuery({
    queryKey: ['sectorNames'],
    queryFn:  getSectorNames,
    staleTime: Infinity,
  })

  const { data: sectorSymbols, isLoading: loadingSector } = useQuery({
    queryKey: ['sectorSymbols', sector],
    queryFn:  () => getSectorSymbols(sector),
    enabled:  !!sector,
    staleTime: 1000 * 60 * 5,
  })

  const baseList: SymbolEntry[] = sector ? (sectorSymbols ?? []) : (allSymbols ?? [])

  const filtered = baseList.filter(s => {
    if (!search) return true
    const q = search.toUpperCase()
    return s.symbol.toUpperCase().includes(q) || s.name.toUpperCase().includes(q)
  })

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE))
  const pageItems  = filtered.slice(page * PAGE, (page + 1) * PAGE)

  const { data: yfNames } = useQuery({
    queryKey: ['stockNames', pageItems.map(s => s.symbol).join(',')],
    queryFn:  () => getStockNames(pageItems.map(s => s.symbol)),
    enabled:  !sector && pageItems.length > 0,
    staleTime: 1000 * 60 * 60,
  })

  const loading = loadingAll || (!!sector && loadingSector)

  function handleSectorChange(val: string) {
    setSector(val)
    setSearch('')
    setPage(0)
  }

  function handleSearch(val: string) {
    setSearch(val)
    setPage(0)
  }

  function getDisplayName(s: SymbolEntry): string {
    if (sector) return s.name
    return yfNames?.[s.symbol] ?? s.name
  }

  return (
    <div className={cn('flex flex-col rounded-md border border-border bg-bg-surface shadow-card', className)}>
      <div className="space-y-2.5 border-b border-border p-4">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-semibold uppercase tracking-widest text-ink-secondary">
            NSE Universe
            {maxSelected && (
              <span className="ml-1 text-ink-disabled">(max {maxSelected})</span>
            )}
          </h3>
        </div>

        {!hideSector && (
          <select
            value={sector}
            onChange={e => handleSectorChange(e.target.value)}
            className="w-full rounded border border-border bg-bg-elevated px-3 py-1.5 text-xs text-ink-primary focus:border-accent focus:outline-none"
          >
            <option value="">All Sectors</option>
            {(sectorNames ?? []).map(n => (
              <option key={n} value={n}>{n}</option>
            ))}
          </select>
        )}

        <div className="relative">
          <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted" />
          <input
            type="text"
            placeholder="Search symbol or name…"
            value={search}
            onChange={e => handleSearch(e.target.value)}
            className="w-full rounded border border-border bg-bg-elevated py-1.5 pl-8 pr-3 text-sm text-ink-primary placeholder:text-ink-disabled focus:border-accent focus:outline-none"
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="flex h-32 items-center justify-center">
            <Spinner size={20} />
          </div>
        ) : (
          pageItems.map(s => {
            const sel  = selected.includes(s.symbol)
            const full = !sel && selected.length >= maxSelected
            const name = getDisplayName(s)
            return (
              <button
                key={s.symbol}
                onClick={() => onToggle(s.symbol)}
                disabled={full}
                className={cn(
                  'flex w-full items-center justify-between px-4 py-2.5 text-left transition-colors',
                  'border-b border-border/40 last:border-0',
                  sel  ? 'bg-[rgba(56,139,253,.06)]'     : 'hover:bg-bg-elevated',
                  full ? 'cursor-not-allowed opacity-40' : '',
                )}
              >
                <div className="min-w-0 flex-1">
                  <p className={cn('font-mono text-sm font-semibold', sel ? 'text-accent' : 'text-ink-primary')}>
                    {s.symbol}
                  </p>
                  <p className="mt-0.5 max-w-[180px] truncate text-xs text-ink-muted">{name}</p>
                </div>
                {sel
                  ? <CheckCircle2 size={15} className="ml-2 shrink-0 text-accent" />
                  : <Plus        size={15} className="ml-2 shrink-0 text-ink-disabled" />
                }
              </button>
            )
          })
        )}
      </div>

      <div className="flex items-center justify-between border-t border-border px-4 py-2.5">
        <button
          onClick={() => setPage(p => Math.max(0, p - 1))}
          disabled={page === 0}
          className="text-xs text-ink-secondary hover:text-ink-primary disabled:text-ink-disabled"
        >
          ← Prev
        </button>
        <span className="text-xs text-ink-muted">{page + 1} / {totalPages}</span>
        <button
          onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
          disabled={page >= totalPages - 1}
          className="text-xs text-ink-secondary hover:text-ink-primary disabled:text-ink-disabled"
        >
          Next →
        </button>
      </div>
    </div>
  )
}
