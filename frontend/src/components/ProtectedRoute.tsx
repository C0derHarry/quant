import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import Spinner from './ui/Spinner'

export default function ProtectedRoute() {
  const { user, loading } = useAuth()
  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bg-base">
        <Spinner size={28} />
      </div>
    )
  }
  return user ? <Outlet /> : <Navigate to="/login" replace />
}
