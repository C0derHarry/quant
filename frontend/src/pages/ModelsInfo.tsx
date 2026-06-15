import { useState, useMemo } from 'react'
import { createPortal } from 'react-dom'
import { X, Search, Lock, CheckCircle2 } from 'lucide-react'
import { cn } from '../lib/utils'
import catalog, { CATEGORIES, type Category, type ModelEntry } from '../data/modelsCatalog'
import Badge from '../components/ui/Badge'

// ─── helpers ──────────────────────────────────────────────────────

function categoryVariant(cat: Category) {
  const map: Record<string, 'accent' | 'gain' | 'violet' | 'warn' | 'neutral'> = {
    'Valuation':   'accent',
    'Quality':     'gain',
    'Profitability': 'gain',
    'Value':       'accent',
    'Growth':      'gain',
    'Risk':        'warn',
    'Momentum':    'violet',
    'Portfolio':   'violet',
    'Factor':      'violet',
    'Volatility':  'warn',
    'Technical':   'neutral',
    'ML / Regime': 'accent',
    'Strategy':    'neutral',
  }
  return map[cat] ?? 'neutral'
}

const DIFF_COLOR: Record<string, string> = {
  Low:    'text-gain',
  Medium: 'text-warn',
  High:   'text-loss',
}

// ─── detail modal ─────────────────────────────────────────────────

