import { cn } from '../../lib/utils'
import type { ScorecardPillar } from '../../lib/api'

const GRADE_COLOR: Record<string, string> = {
  A:   'text-gain',
  B:   'text-accent',
  C:   'text-warn',
  D:   'text-orange-400',
  F:   'text-loss',
  'N/A': 'text-ink-disabled',
}

const GRADE_BG: Record<string, string> = {
  A:   'bg-gain/8  border-gain/20',
  B:   'bg-accent/8 border-accent/20',
  C:   'bg-warn/8  border-warn/20',
  D:   'bg-orange-400/8 border-orange-400/20',
  F:   'bg-loss/8  border-loss/20',
  'N/A': 'bg-bg-elevated border-border',
}

interface Props {
  pillar:   ScorecardPillar
  active:   boolean
  onClick:  () => void
}

export default function PillarGradeCard({ pillar, active, onClick }: Props) {
  const grade     = pillar.grade
  const gradeCol  = GRADE_COLOR[grade] ?? 'text-ink-disabled'
  const gradeBg   = GRADE_BG[grade]   ?? 'bg-bg-elevated border-border'
  const scoreStr  = pillar.score != null ? pillar.score.toFixed(0) : '—'

  return (
    <button
      onClick={onClick}
      className={cn(
        'group flex w-full flex-col gap-2.5 rounded-lg border p-5 text-left transition-all duration-150',
        gradeBg,
        active
          ? 'ring-2 ring-offset-1 ring-offset-bg-base ' + (grade === 'N/A' ? 'ring-border' : 'ring-accent/40')
          : 'hover:border-opacity-40',
      )}
    >
      {/* Pillar label + score chip */}
      <div className="flex items-start justify-between gap-2">
        <p className="text-2xs font-semibold uppercase tracking-[0.1em] text-ink-secondary">
          {pillar.label}
        </p>
        {pillar.score != null && (
          <span className="rounded bg-bg-elevated/60 px-1.5 py-0.5 font-mono text-2xs text-ink-muted">
            {scoreStr}/100
          </span>
        )}
      </div>

      {/* Big grade letter */}
      <div className={cn('num font-mono text-5xl font-bold leading-none', gradeCol)}>
        {grade}
      </div>

      {/* Verdict */}
      <p className="line-clamp-2 text-xs leading-relaxed text-ink-secondary">
        {pillar.verdict}
      </p>

      {/* Coverage bar */}
      {pillar.models.length > 0 && (
        <div className="mt-auto space-y-1">
          <div className="h-1 w-full overflow-hidden rounded-full bg-bg-base/60">
            <div
              className={cn('h-full rounded-full transition-all', gradeCol.replace('text-', 'bg-'))}
              style={{ width: `${Math.round(pillar.coverage * 100)}%` }}
            />
          </div>
          <p className="text-2xs text-ink-disabled">
            {pillar.models.filter(m => m.status !== 'missing').length}/{pillar.models.length} models computed
          </p>
        </div>
      )}
    </button>
  )
}
