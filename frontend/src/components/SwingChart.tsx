import { useEffect, useRef } from 'react'
import {
  createChart,
  ColorType,
  CrosshairMode,
  LineStyle,
  type UTCTimestamp,
  type CandlestickSeriesPartialOptions,
} from 'lightweight-charts'
import type { StockDetail, CandleBar, IndicatorPoint } from '../lib/api'

function toUTC(t: number): UTCTimestamp { return t as UTCTimestamp }

function asCandles(bars: CandleBar[]) {
  return bars.map(b => ({ time: toUTC(b.time), open: b.open, high: b.high, low: b.low, close: b.close }))
}

function asSeries(pts: IndicatorPoint[]) {
  return pts.map(p => ({ time: toUTC(p.time), value: p.value }))
}

interface Props {
  data: StockDetail
}

const CHART_BG    = '#0f1117'
const GRID_COLOR  = '#1e2130'
const TEXT_COLOR  = '#94a3b8'
const UP_COLOR    = '#22c55e'
const DOWN_COLOR  = '#ef4444'
const EMA9_COLOR  = '#f59e0b'
const EMA21_COLOR = '#3b82f6'
const EMA50_COLOR = '#a855f7'
const RSI_COLOR   = '#38bdf8'
const MACD_UP     = '#22c55e'
const MACD_DOWN   = '#ef4444'

const SHARED_OPTS = {
  layout:     { background: { type: ColorType.Solid, color: CHART_BG }, textColor: TEXT_COLOR },
  grid:       { vertLines: { color: GRID_COLOR }, horzLines: { color: GRID_COLOR } },
  crosshair:  { mode: CrosshairMode.Normal },
  timeScale:  { borderColor: GRID_COLOR, timeVisible: true },
  rightPriceScale: { borderColor: GRID_COLOR },
}

export default function SwingChart({ data }: Props) {
  const priceRef = useRef<HTMLDivElement>(null)
  const rsiRef   = useRef<HTMLDivElement>(null)
  const macdRef  = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!priceRef.current || !rsiRef.current || !macdRef.current) return
    if (!data.candles.length) return

    // ── Price chart ──────────────────────────────────────────────────
    const priceChart = createChart(priceRef.current, {
      ...SHARED_OPTS,
      width:  priceRef.current.clientWidth,
      height: priceRef.current.clientHeight,
    })

    const candleSeries = priceChart.addCandlestickSeries({
      upColor:   UP_COLOR,
      downColor: DOWN_COLOR,
      borderUpColor:   UP_COLOR,
      borderDownColor: DOWN_COLOR,
      wickUpColor:   UP_COLOR,
      wickDownColor: DOWN_COLOR,
    } as CandlestickSeriesPartialOptions)
    candleSeries.setData(asCandles(data.candles))

    const ema9Series = priceChart.addLineSeries({ color: EMA9_COLOR, lineWidth: 1 })
    ema9Series.setData(asSeries(data.ema9))

    const ema21Series = priceChart.addLineSeries({ color: EMA21_COLOR, lineWidth: 1 })
    ema21Series.setData(asSeries(data.ema21))

    const ema50Series = priceChart.addLineSeries({ color: EMA50_COLOR, lineWidth: 1, lineStyle: LineStyle.Dashed })
    ema50Series.setData(asSeries(data.ema50))

    // ── RSI chart ────────────────────────────────────────────────────
    const rsiChart = createChart(rsiRef.current, {
      ...SHARED_OPTS,
      width:  rsiRef.current.clientWidth,
      height: rsiRef.current.clientHeight,
    })

    const rsiSeries = rsiChart.addLineSeries({ color: RSI_COLOR, lineWidth: 1 })
    rsiSeries.setData(asSeries(data.rsi))

    const ob = rsiChart.addLineSeries({ color: DOWN_COLOR, lineWidth: 1, lineStyle: LineStyle.Dotted })
    ob.setData(data.rsi.map(p => ({ time: toUTC(p.time), value: 70 })))
    const os = rsiChart.addLineSeries({ color: UP_COLOR, lineWidth: 1, lineStyle: LineStyle.Dotted })
    os.setData(data.rsi.map(p => ({ time: toUTC(p.time), value: 30 })))

    // ── MACD histogram ───────────────────────────────────────────────
    const macdChart = createChart(macdRef.current, {
      ...SHARED_OPTS,
      width:  macdRef.current.clientWidth,
      height: macdRef.current.clientHeight,
    })

    const histSeries = macdChart.addHistogramSeries({
      color: MACD_UP,
    })
    histSeries.setData(
      data.macd_hist.map(p => ({
        time:  toUTC(p.time),
        value: p.value,
        color: p.value >= 0 ? MACD_UP : MACD_DOWN,
      })),
    )

    // Sync time scales across all three charts
    const charts = [priceChart, rsiChart, macdChart]
    charts.forEach(c => {
      c.timeScale().subscribeVisibleLogicalRangeChange(range => {
        if (!range) return
        charts.forEach(other => {
          if (other !== c) other.timeScale().setVisibleLogicalRange(range)
        })
      })
    })

    // Fit content
    charts.forEach(c => c.timeScale().fitContent())

    // Resize observer
    const ro = new ResizeObserver(() => {
      if (priceRef.current) priceChart.applyOptions({ width: priceRef.current.clientWidth })
      if (rsiRef.current)   rsiChart.applyOptions({ width: rsiRef.current.clientWidth })
      if (macdRef.current)  macdChart.applyOptions({ width: macdRef.current.clientWidth })
    })
    if (priceRef.current) ro.observe(priceRef.current)

    return () => {
      ro.disconnect()
      charts.forEach(c => c.remove())
    }
  }, [data])

  return (
    <div className="flex flex-col gap-0 w-full bg-[#0f1117] rounded-lg overflow-hidden">
      {/* Legend */}
      <div className="flex items-center gap-4 px-3 py-2 text-xs">
        <span style={{ color: EMA9_COLOR }}>EMA 9</span>
        <span style={{ color: EMA21_COLOR }}>EMA 21</span>
        <span style={{ color: EMA50_COLOR }}>EMA 50</span>
      </div>

      {/* Price + EMAs */}
      <div ref={priceRef} className="w-full" style={{ height: 320 }} />

      {/* RSI */}
      <div className="px-3 pt-2 pb-0 text-xs text-slate-400">RSI (14)</div>
      <div ref={rsiRef} className="w-full" style={{ height: 100 }} />

      {/* MACD */}
      <div className="px-3 pt-2 pb-0 text-xs text-slate-400">MACD Histogram</div>
      <div ref={macdRef} className="w-full" style={{ height: 100 }} />
    </div>
  )
}
