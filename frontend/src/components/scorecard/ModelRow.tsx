import { Lock, CheckCircle, AlertCircle, XCircle } from 'lucide-react'
import { Link } from 'react-router-dom'
import { cn } from '../../lib/utils'
import type { ScorecardModelResult } from '../../lib/api'

function SubScoreChip({ score }: { score: number }) {
  const color =
    score >= 80 ? 'bg-gain/10 text-gain border-gain/20' :
    score >= 65 ? 'bg-accent/10 text-accent border-accent/20' :
    score >= 50 ? 'bg-warn/10 text-warn border-warn/20' :
    score >= 35 ? 'bg-orange-400/10 text-orange-400 border-orange-400/20' :
                  'bg-loss/10 text-loss border-loss/20'
  return (
    <span className={cn('rounded border px-1.5 py-0.5 font-mono text-2xs font-semibold', color)}>
      {score.toFixed(0)}
    </span>
  )
}

function StatusIcon({ status }: { status: string }) {
  if (status === 'ok')      return <CheckCircle  size={13} className="shrink-0 text-gain" />
  if (status === 'partial') return <AlertCircle  size={13} className="shrink-0 text-warn" />
  return                           <XCircle      size={13} className="shrink-0 text-ink-disabled" />
}

interface Props {
  model: ScorecardModelResult
}

export default function ModelRow({ model }: Props) {
  const isPremiumLocked = model.status === 'missing' && model.tier === 'premium'

  return (
    <div className={cn(
      'flex items-start gap-3 rounded-md px-3 py-2.5 transition-colors',
      model.status === 'missing' ? 'opacity-60' : 'hover:bg-bg-elevated',
    )}>
      {/* Status icon */}
      <div className="mt-0.5">
        {isPremiumLocked
          ? <Lock size={13} className="shrink-0 text-ink-disabled" />
          : <StatusIcon status={model.status} />
        }
      </div>

      {/* Label + note */}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className={cn(
            'text-xs font-medium',
            model.status === 'missing' ? 'text-ink-muted' : 'text-ink-primary',
          )}>
            {model.label}
          </span>
          {model.tier === 'premium' && (
            <span className="rounded bg-violet/10 px-1.5 py-0.5 text-2xs font-semibold text-violet">
              Premium
            </span>
          )}
        </div>
        {model.note && (
          <p className="mt-0.5 text-2xs text-ink-disabled leading-relaxed">{model.note}</p>
        )}
        {isPremiumLocked && (
          <Link
            to="/pricing"
            className="mt-0.5 text-2xs text-accent hover:underline"
            onClick={e => e.stopPropagation()}
          >
            Upgrade to unlock →
          </Link>
        )}
      </div>

      {/* Display value + sub-score */}
      <div className="flex shrink-0 flex-col items-end gap-1">
        <span className={cn(
          'num font-mono text-xs',
          model.status === 'missing' ? 'text-ink-disabled' : 'text-ink-primary',
        )}>
          {model.display}
        </span>
        {model.sub_score != null && (
          <SubScoreChip score={model.sub_score} />
        )}
      </div>
    </div>
  )
}
