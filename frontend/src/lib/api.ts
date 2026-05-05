import { supabase } from './supabase'

const BASE = '/api'

async function authHeader(): Promise<Record<string, string>> {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const auth = await authHeader()
  const res  = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...auth, ...init?.headers },
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
export interface SectorQuote {
  price:      number
  change:     number
  pct_change: number
  volume:     number
}
export const getSectorQuotes = (name: string) =>
  request<Record<string, SectorQuote>>(`/market/sector/${encodeURIComponent(name)}/quotes`)
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
export const getMarketStatus = () =>
  request<{ is_open: boolean; is_trading_day: boolean }>('/market/status')

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

export interface FrontierPoint { ret: number; vol: number; sharpe: number; weights: Record<string, number> }
export interface FrontierResult { frontier: FrontierPoint[]; max_sharpe: FrontierPoint; min_var: FrontierPoint }
export const getEfficientFrontier = (body: { tickers: string[]; period?: string }) =>
  request<FrontierResult>('/portfolio/frontier', { method: 'POST', body: JSON.stringify(body) })

export interface RiskParityResult {
  weights: Record<string, number>
  metrics: { annual_return: number; annual_vol: number; sharpe: number }
  risk_contributions: Record<string, number>
  stop_table: StopRow[]
}
export const getRiskParity = (body: { tickers: string[]; capital: number; stop_loss_k?: number; period?: string }) =>
  request<RiskParityResult>('/portfolio/risk-parity', { method: 'POST', body: JSON.stringify(body) })

export interface WalkForwardResult {
  equity_curve:   { date: string; value: number; benchmark: number }[]
  window_metrics: { window: number; train_start: string; train_end: string;
                    test_start: string; test_end: string; sharpe: number; return: number; max_drawdown: number }[]
  aggregate:      { sharpe: number; annual_return: number; max_drawdown: number; calmar: number; alpha: number }
  degradation_slope: number
}
export const runWalkForward = (body: {
  tickers: string[]; weights: Record<string, number>; train_months?: number;
  test_months?: number; n_windows?: number; cost_bps?: number;
  atr_stop_mult?: number; use_ml?: boolean; use_regimes?: boolean
}) => request<WalkForwardResult>('/backtest/run', { method: 'POST', body: JSON.stringify(body) })

export interface SensitivityResult {
  x_param: string; x_values: number[]; y_param: string; y_values: number[]
  sharpe_grid: number[][]
}
export const runSensitivity = (body: { tickers: string[]; weights: Record<string, number>; period?: string }) =>
  request<SensitivityResult>('/backtest/sensitivity', { method: 'POST', body: JSON.stringify(body) })

export interface RegimeBar { date: string; price: number; regime: string; prob_bull: number; prob_bear: number; prob_sideways: number }
export interface RegimeStat { regime: string; mean_return: number; vol: number; avg_duration_days: number }
export interface RegimeTicker { series: RegimeBar[]; state_stats: RegimeStat[]; transition_matrix: number[][] }
export const getRegimes = (tickers: string[], period = '2y') =>
  request<Record<string, RegimeTicker>>(`/backtest/regimes?tickers=${tickers.join(',')}&period=${period}`)

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
export const getPortfolioNews = (tickers: string[], limit = 15) =>
  request<PortfolioNewsFeed>(`/news/portfolio?tickers=${encodeURIComponent(tickers.join(','))}&limit=${limit}`)

// ── Technical Analysis ────────────────────────────────────────────
export interface TechnicalIndicator {
  name: string; category: string
  signal: 'Bullish' | 'Bearish' | 'Neutral'
  value: string; description: string
}
export interface TechnicalSummary {
  bullish: number; bearish: number; neutral: number; total: number
  verdict: 'STRONG BUY' | 'BUY' | 'NEUTRAL' | 'SELL' | 'STRONG SELL'
  bull_ratio: number
}
export interface TechnicalResult {
  ticker: string; period: string
  indicators: TechnicalIndicator[]; summary: TechnicalSummary
}
export const getTechnicalAnalysis = (ticker: string, period = '1y') =>
  request<TechnicalResult>(`/technical/analyze?ticker=${encodeURIComponent(ticker)}&period=${period}`)

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

