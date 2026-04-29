import { useState, type FormEvent } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { TrendingUp } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'
import Spinner from '../components/ui/Spinner'

export default function Login() {
  const { login }   = useAuth()
  const navigate    = useNavigate()
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [error, setError]       = useState<string | null>(null)
  const [loading, setLoading]   = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await login(email, password)
      navigate('/')
    } catch (err: any) {
      setError(err.message ?? 'Login failed')
    } finally {
      setLoading(false)
    }
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

        <h1 className="mb-1 text-xl font-semibold text-ink-primary">Welcome back</h1>
        <p className="mb-6 text-sm text-ink-muted">Sign in to your account</p>

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
              placeholder="••••••••"
            />
          </div>

          {error && (
            <p className="rounded border border-loss/30 bg-loss/10 px-3 py-2 text-xs text-loss">{error}</p>
          )}

          <button type="submit" disabled={loading}
            className="w-full rounded border border-accent bg-accent py-2.5 text-sm font-semibold text-white transition-all hover:bg-accent/90 disabled:opacity-60">
            {loading ? <Spinner size={14} /> : 'Sign in'}
          </button>
        </form>

        <p className="mt-5 text-center text-xs text-ink-muted">
          Don't have an account?{' '}
          <Link to="/register" className="text-accent hover:underline">Create one</Link>
        </p>
      </div>
    </div>
  )
}
