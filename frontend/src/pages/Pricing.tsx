import { Check, X, Clock, Lock } from 'lucide-react'

const FREE_FEATURES = [
  'Market overview & sector dashboard',
  'Live index & sector quotes',
  'Stock search',
  'Value Screen (Magic Formula, QARP)',
  'Basic fundamentals (KPIs, OHLCV)',
  'Models & education library',
  '1 saved portfolio',
]

const PREMIUM_FEATURES = [
  'Everything in Free',
  'AI stock analysis (stream)',
  'Strategy backtesting (with cost model)',
  'Portfolio optimisation (Black-Litterman, MVO)',
  'Volatility forecasting (GARCH, DCC-GARCH)',
  'ML probability signals (calibrated)',
  'Full technical analysis suite',
  'HMM market regime detection',
  'Earnings surprise analysis',
  'News impact & portfolio news digest',
  'Unlimited saved portfolios',
  'Historical valuation & intrinsic value charts',
  'Sector comparison & advanced screeners',
  'Daily morning newsletter (5 lines)',
  'Data export (CSV / Python script)',
  'VaR, CVaR & stop-loss table',
]

const TRIAL_FEATURES = [
  'Portfolio analysis (once)',
  'Portfolio optimisation (once)',
  'Allocation suggestion (once)',
  'AI portfolio review (once)',
]

interface FeatureRowProps { label: string; available: boolean | 'trial' | 'soon' }

function FeatureRow({ label, available }: FeatureRowProps) {
  return (
    <li className="flex items-start gap-2.5 py-1.5 text-sm">
      <span className="mt-0.5 shrink-0">
        {available === true && <Check size={14} className="text-gain" />}
        {available === false && <X size={14} className="text-ink-disabled" />}
        {available === 'trial' && <Clock size={14} className="text-warn" />}
        {available === 'soon' && <Lock size={14} className="text-ink-disabled" />}
      </span>
      <span className={available ? 'text-ink-secondary' : 'text-ink-disabled'}>{label}</span>
    </li>
  )
}

