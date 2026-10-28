import { useState } from 'react'
import { Beaker } from './icons'

// How long the detector took to catch each type in our timing test.
const FAST = 90 // seconds: anything quicker is good for a live demo
const speed = (s) => (s < 60 ? `~${Math.round(s / 10) * 10} s` : `~${Math.round(s / 60)} min`)

// Demo control: start a fake incident on top of the live feed and watch the
// detector catch it. The backend applies it to the data, so nothing here fakes
// the result: the detector really has to find it.
export default function InjectPanel({ inject, reload, now }) {
  const [busy, setBusy] = useState(false)
  const active = inject?.active
  const types = inject?.types ?? []
  const fast = types.filter((t) => t.catch_seconds <= FAST)
  const slow = types.filter((t) => t.catch_seconds > FAST)

  async function call(method, body) {
    setBusy(true)
    try {
      await fetch('/api/inject', {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: body ? JSON.stringify(body) : undefined,
      })
      reload()
    } finally {
      setBusy(false)
    }
  }

  let left = 0
  let progress = 0
  if (active) {
    const end = new Date(active.end.replace(' ', 'T'))
    const start = new Date(active.start.replace(' ', 'T'))
    left = Math.max(0, Math.round((end - now) / 1000))
    progress = Math.min(100, Math.max(0, ((now - start) / (end - start)) * 100))
  }

  const tile = (t) => (
    <button key={t.type} onClick={() => call('POST', { type: t.type })} disabled={busy}
      title={`${t.what}. Caught by: ${t.detect}`}
      className="group rounded-2xl bg-navy-950/50 p-3 text-left ring-1 ring-white/5 transition-all duration-200 hover:-translate-y-0.5 hover:bg-accent/10 hover:ring-accent/40 active:translate-y-0 disabled:opacity-50">
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-semibold leading-tight">{t.label}</p>
        <span className={`shrink-0 rounded-full px-1.5 py-px text-[10px] font-semibold ${t.catch_seconds <= FAST ? 'bg-emerald-500/15 text-emerald-300' : 'bg-amber-400/15 text-amber-300'}`}>
          {speed(t.catch_seconds)}
        </span>
      </div>
      <p className="mt-1 line-clamp-2 text-[11px] leading-snug text-slate-400">{t.what}</p>
    </button>
  )

  return (
    <section id="sandbox" className="card animate-rise scroll-mt-24 p-5 md:p-6">
      <div className="flex items-center gap-3">
        <span className="grid h-9 w-9 place-items-center rounded-full bg-accent/15 text-accent-soft"><Beaker className="h-4 w-4" /></span>
        <div>
          <h2 className="font-display text-lg font-semibold leading-tight tracking-tight">Sandbox</h2>
          <p className="text-xs text-slate-400">Inject a fake incident into the live feed</p>
        </div>
      </div>
      <p className="mt-3 text-sm text-slate-400">The detector doesn't know it's fake. See whether it catches it.</p>

      {active ? (
        <div className="mt-4 rounded-2xl bg-amber-400/10 p-4 ring-1 ring-amber-400/30">
          <div className="flex items-center justify-between">
            <p className="font-semibold text-amber-200">{active.label}</p>
            <p className="font-mono text-xs tabular-nums text-amber-200">{Math.floor(left / 60)}:{String(left % 60).padStart(2, '0')} left</p>
          </div>
          <p className="mt-0.5 text-sm text-slate-300">{active.what}</p>
          <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/10">
            <div className="h-full rounded-full bg-amber-300 transition-[width] duration-1000 ease-linear" style={{ width: `${progress}%` }} />
          </div>
          <p className="mt-2 text-xs text-slate-400">
            Should be caught by <span className="text-slate-200">{active.detect}</span> in {speed(active.catch_seconds)}
          </p>
          <button onClick={() => call('DELETE')} disabled={busy}
            className="mt-3 w-full rounded-full bg-white/10 py-2 text-sm font-semibold transition hover:bg-white/15 active:scale-[0.99] disabled:opacity-50">
            Stop injection
          </button>
        </div>
      ) : types.length === 0 ? (
        <div className="mt-4 grid grid-cols-2 gap-2">{[0, 1, 2, 3].map((i) => <div key={i} className="skeleton h-16 rounded-2xl" />)}</div>
      ) : (
        <>
          <p className="mb-2 mt-4 text-[11px] font-medium uppercase tracking-wider text-slate-500">Caught within a minute</p>
          <div className="grid grid-cols-2 gap-2">{fast.map(tile)}</div>
          {slow.length > 0 && (
            <>
              <p className="mb-2 mt-4 text-[11px] font-medium uppercase tracking-wider text-slate-500">Slower: takes minutes to show</p>
              <div className="grid grid-cols-2 gap-2">{slow.map(tile)}</div>
            </>
          )}
        </>
      )}
    </section>
  )
}
