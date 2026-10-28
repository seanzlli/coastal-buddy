import { useEffect, useRef, useState } from 'react'
import NavBar from './components/NavBar'
import StatusStrip from './components/StatusStrip'
import FocusChart from './components/FocusChart'
import SensorList from './components/SensorList'
import AnomalyFeed from './components/AnomalyFeed'
import WindCompass from './components/WindCompass'
import FoulingGauge from './components/FoulingGauge'
import InjectPanel from './components/InjectPanel'
import { SENSORS } from './lib/measures'
import { getStatus } from './lib/status'
import { isEvent, uniqueIncidents } from './lib/anomalies'

// VLE posts a reading every ~30 s; no new reading for 2 minutes means the feed stalled.
const STALE_MS = 120_000

async function getJson(url) {
  const r = await fetch(url)
  if (!r.ok) throw new Error(`${url} returned ${r.status}`)
  return r.json()
}

// Poll a URL on an interval; returns [data, error, loading, reload]. Changing the
// URL (e.g. the chart's range buttons) or calling reload() fetches immediately.
function usePoll(url, intervalMs) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const [tick, setTick] = useState(0)
  useEffect(() => {
    let alive = true
    async function load(first) {
      if (first) setLoading(true)
      try {
        const d = await getJson(url)
        if (alive) {
          setData(d)
          setError(null)
        }
      } catch (e) {
        if (alive) setError(e.message)
      } finally {
        if (alive && first) setLoading(false)
      }
    }
    load(true)
    const id = setInterval(() => load(false), intervalMs)
    return () => {
      alive = false
      clearInterval(id)
    }
  }, [url, intervalMs, tick])
  return [data, error, loading, () => setTick((t) => t + 1)]
}

// 1H history has times like "12:14:32"; longer ranges have a full date.
function shortLabel(time, range) {
  if (range === '1h') return time.slice(0, 5)
  if (range === '1d') return time.slice(11, 16)
  return time.slice(5, 10)
}

export default function App() {
  const [range, setRange] = useState('1h')
  const [selected, setSelected] = useState('temp')

  const [latest, latestErr] = usePoll('/api/latest', 5000)
  const [detector] = usePoll('/api/detector', 5000)
  const [inject, , , reloadInject] = usePoll('/api/inject', 5000)
  const [hour] = usePoll('/api/history?range=1h', 5000) // sparklines, 1h change, fouling rate
  // Long ranges barely change between polls and are slow to fetch, so poll them less.
  const [history, historyErr, loading] = usePoll(`/api/history?range=${range}`, range === '1h' ? 5000 : 30000)

  // Feed health: remember when the reading's timestamp last changed.
  const lastSeen = useRef({ time: null, at: Date.now() })
  const [now, setNow] = useState(Date.now())
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 5000)
    return () => clearInterval(id)
  }, [])
  if (latest?.time && latest.time !== lastSeen.current.time) lastSeen.current = { time: latest.time, at: Date.now() }

  const error = latestErr || historyErr
  let feed = { text: 'Live', dot: 'bg-emerald-400', live: true }
  if (error) feed = { text: 'Backend offline', dot: 'bg-red-500' }
  else if (!latest) feed = { text: 'Connecting', dot: 'bg-slate-500' }
  else if (now - lastSeen.current.at > STALE_MS) feed = { text: 'Feed stalled', dot: 'bg-red-500' }

  const sensor = SENSORS.find((s) => s.key === selected)
  const points = history?.points ?? []

  // Line up detector payloads with chart points by reading time. 1H times have
  // no date, so compare only the "HH:MM:SS" part there.
  const key = (t) => (range === '1h' ? t.slice(-8) : t)
  const byTime = new Map()
  for (const p of detector?.recent ?? []) if (p.reading_time) byTime.set(key(p.reading_time), p)

  // predicted = measured - error (the detector sends error = measured - predicted)
  const predicted = points.map((p) => {
    const e = byTime.get(key(p.time))?.error?.[selected]
    return e == null || p[selected] == null ? null : p[selected] - e
  })
  // Red dots only for faults; events (e.g. a long low-salinity spell) would cover the whole line.
  const anomalies = points.map((p) =>
    byTime.get(key(p.time))?.anomalies.some((a) => a.measure === selected && !isEvent(a)) ? p[selected] : null,
  )

  // Per sensor: is something active right now? A fault outranks an event.
  const alerting = new Map()
  for (const a of detector?.latest?.anomalies ?? []) {
    const fault = !isEvent(a)
    if (fault || !alerting.has(a.measure))
      alerting.set(a.measure, { fault, label: fault ? `Anomaly: ${a.type.replaceAll('_', ' ')}` : a.type.replaceAll('_', ' ') })
  }
  const incidentCount = uniqueIncidents(detector?.recent).length
  const activeFaults = (detector?.latest?.anomalies ?? []).filter((a) => !isEvent(a)).length
  const spark = hour?.points ?? []
  const firstHour = spark.map((p) => p[selected]).find((x) => x != null)
  const hourDelta = latest?.[selected] != null && firstHour != null ? latest[selected] - firstHour : null

  return (
    <>
      <NavBar latest={latest} feed={feed} injecting={inject?.active?.label} alertCount={activeFaults} />

      <main className="mx-auto max-w-7xl px-4 pb-28 pt-6 md:px-8 md:pt-8 lg:pb-12">
        {error && (
          <p role="alert" className="mb-6 rounded-2xl bg-red-500/10 px-4 py-3 text-sm text-red-200 ring-1 ring-red-500/30">
            {error}. Is the backend running on port 8000?
          </p>
        )}

        <div id="overview" className="scroll-mt-24">
          <StatusStrip detector={detector} incidentCount={incidentCount} readings={history?.count} signal={latest?.sig} />
        </div>

        <div className="mt-6 grid gap-6 lg:grid-cols-12">
          <div className="space-y-6 lg:col-span-8">
            <FocusChart
              sensor={sensor}
              value={latest?.[selected]}
              delta={hourDelta}
              labels={points.map((p) => shortLabel(p.time, range))}
              values={points.map((p) => p[selected])}
              predicted={predicted}
              anomalies={anomalies}
              range={range}
              onRange={setRange}
              loading={loading}
              count={history?.count}
              shown={points.length}
            />
            <SensorList
              sensors={SENSORS}
              latest={latest}
              spark={spark}
              statusOf={getStatus}
              alerting={alerting}
              selected={selected}
              onSelect={setSelected}
            />
          </div>
          <aside className="space-y-6 lg:col-span-4">
            <AnomalyFeed detector={detector} onSelect={(m) => SENSORS.some((s) => s.key === m) && setSelected(m)} />
            <InjectPanel inject={inject} reload={reloadInject} now={now} />
            <WindCompass speed={latest?.wind} dir={latest?.wdir} alert={alerting.get('wind')?.fault || alerting.get('wdir')?.fault} />
            <FoulingGauge value={latest?.bio} spark={spark} />
          </aside>
        </div>

        <footer className="mt-12 flex flex-col gap-1 border-t border-white/5 pt-6 text-xs text-slate-500 sm:flex-row sm:justify-between">
          <span>Data: VLE Global simulated sensor feed (sp02.aveiro.vle.global), refreshed every 5 s.</span>
          <span>AI for Water hackathon · UvA / AISO</span>
        </footer>
      </main>
    </>
  )
}
