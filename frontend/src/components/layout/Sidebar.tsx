import { NavLink, useLocation } from 'react-router-dom'
import {
  BarChart2, TrendingUp, Search, Activity, Sliders,
  ChevronRight, Home, Brain, Newspaper, Award, LogOut, Sparkles, FlaskConical,
  BookOpen, Tag, Lock,
} from 'lucide-react'
import { cn } from '../../lib/utils'
import { useAuth } from '../../contexts/AuthContext'
import { useEntitlements } from '../../hooks/useEntitlements'

const NAV: { label: string; path: string; icon: React.ElementType; section: string; featureKey?: string }[] = [
  { label: 'Overview',           path: '/',            icon: Home,         section: 'MARKET' },
  { label: 'Value Screen',       path: '/value',        icon: Search,       section: 'RESEARCH' },
  { label: 'Deep Dive',          path: '/fundamentals', icon: BarChart2,    section: 'RESEARCH' },
  { label: 'Earnings',           path: '/earnings',     icon: Award,        section: 'RESEARCH',   featureKey: 'earnings' },
  { label: 'Volatility',         path: '/volatility',   icon: Activity,     section: 'ANALYTICS',  featureKey: 'volatility' },
  { label: 'ML Signals',         path: '/signals',      icon: Brain,        section: 'ANALYTICS',  featureKey: 'ml_signals' },
  { label: 'Technical Analysis', path: '/technical',    icon: BarChart2,    section: 'ANALYTICS',  featureKey: 'technical_analysis' },
  { label: 'AI Overview',        path: '/ai-overview',  icon: Sparkles,     section: 'ANALYTICS',  featureKey: 'ai_overview' },
  { label: 'Portfolio',          path: '/portfolio',    icon: Sliders,      section: 'ANALYTICS',  featureKey: 'portfolio_optimize' },
  { label: 'Backtesting',        path: '/backtesting',  icon: FlaskConical, section: 'ANALYTICS',  featureKey: 'backtesting' },
  { label: 'News Hub',           path: '/news',         icon: Newspaper,    section: 'NEWS' },
  { label: 'Models',             path: '/models',       icon: BookOpen,     section: 'LEARN' },
  { label: 'Pricing',            path: '/pricing',      icon: Tag,          section: 'LEARN' },
]

const SECTIONS = ['MARKET', 'RESEARCH', 'ANALYTICS', 'NEWS', 'LEARN']

export default function Sidebar() {
  const { pathname } = useLocation()
  const { user, logout } = useAuth()
  const { has, tier } = useEntitlements()

  return (
    <aside className="group/sidebar fixed inset-y-0 left-0 z-40 flex w-14 flex-col overflow-hidden border-r border-border bg-bg-surface transition-[width] duration-200 ease-out hover:w-[220px]">
      {/* Logo */}
      <div className="flex h-14 shrink-0 items-center gap-2.5 border-b border-border px-[15px]">
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-sm bg-accent">
          <TrendingUp size={14} className="text-white" strokeWidth={2.5} />
        </div>
        <span className="whitespace-nowrap font-mono text-sm font-semibold tracking-widest text-ink-primary opacity-0 transition-opacity duration-150 group-hover/sidebar:opacity-100">
          QUANTHUB
        </span>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-x-hidden overflow-y-auto py-4">
        {SECTIONS.map((section) => {
          const items = NAV.filter(n => n.section === section)
          return (
            <div key={section} className="mb-3">
              <div className="h-5 px-4">
                <p className="whitespace-nowrap text-2xs font-semibold uppercase tracking-[0.1em] text-ink-disabled opacity-0 transition-opacity duration-150 group-hover/sidebar:opacity-100">
                  {section}
                </p>
              </div>
              {items.map(({ label, path, icon: Icon, featureKey }) => {
                const active  = path === '/' ? pathname === '/' : pathname.startsWith(path)
                const locked  = featureKey ? !has(featureKey) : false
                return (
                  <NavLink key={path} to={path}>
                    <div
                      title={locked ? `${label} — Premium` : label}
                      className={cn(
                        'mx-2 flex items-center gap-3 rounded px-2 py-[7px] text-sm transition-colors duration-150',
                        active
                          ? 'bg-[rgba(56,139,253,.1)] text-accent'
                          : locked
                            ? 'text-ink-disabled hover:bg-bg-elevated hover:text-ink-muted'
                            : 'text-ink-secondary hover:bg-bg-elevated hover:text-ink-primary',
                      )}
                    >
                      <div className={cn(
                        'flex h-[18px] w-[18px] shrink-0 items-center justify-center',
                        active ? 'text-accent' : locked ? 'text-ink-disabled' : 'text-ink-muted',
                      )}>
                        <Icon size={15} strokeWidth={active ? 2.2 : 1.8} />
                      </div>
                      <span className={cn(
                        'min-w-0 flex-1 whitespace-nowrap opacity-0 transition-opacity duration-150 group-hover/sidebar:opacity-100',
                        active ? 'font-semibold' : 'font-medium',
                      )}>
                        {label}
                      </span>
                      {locked && tier !== 'premium' && (
                        <Lock
                          size={10}
                          className="ml-auto shrink-0 text-ink-disabled opacity-0 transition-opacity duration-150 group-hover/sidebar:opacity-100"
                        />
                      )}
                      {active && !locked && (
                        <ChevronRight
                          size={12}
                          className="ml-auto shrink-0 text-accent opacity-0 transition-opacity duration-150 group-hover/sidebar:opacity-60"
                        />
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
      <div className="shrink-0 border-t border-border px-[13px] py-3">
        {user && (
          <div className="mb-1.5 flex items-center gap-2">
            <button
              onClick={logout}
              title="Sign out"
              className="shrink-0 text-ink-disabled transition-colors hover:text-loss"
            >
              <LogOut size={13} />
            </button>
            <p className="min-w-0 flex-1 truncate whitespace-nowrap text-2xs text-ink-secondary opacity-0 transition-opacity duration-150 group-hover/sidebar:opacity-100">
              {user.email}
            </p>
          </div>
        )}
        <div className="space-y-0.5 opacity-0 transition-opacity duration-150 group-hover/sidebar:opacity-100">
          <p className="whitespace-nowrap text-2xs text-ink-disabled">NSE · BSE · Real-time</p>
          <p className="whitespace-nowrap text-2xs text-ink-disabled opacity-60">v0.1.0 · India Markets</p>
        </div>
      </div>
    </aside>
  )
}
