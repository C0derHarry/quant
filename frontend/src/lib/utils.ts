import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function fmt(n: number, decimals = 2): string {
  return n.toLocaleString('en-IN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })
}

export function fmtPct(n: number, decimals = 2): string {
  const sign = n >= 0 ? '+' : ''
  return `${sign}${fmt(n, decimals)}%`
}

export function fmtCurrency(n: number): string {
  if (Math.abs(n) >= 1e7)  return `₹${(n / 1e7).toFixed(2)}Cr`
  if (Math.abs(n) >= 1e5)  return `₹${(n / 1e5).toFixed(2)}L`
  if (Math.abs(n) >= 1000) return `₹${(n / 1000).toFixed(1)}K`
  return `₹${fmt(n, 0)}`
}

export function fmtLargeNum(n: number): string {
  if (Math.abs(n) >= 1e9) return `${(n / 1e9).toFixed(2)}B`
  if (Math.abs(n) >= 1e6) return `${(n / 1e6).toFixed(2)}M`
  if (Math.abs(n) >= 1e3) return `${(n / 1e3).toFixed(1)}K`
  return String(n)
}

export function isMarketOpen(): boolean {
  const now   = new Date()
  const ist   = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Kolkata' }))
  const h     = ist.getHours()
  const m     = ist.getMinutes()
  const mins  = h * 60 + m
  const day   = ist.getDay()
  return day >= 1 && day <= 5 && mins >= 555 && mins <= 930 // 9:15 – 15:30
}

export const REGIME_COLOR: Record<string, string> = {
  Bull:     '#3FB950',
  Bear:     '#F85149',
  Sideways: '#D29922',
}

export const REGIME_BG: Record<string, string> = {
  Bull:     'rgba(63,185,80,.12)',
  Bear:     'rgba(248,81,73,.12)',
  Sideways: 'rgba(210,153,34,.12)',
}
