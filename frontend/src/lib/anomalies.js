// Events: the data is fine, but the port should know (orange).
// Everything else is a fault: the data looks wrong (red).
export const EVENT_TYPES = new Set(['strong_wind', 'high_turbidity', 'warm_water', 'cold_water', 'low_salinity'])
export const isEvent = (a) => EVENT_TYPES.has(a.type)

// The detector reports an ongoing anomaly again with every reading. The same
// type + measure + start time is one incident, so keep only its latest report.
export function uniqueIncidents(recent) {
  const seen = new Map()
  for (const p of recent ?? []) {
    for (const a of p.anomalies) {
      const at = a.since ?? p.reading_time ?? p.checked_at
      seen.set(`${a.type}|${a.measure}|${at}`, { ...a, at, lastSeen: p.reading_time ?? p.checked_at })
    }
  }
  return [...seen.values()]
}
