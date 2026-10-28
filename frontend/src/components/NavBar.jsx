import { Beaker, Bell, Grid, List, Logo } from './icons'

const LINKS = [
  { id: 'overview', label: 'Overview', Icon: Grid },
  { id: 'sensors', label: 'Sensors', Icon: List },
  { id: 'alerts', label: 'Alerts', Icon: Bell },
  { id: 'sandbox', label: 'Sandbox', Icon: Beaker },
]

// Sticky top bar on desktop; on phones the section links move to a bottom tab bar,
// where thumbs can reach them.
export default function NavBar({ latest, feed, injecting, alertCount }) {
  const badge = (n) =>
    n > 0 && (
      <span className="ml-1.5 inline-grid min-w-[1.1rem] place-items-center rounded-full bg-red-500 px-1 text-[10px] font-semibold leading-[1.1rem] text-white">
        {n}
      </span>
    )

  return (
    <>
      <header className="sticky top-0 z-30 border-b border-white/5 bg-navy-950/70 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-7xl items-center gap-6 px-4 md:px-8">
          <a href="#overview" className="flex items-center gap-2.5 rounded-xl">
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-linear-to-br from-accent to-[#1a5fb4] text-white shadow-lg shadow-accent/25">
              <Logo className="h-5 w-5" />
            </span>
            <span className="leading-tight">
              <span className="block whitespace-nowrap font-display text-[15px] font-semibold tracking-tight">Coastal Buddy</span>
              <span className="hidden whitespace-nowrap text-[11px] text-slate-400 sm:block">Station SP-02 · Aveiro, Portugal</span>
            </span>
          </a>

          <nav className="hidden items-center gap-1 lg:flex" aria-label="Sections">
            {LINKS.map((l) => (
              <a key={l.id} href={`#${l.id}`}
                className="flex items-center rounded-full px-3.5 py-1.5 text-sm font-medium text-slate-300 transition-colors hover:bg-white/5 hover:text-white">
                {l.label}
                {l.id === 'alerts' && badge(alertCount)}
              </a>
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-2">
            {injecting && (
              <span className="hidden whitespace-nowrap rounded-full bg-amber-400/15 px-3 py-1.5 text-xs font-medium text-amber-200 ring-1 ring-amber-400/30 xl:inline">
                Demo: {injecting}
              </span>
            )}
            <span className="flex items-center gap-2 whitespace-nowrap rounded-full bg-white/5 px-3 py-1.5 ring-1 ring-white/5" title={latest?.time ?? ''}>
              <span className="relative flex h-2 w-2">
                {feed.live && <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />}
                <span className={`relative inline-flex h-2 w-2 rounded-full ${feed.dot}`} />
              </span>
              <span className="text-xs font-medium">{feed.text}</span>
              <span className="hidden font-mono text-[11px] text-slate-400 sm:inline">{latest?.time?.slice(11) ?? '--:--:--'}</span>
            </span>
          </div>
        </div>
      </header>

      <nav className="fixed inset-x-0 bottom-0 z-30 border-t border-white/5 bg-navy-950/85 pb-[env(safe-area-inset-bottom)] backdrop-blur-xl lg:hidden" aria-label="Sections">
        <div className="grid grid-cols-4">
          {LINKS.map((l) => (
            <a key={l.id} href={`#${l.id}`} className="flex flex-col items-center gap-1 py-2.5 text-[11px] font-medium text-slate-400 active:text-white">
              <span className="relative">
                <l.Icon className="h-5 w-5" />
                {l.id === 'alerts' && alertCount > 0 && <span className="absolute -right-1 -top-1 h-2 w-2 rounded-full bg-red-500" />}
              </span>
              {l.label}
            </a>
          ))}
        </div>
      </nav>
    </>
  )
}
