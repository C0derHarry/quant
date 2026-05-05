import { useState } from 'react'
import { cn } from '../../lib/utils'

interface Preset {
  label:     string
  startDate: string
  endDate:   string
}

function yearsAgo(n: number): string {
  const d = new Date()
  d.setFullYear(d.getFullYear() - n)
  return d.toISOString().slice(0, 10)
}

const today = new Date().toISOString().slice(0, 10)

const PRESETS: Preset[] = [
  { label: '1Y',              startDate: yearsAgo(1),  endDate: today },
  { label: '3Y',              startDate: yearsAgo(3),  endDate: today },
  { label: '5Y',              startDate: yearsAgo(5),  endDate: today },
  { label: '10Y',             startDate: yearsAgo(10), endDate: today },
  { label: 'COVID (Mar 20–Mar 23)', startDate: '2020-03-01', endDate: '2023-03-31' },
]

interface Props {
  startDate: string
  endDate:   string
  onSelect:  (start: string, end: string) => void
}

export default function TimeRangePicker({ startDate, endDate, onSelect }: Props) {
  const [custom, setCustom] = useState(false)

  const activePreset = !custom
    ? PRESETS.find(p => p.startDate === startDate && p.endDate === endDate)
    : null

  function handlePreset(p: Preset) {
    setCustom(false)
    onSelect(p.startDate, p.endDate)
  }

  function handleCustom() {
    setCustom(true)
  }

  return (
    <div>
      <p className="mb-2 text-2xs font-semibold uppercase tracking-wide text-ink-disabled">Time Range</p>

      <div className="flex flex-wrap gap-2">
        {PRESETS.map(p => (
          <button
            key={p.label}
            onClick={() => handlePreset(p)}
            className={cn(
              'rounded border px-3 py-1 text-xs font-medium transition-colors',
              !custom && activePreset?.label === p.label
                ? 'border-accent bg-[rgba(56,139,253,.1)] text-accent'
                : 'border-border text-ink-muted hover:border-ink-disabled hover:text-ink-secondary',
            )}
          >
            {p.label}
          </button>
        ))}
        <button
          onClick={handleCustom}
          className={cn(
            'rounded border px-3 py-1 text-xs font-medium transition-colors',
            custom
              ? 'border-accent bg-[rgba(56,139,253,.1)] text-accent'
              : 'border-border text-ink-muted hover:border-ink-disabled hover:text-ink-secondary',
          )}
        >
          Custom
        </button>
      </div>

      {custom && (
        <div className="mt-3 flex items-center gap-3">
          <div className="flex-1">
            <label className="text-2xs text-ink-disabled">Start</label>
            <input
              type="date"
              value={startDate}
              max={endDate}
              onChange={e => onSelect(e.target.value, endDate)}
              className="mt-1 w-full rounded border border-border bg-bg-overlay px-2.5 py-1.5 text-xs text-ink-primary focus:border-accent focus:outline-none"
            />
          </div>
          <span className="mt-4 text-xs text-ink-disabled">→</span>
          <div className="flex-1">
            <label className="text-2xs text-ink-disabled">End</label>
            <input
              type="date"
              value={endDate}
              min={startDate}
              max={today}
              onChange={e => onSelect(startDate, e.target.value)}
              className="mt-1 w-full rounded border border-border bg-bg-overlay px-2.5 py-1.5 text-xs text-ink-primary focus:border-accent focus:outline-none"
            />
          </div>
        </div>
      )}

      {!custom && (
        <p className="mt-2 text-2xs text-ink-disabled">
          {startDate} → {endDate}
        </p>
      )}
    </div>
  )
}
