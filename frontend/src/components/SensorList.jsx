import Sparkline from './Sparkline'
import { SENSOR_ICON } from './icons'
import { fmt } from '../lib/measures'

// Watchlist of sensors: icon, status, last-hour trend, value and 1h change.
// Clicking a row puts that sensor in the large chart above.
export default function SensorList({ sensors, latest, spark, statusOf, alerting, selected, onSelect }) {
  return (
    <section id="sensors" className="card animate-rise scroll-mt-24 p-3 md:p-4">
      <div className="flex items-baseline justify-between px-3 pb-2 pt-2">
        <h2 className="font-display text-lg font-semibold tracking-tight">Sensors</h2>
        <span className="text-xs text-slate-400">last hour</span>
      </div>
      <ul className="space-y-1">
        {sensors.map((s) => {
          const series = spark.map((p) => p[s.key])
          const first = series.find((x) => x != null)
          const value = latest?.[s.key]
          const delta = value != null && first != null ? value - first : null
          const alert = alerting.get(s.key) // { fault: bool, label } or undefined
          const status = statusOf(s.key, value)
          const isSel = selected === s.key
          const tone = alert ? (alert.fault ? '#ef4444' : '#fbbf24') : null
          const Icon = SENSOR_ICON[s.key]
          return (
            <li key={s.key}>
              <button
                onClick={() => onSelect(s.key)}
                aria-pressed={isSel}
                className={`group flex w-full items-center gap-3 rounded-2xl px-3 py-3 text-left transition-all duration-200 sm:gap-4 ${isSel ? 'bg-accent/10 ring-1 ring-accent/30' : 'hover:bg-white/[0.04]'}`}
              >
                <span
                  className={`grid h-10 w-10 shrink-0 place-items-center rounded-full transition-transform group-hover:scale-105 ${alert?.fault ? 'animate-pulse' : ''}`}
                  style={{ background: tone ? `${tone}26` : 'rgb(47 155 255 / 0.12)', color: tone ?? '#8cc8ff' }}
                >
                  <Icon className="h-5 w-5" />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold">{s.label}</p>
                  <p className="flex items-center gap-1.5 truncate text-xs text-slate-400" style={tone ? { color: tone } : undefined}>
                    {!tone && <span className="h-1.5 w-1.5 rounded-full" style={{ background: status.c }} />}
                    {alert ? alert.label : status.t}
                  </p>
                </div>
                <div className="hidden sm:block">
                  <Sparkline values={series} color={tone ?? (isSel ? '#8cc8ff' : '#2f9bff')} />
                </div>
                <div className="w-24 text-right sm:w-28">
                  {value == null ? (
                    <div className="skeleton ml-auto h-5 w-16" />
                  ) : (
                    <p className="font-display font-semibold tabular-nums">
                      {fmt(value, s.decimals)} <span className="text-xs font-normal text-slate-400">{s.unit}</span>
                    </p>
                  )}
                  {delta != null && (
                    <span className="mt-1 inline-block rounded-full bg-white/5 px-1.5 py-px font-mono text-[10px] text-slate-300">
                      {delta >= 0 ? '▲' : '▼'} {Math.abs(delta).toFixed(s.decimals)}
                    </span>
                  )}
                </div>
              </button>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
