import { Component, type ReactNode } from 'react'
import { Routes, Route } from 'react-router-dom'
import SwingScreener from './pages/SwingScreener'

class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null }
  static getDerivedStateFromError(error: Error) { return { error } }
  render() {
    if (this.state.error) {
      return (
        <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-bg-base p-8 text-center">
          <p className="text-sm font-semibold text-loss">Render Error</p>
          <p className="max-w-xl text-xs text-ink-muted">{(this.state.error as Error).message}</p>
          <button
            onClick={() => this.setState({ error: null })}
            className="mt-2 rounded border border-border px-3 py-1.5 text-xs text-ink-secondary hover:text-ink-primary"
          >
            Retry
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

export default function App() {
  return (
    <ErrorBoundary>
      <Routes>
        <Route path="/*" element={<SwingScreener />} />
      </Routes>
    </ErrorBoundary>
  )
}
