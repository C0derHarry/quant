const BASE = '/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  return res.json()
}

// ── Market ────────────────────────────────────────────────────────
export const getIndices  = () => request<Record<string, TickerSnapshot>>('/market/indices')
export const getSectors  = () => request<Record<string, TickerSnapshot>>('/market/sectors')
export const getSectorStocks = (name: string) =>
  request<SectorStock[]>(`/market/sector/${encodeURIComponent(name)}/stocks`)
export const getAllSymbols = (exchange = 'NSE') =>
  request<SymbolEntry[]>(`/market/symbols?exchange=${exchange}`)
export const getSectorNames = () => request<string[]>('/market/sector-names')
export const getSectorSymbols = (name: string) =>
  request<SymbolEntry[]>(`/market/sector/${encodeURIComponent(name)}/symbols`)
export const getStockNames = (symbols: string[]) =>
  request<Record<string, string>>('/market/stock-names',
    { method: 'POST', body: JSON.stringify({ symbols }) })
export const getIndexList  = () => request<string[]>('/market/index-list')
export const getIndexStocks = (name: string) =>
  request<SectorStock[]>(`/market/index/${encodeURIComponent(name)}/stocks`)

// ── Screener ──────────────────────────────────────────────────────
export const runMagicFormula = (tickers: string[]) =>
  request<{ results: Record<string, unknown>[] }>('/screener/magic-formula',
    { method: 'POST', body: JSON.stringify({ tickers }) })

export const runQARP = (tickers: string[]) =>
  request<{ results: Record<string, unknown>[] }>('/screener/qarp',
    { method: 'POST', body: JSON.stringify({ tickers }) })

// ── Fundamentals ──────────────────────────────────────────────────
export const getOHLCV = (body: FundamentalsReq) =>
  request<Record<string, OHLCVRow[]>>('/fundamentals/ohlcv', { method: 'POST', body: JSON.stringify(body) })

export const getKPIs = (body: FundamentalsReq) =>
  request<Record<string, KPISet>>('/fundamentals/kpis', { method: 'POST', body: JSON.stringify(body) })

export const getRollingKPIs = (body: FundamentalsReq) =>
  request<Record<string, RollingRow[]>>('/fundamentals/rolling-kpis', { method: 'POST', body: JSON.stringify(body) })

// ── Volatility ────────────────────────────────────────────────────
export const analyzeVol = (body: VolRequest) =>
  request<VolAnalysis>('/volatility/analyze', { method: 'POST', body: JSON.stringify(body) })

export const forecastVol = (body: ForecastRequest) =>
  request<VolForecast>('/volatility/forecast', { method: 'POST', body: JSON.stringify(body) })

// ── Portfolio ─────────────────────────────────────────────────────
export const optimizePortfolio = (body: OptimizeRequest) =>
  request<OptimizeResult>('/portfolio/optimize', { method: 'POST', body: JSON.stringify(body) })

// ── Signals ───────────────────────────────────────────────────────
export const analyzeSignals = (body: SignalRequest) =>
  request<SignalResult>('/signals/analyze', { method: 'POST', body: JSON.stringify(body) })

// ── Market extras ────────────────────────────────────────────────
export type AssetCompareResult = Record<string, { date: string; value: number }[]>
export const getAssetCompare = (period: string) =>
  request<AssetCompareResult>(`/market/asset-compare?period=${period}`)

// ── Earnings ──────────────────────────────────────────────────────
export interface EarningsQuarter {
  quarter: string; actual_eps: number | null; estimated_eps: number | null
  surprise_pct: number | null; beat: boolean | null
}
export interface EarningsSurpriseResult {
  quarters: EarningsQuarter[]; beat_rate: number | null; avg_surprise_pct: number | null
  has_estimates: boolean; latest_beat: boolean | null; latest_surprise_pct: number | null
}
export const getEarningsSurprise = (ticker: string, quarters = 8) =>
  request<EarningsSurpriseResult>(`/earnings/surprise?ticker=${encodeURIComponent(ticker)}&quarters=${quarters}`)

// ── News ──────────────────────────────────────────────────────────
export const getNewsFeed   = (scope: 'national' | 'international', limit = 20) =>
  request<NewsFeed>(`/news/feed?scope=${scope}&limit=${limit}`)
export const getStockNews  = (ticker: string, limit = 10) =>
  request<NewsFeed>(`/news/stock?ticker=${encodeURIComponent(ticker)}&limit=${limit}`)
