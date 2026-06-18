import { Component, type ReactNode } from 'react'
import { Routes, Route } from 'react-router-dom'
import { AuthProvider } from './contexts/AuthContext'
import ProtectedRoute    from './components/ProtectedRoute'
import DisclaimerGate    from './components/DisclaimerGate'
import PremiumGate       from './components/PremiumGate'
import Layout            from './components/layout/Layout'

class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null }
  static getDerivedStateFromError(error: Error) { return { error } }
  render() {
    if (this.state.error) {
      return (
        <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-bg-base p-8 text-center">
          <p className="text-sm font-semibold text-loss">Render Error</p>
          <p className="max-w-xl text-xs text-ink-muted">{(this.state.error as Error).message}</p>
          <button
            onClick={() => this.setState({ error: null })}
            className="mt-2 rounded border border-border px-3 py-1.5 text-xs text-ink-secondary hover:text-ink-primary"
          >
            Retry
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
import Login             from './pages/Login'
import Register          from './pages/Register'
import MarketOverview    from './pages/MarketOverview'
import SectorDetail      from './pages/SectorDetail'
import ValueScreen       from './pages/ValueScreen'
import StockFundamentals from './pages/StockFundamentals'
import VolatilityForecast from './pages/VolatilityForecast'
import PositionSizing    from './pages/PositionSizing'
import MLSignals         from './pages/MLSignals'
import NewsHub           from './pages/NewsHub'
import EarningsSurprise  from './pages/EarningsSurprise'
import PortfolioTracker  from './pages/PortfolioTracker'
import TechnicalAnalysis from './pages/TechnicalAnalysis'
import AIOverview        from './pages/AIOverview'
import Backtesting       from './pages/Backtesting'
import ModelsInfo        from './pages/ModelsInfo'
import Pricing           from './pages/Pricing'
import StockAnalysis     from './pages/StockAnalysis'

export default function App() {
  return (
    <ErrorBoundary>
    <AuthProvider>
      <Routes>
        {/* Public routes */}
        <Route path="/login"    element={<Login />} />
        <Route path="/register" element={<Register />} />

        {/* Protected routes — all wrapped in DisclaimerGate then Layout */}
        <Route element={<ProtectedRoute />}>
          <Route element={<DisclaimerGate />}>
            <Route element={<Layout />}>
              {/* Free routes */}
              <Route path="/"             element={<MarketOverview />} />
              <Route path="/sector/:name" element={<SectorDetail />} />
              <Route path="/value"        element={<ValueScreen />} />
              <Route path="/fundamentals" element={<StockFundamentals />} />
              <Route path="/stock"        element={<StockAnalysis />} />
              <Route path="/tracker"      element={<PortfolioTracker />} />
              <Route path="/models"       element={<ModelsInfo />} />
              <Route path="/pricing"      element={<Pricing />} />

              {/* Premium routes */}
              <Route element={<PremiumGate featureKey="volatility" />}>
                <Route path="/volatility" element={<VolatilityForecast />} />
              </Route>
              <Route element={<PremiumGate featureKey="portfolio_optimize" />}>
                <Route path="/portfolio" element={<PositionSizing />} />
              </Route>
              <Route element={<PremiumGate featureKey="ml_signals" />}>
                <Route path="/signals" element={<MLSignals />} />
              </Route>
              <Route path="/news" element={<NewsHub />} />
              <Route element={<PremiumGate featureKey="earnings" />}>
                <Route path="/earnings" element={<EarningsSurprise />} />
              </Route>
              <Route element={<PremiumGate featureKey="technical_analysis" />}>
                <Route path="/technical" element={<TechnicalAnalysis />} />
              </Route>
              <Route element={<PremiumGate featureKey="ai_overview" />}>
                <Route path="/ai-overview" element={<AIOverview />} />
              </Route>
              <Route element={<PremiumGate featureKey="backtesting" />}>
                <Route path="/backtesting" element={<Backtesting />} />
              </Route>
            </Route>
          </Route>
        </Route>
      </Routes>
    </AuthProvider>
    </ErrorBoundary>
  )
}
