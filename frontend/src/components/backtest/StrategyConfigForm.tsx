import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getStrategyCatalog, getBrokerages, type ParamSpec, type StrategySpec, type BrokerageSpec } from '../../lib/api'
import { ChevronDown, ChevronUp } from 'lucide-react'
import { cn } from '../../lib/utils'
import TimeRangePicker from './TimeRangePicker'
import BrokeragePicker from './BrokeragePicker'

interface Props {
  strategyId:  string
  params:      Record<string, unknown>
  brokerId:    string
  universe:    string
  startDate:   string
  endDate:     string
  capital:     number
  onChange:    (field: string, value: unknown) => void
  onBroker:    (id: string) => void
  onUniverse:  (u: string) => void
  onDateRange: (start: string, end: string) => void
  onCapital:   (c: number) => void
  onRun:       () => void
  onBack:      () => void
}

function ParamField({ spec, value, onChange }: {
  spec:     ParamSpec
  value:    unknown
  onChange: (v: unknown) => void
}) {
  if (spec.type === 'bool') {
    return (
      <label className="flex items-center gap-2 cursor-pointer">
        <input
          type="checkbox"
          checked={Boolean(value ?? spec.default)}
          onChange={e => onChange(e.target.checked)}
          className="rounded border-border bg-bg-overlay"
        />
        <span className="text-xs text-ink-primary">{spec.label}</span>
      </label>
    )
  }

  if (spec.type === 'enum' && spec.choices) {
    return (
      <div>
        <label className="text-2xs font-semibold uppercase tracking-wide text-ink-disabled">{spec.label}</label>
        <select
          value={String(value ?? spec.default)}
          onChange={e => onChange(e.target.value)}
          className="mt-1 w-full rounded border border-border bg-bg-overlay px-2.5 py-1.5 text-xs text-ink-primary focus:border-accent focus:outline-none"
        >
          {spec.choices.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <p className="mt-1 text-2xs text-ink-disabled">{spec.help}</p>
      </div>
    )
  }

  // int | float
  return (
    <div>
      <label className="text-2xs font-semibold uppercase tracking-wide text-ink-disabled">{spec.label}</label>
      <input
        type="number"
        value={String(value ?? spec.default)}
        min={spec.min}
        max={spec.max}
        step={spec.type === 'int' ? 1 : 0.01}
        onChange={e => onChange(spec.type === 'int' ? parseInt(e.target.value) : parseFloat(e.target.value))}
        className="mt-1 w-full rounded border border-border bg-bg-overlay px-2.5 py-1.5 text-xs text-ink-primary focus:border-accent focus:outline-none"
      />
      <p className="mt-1 text-2xs text-ink-disabled">{spec.help}</p>
    </div>
  )
}

const UNIVERSES = ["NIFTY 50", "NIFTY 100", "NIFTY MIDCAP 100", "NIFTY SMALLCAP 100", "NIFTY BANK", "NIFTY IT"]

export default function StrategyConfigForm({
  strategyId, params, brokerId, universe, startDate, endDate, capital,
  onChange, onBroker, onUniverse, onDateRange, onCapital, onRun, onBack,
}: Props) {
  const [showAdvanced, setShowAdvanced] = useState(false)

  const { data: catalog } = useQuery({ queryKey: ['strategy-catalog'], queryFn: getStrategyCatalog, staleTime: Infinity })
  const strategy: StrategySpec | undefined = catalog?.find((s: StrategySpec) => s.id === strategyId)

  const basicParams    = strategy?.basic_params    ?? []
  const advancedParams = strategy?.advanced_params ?? []

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <button onClick={onBack} className="text-xs text-ink-muted hover:text-ink-secondary">← Back</button>
        <div>
          <h2 className="text-sm font-semibold text-ink-primary">{strategy?.label ?? 'Configure Strategy'}</h2>
          <p className="text-xs text-ink-muted">Tune parameters then select your time range and broker.</p>
        </div>
      </div>

      {/* Universe */}
      <div>
        <p className="mb-2 text-2xs font-semibold uppercase tracking-wide text-ink-disabled">Stock Universe</p>
        <div className="flex flex-wrap gap-2">
          {UNIVERSES.map(u => (
            <button
              key={u}
              onClick={() => onUniverse(u)}
              className={cn(
                'rounded border px-3 py-1 text-xs font-medium transition-colors',
                universe === u
                  ? 'border-accent bg-[rgba(56,139,253,.1)] text-accent'
                  : 'border-border text-ink-muted hover:border-ink-disabled hover:text-ink-secondary',
              )}
            >
              {u}
            </button>
          ))}
        </div>
      </div>

      {/* Basic params */}
      {basicParams.length > 0 && (
        <div>
          <p className="mb-3 text-2xs font-semibold uppercase tracking-wide text-ink-disabled">Strategy Parameters</p>
          <div className="grid gap-4 sm:grid-cols-2">
            {basicParams.map((spec: ParamSpec) => (
              <ParamField
                key={spec.name}
                spec={spec}
                value={params[spec.name]}
                onChange={v => onChange(spec.name, v)}
              />
            ))}
          </div>
        </div>
      )}

      {/* Advanced params */}
      {advancedParams.length > 0 && (
        <div className="rounded border border-border">
          <button
            onClick={() => setShowAdvanced(p => !p)}
            className="flex w-full items-center justify-between px-4 py-3 text-xs font-semibold text-ink-muted hover:text-ink-primary transition-colors"
          >
            <span>Advanced Parameters</span>
            {showAdvanced ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
          </button>
          {showAdvanced && (
            <div className="border-t border-border px-4 pb-4 pt-3">
              <div className="grid gap-4 sm:grid-cols-2">
                {advancedParams.map((spec: ParamSpec) => (
                  <ParamField
                    key={spec.name}
                    spec={spec}
                    value={params[spec.name]}
                    onChange={v => onChange(spec.name, v)}
                  />
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Time range */}
      <TimeRangePicker startDate={startDate} endDate={endDate} onSelect={onDateRange} />

      {/* Capital */}
      <div>
        <p className="mb-1.5 text-2xs font-semibold uppercase tracking-wide text-ink-disabled">Starting Capital (₹)</p>
        <input
          type="number"
          value={capital}
          min={10000}
          step={10000}
          onChange={e => onCapital(Number(e.target.value))}
          className="w-full rounded border border-border bg-bg-overlay px-3 py-2 text-sm text-ink-primary focus:border-accent focus:outline-none"
        />
      </div>

      {/* Broker */}
      <BrokeragePicker selectedId={brokerId} universe={universe} onChange={onBroker} />

      <button
        onClick={onRun}
        className="w-full rounded bg-accent py-3 text-sm font-bold text-white transition-all hover:bg-accent/90"
      >
        Run Backtest
      </button>
    </div>
  )
}