// ── User Portfolios ───────────────────────────────────────────────
export interface SavedPortfolio {
  id:             string
  name:           string
  tickers:        string[]
  weights:        Record<string, number>
  capital:        number | null
  portfolio_type: string | null
  invested_at:    string
  created_at:     string
}

export interface SavePortfolioBody {
  name:            string
  tickers:         string[]
  weights:         Record<string, number>
  capital?:        number
  portfolio_type?: string
  optimize_result?: Record<string, unknown>
}

export const listPortfolios  = () =>
  request<SavedPortfolio[]>('/portfolios')
export const savePortfolio   = (body: SavePortfolioBody) =>
  request<SavedPortfolio>('/portfolios', { method: 'POST', body: JSON.stringify(body) })
export const deletePortfolio = (id: string) =>
  request<{ ok: boolean }>(`/portfolios/${id}`, { method: 'DELETE' })
export const saveBacktestResult = (portfolioId: string, result: unknown) =>
  request<{ ok: boolean }>(`/portfolios/${portfolioId}/backtest`,
    { method: 'POST', body: JSON.stringify(result) })

// ── Tracker ───────────────────────────────────────────────────────
export interface TrackerSeries { date: string; portfolio: number; benchmark: number | null }
export interface TrackerMetrics {
  total_return: number; cagr: number | null; annual_vol: number | null
  sharpe: number | null; max_drawdown: number; days_held: number
}
export interface TickerPerf { ticker: string; return: number; weight: number; allocation: number | null }
export interface TrackerResult {
  portfolio_name:     string
  invested_at:        string
  capital:            number | null
  tickers:            string[]
  series:             TrackerSeries[]
  metrics:            TrackerMetrics
  ticker_performance: TickerPerf[]
}

export const getTrackerData = (portfolioId: string) =>
  request<TrackerResult>(`/tracker/${portfolioId}`)

export interface NewsArticle {
  id: string; title: string; summary: string; url: string; source: string
  published_at: string; banner_image: string | null
  sentiment_score: number; sentiment_label: string
  tickers: { ticker: string; sentiment_score: number; sentiment_label: string }[]
  topics:  { topic: string; relevance_score: number }[]
}
export interface NewsFeed { articles: NewsArticle[]; cached: boolean }
export interface PortfolioNewsTickerSentiment {
  ticker: string; avg_score: number; label: string; article_count: number
}
export interface PortfolioNewsFeed {
  articles: NewsArticle[]; ticker_sentiment: PortfolioNewsTickerSentiment[]; cached: boolean
}
export type ImpactData =
  | { market_open: true; current_price: number; change: number; change_pct: number; quote_time: string }
  | { market_open: false }

// ── AI Overview ───────────────────────────────────────────────────────────

export interface AIStockAnalysis {
  symbol:        string
  company_name:  string
  sector:        string
  current_price: number | null
  pe:            number | null
  roe:           number | null
  de:            number | null
  tech_verdict:  'STRONG BUY' | 'BUY' | 'NEUTRAL' | 'SELL' | 'STRONG SELL'
  bullish_count: number
  bearish_count: number
  neutral_count: number
  rsi:           number | null
  macd_signal:   'Bullish' | 'Bearish' | 'Neutral'
  ema_signal:    'Bullish' | 'Bearish' | 'Neutral'
  adx_signal:    'Bullish' | 'Bearish' | 'Neutral'
  bb_signal:     'Bullish' | 'Bearish' | 'Neutral'
  quality_verdict: 'Genuinely Discounted' | 'Value Trap' | 'Overvalued' | 'Watch'
  conviction:      'High' | 'Medium' | 'Low'
  entry_comment:   string
  stop_comment:    string
  target_comment:  string
  reasoning:       string
}

export interface AIOverviewResult {
  stocks:          AIStockAnalysis[]
  generated_at:    string
  generated_at_ts: number
  candidate_count: number
  universe:        string
  extras:          string[]
  provider:        string
  model:           string
  from_cache:      boolean
}

