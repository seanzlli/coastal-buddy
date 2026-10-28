import { fmt } from '../lib/measures'
import { getStatus, windDirLabel } from '../lib/status'
import { Wind } from './icons'

// Compass dial: the arrow points the way the wind is blowing towards.
// Wind matters here because turbidity follows it almost exactly.
export default function WindCompass({ speed, dir, alert }) {
  const toward = ((dir ?? 0) + 180) % 360
  const status = getStatus('wind', speed)
  return (
    <section className={`card animate-rise p-5 md:p-6 ${alert ? 'ring-1 ring-red-500/50' : ''}`}>
      <div className="flex items-center gap-3">
        <span className="grid h-9 w-9 place-items-center rounded-full bg-accent/15 text-accent-soft"><Wind className="h-4 w-4" /></span>
        <h2 className="font-display text-lg font-semibold tracking-tight">Wind</h2>
      </div>
      <div className="mt-4 flex items-center gap-5">
        <svg viewBox="0 0 100 100" className="h-28 w-28 shrink-0">
          <circle cx="50" cy="50" r="44" fill="rgba(7,20,38,0.5)" stroke="rgba(255,255,255,0.08)" strokeWidth="1.5" />
          {Array.from({ length: 12 }, (_, i) => {
            const a = (i * 30 * Math.PI) / 180
            return <line key={i} x1={50 + Math.sin(a) * 38} y1={50 - Math.cos(a) * 38} x2={50 + Math.sin(a) * 41} y2={50 - Math.cos(a) * 41} stroke="rgba(255,255,255,0.18)" strokeWidth="1" />
          })}
          {['N', 'E', 'S', 'W'].map((l, i) => {
            const a = (i * 90 - 90) * (Math.PI / 180)
            return (
              <text key={l} x={50 + Math.cos(a) * 30} y={50 + Math.sin(a) * 30 + 3.5} textAnchor="middle" fontSize="9" fill="#94a3b8" fontWeight="600">{l}</text>
            )
          })}
          {dir != null && (
            <g transform={`rotate(${toward} 50 50)`} style={{ transition: 'transform 0.8s cubic-bezier(.2,.7,.2,1)' }}>
              <path d="M50 20 L56 52 L50 47 L44 52 Z" fill="#2f9bff" />
              <path d="M50 80 L53 55 L50 58 L47 55 Z" fill="rgba(140,200,255,0.35)" />
            </g>
          )}
          <circle cx="50" cy="50" r="2.5" fill="#e6f0ff" />
        </svg>
        <div>
          {speed == null ? (
            <div className="skeleton h-8 w-24" />
          ) : (
            <p className="font-display text-3xl font-semibold tabular-nums">
              {fmt(speed, 1)} <span className="text-sm font-medium text-slate-400">km/h</span>
            </p>
          )}
          <p className="mt-1 text-sm text-slate-300">from {windDirLabel(dir)} · {dir ?? '--'}°</p>
          <span className="mt-2 inline-block rounded-full px-2 py-0.5 text-[11px] font-medium" style={{ background: `${status.c}26`, color: status.c }}>
            {status.t}
          </span>
        </div>
      </div>
    </section>
  )
}
