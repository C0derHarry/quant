import { useState, useCallback, useRef } from 'react'
import { streamBacktest, type BacktestResult, type BacktestStreamEvent } from '../lib/api'
import PortfolioPicker from '../components/backtest/PortfolioPicker'
import StrategyCatalog from '../components/backtest/StrategyCatalog'
import StrategyConfigForm from '../components/backtest/StrategyConfigForm'
import RunProgress, { type StageState } from '../components/backtest/RunProgress'
import ResultsView from '../components/backtest/ResultsView'

type AppState = 'pick_portfolio' | 'pick_strategy' | 'configure' | 'running' | 'results'

const STAGE_LABELS = [
  'Fetching price data',
  'Generating signals',
  'Simulating with costs',
  'Computing KPIs',
]

function yearsAgo(n: number) {
  const d = new Date()
  d.setFullYear(d.getFullYear() - n)
  return d.toISOString().slice(0, 10)
}

export default function Backtesting() {
  const [appState,   setAppState]   = useState<AppState>('pick_portfolio')
  const [portfolioId, setPortfolioId] = useState<string | null>(null)
  const [strategyId,  setStrategyId]  = useState<string | null>(null)
  const [params,      setParams]      = useState<Record<string, unknown>>({})
  const [brokerId,    setBrokerId]    = useState('zerodha')
  const [universe,    setUniverse]    = useState('NIFTY 50')
  const [startDate,   setStartDate]   = useState(yearsAgo(3))
  const [endDate,     setEndDate]     = useState(new Date().toISOString().slice(0, 10))
  const [capital,     setCapital]     = useState(1_000_000)
  const [stages,      setStages]      = useState<StageState[]>(
    STAGE_LABELS.map(label => ({ label, status: 'waiting' as const }))
  )
  const [runError,    setRunError]    = useState<string | null>(null)
  const [result,      setResult]      = useState<BacktestResult | null>(null)

  const abortRef = useRef<AbortController | null>(null)

  const handleParam = useCallback((field: string, value: unknown) => {
    setParams(p => ({ ...p, [field]: value }))
  }, [])

  const handleDateRange = useCallback((start: string, end: string) => {
    setStartDate(start)
    setEndDate(end)
  }, [])

  function resetStages() {
    setStages(STAGE_LABELS.map(label => ({ label, status: 'waiting' })))
  }

  async function handleRun() {
    if (!strategyId) return

    resetStages()
    setRunError(null)
    setResult(null)
    setAppState('running')

    abortRef.current = new AbortController()

    function onEvent(ev: BacktestStreamEvent) {
      if (ev.type === 'stage') {
        const idx = ev.stage - 1
        setStages(prev => prev.map((s, i) => {
          if (i < idx)  return { ...s, status: 'done' }
          if (i === idx) return { ...s, status: ev.status, detail: ev.label }
          return s
        }))
      }
      if (ev.type === 'error') {
        setRunError(ev.message)
      }
    }

    try {
      const res = await streamBacktest(
        strategyId,
        JSON.stringify(params),
        brokerId,
        universe,
        startDate,
        endDate,
        capital,
        portfolioId,
        onEvent,
        abortRef.current.signal,
      )
      setStages(prev => prev.map(s => ({ ...s, status: 'done' })))
      setResult(res)
      setAppState('results')
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        setRunError((err as Error).message)
      }
    }
  }

  function handleRerun() {
    setAppState('configure')
    setResult(null)
  }

  return (
    <div className="space-y-5 animate-fade-up">
      {/* Header */}
      <div>
        <h1 className="text-base font-bold text-ink-primary">Backtesting</h1>
        <p className="mt-0.5 text-xs text-ink-muted">
          Test systematic strategies on historical NSE data with realistic Indian transaction costs.
        </p>
      </div>

      {/* Stepper breadcrumb */}
      {appState !== 'running' && appState !== 'results' && (
        <div className="flex items-center gap-2 text-2xs">
          {(['pick_portfolio', 'pick_strategy', 'configure'] as const).map((s, i) => (
            <span key={s} className="flex items-center gap-2">
              {i > 0 && <span className="text-ink-disabled">/</span>}
              <span className={
                appState === s ? 'font-semibold text-accent' : 'text-ink-disabled'
              }>
                {['Portfolio', 'Strategy', 'Configure'][i]}
              </span>
            </span>
          ))}
        </div>
      )}

      {/* Content */}
      <div className="max-w-2xl">
        {appState === 'pick_portfolio' && (
          <PortfolioPicker
            selectedId={portfolioId}
            onChange={setPortfolioId}
            onNext={() => setAppState('pick_strategy')}
          />
        )}

        {appState === 'pick_strategy' && (
          <StrategyCatalog
            selectedId={strategyId}
            onChange={setStrategyId}
            onNext={() => setAppState('configure')}
            onBack={() => setAppState('pick_portfolio')}
          />
        )}

        {appState === 'configure' && strategyId && (
          <StrategyConfigForm
            strategyId={strategyId}
            params={params}
            brokerId={brokerId}
            universe={universe}
            startDate={startDate}
            endDate={endDate}
            capital={capital}
            onChange={handleParam}
            onBroker={setBrokerId}
            onUniverse={setUniverse}
            onDateRange={handleDateRange}
            onCapital={setCapital}
            onRun={handleRun}
            onBack={() => setAppState('pick_strategy')}
          />
        )}

        {appState === 'running' && (
          <RunProgress stages={stages} error={runError} />
        )}
      </div>

      {/* Results — full width */}
      {appState === 'results' && result && (
        <ResultsView result={result} onRerun={handleRerun} />
      )}
    </div>
  )
}