export const getNewsImpact = (ticker: string, publishedAt: string) =>
  request<ImpactData>(`/news/impact?ticker=${encodeURIComponent(ticker)}&published_at=${encodeURIComponent(publishedAt)}`)

// ── Types ─────────────────────────────────────────────────────────
export interface TickerSnapshot {
  price: number; prev_close: number; change: number; pct_change: number
}
export interface SectorStock {
  symbol: string; name: string; price: number
  change: number; pct_change: number; volume: number
  year_high: number; year_low: number
}
export interface SymbolEntry { symbol: string; name: string }

export interface FundamentalsReq {
  symbols: string[]; period: string; interval: string; window?: number
}
export interface OHLCVRow {
  date: string; open: number; high: number; low: number; close: number; volume: number
}
export interface KPISet {
  cagr: number; volatility: number; sharpe: number; max_drawdown: number
  calmar: number; skewness: number; excess_kurtosis: number
  pct_positive: number; stationarity_diffs: number
}
export interface RollingRow {
  date: string; rolling_cagr: number; rolling_sharpe: number
  rolling_calmar: number; drawdown: number
}

export interface VolRequest  { tickers: string[]; period: string }
export interface ForecastRequest {
  tickers: string[]; period: string; best_p: number; best_q: number; horizon: number
}
export interface VolAnalysis {
  opt_lambda: number; half_life: number
  current_vol: number; peak_vol: number; peak_date: string; mean_vol: number
  var_1d_1m: number
  vol_history: { date: string; ewma_vol: number; rolling_vol: number | null }[]
  decay_table:  { λ: number; 'Half-life (days)': number; '95%-weight window (days)': number }[]
  garch_models: GarchModel[]
  best_p: number; best_q: number
  best_aic: number; best_bic: number
}
export interface GarchModel {
  model: string; aic: number; bic: number; all_significant: boolean
}
export interface VolForecast {
  forecast: { day: number; variance: number; daily_vol: number; ann_vol: number; var_1d_1m: number }[]
  hist_vol: { date: string; vol: number }[]
}

export interface OptimizeRequest {
  tickers: string[]; capital: number
  user_target_annual: number; risk_appetite_monthly: number
  allow_short: boolean; invest_mode: string; dca_months: number; stop_loss_k: number
  use_ml_signals?: boolean
}
export interface OptimizeResult {
  metrics: {
    annual_return: number; annual_vol: number; sharpe: number
    monthly_var_95: number; mc_var: number; mc_cvar: number; t_df: number
  }
  weights:      Record<string, number>
  stop_table:   StopRow[]
  warnings:     RegimeWarning[]
  dca_schedule: DCARow[]
  dcc_a: number; dcc_b: number
  ml_adjusted?: boolean
}

export interface SignalRequest {
  tickers: string[]; period?: string
  long_threshold?: number; short_threshold?: number
}
export interface FeatureImportance { feature: string; importance: number }
export interface CalibrationPoint  { predicted: number; actual: number }
export interface SignalHistoryRow  { date: string; p_up: number; signal: number; regime: string }
export interface SignalMetrics {
  log_loss: number; brier: number; roc_auc: number
  accuracy: number; n_test: number; pos_rate: number
}
export interface TickerSignal {
  p_up: number; signal: number; regime: string; confidence_bin: string
  metrics: SignalMetrics
  feature_importances: FeatureImportance[]
  calibration: CalibrationPoint[]
  signal_history: SignalHistoryRow[]
  error?: string
}
export type SignalResult = Record<string, TickerSignal>
export interface StopRow {
  ticker: string; regime: string; regime_probs: Record<string, number>
  bl_return: number; weight: number; allocation: number; shares: number
  entry_price: number; stop_price: number; stop_pct: number
  daily_sigma: number; at_risk: number; is_short: boolean
}
export interface RegimeWarning {
  ticker: string; current: string; shift_to: string; probability: number
}
export interface DCARow { Month: string; 'Deploy (Rs)': number; [ticker: string]: number | string }

export interface NewsArticle {
  id: string; title: string; summary: string; url: string; source: string
  published_at: string; banner_image: string | null
  sentiment_score: number; sentiment_label: string
  tickers: { ticker: string; sentiment_score: number; sentiment_label: string }[]
  topics:  { topic: string; relevance_score: number }[]
}
export interface NewsFeed { articles: NewsArticle[]; cached: boolean }
export type ImpactData =
  | { market_open: true; current_price: number; change: number; change_pct: number; quote_time: string }
  | { market_open: false }
