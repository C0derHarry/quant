import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Sparkles, KeyRound, ExternalLink, Check, Loader2 } from 'lucide-react'
import { cn } from '../../lib/utils'
import {
  getProviders, saveMyAIKey,
  type ProviderId, type ProviderConfig,
} from '../../lib/api'

const PROVIDER_ORDER: ProviderId[] = ['google', 'anthropic', 'openai']

interface Props {
  /** Optional: hide the disclosure toggle if the user is just changing provider. */
  initialProvider?: ProviderId
  onSaved?: () => void
}

export default function ProviderSetup({ initialProvider, onSaved }: Props) {
  const qc = useQueryClient()
  const { data: providers, isLoading } = useQuery({
    queryKey: ['ai-providers'],
    queryFn:  getProviders,
    staleTime: Infinity,
  })

  const [showAll, setShowAll]       = useState<boolean>(!!initialProvider && initialProvider !== 'google')
  const [provider, setProvider]     = useState<ProviderId>(initialProvider ?? 'google')
  const [apiKey, setApiKey]         = useState('')
  const [model, setModel]           = useState<string>('')

  const cfg: ProviderConfig | undefined = providers?.[provider]

  // When provider config arrives or changes, default model to first free (else first paid).
  useEffect(() => {
    if (!cfg) return
    if (model && cfg.models.some(m => m.id === model)) return
    const free = cfg.models.find(m => m.tier === 'free')
    setModel((free ?? cfg.models[0]).id)
  }, [provider, cfg, model])

  const saveMut = useMutation({
    mutationFn: () => saveMyAIKey({ provider, model, api_key: apiKey.trim() }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['ai-key'] })
      setApiKey('')
      onSaved?.()
    },
  })

  if (isLoading || !providers) {
    return (
      <div className="flex items-center justify-center rounded-lg border border-border bg-bg-surface py-16">
        <Loader2 size={20} className="animate-spin text-ink-muted" />
      </div>
    )
  }

  const visibleProviders = showAll ? PROVIDER_ORDER : (['google'] as ProviderId[])
  const canSave = !!apiKey.trim() && !!model && !saveMut.isPending

  return (
    <div className="space-y-5 rounded-lg border border-border bg-bg-surface p-6">
      <div className="flex items-start gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-accent/30 bg-accent/10">
          <KeyRound size={16} className="text-accent" />
        </div>
        <div>
          <h2 className="text-base font-semibold text-ink-primary">Connect an AI provider</h2>
          <p className="mt-0.5 text-xs text-ink-muted">
            Bring your own API key. It's saved to your account (visible only to you) and used
            only when you click "Let AI Analyse".
          </p>
        </div>
      </div>

      {/* Provider tabs */}
      <div className="flex flex-wrap items-center gap-2">
        {visibleProviders.map(p => {
          const pcfg = providers[p]
          const active = p === provider
          return (
            <button
              key={p}
              onClick={() => setProvider(p)}
              className={cn(
                'flex items-center gap-2 rounded border px-3 py-1.5 text-xs font-medium transition-all',
                active
                  ? 'border-accent bg-accent/10 text-accent'
                  : 'border-border text-ink-muted hover:text-ink-secondary',
              )}
            >
              {pcfg.label}
              {pcfg.free_tier_available && (
                <span className={cn(
                  'rounded px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider',
                  active ? 'bg-accent/20 text-accent' : 'bg-gain/15 text-gain',
                )}>
                  free tier
                </span>
              )}
            </button>
          )
        })}
        {!showAll && (
          <button
            onClick={() => setShowAll(true)}
            className="ml-1 text-xs text-ink-muted underline-offset-2 hover:text-accent hover:underline"
          >
            Have an Anthropic / OpenAI key?
          </button>
        )}
      </div>

      {cfg && (
        <>
          {/* Free-tier note */}
          <div className={cn(
            'rounded border px-3 py-2 text-[11px] leading-relaxed',
            cfg.free_tier_available
              ? 'border-gain/30 bg-gain/5 text-ink-secondary'
              : 'border-warn/30 bg-warn/5 text-ink-secondary',
          )}>
            {cfg.free_tier_note}
          </div>

          {/* Instructions */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold uppercase tracking-wider text-ink-disabled">
                How to get a key
              </p>
              <a
                href={cfg.key_url}
                target="_blank" rel="noreferrer"
                className="flex items-center gap-1 text-[11px] text-accent hover:underline"
              >
                Open {cfg.label.split(' ')[0]} console
                <ExternalLink size={11} />
              </a>
            </div>
            <ol className="space-y-1.5 rounded border border-border bg-bg-elevated/40 px-4 py-3">
              {cfg.instructions.map((step, i) => (
                <li key={i} className="flex gap-2 text-[11px] leading-relaxed text-ink-secondary">
                  <span className="font-mono text-[10px] text-ink-disabled">{i + 1}.</span>
                  <span>{step}</span>
                </li>
              ))}
            </ol>
          </div>

          {/* Key input */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold uppercase tracking-wider text-ink-disabled">
              API key
            </label>
            <input
              type="password"
              autoComplete="off"
              spellCheck={false}
              value={apiKey}
              onChange={e => setApiKey(e.target.value)}
              placeholder="Paste your API key here"
              className="w-full rounded border border-border bg-bg-elevated px-3 py-2 font-mono text-xs text-ink-primary placeholder:text-ink-disabled focus:border-accent focus:outline-none"
            />
          </div>

          {/* Model dropdown */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold uppercase tracking-wider text-ink-disabled">
              Model
            </label>
            <div className="grid gap-2 sm:grid-cols-2">
              {cfg.models.map(m => {
                const active = m.id === model
                return (
                  <button
                    key={m.id}
                    onClick={() => setModel(m.id)}
                    className={cn(
                      'flex items-center justify-between gap-2 rounded border px-3 py-2 text-left transition-all',
                      active
                        ? 'border-accent bg-accent/10'
                        : 'border-border bg-bg-elevated hover:border-ink-muted',
                    )}
                  >
                    <span className="flex flex-col gap-0.5">
                      <span className={cn('text-xs font-medium', active ? 'text-accent' : 'text-ink-primary')}>
                        {m.label}
                      </span>
                      <span className="font-mono text-[10px] text-ink-disabled">{m.id}</span>
                    </span>
                    <span className={cn(
                      'shrink-0 rounded px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider',
                      m.tier === 'free' ? 'bg-gain/15 text-gain' : 'bg-bg-elevated text-ink-muted',
                    )}>
                      {m.tier}
                    </span>
                  </button>
                )
              })}
            </div>
          </div>

          {/* Save */}
          <div className="flex items-center gap-3">
            <button
              onClick={() => saveMut.mutate()}
              disabled={!canSave}
              className={cn(
                'flex items-center gap-2 rounded-lg border px-5 py-2.5 text-sm font-semibold transition-all',
                canSave
                  ? 'border-accent/50 bg-accent/10 text-accent hover:bg-accent/20'
                  : 'border-border text-ink-disabled cursor-not-allowed',
              )}
            >
              {saveMut.isPending ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
              Save & continue
            </button>
            {saveMut.isSuccess && (
              <span className="flex items-center gap-1 text-xs text-gain">
                <Check size={12} /> Saved
              </span>
            )}
            {saveMut.error && (
              <span className="text-xs text-loss">{(saveMut.error as Error).message}</span>
            )}
          </div>
        </>
      )}
    </div>
  )
}
