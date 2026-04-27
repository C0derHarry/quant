import { useState, useEffect, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ExternalLink, Search, X, TrendingUp, TrendingDown, Minus } from 'lucide-react'
import { createPortal } from 'react-dom'
import { cn } from '../lib/utils'
import { getNewsFeed, getStockNews, getNewsImpact, NewsArticle, ImpactData } from '../lib/api'
import Spinner, { PageLoader, ErrorState } from '../components/ui/Spinner'

// ── helpers ───────────────────────────────────────────────────────

function timeAgo(published_at: string): string {
  const diff = Date.now() - new Date(published_at).getTime()
  const mins = Math.floor(diff / 60_000)
  if (mins < 60)  return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs  < 24)  return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

const SENTIMENT_BORDER: Record<string, string> = {
  'Bullish':           '#3FB950',
  'Somewhat-Bullish':  '#3FB950',
  'Neutral':           '#21262D',
  'Somewhat-Bearish':  '#F85149',
  'Bearish':           '#F85149',
}

const SENTIMENT_TEXT: Record<string, string> = {
  'Bullish':           'text-gain',
  'Somewhat-Bullish':  'text-gain',
  'Neutral':           'text-ink-muted',
  'Somewhat-Bearish':  'text-loss',
  'Bearish':           'text-loss',
}

const TOPIC_CHIPS = [
  { label: 'All',       key: null },
  { label: 'Markets',   key: 'financial_markets' },
  { label: 'Economy',   key: 'economy_macro' },
  { label: 'Earnings',  key: 'earnings' },
  { label: 'M&A',       key: 'mergers_and_acquisitions' },
  { label: 'Tech',      key: 'technology' },
]

// ── sub-components ────────────────────────────────────────────────

function SentimentBadge({ label }: { label: string }) {
  const cls = SENTIMENT_TEXT[label] ?? 'text-ink-muted'
  const isBull = label.includes('Bullish')
  const isBear = label.includes('Bearish')
  return (
    <span className={cn(
      'inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-2xs font-medium',
      isBull ? 'bg-gain/10' : isBear ? 'bg-loss/10' : 'bg-bg-elevated',
      cls,
    )}>
      {isBull ? <TrendingUp size={9} /> : isBear ? <TrendingDown size={9} /> : <Minus size={9} />}
      {label}
    </span>
  )
}

function NewsCard({ article, onClick }: { article: NewsArticle; onClick: () => void }) {
  const borderColor = SENTIMENT_BORDER[article.sentiment_label] ?? '#21262D'

  return (
    <div
      role="button"
      onClick={onClick}
      className="group flex cursor-pointer flex-col gap-2.5 rounded-md border border-border bg-bg-surface p-4 transition-all duration-150 hover:border-border-strong hover:shadow-card-lg"
      style={{ borderLeftColor: borderColor, borderLeftWidth: '2px' }}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="truncate text-2xs font-semibold uppercase tracking-wide text-ink-disabled">
          {article.source}
        </span>
        <span className="shrink-0 text-2xs text-ink-disabled">{timeAgo(article.published_at)}</span>
      </div>

      <p className="line-clamp-2 text-sm font-medium leading-snug text-ink-primary">
        {article.title}
      </p>

      <p className="line-clamp-3 text-xs leading-relaxed text-ink-muted">
        {article.summary}
      </p>

      <div className="mt-auto flex flex-wrap items-center justify-between gap-2 pt-1">
        <div className="flex flex-wrap gap-1.5">
          {article.topics.slice(0, 2).map(t => (
            <span key={t.topic} className="text-2xs text-ink-disabled">
              #{t.topic.replace(/_/g, ' ')}
            </span>
          ))}
        </div>
        <SentimentBadge label={article.sentiment_label} />
      </div>
    </div>
  )
}

// ── impact card ───────────────────────────────────────────────────

