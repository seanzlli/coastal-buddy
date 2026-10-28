// The water sensors shown in the sensor list and the focus chart.
// minSpan keeps the chart's y-axis from zooming in on rounding noise
// (pH only moves in steps of 0.01, so a tight axis would look like chaos).
export const SENSORS = [
  { key: 'temp', label: 'Temperature', unit: '°C', decimals: 1, minSpan: 2 },
  { key: 'sal', label: 'Salinity', unit: 'PSU', decimals: 2, minSpan: 1 },
  { key: 'turb', label: 'Turbidity', unit: 'NTU', decimals: 1, minSpan: 1 },
  { key: 'ph', label: 'pH', unit: '', decimals: 2, minSpan: 0.2 },
  { key: 'bio', label: 'Bio-loading', unit: 'kg/m²', decimals: 2, minSpan: 2 },
  { key: 'wind', label: 'Wind speed', unit: 'km/h', decimals: 1, minSpan: 10 },
]

export const LABEL = {
  ...Object.fromEntries(SENSORS.map((s) => [s.key, s.label])),
  wdir: 'Wind direction',
  feed: 'Data feed',
}

export const fmt = (v, d) => (v === null || v === undefined ? null : Number(v).toFixed(d))
