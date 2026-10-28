import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
} from 'chart.js'
import { Line } from 'react-chartjs-2'
import { fmt } from '../lib/measures'
import { SENSOR_ICON } from './icons'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Filler, Tooltip)
ChartJS.defaults.font.family = '"Inter", system-ui, sans-serif'

const RANGES = [
  { key: '1h', label: '1H' },
  { key: '1d', label: '24H' },
  { key: '1w', label: '7D' },
  { key: 'all', label: 'All' },
]

// Fit the y-axis to the data, but never tighter than the sensor's minSpan.
function yRange(values, minSpan) {
  const v = values.filter((x) => x !== null && x !== undefined)
  if (!v.length) return {}
  const lo = Math.min(...v)
  const hi = Math.max(...v)
  const half = Math.max(((hi - lo) / 2) * 1.25, minSpan / 2)
  const mid = (lo + hi) / 2
  return { min: mid - half, max: mid + half }
}

// Blue fill that fades out towards the bottom of the chart.
function fadeFill({ chart }) {
  const { ctx, chartArea } = chart
  if (!chartArea) return 'rgba(47,155,255,0.15)'
  const g = ctx.createLinearGradient(0, chartArea.top, 0, chartArea.bottom)
  g.addColorStop(0, 'rgba(47,155,255,0.32)')
  g.addColorStop(1, 'rgba(47,155,255,0)')
  return g
}

// Hero card: the selected sensor's value in large type, its change over the past
// hour, the chart, and the range tabs underneath. The detector's predicted line
// and anomaly markers appear on top when the detector provides them.
export default function FocusChart({ sensor, value, delta, labels, values, predicted, anomalies, range, onRange, loading, count, shown }) {
  const hasPred = predicted.some((v) => v !== null)
  const hasAnom = anomalies.some((v) => v !== null)
  const Icon = SENSOR_ICON[sensor.key]
  const idx = RANGES.findIndex((r) => r.key === range)

  const datasets = [
    { label: 'Measured', data: values, borderColor: '#2f9bff', backgroundColor: fadeFill, fill: 'start', tension: 0.35, pointRadius: 0, pointHoverRadius: 4, borderWidth: 2 },
  ]
  if (hasPred)
    datasets.push({ label: 'Predicted', data: predicted, borderColor: '#8cc8ff', borderDash: [5, 5], borderWidth: 1.5, pointRadius: 0, fill: false, spanGaps: true })
  if (hasAnom)
    datasets.push({ label: 'Anomaly', data: anomalies, showLine: false, pointRadius: 6, pointHoverRadius: 8, pointBackgroundColor: '#ef4444', pointBorderColor: '#fff', pointBorderWidth: 1.5 })

  const options = {
    animation: false,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    scales: {
      y: { ...yRange(values, sensor.minSpan), position: 'right', ticks: { color: '#64748b', font: { size: 11 }, maxTicksLimit: 5 }, grid: { color: 'rgba(255,255,255,0.05)' }, border: { display: false } },
      x: { ticks: { color: '#64748b', font: { size: 11 }, maxRotation: 0, maxTicksLimit: 6 }, grid: { display: false }, border: { display: false } },
    },
    plugins: {
      legend: { display: false },
      tooltip: { backgroundColor: '#0c1f38', borderColor: 'rgba(47,155,255,0.35)', borderWidth: 1, padding: 10, cornerRadius: 12, displayColors: false, titleColor: '#94a3b8', bodyColor: '#e6f0ff' },
    },
  }

  const up = delta != null && delta >= 0

  return (
    <section className="card animate-rise p-5 md:p-7">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="flex items-center gap-2 text-sm text-slate-400">
            <span className="grid h-7 w-7 place-items-center rounded-full bg-accent/15 text-accent-soft"><Icon className="h-4 w-4" /></span>
            {sensor.label}
          </p>
          {value == null ? (
            <div className="skeleton mt-3 h-12 w-48" />
          ) : (
            <p className="mt-2 font-display text-5xl font-semibold tracking-tight tabular-nums md:text-6xl">
              {fmt(value, sensor.decimals)}
              <span className="ml-2 text-xl font-medium text-slate-400 md:text-2xl">{sensor.unit}</span>
            </p>
          )}
          {delta != null && (
            <p className="mt-2 flex items-center gap-2 text-sm">
              <span className="rounded-full bg-accent/15 px-2 py-0.5 font-medium tabular-nums text-accent-soft">
                {up ? '▲' : '▼'} {Math.abs(delta).toFixed(sensor.decimals)} {sensor.unit}
              </span>
              <span className="text-slate-400">past hour</span>
            </p>
          )}
        </div>
        <div className="hidden flex-col items-end gap-1.5 text-xs text-slate-400 sm:flex">
          <Legend swatch="h-0.5 w-4 bg-accent" label="Measured" />
          <Legend swatch="h-0 w-4 border-t-2 border-dashed border-accent-soft" label={hasPred ? 'Predicted' : 'Predicted (no data yet)'} />
          <Legend swatch="h-2 w-2 rounded-full bg-red-500" label="Anomaly" />
        </div>
      </div>

      <div className="relative mt-6 h-64 md:h-80">
        <Line data={{ labels, datasets }} options={options} />
        {loading && <div className="skeleton absolute inset-0 opacity-60" />}
      </div>

      {/* range tabs with a sliding indicator */}
      <div className="relative mt-5 grid grid-cols-4 rounded-full bg-navy-950/60 p-1 ring-1 ring-white/5" role="tablist">
        <span
          className="absolute inset-y-1 left-1 rounded-full bg-accent shadow-lg shadow-accent/30 transition-transform duration-300 ease-out"
          style={{ width: 'calc((100% - 0.5rem) / 4)', transform: `translateX(${Math.max(idx, 0) * 100}%)` }}
        />
        {RANGES.map((r) => (
          <button key={r.key} role="tab" aria-selected={range === r.key} onClick={() => onRange(r.key)}
            className={`relative z-10 rounded-full py-1.5 text-sm font-semibold transition-colors ${range === r.key ? 'text-white' : 'text-slate-400 hover:text-white'}`}>
            {r.label}
          </button>
        ))}
      </div>
      {count != null && (
        <p className="mt-3 text-center font-mono text-[11px] text-slate-500">
          {count === shown ? `${count.toLocaleString()} readings` : `${count.toLocaleString()} readings · averaged to ${shown.toLocaleString()} points`}
        </p>
      )}
    </section>
  )
}

function Legend({ swatch, label }) {
  return (
    <span className="flex items-center gap-2">
      <span className={`inline-block ${swatch}`} />
      {label}
    </span>
  )
}
