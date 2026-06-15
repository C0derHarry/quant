import { useQuery } from '@tanstack/react-query'
import { getMyEntitlements, getMySubscription } from '../lib/api'

export interface Entitlements {
  tier: 'free' | 'premium'
  isLoading: boolean
  has: (featureKey: string) => boolean
}

export function useEntitlements(): Entitlements {
  const subQuery = useQuery({
    queryKey: ['subscription'],
    queryFn:  getMySubscription,
    staleTime: 5 * 60 * 1000,
    retry: 1,
  })

  const entQuery = useQuery({
    queryKey: ['entitlements'],
    queryFn:  getMyEntitlements,
    staleTime: 5 * 60 * 1000,
    retry: 1,
  })

  const tier = (subQuery.data?.tier ?? 'free') as 'free' | 'premium'
  const map  = entQuery.data ?? {}

  return {
    tier,
    isLoading: subQuery.isLoading || entQuery.isLoading,
    has: (key: string) => map[key] ?? false,
  }
}
