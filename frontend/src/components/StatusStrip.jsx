import { LABEL } from '../lib/measures'
import { isEvent } from '../lib/anomalies'
import { Alert, Check, Pulse } from './icons'

const names = (list) => [...new Set(list.map((a) => LABEL[a.measure] ?? a.measure))].join(', ')

// The one-glance answer to "is everything OK?", next to a few key numbers.
// Faults (data looks wrong) outrank events (real conditions the port should know).
export default function StatusStrip({ detector, incidentCount, readings, signal }) {
  const active = detector?.latest?.anomalies ?? []
  const faults = active.filter((a) => !isEvent(a))
  const events = active.filter(isEvent)

  let s
  if (faults.length > 0) {
    s = { title: `${faults.length} active ${faults.length === 1 ? 'anomaly' : 'anomalies'}`, sub: names(faults), tone: '#ef4444', Icon: Alert }
  } else if (events.length > 0) {
    s = {
      title: `${events.length} reportable ${events.length === 1 ? 'event' : 'events'}`,
      sub: `${events.map((a) => a.type.replaceAll('_', ' ')).join(', ')} · sensors OK`,
      tone: '#fbbf24',
      Icon: Pulse,
    }
  } else if (detector?.latest) {
    s = { title: 'All sensors normal', sub: `Last check ${detector.latest.checked_at.slice(11)}`, tone: '#34d399', Icon: Check }
  } else {
    s = { title: 'Monitoring live', sub: 'Waiting for the anomaly detector', tone: '#94a3b8', Icon: Pulse }
  }

  const stats = [
    ['Sensors', '6'],
    ['Incidents', incidentCount],
    ['Readings in view', readings?.toLocaleString() ?? '—'],
    ['Signal', signal != null ? `${signal} dBm` : '—'],
  ]

  return (
    <section className="card flex animate-rise flex-col gap-5 p-5 md:p-6 lg:flex-row lg:items-center lg:justify-between">
      <div className="flex items-center gap-4">
        <span className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl" style={{ background: `${s.tone}1f`, color: s.tone }}>
          <s.Icon className="h-6 w-6" />
        </span>
        <div className="min-w-0">
          <p className="font-display text-xl font-semibold tracking-tight">{s.title}</p>
          <p className="truncate text-sm text-slate-400">{s.sub}</p>
        </div>
      </div>
      <dl className="grid grid-cols-2 gap-x-10 gap-y-3 sm:grid-cols-4 md:gap-x-12">
        {stats.map(([label, value]) => (
          <div key={label}>
            <dt className="text-xs text-slate-400">{label}</dt>
            <dd className="mt-0.5 font-display text-lg font-semibold tabular-nums">{value}</dd>
          </div>
        ))}
      </dl>
    </section>
  )
}