// ── BYO API key catalog + per-user storage ─────────────────────────────

export type ProviderId = 'google' | 'anthropic' | 'openai'

export interface ProviderModel {
  id:    string
  label: string
  tier:  'free' | 'paid'
}

export interface ProviderConfig {
  label: string
  key_url: string
  free_tier_available: boolean
  free_tier_note: string
  instructions: string[]
  models: ProviderModel[]
}

export interface AIKeyInfo {
  provider:  ProviderId
  model:     string
  key_last4: string
}

export const getProviders = () =>
  request<Record<ProviderId, ProviderConfig>>('/ai-keys/providers')

export async function getMyAIKey(): Promise<AIKeyInfo | null> {
  return request<AIKeyInfo | null>('/ai-keys')
}

export const saveMyAIKey = (body: { provider: ProviderId; model: string; api_key: string }) =>
  request<{ ok: true }>('/ai-keys', { method: 'PUT', body: JSON.stringify(body) })

export const deleteMyAIKey = () =>
  request<{ ok: true }>('/ai-keys', { method: 'DELETE' })

export const getAIUniverses = () => request<string[]>('/ai-overview/universes')

export const getCachedAIOverview = (universe: string, extras: string[]) =>
  request<AIOverviewResult>(
    `/ai-overview/cached?universe=${encodeURIComponent(universe)}` +
    (extras.length ? `&extras=${encodeURIComponent(extras.join(','))}` : ''),
  )

export type AIOverviewStreamEvent =
  | { type: 'stage';  stage: number; status: 'running' | 'done' }
  | { type: 'batch';  done: number;  total: number }
  | { type: 'result'; data: AIOverviewResult }
  | { type: 'error';  message: string }

export async function streamAIOverview(
  universe: string,
  extras: string[],
  force: boolean,
  onEvent: (ev: AIOverviewStreamEvent) => void,
  signal?: AbortSignal,
): Promise<AIOverviewResult> {
  const auth   = await authHeader()
  const params = new URLSearchParams({ universe, force: String(force) })
  if (extras.length) params.set('extras', extras.join(','))
  const res = await fetch(`${BASE}/ai-overview/stream?${params.toString()}`, {
    headers: { ...auth },
    signal,
  })
  if (!res.ok || !res.body) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }

  const reader  = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let result: AIOverviewResult | null = null
  let errMsg: string | null = null

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    // SSE frames are separated by a blank line ("\n\n").
    let idx: number
    while ((idx = buffer.indexOf('\n\n')) !== -1) {
      const frame = buffer.slice(0, idx)
      buffer = buffer.slice(idx + 2)
      const line = frame.split('\n').find(l => l.startsWith('data:'))
      if (!line) continue
      const json = line.slice(5).trim()
      if (!json) continue
      try {
        const ev = JSON.parse(json) as AIOverviewStreamEvent
        onEvent(ev)
        if (ev.type === 'result') result = ev.data
        if (ev.type === 'error')  errMsg = ev.message
      } catch {
        // ignore malformed frame
      }
    }
  }

  if (errMsg)  throw new Error(errMsg)
  if (!result) throw new Error('Stream ended without a result')
  return result
}

// ── Strategies / Backtesting ──────────────────────────────────────

export interface ParamSpec {
  name:     string
  type:     'int' | 'float' | 'enum' | 'bool'
  default:  unknown
  label:    string
  help:     string
  min?:     number
  max?:     number
  choices?: string[]
}

export interface StrategySpec {
  id:                    string
  label:                 string
  description:           string
  reference:             string
  requires_fundamentals: boolean
  basic_params:          ParamSpec[]
  advanced_params:       ParamSpec[]
}

export interface BrokerageSpec {
  id:           string
  label:        string
  delivery_pct: number
  dp_per_sell:  number
  source_url:   string
}

export interface BacktestKPIs {
  cagr:            number
  benchmark_cagr:  number
  alpha:           number
  sharpe:          number
  sortino:         number
  calmar:          number
  max_drawdown:    number
  hit_rate:        number
  avg_turnover:    number
  total_cost_inr:  number
  n_trades:        number
  n_rebalances:    number
}

