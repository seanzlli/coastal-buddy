import { fmt } from '../lib/measures'
import { Leaf } from './icons'

// Bio-loading is growth on the sensor. It builds up steadily (~1.2 kg/m² per day),
// so it works like a maintenance counter: how full is it, and when must it be cleaned?
// Levels are the team's own choice (no official cleaning threshold was given).
const GAUGE_MAX = 60
const LEVELS = [
  { upTo: 10, label: 'OK', color: '#34d399' },
  { upTo: 25, label: 'Watch', color: '#fbbf24' },
  { upTo: 40, label: 'Clean sensor', color: '#fb923c' },
  { upTo: GAUGE_MAX, label: 'Urgent', color: '#ef4444' },
]
const CLEAN_AT = 25
const DEFAULT_RATE_PER_DAY = 1.2 // measured over the whole history

const day = (d) => d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })

export default function FoulingGauge({ value, spark }) {
  const level = LEVELS.find((l) => (value ?? 0) < l.upTo) ?? LEVELS[LEVELS.length - 1]
  const pct = Math.min(100, ((value ?? 0) / GAUGE_MAX) * 100)

  // Growth rate from the last hour, falling back to the long-run rate.
  const series = spark.map((p) => p.bio).filter((x) => x != null)
  const perHour = series.length > 1 ? series[series.length - 1] - series[0] : null
  const perDay = perHour && perHour > 0 ? perHour * 24 : DEFAULT_RATE_PER_DAY

  let advice = null
  if (value != null) {
    if (value < CLEAN_AT) {
      advice = `Cleaning due around ${day(new Date(Date.now() + ((CLEAN_AT - value) / perDay) * 86_400_000))}`
    } else {
      const overSince = new Date(Date.now() - ((value - CLEAN_AT) / perDay) * 86_400_000)
      advice = `Overdue: past the cleaning level since ~${day(overSince)}`
    }
  }

  return (
    <section className="card animate-rise p-5 md:p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="grid h-9 w-9 place-items-center rounded-full bg-accent/15 text-accent-soft"><Leaf className="h-4 w-4" /></span>
          <h2 className="font-display text-lg font-semibold tracking-tight">Bio-fouling</h2>
        </div>
        <span className="rounded-full px-2.5 py-1 text-[11px] font-semibold" style={{ background: `${level.color}22`, color: level.color }}>
          {level.label}
        </span>
      </div>
      {value == null ? (
        <div className="skeleton mt-4 h-8 w-32" />
      ) : (
        <p className="mt-4 font-display text-3xl font-semibold tabular-nums">
          {fmt(value, 2)} <span className="text-sm font-medium text-slate-400">kg/m²</span>
        </p>
      )}

      {/* the bar is split into the four maintenance levels */}
      <div className="relative mt-4 flex h-2 overflow-hidden rounded-full">
        {LEVELS.map((l, i) => {
          const from = i ? LEVELS[i - 1].upTo : 0
          return <div key={l.label} style={{ width: `${((l.upTo - from) / GAUGE_MAX) * 100}%`, background: `${l.color}40` }} />
        })}
        <div className="absolute inset-y-0 left-0 rounded-full transition-[width] duration-700" style={{ width: `${pct}%`, background: level.color }} />
      </div>
      <div className="mt-1.5 flex justify-between font-mono text-[10px] text-slate-500">
        <span>0</span><span>10</span><span>25</span><span>40</span><span>{GAUGE_MAX}</span>
      </div>

      {advice && <p className="mt-4 text-sm font-medium" style={{ color: level.color }}>{advice}</p>}
      <p className="mt-0.5 text-xs text-slate-400">Growing ~{perDay.toFixed(1)} kg/m² per day</p>
    </section>
  )
}
