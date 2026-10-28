// Minimal line icons (24x24, 1.8 stroke) so every card uses the same visual language.
const make = (paths) =>
  function Icon({ className = 'h-5 w-5' }) {
    return (
      <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="1.8"
        strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        {paths}
      </svg>
    )
  }

export const Logo = make(
  <>
    <path d="M12 3c3.5 4.2 6 7.6 6 10.6A6 6 0 0 1 6 13.6C6 10.6 8.5 7.2 12 3Z" />
    <path d="M7.5 14.5c1.2.9 2.3.9 3.5 0s2.3-.9 3.5 0 2 .7 2.5.3" />
  </>,
)
export const Thermometer = make(<><path d="M14 14.8V4a2 2 0 0 0-4 0v10.8a4 4 0 1 0 4 0Z" /><path d="M12 9v7" /></>)
export const Droplet = make(<><path d="M12 3c3.5 4.2 6 7.6 6 10.6A6 6 0 0 1 6 13.6C6 10.6 8.5 7.2 12 3Z" /><path d="M9 14a3 3 0 0 0 3 3" /></>)
export const Eye = make(<><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Z" /><circle cx="12" cy="12" r="3" /></>)
export const Flask = make(<><path d="M9 3h6" /><path d="M10 3v6l-5.5 9.5A1.7 1.7 0 0 0 6 21h12a1.7 1.7 0 0 0 1.5-2.5L14 9V3" /><path d="M7.5 15h9" /></>)
export const Leaf = make(<><path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.5 19 2c1 2 2 4.2 2 8 0 5.5-4.8 10-10 10Z" /><path d="M2 21c0-3 1.9-5.4 5.1-6" /></>)
export const Wind = make(<><path d="M17.7 7.7A2.5 2.5 0 1 1 19.5 12H2" /><path d="M9.6 4.6A2 2 0 1 1 11 8H2" /><path d="M12.6 19.4A2 2 0 1 0 14 16H2" /></>)
export const Bell = make(<><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" /><path d="M10.3 21a1.9 1.9 0 0 0 3.4 0" /></>)
export const Beaker = make(<><path d="M4.5 3h15" /><path d="M6 3v16a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V3" /><path d="M6 14h12" /></>)
export const Grid = make(<><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /></>)
export const List = make(<><path d="M8 6h13M8 12h13M8 18h13" /><path d="M3 6h.01M3 12h.01M3 18h.01" /></>)
export const Download = make(<path d="M12 4v11m0 0-4-4m4 4 4-4M5 19h14" />)
export const Check = make(<path d="m5 12 4.5 4.5L19 7" />)
export const Alert = make(<><path d="M12 9v4" /><path d="M12 17h.01" /><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" /></>)
export const Pulse = make(<path d="M3 12h4l3-8 4 16 3-8h4" />)
export const Signal = make(<path d="M3 20h.01M8 20v-4M13 20v-8M18 20V8" />)
export const Gauge = make(<><path d="M12 14l4-4" /><path d="M3.3 19a10 10 0 1 1 17.4 0" /></>)
export const Sparkle = make(<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3Z" />)
export const Feed = make(<><path d="M4 11a9 9 0 0 1 9 9" /><path d="M4 4a16 16 0 0 1 16 16" /><circle cx="5" cy="19" r="1" /></>)

// One icon per sensor key, used in the watchlist, the chart and the alerts.
export const SENSOR_ICON = { temp: Thermometer, sal: Droplet, turb: Eye, ph: Flask, bio: Leaf, wind: Wind, wdir: Wind, feed: Feed }
