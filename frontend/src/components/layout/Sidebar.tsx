import { NavLink, useLocation } from 'react-router-dom'
import {
  BarChart2, TrendingUp, Search, Activity, Sliders,
  ChevronRight, Layers, Home, Brain, Newspaper,
} from 'lucide-react'
import { cn } from '../../lib/utils'

const NAV = [
  { label: 'Overview',   path: '/',            icon: Home,      section: 'MARKET' },
  { label: 'Value Screen', path: '/value',      icon: Search,    section: 'RESEARCH' },
  { label: 'Deep Dive',  path: '/fundamentals', icon: BarChart2, section: 'RESEARCH' },
  { label: 'Volatility', path: '/volatility',   icon: Activity,  section: 'ANALYTICS' },
  { label: 'ML Signals', path: '/signals',      icon: Brain,     section: 'ANALYTICS' },
  { label: 'Portfolio',  path: '/portfolio',    icon: Sliders,    section: 'ANALYTICS' },
  { label: 'News Hub',   path: '/news',          icon: Newspaper,  section: 'NEWS' },
]

const SECTIONS = ['MARKET', 'RESEARCH', 'ANALYTICS', 'NEWS']

export default function Sidebar() {
  const { pathname } = useLocation()

  return (
    <aside className="fixed inset-y-0 left-0 z-30 flex w-[220px] flex-col border-r border-border bg-bg-surface">
      {/* Logo */}
      <div className="flex h-[56px] items-center gap-2.5 border-b border-border px-5">
        <div className="flex h-7 w-7 items-center justify-center rounded-sm bg-accent">
          <TrendingUp size={14} className="text-white" strokeWidth={2.5} />
        </div>
        <span className="font-mono text-sm font-semibold tracking-widest text-ink-primary">
          QUANTHUB
        </span>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-0.5">
        {SECTIONS.map((section) => {
          const items = NAV.filter(n => n.section === section)
          return (
            <div key={section} className="mb-4">
              <p className="mb-1 px-2 text-2xs font-semibold uppercase tracking-[0.1em] text-ink-disabled">
                {section}
              </p>
              {items.map(({ label, path, icon: Icon }) => {
                const active = path === '/'
                  ? pathname === '/'
                  : pathname.startsWith(path)
                return (
                  <NavLink key={path} to={path}>
                    <div
                      className={cn(
                        'group flex items-center gap-3 rounded px-2.5 py-2 text-sm transition-all duration-150',
                        active
                          ? 'bg-[rgba(56,139,253,.1)] text-accent'
                          : 'text-ink-secondary hover:bg-bg-elevated hover:text-ink-primary',
                      )}
                    >
                      <div className={cn(
                        'flex h-[18px] w-[18px] items-center justify-center',
                        active ? 'text-accent' : 'text-ink-muted group-hover:text-ink-secondary',
                      )}>
                        <Icon size={15} strokeWidth={active ? 2.2 : 1.8} />
                      </div>
                      <span className={cn('font-medium', active && 'font-semibold')}>
                        {label}
                      </span>
                      {active && (
                        <ChevronRight size={12} className="ml-auto text-accent opacity-60" />
                      )}
                    </div>
                  </NavLink>
                )
              })}
            </div>
          )
        })}
      </nav>

      {/* Footer */}
      <div className="border-t border-border px-4 py-3">
        <p className="text-2xs text-ink-disabled">
          NSE · BSE · Real-time
        </p>
        <p className="text-2xs text-ink-disabled opacity-60">
          v0.1.0 · India Markets
        </p>
      </div>
    </aside>
  )
}
