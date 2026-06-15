import { useState } from 'react'
import { createPortal } from 'react-dom'
import { Outlet } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ShieldCheck, AlertCircle } from 'lucide-react'
import { getDisclaimerStatus, acceptDisclaimer } from '../lib/api'
import Spinner from './ui/Spinner'

export default function DisclaimerGate() {
  const qc = useQueryClient()
  const [accepting, setAccepting] = useState(false)
  const [error, setError]         = useState<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['disclaimer-status'],
    queryFn:  getDisclaimerStatus,
    staleTime: 30 * 60 * 1000,
    retry: 2,
  })

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bg-base">
        <Spinner size={28} />
      </div>
    )
  }

  if (data?.accepted) {
    return <Outlet />
  }

  async function handleAccept() {
    setAccepting(true)
    setError(null)
    try {
      await acceptDisclaimer()
      await qc.invalidateQueries({ queryKey: ['disclaimer-status'] })
    } catch {
      setError('Failed to record your acceptance. Please try again.')
      setAccepting(false)
    }
  }

  return createPortal(
    <div className="fixed inset-0 z-[200] flex items-center justify-center bg-[rgba(7,9,13,0.92)] p-4">
      <div className="flex w-full max-w-2xl flex-col overflow-hidden rounded-lg border border-border bg-bg-surface shadow-2xl">
        {/* Header */}
        <div className="flex items-center gap-3 border-b border-border bg-bg-elevated px-6 py-4">
          <ShieldCheck size={20} className="shrink-0 text-accent" />
          <div>
            <p className="text-sm font-semibold text-ink-primary">Important Disclaimer</p>
            <p className="text-xs text-ink-muted">Please read carefully before using QuantHub</p>
          </div>
        </div>

        {/* Body — scrollable */}
        <div className="max-h-[60vh] overflow-y-auto px-6 py-5 text-xs leading-relaxed text-ink-secondary">
          <p className="mb-4 font-medium text-ink-primary">
            QuantHub is an educational and analytical platform for Indian markets. By clicking{' '}
            <span className="font-semibold text-accent">"I Agree"</span> you acknowledge and accept
            all of the following:
          </p>

          <ol className="space-y-3">
            <li>
              <span className="font-semibold text-ink-primary">1. Educational purposes only.</span>{' '}
              All content, scores, screens, and model outputs on QuantHub are provided solely for
              education and information. QuantHub does <span className="font-semibold text-loss">not</span>{' '}
              provide investment advice and is not a SEBI-registered investment adviser or research analyst.
            </li>
            <li>
              <span className="font-semibold text-ink-primary">2. Not investment advice or a recommendation.</span>{' '}
              Nothing on this platform constitutes a recommendation, solicitation, or offer to buy, sell, or
              hold any security or financial instrument.
            </li>
            <li>
              <span className="font-semibold text-ink-primary">3. Models are mathematical estimates.</span>{' '}
              All valuations, "fair values," forecasts, signals, and model outputs are results of mathematical
              models based on assumptions that may be incorrect. They are estimates, not facts or guarantees.
            </li>
            <li>
              <span className="font-semibold text-ink-primary">4. Public data may be inaccurate or delayed.</span>{' '}
              Data is aggregated from third-party public sources (including NSE, BSE, Yahoo Finance, and
              others) and may contain errors, omissions, or delays. We do not warrant its accuracy or
              completeness.
            </li>
            <li>
              <span className="font-semibold text-ink-primary">5. Past performance does not guarantee future results.</span>{' '}
              Backtested or historical results shown are hypothetical and do not predict future returns. All
              investments carry risk, including the possible loss of principal.
            </li>
            <li>
              <span className="font-semibold text-ink-primary">6. Do your own due diligence.</span>{' '}
              You are solely responsible for your investment decisions and any resulting gains or losses. The
              platform is a research tool, not a substitute for your own analysis.
            </li>
            <li>
              <span className="font-semibold text-ink-primary">7. Consult a qualified professional.</span>{' '}
              Before making any investment decisions, consult a SEBI-registered investment adviser, research
              analyst, or other qualified financial professional who understands your individual financial
              situation and goals.
            </li>
          </ol>
        </div>

        {/* Footer */}
        <div className="border-t border-border px-6 py-4">
          {error && (
            <div className="mb-3 flex items-center gap-2 rounded border border-loss/30 bg-loss/10 px-3 py-2 text-xs text-loss">
              <AlertCircle size={13} className="shrink-0" />
              {error}
            </div>
          )}
          <div className="flex items-center justify-between gap-4">
            <p className="text-xs text-ink-disabled">
              Acceptance is recorded once per account per disclaimer version.
            </p>
            <button
              onClick={handleAccept}
              disabled={accepting}
              className="flex items-center gap-2 rounded bg-accent px-5 py-2 text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              {accepting && <Spinner size={14} className="text-white" />}
              I Agree
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  )
}
