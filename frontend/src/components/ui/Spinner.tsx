import { cn } from '../../lib/utils'

interface SpinnerProps { className?: string; size?: number }

export default function Spinner({ className, size = 20 }: SpinnerProps) {
  return (
    <svg
      width={size} height={size}
      viewBox="0 0 24 24" fill="none"
      className={cn('animate-spin text-accent', className)}
    >
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2.5"
        className="opacity-20" />
      <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" strokeWidth="2.5"
        strokeLinecap="round" />
    </svg>
  )
}

export function PageLoader({ label }: { label?: string }) {
  return (
    <div className="flex h-[60vh] flex-col items-center justify-center gap-4 text-ink-muted">
      <Spinner size={28} />
      {label && <p className="text-sm">{label}</p>}
    </div>
  )
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="flex h-[60vh] flex-col items-center justify-center gap-2">
      <p className="text-sm font-semibold text-loss">Error</p>
      <p className="max-w-md text-center text-xs text-ink-muted">{message}</p>
    </div>
  )
}
