/** Format euros as £X.XXm or £XXXk */
export function fmtValue(v) {
  if (v == null) return '—'
  if (Math.abs(v) >= 1_000_000) return `£${(v / 1_000_000).toFixed(2)}m`
  if (Math.abs(v) >= 1_000) return `£${(v / 1_000).toFixed(0)}k`
  return `£${v.toFixed(0)}`
}

/** Format a SHAP value with sign */
export function fmtShap(v) {
  if (v == null) return '—'
  const s = v >= 0 ? '+' : ''
  if (Math.abs(v) >= 1_000_000) return `${s}£${(v / 1_000_000).toFixed(2)}m`
  if (Math.abs(v) >= 1_000) return `${s}£${(v / 1_000).toFixed(0)}k`
  return `${s}£${Math.abs(v).toFixed(0)}`
}

/** Format a percentage */
export function fmtPct(v, digits = 1) {
  if (v == null) return '—'
  return `${(v * 100).toFixed(digits)}%`
}

/** Format a number with commas */
export function fmtNum(v, digits = 1) {
  if (v == null) return '—'
  return Number(v).toLocaleString('en-GB', { maximumFractionDigits: digits })
}

/** Truncate a string */
export function trunc(s, n = 22) {
  if (!s) return ''
  return s.length > n ? s.slice(0, n - 1) + '…' : s
}

/** Position colour class */
export function posClass(p) {
  if (p === 'D') return 'pos-D'
  if (p === 'M') return 'pos-M'
  if (p === 'F') return 'pos-F'
  return 'pos-M'
}

/** Clamp a number */
export function clamp(v, lo, hi) {
  return Math.max(lo, Math.min(hi, v))
}

/** Debounce */
export function debounce(fn, ms = 300) {
  let t
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms) }
}

/** Value band colour */
export function valueBand(estimated, market) {
  if (!estimated || !market) return null
  const ratio = estimated / market
  if (ratio < 0.75) return 'green'
  if (ratio > 1.3) return 'red'
  return 'yellow'
}
