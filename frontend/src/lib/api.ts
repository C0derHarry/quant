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

// ── Screener ──────────────────────────────────────────────────────────────────

export interface RunResponse {
  run_id: string
}

export interface RunStatus {
  run_id: string
  status: 'running' | 'done' | 'error'
  total: number
  scanned: number
  passed: number
  error?: string | null
}

export interface ScreenerResult {
  id: string
  run_id: string
  symbol: string
  name: string | null
  score: number
  setup_type: string | null
  signals_triggered: string[]
  rs_ratio: number | null
  rs_rank: number | null
  trend_score: number | null
  adx: number | null
  entry_pivot: number | null
  stop: number | null
  target: number | null
  rr: number | null
  atr: number | null
  earnings_flag: boolean | null
  last_close: number | null
  week52_high: number | null
  week52_low: number | null
  avg_turnover: number | null
}

export interface CandleBar {
  time: number
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export interface IndicatorPoint {
  time: number
  value: number
}

export interface StockDetail {
  symbol: string
  candles: CandleBar[]
  ema9: IndicatorPoint[]
  ema21: IndicatorPoint[]
  ema50: IndicatorPoint[]
  rsi: IndicatorPoint[]
  macd_hist: IndicatorPoint[]
}

export const runScan = () =>
  request<RunResponse>('/screener/run', { method: 'POST' })

export const getRunStatus = (runId: string) =>
  request<RunStatus>(`/screener/run/${runId}/status`)

export const getScreenerResults = () =>
  request<ScreenerResult[]>('/screener/results')

export const getStockDetail = (symbol: string) =>
  request<StockDetail>(`/screener/stock/${encodeURIComponent(symbol)}`)
