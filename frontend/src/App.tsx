import { Routes, Route } from 'react-router-dom'
import Layout from './components/layout/Layout'
import MarketOverview    from './pages/MarketOverview'
import SectorDetail      from './pages/SectorDetail'
import ValueScreen       from './pages/ValueScreen'
import StockFundamentals from './pages/StockFundamentals'
import VolatilityForecast from './pages/VolatilityForecast'
import PositionSizing    from './pages/PositionSizing'
import MLSignals         from './pages/MLSignals'
import NewsHub           from './pages/NewsHub'
import EarningsSurprise  from './pages/EarningsSurprise'

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/"            element={<MarketOverview />} />
        <Route path="/sector/:name" element={<SectorDetail />} />
        <Route path="/value"       element={<ValueScreen />} />
        <Route path="/fundamentals" element={<StockFundamentals />} />
        <Route path="/volatility"  element={<VolatilityForecast />} />
        <Route path="/portfolio"   element={<PositionSizing />} />
        <Route path="/signals"     element={<MLSignals />} />
        <Route path="/news"        element={<NewsHub />} />
        <Route path="/earnings"    element={<EarningsSurprise />} />
      </Routes>
    </Layout>
  )
}
