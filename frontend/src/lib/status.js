// Status badges per measure, copied from the VLE page's thresholds.
export function getStatus(type, val) {
  if (val === null || val === undefined) return { t: 'No data', c: '#64748b' }
  if (type === 'temp') {
    if (val >= 24) return { t: 'Thermal Alert', c: '#ef4444' }
    if (val >= 18) return { t: 'Summer Peak', c: '#48bb78' }
    if (val >= 14) return { t: 'Transition', c: '#06b6d4' }
    return { t: 'Deep Winter', c: '#3b82f6' }
  }
  if (type === 'sal') {
    if (val >= 38) return { t: 'Hypersaline', c: '#ef4444' }
    if (val >= 34) return { t: 'Atlantic Pure', c: '#48bb78' }
    if (val >= 30) return { t: 'Transition', c: '#06b6d4' }
    return { t: 'Brackish/Rain', c: '#3b82f6' }
  }
  if (type === 'ph') {
    if (val >= 8.3) return { t: 'Alkaline Warning', c: '#ed8936' }
    if (val >= 7.8) return { t: 'Safe', c: '#48bb78' }
    return { t: 'Acidic Danger', c: '#f56565' }
  }
  if (type === 'turb') {
    if (val >= 15) return { t: 'Storm/Dredge', c: '#ef4444' }
    if (val >= 8) return { t: 'Activity', c: '#f59e0b' }
    if (val >= 2) return { t: 'Standard', c: '#48bb78' }
    return { t: 'Crystal Clear', c: '#3b82f6' }
  }
  if (type === 'bio') {
    // same maintenance levels as the bio-fouling gauge
    if (val >= 40) return { t: 'Urgent: clean sensor', c: '#ef4444' }
    if (val >= 25) return { t: 'Clean sensor', c: '#fb923c' }
    if (val >= 10) return { t: 'Watch', c: '#fbbf24' }
    return { t: 'OK', c: '#34d399' }
  }
  if (type === 'sig') {
    if (val >= 85) return { t: 'Excellent', c: '#48bb78' }
    if (val >= 60) return { t: 'Stable', c: '#48bb78' }
    if (val >= 20) return { t: 'Weak Link', c: '#ed8936' }
    return { t: 'Offline', c: '#f56565' }
  }
  if (type === 'wind') {
    if (val >= 118) return { t: 'Hurricane', c: '#7f1d1d' }
    if (val >= 103) return { t: 'Violent Storm', c: '#991b1b' }
    if (val >= 89) return { t: 'Severe Storm', c: '#b91c1c' }
    if (val >= 75) return { t: 'Storm', c: '#dc2626' }
    if (val >= 62) return { t: 'Gale Force', c: '#ef4444' }
    if (val >= 50) return { t: 'High Wind', c: '#f97316' }
    if (val >= 39) return { t: 'Strong Breeze', c: '#fb923c' }
    if (val >= 29) return { t: 'Fresh Breeze', c: '#48bb78' }
    if (val >= 20) return { t: 'Moderate Breeze', c: '#38bdf8' }
    if (val >= 12) return { t: 'Gentle Breeze', c: '#3b82f6' }
    if (val >= 6) return { t: 'Light Breeze', c: '#64748b' }
    return { t: 'Calm', c: '#94a3b8' }
  }
  return { t: 'Normal', c: '#48bb78' }
}

// Compass label for a wind direction in degrees.
export function windDirLabel(deg) {
  const names = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
  return names[Math.round(((deg ?? 0) % 360) / 45) % 8]
}
