import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, BarChart2, Info } from 'lucide-react'
import { getScorecard, type ScorecardPillar } from '../lib/api'
import StockSearchInput from '../components/ui/StockSearchInput'
import { PageLoader } from '../components/ui/Spinner'
import PillarGradeCard from '../components/scorecard/PillarGradeCard'
import PillarDeepDive  from '../components/scorecard/PillarDeepDive'
import { cn } from '../lib/utils'

const OVERALL_COLOR: Record<string, string> = {
  A:     'text-gain',
  B:     'text-accent',
  C:     'text-warn',
  D:     'text-orange-400',
  F:     'text-loss',
  'N/A': 'text-ink-disabled',
}

export default function StockAnalysis() {
  const [ticker, setTicker]             = useState('')
  const [activePillar, setActivePillar] = useState<string | null>(null)

  const { data, isLoading, error } = useQuery({
    queryKey:  ['scorecard', ticker],
    queryFn:   () => getScorecard(ticker),
    enabled:   !!ticker,
    staleTime: 5 * 60 * 1000,
  })

  function handleSelect(sym: string) {
    setTicker(sym)
    setActivePillar(null)
  }

  function handleClear() {
    setTicker('')
    setActivePillar(null)
  }

  function togglePillar(key: string) {
    setActivePillar(prev => prev === key ? null : key)
  }

  const activePillarData: ScorecardPillar | undefined =
    data?.pillars.find(p => p.key === activePillar)

  return (
    <div className="h-[calc(100vh-56px)] overflow-y-auto">
      <div className="mx-auto max-w-5xl px-6 py-6">

        {/* Page header */}
        <div className="mb-6 flex items-start justify-between gap-4">
          <div>
            <h1 className="text-base font-semibold text-ink-primary">Stock Scorecard</h1>
            <p className="mt-0.5 text-xs text-ink-secondary">
              Search any NSE stock for an at-a-glance grade across Value, Quality, Momentum and Risk.
            </p>
          </div>
          <StockSearchInput
            selected={ticker}
            onSelect={handleSelect}
            onClear={handleClear}
            placeholder="Search stock (e.g. TCS, RELIANCE…)"
          />
        </div>

        {/* Empty state */}
        {!ticker && (
          <div className="flex flex-col items-center justify-center gap-3 py-24 text-center">
            <BarChart2 size={32} className="text-ink-disabled" />
            <p className="text-sm font-medium text-ink-secondary">Search a stock to see its scorecard</p>
            <p className="max-w-xs text-xs text-ink-disabled">
              Each pillar aggregates multiple quant models into a single A–F grade with a plain-English explanation.
            </p>
          </div>
        )}

        {/* Loading */}
        {ticker && isLoading && <PageLoader />}

        {/* Error */}
        {ticker && error && !isLoading && (
          <div className="flex items-center gap-2 rounded-md border border-loss/20 bg-loss/5 px-4 py-3 text-xs text-loss">
            <AlertTriangle size={14} className="shrink-0" />
            {(error as Error).message}
          </div>
        )}

        {/* Scorecard */}
        {data && !isLoading && (
          <div className="space-y-6">
            {/* Ticker header + overall grade */}
            <div className="flex items-center gap-4">
              <div>
                <div className="flex items-baseline gap-2">
                  <h2 className="font-mono text-xl font-bold text-ink-primary">{data.ticker}</h2>
                  {data.is_financial && (
                    <span className="rounded bg-bg-elevated px-1.5 py-0.5 text-2xs text-ink-muted">Financial</span>
                  )}
                </div>
                <p className="text-2xs text-ink-disabled">as of {data.as_of}</p>
              </div>
              <div className="ml-auto flex items-baseline gap-1.5">
                <span className="text-xs text-ink-secondary">Overall</span>
                <span className={cn('num font-mono text-3xl font-bold', OVERALL_COLOR[data.overall.grade])}>
                  {data.overall.grade}
                </span>
                {data.overall.score != null && (
                  <span className="text-xs text-ink-muted">({data.overall.score.toFixed(0)}/100)</span>
                )}
              </div>
            </div>

            {/* Data warning */}
            {data.data_warning && (
              <div className="flex items-center gap-2 rounded-md border border-warn/20 bg-warn/5 px-4 py-2.5 text-xs text-warn">
                <AlertTriangle size={13} className="shrink-0" />
                {data.data_warning}
              </div>
            )}

            {/* Pillar cards grid */}
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
              {data.pillars.map(pillar => (
                <PillarGradeCard
                  key={pillar.key}
                  pillar={pillar}
                  active={activePillar === pillar.key}
                  onClick={() => togglePillar(pillar.key)}
                />
              ))}
            </div>

            {/* Deep-dive panel */}
            {activePillarData && (
              <PillarDeepDive
                key={activePillar}
                pillar={activePillarData}
                onClose={() => setActivePillar(null)}
              />
            )}

            {/* Deep-dive hint */}
            {!activePillarData && (
              <div className="flex items-start gap-2 rounded-md border border-border bg-bg-surface px-4 py-3 text-xs text-ink-muted">
                <Info size={13} className="mt-0.5 shrink-0" />
                <span>
                  Click any pillar card to see the model breakdown. The Momentum pillar includes Technical and ML Signal tabs; Risk includes a Volatility tab.
                </span>
              </div>
            )}

            {/* Compliance disclaimer note */}
            <p className="text-2xs text-ink-disabled">
              Scores are mathematical model estimates for educational purposes only — not investment advice.
              Past performance does not indicate future results. Consult a SEBI-registered adviser before investing.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
