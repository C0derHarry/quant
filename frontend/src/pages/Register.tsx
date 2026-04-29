import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { TrendingUp, MailCheck } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'
import { supabase } from '../lib/supabase'
import Spinner from '../components/ui/Spinner'

function isEmailTaken(msg: string) {
  return /already registered|already exists|email.*taken|user.*exists/i.test(msg)
}

export default function Register() {
  const { register } = useAuth()
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm]   = useState('')
  const [error, setError]       = useState<string | null>(null)
  const [emailTaken, setEmailTaken] = useState(false)
  const [loading, setLoading]   = useState(false)
  const [resetSent, setResetSent] = useState(false)
  const [done, setDone]         = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setEmailTaken(false)
    if (password !== confirm) { setError('Passwords do not match'); return }
    if (password.length < 6)  { setError('Password must be at least 6 characters'); return }
    setLoading(true)
    try {
      await register(email, password)
      setDone(true)
    } catch (err: any) {
      const msg = err.message ?? 'Registration failed'
      if (isEmailTaken(msg)) {
        setEmailTaken(true)
      } else {
        setError(msg)
      }
    } finally {
      setLoading(false)
    }
  }

  async function sendResetLink() {
    setLoading(true)
    await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: `${window.location.origin}/reset-password`,
    })
    setResetSent(true)
    setLoading(false)
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-bg-base p-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="mb-8 flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-sm bg-accent">
            <TrendingUp size={18} className="text-white" strokeWidth={2.5} />
          </div>
          <span className="font-mono text-lg font-semibold tracking-widest text-ink-primary">
            QUANTHUB
          </span>
        </div>

        {done ? (
          /* Verification notice */
          <div className="rounded-lg border border-accent/30 bg-[rgba(56,139,253,.07)] p-6 text-center">
            <MailCheck size={32} className="mx-auto mb-3 text-accent" />
            <h2 className="mb-2 text-base font-semibold text-ink-primary">Check your inbox</h2>
            <p className="text-sm text-ink-secondary">
              A verification email has been sent to{' '}
              <span className="font-semibold text-ink-primary">{email}</span>.
              Please verify your account before signing in.
            </p>
            <Link to="/login"
              className="mt-5 inline-block text-xs text-accent hover:underline">
              Back to sign in
            </Link>
          </div>
        ) : (
          <>
            <h1 className="mb-1 text-xl font-semibold text-ink-primary">Create account</h1>
            <p className="mb-6 text-sm text-ink-muted">Start managing your portfolio</p>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="mb-1.5 block text-xs font-medium text-ink-secondary">Email</label>
                <input
                  type="email" required value={email} onChange={e => setEmail(e.target.value)}
                  className="w-full rounded border border-border bg-bg-elevated px-3 py-2.5 text-sm text-ink-primary outline-none placeholder:text-ink-disabled focus:border-accent"
                  placeholder="you@example.com"
                />
              </div>
              <div>
                <label className="mb-1.5 block text-xs font-medium text-ink-secondary">Password</label>
                <input
                  type="password" required value={password} onChange={e => setPassword(e.target.value)}
                  className="w-full rounded border border-border bg-bg-elevated px-3 py-2.5 text-sm text-ink-primary outline-none placeholder:text-ink-disabled focus:border-accent"
                  placeholder="Min 6 characters"
                />
              </div>
              <div>
                <label className="mb-1.5 block text-xs font-medium text-ink-secondary">Confirm password</label>
                <input
                  type="password" required value={confirm} onChange={e => setConfirm(e.target.value)}
                  className="w-full rounded border border-border bg-bg-elevated px-3 py-2.5 text-sm text-ink-primary outline-none placeholder:text-ink-disabled focus:border-accent"
                  placeholder="••••••••"
                />
              </div>

              {error && (
                <p className="rounded border border-loss/30 bg-loss/10 px-3 py-2 text-xs text-loss">{error}</p>
              )}

              {emailTaken && (
                <div className="rounded border border-warn/30 bg-[rgba(210,153,34,.08)] px-3 py-2.5">
                  {resetSent ? (
                    <div className="flex items-center gap-2">
                      <MailCheck size={13} className="shrink-0 text-gain" />
                      <p className="text-xs text-ink-secondary">
                        Password reset link sent to <span className="font-semibold text-ink-primary">{email}</span>.
                      </p>
                    </div>
                  ) : (
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-xs text-ink-secondary">
                        <span className="font-semibold text-warn">Email already exists.</span>{' '}
                        Forgot your password?
                      </p>
                      <button type="button" onClick={sendResetLink} disabled={loading}
                        className="shrink-0 rounded border border-accent px-2.5 py-1 text-xs font-semibold text-accent transition-all hover:bg-accent/10 disabled:opacity-50">
                        {loading ? <Spinner size={11} /> : 'Reset password'}
                      </button>
                    </div>
                  )}
                </div>
              )}

              <button type="submit" disabled={loading}
                className="w-full rounded border border-accent bg-accent py-2.5 text-sm font-semibold text-white transition-all hover:bg-accent/90 disabled:opacity-60">
                {loading ? <Spinner size={14} /> : 'Create account'}
              </button>
            </form>

            <p className="mt-5 text-center text-xs text-ink-muted">
              Already have an account?{' '}
              <Link to="/login" className="text-accent hover:underline">Sign in</Link>
            </p>
          </>
        )}
      </div>
    </div>
  )
}