function ImpactCard({ article, impact }: { article: NewsArticle; impact: ImpactData | undefined }) {
  if (!impact) return (
    <div className="flex h-16 items-center justify-center">
      <Spinner size={16} />
    </div>
  )

  if (impact.market_open) {
    const up = impact.change_pct >= 0
    return (
      <div className="rounded-md border border-border bg-bg-elevated p-4">
        <p className="mb-2 text-2xs font-semibold uppercase tracking-wider text-ink-disabled">
          Live Price Impact
        </p>
        <div className="flex items-baseline gap-3">
          <span className="font-mono text-xl font-semibold text-ink-primary">
            {impact.current_price.toFixed(2)}
          </span>
          <span className={cn(
            'inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs font-semibold',
            up ? 'bg-gain/10 text-gain' : 'bg-loss/10 text-loss',
          )}>
            {up ? <TrendingUp size={11} /> : <TrendingDown size={11} />}
            {up ? '+' : ''}{impact.change_pct.toFixed(2)}%
          </span>
        </div>
        <p className="mt-1 text-xs text-ink-muted">
          Article published {timeAgo(article.published_at)} - current as of {impact.quote_time}
        </p>
      </div>
    )
  }

  // Market closed: sentiment probability bars
  // Use ticker-specific score if available (more relevant than overall article score).
  // Positive score = bullish, negative = bearish — derive direction from sign, not label.
  const rawScore = article.tickers[0]?.sentiment_score ?? article.sentiment_score
  const bullish  = Math.max(0,  rawScore)
  const bearish  = Math.max(0, -rawScore)
  const neutral  = Math.max(0, 1 - bullish - bearish)

  const Bar = ({ label, pct, color }: { label: string; pct: number; color: string }) => (
    <div className="flex items-center gap-3">
      <span className="w-16 text-right text-xs text-ink-muted">{label}</span>
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-bg-overlay">
        <div className="h-full rounded-full transition-all duration-700" style={{ width: `${pct * 100}%`, backgroundColor: color }} />
      </div>
      <span className="w-8 text-right font-mono text-xs text-ink-secondary">
        {Math.round(pct * 100)}%
      </span>
    </div>
  )

  return (
    <div className="rounded-md border border-border bg-bg-elevated p-4">
      <p className="mb-3 text-2xs font-semibold uppercase tracking-wider text-ink-disabled">
        Sentiment Analysis - Market Closed
      </p>
      <div className="space-y-2">
        <Bar label="Bullish" pct={bullish} color="#3FB950" />
        <Bar label="Neutral" pct={neutral} color="#484F58" />
        <Bar label="Bearish" pct={bearish} color="#F85149" />
      </div>
      <p className="mt-3 text-2xs text-ink-disabled">
        Based on AlphaVantage NLP sentiment model - live price data available during market hours (9:15 - 15:30 IST)
      </p>
    </div>
  )
}

// ── article modal ─────────────────────────────────────────────────

function ArticleModal({
  article,
  impact,
  onClose,
}: {
  article: NewsArticle
  impact:  ImpactData | undefined
  onClose: () => void
}) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  const hasTickers = article.tickers.length > 0

  return createPortal(
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center p-4"
      style={{ backgroundColor: 'rgba(7,9,13,0.8)' }}
      onClick={onClose}
    >
      <div
        className="relative flex max-h-[90vh] w-full max-w-2xl flex-col overflow-hidden rounded-lg border border-border bg-bg-surface shadow-card-lg animate-fade-in"
        onClick={e => e.stopPropagation()}
      >
        {/* header */}
        <div className="flex items-start justify-between gap-4 border-b border-border px-6 py-4">
          <div className="flex items-center gap-2.5">
            <span className="text-2xs font-semibold uppercase tracking-wide text-ink-disabled">
              {article.source}
            </span>
            <span className="text-2xs text-ink-disabled">{timeAgo(article.published_at)}</span>
            <SentimentBadge label={article.sentiment_label} />
          </div>
          <button
            onClick={onClose}
            className="shrink-0 rounded p-0.5 text-ink-disabled transition-colors hover:text-ink-primary"
          >
            <X size={14} />
          </button>
        </div>

        {/* scrollable body */}
        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
          {/* impact card */}
          {hasTickers && <ImpactCard article={article} impact={impact} />}

          {/* article content */}
          <div className="space-y-3">
            <h2 className="text-md font-semibold leading-snug text-ink-primary">
              {article.title}
            </h2>
            <p className="text-sm leading-relaxed text-ink-secondary">
              {article.summary}
            </p>
          </div>

          {/* tickers mentioned */}
          {hasTickers && (
            <div className="flex flex-wrap gap-2">
              {article.tickers.map(t => (
                <span key={t.ticker} className={cn(
                  'rounded px-2 py-0.5 font-mono text-xs font-medium',
                  t.sentiment_label.includes('Bullish') ? 'bg-gain/10 text-gain' :
                  t.sentiment_label.includes('Bearish') ? 'bg-loss/10 text-loss' :
                  'bg-bg-elevated text-ink-secondary',
                )}>
                  {t.ticker}
                </span>
              ))}
            </div>
          )}

          {/* read more */}
          <a
            href={article.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 rounded border border-border px-3 py-2 text-xs font-medium text-ink-secondary transition-colors hover:border-accent hover:text-accent"
          >
            Read full article
            <ExternalLink size={11} />
          </a>
        </div>
      </div>
    </div>,
    document.body,
  )
}

// ── main page ─────────────────────────────────────────────────────

