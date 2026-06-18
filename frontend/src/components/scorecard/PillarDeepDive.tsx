import { useState } from 'react'
import { X, ExternalLink } from 'lucide-react'
import { Link } from 'react-router-dom'
import { cn } from '../../lib/utils'
import type { ScorecardPillar, ScorecardModelResult } from '../../lib/api'
import ModelRow from './ModelRow'

const GRADE_COLOR: Record<string, string> = {
  A:     'text-gain',
  B:     'text-accent',
  C:     'text-warn',
  D:     'text-orange-400',
  F:     'text-loss',
  'N/A': 'text-ink-disabled',
}

interface ExtraTab {
  id:       string
  label:    string
  modelKey: string
  path:     string
  blurb:    string
}

const EXTRA_TABS: Record<string, ExtraTab[]> = {
  momentum: [
    {
      id: 'technical', label: 'Technical', modelKey: 'tech_composite', path: '/technical',
      blurb: 'Full RSI, MACD, Bollinger Bands, ADX, Stochastic, OBV and more — complete technical indicator breakdown for this stock.',
    },
    {
      id: 'ml', label: 'ML Signal', modelKey: 'ml_pup', path: '/signals',
      blurb: 'Calibrated Gradient Boosting: P(5-day up) from 36 engineered momentum and volatility features (premium).',
    },
  ],
  risk: [
    {
      id: 'volatility', label: 'Volatility', modelKey: 'ewma_var', path: '/volatility',
      blurb: 'EWMA, GARCH(p,q) and DCC-GARCH — dynamic conditional volatility and correlation models for this stock.',
    },
  ],
}

function ModelSummaryCard({ model }: { model: ScorecardModelResult }) {
  return (
    <div className="rounded-md border border-border bg-bg-elevated px-4 py-3">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-medium text-ink-primary">{model.label}</p>
          {model.note && (
            <p className="mt-0.5 text-2xs leading-relaxed text-ink-disabled">{model.note}</p>
          )}
        </div>
        <div className="shrink-0 text-right">
          <p className="num font-mono text-sm font-semibold text-ink-primary">{model.display}</p>
          {model.sub_score != null && (
            <p className="mt-0.5 text-2xs text-ink-muted">{model.sub_score.toFixed(0)}/100</p>
          )}
        </div>
      </div>
    </div>
  )
}

interface Props {
  pillar:  ScorecardPillar
  onClose: () => void
}

export default function PillarDeepDive({ pillar, onClose }: Props) {
  const gradeCol  = GRADE_COLOR[pillar.grade] ?? 'text-ink-disabled'
  const extraTabs = EXTRA_TABS[pillar.key] ?? []
  const hasTabs   = extraTabs.length > 0
  const [tab, setTab] = useState('Models')

  const freeModels    = pillar.models.filter(m => m.tier === 'free')
  const premiumModels = pillar.models.filter(m => m.tier === 'premium')

  return (
    <div className="rounded-lg border border-border bg-bg-surface shadow-card-lg">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 border-b border-border px-5 py-4">
        <div className="flex items-baseline gap-3">
          <span className={cn('num font-mono text-3xl font-bold', gradeCol)}>
            {pillar.grade}
          </span>
          <div>
            <p className="text-sm font-semibold text-ink-primary">{pillar.label}</p>
            <p className="text-xs text-ink-secondary">{pillar.verdict}</p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="mt-0.5 shrink-0 text-ink-disabled transition-colors hover:text-ink-primary"
        >
          <X size={16} />
        </button>
      </div>

      {/* Tab bar — Momentum and Risk pillars only */}
      {hasTabs && (
        <div className="flex overflow-x-auto border-b border-border px-4">
          {['Models', ...extraTabs.map(t => t.label)].map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={cn(
                'shrink-0 px-3 py-2.5 text-xs font-medium transition-colors',
                tab === t
                  ? '-mb-px border-b-2 border-accent text-accent'
                  : 'text-ink-secondary hover:text-ink-primary',
              )}
            >
              {t}
            </button>
          ))}
        </div>
      )}

      {/* Models tab */}
      {tab === 'Models' && (
        <div className="divide-y divide-border/40 py-1">
          {pillar.models.length === 0 && (
            <p className="px-5 py-6 text-center text-xs text-ink-muted">
              No model data available for this pillar yet.
            </p>
          )}
          {freeModels.map(m => <ModelRow key={m.key} model={m} />)}
          {premiumModels.length > 0 && (
            <>
              <div className="px-3 pt-3 pb-1">
                <p className="text-2xs font-semibold uppercase tracking-[0.1em] text-ink-disabled">
                  Premium models
                </p>
              </div>
              {premiumModels.map(m => <ModelRow key={m.key} model={m} />)}
            </>
          )}
        </div>
      )}

      {/* Extra tabs (Technical / ML Signal / Volatility) */}
      {extraTabs.map(et => {
        if (tab !== et.label) return null
        const m = pillar.models.find(x => x.key === et.modelKey)
        return (
          <div key={et.id} className="space-y-3 px-5 py-4">
            {m && <ModelSummaryCard model={m} />}
            <p className="text-xs leading-relaxed text-ink-secondary">{et.blurb}</p>
            <Link
              to={et.path}
              className="inline-flex items-center gap-1.5 text-xs font-medium text-accent hover:underline"
            >
              Go to full analysis <ExternalLink size={11} />
            </Link>
          </div>
        )
      })}

      {/* Coverage footer — Models tab only */}
      {tab === 'Models' && pillar.models.length > 0 && (
        <div className="border-t border-border/40 px-5 py-2.5">
          <div className="flex items-center gap-2">
            <div className="h-1 flex-1 overflow-hidden rounded-full bg-bg-elevated">
              <div
                className={cn('h-full rounded-full', gradeCol.replace('text-', 'bg-'))}
                style={{ width: `${Math.round(pillar.coverage * 100)}%` }}
              />
            </div>
            <span className="shrink-0 text-2xs text-ink-disabled">
              {Math.round(pillar.coverage * 100)}% data coverage
            </span>
          </div>
        </div>
      )}
    </div>
  )
}