export interface BacktestResult {
  strategy_id:               string
  equity_curve:              { date: string; value: number }[]
  benchmark_curve:           { date: string; value: number }[]
  drawdown_curve:            { date: string; dd_pct: number }[]
  trade_log:                 BacktestTrade[]
  kpis:                      BacktestKPIs
  params:                    Record<string, unknown>
  universe:                  string
  start_date:                string
  end_date:                  string
  brokerage_id:              string
  total_cost:                number
  survivorship_bias_warning: boolean
  tickers:                   string[]
  run_id?:                   string
}

export interface BacktestTrade {
  date:   string
  ticker: string
  side:   'buy' | 'sell'
  value:  number
  cost_breakdown: Record<string, number>
}

export type BacktestStreamEvent =
  | { type: 'stage';  stage: number; status: 'running' | 'done'; label?: string; n_tickers?: number; n_rebalances?: number }
  | { type: 'result'; data: BacktestResult }
  | { type: 'error';  message: string }

export const getStrategyCatalog  = () => request<StrategySpec[]>('/strategies/catalog')
export const getBrokerages        = () => request<BrokerageSpec[]>('/strategies/brokerages')
export const getBrokerSummary     = (brokerId: string, universe: string) =>
  request<Record<string, unknown>>(`/strategies/brokerages/${brokerId}/summary?universe=${encodeURIComponent(universe)}`)
export const listStrategyRuns     = (limit = 20) => request<Record<string, unknown>[]>(`/strategies/runs?limit=${limit}`)
export const getStrategyRun       = (id: string) => request<Record<string, unknown>>(`/strategies/runs/${id}`)

export async function exportStrategy(body: {
  strategy_id: string
  params:      Record<string, unknown>
  broker_id:   string
  tickers:     string[]
  start_date:  string
  end_date:    string
  kpis:        BacktestKPIs
}): Promise<void> {
  const auth = await authHeader()
  const res  = await fetch(`${BASE}/strategies/export`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json', ...auth },
    body:    JSON.stringify(body),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  const { filename, content } = await res.json()
  const blob = new Blob([content], { type: 'text/plain' })
  const url  = URL.createObjectURL(blob)
  const a    = document.createElement('a')
  a.href = url; a.download = filename; a.click()
  URL.revokeObjectURL(url)
}

export async function streamBacktest(
  strategyId:  string,
  paramsJson:  string,
  brokerId:    string,
  universe:    string,
  startDate:   string,
  endDate:     string,
  capital:     number,
  portfolioId: string | null,
  onEvent:     (ev: BacktestStreamEvent) => void,
  signal?:     AbortSignal,
): Promise<BacktestResult> {
  const auth   = await authHeader()
  const params = new URLSearchParams({
    strategy_id:  strategyId,
    params_json:  paramsJson,
    broker_id:    brokerId,
    universe,
    start_date:   startDate,
    end_date:     endDate,
    capital:      String(capital),
  })
  if (portfolioId) params.set('portfolio_id', portfolioId)

  const res = await fetch(`${BASE}/strategies/run/stream?${params.toString()}`, {
    headers: { ...auth },
    signal,
  })
  if (!res.ok || !res.body) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }

  const reader  = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let result: BacktestResult | null = null
  let errMsg: string | null = null

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let idx: number
    while ((idx = buffer.indexOf('\n\n')) !== -1) {
      const frame = buffer.slice(0, idx)
      buffer = buffer.slice(idx + 2)
      const line = frame.split('\n').find(l => l.startsWith('data:'))
      if (!line) continue
      const json = line.slice(5).trim()
      if (!json) continue
      try {
        const ev = JSON.parse(json) as BacktestStreamEvent
        onEvent(ev)
        if (ev.type === 'result') result = ev.data
        if (ev.type === 'error')  errMsg = ev.message
      } catch { /* ignore */ }
    }
  }

  if (errMsg)  throw new Error(errMsg)
  if (!result) throw new Error('Backtest stream ended without a result')
  return result
}