function ModelDetail({ model, onClose }: { model: ModelEntry; onClose: () => void }) {
  return createPortal(
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center p-4"
      style={{ backgroundColor: 'rgba(7,9,13,0.85)' }}
      onClick={onClose}
    >
      <div
        className="relative flex max-h-[90vh] w-full max-w-2xl flex-col overflow-hidden rounded-lg border border-border bg-bg-surface shadow-2xl"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-4 border-b border-border bg-bg-elevated px-6 py-4">
          <div className="min-w-0">
            <div className="mb-1.5 flex flex-wrap items-center gap-2">
              <Badge variant={categoryVariant(model.category)}>{model.category}</Badge>
              <Badge variant={model.tier === 'premium' ? 'violet' : 'gain'}>
                {model.tier}
              </Badge>
              {model.implemented
                ? <span className="inline-flex items-center gap-1 text-xs text-gain"><CheckCircle2 size={11} /> Implemented</span>
                : <span className="inline-flex items-center gap-1 text-xs text-ink-disabled"><Lock size={11} /> Coming soon</span>
              }
            </div>
            <h2 className="text-base font-semibold text-ink-primary">{model.name}</h2>
          </div>
          <button onClick={onClose} className="mt-0.5 shrink-0 text-ink-muted transition-colors hover:text-ink-primary">
            <X size={18} />
          </button>
        </div>

        {/* Scrollable body */}
        <div className="overflow-y-auto px-6 py-5 text-xs text-ink-secondary">
          {/* Description */}
          <p className="mb-4 leading-relaxed text-ink-secondary">{model.description}</p>

          {/* Formula */}
          <div className="mb-4">
            <p className="mb-1.5 font-semibold text-ink-primary">Formula</p>
            <pre className="overflow-x-auto rounded border border-border bg-bg-base px-4 py-3 font-mono text-xs text-ink-secondary whitespace-pre-wrap">
              {model.formula}
            </pre>
          </div>

          {/* Two-col: what it measures / interpretation */}
          <div className="mb-4 grid gap-4 sm:grid-cols-2">
            <div>
              <p className="mb-1.5 font-semibold text-ink-primary">What it measures</p>
              <p className="leading-relaxed">{model.measures}</p>
            </div>
            <div>
              <p className="mb-1.5 font-semibold text-ink-primary">Interpretation</p>
              <p className="leading-relaxed">{model.interpretation}</p>
            </div>
          </div>

          {/* Inputs */}
          <div className="mb-4">
            <p className="mb-1.5 font-semibold text-ink-primary">Required inputs</p>
            <ul className="space-y-1">
              {model.inputs.map(inp => (
                <li key={inp} className="flex items-start gap-2">
                  <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-accent" />
                  {inp}
                </li>
              ))}
            </ul>
          </div>

          {/* Data Required */}
          <div className="mb-4">
            <p className="mb-1.5 font-semibold text-ink-primary">Data required</p>
            <ul className="space-y-1">
              {model.dataRequired.map(d => (
                <li key={d} className="flex items-start gap-2">
                  <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-ink-disabled" />
                  {d}
                </li>
              ))}
            </ul>
          </div>

          {/* Pros / Cons */}
          <div className="mb-4 grid gap-4 sm:grid-cols-2">
            <div>
              <p className="mb-1.5 font-semibold text-gain">Advantages</p>
              <ul className="space-y-1">
                {model.advantages.map(a => (
                  <li key={a} className="flex items-start gap-2">
                    <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-gain" />
                    {a}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <p className="mb-1.5 font-semibold text-loss">Limitations</p>
              <ul className="space-y-1">
                {model.limitations.map(l => (
                  <li key={l} className="flex items-start gap-2">
                    <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-loss" />
                    {l}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* Use cases */}
          <div className="mb-2">
            <p className="mb-1.5 font-semibold text-ink-primary">Common use cases</p>
            <div className="flex flex-wrap gap-2">
              {model.useCases.map(u => (
                <span key={u} className="rounded-sm border border-border bg-bg-elevated px-2 py-0.5 text-ink-secondary">
                  {u}
                </span>
              ))}
            </div>
          </div>

          {/* Difficulty */}
          <div className="mt-3 flex items-center gap-2 border-t border-border pt-3">
            <span className="text-ink-disabled">Implementation difficulty:</span>
            <span className={cn('font-semibold', DIFF_COLOR[model.difficulty])}>{model.difficulty}</span>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  )
}

// ─── main page ────────────────────────────────────────────────────

export default function ModelsInfo() {
  const [activeCategory, setActiveCategory] = useState<Category | null>(null)
  const [search,   setSearch]               = useState('')
  const [selected, setSelected]             = useState<ModelEntry | null>(null)
  const [showImplemented, setShowImplemented] = useState<'all' | 'implemented' | 'coming'> ('all')

  const filtered = useMemo(() => {
    const q = search.toLowerCase()
    return catalog.filter(m => {
      if (activeCategory && m.category !== activeCategory) return false
      if (showImplemented === 'implemented' && !m.implemented) return false
      if (showImplemented === 'coming' && m.implemented)       return false
      if (q && !m.name.toLowerCase().includes(q) &&
               !m.description.toLowerCase().includes(q) &&
               !m.category.toLowerCase().includes(q)) return false
      return true
    })
  }, [activeCategory, search, showImplemented])

  const counts = useMemo(() => ({
    implemented: catalog.filter(m => m.implemented).length,
    coming:      catalog.filter(m => !m.implemented).length,
  }), [])

  return (
    <div className="flex h-[calc(100vh-56px)] overflow-hidden">
      {/* Left rail — filters */}
      <aside className="hidden w-52 shrink-0 flex-col gap-1 overflow-y-auto border-r border-border bg-bg-surface px-3 py-4 md:flex">
        <p className="mb-2 px-2 text-2xs font-semibold uppercase tracking-widest text-ink-disabled">Category</p>
        <button
          onClick={() => setActiveCategory(null)}
          className={cn(
            'rounded px-2 py-1.5 text-left text-xs transition-colors',
            activeCategory === null
              ? 'bg-accent/10 font-semibold text-accent'
              : 'text-ink-secondary hover:bg-bg-elevated',
          )}
        >
          All ({catalog.length})
        </button>
        {CATEGORIES.map(cat => {
          const n = catalog.filter(m => m.category === cat).length
          return (
            <button
              key={cat}
              onClick={() => setActiveCategory(cat === activeCategory ? null : cat)}
              className={cn(
                'rounded px-2 py-1.5 text-left text-xs transition-colors',
                activeCategory === cat
                  ? 'bg-accent/10 font-semibold text-accent'
                  : 'text-ink-secondary hover:bg-bg-elevated',
              )}
            >
              {cat} ({n})
            </button>
          )
        })}

        <div className="mt-4 border-t border-border pt-3">
          <p className="mb-2 px-2 text-2xs font-semibold uppercase tracking-widest text-ink-disabled">Status</p>
          {([
            ['all',         'All models'],
            ['implemented', `Live (${counts.implemented})`],
            ['coming',      `Coming soon (${counts.coming})`],
          ] as const).map(([val, label]) => (
            <button
              key={val}
              onClick={() => setShowImplemented(val)}
              className={cn(
                'w-full rounded px-2 py-1.5 text-left text-xs transition-colors',
                showImplemented === val
                  ? 'bg-accent/10 font-semibold text-accent'
                  : 'text-ink-secondary hover:bg-bg-elevated',
              )}
            >
              {label}
            </button>
          ))}
        </div>
      </aside>

      {/* Main */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Top bar */}
        <div className="border-b border-border bg-bg-surface px-4 py-3">
          <div className="flex flex-wrap items-center gap-3">
            <div className="relative flex-1 min-w-48">
              <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted" />
              <input
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Search models..."
                className="w-full rounded border border-border bg-bg-elevated pl-8 pr-3 py-1.5 text-xs text-ink-primary placeholder-ink-muted outline-none transition-colors focus:border-accent/50"
              />
            </div>
            <p className="text-xs text-ink-muted">
              {filtered.length} {filtered.length === 1 ? 'model' : 'models'}
            </p>
          </div>
        </div>

        {/* Grid */}
        <div className="flex-1 overflow-y-auto p-4">
          {filtered.length === 0 ? (
            <div className="flex h-48 items-center justify-center text-sm text-ink-muted">
              No models match your filters.
            </div>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {filtered.map(model => (
                <button
                  key={model.id}
                  onClick={() => setSelected(model)}
                  className="group flex flex-col rounded-lg border border-border bg-bg-surface p-4 text-left transition-all duration-150 hover:border-accent/40 hover:bg-bg-elevated"
                >
                  {/* badges */}
                  <div className="mb-2 flex flex-wrap items-center gap-1.5">
                    <Badge variant={categoryVariant(model.category)} className="text-2xs">
                      {model.category}
                    </Badge>
                    {model.tier === 'premium' && (
                      <Badge variant="violet" className="text-2xs">Premium</Badge>
                    )}
                    {model.implemented
                      ? <span className="inline-flex items-center gap-0.5 text-2xs text-gain"><CheckCircle2 size={10} /> Live</span>
                      : <span className="inline-flex items-center gap-0.5 text-2xs text-ink-disabled"><Lock size={10} /> Soon</span>
                    }
                  </div>

                  <p className="mb-1 text-sm font-semibold text-ink-primary group-hover:text-accent transition-colors">
                    {model.name}
                  </p>
                  <p className="line-clamp-2 text-xs text-ink-muted">
                    {model.description}
                  </p>

                  <div className="mt-3 flex items-center justify-between">
                    <span className={cn('text-2xs font-medium', DIFF_COLOR[model.difficulty])}>
                      {model.difficulty} complexity
                    </span>
                    <span className="text-2xs text-ink-disabled group-hover:text-accent transition-colors">
                      View details →
                    </span>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Detail modal */}
      {selected && <ModelDetail model={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}
