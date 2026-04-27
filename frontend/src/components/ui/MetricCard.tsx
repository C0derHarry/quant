import { cn } from '../../lib/utils'
import { ReactNode, useState, useRef, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { HelpCircle } from 'lucide-react'

interface MetricCardProps {
  label:    string
  value:    string | ReactNode
  sub?:     string | ReactNode
  accent?:  'gain' | 'loss' | 'warn' | 'accent' | 'neutral'
  className?: string
  size?:    'sm' | 'md' | 'lg'
  tooltip?: string
}

const ACCENT_VALUE: Record<string, string> = {
  gain:    'text-gain',
  loss:    'text-loss',
  warn:    'text-warn',
  accent:  'text-accent',
  neutral: 'text-ink-primary',
}

export default function MetricCard({
  label, value, sub, accent = 'neutral', className, size = 'md', tooltip,
}: MetricCardProps) {
  const cardRef  = useRef<HTMLDivElement>(null)
  const [show, setShow] = useState(false)
  const [pos,  setPos]  = useState({ top: 0, right: 0 })

  const handleEnter = useCallback(() => {
    if (!tooltip || !cardRef.current) return
    const r = cardRef.current.getBoundingClientRect()
    setPos({
      top:   r.top + 28,                    // below the ? icon
      right: window.innerWidth - r.right,   // right-aligned to card edge
    })
    setShow(true)
  }, [tooltip])

  const handleLeave = useCallback(() => setShow(false), [])

  return (
    <div
      ref={cardRef}
      onMouseEnter={handleEnter}
      onMouseLeave={handleLeave}
      className={cn(
        'relative rounded-md border border-border bg-bg-surface shadow-card transition-shadow hover:shadow-card-lg',
        size === 'sm' && 'px-4 py-3',
        size === 'md' && 'px-5 py-4',
        size === 'lg' && 'px-6 py-5',
        className,
      )}
    >
      {tooltip && (
        <div className="absolute right-2.5 top-2.5 z-10">
          <HelpCircle
            size={12}
            className={cn(
              'cursor-help transition-colors',
              show ? 'text-ink-muted' : 'text-ink-disabled',
            )}
          />
        </div>
      )}

      <p className="mb-1 text-2xs font-semibold uppercase tracking-[0.08em] text-ink-secondary">
        {label}
      </p>
      <div className={cn(
        'num font-mono font-semibold',
        size === 'sm' && 'text-xl',
        size === 'md' && 'text-2xl',
        size === 'lg' && 'text-3xl',
        ACCENT_VALUE[accent],
      )}>
        {value}
      </div>
      {sub != null && (
        <p className="mt-1 text-xs text-ink-muted">{sub}</p>
      )}

      {show && tooltip && createPortal(
        <div
          className="fixed z-[200] w-56 max-w-[calc(100vw-2rem)] rounded border border-border bg-bg-elevated p-2.5 text-xs leading-relaxed text-ink-secondary shadow-lg"
          style={{ top: pos.top, right: pos.right }}
        >
          {tooltip}
        </div>,
        document.body,
      )}
    </div>
  )
}
