import { useQuery } from '@tanstack/react-query'
import { getBrokerages, getBrokerSummary, type BrokerageSpec } from '../../lib/api'
import { cn } from '../../lib/utils'

interface Props {
  selectedId: string
  universe:   string
  onChange:   (id: string) => void
}

export default function BrokeragePicker({ selectedId, universe, onChange }: Props) {
  const { data: brokers } = useQuery({
    queryKey: ['brokerages'],
    queryFn:  getBrokerages,
    staleTime: Infinity,
  })

  const { data: summary } = useQuery({
    queryKey: ['broker-summary', selectedId, universe],
    queryFn:  () => getBrokerSummary(selectedId, universe),
    staleTime: 60_000,
    enabled:  !!selectedId,
  })

  return (
    <div>
      <p className="mb-2 text-2xs font-semibold uppercase tracking-wide text-ink-disabled">Brokerage</p>

      <div className="flex flex-wrap gap-2">
        {(brokers ?? []).map((b: BrokerageSpec) => (
          <button
            key={b.id}
            onClick={() => onChange(b.id)}
            className={cn(
              'rounded border px-3 py-1.5 text-xs font-medium transition-colors',
              selectedId === b.id
                ? 'border-accent bg-[rgba(56,139,253,.1)] text-accent'
                : 'border-border text-ink-muted hover:border-ink-disabled hover:text-ink-secondary',
            )}
          >
            {b.label}
          </button>
        ))}
      </div>

      {summary && (
        <div className="mt-3 flex items-center gap-6 rounded border border-border bg-bg-elevated px-4 py-2.5 text-xs">
          <div>
            <span className="text-ink-disabled">Buy ₹1L: </span>
            <span className="font-mono font-semibold text-ink-primary">
              ₹{Number((summary as any)?.per_lakh_buy?.total ?? 0).toFixed(2)}
            </span>
          </div>
          <div>
            <span className="text-ink-disabled">Sell ₹1L: </span>
            <span className="font-mono font-semibold text-ink-primary">
              ₹{Number((summary as any)?.per_lakh_sell?.total ?? 0).toFixed(2)}
            </span>
          </div>
          <div>
            <span className="text-ink-disabled">Slippage: </span>
            <span className="font-mono text-ink-secondary">
              {(summary as any)?.slippage_bps ?? 0} bps
            </span>
          </div>
        </div>
      )}
    </div>
  )
}