export default function NewsHub() {
  const [scope,           setScope]    = useState<'national' | 'international'>('national')
  const [tickerInput,     setInput]    = useState('')
  const [debouncedTicker, setDebounced] = useState('')
  const [topicFilter,     setTopic]    = useState<string | null>(null)
  const [selected,        setSelected] = useState<NewsArticle | null>(null)

  useEffect(() => {
    const t = setTimeout(() => setDebounced(tickerInput.trim().toUpperCase()), 400)
    return () => clearTimeout(t)
  }, [tickerInput])

  const feedQuery = useQuery({
    queryKey: ['news-feed', scope],
    queryFn:  () => getNewsFeed(scope),
    staleTime: 15 * 60_000,
  })

  const stockQuery = useQuery({
    queryKey: ['news-stock', debouncedTicker],
    queryFn:  () => getStockNews(debouncedTicker),
    enabled:  !!debouncedTicker,
    staleTime: 15 * 60_000,
  })

  const primaryTicker = selected?.tickers[0]?.ticker ?? ''
  const impactQuery = useQuery({
    queryKey: ['news-impact', selected?.id],
    queryFn:  () => getNewsImpact(primaryTicker, selected!.published_at),
    enabled:  !!selected && !!primaryTicker,
    staleTime: 5 * 60_000,
  })

  const isLoading = debouncedTicker ? stockQuery.isLoading : feedQuery.isLoading
  const error     = debouncedTicker ? stockQuery.error     : feedQuery.error
  const rawArticles = (debouncedTicker ? stockQuery.data : feedQuery.data)?.articles ?? []
  const articles = topicFilter
    ? rawArticles.filter(a => a.topics.some(t => t.topic === topicFilter))
    : rawArticles

  const handleScopeChange = useCallback((s: 'national' | 'international') => {
    setScope(s)
    setTopic(null)
    setInput('')
  }, [])

  return (
    <div className="animate-fade-up space-y-6">
      {/* page header */}
      <div>
        <h1 className="text-xl font-semibold text-ink-primary">Market News</h1>
        <p className="mt-0.5 text-sm text-ink-muted">
          Financial headlines powered by AlphaVantage with NLP sentiment analysis
        </p>
      </div>

      {/* controls */}
      <div className="flex flex-wrap items-center gap-3">
        {/* scope toggle */}
        <div className="flex rounded-md border border-border bg-bg-elevated p-0.5">
          {(['national', 'international'] as const).map(s => (
            <button
              key={s}
              onClick={() => handleScopeChange(s)}
              className={cn(
                'rounded px-3 py-1.5 text-xs font-medium capitalize transition-all',
                scope === s
                  ? 'bg-accent/10 text-accent'
                  : 'text-ink-muted hover:text-ink-secondary',
              )}
            >
              {s}
            </button>
          ))}
        </div>

        {/* ticker filter */}
        <div className="relative flex-1 max-w-xs">
          <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-disabled" />
          <input
            value={tickerInput}
            onChange={e => setInput(e.target.value)}
            placeholder="Filter by ticker (e.g. AAPL, INFY)"
            className="w-full rounded border border-border bg-bg-elevated py-2 pl-7 pr-3 text-xs text-ink-primary placeholder:text-ink-disabled focus:border-accent focus:outline-none"
          />
          {tickerInput && (
            <button
              onClick={() => setInput('')}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-ink-disabled hover:text-ink-primary"
            >
              <X size={11} />
            </button>
          )}
        </div>

        {/* topic chips */}
        <div className="flex flex-wrap gap-1.5">
          {TOPIC_CHIPS.map(chip => (
            <button
              key={chip.label}
              onClick={() => setTopic(chip.key)}
              className={cn(
                'rounded px-2.5 py-1 text-2xs font-medium transition-all',
                topicFilter === chip.key
                  ? 'bg-accent/10 text-accent'
                  : 'bg-bg-elevated text-ink-muted hover:text-ink-secondary',
              )}
            >
              {chip.label}
            </button>
          ))}
        </div>
      </div>

      {/* status line */}
      {(feedQuery.data?.cached || stockQuery.data?.cached) && (
        <p className="text-2xs text-ink-disabled">
          Serving cached results - refreshes hourly to preserve API quota
        </p>
      )}

      {/* content */}
      {isLoading && <PageLoader label="Fetching latest headlines..." />}
      {error     && <ErrorState message={(error as Error).message} />}
      {!isLoading && !error && articles.length === 0 && (
        <div className="py-20 text-center text-sm text-ink-muted">
          {debouncedTicker
            ? `No news found for "${debouncedTicker}" - try a US-listed ticker (e.g. AAPL, INFY)`
            : 'No articles found for this filter.'}
        </div>
      )}

      {!isLoading && articles.length > 0 && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {articles.map(article => (
            <NewsCard
              key={article.id}
              article={article}
              onClick={() => setSelected(article)}
            />
          ))}
        </div>
      )}

      {/* article modal */}
      {selected && (
        <ArticleModal
          article={selected}
          impact={impactQuery.data}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  )
}
