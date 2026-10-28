import { useState } from 'react'
import { LABEL } from '../lib/measures'
import { isEvent, uniqueIncidents } from '../lib/anomalies'
import { Alert, Check, Pulse, SENSOR_ICON, Sparkle } from './icons'

// Activity list of incidents from the detector, newest first: faults in red,
// events in orange. The empty state says whether the detector is connected,
// so a quiet list is never ambiguous.
export default function AnomalyFeed({ detector, onSelect }) {
  const active = new Set((detector?.latest?.anomalies ?? []).map((a) => `${a.type}|${a.measure}`))
  const alerts = uniqueIncidents(detector?.recent)
    .sort((a, b) => (a.at < b.at ? 1 : -1))
    .slice(0, 12)
  const online = !!detector?.latest

  return (
    <section id="alerts" className="card animate-rise scroll-mt-24 p-5 md:p-6">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="font-display text-lg font-semibold tracking-tight">Alerts</h2>
        <span className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium ${online ? 'bg-emerald-500/10 text-emerald-300' : 'bg-white/5 text-slate-400'}`}>
          <span className={`h-1.5 w-1.5 rounded-full ${online ? 'bg-emerald-400' : 'bg-slate-500'}`} />
          {online ? 'Detector online' : 'Detector offline'}
        </span>
      </div>

      {alerts.length === 0 ? (
        <div className="flex flex-col items-center py-8 text-center">
          <span className="mb-3 grid h-12 w-12 place-items-center rounded-full bg-emerald-500/10 text-emerald-300">
            <Check className="h-6 w-6" />
          </span>
          <p className="font-medium">All clear</p>
          <p className="mt-0.5 text-sm text-slate-400">{online ? 'No anomalies reported.' : 'Waiting for the first detector check.'}</p>
        </div>
      ) : (
        <ul className="-mx-2 space-y-1">
          {alerts.map((a) => {
            const ev = isEvent(a)
            const tone = ev ? '#fbbf24' : '#ef4444'
            const ongoing = active.has(`${a.type}|${a.measure}`)
            const Icon = SENSOR_ICON[a.measure] ?? (ev ? Pulse : Alert)
            return (
              <li key={`${a.type}|${a.measure}|${a.at}`}>
                <button onClick={() => onSelect(a.measure)}
                  className="flex w-full items-start gap-3 rounded-2xl px-2 py-2.5 text-left transition-colors hover:bg-white/[0.04]">
                  <span className="mt-0.5 grid h-9 w-9 shrink-0 place-items-center rounded-full" style={{ background: `${tone}22`, color: tone }}>
                    <Icon className="h-4 w-4" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-baseline justify-between gap-2">
                      <p className="truncate text-sm font-semibold">
                        {LABEL[a.measure] ?? a.measure}
                        <span className="font-normal text-slate-400"> · {a.type.replaceAll('_', ' ')}</span>
                      </p>
                      <span className="shrink-0 font-mono text-[11px] text-slate-500">{a.at.slice(11, 16)}</span>
                    </div>
                    {a.message && <p className="mt-0.5 text-xs leading-relaxed text-slate-400">{a.message}</p>}
                    <Explanation result={detector?.explanations?.[`${a.type}|${a.measure}|${a.at}`]} />
                    {ongoing && (
                      <span className="mt-1.5 inline-flex items-center gap-1 rounded-full px-2 py-px text-[10px] font-semibold" style={{ background: `${tone}1f`, color: tone }}>
                        <span className="h-1 w-1 animate-pulse rounded-full" style={{ background: tone }} /> Ongoing
                      </span>
                    )}
                  </div>
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}

// Claude's plain-language explanation of one incident (only when the backend has
// an API key). While it's being written, a shimmer; if it failed, nothing extra.
// Folded to two lines so a few alerts don't stretch the page; click to read more.
function Explanation({ result }) {
  const [open, setOpen] = useState(false)
  if (!result || (result.status !== 'pending' && result.status !== 'done')) return null
  const toggle = (e) => {
    e.stopPropagation() // the alert itself is a button that selects the sensor
    if (e.type === 'click' || e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setOpen((o) => !o) }
  }
  return (
    <div className="mt-2 rounded-xl bg-accent/[0.08] px-2.5 py-2 ring-1 ring-accent/20">
      <p className="mb-0.5 flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wider text-accent-soft">
        <Sparkle className="h-3 w-3" /> AI explanation
      </p>
      {result.status === 'pending' ? (
        <div className="space-y-1.5 py-1">
          <div className="skeleton h-2.5 w-full" />
          <div className="skeleton h-2.5 w-4/5" />
        </div>
      ) : (
        <>
          <p className={`text-xs leading-relaxed text-slate-200 ${open ? '' : 'line-clamp-2'}`}>{result.text}</p>
          <span role="button" tabIndex={0} onClick={toggle} onKeyDown={toggle}
            className="mt-1 inline-block text-[11px] font-semibold text-accent-soft hover:underline">
            {open ? 'Show less' : 'Read more'}
          </span>
        </>
      )}
    </div>
  )
}