export default function Pricing() {
  return (
    <div className="h-[calc(100vh-56px)] overflow-y-auto px-6 py-8">
      <div className="mx-auto max-w-5xl">
        {/* Header */}
        <div className="mb-10 text-center">
          <p className="mb-1 text-xs font-semibold uppercase tracking-widest text-accent">Pricing</p>
          <h1 className="mb-3 text-2xl font-bold text-ink-primary">Simple, transparent pricing</h1>
          <p className="mx-auto max-w-lg text-sm text-ink-secondary">
            Start for free. Upgrade when you want access to the full analytical suite — advanced
            models, backtesting, portfolio optimisation, and the daily newsletter.
          </p>
        </div>

        {/* Tier Cards */}
        <div className="mb-10 grid gap-6 md:grid-cols-2">
          {/* Free */}
          <div className="rounded-lg border border-border bg-bg-surface p-6">
            <div className="mb-4 border-b border-border pb-4">
              <p className="mb-1 text-xs font-semibold uppercase tracking-widest text-ink-muted">Free</p>
              <div className="flex items-end gap-1">
                <span className="text-3xl font-bold text-ink-primary">₹0</span>
                <span className="mb-1 text-sm text-ink-muted">/ month</span>
              </div>
              <p className="mt-1.5 text-xs text-ink-secondary">
                No credit card required. Access core features immediately.
              </p>
            </div>
            <ul className="mb-5 space-y-0.5">
              {FREE_FEATURES.map(f => <FeatureRow key={f} label={f} available={true} />)}
              {TRIAL_FEATURES.map(f => <FeatureRow key={f} label={f} available="trial" />)}
              <FeatureRow label="Advanced models, backtesting, AI overview" available={false} />
            </ul>
            <div className="rounded border border-border bg-bg-elevated px-4 py-2.5 text-center text-sm font-medium text-ink-secondary">
              Current Plan
            </div>
          </div>

          {/* Premium */}
          <div className="rounded-lg border border-accent/40 bg-bg-surface p-6 shadow-[0_0_0_1px_rgba(56,139,253,0.15)]">
            <div className="mb-4 border-b border-border pb-4">
              <div className="mb-1 flex items-center gap-2">
                <p className="text-xs font-semibold uppercase tracking-widest text-accent">Premium</p>
                <span className="rounded-sm bg-accent/15 px-1.5 py-0.5 text-2xs font-semibold uppercase text-accent">
                  Coming Soon
                </span>
              </div>
              <div className="flex items-end gap-1">
                <span className="text-3xl font-bold text-ink-primary">₹999</span>
                <span className="mb-1 text-sm text-ink-muted">/ month</span>
              </div>
              <p className="mt-1.5 text-xs text-ink-secondary">
                Full access to all models, strategies, and features.
              </p>
            </div>
            <ul className="mb-5 space-y-0.5">
              {PREMIUM_FEATURES.map(f => <FeatureRow key={f} label={f} available={true} />)}
            </ul>
            <button
              disabled
              className="w-full cursor-not-allowed rounded bg-accent/40 py-2.5 text-sm font-semibold text-white/60"
            >
              Upgrade — Coming Soon
            </button>
          </div>
        </div>

        {/* Trial explanation */}
        <div className="mb-8 rounded-lg border border-border bg-bg-elevated p-5">
          <div className="flex items-center gap-2 mb-3">
            <Clock size={14} className="text-warn" />
            <p className="text-sm font-semibold text-ink-primary">One-time free trial features</p>
          </div>
          <p className="mb-3 text-xs text-ink-secondary">
            Free users get one complimentary run of the following premium features before needing to upgrade:
          </p>
          <div className="grid grid-cols-2 gap-x-6 gap-y-1">
            {TRIAL_FEATURES.map(f => (
              <div key={f} className="flex items-center gap-2 text-xs text-ink-secondary">
                <Clock size={11} className="shrink-0 text-warn" />
                {f}
              </div>
            ))}
          </div>
        </div>

        {/* Feature matrix */}
        <div className="rounded-lg border border-border bg-bg-surface overflow-hidden">
          <div className="border-b border-border bg-bg-elevated px-5 py-3">
            <p className="text-sm font-semibold text-ink-primary">Full feature comparison</p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border">
                  <th className="px-5 py-3 text-left font-semibold text-ink-secondary">Feature</th>
                  <th className="px-4 py-3 text-center font-semibold text-ink-secondary">Free</th>
                  <th className="px-4 py-3 text-center font-semibold text-accent">Premium</th>
                </tr>
              </thead>
              <tbody>
                {[
                  ['Market overview & sectors',        true,    true],
                  ['Live quotes (NSE/BSE)',            true,    true],
                  ['Stock search',                     true,    true],
                  ['Value screens (Magic Formula, QARP)', true, true],
                  ['Basic fundamentals',               true,    true],
                  ['Models education library',         true,    true],
                  ['Saved portfolios',                 '1',     'Unlimited'],
                  ['Portfolio optimisation',           'trial', true],
                  ['Allocation & rebalancing',         'trial', true],
                  ['AI stock analysis',                'trial', true],
                  ['Strategy backtesting',             false,   true],
                  ['Volatility / GARCH / DCC',        false,   true],
                  ['ML probability signals',           false,   true],
                  ['Full technical analysis',          false,   true],
                  ['HMM regime detection',             false,   true],
                  ['Earnings surprise',                false,   true],
                  ['News impact analysis',             false,   true],
                  ['Historical valuation charts',      false,   true],
                  ['Advanced screeners',               false,   true],
                  ['Alerts & notifications',           false,   true],
                  ['Data export (CSV/Python)',         false,   true],
                  ['Daily newsletter',                 false,   true],
                ].map(([label, free, premium]) => (
                  <tr key={String(label)} className="border-b border-border/50 last:border-0 hover:bg-bg-elevated/40 transition-colors">
                    <td className="px-5 py-2.5 text-ink-secondary">{String(label)}</td>
                    <td className="px-4 py-2.5 text-center">
                      {free === true  && <Check size={13} className="mx-auto text-gain" />}
                      {free === false && <X     size={13} className="mx-auto text-ink-disabled" />}
                      {free === 'trial' && <span className="text-warn">Trial</span>}
                      {typeof free === 'string' && free !== 'trial' && (
                        <span className="text-ink-secondary">{free}</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-center">
                      {premium === true && <Check size={13} className="mx-auto text-gain" />}
                      {typeof premium === 'string' && (
                        <span className="text-ink-secondary">{premium}</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Disclaimer */}
        <p className="mt-8 text-center text-xs text-ink-disabled">
          All prices in INR. QuantHub is an educational platform. Features are analytical tools —
          not investment advice. See our{' '}
          <span className="text-ink-secondary">Terms of Service</span> for full details.
        </p>
      </div>
    </div>
  )
}
