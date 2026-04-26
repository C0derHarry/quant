import { useState, useMemo, ReactNode } from 'react'
import { ChevronUp, ChevronDown, ChevronsUpDown } from 'lucide-react'
import { cn } from '../../lib/utils'

export interface Column<T> {
  key:    string
  header: string
  cell:   (row: T) => ReactNode
  sort?:  (row: T) => number | string
  align?: 'left' | 'right' | 'center'
  width?: string
}

interface DataTableProps<T> {
  columns:      Column<T>[]
  data:         T[]
  keyFn:        (row: T) => string
  className?:   string
  compact?:     boolean
  onRowClick?:  (row: T) => void
}

export default function DataTable<T>({
  columns, data, keyFn, className, compact = false, onRowClick,
}: DataTableProps<T>) {
  const [sortKey, setSortKey]   = useState<string | null>(null)
  const [sortDir, setSortDir]   = useState<'asc' | 'desc'>('desc')

  const sorted = useMemo(() => {
    if (!sortKey) return data
    const col = columns.find(c => c.key === sortKey)
    if (!col?.sort) return data
    return [...data].sort((a, b) => {
      const va = col.sort!(a), vb = col.sort!(b)
      const cmp = typeof va === 'string'
        ? va.localeCompare(String(vb))
        : (va as number) - (vb as number)
      return sortDir === 'asc' ? cmp : -cmp
    })
  }, [data, sortKey, sortDir, columns])

  function toggleSort(key: string) {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('desc') }
  }

  const py = compact ? 'py-1.5' : 'py-2.5'

  return (
    <div className={cn('w-full overflow-x-auto rounded-md border border-border', className)}>
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-border bg-bg-elevated">
            {columns.map(col => (
              <th
                key={col.key}
                onClick={() => col.sort && toggleSort(col.key)}
                style={col.width ? { width: col.width } : undefined}
                className={cn(
                  'select-none px-4 py-2.5 text-2xs font-semibold uppercase tracking-[0.08em] text-ink-secondary',
                  col.align === 'right'  && 'text-right',
                  col.align === 'center' && 'text-center',
                  col.sort && 'cursor-pointer hover:text-ink-primary',
                )}
              >
                <span className="inline-flex items-center gap-1">
                  {col.header}
                  {col.sort && (
                    sortKey === col.key
                      ? sortDir === 'asc'
                        ? <ChevronUp size={11} className="text-accent" />
                        : <ChevronDown size={11} className="text-accent" />
                      : <ChevronsUpDown size={11} className="opacity-30" />
                  )}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map(row => (
            <tr
              key={keyFn(row)}
              onClick={() => onRowClick?.(row)}
              className={cn(
                'tbl-row border-b border-border/50 last:border-0 transition-colors',
                onRowClick && 'cursor-pointer hover:bg-bg-elevated',
              )}
            >
              {columns.map(col => (
                <td
                  key={col.key}
                  className={cn(
                    `px-4 ${py} text-ink-primary`,
                    col.align === 'right'  && 'text-right',
                    col.align === 'center' && 'text-center',
                  )}
                >
                  {col.cell(row)}
                </td>
              ))}
            </tr>
          ))}
          {sorted.length === 0 && (
            <tr>
              <td colSpan={columns.length} className="py-12 text-center text-sm text-ink-muted">
                No data
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
