import { useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getMarketStatus } from '../../lib/api'

const TITLES: Record<string, string> = {
  '/':              'Market Overview',
  '/value':         'Value Screen',
  '/fundamentals':  'Stock Deep-Dive',
  '/volatility':    'Volatility Forecast',
  '/portfolio':     'Position Sizing',
  '/technical':     'Technical Analysis',
}

function getTitleForPath(pathname: string): string {
  if (pathname.startsWith('/sector/')) {
    const name = decodeURIComponent(pathname.replace('/sector/', ''))
    return name
  }
  return TITLES[pathname] ?? 'QuantHub'
}

export default function TopBar() {
  const { pathname } = useLocation()
  const title = getTitleForPath(pathname)

  const { data } = useQuery({
    queryKey:  ['market-status'],
    queryFn:   getMarketStatus,
    staleTime: 5 * 60_000,
    refetchInterval: 5 * 60_000,
  })

  const open = data?.is_open ?? false

  return (
    <header className="fixed top-0 right-0 left-[220px] z-20 flex h-[56px] items-center justify-between border-b border-border bg-bg-surface/90 px-6 backdrop-blur-sm">
      <h1 className="text-md font-semibold text-ink-primary">{title}</h1>

      <div className="flex items-center gap-4">
        {/* Market status */}
        <div className="flex items-center gap-2 rounded-sm border border-border bg-bg-elevated px-3 py-1.5">
          <span
            className={`h-1.5 w-1.5 rounded-full ${
              open ? 'bg-gain animate-pulse-dot' : 'bg-ink-disabled'
            }`}
          />
          <span className="text-xs font-medium text-ink-secondary">
            NSE&nbsp;
            <span className={open ? 'text-gain' : 'text-ink-muted'}>
              {open ? 'LIVE' : 'CLOSED'}
            </span>
          </span>
        </div>

        <div className="h-4 w-px bg-border" />

        <span className="font-mono text-xs text-ink-muted">
          {new Date().toLocaleDateString('en-IN', {
            day: '2-digit', month: 'short', year: 'numeric',
          })}
        </span>
      </div>
    </header>
  )
}
