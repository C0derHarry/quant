import { CheckCircle, Loader2, Circle } from 'lucide-react'
import { cn } from '../../lib/utils'

export interface StageState {
  label:  string
  status: 'waiting' | 'running' | 'done'
  detail?: string
}

interface Props {
  stages: StageState[]
  error?: string | null
}

export default function RunProgress({ stages, error }: Props) {
  return (
    <div className="flex flex-col items-center gap-8 py-12">
      <div className="space-y-4 w-full max-w-sm">
        {stages.map((stage, i) => (
          <div key={i} className="flex items-center gap-4">
            <div className="w-6 shrink-0 flex items-center justify-center">
              {stage.status === 'done' && (
                <CheckCircle size={20} className="text-gain" />
              )}
              {stage.status === 'running' && (
                <Loader2 size={20} className="text-accent animate-spin" />
              )}
              {stage.status === 'waiting' && (
                <Circle size={20} className="text-ink-disabled" />
              )}
            </div>
            <div className="flex-1 min-w-0">
              <p className={cn(
                'text-sm font-medium',
                stage.status === 'done'    ? 'text-gain'     :
                stage.status === 'running' ? 'text-ink-primary' :
                'text-ink-disabled',
              )}>
                {stage.label}
              </p>
              {stage.detail && stage.status === 'running' && (
                <p className="text-xs text-ink-muted mt-0.5">{stage.detail}</p>
              )}
            </div>
          </div>
        ))}
      </div>

      {error && (
        <div className="max-w-sm w-full rounded border border-loss/30 bg-loss/10 px-4 py-3">
          <p className="text-xs font-semibold text-loss">Backtest failed</p>
          <p className="text-xs text-ink-muted mt-1">{error}</p>
        </div>
      )}

      {!error && stages.every(s => s.status !== 'done') && stages.some(s => s.status === 'running') && (
        <p className="text-xs text-ink-muted">This may take 10–30 seconds for large universes…</p>
      )}
    </div>
  )
}
