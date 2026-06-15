import type { ReactNode } from 'react'
import { Outlet, Link } from 'react-router-dom'
import { Lock, Sparkles, ArrowRight } from 'lucide-react'
import { useEntitlements } from '../hooks/useEntitlements'
import { PageLoader } from './ui/Spinner'

const FEATURE_LABELS: Record<string, string> = {
  ai_overview:          'AI Overview',
  backtesting:          'Strategy Backtesting',
  portfolio_optimize:   'Portfolio Optimisation',
  volatility:           'Volatility & GARCH Analysis',
  ml_signals:           'ML Signals',
  technical_analysis:   'Full Technical Analysis',
  earnings:             'Earnings Surprise',
  news_impact:          'News Impact Analysis',
  unlimited_portfolios: 'Unlimited Portfolios',
  alerts:               'Price Alerts',
  export:               'Data Export',
  newsletter:           'Daily Newsletter',
  historical_charts:    'Historical Valuation Charts',
  sector_comparison:    'Sector Comparison',
  advanced_screeners:   'Advanced Screeners',
}

const FEATURE_BENEFITS: Record<string, string[]> = {
  ai_overview:        ['AI-generated stock analysis', 'Multi-universe coverage', 'Conviction scoring'],
  backtesting:        ['Strategy backtesting with real costs', 'Walk-forward validation', 'Export to Python'],
  portfolio_optimize: ['Black-Litterman + MVO', 'HMM regime-conditioned weights', 'DCA schedule'],
  volatility:         ['GARCH volatility forecasts', 'DCC-GARCH correlation', 'VaR & CVaR'],
  ml_signals:         ['Gradient boosting probability', 'Calibrated P(up) signal', 'Feature importance'],
  technical_analysis: ['14+ technical indicators', 'Composite verdict', 'Entry/stop/target levels'],
  earnings:           ['EPS surprise history', 'Beat rate analysis', 'Consensus vs actuals'],
  news_impact:        ['Sentiment-scored news', 'Portfolio news digest', 'Impact classification'],
}

interface PremiumGateProps {
  featureKey: string
  children?: ReactNode
}

export default function PremiumGate({ featureKey, children }: PremiumGateProps) {
  const { has, isLoading } = useEntitlements()

  if (isLoading) return <PageLoader />

  if (has(featureKey)) {
    return children ? <>{children}</> : <Outlet />
  }

  const label    = FEATURE_LABELS[featureKey] ?? 'This Feature'
  const benefits = FEATURE_BENEFITS[featureKey] ?? []

  return (
    <div className="flex h-[calc(100vh-56px)] items-center justify-center p-8">
      <div className="w-full max-w-md rounded-lg border border-border bg-bg-surface p-8 text-center shadow-lg">
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full border border-border bg-bg-elevated">
          <Lock size={20} className="text-ink-muted" />
        </div>

        <div className="mb-1 flex items-center justify-center gap-1.5">
          <Sparkles size={13} className="text-violet" />
          <span className="text-xs font-semibold uppercase tracking-widest text-violet">Premium</span>
        </div>
        <h2 className="mb-2 text-lg font-semibold text-ink-primary">{label}</h2>
        <p className="mb-5 text-sm text-ink-secondary">
          Upgrade to Premium to unlock this feature and the full QuantHub analytical suite.
        </p>

        {benefits.length > 0 && (
          <ul className="mb-6 space-y-1.5 text-left">
            {benefits.map(b => (
              <li key={b} className="flex items-center gap-2 text-xs text-ink-secondary">
                <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
                {b}
              </li>
            ))}
          </ul>
        )}

        <Link
          to="/pricing"
          className="flex items-center justify-center gap-2 rounded bg-accent px-5 py-2.5 text-sm font-semibold text-white transition-opacity hover:opacity-90"
        >
          View Pricing
          <ArrowRight size={14} />
        </Link>

        <p className="mt-3 text-xs text-ink-disabled">
          Payment infrastructure coming soon.
        </p>
      </div>
    </div>
  )
}
