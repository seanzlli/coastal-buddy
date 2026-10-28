// Tiny trend line (last hour) drawn as plain SVG: cheaper than a full chart per row.
export default function Sparkline({ values, color = '#2f9bff', width = 120, height = 32 }) {
  const v = values.filter((x) => x !== null && x !== undefined)
  if (v.length < 2) return <svg viewBox={`0 0 ${width} ${height}`} className="h-8 w-28" />
  const min = Math.min(...v)
  const span = Math.max(...v) - min
  const step = width / (values.length - 1)
  let d = ''
  values.forEach((x, i) => {
    if (x === null || x === undefined) return
    // a perfectly flat series (common for pH) is drawn through the middle
    const y = span ? height - 3 - ((x - min) / span) * (height - 6) : height / 2
    d += `${d ? 'L' : 'M'}${(i * step).toFixed(1)} ${y.toFixed(1)}`
  })
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-8 w-28" preserveAspectRatio="none">
      <path d={d} fill="none" stroke={color} strokeWidth="1.6" vectorEffect="non-scaling-stroke" strokeLinejoin="round" />
    </svg>
  )
}
